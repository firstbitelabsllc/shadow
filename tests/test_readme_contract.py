"""Keep the share-ready README and public help tied to real Shadow surfaces."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHADOW = ROOT / "bin" / "shadow"


class ShareReadyDocumentationTests(unittest.TestCase):
    def test_readme_leads_with_authority_loop_and_footer(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "one durable workboard per computer",
            "PLAN.md",
            "```mermaid",
            "shadow status",
            "shadow throw",
            "shadow accept",
            "shadow status --in-flight --json",
            "Ongoing tasks",
            "Active tasks: none",
            "Proof boundaries",
            "Host integration",
            "scripts/shadow-verify-two-seat.py",
            "--live --goal-file",
        )
        for phrase in required:
            self.assertIn(phrase, text)
        self.assertNotIn("npm test", text)
        self.assertNotIn("/Users/", text)

        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Every Shadow chat response ends with a compact `Ongoing tasks` projection", skill)
        self.assertIn("shadow status --in-flight --json", skill)

    def test_quickstart_has_a_real_claim_and_close_loop(self) -> None:
        text = (ROOT / "docs" / "guide" / "quickstart.md").read_text(encoding="utf-8")
        for phrase in (
            "shadow init --here",
            "$EDITOR PLAN.md",
            "shadow lint PLAN.md",
            "shadow status --by",
            "shadow throw",
            "shadow amp",
            "shadow accept",
            "shadow return",
            "shadow status --in-flight --json",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("proof: cmd npm test", text)

    def test_public_help_is_quiet_and_advertises_supported_flags(self) -> None:
        verbs = (
            "browse", "status", "init", "lint", "goal", "amp", "throw",
            "return", "priority", "accept", "lifecycle", "host", "buckets",
            "doctor",
        )
        for verb in verbs:
            result = subprocess.run(
                [str(SHADOW), "help", verb], cwd=ROOT,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, f"{verb}: {result.stderr}")
            self.assertEqual("", result.stderr, f"{verb} wrote noisy help output")
            self.assertTrue(result.stdout.strip(), f"{verb} has no help text")

        status = subprocess.run(
            [str(SHADOW), "help", "status"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn("--shadowed", status.stdout)

        goal = subprocess.run(
            [str(SHADOW), "help", "goal"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn("--install|--remove", goal.stdout)
        self.assertIn("--host HOST", goal.stdout)

    def test_banner_honors_reduced_motion(self) -> None:
        text = (ROOT / "assets" / "shadow-banner.svg").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", text)
        self.assertIn("animation: none", text)


if __name__ == "__main__":
    unittest.main()
