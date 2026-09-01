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
SCRIPT = ROOT / "scripts" / "shadow-public-ready-grep-gate.py"
SPEC = importlib.util.spec_from_file_location("public_ready", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class PublicReadyTests(unittest.TestCase):
    def test_clean_public_text_passes(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "README.md"
            path.write_text("Shadow stores bounded local proof.\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertTrue(report["ok"], report)

    def test_private_home_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "README.md"
            path.write_text("checkout: /" + "Users/realname/secret\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["findings"][0]["reason"], "private filesystem path")

    def test_secret_shape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "notes.md"
            path.write_text("token: gh" + "p_12345678901234567890\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["findings"][0]["reason"], "secret-shaped value")

    def test_evidence_stream_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "activity.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["findings"][0]["reason"], "forbidden release file")

    def test_current_metadata_is_consistent(self) -> None:
        self.assertEqual(mod.metadata_errors(ROOT), [])


class AmbientGitRedirectPinTests(unittest.TestCase):
    def test_git_paths_ignores_an_ambient_repository_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            decoy = Path(tmp) / "decoy"
            for candidate, name in ((real, "real-file"), (decoy, "decoy-file")):
                subprocess.run(["git", "init", "-q", str(candidate)], check=True, capture_output=True)
                subprocess.run(["git", "-C", str(candidate), "config", "user.email", "t@example.invalid"], check=True, capture_output=True)
                subprocess.run(["git", "-C", str(candidate), "config", "user.name", "T"], check=True, capture_output=True)
                (candidate / name).write_text("x", encoding="utf-8")
                subprocess.run(["git", "-C", str(candidate), "add", "-A"], check=True, capture_output=True)
                subprocess.run(["git", "-C", str(candidate), "commit", "-qm", "init"], check=True, capture_output=True)
            with mock.patch.dict(
                os.environ,
                {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)},
            ):
                paths = [path.name for path in mod.git_paths(real)]
            self.assertEqual(paths, ["real-file"])


if __name__ == "__main__":
    unittest.main()
