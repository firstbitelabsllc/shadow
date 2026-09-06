"""The opt-in proof must not report success when Python removes assertions."""
import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile

SPEC = importlib.util.spec_from_file_location(
    'openrouter_native', Path(__file__).resolve().parents[1] / 'scripts/dev/openrouter_native.py')
native = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = native
SPEC.loader.exec_module(native)


class NativeOutputTests(unittest.TestCase):
    def test_large_complete_output_survives_regular_file_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            result = native.run_native(
                [sys.executable, '-I', '-c', "import os; os.write(1,b'x'*262144); os.write(2,b'y'*262144)"],
                env={**os.environ, 'OPENCODE_EXPERIMENTAL_NATIVE_LLM': 'false'}, cwd=directory, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'x' * 262144)
        self.assertEqual(result.stderr, 'y' * 262144)

    def test_both_streams_have_inherited_hard_limits_and_flood_refuses(self):
        for fd in (1, 2):
            code = ("import os,resource; "
                    f"assert resource.getrlimit(resource.RLIMIT_FSIZE)==({native.OUTPUT_BYTES},{native.OUTPUT_BYTES}); "
                    f"os.write({fd},b'x'*{native.OUTPUT_BYTES * 2})")
            with self.subTest(fd=fd), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, 'hard file-size limit'):
                    native.run_native([sys.executable, '-I', '-c', code],
                                      env={**os.environ, 'OPENCODE_EXPERIMENTAL_NATIVE_LLM': 'false'}, cwd=directory, timeout=10)


class HarnessInterpreterTests(unittest.TestCase):
    def test_optimized_interpreter_refuses_before_argument_or_native_processing(self):
        harness = Path(__file__).resolve().parents[1] / "scripts/dev/test-openrouter-native.py"
        env = {**os.environ, "PYTHONOPTIMIZE": ""}
        normal = subprocess.run([sys.executable, str(harness), "--help"], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(normal.returncode, 0, normal.stderr)
        for flags, setting in ((["-O"], ""), (["-OO"], ""), ([], "1")):
            with self.subTest(flags=flags, setting=setting):
                result = subprocess.run([sys.executable, *flags, str(harness), "--help"],
                                        env={**env, "PYTHONOPTIMIZE": setting},
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refuses optimized Python", result.stderr)
                self.assertNotIn('"passed": true', result.stdout)
