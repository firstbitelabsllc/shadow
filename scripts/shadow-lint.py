#!/usr/bin/env python3
"""Shadow's plan-grammar enforcer.

Reads one or more PLAN.md files and reports findings against the grammar v2
contract. Deterministic: same text, same findings, same order. Exit is
non-zero when any blocking finding exists. No LLM, no network, stdlib only.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import re
import sys
from pathlib import Path
from typing import Final


sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_scrub_lib import SECRET_SHAPE_RE  # noqa: E402


LEGAL_MODES: Final = {"explore", "ship"}
LEGACY_MODES: Final = {"Spike", "Defer", "Challenge", "Broad", "Close"}
STATES: Final = ("pending", "in_progress", "blocked", "completed")
ROW_RE: Final = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?(?P<tail>(?: \| [a-z]+:.*)?)$"
)
ROW_LOOSE_RE: Final = re.compile(r"^- \[[^\]]*\] ")
FIELD_RE: Final = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
NEEDS_VALUE_RE: Final = re.compile(r"~[0-9a-z]{4}(?:[,\s]+~[0-9a-z]{4})*")
PROOF_CLASS_RE: Final = re.compile(r"^(?:cmd|read|gate) \S")
MODE_RE: Final = re.compile(r"^- Mode: (?P<value>.+)$")
HASH_RE: Final = re.compile(r"~[0-9a-z]{4}\b")
TS_RE: Final = re.compile(r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) ")
SPIKE_RE: Final = re.compile(r"^- \S+ SPIKE (?P<id>~[0-9a-z]{4}) (?P<text>.+)$")
DECISION_RE: Final = re.compile(r"^- \S+ DECISION (?P<id>~[0-9a-z]{4}) (?:keep|kill|promote)\b")
ENDS_RE: Final = re.compile(r"\| ends: (?P<date>\S+)\s*$")
MAX_LINE_CHARS: Final = 2_000


def _finding(check: str, line: int, severity: str, detail: str) -> dict:
    return {"check": check, "line": line, "severity": severity, "detail": detail}


def _sections(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    sections: dict[str, list[tuple[int, str]]] = {}
    current = ""
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append((number, line))
    return sections


def lint_plan(text: str, *, today: date | None = None) -> list[dict]:
    findings: list[dict] = []
    lines = text.splitlines()
    sections = _sections(lines)
    today = today or date.today()

    # Section dispatch is exact-string: a typo'd or missing canonical heading
    # would otherwise exempt everything under it from every check, silently.
    for canonical in ("Brief", "Tasks", "Progress"):
        if canonical not in sections:
            findings.append(_finding("SECTION-MISSING", 0, "warning", f"no `## {canonical}` heading"))
    # A typo'd Tasks heading must not silently exempt its rows from every
    # blocking check: row-shaped lines with no canonical section to own them
    # block outright. History sections alongside a real Tasks section stay legal.
    if "Tasks" not in sections:
        for number, line in enumerate(lines, 1):
            if ROW_LOOSE_RE.match(line):
                findings.append(
                    _finding("ROWS-WITHOUT-TASKS", number, "blocking", "task-shaped row with no `## Tasks` section")
                )
                break

    for number, line in enumerate(lines, 1):
        if len(line) > MAX_LINE_CHARS:
            findings.append(_finding("READ-FIT", number, "warning", f"line is {len(line)} chars"))
        # The whole plan is committed and pushed; a secret anywhere in it —
        # especially pasted command output in Progress PROOF lines — must block.
        if SECRET_SHAPE_RE.search(line):
            findings.append(_finding("PLAN-SECRET", number, "blocking", "line carries a secret-shaped value"))

    for number, line in ((n, l) for n, l in sections.get("Brief", []) if MODE_RE.match(l)):
        value = MODE_RE.match(line).group("value").strip()
        if value not in LEGAL_MODES:
            kind = "legacy mode" if value in LEGACY_MODES else "illegal mode"
            findings.append(_finding("MODE-ILLEGAL", number, "blocking", f"{kind}: {value}"))
    mode_ship = any(
        MODE_RE.match(l) and MODE_RE.match(l).group("value").strip() == "ship"
        for _, l in sections.get("Brief", [])
    )

    ids: dict[str, tuple[int, str]] = {}
    needs_refs: list[tuple[int, str]] = []
    milestone_rows: list[list[tuple[int, dict]]] = []
    current_rows: list[tuple[int, dict]] | None = None
    for number, line in sections.get("Tasks", []):
        if line.startswith("### "):
            current_rows = []
            milestone_rows.append(current_rows)
            continue
        match = ROW_RE.match(line)
        if not match:
            if ROW_LOOSE_RE.match(line):
                if "| proof:" not in line:
                    findings.append(_finding("PROOF-MISSING", number, "blocking", "row has no proof field"))
                else:
                    findings.append(_finding("ROW-SHAPE", number, "blocking", "row does not match the grammar"))
            continue
        row = match.groupdict()
        row_id = row["id"]
        if row_id in ids:
            findings.append(_finding("ID-DUP", number, "blocking", f"{row_id} first used on line {ids[row_id][0]}"))
        else:
            ids[row_id] = (number, row["state"])
        tail = row["tail"] or ""
        pairs = FIELD_RE.findall(tail)
        # Every byte of the tail must be accounted for by a parsed field: an
        # embedded " | " inside a value would otherwise silently truncate what
        # the proof (and the secret scan, and accept's rerun) actually sees.
        if "".join(f" | {key}: {value}" for key, value in pairs) != tail:
            findings.append(_finding("ROW-SHAPE", number, "blocking", "tail has residue outside `| key: value` fields"))
        if len(pairs) != len({key for key, _ in pairs}):
            findings.append(_finding("ROW-SHAPE", number, "blocking", "a tail field key repeats"))
        fields = dict(pairs)
        proof = fields.get("proof", "").strip()
        if not proof:
            findings.append(_finding("PROOF-MISSING", number, "blocking", "row has no proof field"))
        elif not PROOF_CLASS_RE.match(proof):
            findings.append(_finding("PROOF-CLASS", number, "blocking", "proof must be classed cmd | read | gate"))
        needs_value = fields.get("needs", "").strip()
        if needs_value and NEEDS_VALUE_RE.fullmatch(needs_value) is None:
            findings.append(_finding("NEEDS-SHAPE", number, "blocking", "needs must be ~hash ids only"))
        for target in HASH_RE.findall(needs_value):
            needs_refs.append((number, target))
        if current_rows is not None:
            current_rows.append((number, row))

    for number, target in needs_refs:
        if target not in ids:
            findings.append(_finding("NEEDS-DANGLE", number, "blocking", f"needs target {target} does not exist"))

    for rows in milestone_rows:
        if len(rows) < 2:
            continue
        dod = [(n, r) for n, r in rows if r["dod"]]
        if len(dod) != 1:
            findings.append(
                _finding("DOD-COUNT", rows[0][0], "blocking", f"milestone has {len(dod)} (DoD) rows, needs exactly 1")
            )
            continue
        dod_number, dod_row = dod[0]
        siblings_open = any(r["state"] != "completed" for n, r in rows if not r["dod"])
        if dod_row["state"] == "completed" and siblings_open:
            findings.append(_finding("DOD-EARLY", dod_number, "blocking", "DoD flipped before its siblings"))

    for number, line in sections.get("Deferred", []):
        if line.startswith("- ") and not re.search(r"(?:^|\| )wake: \S", line):
            findings.append(_finding("DEFER-NO-WAKE", number, "blocking", "deferral without a wake predicate"))

    previous: tuple[str, int] | None = None
    spikes: dict[str, tuple[int, date | None]] = {}
    decisions: dict[str, int] = {}
    for number, line in sections.get("Progress", []):
        ts_match = TS_RE.match(line)
        if ts_match:
            stamp = ts_match.group("ts")
            if previous and stamp < previous[0]:
                findings.append(
                    _finding("TS-ORDER", number, "warning", f"timestamp precedes line {previous[1]}")
                )
            previous = (stamp, number)
        spike = SPIKE_RE.match(line)
        if spike:
            ends = ENDS_RE.search(line)
            end_date: date | None = None
            if ends:
                try:
                    end_date = datetime.strptime(ends.group("date"), "%Y-%m-%d").date()
                except ValueError:
                    end_date = None
            if end_date is None:
                findings.append(_finding("SPIKE-NO-END", number, "blocking", "a spike that never ends is not a spike"))
            if spike.group("id") in spikes:
                findings.append(
                    _finding("SPIKE-DUP", number, "blocking", "re-spiking an id would reset its expiry; decision first")
                )
            else:
                spikes[spike.group("id")] = (number, end_date)
        decision = DECISION_RE.match(line)
        if decision:
            decisions[decision.group("id")] = number
    open_expired = False
    for spike_id, (number, end_date) in spikes.items():
        if end_date is not None and end_date < today and spike_id not in decisions:
            findings.append(
                _finding("SPIKE-EXPIRED-NO-DECISION", number, "blocking", f"spike {spike_id} expired with no decision")
            )
            open_expired = True
    for decision_id, number in decisions.items():
        if decision_id not in spikes:
            findings.append(_finding("ORPHAN-DECISION", number, "warning", f"decision {decision_id} has no spike"))
    if open_expired and mode_ship:
        findings.append(
            _finding("SHIP-OVER-OPEN-SPIKE", 0, "blocking", "ship mode with an expired undecided spike")
        )

    return sorted(findings, key=lambda f: (f["line"], f["check"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plans", nargs="+", type=Path)
    args = parser.parse_args(argv)
    worst = 0
    for path in args.plans:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"{path}: unreadable: {exc}")
            worst = 1
            continue
        findings = lint_plan(text)
        for finding in findings:
            print(f"{path}:{finding['line']}: {finding['check']} [{finding['severity']}] {finding['detail']}")
            if finding["severity"] == "blocking":
                worst = 1
        if not findings:
            print(f"{path}: clean")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
