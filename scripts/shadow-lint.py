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
import shlex
import shutil
import sys
from pathlib import Path
from typing import Final


sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_scrub_lib import SECRET_SHAPE_RE  # noqa: E402
import shadow_root_board as _board  # noqa: E402


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
# This is the row law rather than the plan-wide policy law.  `shadow accept`
# imports this named surface before it flips a row: copying these checks into
# another parser is how the enforcer and the only completion path drifted.
ROW_GRAMMAR_CHECKS: Final = frozenset({
    "ROWS-WITHOUT-TASKS",
    "ROW-SHAPE",
    "ID-DUP",
    "PROOF-MISSING",
    "PROOF-CLASS",
    "PROOF-UNPARSEABLE",
    "PROOF-SHELL-OPERATOR",
    "PROOF-ARGV0",
    "NEEDS-SHAPE",
    "NEEDS-DANGLE",
})


def _finding(check: str, line: int, severity: str, detail: str) -> dict:
    return {"check": check, "line": line, "severity": severity, "detail": detail}


# `shadow accept` runs a cmd proof through `shlex.split` with NO shell, so
# `&&`, `|`, `;`, `$(...)` and redirects arrive as literal ARGUMENTS to argv[0].
# `cmd echo done && shadow --version` therefore lints clean, runs `echo`, exits
# 0, flips the row to completed and writes `-> pass` — while `shadow` never
# ran. Validating the class word alone cannot see that; the argv can.
SHELL_PUNCTUATION: Final = "();<>|&"
SHELLS: Final = frozenset({"bash", "sh", "zsh", "/bin/bash", "/bin/sh", "/usr/bin/env"})


def _shell_script_index(argv: list[str]) -> int:
    """Index of the -c script — the ONE token a deliberate shell interprets.

    Exempting the whole argv here was the same false green one level up:
    `cmd bash -c 'true' && shadow --version` hands `true` to bash and passes
    `&&`, `shadow`, `--version` to it as positional arguments it never runs.
    """
    if argv[0] not in SHELLS:
        return -1
    for index in (1, 2):
        if index < len(argv) and argv[index] == "-c":
            return index + 1
    return -1


def _shell_operators(command: str) -> list[str]:
    """Unquoted shell metacharacters in argument position, worst-first.

    Comparing whole `shlex.split` tokens missed the operator written without a
    space: `echo done&& false` splits to `done&&`, which equals no operator, so
    the check passed while accept still ran `echo` alone. A second parse with
    `punctuation_chars` is the discriminator the plain argv cannot give — it
    breaks an unquoted metacharacter out into its own token and leaves a quoted
    `'a&&b'` whole, which is exactly the difference between an operator a shell
    would have interpreted and a literal the proof means to pass.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []  # PROOF-UNPARSEABLE owns unbalanced quoting; do not double-report
    if not tokens:
        return []
    script = _shell_script_index(tokens)
    return sorted({
        token for index, token in enumerate(tokens)
        if index and index != script and all(char in SHELL_PUNCTUATION for char in token)
    })


def _check_cmd_proof(command: str, number: int, root: Path | None = None) -> list[dict]:
    """A cmd proof must be a runnable argv, because that is how accept runs it."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return [_finding("PROOF-UNPARSEABLE", number, "blocking",
                         f"cmd proof does not parse as a command line: {exc}")]
    if not argv:
        return [_finding("PROOF-UNPARSEABLE", number, "blocking", "cmd proof is empty")]
    offenders = _shell_operators(command)
    if offenders:
        return [_finding("PROOF-SHELL-OPERATOR", number, "blocking",
                         f"{' '.join(offenders)} is passed as a literal argument to "
                         f"`{argv[0]}`, not interpreted — accept runs proofs without a shell. "
                         f"Wrap it: cmd bash -c '<the whole command>'")]
    # A proof naming a command that exists nowhere can never pass, so it is a
    # rotted receipt pretending to be a predicate. Only checked when the plan's
    # own directory is known — resolving an in-tree path needs it, and guessing
    # would turn an unknowable into a false accusation.
    if root is not None and not _resolves(argv[0], root):
        # Severity follows the evidence. A path is answered by the repository
        # itself, so the same text gives the same finding anywhere: blocking.
        # A bare name is answered by this machine's PATH, which is not the
        # plan's text — blocking on it would make the gate's exit code depend
        # on what happens to be installed on the runner, against this file's
        # determinism contract. It is still worth saying out loud.
        if "/" in argv[0]:
            return [_finding("PROOF-ARGV0", number, "blocking",
                             f"`{argv[0]}` is not in this repository, so this proof can never run")]
        return [_finding("PROOF-ARGV0", number, "warning",
                         f"`{argv[0]}` is not on this machine's PATH, so this proof cannot run "
                         "here — install it or name an in-tree path")]
    return []


