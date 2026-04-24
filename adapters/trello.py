"""Trello adapter stub.

Trello (https://trello.com) — simple card-on-list kanban with REST API at
https://api.trello.com/1.

Contract to implement (see `~/Development/vidux/adapters/base.py`):
    fetch_inbox / push_task / pull_status / push_status / pull_fields / push_fields

Auth: Trello uses API key + user token pair (https://trello.com/app-key).
    Pass as query params `?key=<k>&token=<t>` on every call. Store both at
    `~/.config/vidux/trello.key` and `~/.config/vidux/trello.token`
    (chmod 600).

Status mapping: Trello's "lists" ARE columns. The adapter accepts a
    `list_mapping` dict keyed by vidux VidxStatus → Trello list id.
    Discover via `GET /boards/{id}/lists`. Moving a card = `PUT /cards/{id}`
    with `idList` query param.

Custom fields: Trello has custom fields as a paid Power-Up. If disabled,
    the adapter should fall back to embedding vidux metadata in the card's
    `desc` field with the same delimiter pattern as the Linear adapter
    (`<!-- vidux:Evidence -->...<!-- /vidux:Evidence -->`). If enabled,
    `field_mapping` dict keys vidux tag → Trello customField id + type.

Labels: Trello labels map cleanly to the `Blocked` semantics — use a
    board-scoped `blocked` label (create if missing via
    `POST /boards/{id}/labels`). `push_fields({'_blocked': True})` then
    adds/removes the label via `POST/DELETE /cards/{id}/idLabels/{label_id}`.

Rate limits: 300 req/10s per key, 100 req/10s per token. Throttle if needed.

This file is a stub — raising NotImplementedError is the contract until
an implementation lands.
"""

from .base import AdapterBase, ExternalItem, PlanTask, VidxStatus, register


@register
class TrelloAdapter(AdapterBase):
    name = "trello"
    config_schema = {
        "required": [
            "key_file",
            "token_file",
            "board_id",
            "list_mapping",
            "blocked_label_name",
            "field_mapping",
        ],
    }

    def fetch_inbox(self) -> list[ExternalItem]:
        raise NotImplementedError("TrelloAdapter.fetch_inbox not yet implemented")

    def push_task(self, task: PlanTask) -> str:
        raise NotImplementedError("TrelloAdapter.push_task not yet implemented")

    def pull_status(self, external_id: str) -> VidxStatus:
        raise NotImplementedError("TrelloAdapter.pull_status not yet implemented")

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        raise NotImplementedError("TrelloAdapter.push_status not yet implemented")

    def pull_fields(self, external_id: str) -> dict:
        raise NotImplementedError("TrelloAdapter.pull_fields not yet implemented")

    def push_fields(self, external_id: str, fields: dict) -> None:
        raise NotImplementedError("TrelloAdapter.push_fields not yet implemented")
