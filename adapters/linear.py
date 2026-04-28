"""Linear adapter for vidux.

Linear (https://linear.app) is GraphQL-only. Single endpoint
`https://api.linear.app/graphql`, header `Authorization: <key>` (NO `Bearer`).

Implements the 6-method AdapterBase contract by translating between vidux
PlanTask/ExternalItem and Linear's Issue type.

Key design decisions (informed by Linear schema research 2026-04-25):

- **Auth header is bare**: `Authorization: <key>`, not `Bearer <key>`. OAuth
  tokens DO use `Bearer` but personal API keys do not.
- **States are team-scoped UUIDs.** vidux statuses → Linear state IDs requires
  a per-team lookup. Cached on the instance after first load.
- **Description is human-readable markdown ONLY (2026-04-25).** The previous
  HTML-comment codec (`<!-- vidux:Evidence -->...<!-- /vidux:Evidence -->`)
  leaked into Linear's rendered description as visible text, breaking
  readability. Round-trip metadata (Evidence, Investigation, Source, ETA,
  VidxId, VidxPlan) now lives in the per-plan `.external-state.json` sidecar
  under `adapters.linear.task_metadata` keyed by VidxId. The adapter renders
  description from PlanTask fields directly via `_render_body(task)`.
- **Blocked is orthogonal.** Stored as a label (`blocked`) on the issue, NOT a
  state. `push_status(BLOCKED)` raises (matches gh_projects.py contract);
  callers set blocked via `push_fields({"_blocked": True})` instead.
- **Rate limits**: 5,000 req/hour + 3M complexity points/hour personal-key.
  Single-query ceiling 10K points. We batch reads with `first: 250` (Linear's
  max) and avoid deep nested queries to stay under the per-query cap.

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, ClassVar

from adapters.base import (
    AdapterBase,
    ExternalItem,
    PlanTask,
    VidxStatus,
    register,
)


class LinearError(RuntimeError):
    """Wraps a failed Linear GraphQL call (HTTP or GraphQL-level errors)."""


@register
class LinearAdapter(AdapterBase):
    name: ClassVar[str] = "linear"
    config_schema: ClassVar[dict[str, Any]] = {
        "required": [
            "token_file",
            "team_id",
            "state_mapping",
        ],
        "optional": [
            "blocked_label",        # default "blocked"
            "auto_promote_target",  # if "vidux", new external items promote into PLAN.md
            "label_ids",            # default labels applied to every pushed issue
            "project_id",           # if set, scopes fetch_inbox AND push_task to this Linear project
            "project_name",         # expected Linear project name; validates project_id fail-closed
            "allow_team_wide",      # explicit opt-in for no project_id
            "allow_unguarded_project",  # explicit opt-in for project_id without project_name
        ],
    }

    ENDPOINT = "https://api.linear.app/graphql"
    DEFAULT_BLOCKED_LABEL = "blocked"
    PAGE_SIZE = 250  # Linear's max per `first:`
    HTTP_TIMEOUT = 30.0

    # Transient-error patterns worth retrying.
    _TRANSIENT_PATTERNS = (
        "stream error",
        "timeout",
        "temporarily unavailable",
        "502",
        "503",
        "504",
        "connection reset",
    )
    # Rate-limit patterns — never retry; let caller back off until the next
    # window (Linear's reset is hourly, captured in response headers).
    _RATE_LIMIT_PATTERNS = (
        "RATELIMIT",
        "Too many requests",
        "rate limit",
    )

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.token_file: Path = Path(os.path.expanduser(config["token_file"]))
        self.team_id: str = config["team_id"]
        # state_mapping: vidux status string → Linear state UUID
        self.state_mapping: dict[str, str] = dict(config["state_mapping"])
        self.blocked_label: str = config.get(
            "blocked_label", self.DEFAULT_BLOCKED_LABEL
        )
        self.auto_promote_target: str | None = config.get("auto_promote_target")
        self.default_label_ids: list[str] = list(config.get("label_ids", []))
        self.project_id: str | None = config.get("project_id")
        self.project_name: str | None = config.get("project_name")

        # Inverse map for pull_status: state UUID → vidux status string.
        self._status_by_state_id: dict[str, str] = {
            state_id: status for status, state_id in self.state_mapping.items()
        }

        # Lazy caches.
        self._blocked_label_id: str | None = None
        self._inbox_cache: list[ExternalItem] | None = None
        self._inbox_error: LinearError | None = None
        self._project_identity_checked = False

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> None:
        super().validate_config(config)
        project_id = config.get("project_id")
        project_name = config.get("project_name")
        allow_team_wide = config.get("allow_team_wide") is True
        allow_unguarded_project = config.get("allow_unguarded_project") is True

        if config.get("project_name") and not config.get("project_id"):
            raise ValueError(
                "linear adapter config key 'project_name' requires 'project_id'"
            )
        if project_id and not project_name and not allow_unguarded_project:
            raise ValueError(
                "linear adapter config key 'project_id' requires "
                "'project_name' for fail-closed repo intake; set "
                "'allow_unguarded_project': true only for an intentional "
                "product/planning bucket"
            )
        if not project_id and not allow_team_wide:
            raise ValueError(
                "linear adapter config without 'project_id' is team-wide; set "
                "'allow_team_wide': true only when importing the whole team is "
                "intentional"
            )
        if project_id and allow_team_wide:
            raise ValueError(
                "linear adapter config key 'allow_team_wide' is only valid "
                "when 'project_id' is absent"
            )
        if project_name and allow_unguarded_project:
            raise ValueError(
                "linear adapter config key 'allow_unguarded_project' is "
                "redundant when 'project_name' is set"
            )

    # -- Token + HTTP plumbing ------------------------------------------------

    def _load_token(self) -> str:
        if not self.token_file.exists():
            raise LinearError(f"token file not found: {self.token_file}")
        token = self.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise LinearError(f"token file empty: {self.token_file}")
        return token

    def _graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        max_attempts: int = 4,
    ) -> dict[str, Any]:
        """POST a GraphQL query and return the `data` payload.

        Retries on transient HTTP/transport errors with modest exponential
        backoff (0.5s, 1s, 2s). Rate-limit errors short-circuit immediately —
        retry would just burn budget.
        """
        body = json.dumps({
            "query": query,
            "variables": variables or {},
        }).encode("utf-8")

        last_err: str | None = None
        for attempt in range(max_attempts):
            req = urllib.request.Request(
                self.ENDPOINT,
                data=body,
                method="POST",
                headers={
                    "Authorization": self._load_token(),
                    "Content-Type": "application/json",
                    "User-Agent": "vidux-linear-adapter/1.0",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT) as resp:
                    raw = resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                last_err = f"HTTP {exc.code}: {err_body[:300]}"
                # Rate-limit short-circuit — never retry.
                if exc.code == 429 or any(
                    pat.lower() in err_body.lower()
                    for pat in self._RATE_LIMIT_PATTERNS
                ):
                    raise LinearError(f"rate limit: {last_err}") from exc
                # Transient HTTP — retry.
                if attempt + 1 < max_attempts and any(
                    str(exc.code).startswith(p) or p in err_body
                    for p in ("502", "503", "504")
                ):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise LinearError(last_err) from exc
            except urllib.error.URLError as exc:
                last_err = f"URLError: {exc}"
                if attempt + 1 < max_attempts and any(
                    pat.lower() in str(exc).lower()
                    for pat in self._TRANSIENT_PATTERNS
                ):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise LinearError(last_err) from exc

            payload = json.loads(raw)
            if payload.get("errors"):
                # GraphQL-level errors. Treat rate-limit shape as fatal.
                err_text = json.dumps(payload["errors"])
                if any(pat in err_text for pat in self._RATE_LIMIT_PATTERNS):
                    raise LinearError(f"rate limit: {err_text[:300]}")
                raise LinearError(f"graphql errors: {err_text[:500]}")
            return payload.get("data", {})

        raise LinearError(f"exhausted retries: {last_err}")

    # -- Body renderer (clean human-facing markdown) --------------------------

    @classmethod
    def _render_body(cls, task: PlanTask) -> str:
        """Render a PlanTask as clean human-readable markdown.

        Format (sections omitted when their source field is empty):

            ## Purpose
            <one-line title summary>

            ## Evidence
            - <file path 1>
            - <file path 2>
            - ...

            ## Investigation
            <task.investigation>

            ## Source
            <task.source>

            ## ETA
            <eta>h

        NO HTML-comment codec — Linear renders `<!-- ... -->` as visible text,
        which broke description readability. Round-trip metadata (Evidence,
        Investigation, etc.) is mirrored into the per-plan `.external-state.json`
        sidecar under `adapters.linear.task_metadata`; the sync script owns
        sidecar writes.
        """
        sections: list[str] = []

        # Purpose — short prose summary. We use the task title as the source
        # of truth since PlanTask doesn't carry a separate body field today.
        # If the title is the only thing we have, we still emit a Purpose
        # section so the doc has predictable shape.
        sections.append(f"## Purpose\n{task.title.strip()}")

        # Evidence — bullet list, one item per line. Evidence in PlanTask is
        # a single free-form string (often semicolon-separated paths). Split
        # on ';' or newlines and bullet each token; otherwise emit raw.
        if task.evidence:
            evidence_items = cls._split_evidence(task.evidence)
            if evidence_items:
                bullets = "\n".join(f"- {item}" for item in evidence_items)
                sections.append(f"## Evidence\n{bullets}")

        if task.investigation:
            sections.append(f"## Investigation\n{task.investigation.strip()}")

        if task.source:
            sections.append(f"## Source\n{task.source.strip()}")

        if task.eta_hours is not None:
            # Render as "Xh" — accepts either int or float ETAs.
            eta = task.eta_hours
            eta_str = f"{int(eta)}h" if float(eta).is_integer() else f"{eta}h"
            sections.append(f"## ETA\n{eta_str}")

        return "\n\n".join(sections)

    @staticmethod
    def _split_evidence(raw: str) -> list[str]:
        """Split an evidence string on `;` and newlines, trimming each part."""
        if not raw:
            return []
        # Normalize newlines + semicolons to a common separator.
        parts: list[str] = []
        for chunk in raw.replace("\n", ";").split(";"):
            chunk = chunk.strip().strip("`").strip()
            if chunk:
                parts.append(chunk)
        return parts

    # -- Status mapping -------------------------------------------------------

    def _state_id_for(self, status: VidxStatus) -> str:
        if status == VidxStatus.BLOCKED:
            raise LinearError(
                "push_status(BLOCKED) is ambiguous — set blocked via "
                "push_fields({'_blocked': True}) and leave state unchanged, "
                "or pass the actual pipeline status."
            )
        if status.value not in self.state_mapping:
            raise LinearError(
                f"vidux status '{status.value}' not mapped in state_mapping "
                f"(known: {sorted(self.state_mapping.keys())})"
            )
        return self.state_mapping[status.value]

    def _status_from_state_id(self, state_id: str | None) -> VidxStatus:
        if state_id is None:
            return VidxStatus.PENDING
        mapped = self._status_by_state_id.get(state_id)
        if mapped is None:
            return VidxStatus.PENDING
        return VidxStatus(mapped)

    # -- Blocked label discovery / lazy creation -----------------------------

    _LABEL_LOOKUP_QUERY = """
    query($name: String!, $teamId: ID!) {
      issueLabels(filter: { name: { eq: $name }, team: { id: { eq: $teamId } } }, first: 5) {
        nodes { id name }
      }
    }
    """
    _LABEL_CREATE_MUTATION = """
    mutation($input: IssueLabelCreateInput!) {
      issueLabelCreate(input: $input) {
        success
        issueLabel { id name }
      }
    }
    """

    _PROJECT_LOOKUP_QUERY = """
    query($projectId: String!) {
      project(id: $projectId) {
        id
        name
        teams(first: 20) { nodes { id key name } }
      }
    }
    """

    def _ensure_project_identity(self) -> None:
        """Fail closed when config points a repo at the wrong Linear project.

        `project_id` is opaque in config reviews. `project_name` makes the
        intended codebase-owned project explicit, so a copied config cannot
        silently ingest or mutate a product bucket such as "Launch Queue".
        """
        if not self.project_name:
            return
        if self._project_identity_checked:
            return
        if not self.project_id:
            raise LinearError(
                "project_name requires project_id for Linear project validation"
            )

        data = self._graphql(
            self._PROJECT_LOOKUP_QUERY,
            {"projectId": self.project_id},
        )
        project = data.get("project")
        if not project:
            raise LinearError(
                f"Linear project_id '{self.project_id}' not found; "
                f"expected project_name '{self.project_name}'"
            )

        actual_name = project.get("name") or ""
        if actual_name != self.project_name:
            raise LinearError(
                f"Linear project_id '{self.project_id}' resolves to "
                f"project '{actual_name}', expected '{self.project_name}'. "
                "Use a codebase-scoped Linear project or update project_name."
            )

        teams = ((project.get("teams") or {}).get("nodes")) or []
        team_ids = {team.get("id") for team in teams}
        if not team_ids:
            raise LinearError(
                f"Linear project '{actual_name}' has no teams assigned; "
                f"cannot validate team_id '{self.team_id}'"
            )
        if self.team_id not in team_ids:
            raise LinearError(
                f"Linear project '{actual_name}' is not assigned to configured "
                f"team_id '{self.team_id}'"
            )

        self._project_identity_checked = True

    def _get_or_create_blocked_label_id(self) -> str:
        if self._blocked_label_id is not None:
            return self._blocked_label_id
        data = self._graphql(
            self._LABEL_LOOKUP_QUERY,
            {"name": self.blocked_label, "teamId": self.team_id},
        )
        nodes = (data.get("issueLabels") or {}).get("nodes") or []
        if nodes:
            self._blocked_label_id = nodes[0]["id"]
            return self._blocked_label_id
        # Not found — create it scoped to this team.
        created = self._graphql(
            self._LABEL_CREATE_MUTATION,
            {"input": {
                "name": self.blocked_label,
                "teamId": self.team_id,
                "color": "#EB5757",
            }},
        )
        payload = created.get("issueLabelCreate") or {}
        if not payload.get("success") or not payload.get("issueLabel"):
            raise LinearError(
                f"failed to create blocked label '{self.blocked_label}': {created}"
            )
        self._blocked_label_id = payload["issueLabel"]["id"]
        return self._blocked_label_id

    # -- Read path ------------------------------------------------------------

    # Linear state types we drop server-side. `canceled` covers BOTH the
    # default "Canceled" workflow state AND custom "Duplicate" states (Linear
    # treats "Duplicate" as a `canceled`-typed workflow state, not its own
    # type). Pulling these in causes `_status_from_state_id` to fall back to
    # PENDING (the state UUIDs are not in the user's `state_mapping`), which
    # in turn lets the sync script auto-promote them as fresh BD-* tasks.
    _DROP_STATE_TYPES: ClassVar[tuple[str, ...]] = ("canceled",)

    _ISSUES_QUERY_TEAM = """
    query($teamId: ID!, $first: Int!, $after: String) {
      issues(
        filter: {
          team: { id: { eq: $teamId } },
          state: { type: { neq: "canceled" } }
        },
        first: $first,
        after: $after,
        orderBy: updatedAt
      ) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          identifier
          title
          description
          state { id name type }
          labels(first: 20) { nodes { id name } }
          updatedAt
        }
      }
    }
    """

    _ISSUES_QUERY_PROJECT = """
    query($teamId: ID!, $projectId: ID!, $first: Int!, $after: String) {
      issues(
        filter: {
          team: { id: { eq: $teamId } },
          project: { id: { eq: $projectId } },
          state: { type: { neq: "canceled" } }
        },
        first: $first,
        after: $after,
        orderBy: updatedAt
      ) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          identifier
          title
          description
          state { id name type }
          labels(first: 20) { nodes { id name } }
          updatedAt
        }
      }
    }
    """

    def fetch_inbox(self) -> list[ExternalItem]:
        """Return issues on the team (or scoped to project_id when set).

        When `project_id` is configured, fetch_inbox returns ONLY issues on that
        project. This is the safe default for fleet wiring — without scoping, a
        single inbox_sources entry would auto-promote every issue across the
        team's projects into the bound PLAN.md, which is rarely what the user
        wants (each lane usually maps to one project).

        Cached for the adapter instance's lifetime (fleet sync iterates many
        plan_dirs against the same adapter — no point re-fetching the same
        issue list per plan).
        """
        if self._inbox_cache is not None:
            return self._inbox_cache
        if self._inbox_error is not None:
            raise self._inbox_error

        self._ensure_project_identity()

        if self.project_id:
            query = self._ISSUES_QUERY_PROJECT
            variables_base: dict[str, Any] = {
                "teamId": self.team_id,
                "projectId": self.project_id,
            }
        else:
            query = self._ISSUES_QUERY_TEAM
            variables_base = {"teamId": self.team_id}

        items: list[ExternalItem] = []
        cursor: str | None = None
        try:
            while True:
                data = self._graphql(
                    query,
                    {
                        **variables_base,
                        "first": self.PAGE_SIZE,
                        "after": cursor,
                    },
                )
                issues = (data.get("issues") or {})
                for node in issues.get("nodes", []):
                    state_type = ((node.get("state") or {}).get("type") or "")
                    if state_type in self._DROP_STATE_TYPES:
                        continue
                    items.append(self._node_to_external(node))
                page_info = issues.get("pageInfo") or {}
                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")
                if not cursor:
                    break
        except LinearError as exc:
            self._inbox_error = exc
            raise

        self._inbox_cache = items
        return items

    def _node_to_external(self, node: dict[str, Any]) -> ExternalItem:
        state = node.get("state") or {}
        state_id = state.get("id")
        labels = ((node.get("labels") or {}).get("nodes")) or []
        label_names = {l["name"] for l in labels}
        is_blocked = self.blocked_label in label_names
        # Description is treated as opaque human markdown — vidux metadata
        # round-trips via the per-plan .external-state.json sidecar, not the
        # description body. We surface the raw description as `_description`
        # for debugging / diff use only.
        return ExternalItem(
            external_id=node["id"],
            title=node.get("title") or node.get("identifier", ""),
            status=self._status_from_state_id(state_id),
            fields={
                "_description": node.get("description") or "",
                "_identifier": node.get("identifier", ""),
            },
            blocked=is_blocked,
            raw=node,
        )

    # -- Write path -----------------------------------------------------------

    _ISSUE_CREATE_MUTATION = """
    mutation($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier }
      }
    }
    """
    _ISSUE_UPDATE_MUTATION = """
    mutation($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
        issue { id identifier }
      }
    }
    """
    _ISSUE_FETCH_QUERY = """
    query($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        description
        state { id name type }
        labels(first: 20) { nodes { id name } }
      }
    }
    """

    def push_task(self, task: PlanTask) -> str:
        """Create a Linear issue from a PlanTask. Returns Linear issue UUID.

        Description is clean human-readable markdown (Purpose / Evidence /
        Investigation / Source / ETA sections, with empty sections elided).
        VidxId / VidxPlan + the typed metadata round-trip via the per-plan
        `.external-state.json` sidecar — see `adapters/README.md`.
        """
        self._ensure_project_identity()

        description = self._render_body(task)

        input_obj: dict[str, Any] = {
            "teamId": self.team_id,
            "title": task.title,
            "description": description,
            "stateId": self._state_id_for(task.status),
        }
        if self.project_id:
            input_obj["projectId"] = self.project_id
        if self.default_label_ids:
            input_obj["labelIds"] = list(self.default_label_ids)
        if task.blocked:
            input_obj.setdefault("labelIds", []).append(
                self._get_or_create_blocked_label_id()
            )

        data = self._graphql(self._ISSUE_CREATE_MUTATION, {"input": input_obj})
        payload = data.get("issueCreate") or {}
        if not payload.get("success") or not payload.get("issue"):
            raise LinearError(f"issueCreate failed: {data}")
        # Invalidate cache so next fetch_inbox sees the new issue.
        self._inbox_cache = None
        return payload["issue"]["id"]

    def pull_status(self, external_id: str) -> VidxStatus:
        self._ensure_project_identity()
        data = self._graphql(self._ISSUE_FETCH_QUERY, {"id": external_id})
        issue = data.get("issue")
        if not issue:
            raise LinearError(f"issue {external_id} not found")
        state_id = (issue.get("state") or {}).get("id")
        labels = ((issue.get("labels") or {}).get("nodes")) or []
        is_blocked = any(l["name"] == self.blocked_label for l in labels)
        if is_blocked:
            return VidxStatus.BLOCKED
        return self._status_from_state_id(state_id)

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        self._ensure_project_identity()
        state_id = self._state_id_for(status)  # raises on BLOCKED
        data = self._graphql(
            self._ISSUE_UPDATE_MUTATION,
            {"id": external_id, "input": {"stateId": state_id}},
        )
        payload = data.get("issueUpdate") or {}
        if not payload.get("success"):
            raise LinearError(f"issueUpdate(stateId) failed: {data}")
        self._inbox_cache = None

    def pull_fields(self, external_id: str) -> dict[str, Any]:
        """Return adapter-level field state for an issue.

        Since the markdown-delimiter codec was removed (2026-04-25), this is
        effectively just `_blocked` + `_identifier`. Rich vidux metadata
        (Evidence, Investigation, Source, ETA) lives in the per-plan
        `.external-state.json` sidecar — the sync script reads it directly,
        not via the adapter.
        """
        self._ensure_project_identity()
        data = self._graphql(self._ISSUE_FETCH_QUERY, {"id": external_id})
        issue = data.get("issue")
        if not issue:
            raise LinearError(f"issue {external_id} not found")
        labels = ((issue.get("labels") or {}).get("nodes")) or []
        return {
            "_blocked": any(l["name"] == self.blocked_label for l in labels),
            "_identifier": issue.get("identifier", ""),
        }

    def push_fields(self, external_id: str, fields: dict[str, Any]) -> None:
        """Write adapter-level field state for an issue.

        Today only `_blocked` is a real, push-able field — it toggles the
        `blocked` label via addedLabelIds / removedLabelIds. Rich vidux
        metadata (Evidence, etc.) is written to the sidecar by the sync
        script, not via this method. Other keys are silently ignored so
        callers passing legacy field dicts still work.
        """
        self._ensure_project_identity()

        blocked_change = fields.get("_blocked")

        # Nothing to push if the only thing the caller asked for is non-blocked
        # metadata — sidecar handles that, the adapter doesn't.
        if blocked_change is None:
            return

        # Load current label state for the blocked diff.
        data = self._graphql(self._ISSUE_FETCH_QUERY, {"id": external_id})
        issue = data.get("issue")
        if not issue:
            raise LinearError(f"issue {external_id} not found")

        update_input: dict[str, Any] = {}
        blocked_id = self._get_or_create_blocked_label_id()
        current_labels = ((issue.get("labels") or {}).get("nodes")) or []
        currently_blocked = any(
            l["id"] == blocked_id or l["name"] == self.blocked_label
            for l in current_labels
        )
        if blocked_change and not currently_blocked:
            update_input["addedLabelIds"] = [blocked_id]
        elif not blocked_change and currently_blocked:
            update_input["removedLabelIds"] = [blocked_id]

        if not update_input:
            return  # No-op — already in the desired blocked state.

        data = self._graphql(
            self._ISSUE_UPDATE_MUTATION,
            {"id": external_id, "input": update_input},
        )
        payload = data.get("issueUpdate") or {}
        if not payload.get("success"):
            raise LinearError(f"issueUpdate(fields) failed: {data}")
        self._inbox_cache = None
