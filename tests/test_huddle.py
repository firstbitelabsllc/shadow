from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.proc_fixture import git

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as board_api


E1 = "a" * 64
NOW = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)


class HuddleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.home = Path(self.temp_dir.name)

    def v1_board(self, *, revision: int = 7, with_claim: bool = True) -> dict:
        claim = {
            "entity": E1,
            "row": "~aa11",
            "owner": "Codex",
            "claimed_at": "2026-09-04T15:00:00Z",
            "return_by": "2026-09-04T17:00:00Z",
            "recovery": board_api.RECOVERY_ACTION,
        }
        return {
            "schema": board_api.SCHEMA,
            "revision": revision,
            "projects": [{"id": "shadow", "priority": 1}],
            "entities": [{
                "id": E1,
                "project": "shadow",
                "plan": str(self.home / "plans" / "shadow" / "PLAN.md"),
                "resume": "~aa11",
            }],
            "claims": [claim] if with_claim else [],
        }

    def v2_board(self, *, with_claim: bool = True) -> dict:
        return board_api.migrate_v1_to_v2(self.v1_board(with_claim=with_claim))

    def seed_v2(self, payload: dict | None = None) -> tuple[Path, Path]:
        board_api.ensure(home=self.home)
        with board_api._transaction(self.home) as (root, path, current):
            value = payload or board_api.migrate_v1_to_v2(current)
            board_api._validate(value)
            board_api._write_and_commit(root, path, value, "test: seed v2 board", now=NOW)
            return root, path

    def authority(self) -> tuple[bytes, str]:
        root = self.home / ".shadow"
        return (root / board_api.BOARD_NAME).read_bytes(), board_api._journal_head(root)


class HuddleBidTests(HuddleTestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b = HuddleGraphTests.seed(self, [["a"], ["a"]])
        self.huddle = HuddleGraphTests.open(self, self.a, [self.b]).payload["huddles"][0]

    def request(self, participant=None, **changes):
        participant = participant or self.a
        value = dict(huddle_id=self.huddle["id"], seat=participant["owner"],
            claim=board_api._claim_ref(participant), role="own", scope=participant["write_scope"],
            reason="existing_claim", target=None, support_claim=None,
            evidence={"kind": "claim", "value": "self"}, round=1,
            expected_huddle_generation=self.huddle["generation"])
        return value | changes

    def submit(self, participant=None, *, now=NOW, **changes):
        return board_api.submit_huddle_bid(**self.request(participant, **changes), now=now, home=self.home)

    def test_multiple_bids_share_generation_and_replay_returns_original_bid(self):
        first = self.submit()
        receipt = board_api.bid_receipt(self.huddle["id"], board_api._claim_ref(self.a), 1, home=self.home)
        second = self.submit(self.b, role="stand_down", reason="duplicate_intent", now=NOW + timedelta(seconds=2))
        self.assertEqual(second.payload["revision"], first.payload["revision"] + 1)
        self.assertEqual(second.payload["huddles"][0]["generation"], self.huddle["generation"])
        before = self.authority()
        replay = self.submit(now=NOW + timedelta(minutes=3))
        self.assertFalse(replay.changed)
        self.assertIsNone(replay.event)
        self.assertEqual(board_api.bid_receipt(self.huddle["id"], board_api._claim_ref(self.a), 1, home=self.home), receipt)
        self.assertEqual(self.authority(), before)
        with self.assertRaisesRegex(board_api.BoardError, "replay"):
            self.submit(role="unavailable")
        self.assertEqual(self.authority(), before)

    def test_invalid_new_bids_refuse_without_mutation(self):
        before = self.authority()
        for changes in (
            {"seat": "Other"}, {"claim": {**board_api._claim_ref(self.a), "claim_revision": 0}},
            {"expected_huddle_generation": 99}, {"round": 2}, {"round": True},
            {"role": "stand_down"}, {"role": "yield", "target": board_api._claim_ref(self.a)},
            {"scope": ["expanded"]}, {"role": "disjoint", "scope": []},
            {"evidence": {"kind": "claim", "value": "/private/path"}},
            {"target": board_api._claim_ref(self.b)},
        ):
            with self.subTest(changes=changes), self.assertRaises(board_api.BoardError):
                self.submit(**changes)
            self.assertEqual(self.authority(), before)
        with self.assertRaisesRegex(board_api.BoardError, "deadline"):
            self.submit(now=NOW + timedelta(minutes=2))
        self.assertEqual(self.authority(), before)

    def test_bids_are_intent_not_scope_change_or_handoff(self):
        before = board_api.snapshot(home=self.home)["claims"]
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        after = board_api.snapshot(home=self.home)
        self.assertEqual(after["claims"], before)
        self.assertEqual(after["huddles"][0]["holds"], self.huddle["holds"])
        self.assertIsNone(after["huddles"][0]["resolution"])

    def test_disjoint_bid_does_not_shrink_authority_or_release_hold(self):
        before = board_api.snapshot(home=self.home)
        self.submit(self.b, role="disjoint", scope=["a/narrow"], reason="path_disjoint")
        after = board_api.snapshot(home=self.home)
        self.assertEqual(after["claims"], before["claims"])
        self.assertEqual(after["huddles"][0]["holds"], before["huddles"][0]["holds"])
        self.assertEqual(after["huddles"][0]["generation"], before["huddles"][0]["generation"])

    def support(self, *, access="read_only", scope=None):
        with board_api._transaction(self.home) as (root, path, payload):
            support = {**self.b, "row": "~ss11", "access": access,
                       "write_scope": scope or [], "claim_revision": payload["revision"] + 1}
            if access == "read_only":
                support["repository_binding"] = None
            payload["claims"].append(support)
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: support claim", now=NOW)
            entity = next(e for e in payload["entities"] if e["id"] == support["entity"])
        plan = Path(entity["plan"])
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("# Support\n\n## Tasks\n\n- [pending] Support ~ss11 | proof: cmd true\n")
        return support, plan

    def test_review_support_requires_reachable_canonical_checkpoint(self):
        support, plan = self.support()
        valid = plan.read_text()
        for invalid in ("# Empty\n", valid.replace("pending", "completed"),
                        valid.replace("cmd true", "gate approval"),
                        valid.replace(" | proof: cmd true", ""),
                        valid.rstrip() + " | needs: ~zz99\n"):
            plan.write_text(invalid)
            before = self.authority()
            with self.subTest(plan=invalid), self.assertRaises(board_api.BoardError):
                self.submit(self.b, role="review", scope=[], support_claim=board_api._claim_ref(support))
            self.assertEqual(self.authority(), before)
        plan.write_text(valid)
        self.assertTrue(self.submit(self.b, role="review", scope=[],
                                   support_claim=board_api._claim_ref(support)).changed)

    def test_prove_support_cannot_conflict_with_selected_writer(self):
        support, _ = self.support(access="write", scope=["a"])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "support.*conflict"):
            self.submit(self.b, role="prove", support_claim=board_api._claim_ref(support))
        self.assertEqual(self.authority(), before)


