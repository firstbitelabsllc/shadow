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
            subprocess.run(["git", "-C", str(decoy), "tag", "shadow-v1.0.0"], check=True, capture_output=True)
            # The real repo has no release tag; the decoy has one. An
            # unsanitized probe follows GIT_DIR into the decoy and invents a
            # release baseline that does not exist in the real repository.
            with mock.patch.dict(
                os.environ,
                {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)},
            ):
                pressure = shadow_ci.repository_pressure(real)
            self.assertEqual(pressure["RELEASE_BASELINE"], "")


class ReleaseBaselineTests(unittest.TestCase):
    """`~act9`: GitHub Latest and the release baseline must name one commit."""

    @staticmethod
    def _repo(root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        for args in (("config", "user.email", "t@example.invalid"), ("config", "user.name", "T")):
            subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    @classmethod
    def _commit(cls, root: Path, name: str) -> str:
        (root / name).write_text(name, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", name], check=True, capture_output=True)
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_a_lightweight_release_tag_still_resets_the_baseline(self) -> None:
        """Without `--tags`, `describe` sees annotated tags only.

        A release cut with a lightweight tag was invisible, so pressure kept
        measuring from the PREVIOUS release and never reset to zero.
        """

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            self._repo(root)
            self._commit(root, "one")
            subprocess.run(["git", "-C", str(root), "tag", "-a", "shadow-v1.0.0", "-m", "r"],
                           check=True, capture_output=True)
            self._commit(root, "two")
            cut = self._commit(root, "three")
            subprocess.run(["git", "-C", str(root), "tag", "shadow-v1.1.0"],  # lightweight
                           check=True, capture_output=True)

            pressure = shadow_ci.repository_pressure(root)
            self.assertEqual(pressure["RELEASE_BASELINE"], "shadow-v1.1.0")
            self.assertEqual(pressure["RELEASE_BASELINE_COMMIT"], cut)
            self.assertEqual(pressure["ACCEPTED_CHANGE_COUNT"], "0")

    def test_a_pre_release_legacy_tag_never_becomes_the_baseline(self) -> None:
        """`v4.0.3` and friends predate 1.0.0. Measuring 1.x pressure from one
        is worse than measuring none, so no baseline is the honest answer."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            self._repo(root)
            self._commit(root, "one")
            subprocess.run(["git", "-C", str(root), "tag", "v4.0.3"], check=True, capture_output=True)
            self._commit(root, "two")

            pressure = shadow_ci.repository_pressure(root)
            self.assertEqual(pressure["RELEASE_BASELINE"], "")
            self.assertEqual(pressure["RELEASE_BASELINE_COMMIT"], "")
            self.assertEqual(pressure["ACCEPTED_CHANGE_COUNT"], "0")


if __name__ == "__main__":
    unittest.main()
