"""Behavioral falsifiers for the opt-in native-metadata reader."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "efficiency", Path(__file__).resolve().parents[1] / "scripts/dev/shadow-efficiency-audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def run_records(self, host, records, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "native.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in records))
            before = path.read_bytes()
            result = audit.audit([(host, path)], **kwargs)
            self.assertEqual(path.read_bytes(), before)
            return result

    def codex(self, total, time="2026-09-05T01:00:00Z"):
        return {"type": "event_msg", "timestamp": time, "payload": {
            "type": "token_count", "info": {"total_token_usage": {
                "input_tokens": total, "output_tokens": 2,
                "cached_input_tokens": 3, "reasoning_output_tokens": 1}}}}

    def test_cumulative_usage_and_requested_model_are_not_execution_or_acceptance(self):
        records = [{"type": "session_meta", "payload": {"id": "session-a"}},
                   {"type": "turn_context", "payload": {"model": "glm-5.3"}},
                   self.codex(10), self.codex(16), self.codex(16)]
        result = self.run_records("codex-zai", records)
        session = result["sessions"][0]
        self.assertEqual(session["usage"]["input_tokens"], 16)
        self.assertEqual(session["requested_models"], ["glm-5.3"])
        self.assertEqual(session["native_response_models"], [])
        self.assertIsNone(session["accepted_root_task"])
        self.assertIsNone(result["real_work_allocation"])
        self.assertIsNone(session["cost_usd"])

    def test_missing_native_session_identity_leaves_usage_unknown(self):
        digest = "0" * 64
        codex_meta = {"type": "session_meta", "payload": {"id": "session-a"}}
        valid_codex = audit.parse("codex", [codex_meta, self.codex(10)], digest, None, None)
        missing_codex = audit.parse("codex", [self.codex(10)], digest, None, None)
        claude = {"type": "assistant", "sessionId": "session-a",
                  "message": {"id": "message-a", "model": "claude-fable-5",
                              "usage": {"input_tokens": 10, "output_tokens": 2}}}
        missing_claude_record = {**claude, "sessionId": ""}
        valid_claude = audit.parse("claude", [claude], digest, None, None)
        missing_claude = audit.parse("claude", [missing_claude_record], digest, None, None)

        self.assertEqual(valid_codex["usage"]["input_tokens"], 10)
        self.assertEqual(valid_claude["usage"]["input_tokens"], 10)
        for missing in (missing_codex, missing_claude):
            self.assertIsNone(missing["usage"])
            self.assertIn("session_identity_missing", missing["gaps"])
            self.assertNotIn("multiple_session_ids", missing["gaps"])
            self.assertEqual(missing["source_digests"], [digest])

    def test_mixed_identified_and_unidentified_records_refuse_totals(self):
        identified = {"type": "assistant", "sessionId": "session-a",
                      "message": {"id": "message-a", "model": "claude-fable-5",
                                  "usage": {"input_tokens": 10, "output_tokens": 2}}}
        unidentified = {**identified, "sessionId": "", "message": {
            "id": "message-b", "model": "claude-fable-5",
            "usage": {"input_tokens": 20, "output_tokens": 3}}}
        r = self.run_records("claude", [identified, unidentified])
        s = r["sessions"][0]
        self.assertIsNone(s["usage"])
        self.assertIn("session_identity_missing", s["gaps"])
        self.assertNotIn("multiple_session_ids", s["gaps"])
        identified_only = self.run_records("claude", [identified])
        self.assertEqual(identified_only["sessions"][0]["usage"]["input_tokens"], 10)
        self.assertNotIn("session_identity_missing", identified_only["sessions"][0]["gaps"])

    def test_counter_reset_is_unknown(self):
        records = [{"type": "session_meta", "payload": {"id": "session-a"}},
                   self.codex(16), self.codex(10)]
        result = self.run_records("codex", records)
        self.assertIsNone(result["sessions"][0]["usage"])
        self.assertIn("cumulative_reset", result["sessions"][0]["gaps"])

    def test_window_needs_baseline_and_excludes_outside_usage(self):
        records = [{"type": "session_meta", "payload": {"id": "session-a"}},
                   self.codex(10, "2026-09-04T23:00:00Z"), self.codex(16)]
        r = self.run_records("codex", records, since="2026-09-05T00:00:00Z")
        self.assertEqual(r["sessions"][0]["usage"]["input_tokens"], 6)
        records = [{"type": "session_meta", "payload": {"id": "session-a"}}, self.codex(16)]
        r = self.run_records("codex", records, since="2026-09-05T00:00:00Z")
        self.assertIsNone(r["sessions"][0]["usage"])
        self.assertIn("window_baseline_missing", r["sessions"][0]["gaps"])

    def test_claude_message_updates_dedupe_and_models_come_from_response(self):
        records = [{"type": "assistant", "sessionId": "s", "uuid": "event-1",
                    "message": {"id": "m", "model": "claude-fable-5",
                    "usage": {"input_tokens": 10, "output_tokens": n},
                    "content": [{"text": "SECRET-CANARY /private/source"}]}}
                   for n in [1, 3, 3]]
        r = self.run_records("claude", records)
        self.assertEqual(r["sessions"][0]["usage"]["output_tokens"], 3)
        self.assertEqual(r["sessions"][0]["native_response_models"], ["claude-fable-5"])
        self.assertNotIn("SECRET-CANARY", json.dumps(r))
        self.assertNotIn("/private/source", json.dumps(r))
        self.assertNotIn('"s"', json.dumps(r))

    def test_duplicate_files_and_conflicting_session_copies(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d).resolve()/"a", Path(d).resolve()/"b"
            rows = [{"type": "session_meta", "payload": {"id": "same"}}, self.codex(10)]
            a.write_text("\n".join(map(json.dumps, rows)))
            b.write_bytes(a.read_bytes())
            r = audit.audit([("codex", a), ("codex", b)])
            self.assertEqual(len(r["sessions"]), 1)
            self.assertEqual(r["coverage"]["duplicate_sources"], 1)
            b.write_text(a.read_text()+"\n"+json.dumps(self.codex(16)))
            r = audit.audit([("codex", a), ("codex", b)])
            self.assertEqual(len(r["sessions"]), 1)
            self.assertIsNone(r["sessions"][0]["usage"])
            self.assertIn("conflicting_session_copies", r["sessions"][0]["gaps"])

    def test_malformed_record_refuses_whole_input_without_payload(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d).resolve()/"private-name"; p.write_text('{"secret":"CANARY"}\nBAD')
            with self.assertRaisesRegex(audit.Refusal, "malformed_json") as e:
                audit.audit([("codex", p)])
            self.assertNotIn("CANARY", str(e.exception))
            self.assertNotIn(str(p), str(e.exception))

    def test_symlink_and_oversized_line_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d).resolve()/"file"; p.write_text("{}\n"); link = Path(d).resolve()/"link"; link.symlink_to(p)
            with self.assertRaises(audit.Refusal): audit.audit([("codex", link)])
            p.write_text("x" * (audit.MAX_LINE + 1))
            with self.assertRaisesRegex(audit.Refusal, "line_limit"):
                audit.audit([("codex", p)])

    def test_unknown_grok_wire_shape_does_not_claim_execution(self):
        r = self.run_records("grok", [{"type": "tool_call", "model_id": "grok-4.6",
             "outcome": "success", "usage": {"input_tokens": 999}, "text": "CANARY"}])
        self.assertEqual(r["sessions"][0]["native_response_models"], [])
        self.assertIsNone(r["sessions"][0]["usage"])
        self.assertIsNone(r["sessions"][0]["confirmed_delegation"])

    def test_empty_and_negative_usage_do_not_become_zero_success(self):
        with self.assertRaisesRegex(audit.Refusal, "sources_required"): audit.audit([])
        records = [{"type": "session_meta", "payload": {"id": "session-a"}}, self.codex(-1)]
        r = self.run_records("codex", records)
        self.assertIsNone(r["sessions"][0]["usage"])
        self.assertIn("invalid_usage", r["sessions"][0]["gaps"])


if __name__ == "__main__": unittest.main()


PLAN_ENTITY = "a" * 64

PLAN_TEXT = """# Fixture plan

