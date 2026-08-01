"""Focused tests for the bounded Vidux Drive / 90 semantic client."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "browser" / "drive_mode.py"
SPEC = importlib.util.spec_from_file_location("vidux_drive_mode", MODULE)
assert SPEC and SPEC.loader
drive = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = drive
SPEC.loader.exec_module(drive)

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "vidux_outcome_validator",
    ROOT / "scripts" / "vidux-outcome-validate.py",
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
sys.modules[VALIDATOR_SPEC.name] = validator
VALIDATOR_SPEC.loader.exec_module(validator)


def document() -> dict:
    options = [
        {"id": "ship-now", "label": "Ship now", "consequence": "Use the accepted proof."},
        {"id": "hold-review", "label": "Hold for review", "consequence": "Keep the row open."},
        {"id": "run-more", "label": "Run more checks", "consequence": "Spend another bounded cycle."},
        {"id": "write-note", "label": "Write a note", "consequence": "Record the uncertainty."},
        {"id": "stop-work", "label": "Stop work", "consequence": "Leave the outcome unchanged."},
    ]
    return {
        "schema": "vidux.outcome.v1",
        "revision": 4,
        "updated_at": "2026-08-01T18:00:00Z",
        "outcome": {
            "id": "publish-notes",
            "summary": "Ship accurate notes for the next tagged build.",
            "state": "needs_input",
            "current_move": "Choose the next bounded move.",
        },
        "ask": {
            "id": "choose-release",
            "category": "product_choice",
            "question": "What should happen next?",
            "options": options,
            "state": "open",
            "answer_option_id": None,
        },
        "steers": [
            {
                "id": "old-direction",
                "outcome_id": "publish-notes",
                "summary": "The earlier direction was replaced.",
                "state": "superseded",
                "proof_ref": None,
            }
        ],
        "proof": [
            {
                "id": "notes-test",
                "type": "test",
                "locator": "tests/test_drive_mode.py",
                "verification_summary": "Drive contract tests pass.",
                "delivery": "delivered",
            }
        ],
    }


class DriveModeTests(unittest.TestCase):
    def test_projection_is_bounded_and_keeps_superseded_steer_visible(self):
        source = document()
        original = copy.deepcopy(source)
        result = drive.project_drive(source)
        self.assertEqual(result["schema"], "vidux.drive.v1")
        self.assertEqual([option["id"] for option in result["ask"]["options"]], [
            "ship-now",
            "hold-review",
            "run-more",
        ])
        self.assertEqual(result["ask"]["options_total"], 5)
        self.assertTrue(result["ask"]["options_truncated"])
        self.assertEqual(result["steers"][0]["state"], "superseded")
        self.assertIsNone(result["active_steer_id"])
        self.assertEqual(source, original)

    def test_choice_is_closed_typed_and_does_not_include_free_text(self):
        result = drive.build_choice(document(), "hold-review")
        self.assertEqual(
            result,
            {
                "schema": "vidux.drive-steer.v1",
                "kind": "answer",
                "revision": 4,
                "outcome_id": "publish-notes",
                "ask_id": "choose-release",
                "option_id": "hold-review",
            },
        )
        self.assertNotIn("message", result)
        self.assertNotIn("prompt", result)
        self.assertNotIn("provider", result)

    def test_unknown_choice_is_rejected(self):
        with self.assertRaises(drive.DriveInputError):
            drive.build_choice(document(), "invented-choice")

        with self.assertRaises(drive.DriveInputError):
            drive.build_choice(document(), "write-note")

    def test_closed_ask_cannot_receive_a_choice(self):
        source = document()
        source["ask"]["state"] = "superseded"
        source["outcome"]["state"] = "working"
        with self.assertRaises(drive.DriveInputError):
            drive.build_choice(source, "ship-now")

    def test_projection_allowlists_semantic_fields(self):
        source = document()
        source["provider"] = "cursor"
        source["transcript"] = "do not copy this"
        result = drive.project_drive(source)
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn("cursor", encoded)
        self.assertNotIn("do not copy this", encoded)

    def test_projection_is_downstream_of_the_strict_outcome_validator(self):
        source = document()
        self.assertEqual(validator.validate_document(source), [])
        invalid = copy.deepcopy(source)
        invalid["provider"] = "cursor"
        self.assertTrue(validator.validate_document(invalid))

    def test_receive_current_choice_records_same_authority_receipt(self):
        source = document()
        choice = drive.build_choice(source, "hold-review")
        result = drive.receive_choice(
            source,
            choice,
            updated_at="2026-08-01T18:01:00Z",
        )

        self.assertEqual(result["receipt"]["schema"], "vidux.drive-receipt.v1")
        self.assertEqual(result["receipt"]["state"], "received")
        self.assertEqual(result["receipt"]["reason"], "accepted")
        self.assertEqual(result["receipt"]["observed_revision"], 4)
        self.assertEqual(result["receipt"]["authority_revision"], 4)
        self.assertEqual(result["receipt"]["next_revision"], 5)
        self.assertEqual(result["document"]["revision"], 5)
        self.assertEqual(result["document"]["steers"][-1]["state"], "received")
        self.assertEqual(validator.validate_document(result["document"]), [])
        self.assertEqual(source["revision"], 4)
        self.assertEqual(len(source["steers"]), 1)

    def test_receive_stale_choice_is_superseded_without_execution(self):
        source = document()
        source["revision"] = 5
        choice = drive.build_choice(document(), "hold-review")
        result = drive.receive_choice(source, choice)

        self.assertEqual(result["receipt"]["state"], "superseded")
        self.assertEqual(result["receipt"]["reason"], "stale_revision")
        self.assertIsNone(result["receipt"]["proof_ref"])
        self.assertEqual(result["document"]["steers"][-1]["state"], "superseded")
        self.assertEqual(validator.validate_document(result["document"]), [])

    def test_receive_hidden_choice_is_not_delivered_with_bounded_proof(self):
        source = document()
        hidden = {
            "schema": "vidux.drive-steer.v1",
            "kind": "answer",
            "revision": 4,
            "outcome_id": "publish-notes",
            "ask_id": "choose-release",
            "option_id": "write-note",
        }
        result = drive.receive_choice(source, hidden)

        self.assertEqual(result["receipt"]["state"], "not_delivered")
        self.assertEqual(result["receipt"]["reason"], "option_not_visible")
        proof_ref = result["receipt"]["proof_ref"]
        self.assertIsInstance(proof_ref, str)
        self.assertEqual(result["document"]["steers"][-1]["state"], "not_delivered")
        self.assertEqual(result["document"]["steers"][-1]["proof_ref"], proof_ref)
        self.assertEqual(validator.validate_document(result["document"]), [])

    def test_receive_current_choice_supersedes_previous_active_steer(self):
        first = drive.receive_choice(
            document(),
            drive.build_choice(document(), "hold-review"),
        )
        second_document = first["document"]
        second = drive.receive_choice(
            second_document,
            drive.build_choice(second_document, "ship-now"),
        )

        self.assertEqual(second["receipt"]["state"], "received")
        self.assertEqual(second["document"]["steers"][0]["state"], "superseded")
        self.assertEqual(second["document"]["steers"][-1]["state"], "received")
        self.assertEqual(validator.validate_document(second["document"]), [])

    def test_receive_rejects_extra_envelope_fields(self):
        choice = drive.build_choice(document(), "hold-review")
        choice["provider"] = "cursor"
        with self.assertRaises(drive.DriveInputError):
            drive.receive_choice(document(), choice)


if __name__ == "__main__":
    unittest.main()
