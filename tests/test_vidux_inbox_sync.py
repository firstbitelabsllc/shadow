"""Tests for scripts/vidux-inbox-sync.py."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-inbox-sync.py"

spec = importlib.util.spec_from_file_location("vidux_inbox_sync", SCRIPT)
assert spec is not None
sync = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = sync
spec.loader.exec_module(sync)


class FakeLinearAdapter:
    name = "linear"

    def __init__(self, items=None):
        self.items = list(items or [])
        self.pushed = []
        self.status_pushes = []
        self.field_pushes = []

    def fetch_inbox(self):
        return list(self.items)

    def push_task(self, task):
        self.pushed.append(task)
        return f"new-{len(self.pushed)}"

    def pull_status(self, external_id):
        return sync.VidxStatus.PENDING

    def push_status(self, external_id, status):
        self.status_pushes.append((external_id, status))

    def pull_fields(self, external_id):
        return {}

    def push_fields(self, external_id, fields):
        self.field_pushes.append((external_id, fields))


class InboxSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vidux-inbox-sync-")
        self.plan_dir = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_plan(self, tasks: str) -> None:
        self.write_plan_at(self.plan_dir, tasks)

    def write_plan_at(self, plan_dir: Path, tasks: str) -> None:
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "PLAN.md").write_text(
            textwrap.dedent(
                f"""\
                # Test Plan

                ## Purpose
                Test fixture.

                ## Tasks
                {tasks.rstrip()}

                ## Decision Log
                - [DIRECTION] fixture.

                ## Progress
                - fixture.
                """
            ),
            encoding="utf-8",
        )

    def external_item(
        self,
        external_id="lin_1",
        title="Fix duplicated card",
        status=None,
        blocked=False,
    ):
        return sync.ExternalItem(
            external_id=external_id,
            title=title,
            status=status or sync.VidxStatus.PENDING,
            blocked=blocked,
        )

    def test_source_marker_rehydrates_mapping_before_push(self):
        self.write_plan(
            "- [pending] BD-1: Fix duplicated card [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter([self.external_item()])

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="push",
            dry_run=False,
        )

        self.assertEqual(summary["source_mapped"], 1)
        self.assertEqual(adapter.pushed, [])
        state = sync.load_state(self.plan_dir)
        mapping = sync.adapter_state(state, adapter.name)
        self.assertEqual(mapping, {"BD-1": "lin_1"})

    def test_parse_plan_accepts_pre_colon_metadata(self):
        self.write_plan(
            "- [in_progress] CE-10 [ETA: 2h]: Glossary sweep batch A [Source: linear:lin_1]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "CE-10")
        self.assertEqual(tasks[0].eta_hours, 2.0)
        self.assertEqual(tasks[0].source, "linear:lin_1")
        self.assertEqual(tasks[0].title, "Glossary sweep batch A")

    def test_auto_promoted_source_marker_dedupes_when_state_is_missing(self):
        self.write_plan("")
        adapter = FakeLinearAdapter([self.external_item()])

        promoted, new_mappings = sync.auto_promote_novel_items(
            self.plan_dir,
            adapter.fetch_inbox(),
            adapter.name,
            fleet_known_ext_ids=set(),
            dry_run=False,
        )
        self.assertEqual(promoted, 1)
        self.assertEqual(new_mappings, {"BD-1": "lin_1"})
        self.assertFalse((self.plan_dir / sync.STATE_FILENAME).exists())

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="push",
            dry_run=False,
        )

        self.assertEqual(summary["source_mapped"], 1)
        self.assertEqual(adapter.pushed, [])
        state = sync.load_state(self.plan_dir)
        mapping = sync.adapter_state(state, adapter.name)
        self.assertEqual(mapping, {"BD-1": "lin_1"})

    def test_push_status_skipped_when_remote_matches_local(self):
        self.write_plan(
            "- [in_progress] Task 1: Active work [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter(
            [self.external_item(status=sync.VidxStatus.IN_PROGRESS)]
        )

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="push",
            dry_run=False,
        )

        self.assertEqual(adapter.status_pushes, [])
        self.assertEqual(adapter.field_pushes, [])
        self.assertEqual(summary["push_skipped_idempotent"], 2)
        self.assertEqual(summary["errors"], [])

    def test_push_status_fires_when_remote_status_diverges(self):
        self.write_plan(
            "- [in_progress] Task 1: Active work [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter(
            [self.external_item(status=sync.VidxStatus.PENDING)]
        )

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="push",
            dry_run=False,
        )

        self.assertEqual(
            adapter.status_pushes, [("lin_1", sync.VidxStatus.IN_PROGRESS)]
        )
        self.assertEqual(adapter.field_pushes, [])
        self.assertEqual(summary["push_skipped_idempotent"], 1)
        self.assertEqual(summary["errors"], [])

    def test_push_fields_fires_when_blocked_flag_diverges(self):
        self.write_plan(
            "- [blocked] Task 1: Stuck work [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter(
            [
                self.external_item(
                    status=sync.VidxStatus.PENDING,
                    blocked=False,
                )
            ]
        )

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="push",
            dry_run=False,
        )

        self.assertEqual(adapter.status_pushes, [])
        self.assertEqual(
            adapter.field_pushes, [("lin_1", {"_blocked": True})]
        )
        self.assertEqual(summary["push_skipped_idempotent"], 0)
        self.assertEqual(summary["errors"], [])

    def test_do_push_false_suppresses_auto_promote_plan_push(self):
        self.write_plan("- [pending] Task 1: Local-only task")
        adapter = FakeLinearAdapter([])

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="both",
            dry_run=False,
            do_pull=False,
            do_push=False,
        )

        self.assertEqual(summary["push_suppressed_auto_promote"], 1)
        self.assertEqual(adapter.pushed, [])
        self.assertEqual(adapter.status_pushes, [])
        self.assertEqual(adapter.field_pushes, [])

    def test_main_auto_promote_routes_to_target_lane_and_suppresses_push(self):
        root = Path(self.tmp)
        other_plan = root / "plans" / "other"
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(other_plan, "- [pending] Task 1: Local task")
        self.write_plan_at(lane_plan, "")
        config_path = root / "vidux.config.json"
        config_path.write_text(
            textwrap.dedent(
                """\
                {
                  "plan_store": { "mode": "inline", "path": "plans" },
                  "inbox_sources": [
                    {
                      "adapter": "linear",
                      "enabled": true,
                      "config": { "auto_promote_target": "plans/linear-lane" }
                    }
                  ]
                }
                """
            ),
            encoding="utf-8",
        )
        adapter = FakeLinearAdapter([self.external_item()])
        original = sync.instantiate_adapter
        try:
            sync.instantiate_adapter = lambda _source: adapter
            with contextlib.redirect_stdout(io.StringIO()):
                code = sync.main([
                    "--config", str(config_path), "--direction", "both",
                ])
        finally:
            sync.instantiate_adapter = original

        self.assertEqual(code, 0)
        self.assertEqual(adapter.pushed, [])
        self.assertFalse((other_plan / sync.INBOX_FILENAME).exists())
        lane_text = (lane_plan / sync.PLAN_FILENAME).read_text(encoding="utf-8")
        self.assertIn(
            "- [pending] BD-1: Fix duplicated card [Source: linear:lin_1]",
            lane_text,
        )
        state = sync.load_state(lane_plan)
        mapping = sync.adapter_state(state, adapter.name)
        self.assertEqual(mapping, {"BD-1": "lin_1"})

    def test_auto_promote_recovers_existing_title_mapping_before_append(self):
        root = Path(self.tmp)
        other_plan = root / "plans" / "other"
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(
            other_plan,
            "- [pending] CE-10 [ETA: 2h]: Fix duplicated card",
        )
        self.write_plan_at(lane_plan, "")
        config_path = root / "vidux.config.json"
        config_path.write_text(
            textwrap.dedent(
                """\
                {
                  "plan_store": { "mode": "inline", "path": "plans" },
                  "inbox_sources": [
                    {
                      "adapter": "linear",
                      "enabled": true,
                      "config": { "auto_promote_target": "plans/linear-lane" }
                    }
                  ]
                }
                """
            ),
            encoding="utf-8",
        )
        adapter = FakeLinearAdapter([self.external_item()])
        original = sync.instantiate_adapter
        try:
            sync.instantiate_adapter = lambda _source: adapter
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = sync.main([
                    "--config", str(config_path), "--direction", "both",
                    "--json",
                ])
        finally:
            sync.instantiate_adapter = original

        self.assertEqual(code, 0)
        self.assertEqual(adapter.pushed, [])
        self.assertFalse((other_plan / sync.INBOX_FILENAME).exists())
        lane_text = (lane_plan / sync.PLAN_FILENAME).read_text(encoding="utf-8")
        self.assertNotIn("[Source: linear:lin_1]", lane_text)
        state = sync.load_state(other_plan)
        mapping = sync.adapter_state(state, adapter.name)
        self.assertEqual(mapping, {"CE-10": "lin_1"})
        payload = json.loads(output.getvalue())
        auto = [
            r for r in payload["results"]
            if r.get("_kind") == "auto_promote"
        ][0]
        self.assertEqual(auto["promoted"], 0)
        self.assertEqual(auto["title_matched"], 1)

    def test_auto_promote_refuses_large_batch_by_default(self):
        root = Path(self.tmp)
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(lane_plan, "")
        config_path = root / "vidux.config.json"
        config_path.write_text(
            textwrap.dedent(
                """\
                {
                  "plan_store": { "mode": "inline", "path": "plans" },
                  "inbox_sources": [
                    {
                      "adapter": "linear",
                      "enabled": true,
                      "config": { "auto_promote_target": "plans/linear-lane" }
                    }
                  ]
                }
                """
            ),
            encoding="utf-8",
        )
        items = [
            self.external_item(
                external_id=f"lin_{i}",
                title=f"Imported card {i}",
            )
            for i in range(sync.DEFAULT_AUTO_PROMOTE_MAX_NEW + 1)
        ]
        adapter = FakeLinearAdapter(items)
        original = sync.instantiate_adapter
        try:
            sync.instantiate_adapter = lambda _source: adapter
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = sync.main([
                    "--config", str(config_path), "--direction", "both",
                    "--json",
                ])
        finally:
            sync.instantiate_adapter = original

        self.assertEqual(code, 2)
        lane_text = (lane_plan / sync.PLAN_FILENAME).read_text(encoding="utf-8")
        self.assertNotIn("Imported card", lane_text)
        payload = json.loads(output.getvalue())
        auto = [
            r for r in payload["results"]
            if r.get("_kind") == "auto_promote"
        ][0]
        self.assertEqual(auto["promoted"], 0)
        self.assertIn("auto_promote_max_new", auto["errors"][0])

    def test_missing_auto_promote_target_fails_closed(self):
        root = Path(self.tmp)
        home_plan = root / "plans" / "home"
        self.write_plan_at(home_plan, "- [pending] Task 1: Local task")
        config_path = root / "vidux.config.json"
        config_path.write_text(
            textwrap.dedent(
                """\
                {
                  "plan_store": { "mode": "inline", "path": "plans" },
                  "inbox_sources": [
                    {
                      "adapter": "linear",
                      "enabled": true,
                      "config": { "auto_promote_target": "plans/missing-lane" }
                    }
                  ]
                }
                """
            ),
            encoding="utf-8",
        )
        adapter = FakeLinearAdapter([self.external_item()])
        original = sync.instantiate_adapter
        try:
            sync.instantiate_adapter = lambda _source: adapter
            with contextlib.redirect_stdout(io.StringIO()):
                code = sync.main([
                    "--config", str(config_path), "--direction", "both",
                ])
        finally:
            sync.instantiate_adapter = original

        self.assertEqual(code, 2)
        self.assertEqual(adapter.pushed, [])
        self.assertFalse((home_plan / sync.INBOX_FILENAME).exists())
        self.assertFalse((root / "plans" / "missing-lane").exists())


if __name__ == "__main__":
    unittest.main()
