#!/usr/bin/env python3
"""Record planned-vs-actual drift in a Vidux PLAN.md.

The helper makes the UNIFY step mechanical: write a structured Drift Log entry,
optionally block the stale task, append follow-up tasks, and mirror a compact
note into subplans that need to adapt with the parent plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter


try:
    from vidux_signpost import emit_event
except ImportError:  # pragma: no cover - defensive for direct import from tests
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from vidux_signpost import emit_event


H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TASK_RE = re.compile(r"^(\s*-\s*)\[(pending|in_progress| )\](.*)$")
CACHE_SCHEMA_VERSION = 1
CAUSES = {
    "missing_evidence",
    "wrong_surface",
    "scope_change",
    "dependency_shift",
    "implementation_constraint",
    "external_feedback",
    "verification_failure",
    "stale_plan",
    "parallel_session_collision",
    "other",
}
IMPACTS = {"minor", "material", "blocking"}


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
    cause: str = "other"
    impact: str = "material"


def _clean(value: str, *, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def _clean_choice(value: str, *, field: str, choices: set[str]) -> str:
    cleaned = _clean(value, field=field)
    if cleaned not in choices:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(choices))}")
    return cleaned


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_cache_path() -> Path:
    configured = os.environ.get("VIDUX_DRIFT_CACHE")
    if configured:
        return Path(configured).expanduser()
    home = Path(os.environ.get("VIDUX_HOME", "~/.vidux")).expanduser()
    return home / "drift-cache.jsonl"


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


def _entry_block(
    entry: DriftEntry,
    drift_id: str,
    subplans: list[Path],
    prevention_hints: list[str],
) -> str:
    subplan_text = ", ".join(f"`{path.as_posix()}`" for path in subplans) or "none"
    lines = [
        f"- [{entry.today}] {drift_id} — {entry.task}",
        f"  - Planned: {entry.planned}",
        f"  - Actual: {entry.actual}",
        f"  - Why: {entry.why}",
        f"  - Cause: {entry.cause}",
        f"  - Impact: {entry.impact}",
        f"  - Plan update: {entry.plan_update}",
        f"  - Next: {entry.next_step}",
    ]
    for hint in prevention_hints:
        lines.append(f"  - Prevention: {hint}")
    lines.append(f"  - Subplans: {subplan_text}")
    return "\n".join(lines)


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


def _relative_display(path: Path, *, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _cache_event_key(plan_path: Path, drift_id: str) -> str:
    material = f"{plan_path.resolve()}::{drift_id}".encode("utf-8")
    return f"sha256:{hashlib.sha256(material).hexdigest()}"


def _write_cache_record(
    cache_path: Path,
    *,
    plan_path: Path,
    entry: DriftEntry,
    drift_id: str,
    display_subplans: list[Path],
    prevention_hints: list[str],
    add_tasks: list[str],
    block_task: str | None,
    evidence_refs: list[str],
    tags: list[str],
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "event_key": _cache_event_key(plan_path, drift_id),
        "drift_id": drift_id,
        "recorded_at": _utc_now(),
        "date": entry.today,
        "plan_path": str(plan_path.resolve()),
        "plan_ref": _relative_display(plan_path, root=plan_path.parent),
        "task": entry.task,
        "planned": entry.planned,
        "actual": entry.actual,
        "why": entry.why,
        "cause": entry.cause,
        "impact": entry.impact,
        "plan_update": entry.plan_update,
        "next": entry.next_step,
        "prevention_hints": prevention_hints,
        "evidence_refs": evidence_refs,
        "tags": tags,
        "subplans": [path.as_posix() for path in display_subplans],
        "added_tasks": add_tasks,
        "blocked_task": block_task,
        "source": "vidux-drift-log.py",
    }
    cache_path = cache_path.expanduser()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_drift_cache(cache_path: Path | str | None = None) -> list[dict[str, object]]:
    path = Path(cache_path).expanduser() if cache_path is not None else _default_cache_path()
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 4
    }


def suggest_preventions(
    plan_text: str,
    *,
    cache_path: Path | str | None = None,
    limit: int = 3,
) -> list[dict[str, object]]:
    plan_tokens = _tokens(plan_text)
    suggestions: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in read_drift_cache(cache_path):
        hints = record.get("prevention_hints")
        if not isinstance(hints, list):
            continue
        source_text = " ".join(
            str(record.get(key, ""))
            for key in ("task", "planned", "actual", "why", "plan_update", "tags")
        )
        score = len(plan_tokens & _tokens(source_text))
        for hint in hints:
            if not isinstance(hint, str) or not hint.strip():
                continue
            key = hint.strip()
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(
                {
                    "prevention": key,
                    "source_drift_id": record.get("drift_id"),
                    "event_key": record.get("event_key"),
                    "score": score,
                    "cause": record.get("cause"),
                    "why": record.get("why"),
                }
            )
    suggestions.sort(key=lambda item: (int(item["score"]), str(item["source_drift_id"])), reverse=True)
    return suggestions[:limit]


def record_drift(
    plan_path: Path,
    entry: DriftEntry,
    *,
    add_tasks: list[str] | None = None,
    block_task: str | None = None,
    subplans: list[Path] | None = None,
    cache_path: Path | None = None,
    telemetry_path: Path | None = None,
    prevention_hints: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Update plan_path and optional subplans, returning the drift id."""
    started = perf_counter()
    plan_path = plan_path.resolve()
    text = plan_path.read_text(encoding="utf-8")
    today = entry.today or date.today().isoformat()
    drift_id = entry.drift_id or _drift_id(text, today)
    prevention_hints = [_clean(value, field="prevention") for value in (prevention_hints or [])]
    evidence_refs = [_clean(value, field="evidence_ref") for value in (evidence_refs or [])]
    tags = [_clean(value, field="tag") for value in (tags or [])]
    entry = DriftEntry(
        task=_clean(entry.task, field="task"),
        planned=_clean(entry.planned, field="planned"),
        actual=_clean(entry.actual, field="actual"),
        why=_clean(entry.why, field="why"),
        plan_update=_clean(entry.plan_update, field="plan_update"),
        next_step=_clean(entry.next_step, field="next"),
        drift_id=drift_id,
        today=today,
        cause=_clean_choice(entry.cause, field="cause", choices=CAUSES),
        impact=_clean_choice(entry.impact, field="impact", choices=IMPACTS),
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
        _entry_block(entry, drift_id, display_subplans, prevention_hints),
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

    if cache_path:
        _write_cache_record(
            cache_path,
            plan_path=plan_path,
            entry=entry,
            drift_id=drift_id,
            display_subplans=display_subplans,
            prevention_hints=prevention_hints,
            add_tasks=add_tasks or [],
            block_task=block_task,
            evidence_refs=evidence_refs,
            tags=tags,
        )
    if telemetry_path:
        emit_event(
            "drift",
            "record",
            status="ok",
            duration_ms=round((perf_counter() - started) * 1000, 3),
            metadata={
                "drift_id": drift_id,
                "plan_path": str(plan_path),
                "task": entry.task,
                "cache_written": bool(cache_path),
                "subplan_count": len(resolved_subplans),
            },
            log_path=telemetry_path,
        )

    return drift_id


def parse_args(argv: list[str]) -> argparse.Namespace:
    if argv and argv[0] == "suggest":
        parser = argparse.ArgumentParser(
            description="Suggest prevention hints from the drift cache for a PLAN.md."
        )
        parser.set_defaults(command="suggest")
        parser.add_argument("suggest", nargs="?")
        parser.add_argument("plan", type=Path, help="Path to PLAN.md")
        parser.add_argument("--cache", type=Path, default=None)
        parser.add_argument("--limit", type=int, default=3)
        parser.add_argument("--json", action="store_true")
        return parser.parse_args(argv)

    parser = argparse.ArgumentParser(
        description="Record a planned-vs-actual drift entry in PLAN.md and optional subplans."
    )
    parser.set_defaults(command="record")
    parser.add_argument("plan", type=Path, help="Path to PLAN.md")
    parser.add_argument("--task", required=True, help="Task id or short task description")
    parser.add_argument("--planned", required=True, help="What the plan said would happen")
    parser.add_argument("--actual", required=True, help="What actually changed")
    parser.add_argument("--why", required=True, help="Why the deviation was necessary")
    parser.add_argument("--plan-update", required=True, help="How the plan now adapts")
    parser.add_argument("--next", dest="next_step", required=True, help="Next move after this drift")
    parser.add_argument("--cause", choices=sorted(CAUSES), default="other")
    parser.add_argument("--impact", choices=sorted(IMPACTS), default="material")
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
    parser.add_argument("--prevention", action="append", default=[], help="Future plan hint. Repeatable.")
    parser.add_argument("--evidence-ref", action="append", default=[], help="Evidence reference. Repeatable.")
    parser.add_argument("--tag", action="append", default=[], help="Cache tag. Repeatable.")
    parser.add_argument("--cache", type=Path, default=None, help="Drift cache JSONL path.")
    parser.add_argument("--no-cache", action="store_true", help="Do not write a drift cache entry.")
    parser.add_argument("--telemetry", type=Path, default=None, help="Signpost JSONL path.")
    parser.add_argument("--no-telemetry", action="store_true", help="Do not write signpost telemetry.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "suggest":
            suggestions = suggest_preventions(
                args.plan.read_text(encoding="utf-8"),
                cache_path=args.cache,
                limit=args.limit,
            )
            if args.json:
                print(json.dumps({"suggestions": suggestions}, sort_keys=True))
            else:
                if not suggestions:
                    print("no drift-cache suggestions")
                for item in suggestions:
                    print(
                        f"- {item['prevention']} "
                        f"[source: {item['source_drift_id']}, score: {item['score']}]"
                    )
            return 0
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
                cause=args.cause,
                impact=args.impact,
            ),
            add_tasks=args.add_task,
            block_task=args.block_task,
            subplans=args.subplan,
            cache_path=None if args.no_cache else (args.cache or _default_cache_path()),
            telemetry_path=None if args.no_telemetry else (args.telemetry),
            prevention_hints=args.prevention,
            evidence_refs=args.evidence_ref,
            tags=args.tag,
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"vidux-drift-log: {exc}\n")
        return 2
    print(f"recorded drift {drift_id} in {args.plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
