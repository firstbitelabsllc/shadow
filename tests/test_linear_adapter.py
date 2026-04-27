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

from adapters.linear import LinearAdapter  # noqa: E402


def _make_adapter(*, project_id: str | None = None) -> LinearAdapter:
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
    return LinearAdapter(config)


class GraphQLRecorder:
    """Capture (query, variables) calls to `_graphql` and replay canned data."""

    def __init__(self, payload: dict[str, Any]):
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.payload = payload

    def __call__(self, query: str, variables: dict[str, Any] | None = None,
                 *, max_attempts: int = 4) -> dict[str, Any]:
        self.calls.append((query, dict(variables or {})))
        return self.payload


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
        adapter = _make_adapter()
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
        adapter = _make_adapter(project_id="project-uuid")
        recorder = GraphQLRecorder(self._nodes())
        adapter._graphql = recorder  # type: ignore[assignment]

        items = adapter.fetch_inbox()

        ids = [it.external_id for it in items]
        self.assertNotIn("canceled-1", ids)
        self.assertNotIn("duplicate-1", ids)
        self.assertEqual(len(items), 3)


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


if __name__ == "__main__":
    unittest.main()
