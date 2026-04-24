"""Linear adapter stub.

Linear (https://linear.app) — opinionated issue tracker with Projects, Cycles,
and GraphQL API at https://api.linear.app/graphql.

Contract to implement (see `~/Development/vidux/adapters/base.py`):
    fetch_inbox / push_task / pull_status / push_status / pull_fields / push_fields

Auth: Linear Personal API key (https://linear.app/settings/api). Pass via
    `Authorization: <key>` header (NOT "Bearer"). Store at
    `~/.config/vidux/linear.token` (chmod 600) — matches the gh_projects
    convention of per-service single-line token files.

Status mapping: Linear workflow states are team-scoped. Recommend
    configuring the adapter with a `workflow_state_mapping` dict keyed by
    vidux VidxStatus → Linear state UUID (discovered via
    `teams { states { nodes { id name type } } }` on first load). Linear's
    state.type canonicals (`backlog` / `unstarted` / `started` / `completed` /
    `canceled`) let the adapter auto-detect defaults when an explicit
    mapping is absent.

Custom fields: Linear doesn't expose arbitrary custom fields on Issues the
    way GitHub Projects V2 does. ETA / Evidence / Investigation / Source tags
    should round-trip via issue `description` markdown sections with stable
    delimiters (e.g. `<!-- vidux:Evidence -->...<!-- /vidux:Evidence -->`).
    The adapter's `_render_body` + `_parse_body` pair owns this.

Rate limits: Linear's GraphQL endpoint is 1500 req/hour per user. A 10-min
    cron sync of <100 items stays under that ceiling by 10x.

This file is a stub — raising NotImplementedError is the contract until
an implementation lands.
"""

from .base import AdapterBase, ExternalItem, PlanTask, VidxStatus, register


@register
class LinearAdapter(AdapterBase):
    name = "linear"
    config_schema = {
        "required": [
            "api_key_file",
            "team_id",
            "workflow_state_mapping",
        ],
    }

    def fetch_inbox(self) -> list[ExternalItem]:
        raise NotImplementedError("LinearAdapter.fetch_inbox not yet implemented")

    def push_task(self, task: PlanTask) -> str:
        raise NotImplementedError("LinearAdapter.push_task not yet implemented")

    def pull_status(self, external_id: str) -> VidxStatus:
        raise NotImplementedError("LinearAdapter.pull_status not yet implemented")

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        raise NotImplementedError("LinearAdapter.push_status not yet implemented")

    def pull_fields(self, external_id: str) -> dict:
        raise NotImplementedError("LinearAdapter.pull_fields not yet implemented")

    def push_fields(self, external_id: str, fields: dict) -> None:
        raise NotImplementedError("LinearAdapter.push_fields not yet implemented")
