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
