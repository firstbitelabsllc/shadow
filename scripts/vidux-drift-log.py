#!/usr/bin/env python3
"""Record planned-vs-actual drift in a Vidux PLAN.md.

The helper makes the UNIFY step mechanical: write a structured Drift Log entry,
optionally block the stale task, append follow-up tasks, and mirror a compact
note into subplans that need to adapt with the parent plan.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TASK_RE = re.compile(r"^(\s*-\s*)\[(pending|in_progress| )\](.*)$")


@dataclass(frozen=True)
class DriftEntry:
    task: str
    planned: str
    actual: str
    why: str
    plan_update: str
    next_step: str
    drift_id: str | None = None
    today: str | None = None


def _clean(value: str, *, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def _section_bounds(text: str, heading: str) -> tuple[int, int] | None:
    matches = list(H2_RE.finditer(text))
    wanted = heading.lower()
    for index, match in enumerate(matches):
        if match.group(1).strip().lower() != wanted:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return match.start(), end
    return None


def _insert_section(text: str, heading: str, *, before: str | None = None) -> str:
    if _section_bounds(text, heading):
        return text
    insert_at = len(text)
    if before:
        bounds = _section_bounds(text, before)
        if bounds:
            insert_at = bounds[0]
    prefix = "" if text[:insert_at].endswith("\n\n") or insert_at == 0 else "\n"
    section = f"{prefix}## {heading}\n\n"
    suffix = "" if section.endswith("\n\n") or text[insert_at:].startswith("\n") else "\n"
    return text[:insert_at] + section + suffix + text[insert_at:]


def _append_to_section(text: str, heading: str, block: str, *, before: str | None = None) -> str:
    text = _insert_section(text, heading, before=before)
    bounds = _section_bounds(text, heading)
    if not bounds:
        raise ValueError(f"could not create ## {heading}")
    start, end = bounds
    section = text[start:end].rstrip()
    separator = "\n\n" if section else ""
    updated = f"{section}{separator}{block.rstrip()}\n\n"
    return text[:start] + updated + text[end:].lstrip("\n")


def _drift_id(text: str, today: str) -> str:
    stem = f"D-{today.replace('-', '')}"
    count = len(re.findall(rf"\b{re.escape(stem)}-\d+\b", text))
    return f"{stem}-{count + 1:02d}"


def _entry_block(entry: DriftEntry, drift_id: str, subplans: list[Path]) -> str:
    subplan_text = ", ".join(f"`{path.as_posix()}`" for path in subplans) or "none"
    return "\n".join(
        [
            f"- [{entry.today}] {drift_id} — {entry.task}",
            f"  - Planned: {entry.planned}",
            f"  - Actual: {entry.actual}",
            f"  - Why: {entry.why}",
            f"  - Plan update: {entry.plan_update}",
            f"  - Next: {entry.next_step}",
            f"  - Subplans: {subplan_text}",
        ]
    )


def _progress_block(entry: DriftEntry, drift_id: str) -> str:
    return (
        f"- [{entry.today}] Drift {drift_id}: {entry.actual} "
        f"Reason: {entry.why}. Next: {entry.next_step}."
    )


def _normalize_task(task: str, drift_id: str) -> str:
    task = task.strip()
    if task.startswith("- ["):
        return task
    if "[Source:" not in task and "[Evidence:" not in task:
        task = f"{task} [Source: Drift {drift_id}]"
    return f"- [pending] {task}"


def _append_tasks(text: str, tasks: list[str], drift_id: str) -> str:
    if not tasks:
        return text
    bounds = _section_bounds(text, "Tasks")
    if not bounds:
        raise ValueError("PLAN.md missing ## Tasks")
    start, end = bounds
    section = text[start:end].rstrip()
    additions = "\n".join(_normalize_task(task, drift_id) for task in tasks)
    updated = f"{section}\n{additions}\n\n"
    return text[:start] + updated + text[end:].lstrip("\n")


def _block_task(text: str, needle: str, drift_id: str) -> tuple[str, bool]:
    if not needle:
        return text, False
    changed = False
    out: list[str] = []
    for line in text.splitlines():
        match = TASK_RE.match(line)
        if not changed and match and needle in line:
            prefix, _status, rest = match.groups()
            line = f"{prefix}[blocked]{rest} [Drift: {drift_id}]"
            changed = True
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), changed


def record_drift(
    plan_path: Path,
    entry: DriftEntry,
    *,
    add_tasks: list[str] | None = None,
    block_task: str | None = None,
    subplans: list[Path] | None = None,
) -> str:
    """Update plan_path and optional subplans, returning the drift id."""
    plan_path = plan_path.resolve()
    text = plan_path.read_text(encoding="utf-8")
    today = entry.today or date.today().isoformat()
    drift_id = entry.drift_id or _drift_id(text, today)
    entry = DriftEntry(
        task=_clean(entry.task, field="task"),
        planned=_clean(entry.planned, field="planned"),
        actual=_clean(entry.actual, field="actual"),
        why=_clean(entry.why, field="why"),
        plan_update=_clean(entry.plan_update, field="plan_update"),
        next_step=_clean(entry.next_step, field="next"),
        drift_id=drift_id,
        today=today,
    )

    resolved_subplans = [
        path if path.is_absolute() else plan_path.parent / path
        for path in (subplans or [])
    ]
    missing_subplans = [path for path in resolved_subplans if not path.exists()]
    if missing_subplans:
        raise ValueError(f"subplan not found: {missing_subplans[0]}")
    display_subplans = [
        path.relative_to(plan_path.parent)
        if path.is_absolute() and path.is_relative_to(plan_path.parent)
        else path
        for path in resolved_subplans
    ]

    text = _append_to_section(
        text,
        "Drift Log",
        _entry_block(entry, drift_id, display_subplans),
        before="Progress",
    )
    if block_task:
        text, blocked = _block_task(text, block_task, drift_id)
        if not blocked:
            raise ValueError(f"could not find pending/in_progress task matching: {block_task}")
    text = _append_tasks(text, add_tasks or [], drift_id)
    text = _append_to_section(text, "Progress", _progress_block(entry, drift_id))
    plan_path.write_text(text, encoding="utf-8")

    for subplan in resolved_subplans:
        subtext = subplan.read_text(encoding="utf-8")
        mirror = (
            f"- [{today}] {drift_id} from `{plan_path.name}` — {entry.actual}. "
            f"Why: {entry.why}. Parent update: {entry.plan_update}. Next: {entry.next_step}."
        )
        subtext = _append_to_section(subtext, "Drift Log", mirror, before="Progress")
        subplan.write_text(subtext, encoding="utf-8")

    return drift_id


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a planned-vs-actual drift entry in PLAN.md and optional subplans."
    )
    parser.add_argument("plan", type=Path, help="Path to PLAN.md")
    parser.add_argument("--task", required=True, help="Task id or short task description")
    parser.add_argument("--planned", required=True, help="What the plan said would happen")
    parser.add_argument("--actual", required=True, help="What actually changed")
    parser.add_argument("--why", required=True, help="Why the deviation was necessary")
    parser.add_argument("--plan-update", required=True, help="How the plan now adapts")
    parser.add_argument("--next", dest="next_step", required=True, help="Next move after this drift")
    parser.add_argument("--today", help="Override date for deterministic tests, YYYY-MM-DD")
    parser.add_argument("--id", dest="drift_id", help="Override drift id")
    parser.add_argument(
        "--block-task",
        help="Mark the first matching pending/in_progress task blocked with [Drift: ID]",
    )
    parser.add_argument(
        "--add-task",
        action="append",
        default=[],
        help="Append a pending follow-up task under ## Tasks. Repeatable.",
    )
    parser.add_argument(
        "--subplan",
        action="append",
        type=Path,
        default=[],
        help="Subplan path to mirror the drift into. Repeatable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        drift_id = record_drift(
            args.plan,
            DriftEntry(
                task=args.task,
                planned=args.planned,
                actual=args.actual,
                why=args.why,
                plan_update=args.plan_update,
                next_step=args.next_step,
                drift_id=args.drift_id,
                today=args.today,
            ),
            add_tasks=args.add_task,
            block_task=args.block_task,
            subplans=args.subplan,
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"vidux-drift-log: {exc}\n")
        return 2
    print(f"recorded drift {drift_id} in {args.plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
