"""Public, bounded, fail-closed projections from one canonical plan tree."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SHADOW = ROOT / "bin" / "shadow"
MODULE = ROOT / "scripts" / "shadow_plan_store.py"
SPEC = importlib.util.spec_from_file_location("shadow_plan_store_for_read", MODULE)
assert SPEC and SPEC.loader
store = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = store
SPEC.loader.exec_module(store)

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402

READ_SCRIPT = ROOT / "scripts" / "shadow-read.py"
READ_SPEC = importlib.util.spec_from_file_location("shadow_read_for_test", READ_SCRIPT)
assert READ_SPEC and READ_SPEC.loader
read = importlib.util.module_from_spec(READ_SPEC)
sys.modules[READ_SPEC.name] = read
READ_SPEC.loader.exec_module(read)


def source(*, archive: bool = False) -> bytes:
    tombstone = (
        "- Archived milestone: [old](docs/plan-archive/old.md)\n\n"
        if archive
        else ""
    )
    progress = "".join(
        f"- 2026-08-23T17:{minute:02d}:00Z NOTE receipt {minute}\n"
        for minute in range(10)
    )
    return f"""# Assistant

## Brief

- Project: ai-leo
- Mode: prove

## Tasks

### Digest context
- [completed] disposition native non-passes ~gk12 | proof: read receipts
- [pending] release the native corpus ~gk13 (DoD) | proof: read scorecard | needs: ~gk12

{tombstone}## Deferred

- exact wake remains

## Contradictions

- copied queue vs returned attention | provisional winner: returned attention | opened 2026-08-23T17:00:00Z

## Progress

