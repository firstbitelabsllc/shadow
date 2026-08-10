"""Pure projection from a v4 PLAN.md to one board brief.

The browser was written against the v3 Brief contract — a typed ``Outcome:``
block that the v4 grammar retired on 2026-08-09.  After that migration every
real plan on a machine failed ``outcome must be a string`` and the board
rendered a wall of "needs a Brief" cards: a v3 surface reading v4 plans.

This module is the v4-native answer.  It is a TOTAL function on plan text —
it never raises, because a board that errors on the plans it exists to show
is the defect this file replaces.  A plan it cannot read still gets an honest
brief: ``state: "empty"`` with everything else absent.

It reads the same grammar the linter enforces: ``## Brief`` keys, ``### ``
milestones under ``## Tasks`` with ``- [state] text ~id | proof: ...`` rows,
and ``## Contradictions``.  It never writes, never invokes anything, and
returns only bounded display text.
"""

from __future__ import annotations

import re
from typing import Any


BOARD_SCHEMA = "shadow.board-brief.v1"
MAX_ROW_TEXT = 220
ROW_RE = re.compile(
    r"^- \[(pending|in_progress|blocked|completed)\]\s+(.*)$"
)
ID_SPLIT_RE = re.compile(r"\s+~[0-9a-z]{4}\b")
FIELD_RE = re.compile(r"^[-*]\s*([A-Za-z][A-Za-z0-9 /_-]*)\s*:\s*(.+)$")
DOD_RE = re.compile(r"\(DoD\)")
STATES = ("pending", "in_progress", "blocked", "completed")


def _section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    target = f"## {name}".lower()
    start = next(
        (i + 1 for i, line in enumerate(lines) if line.strip().lower() == target),
        None,
    )
    if start is None:
        return []
    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def _display(row_text: str) -> str:
    """The human half of a row: text up to its ~id, whitespace collapsed."""
    head = ID_SPLIT_RE.split(row_text, maxsplit=1)[0]
    head = " ".join(head.split())
    if len(head) > MAX_ROW_TEXT:
        head = head[: MAX_ROW_TEXT - 1].rstrip() + "…"
    return head


def _milestones(task_lines: list[str]) -> list[dict[str, Any]]:
    """Milestones in plan order. Rows above the first ``###`` are legal in the
    grammar (the DoD law only binds rows grouped under a heading); they form
    an implicit leading group so a plan without milestone headings still
    renders instead of reading as empty."""
    result: list[dict[str, Any]] = []
    current: dict[str, Any] = {"title": "Tasks", "rows": []}
    result.append(current)
    for line in task_lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            current = {"title": " ".join(stripped[4:].split())[:120], "rows": []}
            result.append(current)
            continue
        match = ROW_RE.match(stripped)
        if match:
            current["rows"].append(
                {
                    "state": match.group(1),
                    "text": match.group(2),
                    "dod": bool(DOD_RE.search(match.group(2))),
                }
            )
    return [m for m in result if m["rows"]]


def _brief_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in _section(text, "Brief"):
        match = FIELD_RE.match(line.strip())
        if match:
            key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
            fields[key] = " ".join(match.group(2).split())
    return fields


def _open_contradictions(text: str) -> int:
    count = 0
    for line in _section(text, "Contradictions"):
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- RESOLVED"):
            count += 1
    return count


def _latest_progress(text: str) -> str | None:
    rows = [
        line.strip()[2:]
        for line in _section(text, "Progress")
        if line.strip().startswith("- ")
    ]
    if not rows:
        return None
    return _display(rows[-1])


def project_board_brief(text: Any) -> dict[str, Any]:
    """One bounded brief for the board.  Total: bad input -> honest 'empty'."""
    if not isinstance(text, str) or not text.strip():
        return {"schema": BOARD_SCHEMA, "state": "empty", "priority": None,
                "milestone": None, "contradictions_open": 0, "latest_change": None}

    fields = _brief_fields(text)
    milestones = _milestones(_section(text, "Tasks"))

    # The milestone shown is where the work IS: first one with an in_progress
    # row (a stale pending in an old milestone must not shadow live work),
    # else the first with anything left to do; all complete shows the last
    # one, resting.
    active = next(
        (m for m in milestones if any(r["state"] == "in_progress" for r in m["rows"])),
        None,
    ) or next(
        (m for m in milestones if any(r["state"] != "completed" for r in m["rows"])),
        None,
    )
    resting = active is None and bool(milestones)
    shown = active or (milestones[-1] if milestones else None)

    milestone: dict[str, Any] | None = None
    # No parseable rows in a file with real content is a pre-grammar plan,
    # not an empty one — the distinction the import row exists to close.
    substantial = sum(1 for line in text.splitlines() if line.strip()) >= 12
    state = "unmigrated" if substantial else "empty"
    if shown is not None:
        counts = {s: 0 for s in STATES}
        for row in shown["rows"]:
            counts[row["state"]] += 1
        current = next((r for r in shown["rows"] if r["state"] == "in_progress"), None)
        nxt = next((r for r in shown["rows"] if r["state"] == "pending"), None)
        dod = next((r for r in shown["rows"] if r["dod"]), None)
        milestone = {
            "title": shown["title"],
            "counts": counts,
            "current": _display(current["text"]) if current else None,
            "next": _display(nxt["text"]) if nxt else None,
            "dod": {"state": dod["state"], "text": _display(dod["text"])} if dod else None,
        }
        if resting:
            state = "resting"
        elif current is not None:
            state = "working"
        elif counts["pending"]:
            state = "ready"
        elif counts["blocked"]:
            state = "blocked"
        else:
            state = "resting"

    return {
        "schema": BOARD_SCHEMA,
        "state": state,
        "priority": fields.get("priority") or None,
        "milestone": milestone,
        "contradictions_open": _open_contradictions(text),
        "latest_change": _latest_progress(text),
    }
