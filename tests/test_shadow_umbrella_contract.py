"""Keep the portable Shadow front door conversational and honest."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "ai" / "skills" / "shadow" / "SKILL.md"


class ShadowUmbrellaContractTests(unittest.TestCase):
    def test_router_carries_a_self_contained_human_voice_rule(self) -> None:
        text = SKILL.read_text(encoding="utf-8").lower()
        self.assertIn("warm", text)
        self.assertIn("candid", text)
        self.assertIn("fixed response template", text)

    def test_router_is_portable_and_not_personally_identifying(self) -> None:
        self.assertNotIn("leo", SKILL.read_text(encoding="utf-8").lower())

    def test_router_does_not_recreate_the_old_status_card(self) -> None:
        text = SKILL.read_text(encoding="utf-8").upper()
        for heading in (
            "## VERDICT",
            "## OWNER",
            "## EVIDENCE CEILING",
            "## NEXT SAFE STEP",
            "## PROTECTED ACTION",
            "## BUZZ/SLACK DEPENDENCY",
        ):
            self.assertNotIn(heading, text)
        self.assertNotIn("A/B/C", text)

    def test_router_is_honest_when_the_live_board_is_unavailable(self) -> None:
        text = SKILL.read_text(encoding="utf-8").lower()
        self.assertIn("coach mode", text)
        self.assertIn("cannot read or change the current board", text)


if __name__ == "__main__":
    unittest.main()
