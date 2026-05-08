"""Regression tests for the Linear adapter (`adapters/linear.py`).

Focus: Task 14 — canceled / duplicate state.type filtering. Pulling these
state types into the sync pipeline causes `_status_from_state_id` to fall
back to PENDING (the canceled-state UUIDs are not in user `state_mapping`),
which lets the sync script auto-promote them as fresh `BD-*` tasks. We block
both at the GraphQL level (server-side `state.type neq "canceled"` filter)
and as a defensive client-side skip in `fetch_inbox`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.base import ExternalItem, PlanTask, VidxStatus  # noqa: E402
from adapters.linear import LinearAdapter  # noqa: E402


def _make_adapter(
    *,
    project_id: str | None = None,
    project_name: str | None = None,
    allow_team_wide: bool = False,
    allow_unguarded_project: bool = False,
    label_names: list[str] | None = None,
    managed_labels: dict[str, Any] | None = None,
) -> LinearAdapter:
    """Build a LinearAdapter without touching disk or the network.

    Token file is set to a path the adapter never reads (we patch `_graphql`
    on the instance, which short-circuits before token loading).
    """
    config: dict[str, Any] = {
        "token_file": "/dev/null",
        "team_id": "team-uuid",
        "state_mapping": {
            "pending": "state-backlog",
            "in_progress": "state-started",
            "in_review": "state-review",
            "completed": "state-done",
        },
    }
    if project_id is not None:
        config["project_id"] = project_id
    if project_name is not None:
        config["project_name"] = project_name
    if allow_team_wide:
        config["allow_team_wide"] = True
    if allow_unguarded_project:
        config["allow_unguarded_project"] = True
    if label_names is not None:
        config["label_names"] = label_names
    if managed_labels is not None:
        config["managed_labels"] = managed_labels
    return LinearAdapter(config)


class GraphQLRecorder:
    """Capture (query, variables) calls to `_graphql` and replay canned data."""

    def __init__(self, payload: dict[str, Any] | list[dict[str, Any]]):
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.payloads = payload if isinstance(payload, list) else [payload]

    def __call__(self, query: str, variables: dict[str, Any] | None = None,
                 *, max_attempts: int = 4) -> dict[str, Any]:
        self.calls.append((query, dict(variables or {})))
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        return self.payloads[index]


def _project_payload(
    *,
    name: str = "repo-web",
    project_id: str = "project-uuid",
    team_id: str = "team-uuid",
) -> dict[str, Any]:
    return {
        "project": {
            "id": project_id,
            "name": name,
            "teams": {
                "nodes": [
                    {"id": team_id, "key": "APP", "name": "ExampleTeam"},
                ],
            },
        }
    }


class FetchInboxFiltersCanceled(unittest.TestCase):
    """`canceled`-typed nodes that slip past the server filter must be dropped."""

    def _nodes(self) -> dict[str, Any]:
        return {
            "issues": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "id": "live-1",
                        "identifier": "EVE-100",
                        "title": "Active backlog item",
                        "description": "",
                        "state": {"id": "state-backlog", "name": "Backlog",
                                  "type": "backlog"},
                        "labels": {"nodes": []},
                        "updatedAt": "2026-04-26T00:00:00Z",
                    },
                    {
                        "id": "canceled-1",
                        "identifier": "EVE-101",
                        "title": "Canceled card that must not leak",
                        "description": "",
                        "state": {"id": "state-canceled", "name": "Canceled",
                                  "type": "canceled"},
                        "labels": {"nodes": []},
                        "updatedAt": "2026-04-26T00:00:00Z",
                    },
                    {
                        "id": "duplicate-1",
                        "identifier": "EVE-102",
                        "title": "Duplicate state is canceled-typed too",
                        "description": "",
                        "state": {"id": "state-duplicate", "name": "Duplicate",
                                  "type": "canceled"},
                        "labels": {"nodes": []},
                        "updatedAt": "2026-04-26T00:00:00Z",
                    },
                    {
                        "id": "live-2",
                        "identifier": "EVE-103",
                        "title": "In-progress card",
                        "description": "",
                        "state": {"id": "state-started", "name": "In Progress",
                                  "type": "started"},
                        "labels": {"nodes": []},
                        "updatedAt": "2026-04-26T00:00:00Z",
                    },
                    {
                        "id": "live-3",
                        "identifier": "EVE-104",
                        "title": "Completed card stays — completed != canceled",
                        "description": "",
                        "state": {"id": "state-done", "name": "Done",
                                  "type": "completed"},
                        "labels": {"nodes": []},
                        "updatedAt": "2026-04-26T00:00:00Z",
                    },
                ],
            }
        }

    def test_team_query_drops_canceled_type(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder(self._nodes())
        adapter._graphql = recorder  # type: ignore[assignment]

        items = adapter.fetch_inbox()

        ids = [it.external_id for it in items]
        self.assertIn("live-1", ids)
        self.assertIn("live-2", ids)
        self.assertIn("live-3", ids)
        self.assertNotIn("canceled-1", ids)
        self.assertNotIn("duplicate-1", ids)
        self.assertEqual(len(items), 3)

    def test_project_query_drops_canceled_type(self):
        adapter = _make_adapter(
            project_id="project-uuid",
            allow_unguarded_project=True,
        )
        recorder = GraphQLRecorder(self._nodes())
        adapter._graphql = recorder  # type: ignore[assignment]

        items = adapter.fetch_inbox()

        ids = [it.external_id for it in items]
        self.assertNotIn("canceled-1", ids)
        self.assertNotIn("duplicate-1", ids)
        self.assertEqual(len(items), 3)

    def test_project_name_validates_before_project_fetch(self):
        adapter = _make_adapter(
            project_id="project-uuid",
            project_name="repo-web",
        )
        recorder = GraphQLRecorder([_project_payload(), self._nodes()])
        adapter._graphql = recorder  # type: ignore[assignment]

        items = adapter.fetch_inbox()

        self.assertEqual(len(items), 3)
        self.assertIn("project(id: $projectId)", recorder.calls[0][0])
        self.assertEqual(
            recorder.calls[0][1],
            {"projectId": "project-uuid"},
        )
        self.assertIn("issues(", recorder.calls[1][0])

    def test_project_name_mismatch_fails_closed(self):
        adapter = _make_adapter(
            project_id="project-uuid",
            project_name="repo-web",
        )
        recorder = GraphQLRecorder(_project_payload(name="Launch Queue"))
        adapter._graphql = recorder  # type: ignore[assignment]

        with self.assertRaisesRegex(
            Exception,
            "Launch Queue.*expected 'repo-web'",
        ):
            adapter.fetch_inbox()

        self.assertEqual(len(recorder.calls), 1)

    def test_project_without_teams_fails_closed(self):
        adapter = _make_adapter(
            project_id="project-uuid",
            project_name="repo-web",
        )
        payload = _project_payload()
        payload["project"]["teams"]["nodes"] = []
        recorder = GraphQLRecorder(payload)
        adapter._graphql = recorder  # type: ignore[assignment]

        with self.assertRaisesRegex(Exception, "has no teams assigned"):
            adapter.fetch_inbox()

        self.assertEqual(len(recorder.calls), 1)

    def test_project_name_mismatch_blocks_issue_create(self):
        adapter = _make_adapter(
            project_id="project-uuid",
            project_name="repo-web",
        )
        recorder = GraphQLRecorder(_project_payload(name="Launch Queue"))
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="BD-1",
            title="Do not create on wrong project",
            status=VidxStatus.PENDING,
        )

        with self.assertRaisesRegex(
            Exception,
            "Launch Queue.*expected 'repo-web'",
        ):
            adapter.push_task(task)

        self.assertEqual(len(recorder.calls), 1)
        self.assertNotIn("issueCreate", recorder.calls[0][0])


class GraphQLQueryShape(unittest.TestCase):
    """Both queries MUST encode the server-side state-type filter."""

    def test_team_query_includes_state_type_filter(self):
        self.assertIn(
            'state: { type: { neq: "canceled" } }',
            LinearAdapter._ISSUES_QUERY_TEAM,
        )

    def test_project_query_includes_state_type_filter(self):
        self.assertIn(
            'state: { type: { neq: "canceled" } }',
            LinearAdapter._ISSUES_QUERY_PROJECT,
        )

    def test_drop_state_types_includes_canceled(self):
        self.assertIn("canceled", LinearAdapter._DROP_STATE_TYPES)

    def test_project_name_requires_project_id(self):
        with self.assertRaisesRegex(ValueError, "project_name.*project_id"):
            _make_adapter(project_name="repo-web")

    def test_team_wide_source_requires_explicit_allowlist(self):
        with self.assertRaisesRegex(ValueError, "allow_team_wide"):
            _make_adapter()

    def test_project_id_requires_project_name_or_allowlist(self):
        with self.assertRaisesRegex(ValueError, "project_id.*project_name"):
            _make_adapter(project_id="project-uuid")

    def test_explicit_unguarded_project_allowlist_passes(self):
        adapter = _make_adapter(
            project_id="project-uuid",
            allow_unguarded_project=True,
        )

        self.assertEqual(adapter.project_id, "project-uuid")
        self.assertIsNone(adapter.project_name)

    def test_allow_team_wide_rejected_with_project_id(self):
        with self.assertRaisesRegex(ValueError, "allow_team_wide.*project_id"):
            _make_adapter(
                project_id="project-uuid",
                project_name="repo-web",
                allow_team_wide=True,
            )

    def test_project_lookup_query_reads_name_and_teams(self):
        self.assertIn("project(id: $projectId)", LinearAdapter._PROJECT_LOOKUP_QUERY)
        self.assertIn("name", LinearAdapter._PROJECT_LOOKUP_QUERY)
        self.assertIn("teams(first: 20)", LinearAdapter._PROJECT_LOOKUP_QUERY)

    def test_label_names_must_be_non_empty_strings(self):
        with self.assertRaisesRegex(ValueError, "label_names"):
            _make_adapter(allow_team_wide=True, label_names=["repo:vidux", ""])

    def test_managed_labels_reject_unknown_keys(self):
        with self.assertRaisesRegex(ValueError, "managed_labels.*unknown"):
            _make_adapter(
                allow_team_wide=True,
                managed_labels={"repo": "repo:vidux", "mystery": "nope"},
            )


class ManagedLabels(unittest.TestCase):
    @staticmethod
    def _label_payload(label_id: str, name: str) -> dict[str, Any]:
        return {"issueLabels": {"nodes": [{"id": label_id, "name": name}]}}

    @staticmethod
    def _create_payload() -> dict[str, Any]:
        return {"issueCreate": {"success": True, "issue": {"id": "lin-issue-1"}}}

    def test_push_task_applies_label_names_and_managed_repo_source_labels(self):
        adapter = _make_adapter(
            allow_team_wide=True,
            label_names=["fleet"],
            managed_labels={
                "repo": "repo:vidux",
                "source": "source:vidux",
            },
        )
        recorder = GraphQLRecorder([
            self._label_payload("label-fleet", "fleet"),
            self._label_payload("label-repo", "repo:vidux"),
            self._label_payload("label-source", "source:vidux"),
            self._create_payload(),
        ])
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="BD-1",
            title="Label managed issue",
            status=VidxStatus.PENDING,
        )

        external_id = adapter.push_task(task)

        self.assertEqual(external_id, "lin-issue-1")
        issue_input = recorder.calls[-1][1]["input"]
        self.assertEqual(
            issue_input["labelIds"],
            ["label-fleet", "label-repo", "label-source"],
        )


class BodyRendering(unittest.TestCase):
    def test_render_body_includes_details_tags_plan_location_and_gaps(self):
        task = PlanTask(
            id="P1",
            title="Domain types + provider protocol + Azure adapter",
            status=VidxStatus.PENDING,
            details="Lock the contract. ScannedReceipt becomes canonical.",
            evidence="projects/ocr-moat/PLAN.md:53",
            eta_hours=8,
            source="linear:lin_1",
            tags={
                "Sub-plan": "tasks/P1-domain-types-protocol/PLAN.md",
                "ETA": "8h",
                "Evidence": "projects/ocr-moat/PLAN.md:53",
                "Source": "linear:lin_1",
            },
            plan_path="/Users/leokwan/Development/vidux/projects/ocr-moat/PLAN.md",
            line_number=53,
        )

        body = LinearAdapter._render_body(task)

        self.assertIn("## Details", body)
        self.assertIn("ScannedReceipt becomes canonical", body)
        self.assertIn("## Tags\n- Sub-plan:", body)
        self.assertIn("tasks/P1-domain-types-protocol/PLAN.md", body)
        self.assertIn("## Plan", body)
        self.assertIn("PLAN.md:53", body)
        self.assertIn("## ETA\n8h", body)
        self.assertNotIn("## Intake Gaps", body)

    def test_render_body_surfaces_title_only_intake_gaps(self):
        task = PlanTask(
            id="BD-1",
            title="Receipt Lab dev-app surface",
            status=VidxStatus.PENDING,
            plan_path="/tmp/PLAN.md",
            line_number=12,
        )

        body = LinearAdapter._render_body(task)

        self.assertIn("## Purpose\nReceipt Lab dev-app surface", body)
        self.assertIn("## Intake Gaps", body)
        self.assertIn("Missing `[Evidence: ...]`", body)
        self.assertIn("Missing `[ETA: Xh]`", body)

    def test_sync_task_metadata_updates_stale_description(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder({"issueUpdate": {"success": True}})
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="BD-1",
            title="Receipt Lab dev-app surface",
            status=VidxStatus.PENDING,
            plan_path="/tmp/PLAN.md",
            line_number=12,
        )
        remote = ExternalItem(
            external_id="lin_1",
            title="Receipt Lab dev-app surface",
            status=VidxStatus.PENDING,
            fields={"_description": "## Purpose\nReceipt Lab dev-app surface"},
        )

        changed = adapter.sync_task_metadata("lin_1", task, remote=remote)

        self.assertTrue(changed)
        issue_input = recorder.calls[-1][1]["input"]
        self.assertNotIn("title", issue_input)
        self.assertIn("## Intake Gaps", issue_input["description"])

    def test_sync_task_metadata_noops_when_title_and_description_match(self):
        adapter = _make_adapter(allow_team_wide=True)
        task = PlanTask(
            id="BD-1",
            title="Receipt Lab dev-app surface",
            status=VidxStatus.PENDING,
            plan_path="/tmp/PLAN.md",
            line_number=12,
        )
        remote = ExternalItem(
            external_id="lin_1",
            title=task.title,
            status=VidxStatus.PENDING,
            fields={"_description": LinearAdapter._render_body(task)},
        )

        changed = adapter.sync_task_metadata("lin_1", task, remote=remote)

        self.assertFalse(changed)


class EnrichmentFields(unittest.TestCase):
    """MT-5 regression for the 2026-05-08 "vague bullshit" Linear push.

    push_task() must populate four enrichment fields beyond title +
    description: priority, estimate, auto-derived labels (priority / surface),
    and a vidux-trace footer in the description body. sync_task_metadata()
    must reconcile priority + estimate on already-mapped issues without
    requiring a remint.
    """

    @staticmethod
    def _create_payload() -> dict[str, Any]:
        return {"issueCreate": {"success": True, "issue": {"id": "lin-issue-1"}}}

    @staticmethod
    def _label_payload(label_id: str, name: str) -> dict[str, Any]:
        return {"issueLabels": {"nodes": [{"id": label_id, "name": name}]}}

    def test_priority_extracted_from_priority_tag(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder([
            self._label_payload("label-priority-p0", "priority:P0"),
            self._label_payload("label-surface-receipt-detail",
                                "surface:receipt-detail"),
            self._create_payload(),
        ])
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="Fix receipt-detail crash",
            status=VidxStatus.PENDING,
            tags={"Priority": "P0", "Surface": "receipt-detail"},
            eta_hours=0.5,
            plan_path="/tmp/PLAN.md",
            line_number=12,
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertEqual(issue_input["priority"], 1, "P0 → Linear Urgent=1")

    def test_priority_extracted_from_title_token(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder([
            self._label_payload("label-priority-p1", "priority:P1"),
            self._create_payload(),
        ])
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="P1 — Wire Live-Split add-people gate",
            status=VidxStatus.PENDING,
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertEqual(issue_input["priority"], 2, "P1 → Linear High=2")

    def test_priority_omitted_when_unknown(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder(self._create_payload())
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="Plain task with no priority hint",
            status=VidxStatus.PENDING,
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertNotIn("priority", issue_input,
                         "vague task → no priority guess")

    def test_estimate_mapped_from_eta_hours_xs(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder(self._create_payload())
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="Quick lint fix",
            status=VidxStatus.PENDING,
            eta_hours=0.5,
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertEqual(issue_input["estimate"], 1, "0.5h → XS=1")

    def test_estimate_mapped_from_eta_hours_xl(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder(self._create_payload())
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="Multi-day platform migration",
            status=VidxStatus.PENDING,
            eta_hours=16,
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertEqual(issue_input["estimate"], 8, "16h → XL=8")

    def test_estimate_omitted_when_eta_missing(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder(self._create_payload())
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="Vague task without ETA",
            status=VidxStatus.PENDING,
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertNotIn("estimate", issue_input,
                         "missing ETA → no estimate guess")

    def test_auto_derived_priority_and_surface_labels(self):
        adapter = _make_adapter(
            allow_team_wide=True,
            label_names=["fleet"],
        )
        recorder = GraphQLRecorder([
            self._label_payload("label-fleet", "fleet"),
            self._label_payload("label-priority-p0", "priority:P0"),
            self._label_payload("label-surface-receipt-detail",
                                "surface:receipt-detail"),
            self._create_payload(),
        ])
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="Fix receipt-detail crash",
            status=VidxStatus.PENDING,
            tags={"Priority": "P0", "Surface": "Receipt Detail"},
        )

        adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]
        self.assertIn("label-fleet", issue_input["labelIds"])
        self.assertIn("label-priority-p0", issue_input["labelIds"])
        self.assertIn("label-surface-receipt-detail", issue_input["labelIds"])

    def test_render_body_includes_vidux_trace_footer(self):
        task = PlanTask(
            id="T1",
            title="Fix the thing",
            status=VidxStatus.PENDING,
            plan_path="/Users/leokwan/Development/resplit-ios/.cursor/plans/foo.plan.md",
            line_number=42,
        )

        body = LinearAdapter._render_body(task)

        self.assertIn("vidux-trace", body)
        self.assertIn(
            "/Users/leokwan/Development/resplit-ios/.cursor/plans/foo.plan.md:42",
            body,
        )
        self.assertIn("task `T1`", body)

    def test_render_body_omits_trace_footer_when_no_plan_path(self):
        task = PlanTask(
            id="T1",
            title="Synthetic task",
            status=VidxStatus.PENDING,
        )

        body = LinearAdapter._render_body(task)

        self.assertNotIn("vidux-trace", body)

    def test_full_enrichment_round_trip_payload(self):
        """End-to-end: a fully-tagged PlanTask produces a Linear card with
        every enrichment field populated. This is the canonical "no more
        vague bullshit" assertion — if it fails, Leo's complaint resurfaces.
        """
        adapter = _make_adapter(
            allow_team_wide=True,
            label_names=["vidux", "vidux:resplit-ios"],
        )
        recorder = GraphQLRecorder([
            self._label_payload("label-vidux", "vidux"),
            self._label_payload("label-vidux-ios", "vidux:resplit-ios"),
            self._label_payload("label-priority-p0", "priority:P0"),
            self._label_payload("label-surface-pinpad", "surface:pinpad"),
            self._create_payload(),
        ])
        adapter._graphql = recorder  # type: ignore[assignment]
        task = PlanTask(
            id="T1",
            title="P0 — Pinpad popover cut off on right edge",
            status=VidxStatus.PENDING,
            details=(
                "Repro: open receipt detail → tap amount → popover renders "
                "outside frame. Fix: clamp x to safeArea.maxX - popover.width."
            ),
            evidence=(
                "ResplitCore/UI/Components/EditAmountPopoverField.swift:142;"
                "docs/autobot-evidence/2026-04-19-pinpad-popover/before.jpg"
            ),
            investigation=(
                ".cursor/plans/investigations/pinpad-popover-cut-off-2026-04-19.md"
            ),
            eta_hours=2,
            source="asc:ACHQtix2QbIYfdzFwO6tifU",
            tags={
                "Priority": "P0",
                "Surface": "pinpad",
                "Evidence": "...",
                "Investigation": "...",
                "ETA": "2h",
                "Source": "...",
            },
            plan_path="/Users/leokwan/Development/resplit-ios/.cursor/plans/app-store-feedback.plan.md",
            line_number=87,
        )

        external_id = adapter.push_task(task)

        issue_input = recorder.calls[-1][1]["input"]

        # Title — full row, not slug.
        self.assertEqual(
            issue_input["title"],
            "P0 — Pinpad popover cut off on right edge",
        )
        # Description — every section present.
        desc = issue_input["description"]
        for section in ("## Purpose", "## Details", "## Evidence",
                        "## Investigation", "## Plan", "## ETA",
                        "vidux-trace"):
            self.assertIn(section, desc, f"missing {section} in description")
        # Priority + estimate as Linear Ints.
        self.assertEqual(issue_input["priority"], 1)
        self.assertEqual(issue_input["estimate"], 3,
                         "2h ETA → M=3 estimate bucket")
        # Labels — base + auto-derived.
        self.assertEqual(
            issue_input["labelIds"],
            [
                "label-vidux",
                "label-vidux-ios",
                "label-priority-p0",
                "label-surface-pinpad",
            ],
        )
        self.assertEqual(external_id, "lin-issue-1")


class PullRequestLinking(unittest.TestCase):
    def _pr(self) -> dict[str, Any]:
        return {
            "number": 42,
            "url": "https://github.com/leojkwan/repo/pull/42",
            "title": "fix(linear): link PRs",
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "codex/linear-linkage",
        }

    def _issue_payload(
        self,
        *,
        attachment_url: str | None = None,
        comment_body: str | None = None,
        labels: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "issue": {
                "id": "lin-issue-1",
                "identifier": "EVE-123",
                "title": "Wire PR linkage",
                "url": "https://linear.app/leojkwan/issue/EVE-123/wire-pr-linkage",
                "labels": {"nodes": labels or []},
                "attachments": {
                    "nodes": (
                        [{
                            "id": "att-1",
                            "title": "GitHub PR #42",
                            "url": attachment_url,
                        }]
                        if attachment_url
                        else []
                    )
                },
                "comments": {
                    "nodes": (
                        [{"id": "comment-1", "body": comment_body}]
                        if comment_body
                        else []
                    )
                },
            }
        }

    def test_sync_pull_request_link_creates_attachment_and_comment(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder([
            self._issue_payload(),
            {"attachmentCreate": {"success": True, "attachment": {"id": "att-1"}}},
            {"commentCreate": {"success": True, "comment": {"id": "comment-1"}}},
        ])
        adapter._graphql = recorder  # type: ignore[assignment]

        result = adapter.sync_pull_request_link("lin-issue-1", self._pr())

        self.assertEqual(result["issue_identifier"], "EVE-123")
        self.assertTrue(result["attached"])
        self.assertTrue(result["commented"])
        self.assertEqual(len(recorder.calls), 3)
        self.assertIn("attachmentCreate", recorder.calls[1][0])
        self.assertEqual(
            recorder.calls[1][1]["input"]["url"],
            "https://github.com/leojkwan/repo/pull/42",
        )
        self.assertIn("commentCreate", recorder.calls[2][0])
        self.assertIn("Review gate: ready-for-review", recorder.calls[2][1]["input"]["body"])

    def test_sync_pull_request_link_is_idempotent_when_url_already_present(self):
        adapter = _make_adapter(allow_team_wide=True)
        pr = self._pr()
        recorder = GraphQLRecorder(
            self._issue_payload(
                attachment_url=pr["url"],
                comment_body=f"Already linked {pr['url']}",
            )
        )
        adapter._graphql = recorder  # type: ignore[assignment]

        result = adapter.sync_pull_request_link("lin-issue-1", pr)

        self.assertFalse(result["attached"])
        self.assertFalse(result["commented"])
        self.assertTrue(result["already_attached"])
        self.assertTrue(result["already_commented"])
        self.assertEqual(len(recorder.calls), 1)

    def test_sync_pull_request_link_dry_run_plans_without_mutation(self):
        adapter = _make_adapter(allow_team_wide=True)
        recorder = GraphQLRecorder(self._issue_payload())
        adapter._graphql = recorder  # type: ignore[assignment]

        result = adapter.sync_pull_request_link("lin-issue-1", self._pr(), dry_run=True)

        self.assertTrue(result["attached"])
        self.assertTrue(result["commented"])
        self.assertEqual(len(recorder.calls), 1)

    def test_sync_pull_request_link_reconciles_managed_pr_labels(self):
        adapter = _make_adapter(
            allow_team_wide=True,
            managed_labels={
                "pr_state_prefix": "pr-state:",
                "review_state_prefix": "review-state:",
            },
        )
        recorder = GraphQLRecorder([
            self._issue_payload(
                labels=[{"id": "label-old", "name": "pr-state:draft"}]
            ),
            {"issueLabels": {"nodes": [{
                "id": "label-pr-open",
                "name": "pr-state:open",
            }]}},
            {"issueLabels": {"nodes": [{
                "id": "label-review-ready",
                "name": "review-state:ready-for-review",
            }]}},
            {"issueUpdate": {"success": True, "issue": {"id": "lin-issue-1"}}},
            {"attachmentCreate": {"success": True, "attachment": {"id": "att-1"}}},
            {"commentCreate": {"success": True, "comment": {"id": "comment-1"}}},
        ])
        adapter._graphql = recorder  # type: ignore[assignment]

        result = adapter.sync_pull_request_link("lin-issue-1", self._pr())

        self.assertEqual(
            result["labels_added"],
            ["pr-state:open", "review-state:ready-for-review"],
        )
        self.assertEqual(result["labels_removed"], ["pr-state:draft"])
        update_call = recorder.calls[3]
        self.assertIn("issueUpdate", update_call[0])
        self.assertEqual(
            update_call[1]["input"],
            {
                "addedLabelIds": ["label-pr-open", "label-review-ready"],
                "removedLabelIds": ["label-old"],
            },
        )


if __name__ == "__main__":
    unittest.main()