class HuddleSettlementTests(HuddleTestCase):
    request = HuddleBidTests.request
    submit = HuddleBidTests.submit

    def setUp(self):
        super().setUp()
        self.a, self.b = HuddleGraphTests.seed(self, [["a", "b"], ["a"]])
        self.huddle = HuddleGraphTests.open(self, self.a, [self.b]).payload["huddles"][0]
        for entity in board_api.snapshot(home=self.home)["entities"]:
            plan = Path(entity["plan"])
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("# Work\n\n## Tasks\n\n- [pending] Work ~aa11 | proof: cmd true\n")

    def settle(self, *, now=NOW, **changes):
        snapshot = board_api.snapshot(home=self.home)
        request = dict(huddle_id=self.huddle["id"], actor_claim=board_api._claim_ref(self.a),
                       expected_generation=snapshot["huddles"][0]["generation"],
                       expected_board_revision=snapshot["revision"])
        return board_api.settle_huddle(**(request | changes), now=now, home=self.home)

    def test_conflict_gets_one_counter_round_then_existing_owner_wins(self):
        self.submit()
        self.submit(self.b)
        initial = board_api.snapshot(home=self.home)
        first = self.settle().payload
        h = first["huddles"][0]
        self.assertEqual((h["state"], h["round"], h["generation"]), ("open_round_2", 2, 2))
        self.assertEqual(h["reply_by"], "2026-09-04T16:02:00Z")
        self.assertEqual(first["claims"], initial["claims"])
        self.assertEqual(h["bids"], initial["huddles"][0]["bids"])
        self.assertFalse(self.submit().changed)
        result = self.settle(now=NOW + timedelta(minutes=2)).payload
        h = result["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["resolution"]["write_owners"], [board_api._claim_ref(self.a)])
        self.assertEqual(h["holds"], [board_api._claim_ref(self.b)])
        self.assertEqual([b["role"] for b in h["bids"] if b["round"] == 2], ["unavailable", "unavailable"])
        self.assertEqual(result["claims"], initial["claims"])
        before = self.authority()
        with self.assertRaises(board_api.BoardError):
            self.settle(now=NOW + timedelta(minutes=4))
        self.assertEqual(self.authority(), before)

    def test_disjoint_scopes_commit_with_resolution_not_at_bid(self):
        self.submit(role="disjoint", scope=["a/one"], reason="path_disjoint")
        self.submit(self.b, role="disjoint", scope=["a/two"], reason="path_disjoint")
        result = self.settle().payload
        h = result["huddles"][0]
        self.assertEqual(h["state"], "resolved")
        self.assertEqual(h["resolution"]["rule"], "path_disjoint")
        self.assertEqual(h["holds"], [])
        self.assertEqual(h["edges"], [])
        self.assertEqual(h["resolution"]["write_owners"], h["claims"])
        self.assertEqual([c["write_scope"] for c in result["claims"]], [["a/one"], ["a/two"]])

    def test_early_missing_bid_and_stale_identity_refuse_without_writes(self):
        self.submit()
        before = self.authority()
        for changes in ({}, {"expected_generation": 99}, {"expected_board_revision": 0},
                        {"actor_claim": {**board_api._claim_ref(self.a), "owner": "Other"}}):
            with self.subTest(changes=changes), self.assertRaises(board_api.BoardError):
                self.settle(**changes)
            self.assertEqual(self.authority(), before)
        h = self.settle(now=NOW + timedelta(minutes=2)).payload["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["round"], 1)

    def test_missing_or_changed_canonical_plan_refuses_without_writes(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        entity = board_api.snapshot(home=self.home)["entities"][1]
        plan = Path(entity["plan"])
        for text in ("# Empty\n", "# Work\n\n## Tasks\n- [completed] Work ~aa11 | proof: cmd true\n",
                     "# Work\n\n## Tasks\n- [pending] Work ~aa11\n"):
            plan.write_text(text)
            before = self.authority()
            with self.assertRaises(board_api.BoardError):
                self.settle()
            self.assertEqual(self.authority(), before)

    def test_local_handoff_requires_matching_pair_and_preserves_claim_instance(self):
        repo = HuddleAccessTests.repo(self)
        binding = board_api.repository_binding(repo)
        self.a["repository_binding"] = binding
        self.b["repository_binding"] = binding
        with board_api._transaction(self.home) as (root, path, payload):
            for claim in payload["claims"]:
                claim["repository_binding"] = binding
            for entity in payload["entities"]:
                plan = self.home / ".shadow" / "plans" / entity["id"] / "PLAN.md"
                plan.parent.mkdir(parents=True)
                plan.write_text(Path(entity["plan"]).read_text())
                entity["plan"] = str(plan)
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: local plans", now=NOW)
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        before = self.authority()
        with self.assertRaises(board_api.BoardError):
            self.settle(now=NOW + timedelta(minutes=2))
        self.assertEqual(self.authority(), before)
        self.submit(self.b, reason="owner_authorized_handoff")
        result = self.settle().payload
        successor = {**self.a, "owner": self.b["owner"]}
        self.assertEqual(result["claims"], [successor, self.b])
        h = result["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["resolution"]["write_owners"], [board_api._claim_ref(successor)])
        self.assertEqual(h["resolution"]["rule"], "owner_authorized_handoff")
        self.assertEqual(h["holds"], [board_api._claim_ref(self.b)])
        before = self.authority()
        for claim in (successor, self.b):
            context = {key: claim[key] for key in ("entity", "row", "owner", "claim_revision")}
            context["board_revision"] = result["revision"]
            if claim == successor:
                self.assertFalse(board_api.authorize_host_attempt(context=context, repo=repo,
                    write_scope=claim["write_scope"], authority_proposal=False, now=NOW, home=self.home).changed)
            else:
                with self.assertRaisesRegex(board_api.BoardError, "held"):
                    board_api.authorize_host_attempt(context=context, repo=repo,
                        write_scope=claim["write_scope"], authority_proposal=False, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_scope_shrink_does_not_promote_an_explicit_stand_down(self):
        self.submit(role="disjoint", scope=["b"], reason="path_disjoint")
        self.submit(self.b, role="stand_down", reason="duplicate_intent")
        result = self.settle().payload["huddles"][0]
        self.assertEqual(result["state"], "awaiting_compliance")
        self.assertEqual(result["resolution"]["write_owners"], [board_api._claim_ref(self.a)])
        self.assertEqual(result["resolution"]["actions"][1]["action"], "return_required")
        self.assertEqual(result["holds"], [board_api._claim_ref(self.b)])


class HuddleLifecycleTests(HuddleTestCase):
    request = HuddleBidTests.request
    submit = HuddleBidTests.submit
    settle = HuddleSettlementTests.settle

    def setUp(self):
        super().setUp()
        environment = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)
        payload = self.v2_board(with_claim=False)
        payload["entities"] = []
        self.plans = {}
        for index, owner in enumerate(("A", "B"), 1):
            plan = self.home / ".shadow" / "plans" / owner.lower() / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("# Work\n\n## Brief\n- Project: shadow\n- Mode: ship\n\n"
                "## Tasks\n### Outcome\n- [pending] Work ~aa11 | proof: cmd true\n"
                "- [pending] Done ~dd11 (DoD) | proof: read receipt -> reviewed | needs: ~aa11\n\n## Progress\n")
            entity = board_api.entity_id(plan)
            self.plans[owner] = plan
            payload["entities"].append(dict(id=entity, project="shadow", plan=str(plan), resume="~aa11"))
            claim = self.v2_board()["claims"][0]
            claim.update(entity=entity, owner=owner, claim_revision=index, access="write",
                repository_binding={"common_dir_sha256": "c" * 64, "remote_identity": None}, write_scope=["a"])
            payload["claims"].append(claim)
        self.a, self.b = payload["claims"]
        self.seed_v2(payload)
        self.huddle = HuddleGraphTests.open(self, self.a, [self.b]).payload["huddles"][0]

    def release(self, claim, *, reason="handback"):
        return board_api.release(self.plans[claim["owner"]], claim["row"], owner=claim["owner"],
                                 reason=reason, expected_claim=claim, now=NOW, home=self.home)

    def age_claim(self, claim):
        with board_api._transaction(self.home) as (root, path, payload):
            current = next(item for item in payload["claims"]
                           if (item["entity"], item["row"]) == (claim["entity"], claim["row"]))
            # A Huddle reference includes claimed_at; expiry is represented only
            # by the lease, not by fabricating a different claim instance.
            current["return_by"] = "2026-09-04T15:59:00Z"
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: age claim", now=NOW)

    def set_return_by(self, claim, value):
        with board_api._transaction(self.home) as (root, path, payload):
            current = next(item for item in payload["claims"]
                           if (item["entity"], item["row"]) == (claim["entity"], claim["row"]))
            current["return_by"] = value
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: set claim lease", now=NOW)

    def complete_plan(self, owner):
        receipt = "- 2026-09-04T16:00:00Z ~aa11 PROOF cmd true -> pass (manual)"
        plan = self.plans[owner]
        plan.write_text(plan.read_text().replace("[pending] Work", "[completed] Work")
                        + f"\n{receipt}\n")
        return receipt

    def test_return_removes_membership_and_resolves_surviving_owner(self):
        result, changed = self.release(self.a)
        self.assertTrue(changed)
        self.assertEqual(result["claims"], [self.b])
        h = result["huddles"][0]
        self.assertEqual(h["state"], "resolved")
        self.assertEqual(h["claims"], [board_api._claim_ref(self.b)])
        self.assertEqual(h["resolution"]["rule"], "exact_claim_owner")
        self.assertEqual(h["holds"], [])
        self.assertEqual(h["edges"], [])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "claim changed"):
            self.release(self.a)
        self.assertFalse(board_api.release(self.plans["A"], self.a["row"], owner="A",
            reason="handback", now=NOW, home=self.home)[1])
        self.assertEqual(self.authority(), before)

    def test_required_return_needs_changed_canonical_plan_and_clears_compliance(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        self.settle()
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "canonical"):
            self.release(self.b)
        self.assertEqual(self.authority(), before)
        plan = self.plans["B"]
        plan.write_text(plan.read_text().replace("[pending] Work", "[blocked] Work")
                        + "\n## Deferred\n- ~aa11 | overlap owned by A | wake: A completes the shared change\n")
        result, changed = self.release(self.b, reason="blocked")
        self.assertTrue(changed)
        h = result["huddles"][0]
        self.assertEqual(h["state"], "resolved")
        self.assertEqual(h["holds"], [])
        self.assertEqual(h["compliance"][0]["status"], "satisfied")
        self.assertEqual(h["compliance"][0]["completion"]["kind"], "return")
        self.assertEqual(result["claims"], [self.a])

    def test_completion_reservation_refuses_held_and_pending_compliance(self):
        for claim in (self.b, self.a):
            if claim == self.a:
                self.submit()
                self.submit(self.b, role="stand_down")
                self.settle()
            plan = self.plans[claim["owner"]]
            token, _ = board_api.frozen_plan_snapshot(plan, home=self.home)
            before = self.authority()
            with self.assertRaises(board_api.BoardError):
                board_api.reserve_completion(plan, claim["row"], claim["owner"],
                    expected_plan=token, now=NOW, home=self.home)
            self.assertEqual(self.authority(), before)

    def test_selected_completion_releases_node_but_held_completion_refuses(self):
        for claim in (self.b, self.a):
            plan = self.plans[claim["owner"]]
            plan.write_text(plan.read_text().replace("[pending] Work", "[completed] Work")
                            + "\n- 2026-09-04T16:00:00Z ~aa11 PROOF true -> pass (accept)\n")
            before = self.authority()
            if claim == self.b:
                with self.assertRaisesRegex(board_api.BoardError, "Huddle held"):
                    self.release(claim, reason="completed")
                self.assertEqual(self.authority(), before)
            else:
                result, changed = self.release(claim, reason="completed")
                self.assertTrue(changed)
                self.assertEqual(result["huddles"][0]["claims"], [board_api._claim_ref(self.b)])
                self.assertEqual(result["huddles"][0]["state"], "resolved")

    def test_stale_completed_hold_recovers_before_settlement(self):
        self.age_claim(self.b)
        before = self.authority()
        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 0)
        self.assertEqual(self.authority(), before)

        receipt = self.complete_plan("B")
        self.set_return_by(self.b, "2026-09-04T17:00:00Z")
        before = self.authority()
        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 0)
        self.assertEqual(self.authority(), before)

        self.age_claim(self.b)
        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 1)
        result = board_api.snapshot(home=self.home)
        self.assertEqual([claim["owner"] for claim in result["claims"]], ["A"])
        h = result["huddles"][0]
        self.assertEqual(h["state"], "resolved")
        self.assertEqual(h["claims"], [board_api._claim_ref(self.a)])
        self.assertEqual(h["resolution"]["rule"], "exact_claim_owner")
        self.assertNotIn(receipt, json.dumps(result))

    def test_stale_completed_plan_race_keeps_board_and_journal_unchanged(self):
        self.complete_plan("B")
        self.age_claim(self.b)
        before = self.authority()
        original_write = board_api._write_and_commit

        def race(*args, **kwargs):
            self.plans["B"].write_text(self.plans["B"].read_text() + "\n- racing edit\n")
            return original_write(*args, **kwargs)

        with mock.patch.object(board_api, "_write_and_commit", side_effect=race):
            with self.assertRaisesRegex(board_api.BoardError, "canonical plan changed"):
                board_api.release_stranded_completed_claims(now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_stale_completed_support_claim_refuses_without_retargeting_bid(self):
        support = {**self.b, "row": "~ss11", "access": "read_only",
                   "repository_binding": None, "write_scope": [], "claim_revision": 3}
        with board_api._transaction(self.home) as (root, path, payload):
            payload["claims"].append(support)
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: add support", now=NOW)
        plan = self.plans["B"]
        plan.write_text("# Support\n\n## Tasks\n- [pending] Support ~ss11 | proof: cmd true\n\n## Progress\n")
        self.submit(self.b, role="review", scope=[], support_claim=board_api._claim_ref(support))
        plan.write_text("# Support\n\n## Tasks\n- [completed] Support ~ss11 | proof: cmd true\n"
                        "\n## Progress\n- 2026-09-04T16:00:00Z ~ss11 PROOF cmd true -> pass (manual)\n")
        self.age_claim(support)
        before = self.authority()

        with self.assertRaisesRegex(board_api.BoardError, "support"):
            board_api.release_stranded_completed_claims(now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_stale_required_return_preserves_another_pending_return(self):
        plan_c = self.home / ".shadow" / "plans" / "c" / "PLAN.md"
        plan_c.parent.mkdir(parents=True)
        plan_c.write_text(self.plans["B"].read_text())
        entity_c = board_api.entity_id(plan_c)
        with board_api._transaction(self.home) as (root, path, payload):
            claim_c = copy.deepcopy(self.b)
            claim_c.update(entity=entity_c, owner="C", claim_revision=3)
            payload["entities"].append(dict(id=entity_c, project="shadow", plan=str(plan_c),
                                             resume="~aa11"))
            payload["claims"].append(claim_c)
            self.plans["C"] = plan_c
            h = payload["huddles"][0]
            ref_c = board_api._claim_ref(claim_c)
            h["claims"] = sorted(h["claims"] + [ref_c], key=board_api._claim_rank)
            h["edges"] = sorted(
                h["edges"] + [dict(left=board_api._claim_ref(self.a), right=ref_c, kinds=["path_overlap"]),
                              dict(left=board_api._claim_ref(self.b), right=ref_c, kinds=["path_overlap"])],
                key=lambda edge: (board_api._claim_rank(edge["left"]),
                                  board_api._claim_rank(edge["right"])),
            )
            h["holds"] = board_api.claim_holds(h)
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: join third claim", now=NOW)
        self.submit()
        self.submit(self.b, role="stand_down", reason="duplicate_intent")
        self.submit(next(claim for claim in board_api.snapshot(home=self.home)["claims"]
                         if claim["owner"] == "C"),
                    role="stand_down", reason="duplicate_intent")
        settled = self.settle().payload
        h_before = settled["huddles"][0]
        receipt = self.complete_plan("B")
        self.age_claim(self.b)

        before_release_revision = board_api.snapshot(home=self.home)["revision"]
        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 1)

        result = board_api.snapshot(home=self.home)
        h = result["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["resolution"], h_before["resolution"])
        self.assertEqual(h["holds"], [entry["claim"] for entry in h["compliance"]
                                      if entry["status"] == "pending"])
        self.assertEqual([entry["status"] for entry in h["compliance"]], ["satisfied", "pending"])
        completion = h["compliance"][0]["completion"]
        self.assertEqual(completion["kind"], "proof_first_stale_recovery")
        self.assertEqual(completion["board_revision"], before_release_revision + 1)
        self.assertEqual(completion["receipt"], hashlib.sha256(receipt.encode()).hexdigest())

    def test_stale_selected_writer_completion_preserves_pending_return(self):
        self.submit()
        self.submit(self.b, role="stand_down", reason="duplicate_intent")
        settled = self.settle().payload
        self.complete_plan("A")
        self.age_claim(self.a)

        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 1)

        result = board_api.snapshot(home=self.home)
        self.assertEqual([claim["owner"] for claim in result["claims"]], ["B"])
        h = result["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["resolution"], settled["huddles"][0]["resolution"])
        self.assertEqual(h["holds"], [board_api._claim_ref(self.b)])
        self.assertEqual(h["compliance"][0]["status"], "pending")

    def test_stale_local_handoff_successor_completion_preserves_pending_return(self):
        self.submit(role="yield", reason="owner_authorized_handoff",
                    target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        settled = self.settle().payload
        successor = next(claim for claim in settled["claims"] if claim["entity"] == self.a["entity"])
        self.assertEqual(successor["owner"], "B")
        self.complete_plan("A")
        self.age_claim(successor)

        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 1)

        result = board_api.snapshot(home=self.home)
        self.assertEqual([claim["owner"] for claim in result["claims"]], ["B"])
        self.assertEqual(result["claims"][0]["row"], self.b["row"])
        h = result["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["resolution"], settled["huddles"][0]["resolution"])
        self.assertEqual(h["holds"], [board_api._claim_ref(self.b)])

    def test_stale_remote_ambiguity_leaves_board_and_journal_unchanged(self):
        self.submit(role="yield", reason="owner_authorized_handoff",
                    target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        with board_api._transaction(self.home) as (root, path, payload):
            h = payload["huddles"][0]
            source = board_api._claim_ref(self.a)
            successor = {**source, "owner": "B"}
            h.update(state="remote_pending", reply_by=None,
                     holds=[source, successor, board_api._claim_ref(self.b)],
                     remote_transition=dict(
                         source_claim=source, successor_claim=successor,
                         target_prior_claim=board_api._claim_ref(self.b),
                         target_prior_action="return_required",
                         remote_ref=board_api._remote_claim.claim_ref(source["entity"], source["row"]),
                         expected_remote_version="e" * 40, readback="not_attempted",
                         attempt_receipt=None))
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: remote ambiguity", now=NOW)
        self.complete_plan("A")
        self.age_claim(self.a)
        before = self.authority()

        self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 0)
        self.assertEqual(self.authority(), before)

    def test_held_public_accept_refuses_before_proof_or_plan_write(self):
        source = self.home / "source"
        source.mkdir()
        marker = self.home / "proof-was-launched"
        (source / "proof.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        git(source, "init", "-q")
        git(source, "config", "user.email", "test@example.invalid")
        git(source, "config", "user.name", "Test")
        git(source, "remote", "add", "origin", "https://github.com/example/huddle-fixture.git")
        git(source, "add", "proof.py")
        git(source, "commit", "-qm", "fixture")
        plan = self.plans["B"]
        plan.write_text(plan.read_text().replace("- Mode: ship", "- Mode: ship\n- Origin: github.com/example/huddle-fixture")
                        .replace("proof: cmd true", "proof: cmd python3 proof.py"))
        plan_before = plan.read_bytes()
        before = self.authority()
        result = subprocess.run([str(ROOT / "bin" / "shadow"), "accept", "--repo", str(source),
            "--entity", self.b["entity"], "--row", self.b["row"], "--by", "B"],
            text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Huddle held", result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(plan.read_bytes(), plan_before)
        self.assertEqual(self.authority(), before)

    def test_cosmetic_plan_change_cannot_satisfy_required_return(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        self.settle()
        plan = self.plans["B"]
        plan.write_text(plan.read_text() + "\n- 2026-09-04T16:00:00Z NOTE formatting only\n")
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "canonical"):
            self.release(self.b)
        self.assertEqual(self.authority(), before)

    def test_new_canonical_contradiction_allows_pending_required_handback(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        self.settle()
        plan = self.plans["B"]
        plan.write_text(plan.read_text() + "\n## Contradictions\n- ~aa11 duplicates A's current shared change; return until A completes.\n")
        result, _ = self.release(self.b)
        self.assertEqual(result["huddles"][0]["state"], "resolved")

    def test_commit_race_restores_board_and_claim_revision_cas_rejects_replacement(self):
        before = self.authority()
        plan = self.plans["A"]
        original_write = board_api._write_and_commit
        def race(*args, **kwargs):
            plan.write_text(plan.read_text() + "\n- concurrent canonical edit\n")
            return original_write(*args, **kwargs)
        with mock.patch.object(board_api, "_write_and_commit", side_effect=race):
            with self.assertRaisesRegex(board_api.BoardError, "canonical plan changed"):
                self.release(self.a)
        self.assertEqual(self.authority(), before)
        with self.assertRaisesRegex(board_api.BoardError, "claim changed"):
            board_api.release(plan, self.a["row"], owner="A", reason="handback",
                expected_claim={**self.a, "claim_revision": 0}, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)


class HuddleMigrationTests(HuddleTestCase):
    def test_v1_migration_is_lossless_and_does_not_mutate_input(self) -> None:
        payload = self.v1_board()
        original = copy.deepcopy(payload)

        migrated = board_api.migrate_v1_to_v2(payload)

        self.assertEqual(payload, original)
        self.assertIsNot(migrated, payload)
        self.assertEqual(migrated["schema"], board_api.V2_SCHEMA)
        self.assertEqual(migrated["revision"], payload["revision"])
        self.assertEqual(migrated["projects"], payload["projects"])
        self.assertEqual(migrated["entities"], payload["entities"])
        self.assertEqual(migrated["huddles"], [])
        claim = migrated["claims"][0]
        for key, value in payload["claims"][0].items():
            self.assertEqual(claim[key], value)
        self.assertEqual(claim["claim_revision"], 0)
        self.assertEqual(claim["access"], "unscoped")
        self.assertIsNone(claim["repository_binding"])
        self.assertEqual(claim["write_scope"], [])

    def test_migration_refuses_every_malformed_v1_before_copying(self) -> None:
        cases: list[dict] = []
        unknown = self.v1_board()
        unknown["unknown"] = True
        cases.append(unknown)
        wrong_schema = self.v1_board()
        wrong_schema["schema"] = "shadow.root-board.v0"
        cases.append(wrong_schema)
        bad_owner = self.v1_board()
        bad_owner["claims"][0]["owner"] = ""
        cases.append(bad_owner)
        bad_time = self.v1_board()
        bad_time["claims"][0]["claimed_at"] = "not-a-time"
        cases.append(bad_time)
        duplicate = self.v1_board()
        duplicate["claims"].append(copy.deepcopy(duplicate["claims"][0]))
        cases.append(duplicate)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(board_api.BoardError):
                    board_api.migrate_v1_to_v2(payload)

    def test_v2_validation_refuses_malformed_claim_contracts(self) -> None:
        valid = self.v2_board()
        valid["claims"][0].update({
            "claim_revision": 1,
            "access": "write",
            "repository_binding": {
                "common_dir_sha256": "c" * 64,
                "remote_identity": "github.com/firstbitelabsllc/shadow",
            },
            "write_scope": ["scripts", "tests/test_huddle.py"],
        })
        cases: list[dict] = []

        def changed(mutator) -> None:
            payload = copy.deepcopy(valid)
            mutator(payload["claims"][0])
            cases.append(payload)

        changed(lambda claim: claim.update({"extra": True}))
        changed(lambda claim: claim.update({"claim_revision": True}))
        changed(lambda claim: claim.update({"claim_revision": 8}))
        changed(lambda claim: claim.update({"access": "admin"}))
        changed(lambda claim: claim.update({"access": []}))
        changed(lambda claim: claim.update({"repository_binding": None}))
        changed(lambda claim: claim.update({"write_scope": []}))
        changed(lambda claim: claim.update({"write_scope": ["tests", "scripts"]}))
        changed(lambda claim: claim.update({"write_scope": ["scripts", "scripts"]}))
        for scope in (
            ["/absolute"], ["../parent"], ["a//b"], ["a\\b"], ["*.py"],
            ["a/.git/config"], ["a/./b"], ["control\npath"],
            ["x" * 1025], [None], [[]], [1, "scripts"], ["\ud800"],
        ):
            changed(lambda claim, scope=scope: claim.update({"write_scope": scope}))
        changed(lambda claim: claim["repository_binding"].update({"extra": True}))
        changed(lambda claim: claim["repository_binding"].update({"common_dir_sha256": "C" * 64}))
        changed(lambda claim: claim["repository_binding"].update({"remote_identity": "https://github.com/firstbitelabsllc/shadow?token=secret"}))

        read_only = copy.deepcopy(valid)
        read_only["claims"][0].update({
            "access": "read_only",
            "repository_binding": None,
            "write_scope": ["scripts"],
        })
        cases.append(read_only)
        legacy = copy.deepcopy(valid)
        legacy["claims"][0].update({
            "claim_revision": 1,
            "access": "unscoped",
            "repository_binding": None,
            "write_scope": [],
        })
        cases.append(legacy)

        for payload in cases:
            with self.subTest(claim=payload["claims"][0]):
                with self.assertRaises(board_api.BoardError):
                    board_api._validate(payload)

    def test_v2_validation_accepts_closed_access_shapes_and_root_scope(self) -> None:
        unscoped = self.v2_board()
        unscoped["claims"][0].update({
            "claim_revision": 1,
            "repository_binding": {
                "common_dir_sha256": "c" * 64,
                "remote_identity": None,
            },
        })
        read_only = copy.deepcopy(unscoped)
        read_only["claims"][0].update({
            "access": "read_only",
            "repository_binding": None,
        })
        write = copy.deepcopy(unscoped)
        write["claims"][0].update({"access": "write", "write_scope": ["."]})

        classified_legacy = copy.deepcopy(write)
        classified_legacy["claims"][0]["claim_revision"] = 0
        for payload in (unscoped, read_only, write, classified_legacy):
            self.assertIs(board_api._validate(payload), payload)

    def test_read_paths_validate_without_migrating_board_bytes(self) -> None:
        root, path = self.seed_v2()
        before = self.authority()

        self.assertEqual(board_api._read(path)["schema"], board_api.V2_SCHEMA)
        self.assertEqual(board_api.snapshot(home=self.home)["schema"], board_api.V2_SCHEMA)

        self.assertEqual(self.authority(), before)
        self.assertEqual(board_api._journal_head(root), before[1])

    def test_decode_refuses_duplicate_json_keys_at_any_depth(self) -> None:
        board_api.ensure(home=self.home)
        path = self.home / ".shadow" / board_api.BOARD_NAME
        duplicate = (
            '{"schema":"shadow.root-board.v2","revision":0,'
            '"projects":[{"id":"shadow","id":"other","priority":1}],'
            '"entities":[],"claims":[],"huddles":[]}'
        )
        path.write_text(duplicate, encoding="utf-8")

        with self.assertRaises(board_api.BoardError):
            board_api._decode(path)

    def test_successful_rollback_increments_once_and_raw_reread_is_v1(self) -> None:
        _, path = self.seed_v2()
        before = board_api._read(path)

        rolled_back = board_api._rollback_v2_to_v1(
            self.home,
            expected_revision=before["revision"],
            remote_parity=lambda candidate: candidate["schema"] == board_api.SCHEMA,
        )

        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw, rolled_back)
        self.assertEqual(raw["schema"], board_api.SCHEMA)
        self.assertEqual(raw["revision"], before["revision"] + 1)
        self.assertNotIn("huddles", raw)
        self.assertEqual(board_api._validate(raw), raw)

    def test_rollback_refusals_preserve_clean_board_and_journal(self) -> None:
        refusal_cases = ("schema", "revision", "claims", "parity", "truthy")
        for refusal in refusal_cases:
            with self.subTest(refusal=refusal), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                self.home = home
                payload = self.v2_board(with_claim=refusal == "claims")
                if refusal != "claims":
                    payload["claims"] = []
                if refusal == "schema":
                    board_api.ensure(home=home)
                else:
                    self.seed_v2(payload)
                before = self.authority()
                current = json.loads(before[0])
                expected = current["revision"] + (1 if refusal == "revision" else 0)
                parity = (
                    (lambda _: False) if refusal == "parity"
                    else (lambda _: 1) if refusal == "truthy"
                    else (lambda _: True)
                )

                with self.assertRaises(board_api.BoardError):
                    board_api._rollback_v2_to_v1(
                        home, expected_revision=expected, remote_parity=parity
                    )

                self.assertEqual(self.authority(), before)

    def test_rollback_refuses_nonempty_huddles_without_changing_authority(self) -> None:
        root, path = self.seed_v2()
        payload = board_api._read(path)
        payload["huddles"] = [{"unsupported": True}]
        board_api._write(path, payload)
        board_api._commit(root, "test: seed unsupported huddle")
        before = self.authority()

        with self.assertRaises(board_api.BoardError):
            board_api._rollback_v2_to_v1(
                self.home,
                expected_revision=payload["revision"],
                remote_parity=lambda _: True,
            )

        self.assertEqual(self.authority(), before)

    def test_rollback_faults_restore_board_and_journal_without_success(self) -> None:
        for fault in ("before-replace", "after-commit"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.home = Path(tmp)
                root, path = self.seed_v2()
                payload = board_api._read(path)
                before = self.authority()
                if fault == "before-replace":
                    patcher = mock.patch.object(
                        board_api, "_replace", side_effect=OSError("injected replace failure")
                    )
                else:
                    original_commit = board_api._commit

                    def fail_after_commit(board_root: Path, message: str) -> None:
                        original_commit(board_root, message)
                        if message == "shadow board: roll back v2 to v1":
                            raise board_api.BoardError("injected commit failure")

                    patcher = mock.patch.object(board_api, "_commit", side_effect=fail_after_commit)

                with patcher, self.assertRaises((OSError, board_api.BoardError)):
                    board_api._rollback_v2_to_v1(
                        self.home,
                        expected_revision=payload["revision"],
                        remote_parity=lambda _: True,
                    )

                self.assertEqual(self.authority(), before)
                self.assertEqual(git(root, "status", "--porcelain", "--", board_api.BOARD_NAME), "")


class HuddleAccessTests(HuddleTestCase):
    def repo(self, name="repo"):
        repo = self.home / name
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.test",
            "commit", "--allow-empty", "-m", "fixture")
        return repo

    def test_binding_matches_worktrees_and_separate_clones_without_paths(self):
        repo = self.repo()
        first = board_api.repository_binding(repo)
        self.assertIsNone(first["remote_identity"])
        self.assertNotIn(str(repo), json.dumps(first))
        linked = self.home / "linked"
        git(repo, "worktree", "add", "--detach", str(linked))
        self.assertEqual(board_api.repository_binding(linked), first)
        git(repo, "remote", "add", "origin", "https://GitHub.com/Example/Repo.git")
        other = self.repo("other")
        git(other, "remote", "add", "origin", "git@github.com:Example/Repo.git")
        left, right = board_api.repository_binding(repo), board_api.repository_binding(other)
        self.assertEqual(left["remote_identity"], "github.com/Example/Repo")
        self.assertEqual(left["remote_identity"], right["remote_identity"])
        self.assertNotEqual(left["common_dir_sha256"], right["common_dir_sha256"])

    def test_binding_refuses_ambiguous_and_secret_urls(self):
        repo = self.repo()
        for url in ("https://github.com/org/repo?token=secret", "https://user:pass@github.com/org/repo",
                    "https://github.com/org/repo#fragment", "/private/repository"):
            git(repo, "config", "remote.origin.url", url)
            with self.subTest(url=url), self.assertRaises(board_api.BoardError):
                board_api.repository_binding(repo)
        git(repo, "config", "remote.origin.url", "https://github.com/org/repo")
        git(repo, "config", "--add", "remote.origin.url", "https://github.com/other/repo")
        with self.assertRaises(board_api.BoardError):
            board_api.repository_binding(repo)

    def test_scope_is_lexical_and_never_follows_parent_links(self):
        repo = self.repo()
        outside = self.home / "outside"
        outside.mkdir()
        (repo / "link").symlink_to(outside, target_is_directory=True)
        self.assertEqual(board_api.normalize_write_scope(repo, ["link", "new", "new"]), ["link", "new"])
        for scope in (["link/file"], ["../outside"], ["a//b"], [".git"], ["/absolute"], ["a\\b"]):
            with self.subTest(scope=scope), self.assertRaises(board_api.BoardError):
                board_api.normalize_write_scope(repo, scope)
        self.assertEqual(board_api.normalize_write_scope(repo, ["a" * 600, "b" * 600]), ["a" * 600, "b" * 600])
        with self.assertRaises(board_api.BoardError):
            board_api.normalize_write_scope(repo, ["x" * 1025])

    def seed_source(self, repo, *, scope=None):
        value = self.v2_board()
        value["claims"][0].update(claim_revision=1, access="write",
            repository_binding=board_api.repository_binding(repo), write_scope=scope or ["src"])
        self.seed_v2(value)
        return value["claims"][0]

    def preflight(self, repo, *, access="write", scope=None):
        value = board_api.snapshot(home=self.home)
        claim = value["claims"][0]
        return board_api.preflight_access(entity=claim["entity"], row=claim["row"], owner=claim["owner"],
            repo=repo, access=access, write_scope=(scope or ["src"]) if access == "write" else [],
            expected_claim_revision=claim["claim_revision"], expected_board_revision=value["revision"],
            now=NOW, home=self.home)

    def test_bound_claim_can_become_read_only_without_changing_instance(self):
        repo = self.repo()
        before = self.seed_source(repo)
        result = self.preflight(repo, access="read_only")
        claim = result.payload["claims"][0]
        self.assertEqual(claim["access"], "read_only")
        self.assertEqual(claim["write_scope"], [])
        self.assertIsNone(claim["repository_binding"])
        self.assertEqual(claim["claim_revision"], before["claim_revision"])

    def test_equivalent_checkout_preserves_binding_but_different_repository_refuses(self):
        repo = self.repo()
        other = self.repo("other")
        for path in (repo, other):
            git(path, "remote", "add", "origin", "https://github.com/org/repo.git")
        original = self.seed_source(repo)["repository_binding"]
        result = self.preflight(other, scope=["src", "tests"])
        self.assertEqual(result.payload["claims"][0]["repository_binding"], original)
        git(other, "remote", "set-url", "origin", "https://github.com/org/other.git")
        before = self.authority()
        with self.assertRaises(board_api.BoardError):
            self.preflight(other, scope=["src"])
        self.assertEqual(self.authority(), before)

    def test_parent_replacement_during_publication_restores_authority(self):
        repo = self.repo()
        parent = repo / "src"
        parent.mkdir()
        self.seed_source(repo, scope=["src/old.py"])
        before = self.authority()
        original = board_api._write_and_commit
        def replace_parent(*args, **kwargs):
            parent.rename(repo / "previous-src")
            parent.mkdir()
            return original(*args, **kwargs)
        with mock.patch.object(board_api, "_write_and_commit", side_effect=replace_parent):
            with self.assertRaisesRegex(board_api.BoardError, "component"):
                self.preflight(repo, scope=["src/new.py"])
        self.assertEqual(self.authority(), before)

    def test_local_binding_cannot_silently_gain_a_remote(self):
        repo = self.repo()
        self.seed_source(repo)
        git(repo, "remote", "add", "origin", "https://github.com/org/repo.git")
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "contradict"):
            self.preflight(repo, scope=["src", "tests"])
        self.assertEqual(self.authority(), before)

    def test_v1_projection_is_independent_of_eventual_default_schema(self):
        legacy = self.v1_board(with_claim=False)
        migrated = board_api.migrate_v1_to_v2(legacy)
        self.seed_v2(migrated)
        with mock.patch.object(board_api, "SCHEMA", board_api.V2_SCHEMA):
            self.assertEqual(board_api._validate(legacy), legacy)
            self.assertEqual(board_api.migrate_v1_to_v2(legacy), migrated)
            result = board_api._rollback_v2_to_v1(self.home, migrated["revision"], remote_parity=lambda _: True)
            self.assertEqual(result["schema"], board_api.V1_SCHEMA)


class HuddleGraphTests(HuddleTestCase):
    def seed(self, scopes):
        payload = self.v2_board(with_claim=False)
        payload["entities"] = []
        payload["revision"] = len(scopes) + 1
        for index, scope in enumerate(scopes, 1):
            entity = f"{index:064x}"
            payload["entities"].append({"id": entity, "project": "shadow",
                "plan": str(self.home / str(index) / "PLAN.md"), "resume": "~aa11"})
            claim = self.v1_board()["claims"][0]
            claim.update(entity=entity, owner=chr(64 + index), claim_revision=index,
                         access="write", repository_binding={"common_dir_sha256": "c" * 64,
                         "remote_identity": None}, write_scope=scope)
            payload["claims"].append(claim)
        self.seed_v2(payload)
        return payload["claims"]

    def open(self, claim, peers):
        return board_api.open_or_join_huddle(claim=claim, overlap=peers,
            reason="write_scope_overlap", now=NOW, home=self.home)

    def test_direct_edges_hold_b_without_serializing_a_and_c(self):
        a, b, c = self.seed([["a"], ["a", "b"], ["b"]])
        result = self.open(b, [a])
        huddle = result.payload["huddles"][0]
        self.assertEqual([ref["owner"] for ref in huddle["holds"]], ["B"])
        self.assertEqual(len(huddle["edges"]), 2)
        self.assertEqual([ref["owner"] for ref in huddle["claims"]], ["A", "B", "C"])
        before = self.authority()
        replay = self.open(c, [b])
        self.assertFalse(replay.changed)
        self.assertIsNone(replay.event)
        self.assertEqual(self.authority(), before)
        self.assertEqual(board_api.huddle_show(huddle["id"], home=self.home), huddle)
        self.assertEqual(self.authority(), before)

    def test_bridge_refuses_without_changing_board_or_journal(self):
        a, b, c, d, bridge = self.seed([["a"], ["a"], ["b"], ["b"], ["c"]])
        self.open(a, [b])
        self.open(c, [d])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "bridge"):
            board_api.open_or_join_huddle(claim=bridge, overlap=[a, c],
                reason="semantic_suspicion", now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_stale_claim_and_malformed_graph_refuse(self):
        a, b = self.seed([["a"], ["a"]])
        before = self.authority()
        stale = dict(a, claim_revision=0)
        with self.assertRaises(board_api.BoardError):
            self.open(stale, [b])
        self.assertEqual(self.authority(), before)
        result = self.open(a, [b])
        for change in (lambda h: h.update(extra=True), lambda h: h.update(holds=[]),
                       lambda h: h["edges"][0].update(kinds=["unknown"]),
                       lambda h: h["claims"][0].update(claim_revision=True),
                       lambda h: h["edges"][0]["left"].update(claim_revision=True),
                       lambda h: h["holds"][0].update(claim_revision=True),
                       lambda h: h["claims"].append(h["claims"][0])):
            value = copy.deepcopy(result.payload)
            change(value["huddles"][0])
            with self.assertRaises(board_api.BoardError):
                board_api._validate(value)

    def test_missing_real_edge_cannot_authorize_overlapping_writers(self):
        a, b, c = self.seed([["a"], ["a", "b"], ["b"]])
        value = self.open(b, [a]).payload
        huddle = value["huddles"][0]
        huddle["edges"].pop()
        huddle["holds"] = board_api.claim_holds(huddle)
        with self.assertRaises(board_api.BoardError):
            board_api._validate(value)

    def test_legacy_unknown_blocks_write_and_preflight_opens_real_overlap(self):
        a, b = self.seed([["a"], ["a"]])
        repo = self.home / "source"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        binding = board_api.repository_binding(repo)
        with board_api._transaction(self.home) as (root, path, payload):
            for claim in payload["claims"]:
                claim.update(claim_revision=0, access="unscoped", repository_binding=None, write_scope=[])
            board_api._write_and_commit(root, path, payload, "test: legacy claims")
        def preflight(claim, access):
            current = board_api.snapshot(home=self.home)
            return board_api.preflight_access(entity=claim["entity"], row=claim["row"], owner=claim["owner"],
                repo=repo, access=access, write_scope=["a"] if access == "write" else [],
                expected_claim_revision=0, expected_board_revision=current["revision"], now=NOW, home=self.home)
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "legacy_binding_unknown"):
            preflight(a, "write")
        self.assertEqual(self.authority(), before)
        preflight(b, "read_only")
        first = preflight(a, "write")
        self.assertEqual(first.payload["claims"][0]["claim_revision"], 0)
        second = preflight(b, "write")
        self.assertEqual([ref["owner"] for ref in second.payload["huddles"][0]["holds"]], ["B"])

    def test_contradictory_binding_refuses_without_authority_change(self):
        a, b = self.seed([["a"], ["a"]])
        with board_api._transaction(self.home) as (root, path, payload):
            payload["claims"][0]["repository_binding"]["remote_identity"] = "github.com/org/one"
            payload["claims"][1]["repository_binding"]["remote_identity"] = "github.com/org/two"
            board_api._write_and_commit(root, path, payload, "test: conflicting identities")
            a, b = copy.deepcopy(payload["claims"])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "contradict"):
            self.open(a, [b])
        self.assertEqual(self.authority(), before)


class HuddleScopeTransitionTests(HuddleTestCase):
    def seed(self, scopes, *, unscoped=()):
        repo = self.home / "source"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        HuddleGraphTests.seed(self, [scope or ["fixture"] for scope in scopes])
        binding = board_api.repository_binding(repo)
        with board_api._transaction(self.home) as (root, path, payload):
            for index, claim in enumerate(payload["claims"]):
                claim["repository_binding"] = binding
                if index in unscoped:
                    claim.update(access="unscoped", write_scope=[])
            board_api._write_and_commit(root, path, payload, "test: source bindings")
            claims = copy.deepcopy(payload["claims"])
        return repo, claims

    def preflight(self, repo, claim, scope, *, access="write", now=NOW, revision=None):
        current = board_api.snapshot(home=self.home)
        return board_api.preflight_access(entity=claim["entity"], row=claim["row"], owner=claim["owner"],
            repo=repo, access=access, write_scope=scope, expected_claim_revision=claim["claim_revision"],
            expected_board_revision=current["revision"] if revision is None else revision, now=now, home=self.home)

    def open(self, claim, peers, *, reason="write_scope_overlap"):
        return board_api.open_or_join_huddle(claim=claim, overlap=peers,
            reason=reason, now=NOW, home=self.home).payload["huddles"][0]

    def test_classification_resolves_disjoint_scope_without_a_bid_round(self):
        repo, (a, b) = self.seed([[], ["a"]], unscoped=(0,))
        opened = self.open(b, [a], reason="scope_request")
        result = self.preflight(repo, a, ["b"], now=NOW + timedelta(seconds=10))
        h = result.payload["huddles"][0]
        self.assertEqual(h["id"], opened["id"])
        self.assertEqual(h["generation"], opened["generation"] + 1)
        self.assertEqual(h["state"], "resolved")
        self.assertEqual(h["edges"], [])
        self.assertEqual(h["holds"], [])
        self.assertIsNone(h["reply_by"])
        self.assertEqual(h["resolution"]["rule"], "path_disjoint")
        self.assertEqual([r["owner"] for r in h["resolution"]["write_owners"]], ["A", "B"])
        self.assertEqual([r["action"] for r in h["resolution"]["actions"]], ["continue_disjoint"] * 2)
        self.assertEqual(result.payload["claims"][0]["claim_revision"], a["claim_revision"])

    def test_classification_keeps_overlap_and_starts_fresh_round_one(self):
        repo, (a, b) = self.seed([[], ["a"]], unscoped=(0,))
        opened = self.open(b, [a], reason="scope_request")
        result = self.preflight(repo, a, ["a"], now=NOW + timedelta(seconds=10))
        h = result.payload["huddles"][0]
        self.assertEqual((h["state"], h["round"], h["generation"]), ("open_round_1", 1, 2))
        self.assertEqual(h["reply_by"], "2026-09-04T16:02:10Z")
        self.assertEqual([r["owner"] for r in h["holds"]], ["B"])
        self.assertEqual(h["opened_revision"], opened["opened_revision"])

    def test_shrink_keeps_disconnected_disjoint_claim_and_semantic_edges(self):
        repo, (a, b, c) = self.seed([["a"], ["a", "b"], ["b"]])
        self.open(b, [a])
        result = self.preflight(repo, b, ["a"])
        h = result.payload["huddles"][0]
        self.assertEqual([r["owner"] for r in h["claims"]], ["A", "B", "C"])
        self.assertEqual([r["owner"] for r in h["holds"]], ["B"])
        self.assertEqual(len(h["edges"]), 1)
        self.assertEqual(h["generation"], 2)
        self.assertEqual(board_api._validate(result.payload), result.payload)

    def test_semantic_edge_survives_held_scope_shrink(self):
        repo, (a, b) = self.seed([["a"], ["a", "b"]])
        self.open(a, [b], reason="semantic_suspicion")
        result = self.preflight(repo, b, ["b"])
        h = result.payload["huddles"][0]
        self.assertEqual(h["edges"][0]["kinds"], ["semantic_suspicion"])
        self.assertEqual([r["owner"] for r in h["holds"]], ["B"])

    def test_new_overlap_joins_and_scope_bridge_refuses_atomically(self):
        repo, (a, b, c, d, newcomer) = self.seed([["a"], ["a"], ["b"], ["b"], ["c"]])
        self.open(a, [b])
        self.open(c, [d])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "bridge"):
            self.preflight(repo, newcomer, ["a", "b"])
        self.assertEqual(self.authority(), before)
        result = self.preflight(repo, newcomer, ["a"])
        h = result.payload["huddles"][0]
        self.assertEqual(h["generation"], 2)
        self.assertEqual([r["owner"] for r in h["claims"]], ["A", "B", "E"])

    def test_held_expansion_read_only_and_late_classification_refuse(self):
        repo, (a, b) = self.seed([["a"], ["a"]])
        self.open(a, [b])
        before = self.authority()
        for scope, access in ((["a", "b"], "write"), ([], "read_only")):
            with self.subTest(access=access), self.assertRaises(board_api.BoardError):
                self.preflight(repo, b, scope, access=access)
            self.assertEqual(self.authority(), before)
        self.assertFalse(self.preflight(repo, a, ["a"], now=NOW + timedelta(minutes=2)).changed)
        with self.assertRaises(board_api.BoardError):
            self.preflight(repo, a, ["a", "b"], now=NOW + timedelta(minutes=2))
        self.assertEqual(self.authority(), before)

    def test_stale_board_preflight_never_changes_scope_or_generation(self):
        repo, (a, b) = self.seed([["a"], ["a"]])
        previous_revision = board_api.snapshot(home=self.home)["revision"]
        self.open(a, [b])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "board revision"):
            self.preflight(repo, a, ["b"], revision=previous_revision)
        self.assertEqual(self.authority(), before)

    def test_join_cannot_smuggle_a_new_disjoint_participant(self):
        repo, (a, b, c) = self.seed([["a"], ["a"], ["c"]])
        self.open(a, [b])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "direct conflict"):
            self.open(a, [b, c])
        self.assertEqual(self.authority(), before)

    def test_open_and_join_cannot_smuggle_a_disconnected_conflicting_pair(self):
        repo, (a, b, c, d) = self.seed([["a"], ["a"], ["b"], ["b"]])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "connect"):
            self.open(a, [b, c, d])
        self.assertEqual(self.authority(), before)
        self.open(a, [b])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "connect"):
            self.open(a, [b, c, d])
        self.assertEqual(self.authority(), before)

    def test_read_only_classification_resolves_and_retains_historical_refs(self):
        repo, (a, b) = self.seed([[], ["a"]], unscoped=(0,))
        self.open(b, [a], reason="scope_request")
        result = self.preflight(repo, a, [], access="read_only")
        h = result.payload["huddles"][0]
        self.assertEqual(h["state"], "resolved")
        self.assertEqual([r["owner"] for r in h["claims"]], ["B"])
        self.assertEqual(h["resolution"]["write_owners"], h["claims"])
        self.assertEqual(h["retain_until"], "2026-09-05T16:00:00Z")
        historical = copy.deepcopy(result.payload)
        historical["claims"] = []
        board_api._validate(historical)
        for field in ("settled_revision", "actions", "write_owners"):
            malformed = copy.deepcopy(historical)
            resolution = malformed["huddles"][0]["resolution"]
            if field == "settled_revision":
                resolution[field] = True
            elif field == "actions":
                resolution[field][0]["claim"]["claim_revision"] = True
            else:
                resolution[field][0]["claim_revision"] = True
            with self.subTest(field=field), self.assertRaises(board_api.BoardError):
                board_api._validate(malformed)

    def test_read_only_classification_cannot_erase_semantic_suspicion(self):
        repo, (a, b) = self.seed([[], ["a"]], unscoped=(0,))
        self.open(b, [a], reason="semantic_suspicion")
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "semantic"):
            self.preflight(repo, a, [], access="read_only")
        self.assertEqual(self.authority(), before)


