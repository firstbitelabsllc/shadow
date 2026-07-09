"""Tests for scripts/vidux-public-ready-grep-gate.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-public-ready-grep-gate.py"


class PublicReadyGrepGateTests(unittest.TestCase):
    def test_clean_current_surface_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "config.md").write_text("Plans are files.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["matches"], [])

    def test_forbidden_term_in_current_surface_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Add Linear sync back here.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["file"], "README.md")

    def test_ask_leo_is_in_scope_but_hygiene_exempt(self):
        # Round-3 panel finding: ASK-LEO.md was grouped with true history
        # files (ARCHIVE.md/CHANGELOG.md) and excluded from SCAN_TARGETS
        # entirely, hiding a real private-path leak. It's a LIVE, ongoing
        # queue (per its own header), not a closed record -- it must be
        # scanned. But its resolved Q&A entries are still historical enough
        # that HYGIENE_PATTERNS (e.g. "Linear") shouldn't retroactively fire.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            (root / "ASK-LEO.md").write_text(
                "## Q1\nAnswer: migrated off Linear sync in 2026-04.\n"
                "Private path leak: /Users/leokwan/Development/x\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        files_matched = {m["file"] for m in payload["matches"]}
        self.assertEqual(files_matched, {"ASK-LEO.md"})
        patterns_matched = {m["pattern"] for m in payload["matches"]}
        self.assertEqual(patterns_matched, {"private home path"})

    def test_leo_flow_pattern_catches_hyphenated_slash_command_form(self):
        # Round-3 panel finding: the original pattern only matched the
        # spaced "Leo Flow" form and missed "/leo-flow"/"leo-flow", which is
        # the form actually used in prose -- 6 live occurrences in SKILL.md
        # passed the gate green while sitting in a live, current section.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Use `/leo-flow` for lane routing.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "private Leo Flow lane")

    def test_historical_plan_dirs_are_out_of_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "projects" / "old-cleanup" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("Historical Linear removal notes stay here.\n", encoding="utf-8")
            (root / "README.md").write_text("Current docs stay clean.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")


if __name__ == "__main__":
    unittest.main()
