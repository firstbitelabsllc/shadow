"""Lossless, bounded storage tests for partitioned Shadow plans."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
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


if __name__ == "__main__":
    unittest.main()
