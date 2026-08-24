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


ROOT = Path(__file__).resolve().parents[1]
SHADOW = ROOT / "bin" / "shadow"
MODULE = ROOT / "scripts" / "shadow_plan_store.py"
SPEC = importlib.util.spec_from_file_location("shadow_plan_store_for_read", MODULE)
assert SPEC and SPEC.loader
store = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = store
SPEC.loader.exec_module(store)


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
        self.plan, self.build = install_tree(self.root, source())
        self.root_sha256 = hashlib.sha256(self.plan.read_bytes()).hexdigest()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SHADOW), "read", str(self.plan), *args],
            cwd=ROOT,
            env={**os.environ, "SHADOW_ROOT": str(ROOT)},
            capture_output=True,
            text=True,
            check=False,
        )

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
        self.assertEqual(payload["plan"], "PLAN.md")
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
        shard = self.root / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        shard.write_bytes(shard.read_bytes() + b"tamper")

        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:10",
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("shadow read: object digest mismatch", result.stderr)

    def test_missing_selected_shard_returns_no_partial_projection(self) -> None:
        digest = store.lookup_build(
            self.build, tag="progress", tag_sequence=11
        ).object_sha256
        shard = self.root / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
        shard.unlink()

        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:11",
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("shadow read: referenced object is missing", result.stderr)

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
        self.plan, self.build = install_tree(self.root, source(archive=True))
        outside = self.root / "must-not-be-read.txt"
        outside.write_text("PRIVATE_SPILL_SENTINEL", encoding="utf-8")
        archive = self.root / "docs" / "plan-archive" / "old.md"
        archive.parent.mkdir(parents=True)
        archive.symlink_to(outside)

        result = self.cli(
            "--row", "~gk12",
            "--receipt", "progress:10",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PRIVATE_SPILL_SENTINEL", result.stdout + result.stderr)
        self.assertNotIn(str(outside), result.stdout + result.stderr)

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
