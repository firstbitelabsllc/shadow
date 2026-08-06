"""Focused tests for one bounded Shadow A/B/C decision."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from browser import decision_mode as decision


ROOT = Path(__file__).resolve().parent.parent


def document() -> dict:
    return json.loads((ROOT / "examples" / "outcome-choice" / "example.json").read_text(encoding="utf-8"))


class DecisionModeTests(unittest.TestCase):
    def test_projection_is_bounded_and_pure(self) -> None:
        source = document()
        original = copy.deepcopy(source)
        result = decision.project_decision(source)
        self.assertEqual(result["schema"], "shadow.decision.v1")
        self.assertEqual(len(result["ask"]["options"]), 3)
        self.assertEqual(source, original)
        self.assertEqual(
            set(result),
            {"schema", "revision", "updated_at", "outcome", "ask", "proof"},
        )

    def test_closed_document_rejects_implementation_fields(self) -> None:
        source = document()
        source["provider"] = "example"
        with self.assertRaises(decision.DecisionInputError):
            decision.project_decision(source)

    def test_choice_is_closed_and_typed(self) -> None:
        result = decision.build_choice(document(), "full-review")
        self.assertEqual(
            result,
            {
                "schema": "shadow.decision-choice.v1",
                "kind": "answer",
                "revision": 3,
                "outcome_id": "ship-release-notes",
                "ask_id": "choose-review-depth",
                "option_id": "full-review",
            },
        )

    def test_unknown_choice_is_rejected(self) -> None:
        with self.assertRaises(decision.DecisionInputError):
            decision.build_choice(document(), "invented-choice")

    def test_current_choice_is_received_without_mutating_authority(self) -> None:
        source = document()
        original = copy.deepcopy(source)
        result = decision.receive_choice(source, decision.build_choice(source, "focused-review"))
        self.assertEqual(result["receipt"]["state"], "received")
        self.assertEqual(result["receipt"]["reason"], "accepted")
        self.assertEqual(result["receipt"]["authority_revision"], 3)
        self.assertEqual(source, original)
        self.assertEqual(
            set(result["receipt"]),
            {"schema", "state", "reason", "observed_revision", "authority_revision", "outcome_id", "ask_id", "option_id"},
        )

    def test_stale_choice_is_superseded(self) -> None:
        choice = decision.build_choice(document(), "focused-review")
        source = document()
        source["revision"] = 4
        result = decision.receive_choice(source, choice)
        self.assertEqual(result["receipt"]["state"], "superseded")
        self.assertEqual(result["receipt"]["reason"], "stale_revision")

    def test_identity_or_hidden_option_is_not_delivered(self) -> None:
        choice = decision.build_choice(document(), "focused-review")
        choice["outcome_id"] = "other-outcome"
        result = decision.receive_choice(document(), choice)
        self.assertEqual(result["receipt"]["reason"], "identity_mismatch")
        choice = decision.build_choice(document(), "focused-review")
        choice["option_id"] = "hidden-option"
        result = decision.receive_choice(document(), choice)
        self.assertEqual(result["receipt"]["reason"], "option_not_visible")

    def test_choice_rejects_extra_fields(self) -> None:
        choice = decision.build_choice(document(), "focused-review")
        choice["message"] = "extra"
        with self.assertRaises(decision.DecisionInputError):
            decision.receive_choice(document(), choice)


if __name__ == "__main__":
    unittest.main()
