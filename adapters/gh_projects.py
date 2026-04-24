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

    def _run(self, args: list[str], *, stdin: str | None = None) -> str:
        """Run a `gh` command and return stdout.

        Raises GhProjectsError with stderr on nonzero exit. Token is
        injected via env; never appears in argv.
        """
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
        if proc.returncode != 0:
            raise GhProjectsError(
                f"gh command failed ({proc.returncode}): "
                f"{' '.join(args[:3])}... stderr={proc.stderr.strip()}"
            )
        return proc.stdout

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL query via `gh api graphql` and return the `data` payload."""
        args = ["gh", "api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            if isinstance(value, (int, float)):
                args.extend(["-F", f"{key}={value}"])
            else:
                args.extend(["-f", f"{key}={value}"])
        stdout = self._run(args)
        payload = json.loads(stdout)
        if "errors" in payload and payload["errors"]:
            raise GhProjectsError(f"graphql errors: {payload['errors']}")
        return payload.get("data", {})

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
        """Return every item on the project as normalized ExternalItem list."""
        stdout = self._run(
            [
                "gh",
                "project",
                "item-list",
                str(self.project_number),
                "--owner",
                self.owner,
                "--format",
                "json",
                "--limit",
                str(self.ITEM_LIST_LIMIT),
            ]
        )
        payload = json.loads(stdout)
        items = payload.get("items", [])
        out: list[ExternalItem] = []
        for raw in items:
            out.append(self._item_to_external(raw))
        return out

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

    def push_task(self, task: PlanTask) -> str:
        """Create a draft-issue project item from a PlanTask. Return external_id."""
        project_id = self._project_id_cached()
        body = self._render_body(task)
        data = self._graphql(
            self._CREATE_DRAFT_ISSUE_MUTATION,
            {"projectId": project_id, "title": task.title, "body": body},
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
        field = self._field(self.blocked_field_name)
        options = field.get("options") or {}
        target_option = "Yes" if blocked else "No"
        if target_option not in options:
            raise GhProjectsError(
                f"Blocked field missing option '{target_option}'. "
                f"Known: {sorted(options.keys())}"
            )
        self._graphql(
            self._UPDATE_SELECT_MUTATION,
            {
                "projectId": project_id,
                "itemId": external_id,
                "fieldId": field["id"],
                "optionId": options[target_option],
            },
        )
