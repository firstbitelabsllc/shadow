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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
# One canonical module object: the tamper tests patch the exact PlanSnapshot
# that board.open_plan and shadow-read both call. A second exec-loaded copy
# made the patch load-order-dependent and turned three tests into ghosts.
import shadow_plan_store as store  # noqa: E402
from tests.plan_tree_fixture import install_plan_tree
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
        f"- 2026-08-23T17:{minute:02d}:00Z NOTE receipt {minute} — café\n"
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
- 2026-08-23T17:29:00Z ~gk11 S053 UNKNOWN — prior digest baseline
""".encode("utf-8")


class PlanReadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.authority = self.root / "authority"
        self.authority.mkdir()
        self.plan, self.build = install_plan_tree(self.authority, source(), return_build=True)
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
        self.assertIn("S053 UNKNOWN — prior digest baseline", combined)
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
        self.assertEqual(payload["selection_budget"]["verification_passes"], 2)
        self.assertEqual(
            payload["selection_budget"]["aggregate_file_reads"],
            2 * sum(item["provenance"]["file_reads"] for item in payload["results"]),
        )
        self.assertEqual(
            payload["selection_budget"]["aggregate_source_bytes"],
            2 * sum(item["provenance"]["source_bytes"] for item in payload["results"]),
        )
        claimed_projection_sha = payload.pop("projection_sha256")
        encoded = store.canonical_json(payload)
        self.assertEqual(claimed_projection_sha, hashlib.sha256(encoded).hexdigest())
        self.assertIn("— prior digest baseline", result.stdout)

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
        self.plan, self.build = install_plan_tree(self.authority, source(archive=True), return_build=True)
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
        other_plan, _ = install_plan_tree(other_root, other_source, return_build=True)
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
                finds=[],
                expect_root=self.root_sha256,
            )

    def test_selected_shard_tamper_during_projection_is_refused(self) -> None:
        original_row = read.store.PlanSnapshot.row
        digest = store.lookup_build(self.build, row_id="~gk12").object_sha256
        shard = self.authority / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        mutated = False

        def row_then_tamper(snapshot: object, row_id: str) -> object:
            nonlocal mutated
            result = original_row(snapshot, row_id)
            if not mutated:
                mutated = True
                shard.write_bytes(shard.read_bytes() + b"tamper")
            return result

        with (
            mock.patch.dict(os.environ, {"HOME": str(self.home)}),
            mock.patch.object(read.store.PlanSnapshot, "row", new=row_then_tamper),
            self.assertRaisesRegex(ValueError, "object digest mismatch"),
        ):
            read.project(
                entity=self.entity,
                rows=["~gk12"],
                receipts=[],
                finds=[],
                expect_root=self.root_sha256,
            )

    def test_selected_index_tamper_during_projection_is_refused(self) -> None:
        original_row = read.store.PlanSnapshot.row
        digest = self.build.root["row_root"]
        index = self.authority / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        mutated = False

        def row_then_tamper(snapshot: object, row_id: str) -> object:
            nonlocal mutated
            result = original_row(snapshot, row_id)
            if not mutated:
                mutated = True
                index.write_bytes(index.read_bytes() + b"tamper")
            return result

        with (
            mock.patch.dict(os.environ, {"HOME": str(self.home)}),
            mock.patch.object(read.store.PlanSnapshot, "row", new=row_then_tamper),
            self.assertRaisesRegex(ValueError, "object digest mismatch"),
        ):
            read.project(
                entity=self.entity,
                rows=["~gk12"],
                receipts=[],
                finds=[],
                expect_root=self.root_sha256,
            )

    def test_absurd_receipt_sequence_fails_without_traceback_or_path_leak(self) -> None:
        result = self.cli("--receipt", "progress:" + ("9" * 5000))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("receipt selector must be TAG:N", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_absurd_integer_in_board_json_fails_without_traceback_or_path_leak(self) -> None:
        board_path = self.home / ".shadow" / "board.json"
        board_path.write_bytes(
            b'{"schema":"shadow.root-board.v1","revision":'
            + (b"9" * 5000)
            + b'}'
        )

        result = self.cli("--row", "~gk12")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("board file is unreadable or malformed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_absurd_integer_in_plan_root_fails_without_traceback_or_path_leak(self) -> None:
        self.plan.write_bytes(
            store.ROOT_PREFIX
            + b'{"schema":"shadow.plan-tree.v1","generation":'
            + (b"9" * 5000)
            + b'}'
            + store.ROOT_SUFFIX
        )

        result = self.cli("--row", "~gk12")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("plan-tree root JSON is malformed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_quoted_absolute_path_in_error_is_sanitized(self) -> None:
        detail = read._safe_error(
            ValueError('wrapped "/var/folders/private-plan"'),
            "entity@0123456789ab/PLAN.md",
        )

        self.assertEqual(
            detail,
            "canonical plan read failed for entity@0123456789ab/PLAN.md",
        )
        self.assertNotIn("/var/", detail)

    def test_argparse_refusal_does_not_echo_a_private_positional_path(self) -> None:
        result = subprocess.run(
            [
                str(SHADOW), "read", "--entity", self.entity,
                str(self.plan), "--row", "~gk12",
            ],
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

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("shadow read: invalid arguments", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_selector_count_and_duplicate_selectors_are_refused(self) -> None:
        too_many: list[str] = []
        for sequence in range(9):
            too_many.extend(("--receipt", f"progress:{sequence}"))

        capped = self.cli(*too_many)
        duplicate = self.cli("--row", "~gk12", "--row", "~gk12")

        self.assertEqual(capped.returncode, 2)
        self.assertEqual(capped.stdout, "")
        self.assertIn("at most 8 selectors", capped.stderr)
        self.assertEqual(duplicate.returncode, 2)
        self.assertEqual(duplicate.stdout, "")
        self.assertIn("duplicate selector row:~gk12", duplicate.stderr)

    def test_literal_find_scans_one_complete_entity_and_returns_bounded_matches(self) -> None:
        distractor = ("- unrelated production note " + ("x" * 180) + "\n") * 220
        visual = (
            "### Visual treatment\n"
            "- Michael Girdley craft transfer: storyboard, assets, rights, and edit plan ~fx02\n\n"
        )
        content = source().replace(
            b"## Tasks\n",
            (distractor + visual + "## Tasks\n").encode("utf-8"),
        )
        self.plan, self.build = install_plan_tree(self.authority, content, return_build=True)
        self.root_sha256 = hashlib.sha256(self.plan.read_bytes()).hexdigest()

        result = self.cli(
            "--find", "michael girdley",
            "--expect-root", self.root_sha256,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["result_count"], 1)
        found = payload["results"][0]
        self.assertEqual(found["selector"], "find:michael girdley")
        self.assertEqual(found["kind"], "find")
        self.assertEqual(found["match_count"], 1)
        self.assertFalse(found["truncated"])
        self.assertIn("Michael Girdley craft transfer", found["content"])
        self.assertNotIn("unrelated production note", found["content"])
        self.assertEqual(found["provenance"]["root_sha256"], self.root_sha256)
        self.assertEqual(
            found["provenance"]["logical_sha256"],
            self.build.root["logical_sha256"],
        )
        self.assertEqual(found["provenance"]["scan_bytes"], len(content))
        self.assertGreaterEqual(
            payload["selection_budget"]["aggregate_source_bytes"], len(content)
        )

    def test_literal_find_proves_no_match_after_a_complete_verified_scan(self) -> None:
        result = self.cli("--find", "Michael Girdley")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        found = payload["results"][0]
        self.assertEqual(found["match_count"], 0)
        self.assertEqual(found["content"], "")
        self.assertFalse(found["truncated"])
        self.assertTrue(found["complete_scan"])

    def test_literal_find_caps_output_without_turning_omission_into_absence(self) -> None:
        repeated = "".join(
            f"- Michael Girdley visual direction occurrence {index:03d}\n"
            for index in range(80)
        )
        content = source().replace(
            b"## Tasks\n", (repeated + "## Tasks\n").encode("utf-8")
        )
        self.plan, self.build = install_plan_tree(self.authority, content, return_build=True)

        result = self.cli("--find", "Michael Girdley")

        self.assertEqual(result.returncode, 0, result.stderr)
        found = json.loads(result.stdout)["results"][0]
        self.assertEqual(found["match_count"], 80)
        self.assertEqual(found["returned_match_count"], read.MAX_FIND_MATCHES)
        self.assertTrue(found["truncated"])
        self.assertTrue(found["complete_scan"])
        self.assertIn("occurrence 000", found["content"])
        self.assertNotIn("occurrence 079", found["content"])

    def test_literal_find_detects_tamper_anywhere_and_emits_no_partial_result(self) -> None:
        digest = store.lookup_build(self.build, tag="progress", tag_sequence=11).object_sha256
        shard = self.authority / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        shard.write_bytes(shard.read_bytes() + b"tamper")

        result = self.cli("--find", "Assistant")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("object digest mismatch", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_literal_find_validation_is_bounded_and_private(self) -> None:
        empty = self.cli("--find", "")
        huge = self.cli("--find", "x" * (read.MAX_FIND_QUERY_BYTES + 1))
        duplicate = self.cli("--find", "Girdley", "--find", "girdley")

        for result in (empty, huge, duplicate):
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertNotIn(str(self.root), result.stderr)
        self.assertIn("find query", empty.stderr)
        self.assertIn("find query", huge.stderr)
        self.assertIn("duplicate selector find:girdley", duplicate.stderr)


if __name__ == "__main__":
    unittest.main()
