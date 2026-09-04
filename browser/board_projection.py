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
from shadow_plan_grammar import contradiction_is_open  # noqa: E402


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
ID_SPLIT_RE = re.compile(r"\s+~[0-9a-z]{4,}\b")
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
    target = name.lower()
    start = next(
        (
            i + 1
            for i, line in enumerate(lines)
            if line.startswith("## ")
            and (
                line[3:].strip().lower() == target
                or line[3:].strip().lower().startswith(target + " ")
            )
        ),
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


def _public_row(row_text: str, fallback: str | None = None) -> str | None:
    """A bounded row a card may print, or the fallback when it is private.

    The bound runs first so the gate reads the exact string the renderer
    prints — a path that only survives past the cut is still refused.
    """
    return _public(_display(row_text)) or fallback


MILESTONE_CODE_RE = re.compile(r"^M\d+\s*[—–:-]+\s*")
STAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z?)\s+")
HASH_RE = re.compile(r"\b[0-9a-f]{12,64}\b")
ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")
REF_RE = re.compile(r"(?<![A-Za-z0-9_.-])(?:HEAD(?:~\d+)?\b|(?:refs/heads/|origin/|[A-Za-z0-9_.-]+/)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)")
PROVIDER_MODEL_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:gpt-\d+(?:\.\d+)?-[a-z][A-Za-z0-9.-]*|"
    r"(?:claude|openai|anthropic|gemini|opencode|langfuse|openrouter|xai|"
    r"google\s+ai|codex|cursor|grok|zai|codex-zai|sol|luna|terra|fable|opus|"
    r"sonnet|haiku|o[34]|deepseek|mistral|qwen|llama|cohere|perplexity|ollama|"
    r"bedrock|huggingface|vertex\s+ai|together\s+ai|fireworks(?:\s+ai)?|vllm)"
    r"(?:-[A-Za-z0-9.-]+)?|"
    r"glm-\d+(?:\.\d+)?(?:-[A-Za-z0-9.-]+)?)\b",
    re.IGNORECASE,
)
COMMAND_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:"
    r"`[^`\n]+`|"
    r"shadow\s+[a-z][a-z-]*|"
    r"git\s+[a-z][a-z-]*\b|"
    r"(?:npm|pnpm|yarn|bun)\s+(?:test|run|ci|install|build|lint|exec)\b|"
    r"python(?:\d+(?:\.\d+)*)?\s+(?:-m|-[cC]|\S+\.pyw?)\b|"
    r"pip\s+(?:install|uninstall|download|wheel|show|check)\b|"
    r"pytest(?:\s|$)|cargo\s+(?:test|build|run|check|fmt|clippy)\b|"
    r"(?:go|make)\s+(?:test|build|run|install|fmt|vet|generate|clean)\b|"
    r"(?:xcodebuild|curl|docker|npx)\s+\S+|"
    r"node\s+(?:--?\S+|\S+\.(?:js|mjs|cjs))|"
    r"gh\s+(?:run|pr|issue|repo|auth|workflow|api)\b|"
    r"kubectl\s+(?:get|apply|delete|describe|logs|exec|config)\b|"
    r"ssh\s+\S+@\S+|brew\s+(?:install|update|upgrade|uninstall|test)\b|"
    r"uv\s+(?:run|sync|pip|tool)\b|terraform\s+(?:init|plan|apply|destroy|validate)\b|"
    r"(?:commit|sha(?:256)?)\s*[:= -]*[0-9a-f]{7,64}\b)",
    re.IGNORECASE,
)
BRIEF_HASH_RE = re.compile(
    r"\b(?=[0-9a-f]{7,64}\b)[0-9a-f]*[a-f][0-9a-f]*\b",
    re.IGNORECASE,
)
BRIEF_UNSAFE_RE = re.compile(
    f"(?:{UNSAFE_TEXT_RE.pattern}|{ABSOLUTE_PATH_RE.pattern}|"
    f"{REF_RE.pattern}|{PROVIDER_MODEL_RE.pattern}|{COMMAND_RE.pattern}|"
    f"\\bbranch\\s+[A-Za-z0-9_.-]+|~[0-9a-z]{{4,}}\\b|{BRIEF_HASH_RE.pattern})",
    re.IGNORECASE,
)
RECEIPT_KINDS = {
    "STRUCT": "Plan structure changed",
    "PROOF": "Proof recorded",
    "NOTE": "Note",
    "THROWN": "Work claimed",
    "DECISION": "Decision recorded",
}


