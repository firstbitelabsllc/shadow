"""Focused tests for the provider-neutral lifecycle receipt contract."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-lifecycle-validate.py"
EXAMPLE = ROOT / "examples/lifecycle-receipt/example.json"
INVALID_EXAMPLE = ROOT / "examples/lifecycle-receipt/invalid-missing-proof.invalid.json"
SCHEMA = ROOT / "schemas/lifecycle-receipt.v1.json"


def base_document() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class LifecycleReceiptValidatorTests(unittest.TestCase):
    def run_validator(self, document: dict[str, Any] | None = None, path: Path | None = None):
        with tempfile.TemporaryDirectory() as dirname:
            input_path = path
            serialized = None
            if document is not None:
                serialized = json.dumps(document)
                input_args = ["--input", "-"]
            else:
                assert input_path is not None
                input_args = ["--input", str(input_path)]
            env = os.environ.copy()
            env["HOME"] = str(Path(dirname) / "home")
            return subprocess.run(
                [sys.executable, str(SCRIPT), *input_args],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                input=serialized,
                check=False,
            )

    def assert_valid(self, result) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "vidux.lifecycle-validation.v1")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], [])

    def assert_invalid(self, result, code: str, path: str | None = None) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn(code, [item["code"] for item in payload["errors"]])
        if path is not None:
            self.assertIn(path, [item["path"] for item in payload["errors"]])

    def test_shipped_example_is_valid(self):
        self.assert_valid(self.run_validator(path=EXAMPLE))

    def test_shipped_invalid_example_requires_terminal_proof(self):
        self.assert_invalid(self.run_validator(path=INVALID_EXAMPLE), "proof_required")

    def test_disallowed_transition_is_rejected(self):
        document = base_document()
        document["events"][1]["to_state"] = "finished_with_proof"
        document["events"][1]["proof_ref"] = "tests-green"
        self.assert_invalid(self.run_validator(document), "transition", "/events/1/to_state")

    def test_sequence_must_start_planned_and_updated_at_tracks_last_event(self):
        document = base_document()
        document["events"][0]["to_state"] = "working"
        document["updated_at"] = "2026-08-01T16:19:00Z"
        result = self.run_validator(document)
        self.assert_invalid(result, "sequence", "/events/0/to_state")
        self.assertIn("updated_at", [item["code"] for item in json.loads(result.stdout)["errors"]])

    def test_forbidden_provider_field_is_rejected(self):
        document = base_document()
        document["events"][2]["provider"] = "cursor"
        result = self.run_validator(document)
        self.assert_invalid(result, "unknown_field", "/events/2/provider")

    def test_absolute_path_and_secret_are_rejected(self):
        document = base_document()
        home_path = chr(47) + "Users/leokwan/private"
        secret = "sk-" + "abcdefghijklmnopqrstuvwxyz012345"
        document["events"][0]["summary"] = f"Wrote {home_path} with {secret}"
        result = self.run_validator(document)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        codes = [item["code"] for item in payload["errors"]]
        self.assertIn("absolute_path", codes)
        self.assertIn("secret", codes)

    def test_schema_is_closed_and_declares_contract(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "https://vidux.dev/schemas/lifecycle-receipt.v1.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["schema"]["const"], "vidux.lifecycle.v1")


if __name__ == "__main__":
    unittest.main()
