"""Asana adapter stub.

Asana (https://asana.com) — project/task tool with custom fields, sections,
and REST API at https://app.asana.com/api/1.0.

Contract to implement (see `~/Development/vidux/adapters/base.py`):
    fetch_inbox / push_task / pull_status / push_status / pull_fields / push_fields

Auth: Asana Personal Access Token (https://app.asana.com/0/my-apps). Pass via
    `Authorization: Bearer <token>` header. Store at
    `~/.config/vidux/asana.token` (chmod 600).

Status mapping: Asana uses "sections" within a project as the column
    equivalent. The adapter should accept a `section_mapping` dict keyed by
    vidux VidxStatus → Asana section GID. Discover sections on first load
    via `GET /projects/{project_gid}/sections`. `completed` also flips the
    task's top-level `completed: true` boolean.

Custom fields: Asana has first-class custom fields attached at the project
    level. `field_mapping` dict keyed by vidux tag → Asana custom_field GID
    + type (text / number / enum). Discover via
    `GET /projects/{project_gid}/custom_field_settings`.

Rate limits: 1500 req/min per token. Comfortable margin.

This file is a stub — raising NotImplementedError is the contract until
an implementation lands.
"""

from .base import AdapterBase, ExternalItem, PlanTask, VidxStatus, register


@register
class AsanaAdapter(AdapterBase):
    name = "asana"
    config_schema = {
        "required": [
            "token_file",
            "workspace_gid",
            "project_gid",
            "section_mapping",
            "field_mapping",
        ],
    }

    def fetch_inbox(self) -> list[ExternalItem]:
        raise NotImplementedError("AsanaAdapter.fetch_inbox not yet implemented")

    def push_task(self, task: PlanTask) -> str:
        raise NotImplementedError("AsanaAdapter.push_task not yet implemented")

    def pull_status(self, external_id: str) -> VidxStatus:
        raise NotImplementedError("AsanaAdapter.pull_status not yet implemented")

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        raise NotImplementedError("AsanaAdapter.push_status not yet implemented")

    def pull_fields(self, external_id: str) -> dict:
        raise NotImplementedError("AsanaAdapter.pull_fields not yet implemented")

    def push_fields(self, external_id: str, fields: dict) -> None:
        raise NotImplementedError("AsanaAdapter.push_fields not yet implemented")
