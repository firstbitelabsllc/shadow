"""Apple ASC (App Store Connect) read-only feedback-tracker adapter.

Parses repo-local ASC-style YAML trackers (e.g.
`<repo>/.cursor/plans/app-store-feedback.plan.md`) and returns each row
as an `ExternalItem` for the vidux inbox-sync pipeline. The Linear /
GH-Projects PUSH leg of `vidux-inbox-sync.py` then mirrors those items
to a downstream PM board automatically — closing the loop on
`asc-eve-autobridge` T-4 and retiring the tactical
`scripts/vidux-asc-bridge.py` one-shot script.

Apple does NOT publish a public API for marking TestFlight / ASC beta
feedback as handled, so handled-state authority stays with the repo-local
tracker file (`<repo>/.cursor/plans/app-store-feedback.plan.md`),
maintained out-of-band by `ruby scripts/asc_beta_feedback.rb sync-plan`.
This adapter reads that scoped tracker authority but never replaces the
owning PLAN.md plus publish ledger packet for shipped-work recovery. It is
therefore READ-only:

  - `fetch_inbox()` — parses the `## Open` section of the tracker file
    and returns one `ExternalItem` per row.
  - `pull_status(...)` — returns `None` (no agent-tracked status; the
    sync script treats this as PENDING so the row stays on the board).
  - `pull_fields(...)` — returns `{}`.
  - `push_task` / `push_status` / `push_fields` — raise
    `NotImplementedError` with a documented reason.

Tracker file format (one row per `- id:` block; YAML-ish, NOT strict
YAML — produced + consumed by `scripts/asc_beta_feedback.rb`):

    - id: ABUGCGWL18gG13e5Tajjzek
      type: screenshot
      status: fixed
      first_seen: 2026-05-07
      last_seen: 2026-05-08
      submitted_at: 2026-05-07T15:37:17.563Z
      comment: <free-form text, may span multiple lines>
      surface: <free-form text>
      owner: resplit-watch/1778218936
      proof: <free-form text>
      fix_commit: 39eec352
      handled_at: 2026-05-08
      note: <free-form text>

The parser is forgiving:

- Continuation lines (lines indented past the `- id:` column AND not
  starting with `<key>:`) append to the most-recently-seen key's value.
- Sections are delimited by `^## ` Markdown headings; only rows inside
  `## Open` are returned (configurable via the implicit `## Open`
  assumption).
- Git-conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) are tolerated
  and skipped, so a mid-merge tracker doesn't crash the cron.
- Status filter (`status_filter` config key) defaults to
  `["new", "triaged", "claimed"]` — terminal states (`fixed`,
  `verified`, `archived`, `blocked`) are excluded so the inbox doesn't
  flood with already-handled rows.

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from adapters.base import (
    AdapterBase,
    ExternalItem,
    PlanTask,
    VidxStatus,
    register,
)


_DEFAULT_STATUS_FILTER = ("new", "triaged", "claimed")
_TERMINAL_STATES = frozenset({"fixed", "verified", "archived"})
_CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
_TITLE_MAX_CHARS = 80


@register
class AppleAscAdapter(AdapterBase):
    """Read-only adapter for the repo-local ASC feedback tracker file."""

    name: ClassVar[str] = "apple_asc"
    config_schema: ClassVar[dict[str, Any]] = {
        "required": [
            "tracker_file",
        ],
        "optional": [
            "status_filter",
        ],
    }

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        raw_path = str(config["tracker_file"])
        self.tracker_file = Path(os.path.expanduser(raw_path))
        status_filter = config.get("status_filter")
        if status_filter is None:
            self.status_filter: tuple[str, ...] = _DEFAULT_STATUS_FILTER
        else:
            if not isinstance(status_filter, (list, tuple)):
                raise ValueError(
                    f"{self.name} adapter config: status_filter must be a "
                    f"list of strings, got {type(status_filter).__name__}"
                )
            self.status_filter = tuple(str(s).lower() for s in status_filter)

    # -- READ path -----------------------------------------------------------

    def fetch_inbox(self) -> list[ExternalItem]:
        """Parse the tracker file and return one `ExternalItem` per row.

        Rows in terminal states (`fixed`, `verified`, `archived`) are
        always dropped. If `status_filter` is configured, rows whose
        status is not in the filter are also dropped.

        Missing tracker file returns `[]` cleanly — a config with a
        wrong path should fail safe (no items) rather than crash the
        sync script. Adapter validation already requires the
        `tracker_file` key be present in config; the existence check
        belongs at fetch time so the cron can run continuously across
        a repo's tracker-file lifecycle.
        """
        if not self.tracker_file.exists():
            return []
        text = self.tracker_file.read_text(encoding="utf-8")
        rows = _parse_open_section(text)
        items: list[ExternalItem] = []
        for row in rows:
            status = (row.get("status") or "").strip().lower()
            if status in _TERMINAL_STATES:
                continue
            if status and status not in self.status_filter:
                continue
            asc_id = row.get("id", "").strip()
            if not asc_id:
                continue
            items.append(_row_to_external(asc_id, row))
        return items

    def pull_status(self, external_id: str) -> VidxStatus | None:
        """ASC has no agent-tracked status; always returns None.

        The sync script interprets `None` as "leave the PLAN.md status
        unchanged", which is the correct behavior for a read-only
        feedback source — Leo's hand on the tracker-file edit is the
        status mutation authority, not the agent.
        """
        return None

    def pull_fields(self, external_id: str) -> dict[str, Any]:
        """ASC has no custom-field round-trip; always returns {}."""
        return {}

    # -- WRITE path (intentionally not implemented) --------------------------

    _PUSH_REASON = (
        "Apple ASC has no public API for marking TestFlight / beta "
        "feedback handled; the tracker file is one-way READ-only."
    )

    def push_task(self, task: PlanTask) -> str:
        raise NotImplementedError(self._PUSH_REASON)

    def push_status(self, external_id: str, status: VidxStatus) -> None:
        raise NotImplementedError(self._PUSH_REASON)

    def push_fields(self, external_id: str, fields: dict[str, Any]) -> None:
        raise NotImplementedError(self._PUSH_REASON)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_open_section(text: str) -> list[dict[str, str]]:
    """Return every `- id: ...` block inside `## Open`.

    Each block is a dict of `{key: value}` pairs. Continuation lines
    (indented deeper than the `- id:` line and NOT matching `^key:`)
    are appended to the most-recent key's value with a single space.

    Sections outside `## Open` are skipped entirely. Git-conflict
    marker lines are tolerated and ignored.
    """
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    current_key: str | None = None
    in_open = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith(_CONFLICT_MARKERS):
            continue
        if line.startswith("## "):
            # Flush any open row before changing section.
            if current is not None:
                rows.append(current)
                current = None
                current_key = None
            in_open = line.strip() == "## Open"
            continue
        if not in_open:
            continue

        stripped = line.lstrip()
        if stripped.startswith("- id:"):
            # New row — flush the previous one.
            if current is not None:
                rows.append(current)
            current = {}
            current_key = "id"
            current["id"] = stripped[len("- id:"):].strip()
            continue

        if current is None:
            # Free-form prose between rows (e.g. section header notes).
            continue

        # Detect `<key>: <value>` shape. Keys are simple identifiers; we
        # only treat a colon as a key separator when the bit before the
        # colon contains no whitespace and is purely alphanumeric +
        # underscore. This avoids false-positives on prose containing
        # colons (e.g. URLs, time stamps).
        kv = _split_key_value(stripped)
        if kv is not None:
            key, value = kv
            current[key] = value
            current_key = key
            continue

        # Continuation line — append to the most-recent key.
        if current_key is not None and stripped:
            existing = current.get(current_key, "")
            sep = " " if existing else ""
            current[current_key] = f"{existing}{sep}{stripped}"

    if current is not None:
        rows.append(current)
    return rows


def _split_key_value(stripped: str) -> tuple[str, str] | None:
    """Return `(key, value)` if `stripped` looks like a `key: value`
    YAML-ish field, else `None`.

    Keys must be `[A-Za-z_][A-Za-z0-9_]*` and the colon must be the
    first colon in the line — this rejects continuation lines that
    happen to contain colons (URLs, ISO timestamps, prose).
    """
    colon = stripped.find(":")
    if colon <= 0:
        return None
    key = stripped[:colon]
    if not key or not (key[0].isalpha() or key[0] == "_"):
        return None
    for ch in key:
        if not (ch.isalnum() or ch == "_"):
            return None
    value = stripped[colon + 1 :].strip()
    return key, value


def _row_to_external(asc_id: str, row: dict[str, str]) -> ExternalItem:
    """Translate one parsed tracker row to an `ExternalItem`.

    `external_id` is namespaced (`asc:<id>`) so the sync script can
    tell ASC items apart from Linear, GH Projects, etc. when the same
    PLAN.md aggregates from multiple sources.

    `title` prefers `comment` (truncated to 80 chars) and falls back to
    `surface` (the human-curated triage note) when the row has no
    reporter comment. `body` carries the full row contents for the
    sync script to render into INBOX.md or PLAN.md as evidence.
    """
    comment = (row.get("comment") or "").strip()
    surface = (row.get("surface") or "").strip()
    title_source = comment or surface or f"ASC {asc_id}"
    if len(title_source) > _TITLE_MAX_CHARS:
        title = title_source[: _TITLE_MAX_CHARS - 1].rstrip() + "…"
    else:
        title = title_source

    body_lines = [f"{k}: {v}" for k, v in row.items() if k != "id"]
    body = "\n".join(body_lines)

    fields: dict[str, Any] = {}
    if surface:
        fields["Surface"] = surface
    if row.get("submitted_at"):
        fields["Source"] = f"asc:{asc_id} submitted_at={row['submitted_at']}"
    else:
        fields["Source"] = f"asc:{asc_id}"
    if body:
        fields["Evidence"] = body

    return ExternalItem(
        external_id=f"asc:{asc_id}",
        title=title,
        status=VidxStatus.PENDING,
        fields=fields,
        blocked=False,
        raw=dict(row),
    )
