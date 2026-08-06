from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-outcome-validate.py"
SPEC = importlib.util.spec_from_file_location("outcome_validator", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def document() -> dict:
    return json.loads((ROOT / "examples" / "outcome-choice" / "example.json").read_text(encoding="utf-8"))


class OutcomeValidatorTests(unittest.TestCase):
    def assert_code(self, errors: list[dict], code: str) -> None:
        self.assertTrue(any(item["code"] == code for item in errors), errors)

    def test_example_is_valid(self) -> None:
        self.assertEqual(validator.validate_document(document()), [])

    def test_contract_is_closed(self) -> None:
        value = document()
        value["hidden_runtime"] = {"enabled": True}
        self.assert_code(validator.validate_document(value), "additional")

    def test_needs_input_requires_exactly_abc(self) -> None:
        value = document()
        value["ask"]["options"].pop()
        self.assert_code(validator.validate_document(value), "bounds")
        value = document()
        value["ask"] = None
        self.assert_code(validator.validate_document(value), "state")

    def test_other_states_cannot_carry_open_choice(self) -> None:
        value = document()
        value["outcome"]["state"] = "working"
        self.assert_code(validator.validate_document(value), "state")

    def test_ids_are_unique(self) -> None:
        value = document()
        value["ask"]["options"][1]["id"] = value["ask"]["options"][0]["id"]
        self.assert_code(validator.validate_document(value), "duplicate_id")

    def test_private_path_and_secret_fragments_fail(self) -> None:
        value = document()
        value["outcome"]["current_move"] = "/Users/person/private/file"
        self.assert_code(validator.validate_document(value), "privacy")
        fragmented = json.loads(
            (ROOT / "examples" / "outcome-choice" / "privacy-fragmented.invalid.json").read_text(encoding="utf-8")
        )
        self.assert_code(validator.validate_document(fragmented), "privacy")

    def test_finished_state_requires_delivered_proof(self) -> None:
        value = document()
        value["outcome"]["state"] = "finished_with_proof"
        value["ask"] = None
        value["proof"][0]["delivery"] = "not_delivered"
        self.assert_code(validator.validate_document(value), "state")

    def test_cli_rejects_duplicate_json_keys(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input='{"schema":"shadow.outcome.v1","schema":"duplicate"}',
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "json")

    def test_cli_reports_io_as_invocation_failure(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", "/definitely/missing/outcome.json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "io")

    def test_docs_name_only_the_single_contract(self) -> None:
        text = (ROOT / "docs" / "reference" / "outcome-choice.md").read_text(encoding="utf-8")
        self.assertIn("Outcome", text)
        self.assertIn("A/B/C", text)
        self.assertNotIn("queue policy", text)


if __name__ == "__main__":
    unittest.main()
