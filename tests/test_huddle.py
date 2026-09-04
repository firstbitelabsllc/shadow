from __future__ import annotations

import copy
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


if __name__ == "__main__":
    unittest.main()
