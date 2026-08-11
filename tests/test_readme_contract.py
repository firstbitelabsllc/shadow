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
            "--branch shadow-v1.0.0",
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


class ADiagramAStrangerCanFollow(unittest.TestCase):
    """The README's first picture must be followable cold: every concept the
    diagram names is glossed in plain words in the same section, and every
    command the use path names actually exists in the CLI's own help."""

    def test_the_picture_glosses_every_concept_it_names(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## The picture", text)
        section = text.split("## The picture", 1)[1].split("## The loop", 1)[0]
        for concept in ("board", "plans", "seats", "claim", "proof", "accept"):
            self.assertIn(f"**{concept}**", section, f"the diagram names {concept} but never explains it")

    def test_the_use_path_names_only_real_commands(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        section = text.split("## How you use it", 1)[1].split("## The loop", 1)[0]
        help_text = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "--help"], capture_output=True, text=True, check=False
        ).stdout
        import re as _re
        for verb in set(_re.findall(r"`shadow ([a-z-]+)", section)):
            self.assertIn(f"  {verb} ", help_text, f"README use path names `shadow {verb}` but the CLI help does not")


if __name__ == "__main__":
    unittest.main()
