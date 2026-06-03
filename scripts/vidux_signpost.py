#!/usr/bin/env python3
"""Tiny JSONL signpost logger for Vidux feature attribution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = 1
ATTRIBUTION_ENV_KEYS = [
    "VIDUX_SIGNPOST_RUN_ID",
    "VIDUX_RUNTIME",
    "VIDUX_AGENT_ID",
    "VIDUX_AUTOMATION_ID",
    "VIDUX_AUTOMATION_NAME",
    "CODEX_SESSION_ID",
    "CODEX_THREAD_ID",
    "CLAUDE_SESSION_ID",
    "CLAUDE_AUTOMATION_ID",
    "CLAUDE_AUTOMATION_NAME",
    "CURSOR_SESSION_ID",
]


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
    configured = os.environ.get("VIDUX_RUNTIME")
    if configured:
        return configured.strip().lower()
    if os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_AUTOMATION_ID"):
        return "claude"
    if os.environ.get("CURSOR_SESSION_ID"):
        return "cursor"
    if os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    return "unknown"


@contextmanager
def _temporary_env(overrides: dict[str, str | None]):
    saved = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _attribution(*, runtime: str | None = None) -> dict[str, Any]:
    return {
        "runtime": runtime or _runtime(),
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
    run_id: str | None = None,
    runtime: str | None = None,
) -> dict[str, Any]:
    """Append a feature signpost event to JSONL and return the payload."""
    path = Path(log_path).expanduser() if log_path is not None else default_log_path()
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"sp_{uuid4().hex}",
        "run_id": _clean(run_id, field="run_id") if run_id is not None else _run_id(),
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
        "attribution": _attribution(runtime=_clean(runtime, field="runtime") if runtime is not None else None),
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


def trace_events(
    log_path: Path | str | None = None,
    *,
    run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return ordered events for call-stack proof across hooks/subagents."""
    if limit is not None and limit < 0:
        raise ValueError("--limit must be >= 0")
    path = Path(log_path).expanduser() if log_path is not None else default_log_path()
    events = _iter_events(path)
    if run_id:
        events = [event for event in events if str(event.get("run_id", "")) == run_id]
    events.sort(key=lambda event: (str(event.get("ts", "")), str(event.get("event_id", ""))))
    if limit is not None:
        events = events[-limit:] if limit else []

    normalized: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        attribution = event.get("attribution") if isinstance(event.get("attribution"), dict) else {}
        normalized.append(
            {
                "sequence": index,
                "ts": event.get("ts"),
                "run_id": event.get("run_id"),
                "feature": event.get("feature"),
                "action": event.get("action"),
                "status": event.get("status"),
                "called": event.get("called"),
                "emitter": event.get("emitter"),
                "duration_ms": event.get("duration_ms"),
                "exit_code": event.get("exit_code"),
                "runtime": attribution.get("runtime"),
                "agent_id": attribution.get("agent_id"),
                "thread_id": attribution.get("thread_id"),
                "automation_id": attribution.get("automation_id"),
                "metadata": event.get("metadata") if isinstance(event.get("metadata"), dict) else {},
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "log_path": str(path),
        "run_id": run_id,
        "total_events": len(normalized),
        "events": normalized,
    }


def emit_lifecycle_smoke(
    *,
    log_path: Path | str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Emit a standard parent/subagent lifecycle trace and return it."""
    selected_run_id = _clean(run_id, field="run_id") if run_id else f"lifecycle_{uuid4().hex}"
    started = datetime.now(timezone.utc)
    sequence = [
        ("hook", "beforeTask", "codex", "pre", "scripts/vidux-doctor.sh --json"),
        ("subagent", "spawn", "claude", "during", "spawned-worker"),
        ("task", "verify", "cursor", "during", "worker verify"),
        ("hook", "afterTask", "codex", "post", "vidux checkpoint"),
    ]
    for index, (feature, action, runtime, phase, called) in enumerate(sequence):
        emit_event(
            feature,
            action,
            status="ok",
            called=called,
            emitter="vidux signpost lifecycle-smoke",
            metadata={"phase": phase, "sequence": str(index + 1)},
            log_path=log_path,
            now=started + timedelta(milliseconds=index),
            run_id=selected_run_id,
            runtime=runtime,
        )
    return trace_events(log_path, run_id=selected_run_id)


def _smoke_env(selected_run_id: str, overrides: dict[str, str]) -> dict[str, str | None]:
    env: dict[str, str | None] = {key: None for key in ATTRIBUTION_ENV_KEYS}
    env["VIDUX_SIGNPOST_RUN_ID"] = selected_run_id
    env.update(overrides)
    return env


def emit_spawned_subagent_smoke(
    *,
    log_path: Path | str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Emit an env-inheritance smoke for Codex parent and Claude/Cursor workers."""
    selected_run_id = _clean(run_id, field="run_id") if run_id else f"spawned_{uuid4().hex}"
    started = datetime.now(timezone.utc)
    codex_thread = "smoke-codex-thread"
    sequence: list[dict[str, Any]] = [
        {
            "feature": "hook",
            "action": "beforeTask",
            "phase": "pre",
            "called": "scripts/vidux-doctor.sh --json",
            "env": _smoke_env(
                selected_run_id,
                {
                    "CODEX_SESSION_ID": "smoke-codex-parent",
                    "CODEX_THREAD_ID": codex_thread,
                },
            ),
            "metadata": {
                "parent_runtime": "codex",
                "worker_runtime": None,
                "inherited_codex_thread": False,
                "inherited_thread_id": None,
            },
        },
        {
            "feature": "subagent",
            "action": "spawn",
            "phase": "during",
            "called": "claude spawned-worker",
            "env": _smoke_env(
                selected_run_id,
                {
                    "VIDUX_RUNTIME": "claude",
                    "CODEX_THREAD_ID": codex_thread,
                    "CLAUDE_SESSION_ID": "smoke-claude-worker",
                },
            ),
            "metadata": {
                "parent_runtime": "codex",
                "worker_runtime": "claude",
                "inherited_codex_thread": True,
                "inherited_thread_id": codex_thread,
            },
        },
        {
            "feature": "task",
            "action": "verify",
            "phase": "during",
            "called": "cursor worker verify",
            "env": _smoke_env(
                selected_run_id,
                {
                    "VIDUX_RUNTIME": "cursor",
                    "CODEX_THREAD_ID": codex_thread,
                    "CURSOR_SESSION_ID": "smoke-cursor-worker",
                },
            ),
            "metadata": {
                "parent_runtime": "codex",
                "worker_runtime": "cursor",
                "inherited_codex_thread": True,
                "inherited_thread_id": codex_thread,
            },
        },
        {
            "feature": "hook",
            "action": "afterTask",
            "phase": "post",
            "called": "vidux checkpoint",
            "env": _smoke_env(
                selected_run_id,
                {
                    "CODEX_SESSION_ID": "smoke-codex-parent",
                    "CODEX_THREAD_ID": codex_thread,
                },
            ),
            "metadata": {
                "parent_runtime": "codex",
                "worker_runtime": None,
                "inherited_codex_thread": False,
                "inherited_thread_id": None,
            },
        },
    ]
    for index, event in enumerate(sequence):
        metadata = {
            "phase": event["phase"],
            "sequence": str(index + 1),
            "smoke": "spawned-subagent-env",
            **event["metadata"],
        }
        with _temporary_env(event["env"]):
            emit_event(
                event["feature"],
                event["action"],
                status="ok",
                called=event["called"],
                emitter="vidux signpost spawned-subagent-smoke",
                metadata=metadata,
                log_path=log_path,
                now=started + timedelta(milliseconds=index),
            )
    return trace_events(log_path, run_id=selected_run_id)


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


def _print_trace(trace: dict[str, Any]) -> None:
    filter_text = f", run_id={trace['run_id']}" if trace.get("run_id") else ""
    print(f"trace events: {trace['total_events']} ({trace['log_path']}{filter_text})")
    for event in trace["events"]:
        feature = event.get("feature") or "unknown"
        action = event.get("action") or "unknown"
        runtime = event.get("runtime") or "unknown"
        called = event.get("called") or "n/a"
        print(
            f"- #{event['sequence']} {event.get('ts')} "
            f"{event.get('run_id')} {feature}.{action} "
            f"status={event.get('status')} runtime={runtime} called={called}"
        )


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
    emit.add_argument("--run-id", help="Explicit run id. Defaults to VIDUX_SIGNPOST_RUN_ID or a generated id.")
    emit.add_argument("--runtime", help="Explicit runtime attribution, e.g. codex, claude, or cursor.")
    emit.add_argument("--meta", action="append", default=[], help="Metadata key=value. Repeatable.")
    emit.add_argument("--log", type=Path, default=None)

    summary = subparsers.add_parser("summary", help="Summarize signpost counts.")
    summary.add_argument("--log", type=Path, default=None)
    summary.add_argument("--json", action="store_true")

    trace = subparsers.add_parser("trace", help="Print ordered signposts for a run.")
    trace.add_argument("--log", type=Path, default=None)
    trace.add_argument("--run-id", help="Filter to one run id.")
    trace.add_argument("--limit", type=int, help="Show only the latest N events after filtering.")
    trace.add_argument("--json", action="store_true")

    wrap = subparsers.add_parser("wrap", help="Run a child command and signpost its result.")
    wrap.add_argument("--feature", required=True)
    wrap.add_argument("--action", required=True)
    wrap.add_argument("--log", type=Path, default=None)
    wrap.add_argument("--run-id", help="Explicit run id. Defaults to VIDUX_SIGNPOST_RUN_ID or a generated id.")
    wrap.add_argument("--runtime", help="Explicit runtime attribution, e.g. codex, claude, or cursor.")
    wrap.add_argument("child", nargs=argparse.REMAINDER)

    lifecycle = subparsers.add_parser("lifecycle-smoke", help="Emit a standard hook/subagent lifecycle trace.")
    lifecycle.add_argument("--log", type=Path, default=None)
    lifecycle.add_argument("--run-id", help="Explicit run id for the whole lifecycle smoke.")
    lifecycle.add_argument("--json", action="store_true")

    spawned = subparsers.add_parser(
        "spawned-subagent-smoke",
        help="Emit a local env-inheritance smoke for Codex parent and spawned Claude/Cursor workers.",
    )
    spawned.add_argument("--log", type=Path, default=None)
    spawned.add_argument("--run-id", help="Explicit run id for the whole spawned-subagent smoke.")
    spawned.add_argument("--json", action="store_true")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
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
                run_id=args.run_id,
                runtime=args.runtime,
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
        if args.command == "trace":
            trace = trace_events(args.log, run_id=args.run_id, limit=args.limit)
            if args.json:
                print(json.dumps(trace, sort_keys=True))
            else:
                _print_trace(trace)
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
                run_id=args.run_id,
                runtime=args.runtime,
            )
            return result.returncode
        if args.command == "lifecycle-smoke":
            trace = emit_lifecycle_smoke(log_path=args.log, run_id=args.run_id)
            if args.json:
                print(json.dumps(trace, sort_keys=True))
            else:
                _print_trace(trace)
            return 0
        if args.command == "spawned-subagent-smoke":
            trace = emit_spawned_subagent_smoke(log_path=args.log, run_id=args.run_id)
            if args.json:
                print(json.dumps(trace, sort_keys=True))
            else:
                _print_trace(trace)
            return 0
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"vidux-signpost: {exc}\n")
        return 2
    sys.stderr.write(f"vidux-signpost: unknown command {args.command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
