from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


status = load("shadow-status")
doctor = load("shadow-doctor")


class HuddleStatusTests(unittest.TestCase):
    def test_private_legacy_recovery_is_actionable_without_a_huddle(self):
        from tests.test_throw import fixture

        with tempfile.TemporaryDirectory() as dirname:
            repo, home, env = fixture(Path(dirname))
            with mock.patch.dict(os.environ, env):
                board = status._board
                board.reconcile([{"plan": str(repo / "PLAN.md"), "project": "demo",
                                  "priority": 2, "candidates": ["~bb22"]}], [])
                with board._transaction(home) as (root, path, payload):
                    if payload["schema"] == board.V1_SCHEMA:
                        payload = board.migrate_v1_to_v2(payload)
                    payload["claims"] = [{
                        "entity": payload["entities"][0]["id"], "row": "~bb22",
                        "owner": "legacy-seat", "claimed_at": "2000-01-01T00:00:00Z",
                        "return_by": "2000-01-01T08:00:00Z", "recovery": board.RECOVERY_ACTION,
                        "access": "unscoped", "repository_binding": None,
                        "write_scope": [], "claim_revision": 0,
                    }]
                    board._write_and_commit(root, path, payload, "test: legacy recovery guidance")
                before = ((home / ".shadow" / "board.json").read_bytes(),
                          board._journal_head(home / ".shadow"))
            for flags in (("--by", "legacy-seat"),
                          ("--root", str(repo), "--by", "legacy-seat")):
                result = subprocess.run([sys.executable, str(ROOT / "scripts" / "shadow-status.py"),
                                         *flags], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Unbound legacy claims", result.stdout)
                self.assertIn("classify or return before source writes", result.stdout)
                self.assertIn("--claim-revision 0", result.stdout)
                self.assertIn("--expect-board", result.stdout)
                self.assertIn("--repo <verified-checkout>", result.stdout)
                self.assertIn("shadow return --entity", result.stdout)
                self.assertIn("--row '~bb22' --by legacy-seat", result.stdout)
                self.assertEqual(before, ((home / ".shadow" / "board.json").read_bytes(),
                                          board._journal_head(home / ".shadow")))
            for flags in ((), ("--by", "other-seat"), ("--json",), ("--in-flight", "--json")):
                result = subprocess.run([sys.executable, str(ROOT / "scripts" / "shadow-status.py"),
                                         *flags], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("Unbound legacy claims", result.stdout)
                self.assertNotIn("<verified-checkout>", result.stdout)

    def test_private_legacy_recovery_excludes_read_only_and_known_bindings(self):
        claim = {"entity": "a" * 64, "row": "~aa11", "owner": "A",
                 "claim_revision": 7, "access": "unscoped", "repository_binding": None}
        payload = {"revision": 9, "claims": [claim]}
        self.assertIn("--claim-revision 7", status.render_seat_legacy_claims(payload, "A"))
        self.assertIsNone(status.render_seat_legacy_claims(payload, "B"))
        claim["access"] = "read_only"
        self.assertIsNone(status.render_seat_legacy_claims(payload, "A"))
        claim.update(access="unscoped", repository_binding={"remote_identity": "example/repo"})
        self.assertIsNone(status.render_seat_legacy_claims(payload, "A"))

    def huddle(self):
        a = {"entity": "a" * 64, "row": "~aa11", "claim_revision": 4, "owner": "A", "claimed_at": "2026-09-05T01:00:00Z"}
        b = {"entity": "a" * 64, "row": "~bb22", "claim_revision": 5, "owner": "B", "claimed_at": "2026-09-05T01:00:01Z"}
        return {"id": "hdl_00000001", "generation": 3, "state": "awaiting_compliance", "round": 2,
                "reply_by": "2026-09-05T01:02:00Z", "claims": [a, b], "holds": [b],
                "resolution": {"rule": "exact_claim_owner", "write_owners": [a],
                               "actions": [{"action": "continue"}, {"action": "return_required"}]},
                "compliance": [{"claim": b, "status": "pending"}],
                "replacements": [], "bids": [{"evidence": {"value": "/Users/private/provider-token"}}]}

    def test_marker_is_exact_compact_public_shape(self):
        marker = status.in_flight_huddle_marker(self.huddle())
        self.assertEqual(set(marker), {"id", "generation", "state", "round", "deadline", "seats", "holds", "settled_rule", "actions"})
        rendered = json.dumps(marker)
        for forbidden in ("claim_revision", "evidence", "provider", "/Users/", "scope", "token"):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(marker["holds"], {"A": False, "B": True})

    def test_root_views_only_embed_marker_and_do_not_mutate(self):
        payload = {"schema": "shadow.root-board.v2", "revision": 9, "projects": [], "entities": [], "claims": [],
                   "huddles": [self.huddle()]}
        before = json.dumps(payload, sort_keys=True)
        view = status.root_board_view(payload)
        flight = status.in_flight_root_board_view(payload)
        self.assertEqual(view["huddles"], [status.in_flight_huddle_marker(self.huddle())])
        self.assertEqual(flight["huddles"], view["huddles"])
        self.assertEqual(json.dumps(payload, sort_keys=True), before)

    def test_seat_view_has_action_but_person_marker_does_not(self):
        view = status.seat_huddle_view(self.huddle(), "B")
        self.assertEqual(view["disposition"], "return_required")
        self.assertEqual(view["next_command"], "shadow return --entity " + "a" * 64 + " --row ~bb22 --by B")
        help_output = subprocess.run([sys.executable, str(ROOT / "scripts" / "shadow-return.py"), "--help"],
                                     capture_output=True, text=True, check=True).stdout
        self.assertIn("--entity", help_output)
        self.assertNotIn("next_command", status.in_flight_huddle_marker(self.huddle()))

    def test_adopted_hold_is_current_but_remote_pending_keeps_source_owner(self):
        huddle = self.huddle()
        original_b = huddle["claims"][1]
        adopted_b = {**original_b, "owner": "C", "claim_revision": 7, "claimed_at": "2026-09-05T01:03:00Z"}
        original_a = huddle["claims"][0]
        remote_a = {**original_a, "owner": "D", "claim_revision": 8, "claimed_at": "2026-09-05T01:04:00Z"}
        huddle["replacements"] = [{"original": original_b, "current": adopted_b}]
        huddle["remote_transition"] = {"source_claim": original_a, "successor_claim": remote_a}
        marker = status.in_flight_huddle_marker(huddle)
        huddle["state"] = "remote_pending"
        marker = status.in_flight_huddle_marker(huddle)
        self.assertEqual(marker["seats"], ["A", "C"])
        self.assertEqual(marker["holds"], {"A": False, "C": True})
        view = status.seat_huddle_view(huddle, "C")
        self.assertEqual(view["disposition"], "return_required")
        self.assertEqual(view["next_command"], "shadow return --entity " + "a" * 64 + " --row ~bb22 --by C")

    def test_resolved_huddle_is_not_an_active_private_resume_block(self):
        huddle = self.huddle()
        huddle["state"] = "resolved"
        self.assertIsNone(status.render_seat_huddle(huddle, "A"))

    def test_one_seat_with_held_and_writer_claims_gets_per_claim_actions(self):
        huddle = self.huddle()
        a = huddle["claims"][0]
        held = huddle["claims"][1]
        huddle["claims"][1] = {**held, "owner": "A", "row": "~cc33"}
        huddle["holds"] = [huddle["claims"][1]]
        huddle["resolution"]["write_owners"] = [a]
        huddle["compliance"] = []
        view = status.seat_huddle_view(huddle, "A")
        self.assertEqual(view["disposition"], "mixed")
        actions = {item["claim"]["row"]: item["next_command"] for item in view["claims"]}
        self.assertIn("shadow amp", actions["~aa11"])
        self.assertEqual(actions["~cc33"], "shadow huddle show --id hdl_00000001")

    def test_doctor_absent_runtime_is_normal_and_malformed_board_is_reported_not_repaired(self):
        with tempfile.TemporaryDirectory() as dirname:
            home = Path(dirname)
            shadow = home / ".shadow"
            shadow.mkdir()
            board = shadow / "board.json"
            board.write_bytes(b"not json")
            before = board.read_bytes()
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                result = doctor.huddle_check()
            self.assertEqual(result["state"], "fail")
            self.assertEqual(board.read_bytes(), before)
            self.assertFalse((shadow / "runtime" / "huddle-delivery").exists())
