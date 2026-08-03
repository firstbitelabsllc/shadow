from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "pilot-puppy"
BROWSE = ROOT / "bin" / "pilot-puppy-browse"


def run_cli(binary: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        [str(binary), *args],
        cwd=ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


class PythonResolutionTests(unittest.TestCase):
    def test_invalid_override_fails_closed_on_dispatcher(self) -> None:
        result = run_cli(CLI, "status", env={"PILOT_PUPPY_PYTHON": "/usr/bin/false"})
        self.assertEqual(result.returncode, 127)
        self.assertIn("is not a Python 3.10+ interpreter", result.stderr)

    def test_invalid_override_fails_closed_on_browse_launcher(self) -> None:
        result = run_cli(BROWSE, "--help", env={"PILOT_PUPPY_PYTHON": "/usr/bin/false"})
        self.assertEqual(result.returncode, 127)
        self.assertIn("is not a Python 3.10+ interpreter", result.stderr)

    def test_valid_override_is_honored(self) -> None:
        if sys.version_info < (3, 10):
            self.skipTest("test runner itself is below the 3.10 floor")
        result = run_cli(CLI, "doctor", "--json", env={"PILOT_PUPPY_PYTHON": sys.executable})
        expected = "%d.%d.%d" % sys.version_info[:3]
        self.assertIn(expected, result.stdout)
        self.assertNotEqual(result.returncode, 127, result.stderr)

    def test_resolution_finds_an_interpreter_when_unset(self) -> None:
        env = dict(os.environ)
        env.pop("PILOT_PUPPY_PYTHON", None)
        result = subprocess.run(
            [str(CLI), "doctor", "--json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if shutil.which("python3") is None:
            self.assertEqual(result.returncode, 127)
        else:
            self.assertIn(result.returncode, (0, 1))
            self.assertIn('"python"', result.stdout)
