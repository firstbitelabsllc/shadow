"""Focused proof for the shared Pilot Puppy Chief-of-Staff brief."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BROWSER = ROOT / "browser"
sys.path.insert(0, str(BROWSER))

SPEC = importlib.util.spec_from_file_location(
    "pilot_puppy_chief_of_staff",
    BROWSER / "chief_of_staff.py",
)
assert SPEC and SPEC.loader
chief = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = chief
SPEC.loader.exec_module(chief)

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "pilot_puppy_outcome_validator",
    ROOT / "scripts" / "pilot-puppy-outcome-validate.py",
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
sys.modules[VALIDATOR_SPEC.name] = validator
VALIDATOR_SPEC.loader.exec_module(validator)


def document(state: str = "needs_input") -> dict:
    options = [
        {"id": "ship-now", "label": "Ship now", "consequence": "Use the accepted proof."},
        {"id": "hold-review", "label": "Hold for review", "consequence": "Keep the row open."},
        {"id": "run-more", "label": "Run more checks", "consequence": "Spend another bounded cycle."},
    ]
    return {
        "schema": "pilot-puppy.outcome.v1",
        "revision": 4,
        "updated_at": "2026-08-01T18:00:00Z",
        "outcome": {
            "id": "publish-notes",
            "summary": "Ship accurate notes for the next tagged build.",
            "state": state,
            "current_move": "Choose the next bounded move.",
        },
        "ask": {
            "id": "choose-release",
            "category": "product_choice",
            "question": "What should happen next?",
            "options": options,
            "state": "open",
            "answer_option_id": None,
        } if state == "needs_input" else None,
        "proof": [
            {
                "id": "notes-test",
                "type": "test",
                "locator": "tests/test_chief_of_staff.py",
                "verification_summary": "Chief of Staff contract tests pass.",
                "delivery": "delivered",
            }
        ],
    }


class ChiefOfStaffTests(unittest.TestCase):
    def test_needs_you_brief_is_shared_and_limited_to_three_choices(self):
        source = document()
        result = chief.project_chief_of_staff(
            source,
            plan_brief={
                "summary": "Make the next release understandable.",
                "latest_change": "The shared brief contract is ready.",
            },
        )

        self.assertEqual(result["schema"], "pilot-puppy.chief-of-staff.v1")
        self.assertEqual(result["state"], "needs_you")
        self.assertEqual(result["revision"], 4)
        self.assertEqual(result["outcome_id"], "publish-notes")
        self.assertEqual(result["matters"], "Make the next release understandable.")
        self.assertEqual(result["changed"], "The shared brief contract is ready.")
        self.assertEqual(result["blocker"], "What should happen next?")
        self.assertEqual(result["action"], "Choose one option for the next move.")
        self.assertEqual(len(result["choices"]), 3)
        self.assertEqual(result["choices"][0]["id"], "ship-now")
        self.assertEqual(result["proof"]["id"], "notes-test")

    def test_working_brief_reports_no_ask_and_keeps_implementation_out(self):
        source = document("working")
        result = chief.project_chief_of_staff(source)

        self.assertEqual(result["state"], "working")
        self.assertEqual(result["choices"], [])
        self.assertIsNone(result["blocker"])
        self.assertIsNone(result["action"])
        self.assertEqual(result["recommendation"], "Continue the current move.")
        self.assertNotIn("provider", result)
        self.assertNotIn("model", result)
        self.assertNotIn("prompt", result)
        self.assertNotIn("transcript", result)

    def test_blocked_brief_surfaces_action_and_one_proof(self):
        source = document("blocked")
        source["outcome"]["current_move"] = "Waiting for the browser proof."
        result = chief.project_chief_of_staff(source)

        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["blocker"], "Waiting for the browser proof.")
        self.assertEqual(result["action"], "Review the blocker and choose the next move.")
        self.assertEqual(result["recommendation"], "Address the blocker before continuing.")
        self.assertEqual(result["proof"]["delivery"], "delivered")

    def test_rejects_private_plan_text_and_unknown_fields(self):
        with self.assertRaises(chief.DecisionInputError):
            chief.project_chief_of_staff(document(), plan_brief={"summary": "/Users/private"})
        with self.assertRaises(chief.DecisionInputError):
            chief.project_chief_of_staff(document(), plan_brief={"raw": "not allowed"})

    def test_projection_does_not_mutate_shared_outcome(self):
        source = document()
        original = copy.deepcopy(source)
        chief.project_chief_of_staff(source)
        self.assertEqual(source, original)
        self.assertEqual(validator.validate_document(source), [])


if __name__ == "__main__":
    unittest.main()
