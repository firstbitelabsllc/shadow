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

from adapters.base import PlanTask, VidxStatus  # noqa: E402
from adapters.linear import LinearAdapter  # noqa: E402


def _make_adapter(
    *,
    project_id: str | None = None,
    project_name: str | None = None,
    allow_team_wide: bool = False,
    allow_unguarded_project: bool = False,
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


if __name__ == "__main__":
    unittest.main()
