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
- **Custom fields don't exist in Linear's API the way GH Projects V2 has them.**
  Evidence/Investigation/Source/ETA round-trip via markdown delimiters embedded
  in the issue `description`: `<!-- vidux:Evidence -->...<!-- /vidux:Evidence -->`.
  The `_render_body` / `_parse_body` pair owns this codec.
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
import re
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
            "project_id",           # if set, push_task creates issues under this Linear project
        ],
    }

    ENDPOINT = "https://api.linear.app/graphql"
    DEFAULT_BLOCKED_LABEL = "blocked"
    PAGE_SIZE = 250  # Linear's max per `first:`
    HTTP_TIMEOUT = 30.0

    # Custom-field codec — markdown delimiters inside issue.description that
    # round-trip vidux tags (Evidence, Investigation, Source, ETA). Same shape
    # as the linear.py stub specified in 2026-04-25.
    _DELIM_OPEN = "<!-- vidux:{tag} -->"
    _DELIM_CLOSE = "<!-- /vidux:{tag} -->"
    _DELIM_RE = re.compile(
        r"<!--\s*vidux:(?P<tag>[A-Za-z_][A-Za-z0-9_]*)\s*-->"
        r"(?P<body>.*?)"
        r"<!--\s*/vidux:(?P=tag)\s*-->",
        re.DOTALL,
    )

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

        # Inverse map for pull_status: state UUID → vidux status string.
        self._status_by_state_id: dict[str, str] = {
            state_id: status for status, state_id in self.state_mapping.items()
        }

        # Lazy caches.
        self._blocked_label_id: str | None = None
        self._inbox_cache: list[ExternalItem] | None = None
        self._inbox_error: LinearError | None = None

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

    # -- Body codec (markdown-delimiter custom fields) ------------------------

    @classmethod
    def _render_body(
        cls,
        prose: str | None,
        fields: dict[str, str | None],
    ) -> str:
        """Render PlanTask description + tagged fields as markdown.

        Fields with None / empty values are dropped — re-pushing later wipes
        them naturally because the parse side only resurrects what's present.
        """
        parts: list[str] = []
        if prose:
            parts.append(prose.strip())
        for tag, value in fields.items():
            if value is None or value == "":
                continue
            open_d = cls._DELIM_OPEN.format(tag=tag)
            close_d = cls._DELIM_CLOSE.format(tag=tag)
            parts.append(f"{open_d}\n{value.strip()}\n{close_d}")
        return "\n\n".join(parts)

    @classmethod
    def _parse_body(cls, body: str | None) -> tuple[str, dict[str, str]]:
        """Inverse of _render_body. Returns (prose, fields)."""
        if not body:
            return "", {}
        fields: dict[str, str] = {}
        for match in cls._DELIM_RE.finditer(body):
            tag = match.group("tag")
            fields[tag] = match.group("body").strip()
        prose = cls._DELIM_RE.sub("", body).strip()
        return prose, fields

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

    _ISSUES_QUERY = """
    query($teamId: ID!, $first: Int!, $after: String) {
      issues(
        filter: { team: { id: { eq: $teamId } } },
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
        """Return every issue on the team as normalized ExternalItem list.

        Cached for the adapter instance's lifetime (fleet sync iterates many
        plan_dirs against the same adapter — no point re-fetching the same
        issue list per plan).
        """
        if self._inbox_cache is not None:
            return self._inbox_cache
        if self._inbox_error is not None:
            raise self._inbox_error

        items: list[ExternalItem] = []
        cursor: str | None = None
        try:
            while True:
                data = self._graphql(
                    self._ISSUES_QUERY,
                    {
                        "teamId": self.team_id,
                        "first": self.PAGE_SIZE,
                        "after": cursor,
                    },
                )
                issues = (data.get("issues") or {})
                for node in issues.get("nodes", []):
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
        prose, fields = self._parse_body(node.get("description"))
        is_blocked = self.blocked_label in label_names
        return ExternalItem(
            external_id=node["id"],
            title=node.get("title") or node.get("identifier", ""),
            status=self._status_from_state_id(state_id),
            fields={
                **fields,
                "_prose": prose,
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
        """Create a Linear issue from a PlanTask. Returns Linear issue UUID."""
        description = self._render_body(
            None,  # Title carries the prose; description is field-only.
            {
                "Evidence": task.evidence,
                "Investigation": task.investigation,
                "Source": task.source,
                "ETA": str(task.eta_hours) if task.eta_hours is not None else None,
                "VidxId": task.id,
            },
        )

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
        data = self._graphql(self._ISSUE_FETCH_QUERY, {"id": external_id})
        issue = data.get("issue")
        if not issue:
            raise LinearError(f"issue {external_id} not found")
        _, fields = self._parse_body(issue.get("description"))
        # Surface blocked status as a peer field so callers don't need to
        # remember to call pull_status.
        labels = ((issue.get("labels") or {}).get("nodes")) or []
        fields["_blocked"] = any(l["name"] == self.blocked_label for l in labels)
        return fields

    def push_fields(self, external_id: str, fields: dict[str, Any]) -> None:
        """Write tagged fields by re-rendering description.

        Pulls current description, parses it, merges in the new tagged values,
        re-renders, and pushes via issueUpdate. The `_blocked` pseudo-field
        toggles the blocked label via addedLabelIds/removedLabelIds.
        """
        # Fetch current issue state for merge.
        data = self._graphql(self._ISSUE_FETCH_QUERY, {"id": external_id})
        issue = data.get("issue")
        if not issue:
            raise LinearError(f"issue {external_id} not found")
        prose, current = self._parse_body(issue.get("description"))

        # Pop the orthogonal blocked flag — it's a label, not a field.
        blocked_change = fields.pop("_blocked", None)

        # Merge in new field values (None / "" deletes that tag).
        for tag, value in fields.items():
            if value is None or value == "":
                current.pop(tag, None)
            else:
                current[tag] = str(value)
        new_description = self._render_body(prose if prose else None, current)

        update_input: dict[str, Any] = {"description": new_description}

        if blocked_change is not None:
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

        data = self._graphql(
            self._ISSUE_UPDATE_MUTATION,
            {"id": external_id, "input": update_input},
        )
        payload = data.get("issueUpdate") or {}
        if not payload.get("success"):
            raise LinearError(f"issueUpdate(fields) failed: {data}")
        self._inbox_cache = None
