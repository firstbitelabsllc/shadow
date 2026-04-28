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
        self.pr_links = []

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

    def sync_pull_request_link(self, external_id, pr, *, dry_run=False):
        self.pr_links.append((external_id, pr["number"], dry_run))
        return {
            "issue_identifier": "EVE-123",
            "attached": True,
            "commented": True,
            "already_attached": False,
            "already_commented": False,
        }


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

    def test_source_marker_skips_backtick_documentation(self):
        """Backtick-quoted [Source: ...] in task prose must not become a mapping.

        Regression for the 3-error-per-cycle leak observed 2026-04-27 after
        PR #73 enabled push_status for auto-promoted tasks: literal example
        syntax like ``scans for `[Source: linear:<uuid>]`` had been parsed
        as a real source marker and persisted ``<uuid>`` into state.
        """
        self.write_plan(
            "- [completed] T-1: Fix sync. "
            "Push-half scans `[Source: linear:<uuid>]` markers BEFORE pushing. "
            "[Shipped: abc123]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertIsNone(tasks[0].source)

    def test_source_external_id_rejects_placeholder_shape(self):
        from adapters.base import PlanTask, VidxStatus

        task = PlanTask(
            id="T-1", title="x", status=VidxStatus.PENDING,
            source="linear:<uuid>",
        )
        self.assertIsNone(sync.source_external_id(task, "linear"))

    def test_adapter_state_filters_placeholder_pollution_on_load(self):
        """Pre-existing polluted entries self-heal without manual JSON edit."""
        state = {
            "adapters": {
                "linear": {
                    "task_to_external": {
                        "Task 12": "<uuid>",
                        "Task 8": "<id>",
                        "BD-31": "3199f57d-real-uuid",
                    }
                }
            }
        }

        mapping = sync.adapter_state(state, "linear")

        self.assertEqual(mapping, {"BD-31": "3199f57d-real-uuid"})

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

    def test_completed_mapped_task_pushes_terminal_status(self):
        self.write_plan(
            "- [completed] Task 1: Shipped work [Source: linear:lin_1]"
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
            adapter.status_pushes, [("lin_1", sync.VidxStatus.COMPLETED)]
        )
        self.assertEqual(adapter.field_pushes, [])
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

    def test_main_auto_promote_routes_to_target_lane_and_suppresses_new_push(self):
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
                      "config": {
                        "allow_team_wide": true,
                        "auto_promote_target": "plans/linear-lane"
                      }
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

    def test_main_auto_promote_pushes_status_for_source_mapped_tasks(self):
        root = Path(self.tmp)
        other_plan = root / "plans" / "other"
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(other_plan, "- [pending] Task 1: Local task")
        self.write_plan_at(
            lane_plan,
            "- [completed] BD-1: Fix duplicated card [Source: linear:lin_1]",
        )
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
                      "config": {
                        "allow_team_wide": true,
                        "auto_promote_target": "plans/linear-lane"
                      }
                    }
                  ]
                }
                """
            ),
            encoding="utf-8",
        )
        adapter = FakeLinearAdapter(
            [self.external_item(status=sync.VidxStatus.PENDING)]
        )
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
        self.assertEqual(
            adapter.status_pushes, [("lin_1", sync.VidxStatus.COMPLETED)]
        )
        self.assertFalse((other_plan / sync.INBOX_FILENAME).exists())
        payload = json.loads(output.getvalue())
        summaries = [
            r for r in payload["results"]
            if r.get("adapter") == "linear" and "plan" in r
        ]
        self.assertEqual(
            sum(r["push_suppressed_auto_promote"] for r in summaries),
            1,
        )

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
                      "config": {
                        "allow_team_wide": true,
                        "auto_promote_target": "plans/linear-lane"
                      }
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
                      "config": {
                        "allow_team_wide": true,
                        "auto_promote_target": "plans/linear-lane"
                      }
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
                      "config": {
                        "allow_team_wide": true,
                        "auto_promote_target": "plans/missing-lane"
                      }
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

    def test_linear_pr_sweep_links_matching_source_task_and_updates_body(self):
        self.write_plan(
            "- [in_review] BD-1: Wire Linear links [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter([])
        body_files: list[str] = []

        class Result:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(cmd, **_kwargs):
            if cmd[:3] == ["gh", "repo", "view"]:
                return Result(stdout=json.dumps({"nameWithOwner": "leojkwan/repo"}))
            if cmd[:4] == ["gh", "pr", "list", "--repo"]:
                state = cmd[cmd.index("--state") + 1]
                if state == "merged":
                    return Result(stdout="[]")
                return Result(stdout=json.dumps([
                    {
                        "number": 42,
                        "url": "https://github.com/leojkwan/repo/pull/42",
                        "title": "fix(linear): link PRs",
                        "id": "PR_node",
                        "isDraft": False,
                        "state": "OPEN",
                        "mergedAt": None,
                        "headRefName": "codex/linear-links",
                        "body": "Lane: codex/test | Plan task: bd-1 | ship it",
                    }
                ]))
            if cmd[:3] == ["gh", "pr", "edit"]:
                body_file = cmd[cmd.index("--body-file") + 1]
                body_files.append(Path(body_file).read_text(encoding="utf-8"))
                return Result()
            raise AssertionError(f"unexpected command: {cmd}")

        original_run = sync.subprocess.run
        try:
            sync.subprocess.run = fake_run
            summary = sync.sync_prs_to_project(
                adapter,
                self.plan_dir,
                dry_run=False,
                task_index=sync.task_index_by_id([self.plan_dir]),
            )
        finally:
            sync.subprocess.run = original_run

        self.assertEqual(adapter.pr_links, [("lin_1", 42, False)])
        self.assertEqual(summary["linked"], 1)
        self.assertEqual(summary["attached"], 1)
        self.assertEqual(summary["commented"], 1)
        self.assertEqual(summary["body_updates"], 1)
        self.assertIn("Linear: EVE-123", body_files[0])

    def test_linear_pr_sweep_skips_pr_without_plan_task_body_ref(self):
        self.write_plan(
            "- [in_review] BD-1: Wire Linear links [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter([])

        class Result:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(cmd, **_kwargs):
            if cmd[:3] == ["gh", "repo", "view"]:
                return Result(stdout=json.dumps({"nameWithOwner": "leojkwan/repo"}))
            if cmd[:4] == ["gh", "pr", "list", "--repo"]:
                state = cmd[cmd.index("--state") + 1]
                if state == "merged":
                    return Result(stdout="[]")
                return Result(stdout=json.dumps([
                    {
                        "number": 42,
                        "url": "https://github.com/leojkwan/repo/pull/42",
                        "title": "fix(linear): link PRs",
                        "id": "PR_node",
                        "isDraft": False,
                        "state": "OPEN",
                        "mergedAt": None,
                        "headRefName": "codex/linear-links",
                        "body": "No plan metadata yet",
                    }
                ]))
            raise AssertionError(f"unexpected command: {cmd}")

        original_run = sync.subprocess.run
        try:
            sync.subprocess.run = fake_run
            summary = sync.sync_prs_to_project(
                adapter,
                self.plan_dir,
                dry_run=False,
                task_index=sync.task_index_by_id([self.plan_dir]),
            )
        finally:
            sync.subprocess.run = original_run

        self.assertEqual(adapter.pr_links, [])
        self.assertEqual(summary["linked"], 0)
        self.assertEqual(summary["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
