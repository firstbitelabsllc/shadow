"""Tests for scripts/vidux-drift-log.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-drift-log.py"

spec = importlib.util.spec_from_file_location("vidux_drift_log", SCRIPT)
assert spec is not None
drift = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = drift
spec.loader.exec_module(drift)


def base_plan() -> str:
    return """# Test Plan

## Purpose
Ship the thing.

## Evidence
- [Source: test] fixture

## Constraints
- ALWAYS: stay cited
- NEVER: drift silently

## Tasks
- [in_progress] T-1: Build the planned API [Evidence: test]

## Decision Log
- [DIRECTION] [2026-05-21] Keep one plan.

## Progress
- [2026-05-21] Started T-1.
"""


class DriftLogTests(unittest.TestCase):
    def test_records_drift_blocks_task_and_appends_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            plan.write_text(base_plan(), encoding="utf-8")

            drift_id = drift.record_drift(
                plan,
                drift.DriftEntry(
                    task="T-1",
                    planned="Implement the original API.",
                    actual="Replaced it with a smaller CLI helper.",
                    why="The integration point was a script, not an HTTP surface.",
                    plan_update="Parent plan now tracks the CLI helper.",
                    next_step="Run the helper tests.",
                    today="2026-05-22",
                ),
                block_task="T-1",
                add_tasks=["T-2: Wire CLI docs"],
            )

            text = plan.read_text(encoding="utf-8")
            self.assertEqual(drift_id, "D-20260522-01")
            self.assertLess(text.index("## Drift Log"), text.index("## Progress"))
            self.assertIn("- [2026-05-22] D-20260522-01 — T-1", text)
            self.assertIn("- [blocked] T-1: Build the planned API", text)
            self.assertIn("[Drift: D-20260522-01]", text)
            self.assertIn("- [pending] T-2: Wire CLI docs [Source: Drift D-20260522-01]", text)
            self.assertIn("Drift D-20260522-01: Replaced it with a smaller CLI helper.", text)

    def test_records_cache_prevention_hints_and_signpost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "PLAN.md"
            plan.write_text(base_plan(), encoding="utf-8")
            cache = root / "drift-cache.jsonl"
            telemetry = root / "signposts.jsonl"

            drift_id = drift.record_drift(
                plan,
                drift.DriftEntry(
                    task="T-1",
                    planned="Implement the original API.",
                    actual="Replaced it with a smaller CLI helper.",
                    why="The integration point was a script, not an HTTP surface.",
                    plan_update="Parent plan now tracks the CLI helper.",
                    next_step="Run the helper tests.",
                    today="2026-05-22",
                ),
                cache_path=cache,
                telemetry_path=telemetry,
                prevention_hints=["Name the real integration seam before coding."],
            )

            self.assertEqual(drift_id, "D-20260522-01")
            plan_text = plan.read_text(encoding="utf-8")
            self.assertIn("  - Prevention: Name the real integration seam before coding.", plan_text)

            cache_rows = [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(cache_rows), 1)
            self.assertEqual(cache_rows[0]["drift_id"], "D-20260522-01")
            self.assertEqual(cache_rows[0]["task"], "T-1")
            self.assertEqual(cache_rows[0]["plan_path"], str(plan.resolve()))
            self.assertEqual(cache_rows[0]["prevention_hints"], ["Name the real integration seam before coding."])
            self.assertEqual(cache_rows[0]["added_tasks"], [])
            self.assertEqual(cache_rows[0]["blocked_task"], None)

            telemetry_rows = [
                json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(telemetry_rows[0]["feature"], "drift")
            self.assertEqual(telemetry_rows[0]["action"], "record")
            self.assertEqual(telemetry_rows[0]["status"], "ok")
            self.assertEqual(telemetry_rows[0]["metadata"]["drift_id"], "D-20260522-01")

    def test_suggests_preventions_from_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "drift-cache.jsonl"
            cache.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "drift_id": "D-20260522-01",
                        "date": "2026-05-22",
                        "plan_path": "/tmp/PLAN.md",
                        "task": "T-1",
                        "planned": "Build an HTTP API for the local command.",
                        "actual": "Built a CLI helper instead.",
                        "why": "The integration seam was a local script.",
                        "plan_update": "Plan now names the CLI seam.",
                        "next": "Document CLI usage.",
                        "prevention_hints": ["Name the integration seam and caller before implementation."],
                        "subplans": [],
                        "added_tasks": [],
                        "blocked_task": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            suggestions = drift.suggest_preventions(
                "## Tasks\n- [pending] T-9: Build local CLI command for script integration\n",
                cache_path=cache,
                limit=2,
            )

            self.assertEqual(len(suggestions), 1)
            self.assertEqual(
                suggestions[0]["prevention"],
                "Name the integration seam and caller before implementation.",
            )
            self.assertEqual(suggestions[0]["source_drift_id"], "D-20260522-01")

    def test_mirrors_drift_to_subplan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "PLAN.md"
            plan.write_text(base_plan(), encoding="utf-8")
            subdir = root / "investigations"
            subdir.mkdir()
            subplan = subdir / "api.md"
            subplan.write_text("# Investigation\n\n## Progress\n\n- [2026-05-21] Opened.\n", encoding="utf-8")

            drift.record_drift(
                plan,
                drift.DriftEntry(
                    task="T-1",
                    planned="Use HTTP.",
                    actual="Use CLI.",
                    why="The shipped seam is CLI-only.",
                    plan_update="Subplan should test the CLI seam.",
                    next_step="Add fixture coverage.",
                    today="2026-05-22",
                ),
                subplans=[Path("investigations/api.md")],
            )

            text = subplan.read_text(encoding="utf-8")
            self.assertLess(text.index("## Drift Log"), text.index("## Progress"))
            self.assertIn("D-20260522-01 from `PLAN.md`", text)
            self.assertIn("Parent update: Subplan should test the CLI seam.", text)

    def test_missing_subplan_does_not_mutate_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            original = base_plan()
            plan.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "subplan not found"):
                drift.record_drift(
                    plan,
                    drift.DriftEntry(
                        task="T-1",
                        planned="Use HTTP.",
                        actual="Use CLI.",
                        why="The seam moved.",
                        plan_update="Track CLI.",
                        next_step="Run tests.",
                        today="2026-05-22",
                    ),
                    subplans=[Path("missing.md")],
                )

            self.assertEqual(plan.read_text(encoding="utf-8"), original)

    def test_block_task_only_blocks_first_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            plan.write_text(
                base_plan() + "- [pending] T-1 follow-up: Keep this queued [Evidence: test]\n",
                encoding="utf-8",
            )

            drift.record_drift(
                plan,
                drift.DriftEntry(
                    task="T-1",
                    planned="Use HTTP.",
                    actual="Use CLI.",
                    why="The seam moved.",
                    plan_update="Track CLI.",
                    next_step="Run tests.",
                    today="2026-05-22",
                ),
                block_task="T-1",
            )

            text = plan.read_text(encoding="utf-8")
            self.assertEqual(text.count("[blocked] T-1"), 1)
            self.assertIn("- [pending] T-1 follow-up: Keep this queued", text)

    def test_cli_records_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            plan.write_text(base_plan(), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(plan),
                    "--task",
                    "T-1",
                    "--planned",
                    "Use HTTP.",
                    "--actual",
                    "Use CLI.",
                    "--why",
                    "The seam moved.",
                    "--plan-update",
                    "Track CLI.",
                    "--next",
                    "Run tests.",
                    "--today",
                    "2026-05-22",
                    "--no-cache",
                    "--no-telemetry",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("recorded drift D-20260522-01", result.stdout)
            self.assertIn("## Drift Log", plan.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
