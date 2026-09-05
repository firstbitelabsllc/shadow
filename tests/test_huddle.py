from __future__ import annotations

import copy
import dataclasses
from datetime import datetime, timedelta, timezone
import fcntl
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
import shadow_huddle_event as event_api


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
        value |= changes
        if value["role"] == "own" and value["reason"] == "owner_authorized_handoff":
            live = board_api.huddle_show(self.huddle["id"], home=self.home)
            held = {board_api._claim_key(ref) for ref in live["holds"]}
            offered = [bid["claim"] for bid in live["bids"] if bid["role"] == "yield"
                       and bid["target"] == value["claim"]]
            sources = offered or [ref for ref in live["claims"]
                                  if ref != value["claim"] and board_api._claim_key(ref) not in held]
            if len(sources) != 1:
                raise AssertionError("fixture requires one selected handoff source")
            value["evidence"] = {"kind": "claim", "value": board_api.huddle_handoff_acceptance(
                sources[0], value["claim"], home=self.home)}
        return value

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


class HuddleRemoteTests(HuddleSettlementTests):
    """Board half of the two-phase path; Git authentication has its own fixture below."""

    remote_token = {"head": "a" * 40, "blob": "b" * 40, "relative": "PLAN.md"}

    def _finalize(self, **kwargs):
        with mock.patch.object(board_api, "committed_plan_snapshot", return_value=(self.remote_token, b"# Plan\n")):
            return board_api.finalize_huddle_handoff(**kwargs)

    def _begin(self, *, now=NOW, **checks):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        huddle = board_api.snapshot(home=self.home)["huddles"][0]
        source = board_api._claim_ref(self.a)
        successor = {**source, "owner": self.b["owner"]}
        return board_api.begin_huddle_handoff(
            huddle_id=huddle["id"], generation=huddle["generation"], source_claim=source,
            successor_claim=successor, target_prior_claim=board_api._claim_ref(self.b),
            remote_ref=board_api._remote_claim.claim_ref(source["entity"], source["row"]),
            expected_remote_version="d" * 40, now=now, home=self.home, **checks), source, successor

    def test_remote_begin_and_finalize_bind_the_callers_board_revision(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        payload = board_api.snapshot(home=self.home)
        before = self.authority()
        for checks in ({"expected_board_revision": payload["revision"] - 1},
                       {"expected_board_revision": True},
                       {"actor_claim": {**board_api._claim_ref(self.a), "owner": "Other"}}):
            with self.subTest(checks=checks), self.assertRaises(board_api.BoardError):
                self._begin(**checks)
            self.assertEqual(self.authority(), before)
        pending, source, successor = self._begin(expected_board_revision=payload["revision"],
                                                 actor_claim=board_api._claim_ref(self.a))
        huddle = pending.payload["huddles"][0]
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "board revision changed"):
            self._finalize(huddle_id=huddle["id"], generation=huddle["generation"],
                remote_receipt=self._readback(source, successor, "successor"), now=NOW,
                home=self.home, expected_board_revision=pending.payload["revision"] - 1)
        self.assertEqual(self.authority(), before)
        finalized = self._finalize(huddle_id=huddle["id"], generation=huddle["generation"],
            remote_receipt=self._readback(source, successor, "successor"), now=NOW,
            home=self.home, expected_board_revision=pending.payload["revision"])
        self.assertEqual(finalized.payload["huddles"][0]["state"], "awaiting_compliance")

    def test_remote_handoff_waits_for_every_bid_or_records_deadline_silence(self):
        self.a, self.b, c = HuddleGraphTests.seed(self, [["a"], ["a", "b"], ["b"]])
        self.huddle = HuddleGraphTests.open(self, self.b, [self.a]).payload["huddles"][0]
        self.assertEqual(len(self.huddle["claims"]), 3)
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "awaits bids or deadline"):
            self._begin()
        self.assertEqual(self.authority(), before)
        pending, _, _ = self._begin(now=NOW + timedelta(minutes=2))
        huddle = pending.payload["huddles"][0]
        silent = [bid for bid in huddle["bids"] if bid["claim"] == board_api._claim_ref(c)]
        self.assertEqual(len(silent), 1)
        self.assertEqual(silent[0]["role"], "unavailable")
        self.assertEqual(silent[0]["reason"], "transport_unavailable")
        self.assertEqual(silent[0]["expected_huddle_generation"], self.huddle["generation"])
        self.assertEqual(huddle["state"], "remote_pending")

    def _readback(self, source, successor, outcome):
        remote = board_api._remote_claim
        source_full = next(claim for claim in board_api.snapshot(home=self.home)["claims"]
                           if board_api._claim_ref(claim) == source)
        successor_full = {**source_full, "owner": successor["owner"]}
        return remote._authenticated_huddle_readback(
            ref=remote.claim_ref(source["entity"], source["row"]), expected_remote_version="d" * 40,
            outcome=outcome, attempt_receipt=hashlib.sha256(outcome.encode()).hexdigest(),
            source_binding=remote._huddle_binding(source_full), successor_binding=remote._huddle_binding(successor_full),
            plan_binding=json.dumps(self.remote_token, sort_keys=True, separators=(",", ":")), project="shadow")

    def test_remote_handoff_holds_both_identities_and_successor_needs_real_readback(self):
        pending, source, successor = self._begin()
        h = pending.payload["huddles"][0]
        self.assertEqual(h["state"], "remote_pending")
        self.assertEqual(h["remote_transition"]["readback"], "not_attempted")
        self.assertEqual({board_api._claim_key(ref) for ref in h["holds"]}, {
            board_api._claim_key(source), board_api._claim_key(successor), board_api._claim_key(self.b)})
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "authenticated stable"):
            self._finalize(huddle_id=h["id"], generation=h["generation"],
                                               remote_receipt={"outcome": "successor"}, now=NOW, home=self.home)
        remote = board_api._remote_claim
        source_full = next(claim for claim in board_api.snapshot(home=self.home)["claims"]
                           if board_api._claim_ref(claim) == source)
        forged_successor = {**source_full, "owner": "C"}
        forged = remote.HuddleReadback(remote.claim_ref(source["entity"], source["row"]), "d" * 40,
            "successor", "e" * 64, remote._huddle_binding(source_full),
            remote._huddle_binding(forged_successor), "{}", "shadow", remote._HUDDLE_READBACK_SEAL)
        with self.assertRaisesRegex(board_api.BoardError, "authenticated stable"):
            self._finalize(huddle_id=h["id"], generation=h["generation"],
                                               remote_receipt=forged, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)
        result = self._finalize(
            huddle_id=h["id"], generation=h["generation"],
            remote_receipt=self._readback(source, successor, "successor"), now=NOW, home=self.home)
        final = result.payload["huddles"][0]
        self.assertEqual(final["state"], "awaiting_compliance")
        self.assertEqual(final["remote_transition"]["readback"], "successor")
        self.assertEqual(final["resolution"]["write_owners"], [successor])
        self.assertEqual(final["holds"], [board_api._claim_ref(self.b)])

    def test_replaced_or_mutated_readback_cannot_authorize_handoff(self):
        pending, source, successor = self._begin()
        h = pending.payload["huddles"][0]
        valid = self._readback(source, successor, "successor")
        before = self.authority()
        variants = [
            dataclasses.replace(valid, outcome="predecessor"),
            dataclasses.replace(valid, ref="refs/heads/shadow/claims/v1/" + "b" * 64 + "/bb22"),
            dataclasses.replace(valid, expected_remote_version="e" * 40),
            dataclasses.replace(valid, source_binding="{}"),
            dataclasses.replace(valid, successor_binding="{}"),
            dataclasses.replace(valid, plan_binding="{}"),
            dataclasses.replace(valid, attempt_receipt="f" * 64),
        ]
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(board_api.BoardError, "authenticated stable"):
                    self._finalize(huddle_id=h["id"], generation=h["generation"],
                                   remote_receipt=value, now=NOW, home=self.home)
                self.assertEqual(self.authority(), before)
        object.__setattr__(valid, "outcome", "predecessor")
        with self.assertRaisesRegex(board_api.BoardError, "authenticated stable"):
            self._finalize(huddle_id=h["id"], generation=h["generation"],
                           remote_receipt=valid, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_target_self_evidence_is_refused_and_immutable_acceptance_replays(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "acceptance"):
            board_api.submit_huddle_bid(**dict(huddle_id=self.huddle["id"], seat=self.b["owner"],
                claim=board_api._claim_ref(self.b), role="own", scope=self.b["write_scope"],
                reason="owner_authorized_handoff", target=None, support_claim=None,
                evidence={"kind": "claim", "value": "self"}, round=1,
                expected_huddle_generation=self.huddle["generation"]), now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)
        accepted = self.submit(self.b, reason="owner_authorized_handoff")
        replay = self.submit(self.b, reason="owner_authorized_handoff")
        self.assertFalse(replay.changed)
        self.assertEqual(replay.payload, accepted.payload)

    def test_acceptance_root_and_claim_mutants_fail_before_remote_begin(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        h = board_api.snapshot(home=self.home)["huddles"][0]
        source = board_api._claim_ref(self.a)
        target = board_api._claim_ref(self.b)
        accepted = board_api.bid_receipt(h["id"], target, 1, home=self.home)["evidence"]["value"]
        # A changed canonical source plan invalidates the existing acceptance.
        entity = next(e for e in board_api.snapshot(home=self.home)["entities"] if e["id"] == source["entity"])
        plan = Path(entity["plan"])
        plan.write_text(plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertNotEqual(accepted, board_api.huddle_handoff_acceptance(source, target, home=self.home))
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "acceptance"):
            board_api.begin_huddle_handoff(huddle_id=h["id"], generation=h["generation"], source_claim=source,
                successor_claim={**source, "owner": target["owner"]}, target_prior_claim=target,
                remote_ref=board_api._remote_claim.claim_ref(source["entity"], source["row"]),
                expected_remote_version="d" * 40, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_changed_acceptance_after_remote_begin_keeps_holds_pending(self):
        pending, source, successor = self._begin()
        h = pending.payload["huddles"][0]
        target = board_api._claim_ref(self.b)
        entity = next(e for e in board_api.snapshot(home=self.home)["entities"] if e["id"] == target["entity"])
        plan = Path(entity["plan"])
        accepted_bytes = plan.read_bytes()
        accepted_bid = board_api.bid_receipt(h["id"], target, 1, home=self.home)
        accepted_value = accepted_bid["evidence"]["value"]
        prior_state = board_api.plan_state_token(plan)
        os.utime(plan, None)
        self.assertNotEqual(prior_state, board_api.plan_state_token(plan))
        self.assertEqual(accepted_value, board_api.huddle_handoff_acceptance(source, target, home=self.home))
        plan.write_text(accepted_bytes.decode("utf-8") + "\n", encoding="utf-8")
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "acceptance"):
            self._finalize(huddle_id=h["id"], generation=h["generation"],
                           remote_receipt=self._readback(source, successor, "successor"), now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)
        still = board_api.snapshot(home=self.home)["huddles"][0]
        self.assertEqual(still["state"], "remote_pending")
        self.assertEqual({board_api._claim_key(ref) for ref in still["holds"]},
                         {board_api._claim_key(source), board_api._claim_key(successor), board_api._claim_key(target)})
        plan.write_bytes(accepted_bytes)
        self.assertNotEqual(prior_state, board_api.plan_state_token(plan))
        self.assertEqual(accepted_value, board_api.huddle_handoff_acceptance(source, target, home=self.home))
        finished = self._finalize(huddle_id=still["id"], generation=still["generation"],
                                  remote_receipt=self._readback(source, successor, "successor"), now=NOW, home=self.home)
        self.assertEqual(finished.payload["huddles"][0]["resolution"]["write_owners"], [successor])
        self.assertEqual(board_api.bid_receipt(h["id"], target, 1, home=self.home), accepted_bid)

    def test_stable_predecessor_cancels_despite_target_root_change(self):
        pending, source, successor = self._begin()
        h = pending.payload["huddles"][0]
        target = board_api._claim_ref(self.b)
        entity = next(e for e in board_api.snapshot(home=self.home)["entities"] if e["id"] == target["entity"])
        plan = Path(entity["plan"])
        plan.write_text(plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = self._finalize(huddle_id=h["id"], generation=h["generation"],
                                remote_receipt=self._readback(source, successor, "predecessor"), now=NOW, home=self.home)
        final = result.payload["huddles"][0]
        self.assertEqual(final["remote_transition"]["readback"], "predecessor")
        self.assertEqual(final["resolution"]["write_owners"], [source])

    def test_source_lease_change_invalidates_accepted_handoff_without_publication(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        h = board_api.snapshot(home=self.home)["huddles"][0]
        source, target = board_api._claim_ref(self.a), board_api._claim_ref(self.b)
        with board_api._transaction(self.home) as (root, path, payload):
            claim = next(c for c in payload["claims"] if board_api._claim_ref(c) == source)
            claim["return_by"] = "2026-09-04T18:00:00Z"
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: changed source lease", now=NOW)
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "acceptance"):
            board_api.begin_huddle_handoff(huddle_id=h["id"], generation=h["generation"], source_claim=source,
                successor_claim={**source, "owner": target["owner"]}, target_prior_claim=target,
                remote_ref=board_api._remote_claim.claim_ref(source["entity"], source["row"]),
                expected_remote_version="d" * 40, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_binding_and_source_only_target_claim_are_in_acceptance_guards(self):
        payload = board_api.snapshot(home=self.home)
        source, target = payload["claims"]
        root = "a" * 64
        baseline = board_api._handoff_acceptance_digest(source, target, root, root)
        changed_target = copy.deepcopy(target)
        changed_target["repository_binding"] = {"common_dir_sha256": "d" * 64, "remote_identity": None}
        self.assertNotEqual(baseline, board_api._handoff_acceptance_digest(source, changed_target, root, root))
        source_only = copy.deepcopy(target)
        source_only.update(row="~cc33", claim_revision=99, write_scope=["a"])
        source_scope = copy.deepcopy(source)
        source_scope["write_scope"] = ["a"]
        target_scope = copy.deepcopy(target)
        target_scope["write_scope"] = ["b"]
        self.assertTrue(board_api._successor_scope_conflict({"claims": [source_scope, target_scope, source_only]},
                                                            source_scope, target_scope))

    def test_stale_acceptance_recovery_requires_fresh_return_and_reclaim(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        h = board_api.snapshot(home=self.home)["huddles"][0]
        source, target = board_api._claim_ref(self.a), board_api._claim_ref(self.b)
        with board_api._transaction(self.home) as (root, path, payload):
            claim = next(c for c in payload["claims"] if board_api._claim_ref(c) == source)
            claim["return_by"] = "2026-09-04T18:00:00Z"
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: stale acceptance", now=NOW)
        with self.assertRaises(board_api.BoardError):
            board_api.begin_huddle_handoff(huddle_id=h["id"], generation=h["generation"], source_claim=source,
                successor_claim={**source, "owner": target["owner"]}, target_prior_claim=target,
                remote_ref=board_api._remote_claim.claim_ref(source["entity"], source["row"]),
                expected_remote_version="d" * 40, now=NOW, home=self.home)
        # Existing protocol deliberately retains this live Huddle: the old bid cannot be rewritten.
        self.assertEqual(board_api.snapshot(home=self.home)["huddles"][0]["state"], "open_round_1")
        target_entity = next(e for e in board_api.snapshot(home=self.home)["entities"] if e["id"] == target["entity"])
        returned, changed = board_api.release(Path(target_entity["plan"]), target["row"], owner=target["owner"],
                                              reason="handback", expected_claim=self.b, now=NOW, home=self.home)
        self.assertTrue(changed)
        self.assertEqual(returned["huddles"][0]["state"], "resolved")

    def test_remote_predecessor_cancels_transfer_and_ambiguous_retains_holds(self):
        for outcome, expected_state in (("predecessor", "awaiting_compliance"), ("ambiguous", "remote_pending")):
            with self.subTest(outcome=outcome):
                self.setUp()
                pending, source, successor = self._begin()
                h = pending.payload["huddles"][0]
                result = self._finalize(
                    huddle_id=h["id"], generation=h["generation"],
                    remote_receipt=self._readback(source, successor, outcome), now=NOW, home=self.home)
                final = result.payload["huddles"][0]
                self.assertEqual(final["state"], expected_state)
                if outcome == "predecessor":
                    self.assertEqual(final["resolution"]["write_owners"], [source])
                else:
                    self.assertEqual({board_api._claim_key(ref) for ref in final["holds"]}, {
                        board_api._claim_key(source), board_api._claim_key(successor), board_api._claim_key(self.b)})

    def test_real_bare_git_handoff_requires_full_identity_and_stable_readback(self):
        remote = board_api._remote_claim
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bare, repo = root / "remote.git", root / "checkout"
            subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
            repo.mkdir()
            for args in (("init", "-q"), ("config", "user.email", "fixture@example.invalid"),
                         ("config", "user.name", "Fixture")):
                subprocess.run(["git", "-C", str(repo), *args], check=True)
            (repo / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "PLAN.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(bare)], check=True)
            subprocess.run(["git", "-C", str(repo), "push", "-qu", "origin", "HEAD:main"], check=True)
            subprocess.run(["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
            token, _ = board_api.committed_plan_snapshot(repo / "PLAN.md")
            source = {"entity": "a" * 64, "row": "~aa11", "claim_revision": 9,
                      "owner": "A", "claimed_at": "2026-09-04T15:00:00Z",
                      "return_by": "2026-09-04T17:00:00Z", "recovery": board_api.RECOVERY_ACTION}
            successor = {**source, "owner": "B"}
            ref = remote.claim_ref(source["entity"], source["row"])
            initial = remote._receipt(status="acquired", ref=ref, entity=source["entity"], row=source["row"],
                owner="A", project="shadow", plan_token=token, claimed_at=source["claimed_at"],
                return_by=source["return_by"], recovery=source["recovery"], state="acquired",
                reason="acquire", winner="A", failure=None, claim_revision=source["claim_revision"])
            version = remote._commit_receipt(repo, initial, source["claimed_at"])
            self.assertIsNotNone(version)
            self.assertTrue(remote._push(repo, str(bare), ref, version, None))
            result = remote.handoff_huddle_claim(repo, expected_remote_version=version,
                source_claim=source, successor_claim=successor, project="shadow", plan_token=token)
            self.assertEqual(result.outcome, "successor")
            self.assertIs(remote.trusted_huddle_readback(result), result)
            # Same owner/row but a changed lease cannot replay as predecessor.
            stale = {**source, "return_by": "2026-09-04T18:00:00Z"}
            checked = remote.read_remote_claim_stably(repo, expected_remote_version=version,
                source_claim=stale, successor_claim={**stale, "owner": "C"}, project="shadow", plan_token=token)
            self.assertEqual(checked.outcome, "ambiguous")

    def test_alternating_authenticated_readbacks_are_not_a_remote_authorization(self):
        remote = board_api._remote_claim
        token = {"head": "a" * 40, "blob": "b" * 40, "relative": "PLAN.md"}
        source = {"entity": "a" * 64, "row": "~aa11", "claim_revision": 9,
                  "owner": "A", "claimed_at": "2026-09-04T15:00:00Z",
                  "return_by": "2026-09-04T17:00:00Z", "recovery": board_api.RECOVERY_ACTION}
        successor = {**source, "owner": "B"}
        ref = remote.claim_ref(source["entity"], source["row"])
        source_receipt = remote._receipt(status="acquired", ref=ref, entity=source["entity"], row=source["row"],
            owner="A", project="shadow", plan_token=token, claimed_at=source["claimed_at"],
            return_by=source["return_by"], recovery=source["recovery"], state="acquired",
            reason="acquire", winner="A", failure=None, claim_revision=9)
        successor_receipt = {**source_receipt, "owner": "B", "winner": "B", "reason": "handoff"}
        alternating = [("c" * 40, source_receipt), ("d" * 40, successor_receipt)] * 2
        binding = remote.UpstreamBinding(remote.RemoteEligibility.REMOTE, endpoint="fixture")
        with mock.patch.object(remote, "upstream_binding", return_value=binding), \
             mock.patch.object(remote, "_remote_tip", side_effect=alternating):
            result = remote.read_remote_claim_stably(Path("."), expected_remote_version="c" * 40,
                source_claim=source, successor_claim=successor, project="shadow", plan_token=token)
        self.assertEqual(result.outcome, "ambiguous")

    def test_remote_handoff_preserves_another_selected_writer_and_all_holds(self):
        with board_api._transaction(self.home) as (root, path, payload):
            h = payload["huddles"][0]
            current_a = next(claim for claim in payload["claims"] if board_api._claim_ref(claim) == board_api._claim_ref(self.a))
            current_b = next(claim for claim in payload["claims"] if board_api._claim_ref(claim) == board_api._claim_ref(self.b))
            current_a["write_scope"], current_b["write_scope"] = ["a"], ["a", "b"]
            self.a["write_scope"], self.b["write_scope"] = ["a"], ["a", "b"]
            c = copy.deepcopy(self.b)
            c.update(entity="c" * 64, owner="C", claim_revision=payload["revision"],
                     write_scope=["b", "c"])
            plan = self.home / "c" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("# Work\n\n## Tasks\n\n- [pending] Work ~aa11 | proof: cmd true\n")
            payload["entities"].append({"id": c["entity"], "project": "shadow", "plan": str(plan), "resume": "~aa11"})
            payload["claims"].append(c)
            c_ref = board_api._claim_ref(c)
            d = copy.deepcopy(c)
            d.update(entity="d" * 64, owner="D", claim_revision=payload["revision"] + 1,
                     write_scope=["c"])
            d_plan = self.home / "d" / "PLAN.md"
            d_plan.parent.mkdir(parents=True)
            d_plan.write_text("# Work\n\n## Tasks\n\n- [pending] Work ~aa11 | proof: cmd true\n")
            payload["entities"].append({"id": d["entity"], "project": "shadow", "plan": str(d_plan), "resume": "~aa11"})
            payload["claims"].append(d)
            d_ref = board_api._claim_ref(d)
            h["claims"] = sorted(h["claims"] + [c_ref], key=board_api._claim_rank)
            h["claims"] = sorted(h["claims"] + [d_ref], key=board_api._claim_rank)
            h["edges"] = sorted(h["edges"] + [
                dict(left=board_api._claim_ref(self.b), right=c_ref, kinds=["path_overlap"]),
                dict(left=c_ref, right=d_ref, kinds=["path_overlap"])],
                key=lambda edge: (board_api._claim_rank(edge["left"]), board_api._claim_rank(edge["right"])))
            h["holds"] = board_api.claim_holds(h)
            h["generation"] += 1
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: three owner remote graph", now=NOW)
        with board_api._transaction(self.home) as (root, path, payload):
            support = copy.deepcopy(d)
            support.update(entity="e" * 64, row="~ss11", owner="D", claim_revision=payload["revision"] + 1,
                           access="read_only", repository_binding=None, write_scope=[])
            support_plan = self.home / "support" / "PLAN.md"
            support_plan.parent.mkdir(parents=True)
            support_plan.write_text("# Support\n\n## Tasks\n\n- [pending] Support ~ss11 | proof: cmd true\n")
            payload["entities"].append({"id": support["entity"], "project": "shadow", "plan": str(support_plan), "resume": "~ss11"})
            payload["claims"].append(support)
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: remote support", now=NOW)
        h = board_api.snapshot(home=self.home)["huddles"][0]
        board_api.submit_huddle_bid(huddle_id=h["id"], seat="D", claim=d_ref, role="review", scope=[],
            reason="best_proof_access", target=None, support_claim=board_api._claim_ref(support),
            evidence={"kind": "claim", "value": "self"}, round=1,
            expected_huddle_generation=h["generation"], now=NOW, home=self.home)
        self.huddle = board_api.snapshot(home=self.home)["huddles"][0]
        self.submit(c)
        pending, source, successor = self._begin()
        h = pending.payload["huddles"][0]
        result = self._finalize(huddle_id=h["id"], generation=h["generation"],
            remote_receipt=self._readback(source, successor, "successor"), now=NOW, home=self.home)
        final = result.payload["huddles"][0]
        self.assertEqual(final["state"], "awaiting_compliance")
        self.assertEqual({ref["owner"] for ref in final["resolution"]["write_owners"]}, {"B", "C"})
        self.assertEqual(final["holds"], [board_api._claim_ref(self.b), d_ref])
        self.assertEqual(final["resolution"]["support_actions"], [{"participant_claim": d_ref,
            "support_claim": board_api._claim_ref(support), "action": "review_claim"}])


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

    def test_departure_event_follows_commit_and_unlock_and_failure_is_optional(self):
        events = []
        def observe(event, *, repo_root, home):
            self.assertEqual(repo_root, ROOT)
            self.assertEqual(home, self.home)
            with (self.home / ".shadow" / ".board.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    huddle = board_api.snapshot(home=self.home)["huddles"][0]
                    self.assertEqual(huddle["state"], "resolved")
                    self.assertEqual(event, {"schema": "shadow.huddle-delivery-event.v1",
                        "event": "huddle_changed", "huddle_id": huddle["id"],
                        "generation": huddle["generation"]})
                    events.append(event)
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
            raise event_api.RunnerRefused("injected optional transport failure")
        with mock.patch.object(event_api, "emit_post_commit", side_effect=observe):
            result, changed = self.release(self.b)
            self.assertTrue(changed)
            self.assertEqual(len(events), 1)
            self.assertEqual(result, board_api.snapshot(home=self.home))
            self.assertFalse(board_api.release(self.plans["B"], self.b["row"], owner="B",
                reason="handback", now=NOW, home=self.home)[1])
            self.assertEqual(len(events), 1)

    def test_failed_departure_commit_emits_nothing(self):
        before = self.authority()
        with mock.patch.object(event_api, "emit_post_commit") as emit, \
             mock.patch.object(board_api, "_commit", side_effect=board_api.BoardError("injected journal failure")):
            with self.assertRaisesRegex(board_api.BoardError, "injected journal failure"):
                self.release(self.b)
            emit.assert_not_called()
        self.assertEqual(self.authority(), before)

    def test_stale_completion_emits_exact_committed_departure(self):
        self.complete_plan("A")
        self.age_claim(self.a)
        with mock.patch.object(event_api, "emit_post_commit") as emit:
            self.assertEqual(board_api.release_stranded_completed_claims(now=NOW, home=self.home), 1)
            huddle = board_api.snapshot(home=self.home)["huddles"][0]
            emit.assert_called_once_with({"schema": "shadow.huddle-delivery-event.v1",
                "event": "huddle_changed", "huddle_id": huddle["id"],
                "generation": huddle["generation"]}, repo_root=ROOT, home=self.home)

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


class HuddleDefaultActivationTests(HuddleTestCase):
    def seed(self, *, legacy=False):
        repo, plan = HuddleClaimCreationTests.seed(self)
        with board_api._transaction(self.home) as (root, path, payload):
            v1 = self.v1_board(with_claim=legacy)
            board_api._write_and_commit(root, path, v1, "test: legacy authority", now=NOW)
        return repo, plan

    def test_claim_migrates_and_creates_one_revision_without_inventing_legacy_scope(self):
        repo, plan = self.seed(legacy=True)
        before = board_api.snapshot(home=self.home)
        history = board_api._git(self.home / ".shadow", "rev-list", "--count", "HEAD").stdout
        result = board_api.claim(plan, "~aa11", "A", project="shadow", priority=1,
                                 repo=repo, now=NOW, home=self.home)
        payload = result["payload"]
        self.assertEqual(payload["schema"], board_api.V2_SCHEMA)
        self.assertEqual(payload["revision"], before["revision"] + 1)
        self.assertEqual(result["claim"]["claim_revision"], payload["revision"])
        self.assertEqual(result["claim"]["repository_binding"], board_api.repository_binding(repo))
        old = next(claim for claim in payload["claims"] if claim["owner"] == "Codex")
        self.assertEqual(old, before["claims"][0] | {"claim_revision": 0, "access": "unscoped",
                                                     "repository_binding": None, "write_scope": []})
        self.assertEqual(int(board_api._git(self.home / ".shadow", "rev-list", "--count", "HEAD").stdout),
                         int(history) + 1)
        unchanged = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "legacy_binding_unknown"):
            board_api.preflight_access(entity=result["entity"]["id"], row="~aa11", owner="A",
                repo=repo, access="write", write_scope=["a"],
                expected_claim_revision=result["claim"]["claim_revision"],
                expected_board_revision=payload["revision"], now=NOW, home=self.home)
        self.assertEqual(self.authority(), unchanged)

    def test_read_and_failed_claim_leave_v1_bytes_and_journal_unchanged(self):
        repo, plan = self.seed()
        before = self.authority()
        self.assertEqual(board_api.ensure(home=self.home)["schema"], board_api.V1_SCHEMA)
        self.assertEqual(board_api.snapshot(home=self.home)["schema"], board_api.V1_SCHEMA)
        with self.assertRaisesRegex(board_api.BoardError, "explicit repository"):
            board_api.claim(plan, "~aa11", "A", project="shadow", priority=1, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)
        original_commit = board_api._commit
        def fail_after_commit(root, message):
            original_commit(root, message)
            if message == "shadow board: claim ~aa11":
                raise board_api.BoardError("injected migration journal failure")
        with mock.patch.object(board_api, "_commit", side_effect=fail_after_commit):
            with self.assertRaisesRegex(board_api.BoardError, "injected migration"):
                board_api.claim(plan, "~aa11", "A", project="shadow", priority=1,
                                 repo=repo, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)

    def test_host_cannot_implicitly_promote_an_unbound_read_only_claim(self):
        repo, plan = self.seed()
        result = board_api.claim(plan, "~aa11", "A", project="shadow", priority=1,
                                 access="read_only", now=NOW, home=self.home)
        claim = result["claim"]
        context = {key: claim[key] for key in ("entity", "row", "owner", "claim_revision")}
        context["board_revision"] = result["payload"]["revision"]
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "source-bound"):
            board_api.authorize_host_attempt(context=context, repo=repo, write_scope=["a"],
                                             now=NOW, home=self.home, authority_proposal=False)
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
        legacy_scope = copy.deepcopy(valid)
        legacy_scope["claims"][0].update({
            "claim_revision": 1,
            "access": "unscoped",
            "repository_binding": None,
            "write_scope": ["scripts"],
        })
        cases.append(legacy_scope)

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
        migrated_unknown = copy.deepcopy(unscoped)
        migrated_unknown["claims"][0].update({
            "access": "unscoped",
            "repository_binding": None,
            "write_scope": [],
        })
        for payload in (unscoped, read_only, write, classified_legacy, migrated_unknown):
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
        git(repo, "config", "user.name", "Test")
        git(repo, "config", "user.email", "test@example.test")
        git(repo, "commit", "--allow-empty", "-m", "fixture")
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
            plan = self.home / str(index) / "PLAN.md"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("# Plan\n\n## Tasks\n\n- [pending] Task ~aa11 | proof: cmd true\n", encoding="utf-8")
            payload["entities"].append({"id": entity, "project": "shadow",
                "plan": str(plan), "resume": "~aa11"})
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
        clean_git_env = dict(os.environ)
        for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            clean_git_env.pop(key, None)
        clean_git_env.update({
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "user.useConfigOnly",
            "GIT_CONFIG_VALUE_0": "true",
        })
        with mock.patch.dict(os.environ, clean_git_env, clear=True):
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

    def test_fresh_source_claim_without_repository_still_refuses(self):
        _, plan = self.seed()
        for access, scope in (("unscoped", []), ("write", ["a"])):
            with self.subTest(access=access):
                before = self.authority()
                with self.assertRaisesRegex(board_api.BoardError, "explicit repository"):
                    board_api.claim(plan, "~aa11", "A", project="shadow", priority=3,
                                     access=access, write_scope=scope, now=NOW, home=self.home)
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

    def test_native_path_alias_claims_are_held_without_rewriting_scope(self):
        repo, plan = self.seed()
        (repo / "Assets").mkdir()
        (repo / "Caf\u00e9").mkdir()
        original = ["Assets/work", "Caf\u00e9/work"]
        aliases = ["Cafe\u0301/work", "assets/work"]
        first = self.take(repo, plan, "~aa11", "A", scope=original)
        second = self.take(repo, plan, "~bb22", "B", scope=aliases)
        self.assertEqual(first["claim"]["write_scope"], original)
        self.assertEqual(second["claim"]["write_scope"], aliases)
        huddle = second["payload"]["huddles"][0]
        self.assertEqual(huddle["holds"], [board_api._claim_ref(second["claim"])])
        self.assertFalse(board_api._scope_subset(aliases, original))

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


class HuddleRecoveryTests(HuddleTestCase):
    request = HuddleBidTests.request
    submit = HuddleBidTests.submit

    def test_migrated_revision_zero_can_return_its_original_remote_lease(self):
        repo, plan = HuddleClaimCreationTests.seed(self)
        bare = self.home / "legacy-upstream.git"
        git(repo, "init", "--bare", str(bare))
        git(repo, "remote", "add", "origin", "https://github.com/example/legacy-fixture.git")
        git(repo, "push", str(bare), "HEAD:main")
        token, _ = board_api.committed_plan_snapshot(plan)
        remote = board_api._remote_claim
        binding = remote.UpstreamBinding(
            remote.RemoteEligibility.REMOTE, endpoint=str(bare),
            public_identity="github.com/example/legacy-fixture",
            merge_refs=frozenset({"refs/heads/main"}),
        )
        entity = board_api.entity_id(plan)
        lease = {"claimed_at": "2026-09-05T00:00:00Z", "return_by": "2026-09-06T00:00:00Z", "recovery": board_api.RECOVERY_ACTION}
        with mock.patch.object(remote, "upstream_binding", return_value=binding):
            acquired = remote.acquire(
                repo, entity=entity, row="~aa11", owner="legacy-seat",
                project="shadow", plan_token=token, **lease,
            )
            self.assertEqual(acquired["status"], "acquired")
            self.assertNotIn("claim_revision", acquired["claim"])
            released = remote.transition(
                repo, entity=entity, row="~aa11", owner="legacy-seat",
                project="shadow", plan_token=token, claim=lease | {"claim_revision": 0},
                state="released", reason="handback",
            )
            self.assertEqual(released["status"], "acquired")
            self.assertEqual(released["claim"], acquired["claim"])
            tip = remote._remote_tip(repo, endpoint=str(bare), ref=acquired["ref"],
                entity=entity, row="~aa11", project="shadow", plan_token=token)
            self.assertEqual(tip[1]["state"], "released")
            self.assertNotIn("claim_revision", tip[1]["claim"])

    def test_native_acquire_and_transition_preserve_exact_claim_revision(self):
        repo, plan = HuddleClaimCreationTests.seed(self)
        bare = self.home / "upstream.git"
        git(repo, "init", "--bare", str(bare))
        git(repo, "remote", "add", "origin", "https://github.com/example/huddle-fixture.git")
        git(repo, "push", str(bare), "HEAD:main")
        claim = HuddleClaimCreationTests.take(self, repo, plan, "~aa11", "A")["claim"]
        token, _ = board_api.committed_plan_snapshot(plan)
        remote = board_api._remote_claim
        binding = remote.UpstreamBinding(remote.RemoteEligibility.REMOTE, endpoint=str(bare),
            public_identity="github.com/example/huddle-fixture", merge_refs=frozenset({"refs/heads/main"}))
        # Only the locator is substituted; native Git publication and readback run.
        with mock.patch.object(remote, "upstream_binding", return_value=binding):
            acquired = remote.acquire(repo, entity=claim["entity"], row=claim["row"], owner="A",
                project="shadow", plan_token=token, claimed_at=claim["claimed_at"],
                return_by=claim["return_by"], recovery=claim["recovery"],
                claim_revision=claim["claim_revision"])
            self.assertEqual(acquired["status"], "acquired")
            self.assertEqual(acquired["claim"]["claim_revision"], claim["claim_revision"])
            args = dict(repo=repo, entity=claim["entity"], row=claim["row"], owner="A",
                        project="shadow", plan_token=token, state="released", reason="handback")
            wrong = remote.transition(**args, claim=claim | {"claim_revision": claim["claim_revision"] + 1})
            self.assertEqual(wrong["status"], "lost")
            released = remote.transition(**args, claim=claim)
            self.assertEqual(released["status"], "acquired")
            self.assertEqual(released["claim"], acquired["claim"])
            tip = remote._remote_tip(repo, endpoint=str(bare), ref=acquired["ref"],
                entity=claim["entity"], row=claim["row"], project="shadow", plan_token=token)
            self.assertEqual(tip[1]["state"], "released")
            self.assertEqual(tip[1]["claim"], acquired["claim"])

    def test_remote_handoff_checks_every_row_in_a_shared_plan(self):
        repo, plan = HuddleClaimCreationTests.seed(self)
        first = HuddleClaimCreationTests.take(self, repo, plan, "~aa11", "A")["claim"]
        second = HuddleClaimCreationTests.take(self, repo, plan, "~bb22", "B")["claim"]
        payload = board_api.snapshot(home=self.home)
        refs = [board_api._claim_ref(first), board_api._claim_ref(second)]
        content = plan.read_text()
        for invalid in (content.replace("[pending] second", "[completed] second"),
                        "\n".join(line for line in content.splitlines() if "~bb22" not in line)):
            with self.subTest(content=invalid):
                plan.write_text(invalid)
                before = self.authority()
                with self.assertRaises(board_api.BoardError):
                    board_api._remote_handoff_plans(payload, refs, NOW)
                self.assertEqual(self.authority(), before)

    def test_real_git_handback_reclaim_fresh_acceptance_and_remote_handoff(self):
        repo, plan = HuddleClaimCreationTests.seed(self)
        bare = self.home / "upstream.git"
        git(repo, "init", "--bare", str(bare))
        canonical = "https://github.com/example/huddle-fixture.git"
        git(repo, "remote", "add", "origin", canonical)
        git(repo, "push", str(bare), "HEAD:main")
        git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
        self.a = HuddleClaimCreationTests.take(self, repo, plan, "~aa11", "A")["claim"]
        self.b = HuddleClaimCreationTests.take(self, repo, plan, "~bb22", "B")["claim"]
        self.huddle = board_api.snapshot(home=self.home)["huddles"][0]
        source = board_api._claim_ref(self.a)
        target = board_api._claim_ref(self.b)
        remote = board_api._remote_claim
        token, _ = board_api.committed_plan_snapshot(plan)
        reference = remote.claim_ref(source["entity"], source["row"])
        initial = remote._receipt(status="acquired", ref=reference, entity=source["entity"], row=source["row"],
            owner="A", project="shadow", plan_token=token, claimed_at=self.a["claimed_at"],
            return_by=self.a["return_by"], recovery=self.a["recovery"], state="acquired",
            reason="acquire", winner="A", failure=None, claim_revision=source["claim_revision"])
        version = remote._commit_receipt(repo, initial, self.a["claimed_at"])
        self.assertIsNotNone(version)
        self.assertTrue(remote._push(repo, str(bare), reference, version, None))
        self.submit(role="yield", reason="owner_authorized_handoff", target=target)
        self.submit(self.b, reason="owner_authorized_handoff")
        old_huddle_id = self.huddle["id"]
        old_bid = board_api.bid_receipt(self.huddle["id"], target, 1, home=self.home)
        # A changed target lease invalidates the old immutable acceptance.
        with board_api._transaction(self.home) as (root, path, payload):
            changed = next(c for c in payload["claims"] if board_api._claim_ref(c) == target)
            changed["return_by"] = "2026-09-05T17:00:00Z"
            self.b = copy.deepcopy(changed)
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: changed target lease", now=NOW)
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "acceptance"):
            board_api.begin_huddle_handoff(huddle_id=self.huddle["id"], generation=self.huddle["generation"],
                source_claim=source, successor_claim={**source, "owner": "B"}, target_prior_claim=target,
                remote_ref=reference, expected_remote_version=version, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)
        returned, changed = board_api.release(plan, "~bb22", owner="B", reason="handback",
                                              expected_claim=self.b, now=NOW, home=self.home)
        self.assertTrue(changed)
        self.assertEqual(returned["huddles"][0]["state"], "resolved")
        self.assertEqual(returned["claims"], [self.a])
        self.b = HuddleClaimCreationTests.take(self, repo, plan, "~bb22", "B")["claim"]
        self.huddle = next(h for h in board_api.snapshot(home=self.home)["huddles"] if h["state"] != "resolved")
        fresh_target = board_api._claim_ref(self.b)
        self.assertNotEqual(fresh_target["claim_revision"], target["claim_revision"])
        self.assertNotEqual(self.huddle["id"], old_huddle_id)
        self.submit(role="yield", reason="owner_authorized_handoff", target=fresh_target)
        stale_request = self.request(self.b, reason="owner_authorized_handoff")
        stale_request["evidence"] = old_bid["evidence"]
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "acceptance"):
            board_api.submit_huddle_bid(**stale_request, now=NOW, home=self.home)
        self.assertEqual(self.authority(), before)
        self.submit(self.b, reason="owner_authorized_handoff")
        fresh_bid = board_api.bid_receipt(self.huddle["id"], fresh_target, 1, home=self.home)
        self.assertNotEqual(fresh_bid["evidence"], old_bid["evidence"])
        successor = {**source, "owner": "B"}
        pending = board_api.begin_huddle_handoff(huddle_id=self.huddle["id"], generation=self.huddle["generation"],
            source_claim=source, successor_claim=successor, target_prior_claim=fresh_target,
            remote_ref=reference, expected_remote_version=version, now=NOW, home=self.home)
        # Substitute only the test transport locator. Claim binding, board
        # transitions, Git CAS and authenticated double readback stay real;
        # this fixture is not a live-network authorization receipt.
        fixture_transport = remote.UpstreamBinding(remote.RemoteEligibility.REMOTE,
            endpoint=str(bare), public_identity="github.com/example/huddle-fixture", merge_refs=frozenset({"refs/heads/main"}))
        with mock.patch.object(remote, "upstream_binding", return_value=fixture_transport):
            readback = remote.handoff_huddle_claim(repo, expected_remote_version=version,
                source_claim=self.a, successor_claim={**self.a, "owner": "B"}, project="shadow", plan_token=token)
        self.assertEqual(readback.outcome, "successor")
        final = board_api.finalize_huddle_handoff(huddle_id=self.huddle["id"],
            generation=next(h for h in pending.payload["huddles"] if h["id"] == self.huddle["id"])["generation"],
            remote_receipt=readback, now=NOW, home=self.home)
        h = next(h for h in final.payload["huddles"] if h["id"] == self.huddle["id"])
        self.assertEqual(h["resolution"]["write_owners"], [successor])
        self.assertEqual(h["holds"], [fresh_target])
        self.assertEqual(next(c for c in final.payload["claims"] if c["row"] == "~aa11"), {**self.a, "owner": "B"})
        self.assertEqual(board_api.bid_receipt(h["id"], fresh_target, 1, home=self.home), fresh_bid)


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

    def seed_unknown(self, *, migrated=True):
        repo, plan = HuddleClaimCreationTests.seed(self)
        legacy = self.v1_board()
        identity = board_api.entity_id(plan)
        legacy["entities"][0].update(id=identity, plan=str(plan))
        legacy["claims"][0]["entity"] = identity
        payload = board_api.migrate_v1_to_v2(legacy) if migrated else legacy
        self.seed_v2(payload)
        return repo, plan, payload["claims"][0]

    def adopt(self, claim=None, *, now=NOW + timedelta(hours=9), owner="Successor", **changes):
        claim = claim or self.a
        args = dict(project="shadow", priority=3, repo=self.repo,
                    now=now, home=self.home, adopt_expired=True)
        return board_api.claim(self.plan, claim["row"], owner, **(args | changes))

    def adopt_unknown(self, plan, claim, *, now, owner, **changes):
        options = dict(access="unscoped", write_scope=[])
        options.update(changes)
        return board_api.claim(
            plan, claim["row"], owner, project="shadow", priority=3,
            now=now, home=self.home, adopt_expired=True,
            **options)

    def test_initial_migrated_unknown_adoption_preserves_unscoped_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            _, plan, legacy = self.seed_unknown()
            result = board_api.claim(
                plan, legacy["row"], "Successor", project="shadow", priority=3,
                now=NOW + timedelta(hours=3), home=self.home, adopt_expired=True,
                access="unscoped", write_scope=[])
            successor = result["claim"]
            self.assertGreater(successor["claim_revision"], legacy["claim_revision"])
            self.assertEqual(successor["access"], "unscoped")
            self.assertEqual(successor["write_scope"], [])
            self.assertIsNone(successor["repository_binding"])

    def test_repeated_proof_first_stale_unknown_adoption_preserves_declaration(self):
        for migrated in (False, True):
            with self.subTest(migrated=migrated), tempfile.TemporaryDirectory() as tmp:
                self.home = Path(tmp)
                _, plan, legacy = self.seed_unknown(migrated=migrated)
                first_result = self.adopt_unknown(
                    plan, legacy, now=NOW + timedelta(hours=3), owner="Successor")
                first = first_result["claim"]
                second_result = self.adopt_unknown(
                    plan, first, now=NOW + timedelta(hours=12), owner="NewOwner")
                second = second_result["claim"]
                self.assertGreater(first["claim_revision"], 0)
                self.assertGreater(second["claim_revision"], first["claim_revision"])
                for claim in (first, second):
                    self.assertEqual(claim["access"], "unscoped")
                    self.assertEqual(claim["write_scope"], [])
                    self.assertIsNone(claim["repository_binding"])
                self.assertEqual(second_result["payload"]["claims"], [second])
                self.assertIs(board_api._validate(second_result["payload"]), second_result["payload"])

    def test_unknown_adoption_keeps_global_other_writer_fence(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            repo, plan, legacy = self.seed_unknown()
            with board_api._transaction(self.home) as (root, path, payload):
                other = copy.deepcopy(payload["claims"][0])
                other.update(row="~bb22", owner="Other")
                payload["claims"].append(other)
                payload["revision"] += 1
                board_api._write_and_commit(root, path, payload, "test: second unknown claim", now=NOW)

            first = self.adopt_unknown(
                plan, legacy, now=NOW + timedelta(hours=3), owner="Successor")["claim"]

            def assert_other_writer_blocked(now):
                current = board_api.snapshot(home=self.home)
                before = self.authority()
                with self.assertRaisesRegex(board_api.BoardError, "legacy_binding_unknown"):
                    board_api.preflight_access(
                        entity=other["entity"], row=other["row"], owner=other["owner"],
                        repo=repo, access="write", write_scope=["a"],
                        expected_claim_revision=other["claim_revision"],
                        expected_board_revision=current["revision"], now=now, home=self.home)
                self.assertEqual(self.authority(), before)

            assert_other_writer_blocked(NOW + timedelta(hours=3))
            self.adopt_unknown(
                plan, first, now=NOW + timedelta(hours=12), owner="NewOwner")
            assert_other_writer_blocked(NOW + timedelta(hours=12))

    def test_unknown_adoption_requires_owner_preflight_before_source_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            repo, plan, legacy = self.seed_unknown()
            result = self.adopt_unknown(
                plan, legacy, now=NOW + timedelta(hours=3), owner="Successor")
            successor = result["claim"]
            context = {key: successor[key] for key in ("entity", "row", "owner", "claim_revision")}
            context["board_revision"] = result["payload"]["revision"]
            before = self.authority()
            with self.assertRaisesRegex(board_api.BoardError, "source-bound"):
                board_api.authorize_host_attempt(
                    context=context, repo=repo, write_scope=["a"],
                    authority_proposal=False, now=NOW + timedelta(hours=3), home=self.home)
            self.assertEqual(self.authority(), before)
            with self.assertRaises(board_api.AlreadyClaimed):
                board_api.preflight_access(
                    entity=successor["entity"], row=successor["row"], owner="Other",
                    repo=repo, access="write", write_scope=["a"],
                    expected_claim_revision=successor["claim_revision"],
                    expected_board_revision=context["board_revision"],
                    now=NOW + timedelta(hours=3), home=self.home)
            self.assertEqual(self.authority(), before)
            with self.assertRaisesRegex(board_api.BoardError, "preflight claim instance changed"):
                board_api.preflight_access(
                    entity=successor["entity"], row=successor["row"], owner=successor["owner"],
                    repo=repo, access="write", write_scope=["a"],
                    expected_claim_revision=successor["claim_revision"] - 1,
                    expected_board_revision=context["board_revision"],
                    now=NOW + timedelta(hours=3), home=self.home)
            self.assertEqual(self.authority(), before)
            with self.assertRaisesRegex(board_api.BoardError, "preflight board revision changed"):
                board_api.preflight_access(
                    entity=successor["entity"], row=successor["row"], owner=successor["owner"],
                    repo=repo, access="write", write_scope=["a"],
                    expected_claim_revision=successor["claim_revision"],
                    expected_board_revision=context["board_revision"] - 1,
                    now=NOW + timedelta(hours=3), home=self.home)
            self.assertEqual(self.authority(), before)
            classified = board_api.preflight_access(
                entity=successor["entity"], row=successor["row"], owner=successor["owner"],
                repo=repo, access="write", write_scope=["a"],
                expected_claim_revision=successor["claim_revision"],
                expected_board_revision=context["board_revision"], now=NOW + timedelta(hours=3),
                home=self.home)
            current = classified.payload["claims"][0]
            self.assertEqual(current["access"], "write")
            self.assertEqual(current["repository_binding"], board_api.repository_binding(repo))

    def test_unknown_adoption_plan_cas_restores_exact_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            _, plan, legacy = self.seed_unknown()
            before = self.authority()
            plan_before = plan.read_bytes()
            original = board_api._write_and_commit

            def race(*args, **kwargs):
                plan.write_bytes(plan_before + b"\nConcurrent canonical edit\n")
                return original(*args, **kwargs)

            with mock.patch.object(board_api, "_write_and_commit", side_effect=race):
                with self.assertRaisesRegex(board_api.BoardError, "canonical plan changed"):
                    self.adopt_unknown(plan, legacy, now=NOW + timedelta(hours=3), owner="Successor")
            self.assertEqual(self.authority(), before)
            self.assertEqual(board_api._journal_head(self.home / ".shadow"), before[1])
            self.assertEqual(plan.read_bytes(), plan_before + b"\nConcurrent canonical edit\n")

    def test_unknown_adoption_rolls_back_on_journal_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            _, plan, legacy = self.seed_unknown()
            before = self.authority()
            plan_before = plan.read_bytes()
            with mock.patch.object(board_api, "_commit", side_effect=board_api.BoardError("injected")):
                with self.assertRaisesRegex(board_api.BoardError, "injected"):
                    self.adopt_unknown(plan, legacy, now=NOW + timedelta(hours=3), owner="Successor")
            self.assertEqual(self.authority(), before)
            self.assertEqual(plan.read_bytes(), plan_before)

    def test_unknown_adoption_preserves_live_lease_revision_and_scope_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.home = Path(tmp)
            _, plan, legacy = self.seed_unknown()
            current = board_api.snapshot(home=self.home)
            cases = (
                (dict(now=NOW + timedelta(minutes=30)), "claimed by Codex"),
                (dict(now=NOW + timedelta(hours=3), write_scope=["a"]), "preserve access"),
                (dict(now=NOW + timedelta(hours=3), expected_board_revision=current["revision"] - 1),
                 "board revision changed"),
            )
            for changes, message in cases:
                with self.subTest(changes=changes):
                    before = self.authority()
                    with self.assertRaisesRegex(board_api.BoardError, message):
                        self.adopt_unknown(plan, legacy, owner="Successor", **changes)
                    self.assertEqual(self.authority(), before)

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

    def test_settled_selected_writer_adoption_preserves_resolution_and_maps_terminal(self):
        self.submit()
        self.submit(self.b, role="stand_down", reason="duplicate_intent")
        settled = self.settle().payload["huddles"][0]
        result = self.adopt(self.a)
        h = result["payload"]["huddles"][0]
        self.assertEqual(h["state"], "awaiting_compliance")
        self.assertEqual(h["resolution"], settled["resolution"])
        self.assertEqual(h["bids"], settled["bids"])
        self.assertEqual(h["replacements"], [{"original": board_api._claim_ref(self.a),
                                                "current": board_api._claim_ref(result["claim"])}])
        self.assertEqual(h["holds"], [board_api._claim_ref(self.b)])

    def test_mapped_pending_return_remains_held_at_host_door(self):
        self.submit()
        self.submit(self.b, role="stand_down", reason="duplicate_intent")
        self.settle()
        replacement = self.adopt(self.b)
        claim = replacement["claim"]
        context = {key: claim[key] for key in ("entity", "row", "owner", "claim_revision")}
        context["board_revision"] = replacement["payload"]["revision"]
        before = self.authority()
        with self.assertRaisesRegex(board_api.BoardError, "held"):
            board_api.authorize_host_attempt(context=context, repo=self.repo,
                write_scope=claim["write_scope"], authority_proposal=False,
                now=NOW + timedelta(hours=9), home=self.home)
        self.assertEqual(self.authority(), before)

    def test_repeated_held_adoption_preserves_disposition_and_returns_current_only(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        settled = self.settle().payload["huddles"][0]
        first = self.adopt(self.b)["claim"]
        self.plan.write_text(self.plan.read_text().replace("[pending] second", "[blocked] second")
            + "\n## Deferred\n- ~bb22 | overlap owned by A | wake: A completes shared work\n")
        result = self.adopt(first, now=NOW + timedelta(hours=18), owner="D")
        terminal, h = result["claim"], result["payload"]["huddles"][0]
        self.assertEqual(h["replacements"], [{"original": board_api._claim_ref(self.b),
                                             "current": board_api._claim_ref(terminal)}])
        for field in ("claims", "edges", "holds", "bids", "resolution", "compliance", "round", "reply_by"):
            self.assertEqual(h[field], settled[field], field)
        self.assertEqual(h["generation"], settled["generation"] + 2)
        before = self.authority()
        for stale in (self.b, first):
            with self.subTest(owner=stale["owner"]):
                with self.assertRaises(board_api.BoardError):
                    board_api.release(self.plan, stale["row"], owner=stale["owner"], reason="blocked",
                        expected_claim=stale, now=NOW + timedelta(hours=18), home=self.home)
                context = {key: stale[key] for key in ("entity", "row", "owner", "claim_revision")}
                context["board_revision"] = result["payload"]["revision"]
                with self.assertRaises(board_api.BoardError):
                    board_api.authorize_host_attempt(context=context, repo=self.repo,
                        write_scope=stale["write_scope"], authority_proposal=False,
                        now=NOW + timedelta(hours=18), home=self.home)
                self.assertEqual(self.authority(), before)
        returned, changed = board_api.release(self.plan, terminal["row"], owner="D", reason="blocked",
            expected_claim=terminal, now=NOW + timedelta(hours=18), home=self.home)
        self.assertTrue(changed)
        closed = returned["huddles"][0]
        self.assertEqual(closed["state"], "resolved")
        self.assertEqual(closed["resolution"], settled["resolution"])
        self.assertEqual(closed["replacements"], h["replacements"])
        self.assertEqual(closed["compliance"][0]["claim"], board_api._claim_ref(self.b))
        self.assertEqual(closed["compliance"][0]["status"], "satisfied")
        self.assertEqual(closed["compliance"][0]["completion"],
                         dict(kind="return", board_revision=returned["revision"], receipt="self"))
        self.assertEqual(returned["claims"], [self.a])
        fresh = self.adopt(self.a, now=NOW + timedelta(hours=18), owner="Fresh")
        self.assertEqual(fresh["payload"]["huddles"], returned["huddles"])
        self.assertEqual(board_api._claim_huddles(fresh["payload"], fresh["claim"]), [])

    def test_mapped_stale_proof_closure_preserves_remaining_compliance(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        settled = self.settle().payload["huddles"][0]
        replacements = [self.adopt(self.a)["claim"], self.adopt(self.b)["claim"]]
        for claim, word, expected_state in ((replacements[0], "first", "awaiting_compliance"),
                                             (replacements[1], "second", "resolved")):
            self.plan.write_text(self.plan.read_text().replace(f"[pending] {word}", f"[completed] {word}")
                + f"\n- 2026-09-05T10:00:00Z {claim['row']} PROOF read result -> valid\n")
            git(self.repo, "add", "PLAN.md")
            git(self.repo, "commit", "-qm", "record actual canonical completion")
            self.assertEqual(board_api.release_stranded_completed_claims(
                now=NOW + timedelta(hours=18), home=self.home), 1)
            payload = board_api.snapshot(home=self.home)
            h = payload["huddles"][0]
            self.assertEqual(h["state"], expected_state)
            self.assertEqual(h["resolution"], settled["resolution"])
            self.assertEqual(len(h["replacements"]), 2)
        self.assertEqual(payload["claims"], [])
        self.assertEqual(h["compliance"][0]["completion"]["kind"], "proof_first_stale_recovery")

    def test_local_handoff_successor_repeated_adoption_preserves_yield_evidence(self):
        local = self.home / ".shadow" / "plans" / "handoff" / "PLAN.md"
        local.parent.mkdir(parents=True)
        local.write_bytes(self.plan.read_bytes())
        self.plan = local
        self.seed_v2(self.v2_board(with_claim=False))
        self.a = self.take(self.repo, local, "~aa11", "A")["claim"]
        self.b = self.take(self.repo, local, "~bb22", "B")["claim"]
        self.huddle = board_api.snapshot(home=self.home)["huddles"][0]
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        settled = self.settle().payload
        successor = next(c for c in settled["claims"] if c["row"] == self.a["row"])
        first = self.adopt(successor, owner="C")["claim"]
        last = self.adopt(first, now=NOW + timedelta(hours=18), owner="D")
        h = last["payload"]["huddles"][0]
        for field in ("claims", "edges", "holds", "bids", "resolution", "compliance"):
            self.assertEqual(h[field], settled["huddles"][0][field], field)
        self.assertEqual(h["replacements"], [{"original": board_api._claim_ref(successor),
                                             "current": board_api._claim_ref(last["claim"])}])
        malformed = copy.deepcopy(last["payload"])
        malformed["claims"] = [c for c in malformed["claims"] if c["row"] != self.a["row"]]
        malformed["claims"].append(copy.deepcopy(self.a))
        with self.assertRaisesRegex(board_api.BoardError, "handoff source"):
            board_api._validate(malformed)
        malformed = copy.deepcopy(last["payload"])
        malformed["huddles"][0]["replacements"][0]["original"] = board_api._claim_ref(self.a)
        with self.assertRaisesRegex(board_api.BoardError, "operating role"):
            board_api._validate(malformed)
        malformed = copy.deepcopy(last["payload"])
        next(c for c in malformed["claims"] if c["row"] == self.a["row"])["write_scope"] = ["b"]
        with self.assertRaisesRegex(board_api.BoardError, "edges"):
            board_api._validate(malformed)
        before = self.authority()
        for stale in (self.a, successor, first):
            with self.assertRaises(board_api.BoardError):
                board_api.check_huddle_release(local, stale, reason="completed", home=self.home)
            self.assertEqual(self.authority(), before)
        local.write_text(local.read_text().replace("[pending] first", "[completed] first")
            + "\n- 2026-09-05T19:00:00Z ~aa11 PROOF read result -> valid\n")
        self.assertEqual(board_api.release_stranded_completed_claims(
            now=NOW + timedelta(hours=27), home=self.home), 1)
        recovered = board_api.snapshot(home=self.home)["huddles"][0]
        self.assertEqual(recovered["state"], "awaiting_compliance")
        self.assertEqual(recovered["holds"], [board_api._claim_ref(self.b)])
        self.assertEqual(recovered["resolution"], h["resolution"])

    def test_replacement_schema_rejects_unbound_alias_and_stale_terminal(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        self.settle()
        baseline = self.adopt(self.b)["payload"]
        board_api._validate(baseline)
        for defect in ("missing", "foreign_original", "cross_row", "duplicate", "nonmonotonic",
                       "chain", "old_live", "satisfied_live", "scope_drift", "owner_time", "predates_settlement"):
            malformed = copy.deepcopy(baseline)
            h = malformed["huddles"][0]
            mapping = h["replacements"][0]
            current = next(c for c in malformed["claims"] if c["row"] == self.b["row"])
            if defect == "missing":
                del h["replacements"]
            elif defect == "foreign_original":
                mapping["original"]["owner"] = "NotParticipant"
            elif defect == "cross_row":
                mapping["current"]["row"] = "~cc33"
            elif defect == "duplicate":
                h["replacements"].append(copy.deepcopy(mapping))
            elif defect == "nonmonotonic":
                mapping["current"]["claim_revision"] = mapping["original"]["claim_revision"]
            elif defect == "chain":
                h["replacements"].append(dict(original=copy.deepcopy(mapping["current"]),
                    current={**mapping["current"], "owner": "D", "claim_revision": malformed["revision"] + 1}))
                malformed["revision"] += 1
            elif defect == "old_live":
                malformed["claims"].append(copy.deepcopy(self.b))
            elif defect == "satisfied_live":
                malformed["revision"] += 1
                h["compliance"][0].update(status="satisfied", completion=dict(kind="return",
                    board_revision=malformed["revision"], receipt="self"))
                h.update(state="resolved", holds=[], resolved_at="2026-09-05T02:00:00Z",
                         retain_until="2026-09-06T02:00:00Z")
            elif defect == "scope_drift":
                current["write_scope"] = ["b"]
            elif defect == "predates_settlement":
                current["claim_revision"] = mapping["current"]["claim_revision"] = h["resolution"]["settled_revision"]
            else:
                mapping["current"]["claimed_at"] = "2026-09-04T15:00:00Z"
            with self.subTest(defect=defect), self.assertRaises(board_api.BoardError):
                board_api._validate(malformed)

    def test_settled_adoption_rechecks_plan_and_rolls_back_journal_failure(self):
        self.submit()
        self.submit(self.b, role="stand_down")
        self.settle()
        before = self.authority()
        with mock.patch.object(board_api, "_commit", side_effect=board_api.BoardError("journal refused")):
            with self.assertRaisesRegex(board_api.BoardError, "journal refused"):
                self.adopt(self.b)
        self.assertEqual(self.authority(), before)
        original = board_api._write_and_commit
        def change(*args, **kwargs):
            self.plan.write_text(self.plan.read_text() + "\nConcurrent canonical edit\n")
            return original(*args, **kwargs)
        with mock.patch.object(board_api, "_write_and_commit", side_effect=change):
            with self.assertRaisesRegex(board_api.BoardError, "canonical plan changed"):
                self.adopt(self.b)
        self.assertEqual(self.authority(), before)

    def test_remote_pending_refuses_adoption_and_any_terminal_mapping(self):
        self.submit(role="yield", reason="owner_authorized_handoff", target=board_api._claim_ref(self.b))
        self.submit(self.b, reason="owner_authorized_handoff")
        with board_api._transaction(self.home) as (root, path, payload):
            h = payload["huddles"][0]
            source, prior = board_api._claim_ref(self.a), board_api._claim_ref(self.b)
            successor = {**source, "owner": "B"}
            h.update(state="remote_pending", reply_by=None,
                holds=sorted([source, successor, prior], key=board_api._claim_rank),
                remote_transition=dict(source_claim=source, successor_claim=successor,
                    target_prior_claim=prior, target_prior_action="return_required",
                    remote_ref=board_api._remote_claim.claim_ref(source["entity"], source["row"]),
                    expected_remote_version="e" * 40, readback="not_attempted", attempt_receipt=None))
            payload["revision"] += 1
            board_api._write_and_commit(root, path, payload, "test: pending remote CAS", now=NOW)
        before = self.authority()
        for participant in (self.a, self.b):
            with self.assertRaises(board_api.BoardError):
                self.adopt(participant)
            self.assertEqual(self.authority(), before)
        malformed = board_api.snapshot(home=self.home)
        malformed["huddles"][0]["replacements"] = [dict(original=source,
            current={**source, "owner": "C", "claim_revision": malformed["revision"]})]
        with self.assertRaises(board_api.BoardError):
            board_api._validate(malformed)

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
            holds=[b], bids=[], resolution=None, compliance=[], remote_transition=None, replacements=[],
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
