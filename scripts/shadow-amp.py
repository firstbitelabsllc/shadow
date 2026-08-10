#!/usr/bin/env python3
"""shadow amp — project a paste-ready starting block from a repository's PLAN.md.

The goal is a POINTER to the durable plan, never a second copy of it. A goal
may drive work across many milestones and repos; no 4,000-character block can
carry that detail, so the block carries exactly enough to warm-start a seat —
authority pointer, mode, the selected starting row with its proof, the milestone's
tooling line, and the standing rails — and defers everything else to the plan.

Deterministic: no LLM, no network. Same plan, same block. The per-milestone
tooling knowledge rides IN the plan (an optional `- tools:` line directly
under the `###` heading); amp only projects it. Pattern, not store.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

DEFAULT_MAX_CHARS: Final = 4_000
MAX_GIT_VALUE: Final = 200

ROW_RE: Final = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?(?P<tail>(?: \| [a-z]+:.*)?)$"
)
FIELD_RE: Final = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
BRIEF_KEY_RE: Final = re.compile(r"^- (?P<key>Project|Mode|Priority|Loop): (?P<value>.+)$")
TOOLS_RE: Final = re.compile(r"^- tools: (?P<value>.+)$")
HASH_RE: Final = re.compile(r"~[0-9a-z]{4}\b")
ROW_SHAPE_RE: Final = re.compile(r"^- \[")
CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")


def _sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _thrown_ids(text: str) -> set:
    """Ids carrying a THROWN Progress line — dispatched, already in flight."""
    return set(re.findall(r"^- \S+ THROWN (~[0-9a-z]{4})\b", text, flags=re.M))


def _parse(text: str) -> dict:
    lines = text.splitlines()
    sections = _sections(lines)

    brief: dict[str, str] = {}
    for line in sections.get("Brief", []):
        match = BRIEF_KEY_RE.match(line)
        if match:
            brief.setdefault(match.group("key"), match.group("value").strip())

    milestones: list[dict] = []
    current: dict | None = None
    # Row-shaped lines the grammar rejects are REMEMBERED, never silently
    # dropped: a plan whose open work failed to parse would otherwise read as
    # "every task complete" and send the next seat chaining past real rows.
    unparsed: list[str] = []
    for line in sections.get("Tasks", []):
        if line.startswith("### "):
            current = {"title": line[4:].strip(), "tools": None, "rows": []}
            milestones.append(current)
            continue
        if current is None:
            continue
        tools = TOOLS_RE.match(line)
        if tools and not current["rows"]:
            current["tools"] = tools.group("value").strip()
            continue
        match = ROW_RE.match(line)
        if not match:
            if ROW_SHAPE_RE.match(line):
                unparsed.append(line.strip())
            continue
        row = match.groupdict()
        row["fields"] = {
            m.group("key"): m.group("value").strip()
            for m in FIELD_RE.finditer(row.get("tail") or "")
        }
        current["rows"].append(row)

    contradictions = [
        line for line in sections.get("Contradictions", []) if line.startswith("- ")
    ]
    return {
        "brief": brief,
        "milestones": milestones,
        "contradictions": contradictions,
        "unparsed": unparsed,
        "text": text,
        "thrown": _thrown_ids(text),
    }


def _completed_ids(milestones: list[dict]) -> set[str]:
    return {
        row["id"]
        for milestone in milestones
        for row in milestone["rows"]
        if row["state"] == "completed"
    }


def _ready(row: dict, done: set[str]) -> bool:
    needs = row["fields"].get("needs", "")
    return all(ref in done for ref in HASH_RE.findall(needs))


def _gated(row: dict) -> bool:
    """A `gate <owner> resume: ...` proof is a person-gated agent-side stop:
    the plan closes there and hands off, so auto-resume must never hand one
    to a seat as its own work. `--task ~hash` stays explicit and may target
    one — that is a person choosing, not the tool choosing for them."""
    return row["fields"].get("proof", "").startswith("gate ")


def _select(plan: dict, task_id: str | None) -> tuple[dict, dict] | None:
    """Return (milestone, row): the in_progress row first, else the first
    ready pending row, milestone order — the same order a cycle resumes in.
    Person-gated rows are never auto-selected."""
    done = _completed_ids(plan["milestones"])
    if task_id:
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["id"] == task_id:
                    return milestone, row
        return None
    # A row already THROWN is in flight elsewhere: auto-resume must skip it, or
    # a fresh seat re-runs work another conversation is doing right now. An
    # in_progress row WITHOUT a THROWN line is a hand-claimed resume target and
    # stays selectable — that split is what keeps crash-resume working.
    thrown = plan.get("thrown") or set()
    for state_pass in ("in_progress", "pending"):
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["id"] in thrown:
                    continue
                if row["state"] == state_pass and not _gated(row) and (
                    state_pass == "in_progress" or _ready(row, done)
                ):
                    return milestone, row
    return None


_LINT: object | None = None
_LINT_TRIED = False


def _lint_blocking(text: str) -> int | None:
    """Blocking `shadow lint` findings for this plan text, or None when the
    linter cannot be loaded. Parsing is deliberately tolerant, so a plan can
    parse into FEWER rows than it really has; only a lint-clean plan may be
    called finished."""
    global _LINT, _LINT_TRIED
    if not _LINT_TRIED:
        _LINT_TRIED = True
        path = Path(__file__).resolve().parent / "shadow-lint.py"
        try:
            spec = importlib.util.spec_from_file_location("shadow_lint", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("shadow_lint", module)
            spec.loader.exec_module(module)
            _LINT = module
        except Exception:  # a missing/broken linter must never break a projection
            _LINT = None
    if _LINT is None:
        return None
    try:
        return sum(
            1 for f in _LINT.lint_plan(text) if f.get("severity") == "blocking"
        )
    except Exception:  # same rule: the linter advises, it does not gate the parse
        return None


def unclean_note(plan: dict) -> str | None:
    """One sentence naming why this plan may not be readable as written, or
    None when it parses clean and lints clean."""
    parts = []
    if plan.get("unparsed"):
        parts.append(f"{len(plan['unparsed'])} row-shaped line(s) the grammar rejects")
    blocking = _lint_blocking(plan.get("text", ""))
    if blocking:
        parts.append(f"{blocking} blocking lint finding(s)")
    if not parts:
        return None
    return f"the plan does not read clean — {' and '.join(parts)}; run `shadow lint`"


def stall_reason(plan: dict) -> str:
    """Why auto-resume selected nothing — never 'all complete' while open rows
    remain, and never 'all complete' for a plan whose rows may not all have
    parsed. A plan can stall with work left: every open row person-gated,
    blocked, or waiting on unmet `needs:`. Saying 'mint the successor' there
    would tell a seat to chain past work nobody has done."""
    done = _completed_ids(plan["milestones"])
    open_rows = [
        row
        for milestone in plan["milestones"]
        for row in milestone["rows"]
        if row["state"] != "completed"
    ]
    unclean = unclean_note(plan)
    if not open_rows:
        if unclean:
            return f"{unclean} before chaining a successor over unread work"
        return "every task complete; mint the successor (goal chaining)"
    thrown = plan.get("thrown") or set()
    # A thrown row is the reason auto-resume passed over work that otherwise
    # looks takeable, so it is named rather than tallied as "other" — "in
    # flight elsewhere" and "nobody has picked this up" call for different moves.
    counts = {"person-gated": 0, "blocked": 0, "in flight elsewhere (thrown)": 0,
              "waiting on needs": 0, "other": 0}
    for row in open_rows:
        if _gated(row):
            counts["person-gated"] += 1
        elif row["state"] == "blocked":
            counts["blocked"] += 1
        elif row["id"] in thrown:
            counts["in flight elsewhere (thrown)"] += 1
        elif not _ready(row, done):
            counts["waiting on needs"] += 1
        else:
            counts["other"] += 1
    detail = ", ".join(f"{count} {name}" for name, count in counts.items() if count)
    advice = "hand off, unblock, or mint the successor"
    if counts["in flight elsewhere (thrown)"]:
        advice = ("probe the thrown row(s) with `shadow status --in-flight`, "
                  "hand off, unblock, or mint the successor")
    reason = f"nothing agent-takeable — {len(open_rows)} open row(s): {detail}; {advice}"
    return f"{reason} ({unclean})" if unclean else reason


def _clean(value: str, limit: int = MAX_GIT_VALUE) -> str:
    """Git metadata (a remote URL, a branch name) and free-text Brief values
    are repository-controlled data that land in a block a person pastes into
    an agent prompt. A value carrying newlines could otherwise append its own
    instruction lines, so control characters collapse to spaces and the value
    is bounded. Every such value goes through here — a plan is authority over
    what to work on, never authority over the rails around the work."""
    flat = CONTROL_RE.sub(" ", value).strip()
    return f"{flat[:limit]}…" if len(flat) > limit else flat


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return _clean(out.stdout) if out.returncode == 0 else ""
    except OSError:
        return ""


def _pointer(repo: Path, plan_path: Path) -> tuple[str, bool]:
    """(pointer, dirty). `dirty` is true when the plan on disk differs from
    the ref the pointer names — amp read the working tree, so the block must
    say so rather than advertise a ref that serves different content."""
    origin = _git(repo, "config", "--get", "remote.origin.url")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    sha = _git(repo, "rev-parse", "--short", "HEAD")
    where = origin or str(repo)
    rel = plan_path.name if plan_path.parent == repo else str(plan_path.relative_to(repo))
    dirty = bool(sha) and bool(_git(repo, "status", "--porcelain", "--", str(plan_path)))
    at = f" @ {branch}@{sha}" if sha else ""
    if dirty:
        at += " +UNCOMMITTED"
    return f"{rel}{at} in {where}", dirty


def build_block(plan: dict, repo: Path, plan_path: Path,
                task_id: str | None, max_chars: int) -> tuple[str, list[str]]:
    selected = _select(plan, task_id)
    if selected is None:
        raise LookupError(
            stall_reason(plan)
            if task_id is None
            else f"task {task_id} not found in the plan"
        )
    milestone, row = selected
    brief = plan["brief"]
    # Project rides the required header, which never drops, so it needs the
    # same bound as Mode, Priority, and Loop: unbounded, a 3,400-char Project
    # value evicted RAILS from a 4k block while amp still reported success.
    # The default loop derives from the cleaned value so both stay bounded.
    project = _clean(brief.get("Project", repo.name), 64)
    loop = _clean(brief.get("Loop", f"/{project}-loop"), 64)

    dod = next((r for r in milestone["rows"] if r["dod"]), None)
    gates = [
        r for r in milestone["rows"]
        if r["state"] != "completed"
        and r["fields"].get("proof", "").startswith("gate ")
        and r is not row
        and r is not dod  # the DoD gets its own line; never list it twice
    ]

    header = f"/goal {project} — {milestone['title']}"
    pointer, dirty = _pointer(repo, plan_path)
    authority = (
        f"AUTHORITY: {pointer} — section \"### {milestone['title']}\".\n"
        "This goal is a POINTER: the plan file is the sole authority; when this block and\n"
        "the plan disagree, the plan wins. First move: fetch, read that section at the\n"
        "current origin ref, and state the ref you read."
    )
    if dirty:
        # The block was projected from the WORKING TREE; the named ref serves
        # different content, so the pointer would lie to a seat that fetched
        # it. Say it in the part of the block that never drops.
        authority += (
            "\nUNCOMMITTED: this block was read from the working tree, which differs from\n"
            "the ref above — commit and push the plan before handing this goal to a seat."
        )
    mode_bits = [f"MODE: {_clean(brief.get('Mode', 'explore'), 16)}"]
    if brief.get("Priority"):
        mode_bits.append(f"Priority: {_clean(brief['Priority'])}")
    mode_bits.append(f"Loop: {_clean(loop, 64)}")
    mode_line = " | ".join(mode_bits)

    resume = f"RESUME: [{row['state']}] {row['text']} {row['id']}"
    proof = f"PROOF: {row['fields'].get('proof', 'MISSING — fix the plan before working')}"
    if row["fields"].get("needs"):
        proof += f" | needs: {row['fields']['needs']}"

    # Assembly order is also drop priority: optional parts vanish from the
    # bottom up until the block fits. The pointer and the resume never drop.
    required = [header, "", authority, "", mode_line, resume, proof]
    optional: list[tuple[str, str]] = []
    if milestone["tools"]:
        optional.append(("TOOLS", f"TOOLS: {milestone['tools']}"))
    if dod and dod is not row:
        dod_line = f"DoD: [{dod['state']}] {dod['text']} | proof: {dod['fields'].get('proof', '?')}"
        optional.append(("DOD", dod_line))
    if gates:
        gate_lines = "; ".join(f"{r['text']} {r['id']}" for r in gates)
        optional.append(("GATES", f"PERSON-GATED (do not take): {gate_lines}"))
    if plan["contradictions"]:
        optional.append((
            "CONTRA",
            f"CONTRADICTIONS OPEN: {len(plan['contradictions'])} — read ## Contradictions "
            "before landing any task.",
        ))
    optional.append((
        "RAILS",
        "RAILS: drain every reachable row needed by the Outcome; fan out safe disjoint "
        "claims; park only exact hard-rail wakes; no proof, no completed; run `shadow "
        "lint` before mode flips; append your own Progress rows, never rewrite another "
        "lane's; keep choosing successors until full acceptance.",
    ))

    kept = list(optional)
    dropped: list[str] = []
    while True:
        block = "\n".join(required + [line for _, line in kept]) + "\n"
        if len(block) <= max_chars or not kept:
            break
        name, _ = kept.pop()
        dropped.append(name)
    if len(block) > max_chars:
        # Name the part that is actually big AND shrinkable. This used to
        # always blame the resume row, sending people to shrink a 30-char task
        # line while an oversized Priority value was the real cause. The
        # authority pointer is deliberately excluded: it is fixed boilerplate
        # that no plan edit can shorten, so naming it is advice nobody can
        # follow — its cost is reported separately as the floor.
        part, size = max(
            (("resume row", len(resume)), ("proof line", len(proof)),
             ("mode/priority line", len(mode_line))),
            key=lambda pair: pair[1],
        )
        raise ValueError(
            f"minimal block is {len(block)} chars (> {max_chars}); {len(header) + len(authority)} "
            f"of that is the fixed authority pointer, and the largest plan-owned part is the "
            f"{part} at {size} chars — raise --max-chars or shrink that line (see READ-FIT)."
        )
    return block, dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow amp",
        description="Project a paste-ready starting block from a repository-owned PLAN.md.",
        epilog="Deterministic: no LLM, no network. amp reads a plan file and cannot see "
               "your conversation, so it projects the pointer, not the judgment; the "
               "judgment half is SKILL.md section 'Shape a goal'.",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    parser.add_argument("--plan", default=None, help="plan path (default: <repo>/PLAN.md)")
    parser.add_argument("--task", default=None, help="target one row by ~hash instead of auto-resume")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help=f"paste budget (default: {DEFAULT_MAX_CHARS})")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if args.plan:
        # A relative --plan is relative to the REPO, not the process cwd —
        # `shadow amp --repo /x --plan PLAN.md` must never read a same-named
        # plan that happens to sit in the caller's working directory.
        given = Path(args.plan)
        plan_path = (given if given.is_absolute() else repo / given).resolve()
    else:
        plan_path = repo / "PLAN.md"
    if not plan_path.is_file():
        print(f"shadow amp: no plan at {plan_path}", file=sys.stderr)
        return 2
    if args.task and not re.fullmatch(r"~[0-9a-z]{4}", args.task):
        print(f"shadow amp: --task wants a four-char id like ~ab12, got {args.task}",
              file=sys.stderr)
        return 2

    plan = _parse(plan_path.read_text(encoding="utf-8"))
    try:
        block, dropped = build_block(plan, repo, plan_path, args.task, args.max_chars)
    except LookupError as err:
        print(f"shadow amp: no goal to project — {err}.", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"shadow amp: {err}", file=sys.stderr)
        return 1

    sys.stdout.write(block)
    unclean = unclean_note(plan)
    if unclean:
        print(f"shadow amp: warning — {unclean}; rows it rejected are not in this block",
              file=sys.stderr)
    note = f"[amp] {len(block)}/{args.max_chars} chars"
    if dropped:
        note += f"; dropped to fit: {', '.join(dropped)} (all still in the plan)"
    print(note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
