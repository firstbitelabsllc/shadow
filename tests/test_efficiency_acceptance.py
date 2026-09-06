"""Falsify credit inferred from copied, failed, reopened or ambiguous receipts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("efficiency_acceptance",
    Path(__file__).resolve().parents[1] / "scripts/dev/shadow-efficiency-acceptance.py")
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)

HEAD = "a" * 40
PLAN = f"""# Test
## Tasks
- [completed] accepted work ~aa11 | proof: cmd python3 check.py
## Progress
- 2026-09-06T01:00:00Z ~aa11 PROOF python3 check.py -> pass (accept)
- 2026-09-06T01:00:00Z ~aa11 SOURCE github.com/example/project HEAD {HEAD} -> proof and final lint (accept)
"""


def attempt():
    return {"schema": "shadow.host-attempt.v1", "status": "ok", "task_id": "untrusted",
            "execution_binding": {"admitted_claim": {"row": "~aa11", "owner": "copied-owner"},
                                  "repository": {"remote_identity": "github.com/example/project"},
                                  "head_after": HEAD, "execution_candidate": True}}


class AcceptanceTests(unittest.TestCase):
    def test_copied_valid_head_and_forged_actor_never_earn_credit(self):
        for status in ("ok", "failed", "blocked"):
            value = attempt()
            value["status"] = status
            value["accepted_by_lead"] = True
            value["execution_binding"]["admitted_claim"]["owner"] = "forged-worker"
            result = reader.compare(value, PLAN)
            self.assertTrue(result["exact_accepted_source_match"])
            self.assertIsNone(result["accepted_worker_contribution"])
            self.assertIsNone(result["usage_join"])

    def test_reopened_root_has_no_current_source_acceptance(self):
        result = reader.compare(attempt(), PLAN.replace("[completed]", "[pending]"))
        self.assertEqual(result["referenced_root_state"], "not_completed")
        self.assertIsNone(result["exact_accepted_source_match"])

    def test_forged_task_id_cannot_select_another_root(self):
        value = attempt()
        value["task_id"] = "~aa11"
        value["execution_binding"]["admitted_claim"]["row"] = "~bb22"
        self.assertIsNone(reader.compare(value, PLAN)["exact_accepted_source_match"])

    def test_wrong_repository_or_head_does_not_match(self):
        for key in ("head", "repository"):
            value = attempt()
            if key == "head":
                value["execution_binding"]["head_after"] = "b" * 40
            else:
                value["execution_binding"]["repository"]["remote_identity"] = "github.com/other/project"
            self.assertFalse(reader.compare(value, PLAN)["exact_accepted_source_match"])

    def test_ambiguous_missing_or_unpaired_receipts_stay_unknown(self):
        source = PLAN.splitlines()[-1]
        for plan in (PLAN + source + "\n", PLAN.replace(source, ""),
                     PLAN.replace("01:00:00Z ~aa11 SOURCE", "02:00:00Z ~aa11 SOURCE"),
                     PLAN.replace("## Progress", "## Notes"),
                     PLAN.replace("SOURCE github", "SOURCE malformed github")):
            with self.subTest(plan=plan):
                self.assertIsNone(reader.compare(attempt(), plan)["exact_accepted_source_match"])

    def test_non_command_review_is_unknown_not_failure_or_worker_commit(self):
        result = reader.compare(attempt(), PLAN.replace("cmd python3 check.py", "read evidence.md -> pass"))
        self.assertEqual(result["reason"], "non_command_acceptance_requires_separate_witness")
        self.assertIsNone(result["accepted_worker_contribution"])

    def test_input_is_bounded_and_duplicate_json_and_symlink_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "attempt.json"
            for raw in ('{"schema":1,"schema":2}', " " * (reader.MAX_BYTES + 1), "[]"):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    reader.read_attempt(path)
            path.write_text(json.dumps(attempt()))
            before = path.read_bytes()
            reader.read_attempt(path)
            self.assertEqual(path.read_bytes(), before)
            link = path.with_name("link.json")
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                reader.read_attempt(link)

    def test_dedup_and_output_does_not_echo_actor_or_private_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "private-input.json"
            value = attempt()
            value["execution_binding"]["admitted_claim"]["entity"] = "e" * 64
            value["summary"] = "PRIVATE_TRANSCRIPT_CANARY"
            path.write_text(json.dumps(value))
            with patch.object(reader.board, "snapshot", return_value={"revision": 1}), \
                 patch.object(reader.board, "canonical_plan_by_id_at_revision", return_value=Path("plan")), \
                 patch.object(reader.board, "read_plan_text", return_value=PLAN), \
                 patch.object(reader.board, "plan_state_token", return_value="stable"):
                result = reader.audit([path, path])
            self.assertEqual(len(result["receipts"]), 1)
            for secret in (str(path), "PRIVATE_TRANSCRIPT_CANARY", "copied-owner", "untrusted"):
                self.assertNotIn(secret, json.dumps(result))
            self.assertIsNone(result["accepted_worker_tasks"])

    def test_board_or_plan_moves_refuse_whole_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "input.json"
            value = attempt()
            value["execution_binding"]["admitted_claim"]["entity"] = "e" * 64
            path.write_text(json.dumps(value))
            for board_values, tokens in (([{"revision": 1}, {"revision": 2}], ["a", "a", "a"]),
                                         ([{"revision": 1}, {"revision": 1}], ["a", "a", "b"])):
                with patch.object(reader.board, "snapshot", side_effect=board_values), \
                     patch.object(reader.board, "canonical_plan_by_id_at_revision", return_value=Path("plan")), \
                     patch.object(reader.board, "read_plan_text", return_value=PLAN), \
                     patch.object(reader.board, "plan_state_token", side_effect=tokens):
                    with self.assertRaises(ValueError):
                        reader.audit([path])


if __name__ == "__main__":
    unittest.main()