def _resolves(program: str, root: Path) -> bool:
    if "/" in program:
        candidate = Path(program)
        if candidate.is_absolute():
            return candidate.exists()
        return (root / program).exists()
    return shutil.which(program) is not None


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


# A heading may carry a suffix — `## Deferred (v3)`, `## Brief — the north
# star`. PR #272 fixed that for Deferred and left every sibling exact-string,
# so a suffixed `## Brief` silently downgraded MODE-ILLEGAL from blocking to a
# warning. One accessor, so a future section cannot be half-fixed again.
def _section(sections: dict[str, list[tuple[int, str]]], name: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for heading, entries in sections.items():
        if heading == name or heading.startswith(name + " "):
            found.extend(entries)
    return found


def _has_section(sections: dict[str, list[tuple[int, str]]], name: str) -> bool:
    return any(h == name or h.startswith(name + " ") for h in sections)


def row_grammar_findings(text: str, *, root: Path | None = None) -> list[dict]:
    """Return the blocking row-law findings a completion must also refuse.

    This is deliberately a projection of ``lint_plan`` rather than a second
    parser.  The plan enforcer remains the sole definition of task shape; the
    flip path merely asks it for the subset that says whether any row is safe
    to interpret as a task.
    """
    return [
        finding
        for finding in lint_plan(text, root=root)
        if finding["severity"] == "blocking" and finding["check"] in ROW_GRAMMAR_CHECKS
    ]


def lint_plan(text: str, *, today: date | None = None, root: Path | None = None) -> list[dict]:
    findings: list[dict] = []
    lines = text.splitlines()
    sections = _sections(lines)
    today = today or date.today()
    budget = _board.hot_plan_budget(text.encode("utf-8"))
    for dimension in budget["exceeded"]:
        check = {
            "bytes": "HOT-PLAN-BYTES",
            "task_rows": "HOT-PLAN-ROWS",
            "milestones": "HOT-PLAN-MILESTONES",
        }[dimension]
        findings.append(
            _finding(
                check,
                0,
                "blocking",
                f"{dimension} is {budget[dimension]} (limit {budget['limits'][dimension]}); "
                "archive one proven milestone with shadow lifecycle",
            )
        )

    # Section dispatch recognizes a canonical heading or that heading plus a
    # suffix. A typo'd or missing canonical prefix must not silently exempt the
    # section from its checks.
    for canonical in ("Brief", "Tasks", "Progress"):
        if not _has_section(sections, canonical):
            findings.append(_finding("SECTION-MISSING", 0, "warning", f"no `## {canonical}` heading"))
    # A typo'd Tasks heading must not silently exempt its rows from every
    # blocking check: row-shaped lines with no canonical section to own them
    # block outright. History sections alongside a real Tasks section stay legal.
    if not _has_section(sections, "Tasks"):
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

    for number, line in ((n, l) for n, l in _section(sections, "Brief") if MODE_RE.match(l)):
        value = MODE_RE.match(line).group("value").strip()
        if value not in LEGAL_MODES:
            kind = "legacy mode" if value in LEGACY_MODES else "illegal mode"
            findings.append(_finding("MODE-ILLEGAL", number, "blocking", f"{kind}: {value}"))
    mode_ship = any(
        MODE_RE.match(l) and MODE_RE.match(l).group("value").strip() == "ship"
        for _, l in _section(sections, "Brief")
    )

    ids: dict[str, tuple[int, str]] = {}
    needs_refs: list[tuple[int, str]] = []
    milestone_rows: list[list[tuple[int, dict]]] = []
    current_rows: list[tuple[int, dict]] | None = None
    # Row grammar runs over the WHOLE file, because `shadow accept` builds its
    # row list from every line of the plan and will flip a row wherever it
    # sits. Scoping the enforcer to `## Tasks` while the only flip path scans
    # everything left every row under any other heading with ZERO checks and
    # still flippable — the enforcer and the flip path disagreeing about what a
    # task is. Milestone grouping stays Tasks-scoped: DoD law is about
    # milestones, not about every task-shaped line in the file.
    in_tasks = False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            heading = line[3:].strip()
            in_tasks = heading == "Tasks" or heading.startswith("Tasks ")
            continue
        if line.startswith("### "):
            if in_tasks:
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
            findings.append(_finding("ROW-SHAPE", number, "blocking", "the row repeats a tail field key"))
        fields = dict(pairs)
        proof = fields.get("proof", "").strip()
        if not proof:
            findings.append(_finding("PROOF-MISSING", number, "blocking", "row has no proof field"))
        elif not PROOF_CLASS_RE.match(proof):
            findings.append(_finding("PROOF-CLASS", number, "blocking", "proof must be classed cmd | read | gate"))
        elif proof.startswith("cmd "):
            findings.extend(_check_cmd_proof(proof[4:], number, root))
        needs_value = fields.get("needs", "").strip()
        if needs_value and NEEDS_VALUE_RE.fullmatch(needs_value) is None:
            findings.append(_finding("NEEDS-SHAPE", number, "blocking", "needs must be ~hash ids only"))
        for target in HASH_RE.findall(needs_value):
            needs_refs.append((number, target))
        if in_tasks and current_rows is not None:
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

    # Match by PREFIX, not by exact heading. "## Deferred proof (not a global
    # blocker)" is a legal heading and it silently disabled this entire check:
    # the reference plan carried 47 wake-predicate-less rows, invisible to its
    # own enforcer, because the section name had four extra words.
    # Section order drifted unnoticed because sections are read into a dict,
    # so nothing compared their positions. Progress is append-only, which makes
    # it the worst one to leave in the middle: every cycle buries whatever sits
    # below it a little deeper, and a cold reader scrolls past a thousand lines
    # of receipts to reach the open deferrals.
    order = [line[3:].strip() for _, line in
             ((n, l) for n, l in enumerate(lines, 1) if l.startswith("## "))]
    canonical = [name for name in ("Brief", "Tasks", "Deferred", "Contradictions", "Progress")
                 if any(s == name or s.startswith(name + " ") for s in order)]
    seen = [name for s in order for name in canonical
            if s == name or s.startswith(name + " ")]
    if seen != canonical:
        findings.append(_finding(
            "SECTION-ORDER", 0, "warning",
            f"sections read {' -> '.join(seen)}; the grammar prints "
            f"{' -> '.join(canonical)} — Progress is append-only and belongs last",
        ))

    # A plan carrying conflict markers linted CLEAN, which is how a half-merged
    # PLAN.md reaches a commit. It matters more now that several leads write one
    # plan: `shadow throw` refuses on unmerged paths, but nothing caught a
    # marker that was already committed.
    for number, line in enumerate(lines, 1):
        if line.startswith(("<<<<<<< ", ">>>>>>> ")) or line.rstrip() == "=======":
            findings.append(_finding(
                "CONFLICT-MARKER", number, "blocking",
                "unresolved merge conflict in the plan — resolve it before anything reads this",
            ))

    deferred: list[tuple[int, str]] = []
    for name, entries in sections.items():
        if name == "Deferred" or name.startswith("Deferred "):
            deferred.extend(entries)
    for number, line in deferred:
        if line.startswith("- ") and not re.search(r"(?:^|\| )wake: \S", line):
            findings.append(_finding("DEFER-NO-WAKE", number, "blocking", "deferral without a wake predicate"))

    previous: tuple[str, int] | None = None
    spikes: dict[str, tuple[int, date | None]] = {}
    decisions: dict[str, int] = {}
    for number, line in _section(sections, "Progress"):
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

    # "No proof, no completed" is the product's central claim, and until 0.1.0
    # nothing enforced it: a row hand-flipped to [completed] with zero PROOF
    # lines linted clean, and status then reported "every task complete; mint
    # the successor". Shape was checked; truth was not. A completed row must
    # name its receipt in Progress — that pairing is the whole contract.
    for row_id, (number, state) in ids.items():
        if state == "completed" and not _board.progress_proof_receipts(text, row_id):
            findings.append(
                _finding(
                    "COMPLETED-NO-PROOF", number, "blocking",
                    f"{row_id} is completed with no canonical '<ts> {row_id} PROOF ... -> result' line in ## Progress; "
                    "run `shadow accept` for a cmd proof, or re-observe a read/gate proof and "
                    "append the line with the flip",
                )
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
        findings = lint_plan(text, root=path.resolve().parent)
        for finding in findings:
            print(f"{path}:{finding['line']}: {finding['check']} [{finding['severity']}] {finding['detail']}")
            if finding["severity"] == "blocking":
                worst = 1
        if not findings:
            print(f"{path}: clean")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
