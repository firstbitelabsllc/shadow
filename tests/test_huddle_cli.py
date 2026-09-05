from __future__ import annotations

import json
import contextlib
import fcntl
import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.test_huddle import HuddleGraphTests, HuddleTestCase, NOW
from tests.proc_fixture import configure_public_fixture_ssh_remote, git

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board
import shadow_remote_claim as remote

import importlib.util
_CLI_SPEC = importlib.util.spec_from_file_location("shadow_huddle_cli", ROOT / "scripts" / "shadow-huddle.py")
cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(cli)


class HuddleCliTests(HuddleTestCase):
    def run_cli(self, *args: str, stdin: bytes = b"") -> subprocess.CompletedProcess[str]:
        env = os.environ | {"HOME": str(self.home), "SHADOW_ROOT": str(ROOT)}
        return subprocess.run([str(ROOT / "bin" / "shadow"), "huddle", *args], input=stdin,
                              capture_output=True, text=False, env=env, cwd=ROOT, timeout=20)

    def seed_open(self):
        a, b = HuddleGraphTests.seed(self, [["a"], ["a"]])
        opened = HuddleGraphTests.open(self, a, [b]).payload["huddles"][0]
        return a, b, opened

    def seed_remote_handoff(self):
        """Build one isolated tracked checkout and real SSH-backed claim ref."""
        repo = self.home / "checkout"
        bare = self.home / "remote.git"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "fixture@example.invalid")
        git(repo, "config", "user.name", "Fixture")
        (repo / "a").mkdir()
        (repo / "b").mkdir()
        (repo / "a" / "PLAN.md").write_text(
            "# A\n\n## Tasks\n\n- [pending] A ~aa11 | proof: cmd true\n", encoding="utf-8")
        (repo / "b" / "PLAN.md").write_text(
            "# B\n\n## Tasks\n\n- [pending] B ~bb22 | proof: cmd true\n", encoding="utf-8")
        git(repo, "add", "a/PLAN.md", "b/PLAN.md")
        git(repo, "commit", "-qm", "fixture")
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True,
                       capture_output=True, text=True)
        git(repo, "remote", "add", "origin", "ssh://fixture@fixture.invalid/project.git")
        endpoint = configure_public_fixture_ssh_remote(repo, bare)
        git(repo, "push", "-qu", "origin", "HEAD:main")
        git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
        git(repo, "branch", "--set-upstream-to=origin/main", "main")
        binding = board.repository_binding(repo)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        claimed_at = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return_by = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        e1 = board.entity_id(repo / "a" / "PLAN.md")
        e2 = board.entity_id(repo / "b" / "PLAN.md")
        payload = board.migrate_v1_to_v2({
            "schema": board.V1_SCHEMA, "revision": 2,
            "projects": [{"id": "shadow", "priority": 1}],
            "entities": [
                {"id": e1, "project": "shadow", "plan": str(repo / "a" / "PLAN.md"), "resume": "~aa11"},
                {"id": e2, "project": "shadow", "plan": str(repo / "b" / "PLAN.md"), "resume": "~bb22"},
            ], "claims": [],
        })
        payload["claims"] = [
            {"entity": e1, "row": "~aa11", "owner": "A", "claimed_at": claimed_at,
             "return_by": return_by, "recovery": board.RECOVERY_ACTION, "claim_revision": 1,
             "access": "write", "write_scope": ["a"], "repository_binding": binding},
            {"entity": e2, "row": "~bb22", "owner": "B", "claimed_at": claimed_at,
             "return_by": return_by, "recovery": board.RECOVERY_ACTION, "claim_revision": 2,
             "access": "write", "write_scope": ["a"], "repository_binding": binding},
        ]
        self.seed_v2(payload)
        a, b = payload["claims"]
        opened = board.open_or_join_huddle(claim=a, overlap=[b], reason="write_scope_overlap",
                                           now=now, home=self.home)
        huddle = opened.payload["huddles"][0]
        source_ref, target_ref = board._claim_ref(a), board._claim_ref(b)
        board.submit_huddle_bid(
            huddle_id=huddle["id"], seat="A", claim=source_ref, role="yield", scope=["a"],
            reason="owner_authorized_handoff", target=target_ref, support_claim=None,
            evidence={"kind": "claim", "value": "self"}, round=1,
            expected_huddle_generation=huddle["generation"], now=now, home=self.home)
        acceptance = board.huddle_handoff_acceptance(source_ref, target_ref, home=self.home)
        huddle = board.snapshot(home=self.home)["huddles"][0]
        board.submit_huddle_bid(
            huddle_id=huddle["id"], seat="B", claim=target_ref, role="own", scope=["a"],
            reason="owner_authorized_handoff", target=None, support_claim=None,
            evidence={"kind": "claim", "value": acceptance}, round=1,
            expected_huddle_generation=huddle["generation"], now=now, home=self.home)
        token, _ = board.committed_plan_snapshot(repo / "a" / "PLAN.md", repo=repo)
        ref = remote_ref = remote.claim_ref(e1, "~aa11")
        initial = remote._receipt(
            status="acquired", ref=remote_ref, entity=e1, row="~aa11", owner="A", project="shadow",
            plan_token=token, claimed_at=claimed_at, return_by=return_by,
            recovery=board.RECOVERY_ACTION, state="acquired", reason="acquire", winner="A",
            failure=None, claim_revision=1)
        version = remote._commit_receipt(repo, initial, claimed_at)
        self.assertIsNotNone(version)
        self.assertTrue(remote._push(repo, endpoint, ref, version, None))
        return repo, bare, endpoint, now, board.snapshot(home=self.home), version

    def invoke_main(self, *args: str) -> dict:
        """Run the installed-core Python entry point against this test HOME."""
        output = io.StringIO()
        environment = {"HOME": str(self.home), "SHADOW_ROOT": str(self.home / "untrusted")}
        with mock.patch.dict(os.environ, environment, clear=False), \
             mock.patch.object(sys, "argv", ["shadow", *args]), \
             contextlib.redirect_stdout(output):
            cli.main()
        return json.loads(output.getvalue())

    def test_remote_cli_settle_uses_real_git_and_releases_board_lock(self):
        repo, _bare, _endpoint, _now, snapshot, version = self.seed_remote_handoff()
        huddle = snapshot["huddles"][0]
        source = next(claim for claim in snapshot["claims"] if claim["owner"] == "A")
        target = next(claim for claim in snapshot["claims"] if claim["owner"] == "B")
        source_ref, target_ref = board._claim_ref(source), board._claim_ref(target)
        observed = []
        original_handoff = remote.handoff_huddle_claim

        def observe_then_handoff(remote_repo, **kwargs):
            pending = board.snapshot(home=self.home)
            observed.append((pending["huddles"][0]["state"], pending["revision"]))
            lock_path = self.home / ".shadow" / board.LOCK_NAME
            with lock_path.open("a+", encoding="utf-8") as stream:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise AssertionError("board lock remained held during Git handoff") from exc
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            return original_handoff(remote_repo, **kwargs)

        with mock.patch.object(remote, "handoff_huddle_claim", side_effect=observe_then_handoff):
            result = self.invoke_main(
                "settle", "--id", huddle["id"], "--generation", str(huddle["generation"]),
                "--expect-board", str(snapshot["revision"]), "--by", "A")

        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], "remote_pending")
        final = board.snapshot(home=self.home)
        final_huddle = final["huddles"][0]
        self.assertEqual(final_huddle["state"], "awaiting_compliance")
        self.assertEqual(final_huddle["remote_transition"]["readback"], "successor")
        self.assertEqual(final_huddle["resolution"]["write_owners"], [dict(source_ref, owner="B")])
        self.assertEqual(result["board_revision"], final["revision"])
        token, _ = board.committed_plan_snapshot(repo / "a" / "PLAN.md", repo=repo)
        actual = remote.read_remote_claim_stably(
            repo, expected_remote_version=version, source_claim=source,
            successor_claim=dict(source, owner="B"), project="shadow", plan_token=token)
        self.assertEqual(actual.outcome, "successor")
        self.assertEqual(actual.ref, remote.claim_ref(source["entity"], source["row"]))

    def test_remote_cli_settle_stale_board_and_nonparticipant_are_nonmutating(self):
        _repo, _bare, _endpoint, _now, snapshot, _version = self.seed_remote_handoff()
        huddle = snapshot["huddles"][0]
        args = ("settle", "--id", huddle["id"], "--generation", str(huddle["generation"]))
        before = self.authority()
        with self.assertRaises(board.BoardError):
            self.invoke_main(*args, "--expect-board", str(snapshot["revision"] - 1), "--by", "A")
        self.assertEqual(self.authority(), before)
        with self.assertRaises(board.BoardError):
            self.invoke_main(*args, "--expect-board", str(snapshot["revision"]), "--by", "C")
        self.assertEqual(self.authority(), before)

    def test_remote_cli_pending_recovery_reads_without_repush(self):
        repo, _bare, _endpoint, now, snapshot, version = self.seed_remote_handoff()
        huddle = snapshot["huddles"][0]
        source = next(claim for claim in snapshot["claims"] if claim["owner"] == "A")
        target = next(claim for claim in snapshot["claims"] if claim["owner"] == "B")
        source_ref, target_ref = board._claim_ref(source), board._claim_ref(target)
        pending = board.begin_huddle_handoff(
            huddle_id=huddle["id"], generation=huddle["generation"], source_claim=source_ref,
            successor_claim=dict(source_ref, owner="B"), target_prior_claim=target_ref,
            remote_ref=remote.claim_ref(source["entity"], source["row"]),
            expected_remote_version=version, now=now, home=self.home,
            expected_board_revision=snapshot["revision"], actor_claim=source_ref)
        pending_huddle = pending.payload["huddles"][0]
        with mock.patch.object(remote, "handoff_huddle_claim", side_effect=AssertionError("recovery must not handoff")), \
             mock.patch.object(remote, "_push", side_effect=AssertionError("recovery must not push")):
            self.invoke_main(
                "settle", "--id", pending_huddle["id"], "--generation", str(pending_huddle["generation"]),
                "--expect-board", str(pending.payload["revision"]), "--by", "A")

        final_huddle = board.snapshot(home=self.home)["huddles"][0]
        self.assertEqual(final_huddle["state"], "awaiting_compliance")
        self.assertEqual(final_huddle["remote_transition"]["readback"], "predecessor")
        self.assertEqual(final_huddle["resolution"]["write_owners"], [source_ref])
        self.assertEqual(board.snapshot(home=self.home)["claims"][0]["owner"], "A")
        token, _ = board.committed_plan_snapshot(repo / "a" / "PLAN.md", repo=repo)
        actual = remote.read_remote_claim_stably(
            repo, expected_remote_version=version, source_claim=source,
            successor_claim=dict(source, owner="B"), project="shadow", plan_token=token)
        self.assertEqual(actual.outcome, "predecessor")

    def test_remote_cli_pending_ambiguous_readback_keeps_holds_without_repush(self):
        repo, _bare, endpoint, now, snapshot, version = self.seed_remote_handoff()
        huddle = snapshot["huddles"][0]
        source = next(claim for claim in snapshot["claims"] if claim["owner"] == "A")
        target = next(claim for claim in snapshot["claims"] if claim["owner"] == "B")
        source_ref, target_ref = board._claim_ref(source), board._claim_ref(target)
        pending = board.begin_huddle_handoff(
            huddle_id=huddle["id"], generation=huddle["generation"], source_claim=source_ref,
            successor_claim=dict(source_ref, owner="B"), target_prior_claim=target_ref,
            remote_ref=remote.claim_ref(source["entity"], source["row"]),
            expected_remote_version=version, now=now, home=self.home,
            expected_board_revision=snapshot["revision"], actor_claim=source_ref)
        token, _ = board.committed_plan_snapshot(repo / "a" / "PLAN.md", repo=repo)
        unexpected = remote._receipt(
            status="acquired", ref=remote.claim_ref(source["entity"], source["row"]),
            entity=source["entity"], row=source["row"], owner="C", project="shadow",
            plan_token=token, claimed_at=source["claimed_at"], return_by=source["return_by"],
            recovery=source["recovery"], state="acquired", reason="acquire", winner="C",
            failure=None, claim_revision=source["claim_revision"])
        unexpected_version = remote._commit_receipt(repo, unexpected, source["claimed_at"], version)
        self.assertIsNotNone(unexpected_version)
        self.assertTrue(remote._push(repo, endpoint, remote.claim_ref(source["entity"], source["row"]),
                                     unexpected_version, version))
        pending_huddle = pending.payload["huddles"][0]
        before_holds = pending_huddle["holds"]
        with mock.patch.object(remote, "handoff_huddle_claim", side_effect=AssertionError("ambiguous must hold")), \
             mock.patch.object(remote, "_push", side_effect=AssertionError("ambiguous recovery must not push")):
            self.invoke_main(
                "settle", "--id", pending_huddle["id"], "--generation", str(pending_huddle["generation"]),
                "--expect-board", str(pending.payload["revision"]), "--by", "A")

        final_huddle = board.snapshot(home=self.home)["huddles"][0]
        self.assertEqual(final_huddle["state"], "remote_pending")
        self.assertEqual(final_huddle["remote_transition"]["readback"], "ambiguous")
        self.assertEqual(final_huddle["holds"], before_holds)

    def test_help_lists_exactly_six_routes(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        for route in ("preflight", "open", "bid", "show", "settle", "contact-register"):
            self.assertIn(route, result.stdout.decode())

    def test_show_and_unknown_route_do_not_mutate(self):
        _, _, huddle = self.seed_open()
        before = self.authority()
        shown = self.run_cli("show", "--id", huddle["id"])
        self.assertEqual(shown.returncode, 0, shown.stderr.decode())
        self.assertEqual(json.loads(shown.stdout), huddle)
        unknown = self.run_cli("resume")
        self.assertEqual(unknown.returncode, 2)
        self.assertEqual(self.authority(), before)

    def test_open_rejects_duplicate_keys_and_oversized_input_without_mutation(self):
        a, b, _ = self.seed_open()
        before = self.authority()
        duplicate = b'{"claim_keys":[],"claim_keys":[],"reason":"semantic_suspicion"}'
        result = self.run_cli("open", "--by", "A", stdin=duplicate)
        self.assertNotEqual(result.returncode, 0)
        large = b"{" + b"x" * (64 * 1024 + 2) + b"}"
        result = self.run_cli("open", "--by", "A", stdin=large)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.authority(), before)

    def test_contact_register_is_explicitly_unavailable_without_adapter(self):
        before = tuple(self.home.iterdir())
        result = self.run_cli("contact-register", "--seat", "A", stdin=b"{}")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        expected_reason = ("optional delivery adapter absent"
                           if sys.platform == "darwin" else "unsupported_confinement")
        self.assertEqual(json.loads(result.stdout), {"available": False, "reason": expected_reason})
        self.assertEqual(tuple(self.home.iterdir()), before)

    def test_cli_rejects_noncanonical_ids_and_out_of_bounds_integers(self):
        board.ensure(home=self.home)
        before = self.authority()
        for args in (("show", "--id", "hdl_not-hex"),
                     ("show", "--id", "hdl_000000000"),
                     ("settle", "--id", "hdl_00000001", "--generation", "0",
                      "--expect-board", "0", "--by", "A"),
                     ("settle", "--id", "hdl_00000001", "--generation", "1",
                      "--expect-board", "-1", "--by", "A")):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2, (args, result.stderr.decode()))
        self.assertEqual(self.authority(), before)

    def test_settle_actor_is_selected_from_huddle_current_participants(self):
        _, _, huddle = self.seed_open()
        # A second current claim for A exists outside this Huddle. The CLI must
        # use the one exact participant reference from this board snapshot.
        with board._transaction(self.home) as (root, path, payload):
            original = next(c for c in payload["claims"] if c["owner"] == "A")
            duplicate = dict(original, row="~cc33", claim_revision=payload["revision"] + 1)
            payload["claims"].append(duplicate)
            payload["revision"] += 1
            board._write_and_commit(root, path, payload, "test: unrelated current claim", now=NOW)
        before = board.snapshot(home=self.home)["revision"]
        result = self.run_cli("settle", "--id", huddle["id"], "--generation", "1",
                              "--expect-board", str(before), "--by", "A")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("seat does not resolve", result.stderr.decode())

    def test_semantic_round_trip_replays_bid_and_rejects_stale_generation(self):
        a, b = HuddleGraphTests.seed(self, [["a"], ["b"]])
        with board._transaction(self.home) as (root, path, payload):
            future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for claim in payload["claims"]:
                claim["return_by"] = future
            payload["revision"] += 1
            board._write_and_commit(root, path, payload, "test: current CLI leases", now=datetime.now(timezone.utc))
            a, b = payload["claims"]
        refs = [board._claim_ref(a), board._claim_ref(b)]
        opened = self.run_cli("open", "--by", "A", stdin=json.dumps({"claim_keys": refs, "reason": "semantic_suspicion"}).encode())
        self.assertEqual(opened.returncode, 0, opened.stderr.decode())
        opened_receipt = json.loads(opened.stdout)
        huddle = json.loads(self.run_cli("show", "--id", opened_receipt["huddle_id"]).stdout)
        def bid(claim, role, reason):
            return {"seat": claim["owner"], "claim": board._claim_ref(claim), "role": role,
                    "scope": claim["write_scope"], "reason": reason, "target": None,
                    "support_claim": None, "evidence": {"kind": "claim", "value": "self"},
                    "round": 1, "expected_huddle_generation": huddle["generation"]}
        first = bid(a, "own", "existing_claim")
        first_args = ("bid", "--id", huddle["id"], "--generation", str(huddle["generation"]), "--by", "A")
        one = self.run_cli(*first_args, stdin=json.dumps(first).encode())
        self.assertEqual(one.returncode, 0, one.stderr.decode())
        second = self.run_cli(*first_args, stdin=json.dumps(first).encode())
        self.assertEqual(second.returncode, 0, second.stderr.decode())
        self.assertEqual(one.stdout, second.stdout)
        other = bid(b, "stand_down", "duplicate_intent")
        self.assertEqual(self.run_cli("bid", "--id", huddle["id"], "--generation", str(huddle["generation"]), "--by", "B", stdin=json.dumps(other).encode()).returncode, 0)
        self.assertEqual(self.run_cli(*first_args, stdin=json.dumps(first).encode()).stdout, one.stdout)
        before = self.authority()
        stale = self.run_cli("bid", "--id", huddle["id"], "--generation", str(huddle["generation"] + 1), "--by", "A", stdin=json.dumps(first).encode())
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(before, self.authority())
        settled = self.run_cli("settle", "--id", huddle["id"], "--generation", str(huddle["generation"]), "--expect-board", str(board.snapshot(home=self.home)["revision"]), "--by", "A")
        self.assertEqual(settled.returncode, 0, settled.stderr.decode())
        shown = self.run_cli("show", "--id", huddle["id"])
        round_two = json.loads(shown.stdout)
        self.assertEqual((round_two["state"], round_two["round"]), ("open_round_2", 2))
        self.assertEqual(self.run_cli(*first_args, stdin=json.dumps(first).encode()).stdout, one.stdout)
        for claim, role, reason in ((a, "own", "existing_claim"), (b, "stand_down", "duplicate_intent")):
            payload = bid(claim, role, reason)
            payload["round"] = 2
            payload["expected_huddle_generation"] = round_two["generation"]
            result = self.run_cli("bid", "--id", huddle["id"], "--generation", str(round_two["generation"]), "--by", claim["owner"], stdin=json.dumps(payload).encode())
            self.assertEqual(result.returncode, 0, result.stderr.decode())
        settled = self.run_cli("settle", "--id", huddle["id"], "--generation", str(round_two["generation"]), "--expect-board", str(board.snapshot(home=self.home)["revision"]), "--by", "A")
        self.assertEqual(settled.returncode, 0, settled.stderr.decode())
        final = json.loads(self.run_cli("show", "--id", huddle["id"]).stdout)
        self.assertEqual(final["resolution"]["write_owners"], [board._claim_ref(a)])
        self.assertEqual(final["holds"], [board._claim_ref(b)])


if __name__ == "__main__":
    unittest.main()
