"""Keep the share-ready README and public help tied to real Shadow surfaces."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHADOW = ROOT / "bin" / "shadow"


class ShareReadyDocumentationTests(unittest.TestCase):
    def test_readme_leads_with_authority_loop_and_install(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "assets/shadow-banner.svg",
            "PLAN.md",
            "shadow init --here",
            "shadow status",
            "shadow accept",
            "shadow doctor",
            "install.sh",
            "--branch shadow-v1.0.2",
        )
        for phrase in required:
            self.assertIn(phrase, text)
        # The board's authority is per computer, and the work is durable across
        # a killed chat: the two claims a stranger must read before installing.
        self.assertRegex(text, r"one\s+board per computer")
        self.assertIn("durable", text)
        self.assertNotIn("npm test", text)
        self.assertNotIn("/Users/", text)

        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Every Shadow chat response ends with a compact `Ongoing tasks` projection", skill)
        self.assertIn("shadow status --in-flight --json", skill)

    def test_the_footer_projection_contract_stays_written_down(self) -> None:
        """The README sends detail to the docs site, so the host-facing footer
        contract must stay stated where hosts and strangers actually read it."""
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        quickstart = (ROOT / "docs" / "guide" / "quickstart.md").read_text(encoding="utf-8")
        for text in (skill, quickstart):
            self.assertIn("shadow status --in-flight --json", text)
            self.assertIn("Ongoing tasks", text)
            self.assertIn("Active tasks: none", text)

    def test_the_two_seat_harness_stays_written_down(self) -> None:
        commands = (ROOT / "docs" / "reference" / "commands.md").read_text(encoding="utf-8")
        self.assertIn("scripts/shadow-verify-two-seat.py", commands)
        self.assertIn("--live --goal-file", commands)
        host = (ROOT / "docs" / "reference" / "host-integration.md")
        self.assertTrue(host.is_file(), "host integration detail must have a documented home")

    def test_quickstart_has_a_real_claim_and_close_loop(self) -> None:
        text = (ROOT / "docs" / "guide" / "quickstart.md").read_text(encoding="utf-8")
        for phrase in (
            "shadow init --here",
            # `shadow init --here` writes the machine-local plan under
            # ~/.shadow/plans/<project>/, so the quickstart must open and lint
            # that printed path with this checkout as its source.
            "$EDITOR ~/.shadow/plans/<project>/PLAN.md",
            "shadow lint --repo . ~/.shadow/plans/<project>/PLAN.md",
            "shadow status --by",
            "shadow throw",
            "shadow amp",
            "shadow accept",
            "shadow return",
            "shadow status --in-flight --json",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("proof: cmd npm test", text)
        # Never send a reader back to a repo-root PLAN.md: no such file exists.
        self.assertNotIn("shadow lint PLAN.md", text)

    def test_public_help_is_quiet_and_advertises_supported_flags(self) -> None:
        verbs = (
            "browse", "status", "init", "lint", "goal", "amp", "throw",
            "return", "priority", "accept", "lifecycle", "host", "slots",
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


class AReadmeAStrangerCanFollow(unittest.TestCase):
    """The README must be followable cold: every word the vocabulary leans on is
    glossed in plain words before the install, and every command it names
    actually exists in the CLI's own help."""

    def test_the_vocabulary_glosses_every_word_it_names(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        section = text.split("## Install", 1)[0]
        for concept in ("board", "plans", "seats", "claim", "proof", "accept"):
            self.assertIn(f"**{concept}**", section, f"the README leans on {concept} but never explains it")
        self.assertIn("claim → work → prove → accept → next", section)

    def test_the_readme_names_only_real_commands(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        help_text = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "--help"], capture_output=True, text=True, check=False
        ).stdout
        import re as _re
        for verb in set(_re.findall(r"(?:`|^|\s)shadow ([a-z-]+)", text, _re.MULTILINE)):
            self.assertIn(f"  {verb} ", help_text, f"README names `shadow {verb}` but the CLI help does not")


if __name__ == "__main__":
    unittest.main()
