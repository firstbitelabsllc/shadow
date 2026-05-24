#!/usr/bin/env python3
"""Tiny JSONL signpost logger for Vidux feature attribution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = 1


def default_log_path() -> Path:
    configured = os.environ.get("VIDUX_TELEMETRY_LOG")
    if configured:
        return Path(configured).expanduser()
    home = Path(os.environ.get("VIDUX_HOME", "~/.vidux")).expanduser()
    return home / "signposts.jsonl"


def _clean(value: str, *, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def _timestamp(now: str | datetime | None = None) -> str:
    if now is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(now, datetime):
        current = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return current.isoformat().replace("+00:00", "Z")
    return now


def _run_id() -> str:
    configured = os.environ.get("VIDUX_SIGNPOST_RUN_ID")
    if configured:
        return configured
    return f"run_{uuid4().hex}"


def _runtime() -> str:
    if os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    if os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_AUTOMATION_ID"):
        return "claude"
    if os.environ.get("CURSOR_SESSION_ID"):
        return "cursor"
    return "unknown"


def _attribution() -> dict[str, Any]:
    return {
        "runtime": _runtime(),
        "agent_id": os.environ.get("VIDUX_AGENT_ID")
        or os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("CURSOR_SESSION_ID"),
        "thread_id": os.environ.get("CODEX_THREAD_ID"),
        "automation_id": os.environ.get("VIDUX_AUTOMATION_ID")
        or os.environ.get("CLAUDE_AUTOMATION_ID"),
        "automation_name": os.environ.get("VIDUX_AUTOMATION_NAME")
        or os.environ.get("CLAUDE_AUTOMATION_NAME"),
        "pid": os.getpid(),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * percentile
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return round(ordered[low] + (ordered[high] - ordered[low]) * fraction, 3)


def emit_event(
    feature: str,
    action: str,
    *,
    status: str = "ok",
    duration_ms: int | float | None = None,
    exit_code: int | None = 0,
    called: str | None = None,
    emitter: str | None = None,
    files: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    log_path: Path | str | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    """Append a feature signpost event to JSONL and return the payload."""
    path = Path(log_path).expanduser() if log_path is not None else default_log_path()
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"sp_{uuid4().hex}",
        "run_id": _run_id(),
        "ts": _timestamp(now),
        "feature": _clean(feature, field="feature"),
        "action": _clean(action, field="action"),
        "called": called,
        "emitter": emitter,
        "status": _clean(status, field="status"),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "repo": Path.cwd().name,
        "files": files or [],
        "attribution": _attribution(),
        "metadata": metadata or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def _iter_events(log_path: Path | str) -> list[dict[str, Any]]:
    path = Path(log_path).expanduser()
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def summarize_events(log_path: Path | str | None = None) -> dict[str, Any]:
    """Return count/status/duration aggregates keyed by feature.action."""
    path = Path(log_path).expanduser() if log_path is not None else default_log_path()
    events = _iter_events(path)
    grouped: dict[str, dict[str, Any]] = {}
    durations: dict[str, list[float]] = defaultdict(list)

    for event in events:
        key = f"{event.get('feature', 'unknown')}.{event.get('action', 'unknown')}"
        item = grouped.setdefault(
            key,
            {
                "count": 0,
                "statuses": {},
                "total_duration_ms": 0.0,
                "avg_duration_ms": None,
                "min_duration_ms": None,
                "p50_duration_ms": None,
                "p95_duration_ms": None,
                "max_duration_ms": None,
                "last_ts": None,
            },
        )
        item["count"] += 1
        item["last_ts"] = max(str(event.get("ts", "")), str(item["last_ts"] or ""))
        status = str(event.get("status", "unknown"))
        item["statuses"][status] = item["statuses"].get(status, 0) + 1
        duration = event.get("duration_ms")
        if isinstance(duration, int | float):
            item["total_duration_ms"] += float(duration)
            durations[key].append(float(duration))

    for key, values in durations.items():
        grouped[key]["avg_duration_ms"] = round(sum(values) / len(values), 3)
        grouped[key]["total_duration_ms"] = round(grouped[key]["total_duration_ms"], 3)
        grouped[key]["min_duration_ms"] = round(min(values), 3)
        grouped[key]["p50_duration_ms"] = _percentile(values, 0.5)
        grouped[key]["p95_duration_ms"] = _percentile(values, 0.95)
        grouped[key]["max_duration_ms"] = round(max(values), 3)

    return {
        "schema_version": SCHEMA_VERSION,
        "log_path": str(path),
        "total_events": len(events),
        "features": grouped,
    }


def _parse_meta(values: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--meta must be key=value: {value}")
        key, item = value.split("=", 1)
        metadata[_clean(key, field="meta key")] = item
    return metadata


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"events: {summary['total_events']} ({summary['log_path']})")
    for key in sorted(summary["features"]):
        item = summary["features"][key]
        avg = item["avg_duration_ms"]
        avg_text = "n/a" if avg is None else f"{avg}ms"
        print(f"- {key}: count={item['count']} avg={avg_text} statuses={item['statuses']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit or summarize Vidux JSONL signposts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    emit = subparsers.add_parser("emit", help="Append one signpost event.")
    emit.add_argument("--feature", required=True)
    emit.add_argument("--action", required=True)
    emit.add_argument("--status", default="ok")
    emit.add_argument("--duration-ms", type=float)
    emit.add_argument("--exit-code", type=int, default=0)
    emit.add_argument("--called")
    emit.add_argument("--emitter")
    emit.add_argument("--meta", action="append", default=[], help="Metadata key=value. Repeatable.")
    emit.add_argument("--log", type=Path, default=None)

    summary = subparsers.add_parser("summary", help="Summarize signpost counts.")
    summary.add_argument("--log", type=Path, default=None)
    summary.add_argument("--json", action="store_true")

    wrap = subparsers.add_parser("wrap", help="Run a child command and signpost its result.")
    wrap.add_argument("--feature", required=True)
    wrap.add_argument("--action", required=True)
    wrap.add_argument("--log", type=Path, default=None)
    wrap.add_argument("child", nargs=argparse.REMAINDER)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "emit":
            emit_event(
                args.feature,
                args.action,
                status=args.status,
                duration_ms=args.duration_ms,
                exit_code=args.exit_code,
                called=args.called,
                emitter=args.emitter,
                metadata=_parse_meta(args.meta),
                log_path=args.log,
            )
            print(f"signposted {args.feature}.{args.action} {args.status}")
            return 0
        if args.command == "summary":
            summary = summarize_events(args.log)
            if args.json:
                print(json.dumps(summary, sort_keys=True))
            else:
                _print_summary(summary)
            return 0
        if args.command == "wrap":
            child = args.child[1:] if args.child and args.child[0] == "--" else args.child
            if not child:
                raise ValueError("wrap requires a child command after --")
            started = perf_counter()
            result = subprocess.run(child, check=False)
            emit_event(
                args.feature,
                args.action,
                status="ok" if result.returncode == 0 else "error",
                duration_ms=round((perf_counter() - started) * 1000, 3),
                exit_code=result.returncode,
                called=" ".join(child),
                emitter="vidux signpost wrap",
                log_path=args.log,
            )
            return result.returncode
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"vidux-signpost: {exc}\n")
        return 2
    sys.stderr.write(f"vidux-signpost: unknown command {args.command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
