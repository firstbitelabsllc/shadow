"""The opt-in proof must not report success when Python removes assertions."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


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
