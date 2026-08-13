"""Lossless, bounded storage tests for partitioned Shadow plans."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "shadow_plan_store.py"
SPEC = importlib.util.spec_from_file_location("shadow_plan_store", MODULE)
assert SPEC and SPEC.loader
store = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = store
SPEC.loader.exec_module(store)


def plan(*, duplicate: bool = False, dangling: bool = False) -> bytes:
    second_id = "~aa11" if duplicate else "~bb22"
    needs = "~nope" if dangling else "~aa11"
    progress = "".join(
        f"- 2026-08-12T00:{minute:02d}:00Z LESSON receipt {minute}\n"
        for minute in range(40)
    )
    return f"""# Alpha

## Brief

- Project: alpha
- Mode: ship

## Tasks

### First milestone
- [completed] first result ~aa11 | proof: cmd true

### Second milestone
- [pending] second result {second_id} | proof: cmd true | needs: {needs}
- [pending] delivery is proven ~zz99 (DoD) | proof: cmd true | needs: {second_id}

## Deferred

- later idea

## Contradictions

- monolith vs shards | provisional winner: shards | opened 2026-08-12T00:00:00Z

## Progress

- 2026-08-12T00:00:00Z ~aa11 PROOF cmd true -> pass
- 2026-08-12T00:01:00Z DECISION keep exact authority
{progress}""".encode("utf-8")


def install_tree(root: Path, content: bytes) -> Path:
    build = store.build_tree(content)
    plan_path = root / "PLAN.md"
    plan_path.write_bytes(build.root_bytes)
    object_root = root / "PLAN.d" / "objects" / "sha256"
    for digest, body in build.objects.items():
        bucket = object_root / digest[:2]
        bucket.mkdir(parents=True, exist_ok=True)
        (bucket / digest).write_bytes(body)
    return plan_path


class PlanTreeBuildTests(unittest.TestCase):
    def test_build_is_lossless_deterministic_and_content_addressed(self) -> None:
        source = plan()

        first = store.build_tree(source)
        second = store.build_tree(source)

        self.assertEqual(store.materialize_build(first), source)
        self.assertEqual(first.root_bytes, second.root_bytes)
        self.assertEqual(first.objects, second.objects)
        self.assertLessEqual(len(first.root_bytes), store.ROOT_MAX_BYTES)
        for digest, body in first.objects.items():
            self.assertEqual(hashlib.sha256(body).hexdigest(), digest)
            self.assertLessEqual(len(body), store.DATA_MAX_BYTES)

    def test_row_and_tag_routes_rebuild_from_canonical_shards(self) -> None:
        build = store.build_tree(plan())

        row = store.lookup_build(build, row_id="~bb22")
        proof = store.lookup_build(build, tag="proof")
        rebuilt = store.rebuild_routes(build)

        self.assertIn(b"second result", row.content)
        self.assertIn(b"~aa11 PROOF", proof.content)
        self.assertEqual(rebuilt.row_routes, build.row_routes)
        self.assertEqual(rebuilt.tag_routes, build.tag_routes)

    def test_duplicate_row_id_refuses(self) -> None:
        with self.assertRaisesRegex(store.PlanStoreError, "duplicate row id ~aa11"):
            store.build_tree(plan(duplicate=True))

    def test_dangling_needs_refuses(self) -> None:
        with self.assertRaisesRegex(store.PlanStoreError, "needs target ~nope"):
            store.build_tree(plan(dangling=True))

    def test_single_oversize_grammar_item_refuses(self) -> None:
        source = plan() + (b"- " + b"x" * (store.DATA_MAX_BYTES + 1) + b"\n")
        with self.assertRaisesRegex(store.PlanStoreError, "grammar item exceeds"):
            store.build_tree(source)

    def test_large_brief_splits_only_at_existing_top_level_items(self) -> None:
        items = "".join(f"- source {index}: {'x' * 400}\n" for index in range(100))
        source = plan().replace(b"## Brief\n\n", f"## Brief\n\n{items}".encode())

        build = store.build_tree(source)

        self.assertEqual(store.materialize_build(build), source)


class PlanSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_tree_row_lookup_is_bounded_and_traceable(self) -> None:
        plan_path = install_tree(self.root, plan())

        result = store.PlanSnapshot.open(plan_path).row("~bb22")

        self.assertIn(b"second result", result.content)
        self.assertEqual(result.provenance.selector, "row:~bb22")
        self.assertRegex(result.provenance.root_sha256, r"^[0-9a-f]{64}$")
        self.assertRegex(result.provenance.shard_sha256, r"^[0-9a-f]{64}$")
        self.assertLessEqual(result.provenance.file_reads, 10)
        self.assertLessEqual(result.provenance.source_bytes, 168 * 1024)

    def test_tree_materialization_restores_exact_legacy_bytes(self) -> None:
        source = plan()
        plan_path = install_tree(self.root, source)

        restored = store.PlanSnapshot.open(plan_path).materialize()

        self.assertEqual(restored, source)

    def test_tampered_object_refuses_before_returning_content(self) -> None:
        source = plan()
        build = store.build_tree(source)
        plan_path = install_tree(self.root, source)
        digest = store.lookup_build(build, row_id="~bb22").object_sha256
        object_path = self.root / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        object_path.write_bytes(object_path.read_bytes() + b"tamper")

        with self.assertRaisesRegex(store.PlanStoreError, "object digest mismatch"):
            store.PlanSnapshot.open(plan_path).row("~bb22")

    def test_missing_object_refuses_materialization(self) -> None:
        source = plan()
        build = store.build_tree(source)
        plan_path = install_tree(self.root, source)
        digest = build.root["catalog_root"]
        (self.root / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest).unlink()

        with self.assertRaisesRegex(store.PlanStoreError, "referenced object is missing"):
            store.PlanSnapshot.open(plan_path).materialize()


class DryRunMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan_path = self.root / "PLAN.md"
        self.plan_path.write_bytes(plan())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def test_dry_run_writes_nothing_and_restores_exact_source(self) -> None:
        before = self.snapshot()

        report = store.dry_run_migration(self.plan_path, board=None)

        self.assertEqual(self.snapshot(), before)
        self.assertTrue(report.exact_materialization)
        self.assertTrue(report.routes_rebuilt)
        self.assertEqual(report.query_mismatches, ())
        self.assertEqual(report.source_sha256, report.materialized_sha256)
        self.assertLessEqual(report.root_bytes, store.ROOT_MAX_BYTES)
        self.assertLessEqual(report.max_index_bytes, store.INDEX_MAX_BYTES)
        self.assertLessEqual(report.max_data_bytes, store.DATA_MAX_BYTES)

    def test_missing_archive_is_an_explicit_refusal(self) -> None:
        self.plan_path.write_bytes(
            plan().replace(
                b"## Deferred\n",
                b"- Archived milestone: [missing](docs/plan-archive/missing.md)\n\n## Deferred\n",
            )
        )

        with self.assertRaisesRegex(store.PlanStoreError, "archive content is missing"):
            store.dry_run_migration(self.plan_path, board=None)

    def test_cli_report_never_emits_the_private_plan_path_or_plan_text(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "shadow-plan.py"),
                "migrate",
                str(self.plan_path),
                "--dry-run",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.plan-migration.v1")
        self.assertEqual(payload["plan"], "PLAN.md")
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        self.assertNotIn("first result", result.stdout + result.stderr)


class PlanTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = plan()
        self.plan_path = self.root / "PLAN.md"
        self.plan_path.write_bytes(self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def changed(self, label: bytes = b"second result revised") -> bytes:
        return self.source.replace(b"second result", label)

    def test_legacy_publish_and_rollback_are_byte_exact(self) -> None:
        original = self.plan_path.read_bytes()
        published = (
            store.PlanTransaction.begin(self.plan_path)
            .replace_content(self.changed())
            .publish()
        )

        self.assertTrue(store.PlanSnapshot.open(self.plan_path).is_tree)
        self.assertEqual(
            store.PlanSnapshot.open(self.plan_path).materialize(),
            self.changed(),
        )
        restored = store.rollback(self.plan_path, expected_root=published.root_sha256)

        self.assertEqual(self.plan_path.read_bytes(), original)
        self.assertEqual(store.PlanSnapshot.open(self.plan_path).materialize(), original)
        self.assertEqual(restored.root_sha256, hashlib.sha256(original).hexdigest())

    def test_rollback_can_remove_only_the_transactions_unreachable_objects(self) -> None:
        published = (
            store.PlanTransaction.begin(self.plan_path)
            .replace_content(self.changed())
            .publish()
        )
        store.rollback(self.plan_path, expected_root=published.root_sha256)

        removed = store.discard_unreachable(self.plan_path, published.new_objects)

        self.assertEqual(set(removed), set(published.new_objects))
        self.assertEqual(self.plan_path.read_bytes(), self.source)
        self.assertEqual(
            list((self.root / "PLAN.d" / "objects" / "sha256").glob("*/*")),
            [],
        )

    def test_stale_writer_loses_the_root_cas(self) -> None:
        first = store.PlanTransaction.begin(self.plan_path)
        second = store.PlanTransaction.begin(self.plan_path)
        first.replace_content(self.changed()).publish()

        with self.assertRaisesRegex(store.PlanStoreError, "root changed"):
            second.replace_content(self.changed(b"another revision")).publish()

        self.assertEqual(
            store.PlanSnapshot.open(self.plan_path).materialize(),
            self.changed(),
        )

    def test_failure_before_root_replace_leaves_original_authority(self) -> None:
        def fail(point: str) -> None:
            if point == "before-root-replace":
                raise RuntimeError("injected crash")

        with self.assertRaisesRegex(RuntimeError, "injected crash"):
            (
                store.PlanTransaction.begin(self.plan_path)
                .replace_content(self.changed())
                .publish(fault=fail)
            )

        self.assertEqual(self.plan_path.read_bytes(), self.source)
        self.assertEqual(store.PlanSnapshot.open(self.plan_path).materialize(), self.source)

    def test_failure_after_root_replace_leaves_new_authority_readable(self) -> None:
        def fail(point: str) -> None:
            if point == "after-root-replace":
                raise RuntimeError("injected crash")

        with self.assertRaisesRegex(RuntimeError, "injected crash"):
            (
                store.PlanTransaction.begin(self.plan_path)
                .replace_content(self.changed())
                .publish(fault=fail)
            )

        snapshot = store.PlanSnapshot.open(self.plan_path)
        self.assertTrue(snapshot.is_tree)
        self.assertEqual(snapshot.materialize(), self.changed())

    def test_corrupt_existing_object_refuses_before_root_change(self) -> None:
        candidate = store.build_tree(self.changed())
        digest, body = next(iter(candidate.objects.items()))
        destination = (
            self.root / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        )
        destination.parent.mkdir(parents=True)
        destination.write_bytes(body + b"corrupt")

        with self.assertRaisesRegex(
            store.PlanStoreError,
            "existing content-addressed object is corrupt",
        ):
            (
                store.PlanTransaction.begin(self.plan_path)
                .replace_content(self.changed())
                .publish()
            )

        self.assertEqual(self.plan_path.read_bytes(), self.source)

    def test_tree_mutation_reuses_unchanged_objects(self) -> None:
        install_tree(self.root, self.source)
        before = {
            path.name
            for path in (self.root / "PLAN.d" / "objects" / "sha256").glob("*/*")
        }
        receipt = (
            store.PlanTransaction.begin(self.plan_path)
            .replace_content(self.changed())
            .publish()
        )
        after = {
            path.name
            for path in (self.root / "PLAN.d" / "objects" / "sha256").glob("*/*")
        }

        self.assertTrue(before & after)
        self.assertLess(receipt.object_writes, len(store.build_tree(self.changed()).objects) + 1)

    def test_rollback_requires_the_current_root(self) -> None:
        receipt = (
            store.PlanTransaction.begin(self.plan_path)
            .replace_content(self.changed())
            .publish()
        )

        with self.assertRaisesRegex(store.PlanStoreError, "root changed"):
            store.rollback(self.plan_path, expected_root="0" * 64)

        self.assertEqual(
            store.PlanSnapshot.open(self.plan_path).root_sha256,
            receipt.root_sha256,
        )


if __name__ == "__main__":
    unittest.main()
