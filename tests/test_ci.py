"""shadow-ci — release-pressure probes ignore an ambient repository redirect."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-ci.py"
SPEC = importlib.util.spec_from_file_location("shadow_ci", SCRIPT)
assert SPEC and SPEC.loader
shadow_ci = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = shadow_ci
SPEC.loader.exec_module(shadow_ci)


class AmbientGitRedirectPinTests(unittest.TestCase):
    def test_repository_pressure_ignores_an_ambient_repository_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            decoy = Path(tmp) / "decoy"
            subprocess.run(["git", "init", "-q", str(real)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-q", str(decoy)], check=True, capture_output=True)
            for args in (("config", "user.email", "t@example.invalid"), ("config", "user.name", "T")):
                subprocess.run(["git", "-C", str(decoy), *args], check=True, capture_output=True)
            (decoy / "f").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", str(decoy), "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(decoy), "commit", "-qm", "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(decoy), "tag", "v1.0.0"], check=True, capture_output=True)
            # The real repo has no release tag; the decoy has one. An
            # unsanitized probe follows GIT_DIR into the decoy and invents a
            # release baseline that does not exist in the real repository.
            with mock.patch.dict(
                os.environ,
                {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)},
            ):
                pressure = shadow_ci.repository_pressure(real)
            self.assertEqual(pressure["RELEASE_BASELINE"], "")


if __name__ == "__main__":
    unittest.main()
