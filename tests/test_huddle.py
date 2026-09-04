from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
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
            board_api._write_and_commit(root, path, value, "test: seed v2 board")
            return root, path

    def authority(self) -> tuple[bytes, str]:
        root = self.home / ".shadow"
        return (root / board_api.BOARD_NAME).read_bytes(), board_api._journal_head(root)


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
        with self.assertRaises(board_api.BoardError):
            self.preflight(repo, a, ["a"], now=NOW + timedelta(minutes=2))
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


if __name__ == "__main__":
    unittest.main()
