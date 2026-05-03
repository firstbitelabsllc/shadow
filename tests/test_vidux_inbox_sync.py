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

    def test_parse_plan_accepts_bold_composite_id_with_slug(self):
        """Bold-wrapped task IDs that embed an em-dash slug + colon must parse.

        Regression for the iOS Resplit fleet where every weekend-push task
        used `**T1 — AAFuZnay: title**` shape, causing
        `vidux-inbox-sync.py --direction=push --only-adapter linear` to
        return `tasks: 0` for resplit-2-0-weekend-push and ocr-moat
        (Leo 2026-05-03: 'i would push ios work into linear otherwise
        how are we gonna track the work?').
        """
        self.write_plan(
            "- [completed] **T1 — AAFuZnay: cap receipt scan hero image height to 220pt** "
            "[Evidence: ASC quote] [Source: linear:lin_1]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "T1")
        self.assertEqual(
            tasks[0].title,
            "cap receipt scan hero image height to 220pt",
        )
        self.assertEqual(tasks[0].source, "linear:lin_1")
        self.assertEqual(tasks[0].evidence, "ASC quote")
        self.assertEqual(tasks[0].status, sync.VidxStatus.COMPLETED)

    def test_parse_plan_accepts_em_dash_separator_no_colon(self):
        """`T-cron-1 — Seed proactive baseline` (em-dash, no colon)."""
        self.write_plan(
            "- [pending] T-cron-1 — Seed proactive sim-walk baseline directory [ETA: 1h]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "T-cron-1")
        self.assertEqual(
            tasks[0].title,
            "Seed proactive sim-walk baseline directory",
        )
        self.assertEqual(tasks[0].eta_hours, 1.0)

    def test_parse_plan_accepts_no_separator_body(self):
        """`T1 Add value-mix brake subsection` (whitespace-only separator)."""
        self.write_plan(
            "- [pending] T1 Add value-mix brake subsection [Evidence: usage report]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "T1")
        self.assertEqual(tasks[0].title, "Add value-mix brake subsection")

    def test_parse_plan_accepts_task_keyword_prefix(self):
        """`Task MOU-1: Ship Moussey dashboard` (mouseey/moussey style)."""
        self.write_plan(
            "- [completed] Task MOU-1: Ship Moussey dashboard entrypoint"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "MOU-1")
        self.assertEqual(tasks[0].title, "Ship Moussey dashboard entrypoint")

    def test_parse_plan_accepts_digit_leading_id(self):
        """`4.1 Continue README iteration` (claudux-evolution style)."""
        self.write_plan(
            "- [pending] 4.1 Continue README iteration via claudux-opensource cron"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "4.1")
        self.assertEqual(
            tasks[0].title,
            "Continue README iteration via claudux-opensource cron",
        )

    def test_parse_plan_accepts_pre_id_bracket_annotation(self):
        """`[owner: claude] M1: Smoke test` (voxtral-reader-addon style)."""
        self.write_plan(
            "- [completed] [owner: claude] M1: Smoke test mlx-audio Voxtral [ETA: 0.5h]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "M1")
        self.assertEqual(tasks[0].title, "Smoke test mlx-audio Voxtral")
        self.assertEqual(tasks[0].eta_hours, 0.5)

    def test_parse_plan_accepts_backtick_wrapped_status(self):
        """``` `[pending]` **P1 — Domain types** ``` (ocr-moat style)."""
        self.write_plan(
            "- `[pending]` **P1 — Domain types + provider protocol + Azure adapter** "
            "[Sub-plan: tasks/P1-domain-types-protocol/PLAN.md] [ETA: 8h]"
        )

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "P1")
        self.assertEqual(
            tasks[0].title,
            "Domain types + provider protocol + Azure adapter",
        )
        self.assertEqual(tasks[0].eta_hours, 8.0)

    def test_parse_plan_accepts_tasks_phases_header(self):
        """`## Tasks (Phases)` header variant (ocr-moat)."""
        plan = textwrap.dedent(
            """\
            # Test
            ## Tasks (Phases)
            - [pending] **P1 — Domain types** [ETA: 8h] — Lock the contract.
            - [pending] **P2 — Fixture corpus** [ETA: 6h] — JSONL frozen.
            ## Decision Log
            """
        )
        (self.plan_dir / "PLAN.md").write_text(plan, encoding="utf-8")

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].id, "P1")
        self.assertEqual(tasks[1].id, "P2")

    def test_parse_plan_does_not_match_non_status_brackets(self):
        """Defence in depth: `[Source:]`, `[DIRECTION]`, `[deferred]` are not tasks.

        Vidux's status FSM is strictly pending|in_progress|in_review|
        completed|blocked. `[deferred]` is intentionally unsupported (see
        `adapters/base.VidxStatus`) — Resplit's deferred-to-2.0.1 rows MUST
        NOT push to Linear.
        """
        plan = textwrap.dedent(
            """\
            # Test
            ## Tasks
            - [Source: codebase] not a task
            - [DIRECTION] not a task
            - [deferred] T8: replace icon (must not parse — deferred is not a vidux state)
            - [pending] T9: real task
            ## Decision Log
            """
        )
        (self.plan_dir / "PLAN.md").write_text(plan, encoding="utf-8")

        tasks = sync.parse_plan(self.plan_dir / sync.PLAN_FILENAME)

        # Only the [pending] row counts. The bracketed annotations and
        # the [deferred] row must be skipped.
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "T9")

    def test_flip_plan_statuses_handles_bold_composite_ids(self):
        """flip_plan_statuses must use the same lenient matcher as parse_plan.

        Otherwise a status-flip request for `T1` would silently no-op
        because the canonical regex doesn't match `**T1 — AAFuZnay: ...**`.
        """
        self.write_plan(
            "- [pending] **T1 — AAFuZnay: cap receipt scan**"
        )
        plan_path = self.plan_dir / sync.PLAN_FILENAME

        flipped = sync.flip_plan_statuses(
            plan_path,
            {"T1": sync.VidxStatus.COMPLETED},
            dry_run=False,
        )

        self.assertEqual(flipped, 1)
        text = plan_path.read_text(encoding="utf-8")
        self.assertIn("[completed] **T1 — AAFuZnay:", text)
        self.assertNotIn("[pending] **T1 —", text)

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

    def test_pull_skips_completed_novel_items_for_inbox(self):
        self.write_plan("")
        adapter = FakeLinearAdapter(
            [self.external_item(status=sync.VidxStatus.COMPLETED)]
        )

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="pull",
            dry_run=False,
        )

        self.assertEqual(summary["inbox_appended"], 0)
        self.assertEqual(summary["completed_novel_skipped"], 1)
        self.assertFalse((self.plan_dir / sync.INBOX_FILENAME).exists())

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

    def test_both_pull_completed_does_not_push_stale_local_status(self):
        self.write_plan(
            "- [in_review] BD-1: PR landed remotely [Source: linear:lin_1]"
        )
        adapter = FakeLinearAdapter(
            [self.external_item(status=sync.VidxStatus.COMPLETED)]
        )

        summary = sync.sync_plan_with_adapter(
            self.plan_dir,
            adapter,
            direction="both",
            dry_run=False,
        )

        self.assertEqual(summary["plan_flipped"], 1)
        self.assertEqual(summary["flipped_ids"], ["BD-1"])
        self.assertEqual(adapter.status_pushes, [])
        plan_text = (self.plan_dir / sync.PLAN_FILENAME).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "- [completed] BD-1: PR landed remotely [Source: linear:lin_1]",
            plan_text,
        )

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

    def test_main_auto_promote_skips_completed_novel_items(self):
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
        adapter = FakeLinearAdapter([
            self.external_item(
                title="Already shipped",
                status=sync.VidxStatus.COMPLETED,
            )
        ])
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
        lane_text = (lane_plan / sync.PLAN_FILENAME).read_text(encoding="utf-8")
        self.assertNotIn("Already shipped", lane_text)
        payload = json.loads(output.getvalue())
        auto = [
            r for r in payload["results"]
            if r.get("_kind") == "auto_promote"
        ][0]
        self.assertEqual(auto["promoted"], 0)
        self.assertEqual(auto["completed_skipped"], 1)
        self.assertEqual(auto["errors"], [])

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

    def test_push_to_external_opt_in_overrides_auto_promote_suppression(self):
        """`push_only_for_plans` lets opted-in plans push brand-new external issues
        even when `auto_promote_target` would normally suppress that creation
        for the rest of the fleet.

        Use case (Leo 2026-05-03): iOS-lane plans (resplit-2-0-weekend-push,
        ocr-moat) should push their tasks to Linear while the rest of the fleet
        stays in PULL-only mode (auto_promote_target keeps non-iOS plans from
        flooding Linear with 267 fleet tasks).
        """
        root = Path(self.tmp)
        ios_plan = root / "plans" / "resplit-2-0-weekend-push"
        other_plan = root / "plans" / "other-fleet-plan"
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(
            ios_plan,
            "- [pending] T1: iOS task that should push to Linear",
        )
        self.write_plan_at(
            other_plan,
            "- [pending] T1: Non-iOS task that must stay suppressed",
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
                        "auto_promote_target": "plans/linear-lane",
                        "push_only_for_plans": ["plans/resplit-2-0-weekend-push"]
                      }
                    }
                  ]
                }
                """
            ),
            encoding="utf-8",
        )
        adapter = FakeLinearAdapter([])
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
        # iOS plan's task pushed to Linear (override fired)
        self.assertEqual(len(adapter.pushed), 1)
        self.assertEqual(adapter.pushed[0].id, "T1")
        self.assertEqual(
            adapter.pushed[0].title,
            "iOS task that should push to Linear",
        )
        # Non-iOS plan's task stayed suppressed (default behavior preserved)
        payload = json.loads(output.getvalue())
        other_summary = [
            r for r in payload["results"]
            if r.get("plan", "").endswith("other-fleet-plan")
        ][0]
        self.assertEqual(other_summary["push_suppressed_auto_promote"], 1)
        self.assertEqual(other_summary["pushed"], 0)

    def test_push_to_external_default_unset_preserves_existing_suppression(self):
        """When `push_only_for_plans` is unset / empty, every plan stays suppressed
        — preserves the pre-feature contract for the 267-fleet-task case."""
        root = Path(self.tmp)
        plan_a = root / "plans" / "plan-a"
        plan_b = root / "plans" / "plan-b"
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(plan_a, "- [pending] T1: Local-only task A")
        self.write_plan_at(plan_b, "- [pending] T1: Local-only task B")
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
        adapter = FakeLinearAdapter([])
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
        # No push fired anywhere; all plans suppressed by auto_promote_target.
        self.assertEqual(adapter.pushed, [])
        payload = json.loads(output.getvalue())
        per_plan = [
            r for r in payload["results"]
            if r.get("adapter") == "linear" and "plan" in r
        ]
        self.assertEqual(
            sum(r["push_suppressed_auto_promote"] for r in per_plan),
            2,
        )
        self.assertEqual(sum(r["pushed"] for r in per_plan), 0)

    def test_push_to_external_path_matching_relative_and_absolute(self):
        """`push_only_for_plans` accepts both relative (resolved against the config
        file's parent dir) and absolute paths. Both forms must opt the listed
        plan into PUSH; entries that don't match any plan_dir are silently
        ignored (no error — operator may pre-stage paths)."""
        root = Path(self.tmp)
        rel_plan = root / "plans" / "rel-plan"
        abs_plan = root / "plans" / "abs-plan"
        lane_plan = root / "plans" / "linear-lane"
        self.write_plan_at(rel_plan, "- [pending] T1: Relative-path opt-in task")
        self.write_plan_at(abs_plan, "- [pending] T1: Absolute-path opt-in task")
        self.write_plan_at(lane_plan, "")
        config_path = root / "vidux.config.json"
        # Mix relative + absolute entries to exercise both branches of the
        # path-resolution logic.
        config_payload = {
            "plan_store": {"mode": "inline", "path": "plans"},
            "inbox_sources": [
                {
                    "adapter": "linear",
                    "enabled": True,
                    "config": {
                        "allow_team_wide": True,
                        "auto_promote_target": "plans/linear-lane",
                        "push_only_for_plans": [
                            "plans/rel-plan",
                            str(abs_plan.resolve()),
                        ],
                    },
                }
            ],
        }
        config_path.write_text(json.dumps(config_payload), encoding="utf-8")
        adapter = FakeLinearAdapter([])
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
        # Both opted-in plans pushed their tasks (count == 2).
        self.assertEqual(len(adapter.pushed), 2)
        pushed_titles = sorted(t.title for t in adapter.pushed)
        self.assertEqual(
            pushed_titles,
            ["Absolute-path opt-in task", "Relative-path opt-in task"],
        )

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
