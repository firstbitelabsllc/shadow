#!/usr/bin/env python3
"""shadow amp — project one paste-ready goal block from a repository's PLAN.md.

The goal is a POINTER to the durable plan, never a second copy of it. A goal
may drive work across many milestones and repos; no 4,000-character block can
carry that detail, so the block carries exactly enough to warm-start a seat —
authority pointer, mode, the one resume row with its proof, the milestone's
tooling line, and the standing rails — and defers everything else to the plan.

Deterministic: no LLM, no network. Same plan, same block. The per-milestone
tooling knowledge rides IN the plan (an optional `- tools:` line directly
under the `###` heading); amp only projects it. Pattern, not store.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

DEFAULT_MAX_CHARS: Final = 4_000

ROW_RE: Final = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?(?P<tail>(?: \| [a-z]+:.*)?)$"
)
FIELD_RE: Final = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
BRIEF_KEY_RE: Final = re.compile(r"^- (?P<key>Project|Mode|Priority|Loop): (?P<value>.+)$")
TOOLS_RE: Final = re.compile(r"^- tools: (?P<value>.+)$")
HASH_RE: Final = re.compile(r"~[0-9a-z]{4}\b")


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
    return {"brief": brief, "milestones": milestones, "contradictions": contradictions}


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


def _select(plan: dict, task_id: str | None) -> tuple[dict, dict] | None:
    """Return (milestone, row): the in_progress row first, else the first
    ready pending row, milestone order — the same order a cycle resumes in."""
    done = _completed_ids(plan["milestones"])
    if task_id:
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["id"] == task_id:
                    return milestone, row
        return None
    for state_pass in ("in_progress", "pending"):
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["state"] == state_pass and (
                    state_pass == "in_progress" or _ready(row, done)
                ):
                    return milestone, row
    return None


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except OSError:
        return ""


def _pointer(repo: Path, plan_path: Path) -> str:
    origin = _git(repo, "config", "--get", "remote.origin.url")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    sha = _git(repo, "rev-parse", "--short", "HEAD")
    where = origin or str(repo)
    at = f" @ {branch}@{sha}" if sha else ""
    rel = plan_path.name if plan_path.parent == repo else str(plan_path.relative_to(repo))
    return f"{rel}{at} in {where}"


def build_block(plan: dict, repo: Path, plan_path: Path,
                task_id: str | None, max_chars: int) -> tuple[str, list[str]]:
    selected = _select(plan, task_id)
    if selected is None:
        raise LookupError(
            "no open task reachable"
            if task_id is None
            else f"task {task_id} not found in the plan"
        )
    milestone, row = selected
    brief = plan["brief"]
    project = brief.get("Project", repo.name)
    loop = brief.get("Loop", f"/{project}-loop")

    dod = next((r for r in milestone["rows"] if r["dod"]), None)
    gates = [
        r for r in milestone["rows"]
        if r["state"] != "completed"
        and r["fields"].get("proof", "").startswith("gate ")
        and r is not row
        and r is not dod  # the DoD gets its own line; never list it twice
    ]

    header = f"/goal {project} — {milestone['title']}"
    authority = (
        f"AUTHORITY: {_pointer(repo, plan_path)} — section \"### {milestone['title']}\".\n"
        "This goal is a POINTER: the plan file is the sole authority; when this block and\n"
        "the plan disagree, the plan wins. First move: fetch, read that section at the\n"
        "current origin ref, and state the ref you read."
    )
    mode_bits = [f"MODE: {brief.get('Mode', 'explore')}"]
    if brief.get("Priority"):
        mode_bits.append(f"Priority: {brief['Priority']}")
    mode_bits.append(f"Loop: {loop}")
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
        "RAILS: one bounded task per cycle; no proof, no completed; run `shadow lint` "
        "before honoring a mode flip; append your own Progress rows, never rewrite "
        "another lane's; end by writing the next resume move into the plan.",
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
        raise ValueError(
            f"minimal block is {len(block)} chars (> {max_chars}); the resume row itself "
            "is too large — shrink the task line in the plan (see READ-FIT)."
        )
    return block, dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow amp",
        description="Project one paste-ready goal block from a repository-owned PLAN.md.",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    parser.add_argument("--plan", default=None, help="plan path (default: <repo>/PLAN.md)")
    parser.add_argument("--task", default=None, help="target one row by ~hash instead of auto-resume")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help=f"paste budget (default: {DEFAULT_MAX_CHARS})")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    plan_path = Path(args.plan).resolve() if args.plan else repo / "PLAN.md"
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
        print(f"shadow amp: {err} — if the milestone is done, mint the successor "
              "goal in the plan first (goal chaining).", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"shadow amp: {err}", file=sys.stderr)
        return 1

    sys.stdout.write(block)
    note = f"[amp] {len(block)}/{args.max_chars} chars"
    if dropped:
        note += f"; dropped to fit: {', '.join(dropped)} (all still in the plan)"
    print(note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
