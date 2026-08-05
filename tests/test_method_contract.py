"""The Method's shipped contract: AGENT.md and the file grammar stay coherent."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "AGENT.md"
METHOD = ROOT / "docs" / "reference" / "method.md"
SKILL = ROOT / "SKILL.md"


class MethodContractTests(unittest.TestCase):
    def test_method_files_exist_and_are_linked(self) -> None:
        self.assertTrue(AGENT.is_file(), "AGENT.md must ship at the skill root")
        self.assertTrue(METHOD.is_file(), "docs/reference/method.md must ship")
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("AGENT.md", skill)
        self.assertIn("docs/reference/method.md", skill)
        index = (ROOT / "docs" / "reference" / "index.md").read_text(encoding="utf-8")
        self.assertIn("(method.md)", index)

    def test_agent_md_carries_the_standing_behaviors(self) -> None:
        text = AGENT.read_text(encoding="utf-8")
        for anchor in (
            "One chief of staff",
            "SPIKE",
            "DEFER",
            "CHALLENGE",
            "CLOSE",
            "Existential",
            "Contradiction",
            "PLAN-LINT",
            "Transfer the lesson",
            "lesson delta",
            "read-only projection",
        ):
            self.assertIn(anchor, text, anchor)

    def test_method_grammar_is_pinned(self) -> None:
        text = METHOD.read_text(encoding="utf-8")
        for anchor in (
            "- Entity: resplit",
            "Spike | Defer | Challenge | Close",
            "(DoD)",
            "| proof:",
            "| size:",
            "needs:",
            "from:",
            "CLAIM",
            "PROOF",
            "DONE",
            "PLAN-LINT",
            "LESSON none",
            "Default if silent",
        ):
            self.assertIn(anchor, text, anchor)
        self.assertRegex(text, r"C\d+~[0-9a-z]{4}")
        self.assertIn("^[a-z][a-z0-9-]{1,31}$", text)

    def test_grammar_matches_the_shipped_board_scanner(self) -> None:
        server = (ROOT / "browser" / "server.py").read_text(encoding="utf-8")
        method = METHOD.read_text(encoding="utf-8")
        entity_re = re.search(r'ENTITY_VALUE_RE = re\.compile\(r"([^"]+)"\)', server)
        self.assertIsNotNone(entity_re)
        self.assertIn(entity_re.group(1), method)
        mode_re = re.search(r'MODE_VALUE_RE = re\.compile\(r"([^"]+)"\)', server)
        self.assertIsNotNone(mode_re)
        for mode in ("spike", "defer", "challenge", "close"):
            self.assertIn(mode, mode_re.group(1))


if __name__ == "__main__":
    unittest.main()
