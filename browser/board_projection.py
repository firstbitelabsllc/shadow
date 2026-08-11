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

from pathlib import Path
import re
import sys
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:  # this module is imported before server.py
    sys.path.insert(0, str(_SCRIPTS))

from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE  # noqa: E402


BOARD_SCHEMA = "shadow.board-brief.v1"
# Every free-text field a person typed on their own machine passes the same
# canonical gate the title path uses. A Progress line or a Brief priority can
# name /Users/<someone>/… or carry a token; the loopback board is a page an
# owner screenshots, so a private shape is withheld rather than printed.
UNSAFE_TEXT_RE = re.compile(
    f"(?:{PRIVATE_PATH_RE.pattern}|{SECRET_SHAPE_RE.pattern})",
    re.IGNORECASE,
)
MAX_ROW_TEXT = 220
ROW_RE = re.compile(
    r"^- \[(pending|in_progress|blocked|completed)\]\s+(.*)$"
)
ID_SPLIT_RE = re.compile(r"\s+~[0-9a-z]{4}\b")
FIELD_RE = re.compile(r"^[-*]\s*([A-Za-z][A-Za-z0-9 /_-]*)\s*:\s*(.+)$")
DOD_RE = re.compile(r"\(DoD\)")
STATES = ("pending", "in_progress", "blocked", "completed")


def _public(text: str | None) -> str | None:
    """The text a card may print, or None when it carries a private shape.

    Withholding beats redacting here: a card that says nothing is honest,
    while a half-scrubbed path still tells a stranger whose machine this is.
    """
    if not text:
        return None
    return None if UNSAFE_TEXT_RE.search(text) else text


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
    """The human half of a row: text up to its ~id, whitespace collapsed.

    The length bound cuts at a WORD, never mid-word — a card that reads
    "any unavailable r…" told the owner the surface was a debug dump.
    """
    head = ID_SPLIT_RE.split(row_text, maxsplit=1)[0]
    head = " ".join(head.split())
    if len(head) > MAX_ROW_TEXT:
        cut = head[: MAX_ROW_TEXT - 1]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        head = cut.rstrip(" ,;:—–-") + "…"
    return head


MILESTONE_CODE_RE = re.compile(r"^M\d+\s*[—–:-]+\s*")
STAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z?)\s+")
HASH_RE = re.compile(r"\b[0-9a-f]{12,64}\b")
RECEIPT_KINDS = {
    "STRUCT": "Plan structure changed",
    "PROOF": "Proof recorded",
    "NOTE": "Note",
    "THROWN": "Work claimed",
    "DECISION": "Decision recorded",
}


def _human_title(title: str) -> str:
    """A milestone heading without its internal code number.

    The plan law keeps milestone numbers and row IDs off human surfaces;
    the heading text after the code is the outcome a person reads.
    """
    return MILESTONE_CODE_RE.sub("", title).strip() or title


def _human_change(raw: str) -> dict[str, Any]:
    """A Progress receipt shaped for a person: when, what kind, plain words.

    The raw line is machine grammar — ISO stamp, receipt keyword, commit
    hashes. A card shows none of that: hashes are dropped entirely, the
    keyword becomes a plain phrase, and the stamp is carried separately so
    the renderer can say "3 hours ago" instead of printing it.
    """
    text = " ".join(raw.split())
    when = None
    stamp = STAMP_RE.match(text)
    if stamp:
        when = stamp.group(1)
        text = text[stamp.end():]
    kind = None
    first = text.split(" ", 1)
    if first and first[0].rstrip(":") in RECEIPT_KINDS:
        kind = RECEIPT_KINDS[first[0].rstrip(":")]
        text = first[1] if len(first) > 1 else ""
    text = ID_SPLIT_RE.sub("", text)
    text = HASH_RE.sub("", text)
    text = re.sub(r"`\s*`", "", text)          # empty code spans a dropped hash leaves
    text = text.replace("`", "")
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    text = " ".join(text.split())
    if len(text) > MAX_ROW_TEXT:
        cut = text[: MAX_ROW_TEXT - 1]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        text = cut.rstrip(" ,;:—–-") + "…"
    # Gate the FINAL text: truncation and hash-stripping run first, so a
    # path that survives either of them is still refused here.
    return {"when": when, "kind": kind, "summary": _public(text)}


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
            title = " ".join(stripped[4:].split())
            if len(title) > 120:
                cut = title[:119]
                if " " in cut:
                    cut = cut[: cut.rfind(" ")]
                title = cut.rstrip(" ,;:—–-") + "…"
            current = {"title": title, "rows": []}
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
    return rows[-1]


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
            "title": _human_title(shown["title"]),
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
        "priority": _public(fields.get("priority")),
        "milestone": milestone,
        "contradictions_open": _open_contradictions(text),
        "latest_change": _human_change(latest) if (latest := _latest_progress(text)) else None,
    }
