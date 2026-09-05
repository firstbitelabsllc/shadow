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
    def test_edit_then_real_fixed_test_leaves_input_unchanged(self):
        files = {"answer.py": "VALUE = 0\n", "tests/check.py": "from answer import VALUE\nassert VALUE == 42\n"}
        before = dict(files)
        result = candidate.evaluate(files, {"answer.py"}, "tests/check.py",
                                    json.dumps({"answer.py": "VALUE = 42\n"}))
        self.assertEqual(result["test_exit_code"], 0)
        self.assertEqual(result["candidate"], {"answer.py": "VALUE = 42\n"})
        self.assertEqual(files, before)

    def test_unfixed_candidate_fails_real_test(self):
        result = candidate.evaluate({"answer.py": "VALUE = 0\n", "check.py": "from answer import VALUE\nassert VALUE == 42\n"},
                                    {"answer.py"}, "check.py", '{"answer.py":"VALUE = 1\\n"}')
        self.assertNotEqual(result["test_exit_code"], 0)

    def test_untrusted_proposals_refuse_before_execution(self):
        files = {"answer.py": "VALUE = 0\n", "check.py": "raise RuntimeError('must not run')\n"}
        for proposal in ('{"../escape":"x"}', '{".git/config":"x"}', '{"check.py":"pass"}',
                         '{"answer.py":null}', '{"answer.py":"x","answer.py":"y"}',
                         '{"command":"/bin/sh"}', '{"answer.py":"x","extra.py":"x"}'):
            with self.subTest(proposal=proposal), self.assertRaises(candidate.Refused):
                candidate.evaluate(files, {"answer.py"}, "check.py", proposal)

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
            self.assertEqual(result["test_exit_code"], 0, result)
            self.assertFalse(marker.exists())
            self.assertEqual(external.read_text(), "PRIVATE_SENTINEL")


if __name__ == "__main__":
    unittest.main()
