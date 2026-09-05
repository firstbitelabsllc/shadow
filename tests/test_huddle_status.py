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