{progress}- 2026-08-23T17:26:00Z ~gk11 S044 PASS stable obligation key personal:volt:thread:message
- 2026-08-23T17:29:00Z ~gk11 S053 UNKNOWN prior digest baseline
""".encode("utf-8")


def install_tree(root: Path, content: bytes) -> tuple[Path, object]:
    build = store.build_tree(content)
    plan = root / "PLAN.md"
    plan.write_bytes(build.root_bytes)
    object_root = root / "PLAN.d" / "objects" / "sha256"
    for digest, body in build.objects.items():
        bucket = object_root / digest[:2]
        bucket.mkdir(parents=True, exist_ok=True)
        (bucket / digest).write_bytes(body)
    return plan, build


class PlanReadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.authority = self.root / "authority"
        self.authority.mkdir()
        self.plan, self.build = install_tree(self.authority, source())
        self.root_sha256 = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        self.home = self.root / "home"
        self.home.mkdir()
        self.entity = board.entity_id(self.plan)
        self.write_board([(self.entity, self.plan)])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_board(self, entities: list[tuple[str, Path]]) -> None:
        root = self.home / ".shadow"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {
            "schema": board.SCHEMA,
            "revision": 7,
            "projects": [{"id": "ai-leo", "priority": 1}],
            "entities": [
                {
                    "id": identity,
                    "project": "ai-leo",
                    "plan": str(plan),
                    "resume": "~gk12",
                }
                for identity, plan in entities
            ],
            "claims": [],
        }
        path = root / "board.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)

    def cli_for(self, entity: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SHADOW), "read", "--entity", entity, *args],
            cwd=ROOT,
            env={
                **os.environ,
                "HOME": str(self.home),
                "SHADOW_ROOT": str(ROOT),
            },
            capture_output=True,
            text=True,
            check=False,
        )

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.cli_for(self.entity, *args)

    def test_exact_row_and_receipts_emit_content_with_complete_provenance(self) -> None:
        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:10",
            "--receipt", "progress:11",
            "--expect-root", self.root_sha256,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.plan-projection.v1")
        self.assertEqual(payload["plan"], board.public_entity_locator(self.entity))
        self.assertEqual(payload["entity_id"], self.entity)
        self.assertEqual(payload["board_revision"], 7)
        self.assertEqual(payload["root_sha256"], self.root_sha256)
        self.assertEqual(payload["result_count"], 3)
        self.assertEqual(
            [item["selector"] for item in payload["results"]],
            ["row:~gk12", "tag:progress:10", "tag:progress:11"],
        )
        combined = "".join(item["content"] for item in payload["results"])
        self.assertIn("disposition native non-passes ~gk12", combined)
        self.assertIn("S044 PASS stable obligation key", combined)
        self.assertIn("S053 UNKNOWN prior digest baseline", combined)
        self.assertNotIn("exact wake remains", combined)
        self.assertNotIn("receipt 9", combined)
        for item in payload["results"]:
            provenance = item["provenance"]
            self.assertEqual(provenance["selector"], item["selector"])
            self.assertEqual(provenance["entity_id"], self.entity)
            self.assertEqual(
                provenance["entity_locator"],
                board.public_entity_locator(self.entity),
            )
            self.assertEqual(provenance["root_sha256"], self.root_sha256)
            self.assertRegex(provenance["shard_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(provenance["result_sha256"], r"^[0-9a-f]{64}$")
            self.assertLessEqual(provenance["file_reads"], 10)
            self.assertLessEqual(provenance["source_bytes"], 168 * 1024)
        claimed_projection_sha = payload.pop("projection_sha256")
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(claimed_projection_sha, hashlib.sha256(encoded).hexdigest())

    def test_tampered_selected_shard_returns_no_partial_projection(self) -> None:
        digest = store.lookup_build(self.build, row_id="~gk12").object_sha256
        shard = self.authority / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        shard.write_bytes(shard.read_bytes() + b"tamper")

        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:10",
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("shadow read: object digest mismatch", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_missing_selected_shard_returns_no_partial_projection(self) -> None:
        digest = store.lookup_build(
            self.build, tag="progress", tag_sequence=11
        ).object_sha256
        shard = self.authority / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        shard.unlink()

        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:11",
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("shadow read: referenced object is missing", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_root_cas_mismatch_returns_no_content(self) -> None:
        result = self.cli(
            "--row", "~gk12",
            "--expect-root", "0" * 64,
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("plan root changed", result.stderr)
        self.assertNotIn("disposition native non-passes", result.stderr)

    def test_legacy_plan_is_refused_instead_of_being_read_whole(self) -> None:
        self.plan.write_bytes(source())

        result = self.cli("--row", "~gk12")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("requires a shadow.plan-tree.v1 root", result.stderr)
        self.assertNotIn("S044", result.stderr)

    def test_projection_never_follows_archive_tombstones_or_spill_files(self) -> None:
        self.plan, self.build = install_tree(self.authority, source(archive=True))
        outside = self.root / "must-not-be-read.txt"
        outside.write_text("PRIVATE_SPILL_SENTINEL", encoding="utf-8")
        archive = self.authority / "docs" / "plan-archive" / "old.md"
        archive.parent.mkdir(parents=True)
        archive.symlink_to(outside)

        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:10",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PRIVATE_SPILL_SENTINEL", result.stdout + result.stderr)
        self.assertNotIn(str(outside), result.stdout + result.stderr)

    def test_entity_binding_distinguishes_two_registered_plan_trees(self) -> None:
        other_root = self.root / "other-authority"
        other_root.mkdir()
        other_source = source().replace(
            b"disposition native non-passes",
            b"WRONG AUTHORITY CONTENT",
        )
        other_plan, _ = install_tree(other_root, other_source)
        other_entity = board.entity_id(other_plan)
        self.write_board(
            [(self.entity, self.plan), (other_entity, other_plan)]
        )

        first = self.cli_for(self.entity, "--row", "~gk12")
        second = self.cli_for(other_entity, "--row", "~gk12")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)
        self.assertEqual(first_payload["entity_id"], self.entity)
        self.assertEqual(second_payload["entity_id"], other_entity)
        self.assertNotEqual(first_payload["plan"], second_payload["plan"])
        self.assertNotIn("WRONG AUTHORITY CONTENT", first.stdout)
        self.assertIn("WRONG AUTHORITY CONTENT", second.stdout)

    def test_registered_pointer_with_a_symlinked_parent_is_refused(self) -> None:
        alias = self.root / "plan-alias"
        alias.symlink_to(self.authority, target_is_directory=True)
        self.write_board([(self.entity, alias / "PLAN.md")])

        result = self.cli("--row", "~gk12")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("registered entity plan is missing, unreadable, or a symlink", result.stderr)
        self.assertNotIn("disposition native non-passes", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_root_replacement_during_projection_is_refused(self) -> None:
        original_row = read.store.PlanSnapshot.row
        changed = source().replace(
            b"disposition native non-passes",
            b"root changed during read",
        )
        mutated = False

        def row_then_replace(snapshot: object, row_id: str) -> object:
            nonlocal mutated
            result = original_row(snapshot, row_id)
            if not mutated:
                mutated = True
                (
                    read.store.PlanTransaction.begin(self.plan)
                    .replace_content(changed)
                    .publish()
                )
            return result

        with (
            mock.patch.dict(os.environ, {"HOME": str(self.home)}),
            mock.patch.object(read.store.PlanSnapshot, "row", new=row_then_replace),
            self.assertRaisesRegex(ValueError, "plan root changed during projection"),
        ):
            read.project(
                entity=self.entity,
                rows=["~gk12"],
                receipts=[],
                expect_root=self.root_sha256,
            )

    def test_absurd_receipt_sequence_fails_without_traceback_or_path_leak(self) -> None:
        result = self.cli("--receipt", "progress:" + ("9" * 5000))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("receipt selector must be TAG:N", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_selector_count_and_duplicate_selectors_are_refused(self) -> None:
        too_many: list[str] = []
        for sequence in range(9):
            too_many.extend(("--receipt", f"progress:{sequence}"))

        capped = self.cli(*too_many)
        duplicate = self.cli("--row", "~gk12", "--row", "~gk12")

        self.assertEqual(capped.returncode, 2)
        self.assertEqual(capped.stdout, "")
        self.assertIn("at most 8 exact selectors", capped.stderr)
        self.assertEqual(duplicate.returncode, 2)
        self.assertEqual(duplicate.stdout, "")
        self.assertIn("duplicate selector row:~gk12", duplicate.stderr)


if __name__ == "__main__":
    unittest.main()
