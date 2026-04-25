"""GitHub Projects V2 adapter for vidux.

Wraps the `gh` CLI + `gh api graphql` so core vidux never speaks GH-specific
GraphQL. Token is read from a file at init time (never echoed, never logged)
and injected as `GH_TOKEN=<token>` on every subprocess call so the cron
never overwrites Leo's `gh auth` keyring.

Reads use `gh project item-list --format json`. Writes use the
`updateProjectV2ItemFieldValue` GraphQL mutation via `gh api graphql`.
Project + field metadata is discovered at first access and cached on the
instance (cycles are short; no need for a TTL).

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from adapters.base import (
    AdapterBase,
    ExternalItem,
    PlanTask,
    VidxStatus,
    register,
)


class GhProjectsError(RuntimeError):
    """Wraps a failed `gh` invocation with stderr for debugging."""


@register
class GhProjectsAdapter(AdapterBase):
    name: ClassVar[str] = "gh_projects"
    config_schema: ClassVar[dict[str, Any]] = {
        "required": [
            "owner",
            "project_number",
            "token_file",
            "status_field_name",
            "column_mapping",
            "field_mapping",
        ],
        "optional": [
            "blocked_field_name",
            "blocked_linked_label_fallback",
        ],
    }

    DEFAULT_BLOCKED_FIELD = "Blocked"
    DEFAULT_BLOCKED_LABEL_FALLBACK = "blocked"
    # `gh project item-list` default limit is 30; raise to cover a full board.
    ITEM_LIST_LIMIT = 500

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.owner: str = config["owner"]
        self.project_number: int = int(config["project_number"])
        self.token_file: Path = Path(os.path.expanduser(config["token_file"]))
        self.status_field_name: str = config["status_field_name"]
        self.column_mapping: dict[str, str] = dict(config["column_mapping"])
        self.field_mapping: dict[str, dict[str, str]] = dict(config["field_mapping"])
        self.blocked_field_name: str = config.get(
            "blocked_field_name", self.DEFAULT_BLOCKED_FIELD
        )
        self.blocked_linked_label_fallback: str = config.get(
            "blocked_linked_label_fallback", self.DEFAULT_BLOCKED_LABEL_FALLBACK
        )

        # Inverse lookup: column name on board -> vidux status string.
        self._status_by_column: dict[str, str] = {
            column: status for status, column in self.column_mapping.items()
        }

        # Lazy-loaded metadata cache.
        self._project_id: str | None = None
        self._fields_by_name: dict[str, dict[str, Any]] | None = None
        # Per-instance fetch_inbox cache — shared across all sync_plan_with_adapter
        # calls for the same board within one CLI run. Prevents 40+ identical
        # item-list calls from blowing through the GitHub API rate limit.
        self._inbox_cache: list[ExternalItem] | None = None
        # Raw items list — fetched once, used by fetch_inbox AND PR url map.
        self._raw_items_cache: list[dict[str, Any]] | None = None
        # Cache the exception too — if the first fetch fails (typically rate
        # limit), don't retry 39 more times, just re-raise the cached error.
        self._inbox_error: GhProjectsError | None = None
        # Cache PR content URL → project_item_id for idempotency on add_pr.
        self._pr_url_map: dict[str, str] | None = None

    # -- Token + subprocess plumbing -----------------------------------------

    def _load_token(self) -> str:
        if not self.token_file.exists():
            raise GhProjectsError(
                f"token file not found: {self.token_file}"
            )
        token = self.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise GhProjectsError(f"token file empty: {self.token_file}")
        return token

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["GH_TOKEN"] = self._load_token()
        # Strip inherited GITHUB_TOKEN so gh doesn't prefer it silently.
        env.pop("GITHUB_TOKEN", None)
        return env

    # GitHub's http2 transport occasionally raises transient stream errors
    # mid-POST ("cannot retry err [stream error: ...]"). Retry these with
    # modest exponential backoff; everything else fails fast.
    _TRANSIENT_PATTERNS = (
        "stream error",
        "http2: Transport",
        "timeout",
        "temporarily unavailable",
        "502 Bad Gateway",
        "503 Service Unavailable",
        "connection reset",
    )

    def _run(self, args: list[str], *, stdin: str | None = None,
             max_attempts: int = 4) -> str:
        """Run a `gh` command and return stdout.

        Raises GhProjectsError with stderr on nonzero exit. Token is
        injected via env; never appears in argv. Retries on transient
        GitHub GraphQL flakiness (http2 stream errors, 502/503) with
        exponential backoff (0.5s, 1s, 2s).
        """
        import time
        last_err: str | None = None
        for attempt in range(max_attempts):
            try:
                proc = subprocess.run(
                    args,
                    input=stdin,
                    env=self._env(),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise GhProjectsError(f"gh CLI not found: {exc}") from exc
            if proc.returncode == 0:
                return proc.stdout
            stderr = proc.stderr.strip()
            last_err = stderr
            if attempt + 1 < max_attempts and any(
                pat in stderr for pat in self._TRANSIENT_PATTERNS
            ):
                time.sleep(0.5 * (2 ** attempt))
                continue
            break
        raise GhProjectsError(
            f"gh command failed: {' '.join(args[:3])}... stderr={last_err}"
        )

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL query via `gh api graphql` and return the `data` payload.

        Payload serialized as JSON on stdin so Float variables survive round-trip.
        `gh api graphql -F key=val` auto-types ints and bools but coerces floats
        to strings, which GraphQL rejects when the schema declares `Float!`.
        """
        payload = json.dumps({"query": query, "variables": variables})
        stdout = self._run(
            ["gh", "api", "graphql", "--input", "-"],
            stdin=payload,
        )
        resp = json.loads(stdout)
        if "errors" in resp and resp["errors"]:
            raise GhProjectsError(f"graphql errors: {resp['errors']}")
        return resp.get("data", {})

    # -- Metadata discovery ---------------------------------------------------

    _PROJECT_META_QUERY = """
    query($login: String!, $number: Int!) {
      user(login: $login) {
        projectV2(number: $number) {
          id
          fields(first: 50) {
            nodes {
              __typename
              ... on ProjectV2Field            { id name dataType }
              ... on ProjectV2IterationField   { id name dataType }
              ... on ProjectV2SingleSelectField {
                id name dataType
                options { id name }
              }
            }
          }
        }
      }
    }
    """

    def _load_metadata(self) -> None:
        data = self._graphql(
            self._PROJECT_META_QUERY,
            {"login": self.owner, "number": self.project_number},
        )
        user = data.get("user") or {}
        project = user.get("projectV2")
        if not project:
            raise GhProjectsError(
                f"project {self.owner}/{self.project_number} not visible with this token"
            )
        self._project_id = project["id"]
        fields_by_name: dict[str, dict[str, Any]] = {}
        for node in project["fields"]["nodes"]:
            if not node:
                continue
            entry: dict[str, Any] = {
                "id": node["id"],
                "type": node["dataType"],
            }
            if node.get("options"):
                entry["options"] = {opt["name"]: opt["id"] for opt in node["options"]}
            fields_by_name[node["name"]] = entry
        self._fields_by_name = fields_by_name

    def _project_id_cached(self) -> str:
        if self._project_id is None:
            self._load_metadata()
        assert self._project_id is not None
        return self._project_id

    def _field(self, name: str) -> dict[str, Any]:
        if self._fields_by_name is None:
            self._load_metadata()
        assert self._fields_by_name is not None
        if name not in self._fields_by_name:
            raise GhProjectsError(
                f"field '{name}' not found on project. "
                f"Known: {sorted(self._fields_by_name.keys())}"
            )
        return self._fields_by_name[name]

    # -- Status + blocked mapping --------------------------------------------

    def _column_for(self, status: VidxStatus) -> str:
        if status == VidxStatus.BLOCKED:
            # Blocked is orthogonal — caller also writes Blocked=Yes.
            # Leave the Status column at whatever it already is; callers that
            # want a full transition should call push_status separately with a
            # non-blocked status.
            raise GhProjectsError(
                "push_status(BLOCKED) is ambiguous — set Blocked=Yes via "
                "push_fields({'_blocked': True}) and leave Status unchanged, "
                "or pass the actual pipeline status."
            )
        if status.value not in self.column_mapping:
            raise GhProjectsError(
                f"status '{status.value}' not mapped in column_mapping"
            )
        return self.column_mapping[status.value]

    def _status_from_column(self, column: str | None) -> VidxStatus:
        if column is None or column not in self._status_by_column:
            return VidxStatus.PENDING
        return VidxStatus(self._status_by_column[column])

    # -- Read path -----------------------------------------------------------

    def fetch_inbox(self) -> list[ExternalItem]:
        """Return every item on the project as normalized ExternalItem list.

        Cached for the adapter instance's lifetime — the fleet sync script
        iterates 40+ plan_dirs against the same adapter per run, and without
        caching we'd burn 40+ API calls for an identical board snapshot
        (which caused 'API rate limit exceeded' on strongyes-web fan-out).
        """
        if self._inbox_cache is not None:
            return self._inbox_cache
        if self._inbox_error is not None:
            raise self._inbox_error
        self._fetch_raw_items()
        return self._inbox_cache  # type: ignore[return-value]

    def _fetch_raw_items(self) -> list[dict[str, Any]]:
        """Single shared fetch — populates `_inbox_cache` (parsed) and
        `_pr_url_map` (idempotency lookup) in one API call. Cached.

        Without this, fetch_inbox and _pr_url_to_item_id_cache each issued
        their own item-list call, doubling API cost and burning through the
        secondary rate limit on fleet-wide sweeps.
        """
        if self._raw_items_cache is not None:
            return self._raw_items_cache
        if self._inbox_error is not None:
            raise self._inbox_error
        try:
            stdout = self._run([
                "gh", "project", "item-list", str(self.project_number),
                "--owner", self.owner,
                "--format", "json",
                "--limit", str(self.ITEM_LIST_LIMIT),
            ])
        except GhProjectsError as exc:
            self._inbox_error = exc
            raise
        items = json.loads(stdout).get("items", [])
        self._raw_items_cache = items
        self._inbox_cache = [self._item_to_external(raw) for raw in items]
        url_map: dict[str, str] = {}
        for raw in items:
            content = raw.get("content") or {}
            url = content.get("url")
            item_id = raw.get("id")
            if url and item_id:
                url_map[url] = item_id
        self._pr_url_map = url_map
        return items

    def _item_to_external(self, raw: dict[str, Any]) -> ExternalItem:
        """Translate a single `gh project item-list` item to ExternalItem."""
        external_id = raw.get("id", "")
        title = raw.get("title", "") or (raw.get("content") or {}).get("title", "")
        column = raw.get(self.status_field_name.lower()) or raw.get(
            self.status_field_name
        )
        status = self._status_from_column(column)
        fields: dict[str, Any] = {}
        for vidux_key, mapping in self.field_mapping.items():
            project_field = mapping["project_field"]
            # `gh project item-list --format json` lowercases field names.
            val = raw.get(project_field.lower(), raw.get(project_field))
            if val is not None:
                fields[vidux_key] = val

        blocked_val = raw.get(self.blocked_field_name.lower()) or raw.get(
            self.blocked_field_name
        )
        blocked = self._is_blocked(blocked_val, raw)

        return ExternalItem(
            external_id=external_id,
            title=title,
            status=status,
            fields=fields,
            blocked=blocked,
            raw=raw,
        )

    def _is_blocked(self, blocked_field_value: Any, raw: dict[str, Any]) -> bool:
        """Resolve blocked=True/False from the Blocked single-select +
        linked-issue label fallback."""
        if isinstance(blocked_field_value, str) and blocked_field_value.lower() == "yes":
            return True
        # Fallback: read the built-in `Labels` view of a linked Issue/PR.
        labels = raw.get("labels") or []
        if isinstance(labels, list):
            for label in labels:
                name = label.get("name") if isinstance(label, dict) else str(label)
                if name and name.lower() == self.blocked_linked_label_fallback.lower():
                    return True
        return False

    def pull_status(self, external_id: str) -> VidxStatus:
        """Read the Status column of a single item.

        Implemented as a filter over fetch_inbox since `gh project item-list`
        doesn't take an item id. Cheap for boards under a few hundred items.
        """
        for item in self.fetch_inbox():
            if item.external_id == external_id:
                return item.status
        raise GhProjectsError(f"item not found: {external_id}")

    def pull_fields(self, external_id: str) -> dict[str, Any]:
        for item in self.fetch_inbox():
            if item.external_id == external_id:
                return dict(item.fields)
        raise GhProjectsError(f"item not found: {external_id}")

    # -- Write path ----------------------------------------------------------

    _CREATE_DRAFT_ISSUE_MUTATION = """
    mutation($projectId:ID!, $title:String!, $body:String!) {
      addProjectV2DraftIssue(input:{
        projectId: $projectId, title: $title, body: $body
      }) {
        projectItem { id }
      }
    }
    """

    # GitHub draft-issue title cap.
    _MAX_TITLE_LEN = 256

    def push_task(self, task: PlanTask) -> str:
        """Create a draft-issue project item from a PlanTask. Return external_id."""
        project_id = self._project_id_cached()
        body = self._render_body(task)
        # Titles > 256 chars are rejected by GH. Truncate in the title and let
        # the body carry the full content (body is unbounded in practice).
        title = task.title
        if len(title) > self._MAX_TITLE_LEN:
            title = title[: self._MAX_TITLE_LEN - 1].rstrip() + "…"
            body = f"{body}\n\nfull title: {task.title}"
        data = self._graphql(
            self._CREATE_DRAFT_ISSUE_MUTATION,
            {"projectId": project_id, "title": title, "body": body},
        )
        item = data["addProjectV2DraftIssue"]["projectItem"]
        external_id = item["id"]

        # Populate Status + custom fields + blocked flag.
        if task.status != VidxStatus.PENDING:
            self.push_status(external_id, task.status)
        field_payload: dict[str, Any] = {}
        if task.evidence is not None:
            field_payload["Evidence"] = task.evidence
        if task.investigation is not None:
            field_payload["Investigation"] = task.investigation
        if task.eta_hours is not None:
            field_payload["ETA"] = task.eta_hours
        if task.source is not None:
            field_payload["Source"] = task.source
        if task.blocked:
            field_payload["_blocked"] = True
        if field_payload:
            self.push_fields(external_id, field_payload)
        return external_id

    @staticmethod
    def _render_body(task: PlanTask) -> str:
        """Build a body for a draft issue from a PlanTask.

        Keep the body short — custom fields carry structured metadata.
        """
        lines = [f"vidux id: `{task.id}`"]
        if task.source:
            lines.append(f"Source: `{task.source}`")
        return "\n".join(lines)

    _ADD_ITEM_BY_ID_MUTATION = """
    mutation($projectId:ID!, $contentId:ID!) {
      addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) {
        item { id }
      }
    }
    """

    def add_pr_to_project(self, pr_node_id: str,
                          status: VidxStatus = VidxStatus.IN_PROGRESS
                          ) -> str:
        """Link an existing PR (or Issue) to this project. Returns external_id.

        Idempotent at the GitHub layer — re-adding the same content node returns
        the same project-item id. Caller is responsible for skipping when already
        mapped to avoid the API call.
        """
        project_id = self._project_id_cached()
        data = self._graphql(
            self._ADD_ITEM_BY_ID_MUTATION,
            {"projectId": project_id, "contentId": pr_node_id},
        )
        item_id = data["addProjectV2ItemById"]["item"]["id"]
        # Default open PRs to the in_progress column.
        if status != VidxStatus.PENDING:
            self.push_status(item_id, status)
        return item_id

    def _pr_url_to_item_id_cache(self) -> dict[str, str]:
        """Return a {pr_content_url: project_item_id} map. Shares the same
        single API call as fetch_inbox — see _fetch_raw_items.
        """
        if self._pr_url_map is None:
            self._fetch_raw_items()
        return self._pr_url_map or {}

    _UPDATE_SELECT_MUTATION = """
    mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $optionId:String!) {
      updateProjectV2ItemFieldValue(input:{
        projectId: $projectId,
        itemId: $itemId,
        fieldId: $fieldId,
        value: { singleSelectOptionId: $optionId }
      }) { projectV2Item { id } }
    }
    """

    _CLEAR_FIELD_MUTATION = """
    mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!) {
      clearProjectV2ItemFieldValue(input:{
        projectId: $projectId,
        itemId: $itemId,
        fieldId: $fieldId
      }) { projectV2Item { id } }
    }
    """

    _UPDATE_TEXT_MUTATION = """
    mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $text:String!) {
      updateProjectV2ItemFieldValue(input:{
        projectId: $projectId,
        itemId: $itemId,
        fieldId: $fieldId,
        value: { text: $text }
      }) { projectV2Item { id } }
    }
    """

    _UPDATE_NUMBER_MUTATION = """
    mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $number:Float!) {
      updateProjectV2ItemFieldValue(input:{
        projectId: $projectId,
        itemId: $itemId,
        fieldId: $fieldId,
        value: { number: $number }
      }) { projectV2Item { id } }
    }
    """

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        """Set Status column to the mapped column for this vidux status.

        BLOCKED is rejected here — callers write Blocked=Yes separately so
        the Status column preserves the pipeline state orthogonally.
        """
        column = self._column_for(status)
        field = self._field(self.status_field_name)
        options = field.get("options") or {}
        if column not in options:
            raise GhProjectsError(
                f"Status column '{column}' missing on project. Known: {sorted(options.keys())}"
            )
        option_id = options[column]
        self._graphql(
            self._UPDATE_SELECT_MUTATION,
            {
                "projectId": self._project_id_cached(),
                "itemId": external_id,
                "fieldId": field["id"],
                "optionId": option_id,
            },
        )

    def push_fields(self, external_id: str, fields: dict[str, Any]) -> None:
        """Write custom-field values keyed by vidux tag name.

        `_blocked: bool` is a reserved key that writes the Blocked
        single-select (Yes/No). Everything else routes through
        `field_mapping` to its project field + declared type.
        """
        project_id = self._project_id_cached()
        for vidux_key, value in fields.items():
            if vidux_key == "_blocked":
                self._write_blocked(external_id, bool(value), project_id)
                continue
            if vidux_key not in self.field_mapping:
                raise GhProjectsError(
                    f"field '{vidux_key}' not in field_mapping. "
                    f"Known: {sorted(self.field_mapping.keys())}"
                )
            mapping = self.field_mapping[vidux_key]
            project_field = mapping["project_field"]
            declared_type = mapping["type"].upper()
            field_meta = self._field(project_field)
            field_id = field_meta["id"]
            if declared_type == "TEXT":
                self._graphql(
                    self._UPDATE_TEXT_MUTATION,
                    {
                        "projectId": project_id,
                        "itemId": external_id,
                        "fieldId": field_id,
                        "text": str(value),
                    },
                )
            elif declared_type == "NUMBER":
                self._graphql(
                    self._UPDATE_NUMBER_MUTATION,
                    {
                        "projectId": project_id,
                        "itemId": external_id,
                        "fieldId": field_id,
                        "number": float(value),
                    },
                )
            else:
                raise GhProjectsError(
                    f"unsupported field type '{declared_type}' for '{vidux_key}'"
                )

    def _write_blocked(
        self, external_id: str, blocked: bool, project_id: str
    ) -> None:
        """Mark an item blocked or clear the flag.

        Supports two common Blocked field shapes:
          * Two-option ("Yes" / "No") — set the matching option.
          * Single-option ("blocked" / "Blocked") — set when blocked=True,
            CLEAR the field (no value) when blocked=False. Clearing a single-
            select field is the natural "not blocked" signal.
        """
        field = self._field(self.blocked_field_name)
        options = field.get("options") or {}
        field_id = field["id"]

        if blocked:
            # Prefer explicit "Yes"; otherwise use the first option that
            # looks like a "blocked" marker.
            if "Yes" in options:
                option_id = options["Yes"]
            else:
                match = next(
                    (oid for name, oid in options.items()
                     if name.lower() in ("blocked", "true", "yes")),
                    None,
                )
                if match is None:
                    raise GhProjectsError(
                        f"Blocked field missing a blocked-marker option. "
                        f"Known: {sorted(options.keys())}"
                    )
                option_id = match
            self._graphql(
                self._UPDATE_SELECT_MUTATION,
                {
                    "projectId": project_id,
                    "itemId": external_id,
                    "fieldId": field_id,
                    "optionId": option_id,
                },
            )
            return

        # blocked=False: prefer an explicit "No" option when present,
        # otherwise clear the field.
        if "No" in options:
            self._graphql(
                self._UPDATE_SELECT_MUTATION,
                {
                    "projectId": project_id,
                    "itemId": external_id,
                    "fieldId": field_id,
                    "optionId": options["No"],
                },
            )
            return
        # Clear the single-select field (unset = "not blocked").
        self._graphql(
            self._CLEAR_FIELD_MUTATION,
            {
                "projectId": project_id,
                "itemId": external_id,
                "fieldId": field_id,
            },
        )