class HuddleClaimCreationTests(HuddleTestCase):
    def seed(self):
        repo = HuddleAccessTests.repo(self)
        plan = repo / "PLAN.md"
        plan.write_text("## Brief\n- Project: shadow\n- Mode: ship\n\n## Tasks\n"
                        "### Work\n- [pending] first ~aa11 | proof: read result -> valid\n"
                        "- [pending] second ~bb22 (DoD) | proof: read result -> valid\n"
                        "\n## Progress\n", encoding="utf-8")
        git(repo, "add", "PLAN.md")
        git(repo, "commit", "-qm", "seed plan")
        self.seed_v2()
        return repo, plan

    def take(self, repo, plan, row, owner, *, access="write", scope=None, **kwargs):
        return board_api.claim(plan, row, owner, project="shadow", priority=3,
            repo=repo, access=access, write_scope=["a"] if scope is None else scope,
            now=NOW, home=self.home, **kwargs)

    def test_real_claim_creation_assigns_revision_and_opens_overlap_atomically(self):
        repo, plan = self.seed()
        first = self.take(repo, plan, "~aa11", "A")
        second = self.take(repo, plan, "~bb22", "B")
        payload = board_api.snapshot(home=self.home)
        self.assertEqual(first["claim"]["claim_revision"], first["payload"]["revision"])
        self.assertEqual(second["claim"]["claim_revision"], payload["revision"])
        self.assertGreater(second["claim"]["claim_revision"], first["claim"]["claim_revision"])
        self.assertEqual(first["claim"]["repository_binding"], board_api.repository_binding(repo))
        h = payload["huddles"][0]
        self.assertEqual(h["state"], "open_round_1")
        self.assertEqual(h["holds"], [board_api._claim_ref(second["claim"])])
        self.assertEqual(h["claims"], [board_api._claim_ref(first["claim"]), board_api._claim_ref(second["claim"])])
        before = self.authority()
        with mock.patch.object(board_api, "repository_binding", side_effect=AssertionError("duplicate must win first")):
            with self.assertRaises(board_api.AlreadyClaimed):
                self.take(repo, plan, "~aa11", "C")
        self.assertEqual(self.authority(), before)

    def test_known_unscoped_claim_opens_scope_request_but_read_only_does_not(self):
        for access in ("unscoped", "read_only"):
            with self.subTest(access=access), tempfile.TemporaryDirectory() as tmp:
                self.home = Path(tmp)
                repo, plan = self.seed()
                first = self.take(repo, plan, "~aa11", "A", access=access, scope=[])
                second = self.take(repo, plan, "~bb22", "B")
                huddles = second["payload"]["huddles"]
                if access == "read_only":
                    self.assertIsNone(first["claim"]["repository_binding"])
                    self.assertEqual(huddles, [])
                else:
                    self.assertEqual(first["claim"]["repository_binding"], board_api.repository_binding(repo))
                    self.assertEqual(huddles[0]["state"], "awaiting_scope")
                    self.assertEqual(huddles[0]["holds"], [board_api._claim_ref(second["claim"])])

    def test_claim_publication_failure_rolls_back_both_claim_and_huddle(self):
        repo, plan = self.seed()
        self.take(repo, plan, "~aa11", "A")
        before = self.authority()
        with mock.patch.object(board_api, "_commit", side_effect=board_api.BoardError("injected journal failure")):
            with self.assertRaisesRegex(board_api.BoardError, "injected"):
                self.take(repo, plan, "~bb22", "B")
        self.assertEqual(self.authority(), before)

    def test_staged_reconcile_imports_historical_claim_as_unknown_revision_zero(self):
        repo, plan = self.seed()
        payload = board_api.reconcile([{"plan": str(plan), "project": "shadow", "priority": 3,
            "candidates": ["~aa11", "~bb22"]}], [{"plan": str(plan), "row": "~aa11",
            "owner": "Legacy", "claimed_at": "2026-09-04T15:00:00Z"}], home=self.home)
        claim = payload["claims"][0]
        self.assertEqual(claim["claim_revision"], 0)
        self.assertEqual(claim["access"], "unscoped")
        self.assertIsNone(claim["repository_binding"])
        self.assertEqual(claim["write_scope"], [])
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "legacy_binding_unknown"):
            self.take(repo, plan, "~bb22", "B")
        self.assertEqual(self.authority(), before)


