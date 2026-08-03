from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
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
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            marker = root / "interpreter-used"
            shim = root / "python-shim"
            shim.write_text(
                "#!/bin/sh\n"
                f"printf x >> {shlex.quote(str(marker))}\n"
                f"exec {shlex.quote(sys.executable)} \"$@\"\n",
                encoding="utf-8",
            )
            shim.chmod(0o755)
            result = run_cli(
                CLI,
                "status",
                "--json",
                "--root",
                str(root),
                env={"PILOT_PUPPY_PYTHON": str(shim)},
            )
            used = marker.is_file()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"schema": "pilot-puppy.status.v1"', result.stdout)
        self.assertTrue(used)

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

    def test_versioned_interpreter_wins_over_low_bare_python3(self) -> None:
        candidates = [
            name
            for name in ("python3.10", "python3.11", "python3.12", "python3.13", "python3.14")
            if shutil.which(name)
        ]
        if not candidates:
            self.skipTest("no versioned Python 3 interpreter is installed")
        versioned = max(candidates, key=lambda name: int(name.rsplit(".", 1)[1]))
        real_interpreter = Path(shutil.which(versioned) or versioned).resolve()
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            marker = root / "versioned-interpreter-used"
            low = bin_dir / "python3"
            low.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            low.chmod(0o755)
            wrapper = bin_dir / versioned
            wrapper.write_text(
                "#!/bin/sh\n"
                f"printf x >> {shlex.quote(str(marker))}\n"
                f"exec {shlex.quote(str(real_interpreter))} \"$@\"\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            env = {
                "PATH": f"{bin_dir}{os.pathsep}{Path(real_interpreter).parent}{os.pathsep}{os.environ.get('PATH', '')}",
                "PILOT_PUPPY_PYTHON": "",
            }
            result = run_cli(CLI, "status", "--json", "--root", str(root), env=env)
            used = marker.is_file()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"schema": "pilot-puppy.status.v1"', result.stdout)
        self.assertTrue(used)
