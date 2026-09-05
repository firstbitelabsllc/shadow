"""Real macOS sandbox tests for isolated candidate execution, not provider proof."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "openrouter_candidate", Path(__file__).resolve().parents[1] / "scripts/dev/openrouter-candidate.py")
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


@unittest.skipUnless(sys.platform == "darwin", "native candidate proof requires macOS sandbox-exec")
class CandidateTests(unittest.TestCase):
    def test_edit_then_test_process_leaves_input_unchanged(self):
        files = {"answer.py": "VALUE = 0\n", "tests/check.py": "from answer import VALUE\nassert VALUE == 42\n"}
        before = dict(files)
        result = candidate.evaluate(files, {"answer.py"}, "tests/check.py",
                                    json.dumps({"answer.py": "VALUE = 42\n"}))
        self.assertEqual(result["test_process_exit_code"], 0)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["candidate"], {"answer.py": "VALUE = 42\n"})
        self.assertEqual(files, before)

    def test_unfixed_candidate_fails_real_test(self):
        result = candidate.evaluate({"answer.py": "VALUE = 0\n", "check.py": "from answer import VALUE\nassert VALUE == 42\n"},
                                    {"answer.py"}, "check.py", '{"answer.py":"VALUE = 1\\n"}')
        self.assertNotEqual(result["test_process_exit_code"], 0)

    def test_untrusted_proposals_refuse_before_execution(self):
        files = {"answer.py": "VALUE = 0\n", "check.py": "raise RuntimeError('must not run')\n"}
        for proposal in ('{"../escape":"x"}', '{".git/config":"x"}', '{"check.py":"pass"}',
                         '{"answer.py":null}', '{"answer.py":"x","answer.py":"y"}',
                         '{"command":"/bin/sh"}', '{"answer.py":"x","extra.py":"x"}'):
            with self.subTest(proposal=proposal), self.assertRaises(candidate.Refused):
                candidate.evaluate(files, {"answer.py"}, "check.py", proposal)

    def test_early_exit_zero_is_not_acceptance(self):
        for exit_call in ("os._exit(0)", "sys.exit(0)"):
            result = candidate.evaluate(
                {"answer.py": "VALUE = 0", "check.py": "from answer import VALUE\nassert VALUE == 42"},
                {"answer.py"}, "check.py",
                json.dumps({"answer.py": "import os, sys\nVALUE = 0\n" + exit_call}))
            self.assertEqual(result["test_process_exit_code"], 0)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["requires"], "independent ordinary-seat diff review")

    def test_keychain_framework_query_is_denied(self):
        # Bypass ctypes' uname probe so this reaches the Keychain boundary even
        # though the default-deny profile also blocks that unrelated syscall.
        # Only a deliberately nonexistent service is queried; no item is read.
        hostile = '''import os, types
os.uname = lambda: types.SimpleNamespace(release="26.0")
import ctypes
sec = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFDictionaryCreateMutable.restype = ctypes.c_void_p
query = cf.CFDictionaryCreateMutable(None, 0, None, None)
cf.CFDictionarySetValue(ctypes.c_void_p(query), ctypes.c_void_p.in_dll(sec, "kSecClass"), ctypes.c_void_p.in_dll(sec, "kSecClassGenericPassword"))
service = cf.CFStringCreateWithCString(None, b"ow46-offline-nonexistent-service", 0x08000100)
cf.CFDictionarySetValue(ctypes.c_void_p(query), ctypes.c_void_p.in_dll(sec, "kSecAttrService"), ctypes.c_void_p(service))
out = ctypes.c_void_p()
rc = sec.SecItemCopyMatching(ctypes.c_void_p(query), ctypes.byref(out))
assert rc == -50, f"Keychain boundary changed: {rc}"
VALUE = 42
'''
        result = candidate.evaluate(
            {"answer.py": "VALUE = 0", "check.py": "from answer import VALUE\nassert VALUE == 42"},
            {"answer.py"}, "check.py", json.dumps({"answer.py": hostile}))
        self.assertEqual(result["test_process_exit_code"], 0, result)

    def test_inventory_file_directory_collision_refuses(self):
        with self.assertRaises(candidate.Refused):
            candidate.evaluate({"a": "x", "a/b.py": "x", "check.py": "pass"},
                               {"a"}, "check.py", '{"a":"y"}')

    def test_native_denials_precede_effects(self):
        with tempfile.TemporaryDirectory(prefix="openrouter-candidate-denials-") as temp:
            external = Path(temp) / "private.txt"
            external.write_text("PRIVATE_SENTINEL")
            marker = Path(temp) / "escaped"
            hostile = f'''import errno, os, pathlib, socket, subprocess
def denied(action):
    try:
        action()
    except OSError as error:
        assert error.errno in (errno.EPERM, errno.EACCES), error
        return
    raise AssertionError("forbidden operation succeeded")
denied(lambda: pathlib.Path({str(external)!r}).read_text())
denied(lambda: pathlib.Path({str(external)!r}).stat())
denied(lambda: os.listdir("/private/tmp"))
denied(lambda: pathlib.Path({str(marker)!r}).write_text("escape"))
denied(lambda: pathlib.Path("answer.py").unlink())
denied(lambda: pathlib.Path("check.py").write_text("pass"))
denied(lambda: subprocess.run(["/bin/sh", "-c", "exit 0"], check=True))
denied(lambda: subprocess.run(["/usr/bin/security", "help"], check=True))
denied(lambda: subprocess.run(["/usr/bin/git", "--version"], check=True))
denied(lambda: socket.create_connection(("127.0.0.1", 9), timeout=1))
VALUE = 42
'''
            result = candidate.evaluate({"answer.py": "VALUE = 0\n", "check.py": "from answer import VALUE\nassert VALUE == 42\n"},
                                        {"answer.py"}, "check.py", json.dumps({"answer.py": hostile}))
            self.assertEqual(result["test_process_exit_code"], 0, result)
            self.assertFalse(marker.exists())
            self.assertEqual(external.read_text(), "PRIVATE_SENTINEL")


if __name__ == "__main__":
    unittest.main()