class HuddleAdoptionTests(HuddleTestCase):
    take = HuddleClaimCreationTests.take
    request = HuddleBidTests.request
    submit = HuddleBidTests.submit
    settle = HuddleSettlementTests.settle

    def setUp(self):
        super().setUp()
        self.repo, self.plan = HuddleClaimCreationTests.seed(self)
        self.a = self.take(self.repo, self.plan, "~aa11", "A")["claim"]
        self.b = self.take(self.repo, self.plan, "~bb22", "B")["claim"]
        self.huddle = board_api.snapshot(home=self.home)["huddles"][0]

    def adopt(self, claim=None, *, now=NOW + timedelta(hours=9), owner="Successor", **changes):
        claim = claim or self.a
        args = dict(project="shadow", priority=3, repo=self.repo,
                    now=now, home=self.home, adopt_expired=True)
        return board_api.claim(self.plan, claim["row"], owner, **(args | changes))

    def test_open_adoption_installs_new_rank_and_preserves_unaffected_bid(self):
        self.submit()
        peer_bid = self.submit(self.b).payload["huddles"][0]["bids"][-1]
        before = board_api.snapshot(home=self.home)
        result = self.adopt()
        replacement, h = result["claim"], result["payload"]["huddles"][0]
        ref = board_api._claim_ref(replacement)
        self.assertEqual(replacement["claim_revision"], before["revision"] + 1)
        for field in ("access", "repository_binding", "write_scope"):
            self.assertEqual(replacement[field], self.a[field])
        self.assertEqual(h["claims"], [board_api._claim_ref(self.b), ref])
        self.assertEqual(h["holds"], [ref])
        self.assertEqual(h["edges"], [dict(left=board_api._claim_ref(self.b), right=ref, kinds=["path_overlap"])])
        self.assertEqual(h["bids"], [peer_bid])
        self.assertEqual((h["state"], h["round"], h["generation"]), ("open_round_1", 1, 2))
        self.assertEqual(h["reply_by"], "2026-09-05T01:02:00Z")
        self.assertEqual(result["event"]["generation"], h["generation"])
        frozen = self.authority()
        with self.assertRaises(board_api.BoardError):
            self.submit()
        self.assertEqual(self.authority(), frozen)

    def test_round_two_adoption_keeps_round_and_other_original_receipts(self):
        self.submit()
        self.submit(self.b)
        second = self.settle().payload["huddles"][0]
        self.huddle = second
        self.submit(round=2)
        self.submit(self.b, round=2)
        before = board_api.snapshot(home=self.home)["huddles"][0]
        h = self.adopt()["payload"]["huddles"][0]
        self.assertEqual((h["state"], h["round"]), ("open_round_2", 2))
        self.assertEqual(h["generation"], before["generation"] + 1)
        self.assertEqual(h["bids"], [b for b in before["bids"] if b["claim"] == board_api._claim_ref(self.b)])

    def test_adoption_invalidates_yield_target_without_forging_its_digest(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        h = self.adopt(self.b)["payload"]["huddles"][0]
        self.assertEqual(h["bids"], [])
        self.assertEqual(h["holds"], [h["claims"][-1]])

    def test_unaffected_stand_down_remains_exact_after_peer_becomes_selected(self):
        self.submit(self.b, role="stand_down")
        before = board_api.snapshot(home=self.home)["huddles"][0]["bids"]
        after = self.adopt()["payload"]["huddles"][0]
        self.assertEqual(after["bids"], before)
        self.assertNotIn(board_api._claim_ref(self.b), after["holds"])

    def test_adoption_rechecks_canonical_bytes_and_repository_before_commit(self):
        for race in ("plan", "repo"):
            with self.subTest(race=race):
                before = self.authority()
                original = board_api._write_and_commit
                plan_bytes = self.plan.read_bytes()
                def change(*args, **kwargs):
                    if race == "plan":
                        self.plan.write_bytes(plan_bytes + b"\nConcurrent change\n")
                    else:
                        git(self.repo, "remote", "add", "origin", "https://github.com/other/source.git")
                    return original(*args, **kwargs)
                with mock.patch.object(board_api, "_write_and_commit", side_effect=change):
                    with self.assertRaisesRegex(board_api.BoardError, "changed"):
                        self.adopt()
                self.assertEqual(self.authority(), before)
                if race == "plan":
                    self.assertTrue(self.plan.read_bytes().endswith(b"Concurrent change\n"))
                    self.plan.write_bytes(plan_bytes)
                else:
                    git(self.repo, "remote", "remove", "origin")

    def test_adoption_rejects_foreign_repository_without_mutation(self):
        other = HuddleAccessTests.repo(self, "other")
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "binding"):
            self.adopt(repo=other)
        self.assertEqual(self.authority(), before)

    def test_replacement_and_old_identity_cannot_launch_but_current_selected_peer_can(self):
        with board_api._transaction(self.home) as (root, path, payload):
            peer = next(c for c in payload["claims"] if c["owner"] == "B")
            peer["return_by"] = board_api._stamp(NOW + timedelta(hours=10))
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: preserve valid peer", now=NOW)
        result = self.adopt()
        before = self.authority()
        for claim, allowed in ((self.a, False), (result["claim"], False), (self.b, True)):
            context = {key: claim[key] for key in ("entity", "row", "owner", "claim_revision")}
            context["board_revision"] = result["payload"]["revision"]
            request = dict(context=context, repo=self.repo, write_scope=claim["write_scope"],
                           authority_proposal=False, now=NOW + timedelta(hours=9), home=self.home)
            with self.subTest(owner=claim["owner"]):
                if allowed:
                    self.assertFalse(board_api.authorize_host_attempt(**request).changed)
                else:
                    with self.assertRaises(board_api.BoardError):
                        board_api.authorize_host_attempt(**request)
                self.assertEqual(self.authority(), before)

    def test_same_seat_adoption_still_invalidates_old_key(self):
        replacement = self.adopt(owner="A")["claim"]
        self.assertEqual(replacement["owner"], self.a["owner"])
        self.assertNotEqual(replacement["claim_revision"], self.a["claim_revision"])
        before = self.authority()
        with self.assertRaises(board_api.BoardError):
            self.submit()
        self.assertEqual(self.authority(), before)

    def test_direct_edge_reselection_invalidates_only_newly_held_yield(self):
        a, b = board_api._claim_ref(self.a), board_api._claim_ref(self.b)
        c = dict(a, row="~cc33", owner="C", claim_revision=b["claim_revision"] + 1)
        h = copy.deepcopy(self.huddle)
        h.update(claims=[a, b, c], edges=[dict(left=a, right=b, kinds=["path_overlap"]),
                                       dict(left=b, right=c, kinds=["path_overlap"])])
        h["holds"] = board_api.claim_holds(h)
        stable = dict(claim=b, target=None, support_claim=None, role="stand_down", round=1)
        h["bids"] = [stable, dict(claim=c, target=b, support_claim=None, role="yield", round=1)]
        replacement = dict(self.a, owner="Successor", claim_revision=c["claim_revision"] + 1)
        board_api._adopt_open_huddle_participant({"huddles": [h]}, self.a, replacement, NOW)
        self.assertEqual(h["bids"], [stable])
        self.assertEqual(h["holds"], [c, board_api._claim_ref(replacement)])

    def test_awaiting_scope_adoption_keeps_unknown_scope_and_round_zero(self):
        # Change only this fixture through the real owner classification path.
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            self.repo, self.plan = HuddleClaimCreationTests.seed(self)
            self.a = self.take(self.repo, self.plan, "~aa11", "A", access="unscoped", scope=[])["claim"]
            self.b = self.take(self.repo, self.plan, "~bb22", "B")["claim"]
            result = self.adopt()
            h = result["payload"]["huddles"][0]
            self.assertEqual((h["state"], h["round"]), ("awaiting_scope", 0))
            self.assertEqual(h["edges"][0]["kinds"], ["scope_unknown"])
            self.assertEqual(result["claim"]["access"], "unscoped")
            self.assertEqual(result["claim"]["write_scope"], [])
            self.assertEqual(h["holds"], [board_api._claim_ref(result["claim"])])

    def test_adoption_refuses_live_claim_and_declaration_changes_without_mutation(self):
        for changes in ({"now": NOW}, {"access": "read_only"},
                        {"access": "write", "write_scope": ["b"]},
                        {"access": "write", "write_scope": ["a", "b"]}):
            with self.subTest(changes=changes):
                before = self.authority()
                with self.assertRaises(board_api.BoardError):
                    self.adopt(**changes)
                self.assertEqual(self.authority(), before)

    def test_adoption_rolls_back_on_journal_failure(self):
        before = self.authority()
        with mock.patch.object(board_api, "_commit", side_effect=board_api.BoardError("injected")):
            with self.assertRaisesRegex(board_api.BoardError, "injected"):
                self.adopt()
        self.assertEqual(self.authority(), before)


