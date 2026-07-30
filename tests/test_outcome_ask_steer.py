"""Focused tests for scripts/vidux-outcome-validate.py."""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-outcome-validate.py"
EXAMPLE = ROOT / "examples" / "outcome-ask-steer" / "example.json"
FRAGMENTED_PRIVACY_EXAMPLE = (
    ROOT / "examples" / "outcome-ask-steer" / "privacy-fragmented.invalid.json"
)
SCHEMA = ROOT / "schemas" / "outcome-ask-steer.v1.json"
DOC = ROOT / "docs" / "reference" / "outcome-ask-steer.md"
PACKAGE = ROOT / "package.json"
MAX_INPUT_BYTES = 1 * 1024 * 1024
MAX_JSON_DEPTH = 64


def base_document() -> Dict[str, Any]:
    return {
        "schema": "vidux.outcome.v1",
        "revision": 1,
        "updated_at": "2026-07-29T12:00:00Z",
        "outcome": {
            "id": "publish-notes",
            "summary": "Ship accurate notes for the next tagged build.",
            "state": "working",
            "current_move": "Draft the outline from the interchange example.",
        },
        "ask": None,
        "steers": [],
        "proof": [
            {
                "id": "outline-doc",
                "type": "document",
                "locator": "docs/reference/outcome-ask-steer.md",
                "verification_summary": "Document locator is repository-relative and synthetic.",
                "delivery": "delivered",
            }
        ],
    }


