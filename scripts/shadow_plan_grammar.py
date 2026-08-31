"""The one executable grammar for Shadow PLAN task rows and cmd proofs.

The linter, projector, lifecycle, board, and accept path all read the same
PLAN.md.  Keeping their row and receipt patterns here prevents one surface
from accepting work another surface cannot safely execute or recover.
"""

from __future__ import annotations

import re
import shlex
from typing import Final


ROW_ID_RE: Final = re.compile(r"^~[0-9a-z]{4}$")
NEEDS_REF_RE: Final = re.compile(r"~[0-9a-z]{4}")
HASH_RE: Final = re.compile(r"~[0-9a-z]{4}\b")
ROW_RE: Final = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?(?P<tail>(?: \| [a-z]+:.*)?)$"
)
ROW_LOOSE_RE: Final = re.compile(r"^- \[[^\]]*\] ")
HOT_TASK_ROW_RE: Final = ROW_RE
FIELD_RE: Final = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
NEEDS_VALUE_RE: Final = re.compile(r"~[0-9a-z]{4}(?:[,\s]+~[0-9a-z]{4})*")
PROOF_CLASS_RE: Final = re.compile(r"^(?:cmd|read|gate) \S")
PROOF_MARKER_RE: Final = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}")
PROOF_FLOOR_RE: Final = re.compile(r"[1-9][0-9]{0,8}")
PROOF_RECEIPT_PREFIX_RE: Final = re.compile(
    r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
    r"(?P<id>~[0-9a-z]{4}) PROOF\b"
)
PROOF_RECEIPT_RE: Final = re.compile(
    r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
    r"(?P<id>~[0-9a-z]{4}) PROOF (?P<proof>.+) -> (?P<result>.+)$"
)
PROOF_LINE_RE: Final = re.compile(r"^- \S+ (?P<id>~[0-9a-z]{4}) PROOF\b")
CONTRADICTION_RESOLVED_RE: Final = re.compile(r"^- RESOLVED(?:\s|:|$)")
CONTRADICTION_NONE_RE: Final = re.compile(
    r"^- none(?: recorded)? yet\.?$",
    re.IGNORECASE,
)
ORIGIN_LINE_RE: Final = re.compile(r"^- Origin:(?: (?P<value>.*))?$")

# `shadow accept` executes a proof with argv, never an implicit shell.  These
# helpers are shared so lint rejects precisely the argument shapes accept would
# otherwise run only partially.
SHELL_PUNCTUATION: Final = "();<>|&"
SHELLS: Final = frozenset({"bash", "sh", "zsh", "/bin/bash", "/bin/sh", "/usr/bin/env"})


def proof_argv(command: str) -> list[str]:
    """Split the exact command accept will execute, raising ValueError on bad quotes."""
    return shlex.split(command)


def shell_script_index(argv: list[str]) -> int:
    """Return the single ``-c`` script token a deliberate shell interprets."""
    if not argv or argv[0] not in SHELLS:
        return -1
    for index in (1, 2):
        if index < len(argv) and argv[index] == "-c":
            return index + 1
    return -1


def shell_operators(command: str) -> list[str]:
    """Return unquoted shell operators that would be literal argv arguments."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    if not tokens:
        return []
    script = shell_script_index(tokens)
    return sorted(
        {
            token
            for index, token in enumerate(tokens)
            if index and index != script and all(char in SHELL_PUNCTUATION for char in token)
        }
    )


def progress_proof_receipt(line: str) -> tuple[str, str, str] | None:
    """Parse the canonical ``Progress`` receipt consumed by lint and claims."""
    match = PROOF_RECEIPT_RE.match(line)
    if match is None:
        return None
    return match.group("id"), match.group("proof"), match.group("result")


def brief_origin_values(plan_text: str) -> list[str]:
    """Return every Brief ``Origin:`` value, including empty declarations."""
    values: list[str] = []
    in_brief = False
    for line in plan_text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            in_brief = heading == "Brief" or heading.startswith("Brief ")
            continue
        if not in_brief:
            continue
        match = ORIGIN_LINE_RE.fullmatch(line)
        if match is not None:
            values.append((match.group("value") or "").strip())
    return values


def candidate_row_ids(plan_text: str, claimed: set[str] | None = None) -> list[str]:
    """Return agent-takeable rows in canonical in-progress/pending order.

    Only Tasks-section rows are checkpoints: a row-shaped line inside a
    Contradictions bullet or a Progress note is prose that quotes a row, never
    a takeable one — the same universe the plan parser models.
    """
    rows: list[tuple[str, str, dict[str, str]]] = []
    completed: set[str] = set()
    in_tasks = False
    for line in plan_text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            in_tasks = heading == "Tasks" or heading.startswith("Tasks ")
            continue
        if not in_tasks:
            continue
        match = ROW_RE.fullmatch(line)
        if match is None:
            continue
        fields = {
            field.group("key"): field.group("value").strip()
            for field in FIELD_RE.finditer(match.group("tail"))
        }
        row = match.group("id")
        state = match.group("state")
        rows.append((state, row, fields))
        if state == "completed":
            completed.add(row)
    unavailable = set(claimed or ())
    result: list[str] = []
    for state_pass in ("in_progress", "pending"):
        for state, row, fields in rows:
            if (
                state != state_pass
                or row in unavailable
                or fields.get("proof", "").startswith("gate ")
                or (
                    state_pass == "pending"
                    and any(
                        need not in completed
                        for need in NEEDS_REF_RE.findall(fields.get("needs", ""))
                    )
                )
            ):
                continue
            result.append(row)
    return result


def contradiction_is_open(line: str) -> bool:
    """Return whether a canonical Contradictions bullet is unresolved.

    ``winner`` and ``provisional winner`` record a current judgment, not a
    delivered resolution. Only the explicit leading ``RESOLVED`` marker
    closes a real bullet. The conventional ``None ...`` sentinel is not a
    contradiction at all.
    """
    stripped = line.strip()
    if not stripped.startswith("- ") or CONTRADICTION_NONE_RE.match(stripped):
        return False
    return CONTRADICTION_RESOLVED_RE.match(stripped) is None