class HuddleSchemaTests(HuddleTestCase):
    def fixture(self, state):
        payload = self.v2_board(with_claim=False)
        payload["revision"] = 20
        for index, owner in enumerate(("A", "B"), 1):
            claim = self.v1_board()["claims"][0]
            claim.update(owner=owner, row="~aa11" if index == 1 else "~bb22",
                claim_revision=index, access="write", write_scope=["a"],
                repository_binding={"common_dir_sha256": "c" * 64, "remote_identity": None})
            payload["claims"].append(claim)
        a, b = [{key: c[key] for key in ("entity", "row", "claim_revision", "owner", "claimed_at")}
                for c in payload["claims"]]
        h = dict(id="hdl_1234abcd", state=state, reason="write_scope_overlap", opened_revision=3,
            generation=3, opened_at="2026-09-04T16:00:00Z", reply_by="2026-09-04T16:02:00Z",
            round=1, claims=[a, b], edges=[{"left": a, "right": b, "kinds": ["path_overlap"]}],
            holds=[b], bids=[], resolution=None, compliance=[], remote_transition=None,
            resolved_at=None, retain_until=None)
        payload["huddles"] = [h]
        if state == "awaiting_scope":
            payload["claims"][0].update(access="unscoped", write_scope=[])
            h.update(round=0)
            h["edges"][0]["kinds"] = ["scope_unknown"]
        elif state == "open_round_2":
            h.update(round=2, reply_by="2026-09-04T16:04:00Z")
            h["bids"] = [self.bid(h, a, "own", round=1, generation=2),
                         self.bid(h, b, "own", round=1, generation=2)]
        elif state == "remote_pending":
            successor = {**a, "owner": "B"}
            h.update(reply_by=None, holds=[a, successor, b], remote_transition={
                "source_claim": a, "successor_claim": successor, "target_prior_claim": b,
                "target_prior_action": "return_required",
                "remote_ref": "refs/heads/shadow/claims/v1/" + E1 + "/aa11",
                "expected_remote_version": "e" * 40, "readback": "not_attempted", "attempt_receipt": None})
            h["bids"] = [self.bid(h, a, "yield", target=b), self.bid(h, b, "own", handoff=True)]
        elif state in ("awaiting_compliance", "resolved"):
            h.update(reply_by=None, resolution={"settled_revision": 10, "settled_at": "2026-09-04T16:01:00Z",
                "rule": "earliest_valid_claim", "handoff": None, "write_owners": [a],
                "actions": [{"claim": a, "action": "continue"}, {"claim": b, "action": "return_required"}],
                "support_actions": []}, compliance=[{"claim": b, "required": "canonical_disposition_then_return",
                    "plan_root_at_settlement": "e" * 64, "status": "pending", "completion": None}])
            if state == "resolved":
                payload["claims"].pop()
                h.update(holds=[], resolved_at="2026-09-04T16:02:00Z", retain_until="2026-09-05T16:02:00Z")
                h["compliance"][0].update(status="satisfied", completion={
                    "kind": "return", "board_revision": 11, "receipt": "self"})
        return payload

    def bid(self, h, ref, role, *, round=1, generation=3, target=None, handoff=False):
        request = dict(seat=ref["owner"], claim=copy.deepcopy(ref), role=role, scope=["a"],
            reason="owner_authorized_handoff" if target or handoff else "existing_claim", target=target,
            support_claim=None, evidence={"kind": "claim", "value": "self"}, round=round,
            expected_huddle_generation=generation)
        digest = hashlib.sha256(json.dumps({"huddle_id": h["id"], **request},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {**request, "bid_digest": digest, "submitted_at": "2026-09-04T16:00:30Z"}

    def test_all_six_complete_states_decode_and_round_two_keeps_prior_bids(self):
        for state in ("awaiting_scope", "open_round_1", "open_round_2", "remote_pending", "awaiting_compliance", "resolved"):
            with self.subTest(state=state):
                payload = self.fixture(state)
                board_api._validate(payload)

    def test_state_matrix_and_nested_closed_fields_refuse_one_fault_at_a_time(self):
        cases = [
            ("awaiting_scope", ("round",), 1),
            ("open_round_1", ("reply_by",), None),
            ("open_round_2", ("round",), 3),
            ("remote_pending", ("remote_transition", "readback"), "successor"),
            ("remote_pending", ("remote_transition", "successor_claim", "row"), "~cc33"),
            ("remote_pending", ("remote_transition", "expected_remote_version"), "private/value"),
            ("remote_pending", ("holds",), []),
            ("awaiting_compliance", ("compliance", 0, "completion"), {}),
            ("awaiting_compliance", ("resolution", "actions", 1, "action"), "continue"),
            ("awaiting_compliance", ("resolution", "write_owners"), []),
            ("resolved", ("retain_until",), "2026-09-05T16:02:01Z"),
            ("resolved", ("compliance", 0, "completion", "board_revision"), True),
            ("resolved", ("compliance", 0, "completion", "receipt"), "/Users/private"),
            ("resolved", ("resolution", "actions", 0, "claim", "claim_revision"), True),
        ]
        for state, path, value in cases:
            payload = self.fixture(state)
            node = payload["huddles"][0]
            for component in path[:-1]:
                node = node[component]
            node[path[-1]] = value
            with self.subTest(state=state, path=path), self.assertRaises(board_api.BoardError):
                board_api._validate(payload)
        for state, field in (("open_round_2", "bids"), ("awaiting_compliance", "compliance"),
                             ("awaiting_compliance", "resolution"), ("remote_pending", "remote_transition")):
            payload = self.fixture(state)
            node = payload["huddles"][0][field]
            (node[0] if isinstance(node, list) else node)["transcript"] = "forbidden"
            with self.subTest(field=field), self.assertRaises(board_api.BoardError):
                board_api._validate(payload)

    def test_bid_digest_scope_identity_and_evidence_are_not_trusted(self):
        for field, value in (("seat", "Other"), ("bid_digest", "0" * 64),
            ("evidence", {"kind": "claim", "value": "/Users/private"}), ("target", {}),
            ("scope", ["../private"]), ("expected_huddle_generation", True)):
            payload = self.fixture("open_round_2")
            payload["huddles"][0]["bids"][0][field] = value
            with self.subTest(field=field), self.assertRaises(board_api.BoardError):
                board_api._validate(payload)

    def test_terminal_remote_readback_and_local_handoff_have_exact_successors(self):
        for mode in ("local", "remote"):
            payload = self.fixture("remote_pending")
            h = payload["huddles"][0]
            remote = h["remote_transition"]
            a, b = h["claims"]
            successor = remote["successor_claim"]
            payload["claims"][0]["owner"] = "B"
            h.update(state="awaiting_compliance", holds=[b], resolution={"settled_revision": 10,
                "settled_at": "2026-09-04T16:01:00Z", "rule": "owner_authorized_handoff",
                "handoff": {key: remote[key] for key in ("source_claim", "successor_claim", "target_prior_claim", "target_prior_action")},
                "write_owners": [successor], "actions": [{"claim": a, "action": "handoff_complete"},
                    {"claim": b, "action": "return_required"}], "support_actions": []},
                compliance=[{"claim": b, "required": "canonical_disposition_then_return", "plan_root_at_settlement": "e" * 64,
                    "status": "pending", "completion": None}])
            h["resolution"]["handoff"].update(mode=mode, remote_readback="successor" if mode == "remote" else None)
            if mode == "remote":
                remote.update(readback="successor", attempt_receipt="f" * 64)
            else:
                h["remote_transition"] = None
            with self.subTest(mode=mode):
                board_api._validate(payload)
                malformed = copy.deepcopy(payload)
                malformed["huddles"][0]["resolution"]["handoff"]["successor_claim"]["owner"] = "Other"
                with self.assertRaises(board_api.BoardError):
                    board_api._validate(malformed)

    def test_historical_resolution_does_not_freeze_later_access_declarations(self):
        payload = self.fixture("resolved")
        payload["claims"][0].update(access="read_only", repository_binding=None, write_scope=[])
        board_api._validate(payload)

    def test_superseded_round_one_handoff_pair_cannot_authorize_round_two(self):
        payload = self.fixture("remote_pending")
        h = payload["huddles"][0]
        h.update(round=2, generation=4)
        a, b = h["claims"]
        h["bids"].extend([self.bid(h, a, "own", round=2, generation=4),
                           self.bid(h, b, "stand_down", round=2, generation=4)])
        with self.assertRaisesRegex(board_api.BoardError, "pair"):
            board_api._validate(payload)

    def test_superseded_support_bid_cannot_create_final_support_action(self):
        payload = self.fixture("awaiting_compliance")
        h = payload["huddles"][0]
        support = copy.deepcopy(payload["claims"][1])
        support.update(row="~cc33", claim_revision=4, access="read_only", repository_binding=None, write_scope=[])
        payload["claims"].append(support)
        support_ref = {key: support[key] for key in ("entity", "row", "claim_revision", "owner", "claimed_at")}
        bid = self.bid(h, h["claims"][1], "review")
        bid.update(support_claim=support_ref, scope=[])
        request = {key: value for key, value in bid.items() if key not in ("bid_digest", "submitted_at")}
        bid["bid_digest"] = hashlib.sha256(json.dumps({"huddle_id": h["id"], **request},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        h["bids"] = [bid]
        h["resolution"]["support_actions"] = [{"participant_claim": h["claims"][1],
            "support_claim": support_ref, "action": "review_claim"}]
        board_api._validate(payload)
        h.update(round=2, generation=4)
        h["bids"].append(self.bid(h, h["claims"][1], "stand_down", round=2, generation=4))
        with self.assertRaisesRegex(board_api.BoardError, "matching bid"):
            board_api._validate(payload)

    def test_remote_pending_preserves_all_65_derived_holds(self):
        payload = self.fixture("remote_pending")
        payload["revision"] = 100
        h = payload["huddles"][0]
        for index in range(3, 65):
            claim = copy.deepcopy(payload["claims"][1])
            claim.update(row=f"~{index:04x}", claim_revision=index, owner=f"Seat{index}")
            payload["claims"].append(claim)
            h["claims"].append({key: claim[key] for key in ("entity", "row", "claim_revision", "owner", "claimed_at")})
        payload["claims"].sort(key=lambda c: (c["entity"], c["row"]))
        h["edges"] = [{"left": left, "right": right, "kinds": ["path_overlap"]}
            for index, left in enumerate(h["claims"]) for right in h["claims"][index + 1:]]
        h["holds"] = [h["claims"][0], h["remote_transition"]["successor_claim"], *h["claims"][1:]]
        self.assertEqual(len(h["holds"]), 65)
        board_api._validate(payload)
        h["holds"].pop()
        with self.assertRaisesRegex(board_api.BoardError, "holds"):
            board_api._validate(payload)

    def test_superseded_support_bid_can_outlive_its_independent_claim(self):
        payload = self.fixture("open_round_2")
        h = payload["huddles"][0]
        bid = self.bid(h, h["claims"][1], "review", round=1, generation=2)
        bid.update(scope=[], support_claim={**h["claims"][1], "row": "~cc33", "claim_revision": 4})
        request = {key: value for key, value in bid.items() if key not in ("bid_digest", "submitted_at")}
        bid["bid_digest"] = hashlib.sha256(json.dumps({"huddle_id": h["id"], **request},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        h["bids"] = [bid, self.bid(h, h["claims"][1], "unavailable", round=2)]
        board_api._validate(payload)


class HuddleRetentionTests(HuddleTestCase):
    def test_publication_refuses_invalid_nested_state_before_any_write(self):
        payload = HuddleSchemaTests.fixture(self, "resolved")
        self.seed_v2(payload)
        before = self.authority()
        with board_api._transaction(self.home) as (root, path, current):
            current["revision"] += 1
            current["huddles"][0]["resolution"]["transcript"] = "forbidden"
            with mock.patch.object(board_api, "datetime", wraps=datetime) as clock:
                clock.now.return_value = NOW + timedelta(hours=25)
                with self.assertRaises(board_api.BoardError):
                    board_api._write_and_commit(root, path, current, "test: malformed expired resolution")
        self.assertEqual(self.authority(), before)

    def test_reads_retain_expired_record_until_next_successful_mutation(self):
        payload = HuddleSchemaTests.fixture(self, "resolved")
        self.seed_v2(payload)
        before = self.authority()
        with mock.patch.object(board_api, "datetime", wraps=datetime) as clock:
            clock.now.return_value = NOW + timedelta(hours=25)
            self.assertEqual(len(board_api.snapshot(home=self.home)["huddles"]), 1)
            self.assertEqual(board_api.huddle_show("hdl_1234abcd", home=self.home)["state"], "resolved")
            self.assertEqual(self.authority(), before)
            with board_api._transaction(self.home) as (root, path, current):
                current["revision"] += 1
                board_api._write_and_commit(root, path, current, "test: next mutation prunes expired history")
        after = board_api.snapshot(home=self.home)
        self.assertEqual(after["huddles"], [])
        self.assertEqual(after["revision"], payload["revision"] + 1)

    def test_65th_resolution_evicts_oldest_settled_revision_then_id(self):
        payload = HuddleSchemaTests.fixture(self, "resolved")
        template = payload["huddles"][0]
        payload["huddles"] = [{**copy.deepcopy(template), "id": f"hdl_{index:08x}"} for index in range(64)]
        self.seed_v2(payload)
        with board_api._transaction(self.home) as (root, path, current):
            current["revision"] += 1
            current["huddles"].append({**copy.deepcopy(template), "id": "hdl_ffffffff"})
            board_api._write_and_commit(root, path, current, "test: retain newest terminal receipt",
                                        now=NOW + timedelta(minutes=3))
        after = board_api.snapshot(home=self.home)
        self.assertEqual(len(after["huddles"]), 64)
        self.assertNotIn("hdl_00000000", [h["id"] for h in after["huddles"]])
        self.assertIn("hdl_ffffffff", [h["id"] for h in after["huddles"]])
        self.assertEqual(after["claims"], payload["claims"])

    def test_public_scope_resolution_succeeds_at_retention_capacity(self):
        repo, (a, b) = HuddleScopeTransitionTests.seed(self, [[], ["a"]], unscoped=(0,))
        opened = board_api.open_or_join_huddle(claim=b, overlap=[a], reason="scope_request", now=NOW, home=self.home)
        huddle_id = opened.payload["huddles"][0]["id"]
        template = HuddleSchemaTests.fixture(self, "resolved")["huddles"][0]
        with board_api._transaction(self.home) as (root, path, current):
            current["revision"] = 50
            current["huddles"].extend({**copy.deepcopy(template), "id": f"hdl_f{index:07x}"} for index in range(64))
            board_api._write_and_commit(root, path, current, "test: fill retained capacity",
                                        now=NOW + timedelta(minutes=3))
        result = board_api.preflight_access(entity=a["entity"], row=a["row"], owner=a["owner"], repo=repo,
            access="write", write_scope=["b"], expected_claim_revision=a["claim_revision"],
            expected_board_revision=50, now=NOW + timedelta(seconds=10), home=self.home)
        self.assertEqual(len(result.payload["huddles"]), 64)
        self.assertEqual(result.payload["revision"], 51)
        self.assertEqual(board_api.huddle_show(huddle_id, home=self.home)["state"], "resolved")


if __name__ == "__main__":
    unittest.main()
