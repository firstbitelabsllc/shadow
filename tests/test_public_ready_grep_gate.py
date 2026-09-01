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

from shadow_scrub_lib import PRIVATE_PATH_RE  # noqa: E402  (gate put scripts/ on sys.path)


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

    def test_home_rooted_operator_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "findings.md"
            path.write_text("the clone sits in ~/" + "Workspace/Dev\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"], report)
        self.assertEqual(report["findings"][0]["reason"], "private filesystem path")

    def test_tool_owned_dot_paths_pass(self) -> None:
        # These are user-facing instructions throughout the public docs. A gate
        # that fires on them would refuse every future change to those files.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "guide.md"
            path.write_text(
                "The board is `~/.shadow`; plans live under `~/.shadow/plans/<name>/`.\n"
                "Activation writes `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,\n"
                "and `~/.grok/AGENTS.md`; install.sh links into `~/.local/bin`.\n"
                "`SHADOW_PORTFOLIO_ROOT` defaults to `~/Development`.\n",
                encoding="utf-8",
            )
            report = mod.scan(root, [path], metadata=False)
        self.assertTrue(report["ok"], report)

    def test_mixed_document_reports_only_the_operator_line(self) -> None:
        # The shape of the document that reached review: two lines teaching the
        # tool-owned board path, one line naming a machine's own directory.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "findings.md"
            path.write_text(
                "receipts are on one machine's local board (`~/.shadow`, revisions\n"
                "`~/.shadow/plans/<name>/` cannot be scaffolded by the CLI at all.\n"
                "the clone sits in the machine's `~/" + "Workspace/Dev`, so it boarded.\n",
                encoding="utf-8",
            )
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"], report)
        self.assertEqual(
            [(item["line"], item["reason"]) for item in report["findings"]],
            [(3, "private filesystem path")],
        )

    def test_gate_tilde_shape_stays_inside_the_canonical_matcher(self) -> None:
        # The gate is deliberately narrower than shadow_scrub_lib, whose callers
        # bound receipts and refuse every `~/`. Pin both directions so the two
        # cannot drift into disagreeing about what a home-rooted path is.
        operator = "the clone sits in ~/" + "Workspace/Dev"
        documented = "the board is `~/.shadow/plans/<name>/`"
        self.assertTrue(mod.contains_private_path(operator))
        self.assertTrue(PRIVATE_PATH_RE.search(operator))
        self.assertFalse(mod.contains_private_path(documented))
        self.assertTrue(PRIVATE_PATH_RE.search(documented))

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