## Brief
Mode: explore

## Tasks
### MFixture - join fixtures
- [completed] Credited fixture row ~fx01 | proof: cmd bash -c 'true'
- [completed] Second fixture row ~fx02 | proof: cmd bash -c 'true'
- [pending] Open fixture row ~fx03 | proof: cmd bash -c 'true'

## Progress

- 2026-09-10T10:00:00Z ~fx01 PROOF evidence/x.md -> pass
- 2026-09-10T11:00:00Z ~fx02 PROOF evidence/x.md -> pass
"""

CLAUDE_ACCEPT = {"type": "assistant", "timestamp": "2026-09-10T10:05:00Z", "sessionId": "s1",
                 "message": {"id": "m1", "model": "claude-x", "usage": {"input_tokens": 10, "output_tokens": 5},
                             "content": [{"type": "tool_use", "name": "Bash", "input": {"command":
                                 "shadow accept --row '~fx01' --entity " + PLAN_ENTITY + " --by seat-a"}}]}}
CLAUDE_PROSE = {"type": "assistant", "timestamp": "2026-09-10T10:06:00Z", "sessionId": "s1",
                "message": {"id": "m2", "model": "claude-x", "usage": {"input_tokens": 10, "output_tokens": 5},
                            "content": [{"type": "text", "text":
                                "run: shadow accept --row '~fx02' --entity " + PLAN_ENTITY + " --by seat-a"}]}}
CLAUDE_THROW = {"type": "assistant", "timestamp": "2026-09-10T09:00:00Z", "sessionId": "s2",
                "message": {"id": "m3", "model": "claude-x", "usage": {"input_tokens": 7, "output_tokens": 1},
                            "content": [{"type": "tool_use", "name": "Bash", "input": {"command":
                                "shadow throw --entity " + PLAN_ENTITY + " --task '~fx01' --by seat-b"}}]}}


class JoinTests(unittest.TestCase):
    def joined(self, records, plan_text=PLAN_TEXT, since="2026-09-01T00:00:00Z", until="2026-09-30T00:00:00Z"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "native.jsonl"
            source.write_text("".join(json.dumps(r) + "\n" for r in records))
            plan = root / "PLAN.md"
            plan.write_text(plan_text)
            return audit.audit([( "claude", source)], since=since, until=until,
                               plan_path=plan, entity=PLAN_ENTITY)

    def test_accept_marker_credits_the_session_and_row(self):
        result = self.joined([CLAUDE_ACCEPT])
        join = result["join"]
        self.assertEqual(join["eligible_root_tasks"], 2)
        self.assertEqual(join["mapped_root_tasks"], 1)
        self.assertEqual(join["mapped_rows"], ["~fx01"])
        self.assertEqual(join["accepted_work_rate"], 0.5)
        self.assertEqual(join["real_work_allocation"]["claude"]["credited_sessions"], 1)
        self.assertEqual(join["plan_snapshot"]["entity"], PLAN_ENTITY)
        self.assertIn("generation", join["plan_snapshot"])

    def test_prose_mention_is_provenance_never_credit(self):
        result = self.joined([CLAUDE_ACCEPT, CLAUDE_PROSE])
        join = result["join"]
        self.assertEqual(join["mapped_rows"], ["~fx01"])
        self.assertTrue(any(m["row"] == "~fx02" and m["via"] == "text"
                            for m in join["provenance_markers"]))
        self.assertNotIn("~fx02", join["mapped_rows"])

    def test_throw_marker_never_credits(self):
        result = self.joined([CLAUDE_THROW])
        join = result["join"]
        self.assertEqual(join["mapped_root_tasks"], 0)
        self.assertTrue(any(m["verb"] == "throw" for m in join["provenance_markers"]))

    def test_wrong_entity_accept_is_refused_not_credited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "native.jsonl"
            source.write_text(json.dumps(CLAUDE_ACCEPT) + "\n")
            plan = root / "PLAN.md"
            plan.write_text(PLAN_TEXT)
            result = audit.audit([("claude", source)], since="2026-09-01T00:00:00Z",
                                 until="2026-09-30T00:00:00Z", plan_path=plan,
                                 entity="b" * 64)
            self.assertEqual(result["join"]["mapped_root_tasks"], 0)
            self.assertEqual(result["join"]["unmatched_accepts"][0]["reason"], "entity_mismatch")

    def test_row_outside_window_is_not_eligible(self):
        result = self.joined([CLAUDE_ACCEPT], since="2026-09-11T00:00:00Z", until="2026-09-30T00:00:00Z")
        self.assertEqual(result["join"]["eligible_root_tasks"], 0)  # both proofs are Sept 10
        self.assertEqual(result["join"]["accepted_work_rate"], None)
        self.assertEqual(result["join"]["unmatched_accepts"][0]["reason"], "row_not_eligible")

    def test_inclusive_since_and_exclusive_until_boundaries(self):
        result = self.joined([CLAUDE_ACCEPT], since="2026-09-10T10:00:00Z", until="2026-09-10T11:00:00Z")
        self.assertEqual(result["join"]["eligible_root_tasks"], 1)  # ~fx01 at 10:00 in, ~fx02 at 11:00 out

    def test_completed_row_without_dated_proof_is_undated(self):
        text = PLAN_TEXT.replace("- 2026-09-10T11:00:00Z ~fx02 PROOF evidence/x.md -> pass\n", "")
        result = self.joined([], plan_text=text)
        join = result["join"]
        self.assertEqual(join["eligible_root_tasks"], 1)
        self.assertEqual(join["undated_completed_rows"], ["~fx02"])

    def test_plan_without_entity_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "native.jsonl"
            source.write_text("")
            with self.assertRaises(audit.Refusal) as caught:
                audit.audit([("claude", source)], plan_path=Path(directory) / "PLAN.md")
            self.assertEqual(str(caught.exception), "plan_entity_unresolved")

    def test_join_is_deterministic_across_reruns(self):
        import subprocess, sys as sysmod
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "native.jsonl"
            source.write_text(json.dumps(CLAUDE_ACCEPT) + "\n")
            plan = root / "PLAN.md"
            plan.write_text(PLAN_TEXT)
            cmd = [sysmod.executable, "-B", str(audit.__file__ if hasattr(audit, '__file__') else
                   Path(audit.__spec__.origin)), "--source", f"claude={source}",
                   "--plan", str(plan), "--entity", PLAN_ENTITY]
            first = subprocess.run(cmd, capture_output=True, text=True)
            second = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0)
            self.assertEqual(first.stdout, second.stdout)

    def test_drift_flag_on_backdated_marker(self):
        early = dict(CLAUDE_ACCEPT, timestamp="2026-09-01T10:05:00Z")
        result = self.joined([early])
        self.assertEqual(len(result["join"]["marker_disagreements"]), 1)