class OutcomeAskSteerValidatorTests(unittest.TestCase):
    def run_validator(
        self,
        *,
        input_path: Optional[Path] = None,
        stdin_data: Optional[bytes] = None,
        extra_args: Optional[List[str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [sys.executable, str(SCRIPT)]
        if extra_args:
            args.extend(extra_args)
        elif input_path is not None:
            args.extend(["--input", str(input_path)])
        env = os.environ.copy()
        env["HOME"] = str(Path(tempfile.mkdtemp()) / "home")
        return subprocess.run(
            args,
            input=None if stdin_data is None else stdin_data.decode("utf-8", errors="surrogateescape"),
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_json_doc(self, document: Dict[str, Any]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "doc.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            return self.run_validator(input_path=path)

    def assert_valid(self, result: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "vidux.outcome-validation.v1")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], [])
        return payload

    def assert_invalid(
        self,
        result: subprocess.CompletedProcess[str],
        *,
        code: Optional[str] = None,
        path: Optional[str] = None,
        exit_code: int = 1,
    ) -> Dict[str, Any]:
        self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "vidux.outcome-validation.v1")
        self.assertFalse(payload["valid"])
        self.assertGreaterEqual(len(payload["errors"]), 1)
        codes = [item["code"] for item in payload["errors"]]
        paths = [item["path"] for item in payload["errors"]]
        if code is not None:
            self.assertIn(code, codes, payload)
        if path is not None:
            self.assertIn(path, paths, payload)
        ordered = sorted(
            payload["errors"],
            key=lambda item: (item["path"], item["code"], item["message"]),
        )
        self.assertEqual(payload["errors"], ordered)
        return payload

    def test_shipped_example_is_valid(self):
        result = self.run_validator(input_path=EXAMPLE)
        self.assert_valid(result)

    def test_shipped_fragmented_privacy_example_is_rejected(self):
        result = self.run_validator(input_path=FRAGMENTED_PRIVACY_EXAMPLE)
        self.assert_invalid(
            result,
            code="fragmented_secret_shape",
            path="/proof/0/verification_summary",
        )

    def test_schema_ask_option_text_uses_nonblank_refs(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        option = schema["$defs"]["askOption"]["properties"]
        self.assertEqual(option["label"], {"$ref": "#/$defs/nonblank80"})
        self.assertEqual(option["consequence"], {"$ref": "#/$defs/nonblank280"})
        for definition in ("nonblank80", "nonblank280"):
            pattern = schema["$defs"][definition]["pattern"]
            self.assertIsNone(re.fullmatch(pattern, "   "))

    def test_stdin_valid_document(self):
        raw = json.dumps(base_document()).encode("utf-8")
        result = self.run_validator(stdin_data=raw, extra_args=[])
        self.assert_valid(result)

    def test_stdin_dash_input(self):
        raw = json.dumps(base_document()).encode("utf-8")
        result = self.run_validator(stdin_data=raw, extra_args=["--input", "-"])
        self.assert_valid(result)

    def test_parse_error_exits_2(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "bad.json"
            path.write_text("{not-json", encoding="utf-8")
            result = self.run_validator(input_path=path)
        self.assert_invalid(result, code="parse_error", exit_code=2)

    def test_help_and_bad_cli_emit_only_json_with_exit_2(self):
        for arguments in (["--help"], ["--unknown"]):
            with self.subTest(arguments=arguments):
                result = self.run_validator(extra_args=arguments)
                self.assert_invalid(result, code="usage", exit_code=2)
                self.assertEqual(result.stderr, "")

    def test_duplicate_key_with_hidden_secret_is_rejected_at_exact_path(self):
        raw = EXAMPLE.read_text(encoding="utf-8").replace(
            '"summary": "Publish accurate',
            '"summary": "sk-abcdefghijklmnopqrstuvwxyz012345",\n'
            '    "summary": "Publish accurate',
            1,
        )
        result = self.run_validator(
            stdin_data=raw.encode("utf-8"),
            extra_args=[],
        )
        self.assert_invalid(
            result,
            code="duplicate_key",
            path="/outcome/summary",
            exit_code=2,
        )

    def test_duplicate_key_path_uses_json_pointer_escaping(self):
        result = self.run_validator(
            stdin_data=b'{"a/b":{"x~y":1,"x~y":2}}',
            extra_args=[],
        )
        self.assert_invalid(
            result,
            code="duplicate_key",
            path="/a~1b/x~0y",
            exit_code=2,
        )

    def test_size_cap_exits_2(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "big.json"
            path.write_bytes(b"{" + (b"a" * (MAX_INPUT_BYTES + 8)))
            result = self.run_validator(input_path=path)
        self.assert_invalid(result, code="size_error", exit_code=2)

    def test_missing_input_file_exits_2(self):
        missing = ROOT / "examples" / "outcome-ask-steer" / "does-not-exist.json"
        result = self.run_validator(input_path=missing)
        self.assert_invalid(result, code="io_error", exit_code=2)

    def test_unknown_field_rejected(self):
        doc = base_document()
        doc["extra"] = "nope"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="unknown_field", path="/extra")

    def test_bool_is_not_integer_revision(self):
        doc = base_document()
        doc["revision"] = True
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="type", path="/revision")

    def test_duplicate_ids_rejected(self):
        doc = base_document()
        doc["steers"] = [
            {
                "id": "outline-doc",
                "outcome_id": "publish-notes",
                "summary": "Reuse a proof id to force a document-wide clash.",
                "state": "applied",
                "proof_ref": None,
            }
        ]
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="duplicate_id")

    def test_bad_steer_outcome_link(self):
        doc = base_document()
        doc["steers"] = [
            {
                "id": "steer-one",
                "outcome_id": "other-outcome",
                "summary": "Points at the wrong outcome id.",
                "state": "received",
                "proof_ref": None,
            }
        ]
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="unresolved_link", path="/steers/0/outcome_id")

    def test_bad_proof_ref_link(self):
        doc = base_document()
        doc["steers"] = [
            {
                "id": "steer-one",
                "outcome_id": "publish-notes",
                "summary": "Points at a missing proof id.",
                "state": "applied",
                "proof_ref": "missing-proof",
            }
        ]
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="unresolved_link", path="/steers/0/proof_ref")

    def test_only_one_nonterminal_steer_is_allowed(self):
        doc = base_document()
        doc["steers"] = [
            {
                "id": "steer-one",
                "outcome_id": "publish-notes",
                "summary": "First recorded direction.",
                "state": "working",
                "proof_ref": None,
            },
            {
                "id": "steer-two",
                "outcome_id": "publish-notes",
                "summary": "Competing recorded direction.",
                "state": "applied",
                "proof_ref": None,
            },
        ]
        result = self.run_json_doc(doc)
        self.assert_invalid(
            result,
            code="steer_lifecycle",
            path="/steers/1/state",
        )

    def test_multiple_terminal_steers_are_allowed(self):
        doc = base_document()
        doc["steers"] = [
            {
                "id": "steer-old",
                "outcome_id": "publish-notes",
                "summary": "Older recorded direction.",
                "state": "superseded",
                "proof_ref": None,
            },
            {
                "id": "steer-done",
                "outcome_id": "publish-notes",
                "summary": "Completed recorded direction.",
                "state": "finished_with_proof",
                "proof_ref": "outline-doc",
            },
        ]
        result = self.run_json_doc(doc)
        self.assert_valid(result)

    def test_needs_input_requires_open_ask(self):
        doc = base_document()
        doc["outcome"]["state"] = "needs_input"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="needs_input", path="/outcome/state")

    def test_open_ask_requires_needs_input(self):
        doc = base_document()
        doc["ask"] = {
            "id": "name-choice",
            "category": "product_choice",
            "question": "Which reserved-domain label should notes use?",
            "options": [
                {
                    "id": "keep-label",
                    "label": "Keep example.com",
                    "consequence": "Notes keep the current reserved-domain label.",
                },
                {
                    "id": "use-alt-label",
                    "label": "Use example.org",
                    "consequence": "Notes switch to the alternate reserved-domain label.",
                },
            ],
            "state": "open",
            "answer_option_id": None,
        }
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="needs_input", path="/ask/state")

    def test_open_ask_with_answer_rejected(self):
        doc = base_document()
        doc["outcome"]["state"] = "needs_input"
        doc["ask"] = {
            "id": "name-choice",
            "category": "product_choice",
            "question": "Which reserved-domain label should notes use?",
            "options": [
                {
                    "id": "keep-label",
                    "label": "Keep example.com",
                    "consequence": "Notes keep the current reserved-domain label.",
                },
                {
                    "id": "use-alt-label",
                    "label": "Use example.org",
                    "consequence": "Notes switch to the alternate reserved-domain label.",
                },
            ],
            "state": "open",
            "answer_option_id": "keep-label",
        }
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="ask_lifecycle", path="/ask/answer_option_id")

    def test_answered_ask_requires_resolving_option(self):
        doc = base_document()
        doc["ask"] = {
            "id": "name-choice",
            "category": "product_choice",
            "question": "Which reserved-domain label should notes use?",
            "options": [
                {
                    "id": "keep-label",
                    "label": "Keep example.com",
                    "consequence": "Notes keep the current reserved-domain label.",
                },
                {
                    "id": "use-alt-label",
                    "label": "Use example.org",
                    "consequence": "Notes switch to the alternate reserved-domain label.",
                },
            ],
            "state": "answered",
            "answer_option_id": "missing-option",
        }
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="unresolved_link", path="/ask/answer_option_id")

    def test_finished_outcome_requires_delivered_proof(self):
        doc = base_document()
        doc["outcome"]["state"] = "finished_with_proof"
        doc["proof"][0]["delivery"] = "not_delivered"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="terminal_proof", path="/outcome/state")

    def test_not_delivered_outcome_requires_matching_proof(self):
        doc = base_document()
        doc["outcome"]["state"] = "not_delivered"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="terminal_proof", path="/outcome/state")

    def test_terminal_steer_requires_matching_proof(self):
        doc = base_document()
        doc["steers"] = [
            {
                "id": "steer-done",
                "outcome_id": "publish-notes",
                "summary": "Claim finished without a matching delivered proof.",
                "state": "finished_with_proof",
                "proof_ref": None,
            }
        ]
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="terminal_proof", path="/steers/0/proof_ref")

    def test_nonfinite_number_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "nan.json"
            path.write_text('{"schema":"vidux.outcome.v1","revision":NaN}', encoding="utf-8")
            result = self.run_validator(input_path=path)
        self.assert_invalid(result, code="parse_error", exit_code=2)

    def test_deeply_nested_json_returns_structured_error(self):
        raw = ("[" * 2000 + "0" + "]" * 2000).encode("utf-8")
        result = self.run_validator(stdin_data=raw, extra_args=[])
        self.assert_invalid(result, code="depth")
        self.assertNotIn("Traceback", result.stderr)

    def test_depth_limit_accepts_64_and_rejects_65_before_decoder(self):
        at_limit = ("[" * MAX_JSON_DEPTH + "0" + "]" * MAX_JSON_DEPTH).encode(
            "utf-8"
        )
        at_limit_result = self.run_validator(stdin_data=at_limit, extra_args=[])
        at_limit_payload = self.assert_invalid(at_limit_result, code="type")
        self.assertNotIn("depth", [item["code"] for item in at_limit_payload["errors"]])

        over_limit = (
            "[" * (MAX_JSON_DEPTH + 1) + "0" + "]" * (MAX_JSON_DEPTH + 1)
        ).encode("utf-8")
        over_limit_result = self.run_validator(stdin_data=over_limit, extra_args=[])
        self.assert_invalid(over_limit_result, code="depth")

    def test_depth_preflight_ignores_delimiters_and_escapes_inside_strings(self):
        doc = base_document()
        doc["outcome"]["summary"] = (
            "Literal " + ("[{" * 65) + ' plus \\"quoted\\" and \\\\ text.'
        )
        result = self.run_json_doc(doc)
        self.assert_valid(result)

    def test_depth_preflight_does_not_sum_sibling_containers(self):
        raw = json.dumps([[] for _ in range(MAX_JSON_DEPTH + 50)]).encode("utf-8")
        result = self.run_validator(stdin_data=raw, extra_args=[])
        payload = self.assert_invalid(result, code="type")
        self.assertNotIn("depth", [item["code"] for item in payload["errors"]])

    def test_malformed_over_depth_input_preserves_resource_limit_precedence(self):
        raw = ("[" * (MAX_JSON_DEPTH + 1)).encode("utf-8")
        result = self.run_validator(stdin_data=raw, extra_args=[])
        self.assert_invalid(result, code="depth")

    def test_privacy_absolute_home_path_rejected(self):
        doc = base_document()
        doc["outcome"]["summary"] = "Do not read /" + "Users/example/secret-notes.txt"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="privacy_path", path="/outcome/summary")

    def test_privacy_tilde_path_rejected(self):
        doc = base_document()
        doc["outcome"]["current_move"] = "Avoid ~/private/token.env"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="privacy_path", path="/outcome/current_move")

    def test_privacy_file_url_rejected(self):
        doc = base_document()
        doc["proof"][0]["locator"] = "file:///tmp/example.txt"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="privacy_path")

    def test_forbidden_key_fragment_rejected(self):
        doc = base_document()
        doc["outcome"]["model_hint"] = "should-not-appear"
        result = self.run_json_doc(doc)
        payload = self.assert_invalid(result, code="forbidden_key")
        self.assertTrue(
            any(item["path"].endswith("/model_hint") for item in payload["errors"]),
            payload,
        )

    def test_secret_token_shape_rejected(self):
        doc = base_document()
        doc["outcome"]["summary"] = "token sk-abcdefghijklmnopqrstuvwxyz012345"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="secret_shape", path="/outcome/summary")

    def test_secret_token_split_across_three_fields_is_rejected(self):
        doc = base_document()
        doc["outcome"]["a"] = "sk"
        doc["outcome"]["b"] = "-abcdefgh"
        doc["outcome"]["c"] = "ijkl012345"
        result = self.run_json_doc(doc)
        self.assert_invalid(
            result,
            code="fragmented_secret_shape",
            path="/outcome/c",
        )

    def test_fragment_detection_is_independent_of_object_insertion_order(self):
        for keys in (("a", "b", "c"), ("c", "a", "b")):
            with self.subTest(keys=keys):
                doc = base_document()
                values = {"a": "sk", "b": "-abcdefgh", "c": "ijkl012345"}
                for key in keys:
                    doc["outcome"][key] = values[key]
                result = self.run_json_doc(doc)
                self.assert_invalid(
                    result,
                    code="fragmented_secret_shape",
                    path="/outcome/c",
                )

    def test_sensitive_token_prefix_fragment_is_rejected(self):
        doc = base_document()
        doc["outcome"]["summary"] = "token prefix sk-"
        result = self.run_json_doc(doc)
        self.assert_invalid(
            result,
            code="secret_prefix_fragment",
            path="/outcome/summary",
        )

    def test_fragment_scan_is_bounded_and_normal_fragments_remain_valid(self):
        doc = base_document()
        doc["proof"] = [
            {
                "id": f"proof-{index}",
                "type": "document",
                "locator": f"evidence/proof-{index}.json",
                "verification_summary": "Synthetic verification fragment.",
                "delivery": "delivered",
            }
            for index in range(64)
        ]
        result = self.run_json_doc(doc)
        self.assert_valid(result)

    def test_private_key_shape_rejected(self):
        doc = base_document()
        doc["proof"][0]["verification_summary"] = (
            "Contains -----BEGIN PRIVATE KEY----- which must be rejected."
        )
        result = self.run_json_doc(doc)
        self.assert_invalid(
            result, code="secret_shape", path="/proof/0/verification_summary"
        )

    def test_locator_rejects_parent_segment(self):
        doc = base_document()
        doc["proof"][0]["locator"] = "docs/../secrets.txt"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="locator", path="/proof/0/locator")

    def test_locator_rejects_https_userinfo(self):
        doc = base_document()
        doc["proof"][0]["locator"] = "https://user:pass@example.com/proof"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="locator", path="/proof/0/locator")

    def test_locator_rejects_https_query_and_fragment(self):
        for locator in (
            "https://example.com/proof?token=synthetic",
            "https://example.com/proof#section",
        ):
            with self.subTest(locator=locator):
                doc = base_document()
                doc["proof"][0]["locator"] = locator
                result = self.run_json_doc(doc)
                self.assert_invalid(result, code="locator", path="/proof/0/locator")

    def test_locator_rejects_hostile_ipv6_without_traceback(self):
        doc = base_document()
        doc["proof"][0]["locator"] = "https://[::1"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="locator", path="/proof/0/locator")
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_timestamp_rejected(self):
        doc = base_document()
        doc["updated_at"] = "2026-07-29T12:00:00+00:00"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="pattern", path="/updated_at")

    def test_overlong_summary_rejected(self):
        doc = base_document()
        doc["outcome"]["summary"] = "x" * 281
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="length", path="/outcome/summary")

    def test_control_character_rejected(self):
        doc = base_document()
        doc["outcome"]["summary"] = "bad\u0000null"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="control_char", path="/outcome/summary")

    def test_absolute_and_home_variable_paths_are_rejected(self):
        values = (
            "/root/private.json",
            "/private/var/tmp/private.json",
            "\\\\server\\share\\private.json",
            "$HOME/private.json",
            "${HOME}/private.json",
        )
        for value in values:
            with self.subTest(value=value):
                doc = base_document()
                doc["outcome"]["summary"] = f"Do not open {value}"
                result = self.run_json_doc(doc)
                self.assert_invalid(
                    result,
                    code="privacy_path",
                    path="/outcome/summary",
                )

    def test_unicode_format_and_non_nfc_strings_are_rejected(self):
        cases = (
            ("Direction contains \u202e hidden text.", "unicode_format"),
            ("Cafe\u0301 proof summary.", "unicode_normalization"),
        )
        for value, code in cases:
            with self.subTest(code=code):
                doc = base_document()
                doc["outcome"]["summary"] = value
                result = self.run_json_doc(doc)
                self.assert_invalid(result, code=code, path="/outcome/summary")

    def test_valid_answered_ask_and_https_locator(self):
        doc = base_document()
        doc["ask"] = {
            "id": "name-choice",
            "category": "product_choice",
            "question": "Which reserved-domain label should notes use?",
            "options": [
                {
                    "id": "keep-label",
                    "label": "Keep example.com",
                    "consequence": "Notes keep the current reserved-domain label.",
                },
                {
                    "id": "use-alt-label",
                    "label": "Use example.org",
                    "consequence": "Notes switch to the alternate reserved-domain label.",
                },
            ],
            "state": "answered",
            "answer_option_id": "keep-label",
        }
        doc["proof"].append(
            {
                "id": "runtime-check",
                "type": "runtime",
                "locator": "https://example.com/status/notes",
                "verification_summary": "Synthetic https locator on a reserved domain.",
                "delivery": "delivered",
            }
        )
        doc["steers"] = [
            {
                "id": "steer-finish",
                "outcome_id": "publish-notes",
                "summary": "Keep the notes short and link deeper docs.",
                "state": "finished_with_proof",
                "proof_ref": "outline-doc",
            }
        ]
        doc["outcome"]["state"] = "finished_with_proof"
        result = self.run_json_doc(doc)
        self.assert_valid(result)

    def test_diagnostics_sorted_deterministically(self):
        doc = base_document()
        doc["extra_z"] = 1
        doc["extra_a"] = 1
        doc["outcome"]["state"] = "needs_input"
        result = self.run_json_doc(doc)
        payload = self.assert_invalid(result)
        paths_codes = [(item["path"], item["code"], item["message"]) for item in payload["errors"]]
        self.assertEqual(paths_codes, sorted(paths_codes))

    def test_schema_mismatch_rejected(self):
        doc = base_document()
        doc["schema"] = "vidux.outcome.v0"
        result = self.run_json_doc(doc)
        self.assert_invalid(result, code="const", path="/schema")

    def test_copy_of_example_mutated_unknown_nested_field(self):
        doc = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(doc)
        mutated["ask"]["options"][0]["secret_note"] = "no"
        result = self.run_json_doc(mutated)
        self.assert_invalid(result, code="unknown_field")

    def test_docs_define_steer_supersession_as_host_policy(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("according to its own queue policy", text)
        self.assertIn("Vidux only validates the recorded states", text)
        self.assertIn("does not stop workers or mutate", text)
        self.assertNotIn(
            "must not continue as a competing queue item",
            text,
        )

    def test_prepublish_runs_full_verification_and_release_verification(self):
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["prepublishOnly"],
            "npm run verify && npm run release:verify",
        )


if __name__ == "__main__":
    unittest.main()