def _brief_public(text: str | None, fallback: str) -> str:
    """Return safe human copy for the four fields shown in a Brief card."""
    if not text:
        return fallback
    clean = " ".join(text.split())
    return clean if not BRIEF_UNSAFE_RE.search(clean) else fallback


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
    return sum(
        contradiction_is_open(line)
        for line in _section(text, "Contradictions")
    )


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
                "milestone": None, "contradictions_open": 0, "latest_change": None,
                "outcome": "Outcome not available yet.",
                "now": "Current work not available yet.",
                "risk": "No known risk.",
                "decision": "No decision needed right now."}

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
        # Every printed milestone string passes the same gate as the priority
        # and the latest change. A heading and a DoD still need words for the
        # card to read, so those withhold to a neutral label; a current/next
        # line simply drops, which the renderer already handles.
        milestone = {
            "title": _brief_public(_human_title(shown["title"]), "Milestone"),
            "counts": counts,
            "current": _public_row(current["text"]) if current else None,
            "next": _public_row(nxt["text"]) if nxt else None,
            "dod": {
                "state": dod["state"],
                "text": _public_row(dod["text"], "Checkpoint text withheld"),
            } if dod else None,
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

    shown_rows = shown["rows"] if shown else []
    blocked = next((row for row in shown_rows if row["state"] == "blocked"), None)
    current = next(
        (row for row in shown["rows"] if row["state"] == "in_progress"), None
    ) if shown else None
    pending = next(
        (row for row in shown["rows"] if row["state"] == "pending"), None
    ) if shown else None
    is_gate = lambda row: bool(
        re.search(r"\|\s*proof\s*:\s*gate\b", row["text"], re.IGNORECASE)
    )
    decision_row = None
    if current is not None and is_gate(current):
        decision_row = current
    elif pending is not None and is_gate(pending):
        decision_row = pending
    elif current is None and pending is None and blocked is not None and is_gate(blocked):
        decision_row = blocked
    blocked_elsewhere = sum(
        row["state"] == "blocked"
        for milestone_group in milestones
        for row in milestone_group["rows"]
    )
    open_risks = _open_contradictions(text)
    if blocked is not None:
        count = sum(row["state"] == "blocked" for row in shown_rows)
        noun = "item" if count == 1 else "items"
        verb = "is" if count == 1 else "are"
        risk = f"{count} {noun} in the active milestone {verb} blocked."
    elif blocked_elsewhere:
        if blocked_elsewhere == 1:
            risk = "1 other blocked item needs attention."
        else:
            risk = f"{blocked_elsewhere} other blocked items need attention."
    elif open_risks:
        suffix = "" if open_risks == 1 else "s"
        risk = f"{open_risks} unresolved risk{suffix} remain."
    else:
        risk = "No known risk."

    if current is not None:
        now = "Work is in progress."
    elif pending is not None:
        now = "The next task is ready."
    elif blocked is not None:
        now = "This milestone is blocked."
    else:
        now = "No work is waiting right now."

    return {
        "schema": BOARD_SCHEMA,
        "state": state,
        "priority": _public(fields.get("priority")),
        "milestone": milestone,
        "contradictions_open": _open_contradictions(text),
        "latest_change": _human_change(latest) if (latest := _latest_progress(text)) else None,
        "outcome": _brief_public(
            fields.get("milestone") or fields.get("outcome"),
            "Outcome not available yet.",
        ),
        "now": _brief_public(fields.get("next"), now),
        "risk": _brief_public(fields.get("risk"), risk),
        "decision": (
            _brief_public(fields.get("decision"), "A decision is needed to continue.")
            if decision_row else "No decision needed right now."
        ),
    }
