"""Jira adapter stub.

Jira (https://atlassian.com/software/jira) — enterprise issue tracker with
projects, issue types, workflows, and REST API v3 at
https://<host>.atlassian.net/rest/api/3.

Contract to implement (see `~/Development/vidux/adapters/base.py`):
    fetch_inbox / push_task / pull_status / push_status / pull_fields / push_fields

Auth: Jira uses email + API token basic auth (NOT the UI password). Tokens
    at https://id.atlassian.com/manage-profile/security/api-tokens. Pass via
    `Authorization: Basic base64(email:token)`. Store token at
    `~/.config/vidux/jira.token` and email at `~/.config/vidux/jira.email`
    (both chmod 600).

Status mapping: Jira statuses are workflow-scoped. The adapter should accept
    a `status_mapping` dict keyed by vidux VidxStatus → Jira status name
    (e.g. "To Do" / "In Progress" / "In Review" / "Done"). Transitions are
    NOT direct status writes — use `POST /issue/{id}/transitions` with the
    transition id discovered via `GET /issue/{id}/transitions`. The adapter
    must cache available transitions per issue since they depend on current
    status.

Custom fields: Jira custom fields have opaque ids like `customfield_10001`.
    `field_mapping` dict keyed by vidux tag → `{field_id, type}`. Discover
    via `GET /field`.

Rate limits: Per-host, usually 500 req/min. Respect `Retry-After` on 429.

This file is a stub — raising NotImplementedError is the contract until
an implementation lands.
"""

from .base import AdapterBase, ExternalItem, PlanTask, VidxStatus, register


@register
class JiraAdapter(AdapterBase):
    name = "jira"
    config_schema = {
        "required": [
            "host",
            "email_file",
            "token_file",
            "project_key",
            "issue_type",
            "status_mapping",
            "field_mapping",
        ],
    }

    def fetch_inbox(self) -> list[ExternalItem]:
        raise NotImplementedError("JiraAdapter.fetch_inbox not yet implemented")

    def push_task(self, task: PlanTask) -> str:
        raise NotImplementedError("JiraAdapter.push_task not yet implemented")

    def pull_status(self, external_id: str) -> VidxStatus:
        raise NotImplementedError("JiraAdapter.pull_status not yet implemented")

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        raise NotImplementedError("JiraAdapter.push_status not yet implemented")

    def pull_fields(self, external_id: str) -> dict:
        raise NotImplementedError("JiraAdapter.pull_fields not yet implemented")

    def push_fields(self, external_id: str, fields: dict) -> None:
        raise NotImplementedError("JiraAdapter.push_fields not yet implemented")
