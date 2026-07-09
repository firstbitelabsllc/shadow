#!/usr/bin/env python3
"""
vidux browser — local web UI for viewing PLAN.md across the fleet.

Read-mostly viewer. Local-only write endpoints append artifacts/INBOX notes.
Stdlib only. See projects/vidux-browser/PLAN.md.
"""

from __future__ import annotations

import json
import os
import copy
import ipaddress
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from glob import glob
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Receipt corpus lab handlers (math-fortress T9). Sibling package — server.py
# is callable both as __main__ (sys.path[0] = browser/) and via importlib spec
# from tests (sys.path[0] = caller CWD). Insert browser/ explicitly so the
# import resolves regardless of caller.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import handler as _receipts_handler

DEV_ROOT = Path(os.environ.get("VIDUX_DEV_ROOT", Path.home() / "Development")).expanduser().resolve()
HOST = os.environ.get("VIDUX_BROWSER_HOST", "127.0.0.1")
PORT = int(os.environ.get("VIDUX_BROWSER_PORT", "7191"))

BROWSER_DIR = Path(__file__).resolve().parent
VIDUX_ROOT = Path(os.environ.get("VIDUX_ROOT", BROWSER_DIR.parent)).expanduser().resolve()
SERVER_FILE = Path(__file__).resolve()
SERVER_MTIME_NS = SERVER_FILE.stat().st_mtime_ns
STATIC_DIR = BROWSER_DIR / "static"
ARTIFACTS_DIR = BROWSER_DIR / "artifacts"
CLAUDE_PROJECTS_DIR = Path(
    os.environ.get("VIDUX_CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects")
).expanduser()
SESSION_TURN_LIMIT = 5
SESSION_EXCERPT_LIMIT = 360
SESSION_TAIL_BYTES = 2 * 1024 * 1024
try:
    DASHBOARD_ITEM_LIMIT = max(1, int(os.environ.get("VIDUX_DASHBOARD_ITEM_LIMIT", "200")))
except ValueError:
    DASHBOARD_ITEM_LIMIT = 200
LEDGER_FILE = Path(os.environ.get("VIDUX_LEDGER_FILE", Path.home() / ".agent-ledger" / "activity.jsonl")).expanduser()
try:
    LEDGER_ITEM_LIMIT = max(1, int(os.environ.get("VIDUX_LEDGER_ITEM_LIMIT", "20")))
except ValueError:
    LEDGER_ITEM_LIMIT = 20
try:
    LEDGER_SCAN_LIMIT = max(1, int(os.environ.get("VIDUX_LEDGER_SCAN_LIMIT", "5000")))
except ValueError:
    LEDGER_SCAN_LIMIT = 5000

# Plan-layout conventions. The two-segment vidux/projects/ai patterns catch
# parent plans (e.g., `vidux/design-overhaul/PLAN.md`); the `**` recursive forms
# pick up sub-plans nested under those parents (e.g.,
# `vidux/design-overhaul/<child>/PLAN.md`). Recursive globs land MORE files but
# `discover_plans()` dedupes by resolved path so we never count twice. Override
# via env `VIDUX_PLAN_GLOBS` (colon-separated) for non-standard fleets.
PLAN_GLOBS = (
    os.environ.get("VIDUX_PLAN_GLOBS", "").split(":")
    if os.environ.get("VIDUX_PLAN_GLOBS")
    else [
        "*/ai/plans/*/PLAN.md",
        "*/vidux/*/PLAN.md",
        "*/vidux/**/PLAN.md",
        "*/projects/*/PLAN.md",
        "*/projects/**/PLAN.md",
        "*/PLAN.md",
    ]
)

# Aliases for historical checkout names that can still contain copied vidux
# plans (e.g., a repo was renamed but old clones still exist). When the same
# plan resolves under both names, prefer the canonical checkout. Override via
# env `VIDUX_REPO_ALIASES` as JSON (e.g. '{"oldname": "newname"}').
def _parse_repo_aliases():
    raw = os.environ.get("VIDUX_REPO_ALIASES", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}
LEGACY_REPO_ALIASES = _parse_repo_aliases()

PLANS_CACHE_TTL_SECONDS = float(os.environ.get("VIDUX_PLANS_CACHE_TTL_SECONDS", "20"))
_PLANS_CACHE_LOCK = threading.Lock()
_PLANS_CACHE: dict[str, object] = {
    "key": None,
    "expires_at": 0.0,
    "plans": None,
}


def clear_plans_cache() -> None:
    with _PLANS_CACHE_LOCK:
        _PLANS_CACHE["key"] = None
        _PLANS_CACHE["expires_at"] = 0.0
        _PLANS_CACHE["plans"] = None


def discover_plans_cached() -> list[dict]:
    """Cache the fleet index briefly so auto-refresh does not rescan every hit."""
    if PLANS_CACHE_TTL_SECONDS <= 0:
        return discover_plans()

    key = (str(DEV_ROOT), tuple(PLAN_GLOBS), tuple(sorted(LEGACY_REPO_ALIASES.items())))
    now = time.monotonic()
    with _PLANS_CACHE_LOCK:
        plans = _PLANS_CACHE["plans"]
        if plans is not None and _PLANS_CACHE["key"] == key and now < _PLANS_CACHE["expires_at"]:
            return plans  # type: ignore[return-value]

        plans = discover_plans()
        _PLANS_CACHE["key"] = key
        _PLANS_CACHE["expires_at"] = time.monotonic() + PLANS_CACHE_TTL_SECONDS
        _PLANS_CACHE["plans"] = plans
        return plans

# Files to expose alongside PLAN.md when present.
# Note: PLAN.md, INBOX.md, investigations/, evidence/ are core /vidux per the
# canonical doctrine (DOCTRINE.md + guides/fleet-ops.md + guides/investigation.md
# + guides/evidence-format.md). PROGRESS.md as a separate file and ASK-LEO.md
# are Leo-fleet extensions; the browser surfaces them when present but does not
# require them — a clean canonical-vidux repo without those files still works.
SIBLING_FILES = ["PROGRESS.md", "INBOX.md", "ASK-LEO.md", "DOCTRINE.md", "README.md"]

# safe_resolve() whitelist. Any other filename under DEV_ROOT is rejected —
# without this gate, a malicious page could fetch /api/file?path=…/.env or
# …/.ssh/config from a browser tab on Leo's machine.
ALLOWED_PLAN_FILES = frozenset({"PLAN.md", *SIBLING_FILES})

HOT_DAYS = 7
STALE_DAYS = 30

ARTIFACT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ARTIFACT_MAX_BYTES = 1024 * 1024  # 1 MB cap on POSTed HTML
ARTIFACT_TITLE_RE = re.compile(
    r"<title>([^<]+)</title>|<h1[^>]*>([^<]+)</h1>", re.I
)
PLAN_NOTE_MAX_BYTES = 16 * 1024
PLAN_NOTE_SOURCE_RE = re.compile(r"[^A-Za-z0-9_.:/@ -]+")
COMMENTS_FILE = Path(
    os.environ.get("VIDUX_BROWSER_COMMENTS_FILE", Path.home() / ".vidux-browser" / "comments.jsonl")
).expanduser()
COMMENT_BODY_MAX_BYTES = 8 * 1024
COMMENT_AUTHOR_MAX_CHARS = 80
COMMENT_AUTHOR_RE = re.compile(r"[^A-Za-z0-9_.:/@' -]+")
COMMENT_ANCHOR_FIELD_LIMITS = {
    "selector": 160,
    "label": 180,
    "excerpt": 360,
    "tag": 32,
    "kind": 32,
}
COMMENT_ANCHOR_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
JSON_CONTENT_TYPE = "application/json"
VIDUX_TRUTH_CACHE_TTL_SECONDS = float(os.environ.get("VIDUX_TRUTH_CACHE_TTL_SECONDS", "45"))
_VIDUX_TRUTH_CACHE_LOCK = threading.Lock()
_VIDUX_TRUTH_CACHE: dict[str, object] = {
    "expires_at": 0.0,
    "payload": None,
    "generated_monotonic": 0.0,
    "refreshing": False,
}


def clear_vidux_truth_cache() -> None:
    with _VIDUX_TRUTH_CACHE_LOCK:
        _VIDUX_TRUTH_CACHE["expires_at"] = 0.0
        _VIDUX_TRUTH_CACHE["payload"] = None
        _VIDUX_TRUTH_CACHE["generated_monotonic"] = 0.0
        _VIDUX_TRUTH_CACHE["refreshing"] = False


def run_truth_command(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(VIDUX_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _truth_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _truth_command_payload(args: list[str], *, timeout: float) -> dict:
    started = time.monotonic()
    try:
        result = run_truth_command(args, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            "command": args,
            "command_ok": False,
            "returncode": None,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": f"timed out after {exc.timeout}s",
            "data": {},
        }
    except OSError as exc:
        return {
            "command": args,
            "command_ok": False,
            "returncode": None,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": str(exc),
            "data": {},
        }

    raw = (result.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {}
        parsed = isinstance(data, dict)
    except json.JSONDecodeError as exc:
        data = {}
        parsed = False
        error = f"invalid json: {exc}"
    else:
        error = "" if parsed else "json root was not an object"

    return {
        "command": args,
        "command_ok": result.returncode == 0 and parsed,
        "returncode": result.returncode,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "error": error or (result.stderr or "").strip(),
        "data": data if parsed else {},
    }


def _compact_latest_signpost_run(trace_data: dict) -> dict:
    events = trace_data.get("events", [])
    if not isinstance(events, list) or not events:
        return {}

    latest_run_id = ""
    for event in reversed(events):
        if isinstance(event, dict) and event.get("run_id"):
            latest_run_id = str(event["run_id"])
            break
    if not latest_run_id:
        return {}

    run_events = [
        event
        for event in events
        if isinstance(event, dict) and str(event.get("run_id", "")) == latest_run_id
    ]
    actions = [str(event.get("action", "")) for event in run_events]
    runtimes = [str(event.get("runtime", "")) for event in run_events]
    phases = [
        str((event.get("metadata") or {}).get("phase", ""))
        if isinstance(event.get("metadata"), dict)
        else ""
        for event in run_events
    ]
    called = [str(event.get("called", "")) for event in run_events]
    complete_lifecycle = actions == ["beforeTask", "spawn", "verify", "afterTask"] and runtimes == [
        "codex",
        "claude",
        "cursor",
        "codex",
    ]

    return {
        "run_id": latest_run_id,
        "event_count": len(run_events),
        "actions": actions,
        "runtimes": runtimes,
        "phases": phases,
        "called": called,
        "call_stack": " > ".join(runtime for runtime in runtimes if runtime),
        "complete_lifecycle": complete_lifecycle,
    }


def _collect_vidux_truth_payload() -> dict:
    """Collect read-only local truth for the browser chrome.

    The browser intentionally does not run the install doctor (`vidux doctor`)
    because that path can execute `npm test`. Runtime state comes from the
    JSON runtime doctor without --fix, so refreshes stay read-only.
    """
    config_cmd = _truth_command_payload(
        [sys.executable, str(VIDUX_ROOT / "scripts" / "vidux-config.py"), "check", "--json"],
        timeout=5,
    )
    runtime_cmd = _truth_command_payload(
        ["bash", str(VIDUX_ROOT / "scripts" / "vidux-doctor.sh"), "--json"],
        timeout=20,
    )
    signpost_cmd = _truth_command_payload(
        [sys.executable, str(VIDUX_ROOT / "scripts" / "vidux_signpost.py"), "summary", "--json"],
        timeout=5,
    )
    signpost_trace_cmd = _truth_command_payload(
        [
            sys.executable,
            str(VIDUX_ROOT / "scripts" / "vidux_signpost.py"),
            "trace",
            "--limit",
            "12",
            "--json",
        ],
        timeout=5,
    )

    config_data = config_cmd["data"]
    runtime_data = runtime_cmd["data"]
    signpost_data = signpost_cmd["data"]
    signpost_trace_data = signpost_trace_cmd["data"]
    runtime_checks = runtime_data.get("checks", []) if isinstance(runtime_data.get("checks"), list) else []
    runtime_warnings = [
        str(check.get("id", "unknown"))
        for check in runtime_checks
        if isinstance(check, dict) and check.get("status") == "warn"
    ]
    runtime_blockers = [
        str(check.get("id", "unknown"))
        for check in runtime_checks
        if isinstance(check, dict) and check.get("status") == "block"
    ]
    runtime_status = "block" if runtime_blockers else ("warn" if runtime_warnings else "pass")
    runtime_system_memory = next(
        (
            check
            for check in runtime_checks
            if isinstance(check, dict) and check.get("id") == "system_memory_pressure"
        ),
        {},
    )
    system_memory_keys = (
        "status",
        "available",
        "memory_pressure_free_pct",
        "memory_free_pct",
        "min_memory_free_pct",
        "memory_pct_source",
        "vm_free_mb",
        "vm_speculative_mb",
        "free_mb",
        "speculative_mb",
        "vm_pages_source",
        "total_bytes",
    )
    system_memory = {
        key: runtime_system_memory[key]
        for key in system_memory_keys
        if isinstance(runtime_system_memory, dict) and key in runtime_system_memory
    }

    payload = {
        "ok": True,
        "generated_at": _truth_now(),
        "repo_root": str(VIDUX_ROOT),
        "read_only": True,
        "browser_runs_install_doctor": False,
        "browser_runs_runtime_fix": False,
        "config": {
            "ok": bool(config_cmd["command_ok"] and config_data.get("status") == "ok"),
            "command": "vidux config check --json",
            "returncode": config_cmd["returncode"],
            "duration_ms": config_cmd["duration_ms"],
            "status": config_data.get("status", "unknown"),
            "source": config_data.get("source", "unknown"),
            "path": config_data.get("path", ""),
            "live_config_present": bool(config_data.get("live_config_present")),
            "using_example": bool(config_data.get("using_example")),
            "issues": config_data.get("issues", []),
            "plan_store": config_data.get("plan_store", {}),
            "error": config_cmd["error"],
        },
        "install_doctor": {
            "command": "vidux doctor",
            "role": "install/readiness",
            "browser_status": "not_run",
            "pre_hook_safe": False,
            "may_run_npm_test": True,
        },
        "runtime_doctor": {
            "ok": bool(runtime_cmd["command_ok"]),
            "command": "scripts/vidux-doctor.sh --json",
            "role": "runtime",
            "returncode": runtime_cmd["returncode"],
            "duration_ms": runtime_cmd["duration_ms"],
            "status": runtime_status,
            "pass": runtime_data.get("pass", 0),
            "total": runtime_data.get("total", 0),
            "warnings": runtime_warnings,
            "blockers": runtime_blockers,
            "system_memory": system_memory,
            "pre_hook_safe": True,
            "fix_available_only_with_explicit_flag": True,
            "error": runtime_cmd["error"],
        },
        "signposts": {
            "ok": bool(signpost_cmd["command_ok"]),
            "command": "vidux signpost summary --json",
            "returncode": signpost_cmd["returncode"],
            "duration_ms": signpost_cmd["duration_ms"],
            "trace_ok": bool(signpost_trace_cmd["command_ok"]),
            "trace_command": "vidux signpost trace --limit 12 --json",
            "trace_returncode": signpost_trace_cmd["returncode"],
            "trace_duration_ms": signpost_trace_cmd["duration_ms"],
            "total_events": signpost_data.get("total_events", 0),
            "feature_count": len(signpost_data.get("features", {})) if isinstance(signpost_data.get("features"), dict) else 0,
            "latest_run": _compact_latest_signpost_run(signpost_trace_data),
            "log_path": signpost_data.get("log_path", ""),
            "error": signpost_cmd["error"] or signpost_trace_cmd["error"],
        },
    }

    return payload


def _cache_vidux_truth_payload(payload: dict) -> None:
    if VIDUX_TRUTH_CACHE_TTL_SECONDS <= 0:
        return
    with _VIDUX_TRUTH_CACHE_LOCK:
        _VIDUX_TRUTH_CACHE["payload"] = payload
        _VIDUX_TRUTH_CACHE["generated_monotonic"] = time.monotonic()
        _VIDUX_TRUTH_CACHE["expires_at"] = time.monotonic() + VIDUX_TRUTH_CACHE_TTL_SECONDS


def _truth_with_cache_status(payload: dict, *, status: str, refreshing: bool, age_seconds: float | None) -> dict:
    enriched = copy.deepcopy(payload)
    enriched["cache"] = {
        "status": status,
        "refreshing": refreshing,
        "age_seconds": None if age_seconds is None else round(max(age_seconds, 0.0), 2),
        "ttl_seconds": VIDUX_TRUTH_CACHE_TTL_SECONDS,
    }
    return enriched


def _warming_vidux_truth_payload(*, refreshing: bool) -> dict:
    return _truth_with_cache_status(
        {
            "ok": True,
            "generated_at": _truth_now(),
            "repo_root": str(VIDUX_ROOT),
            "read_only": True,
            "browser_runs_install_doctor": False,
            "browser_runs_runtime_fix": False,
            "config": {
                "ok": False,
                "command": "vidux config check --json",
                "returncode": None,
                "duration_ms": None,
                "status": "warming",
                "source": "pending",
                "path": "",
                "live_config_present": False,
                "using_example": False,
                "issues": [],
                "plan_store": {},
                "error": "",
            },
            "install_doctor": {
                "command": "vidux doctor",
                "role": "install/readiness",
                "browser_status": "not_run",
                "pre_hook_safe": False,
                "may_run_npm_test": True,
            },
            "runtime_doctor": {
                "ok": False,
                "command": "scripts/vidux-doctor.sh --json",
                "role": "runtime",
                "returncode": None,
                "duration_ms": None,
                "status": "warming",
                "pass": 0,
                "total": 0,
                "warnings": [],
                "blockers": [],
                "system_memory": {},
                "pre_hook_safe": True,
                "fix_available_only_with_explicit_flag": True,
                "error": "",
            },
            "signposts": {
                "ok": False,
                "command": "vidux signpost summary --json",
                "returncode": None,
                "duration_ms": None,
                "total_events": 0,
                "feature_count": 0,
                "latest_run": {},
                "log_path": "",
                "error": "",
            },
        },
        status="warming",
        refreshing=refreshing,
        age_seconds=None,
    )


def _refresh_vidux_truth_cache() -> None:
    try:
        payload = _collect_vidux_truth_payload()
        _cache_vidux_truth_payload(payload)
    finally:
        with _VIDUX_TRUTH_CACHE_LOCK:
            _VIDUX_TRUTH_CACHE["refreshing"] = False


def _start_vidux_truth_refresh() -> bool:
    with _VIDUX_TRUTH_CACHE_LOCK:
        if _VIDUX_TRUTH_CACHE.get("refreshing"):
            return False
        _VIDUX_TRUTH_CACHE["refreshing"] = True
    thread = threading.Thread(target=_refresh_vidux_truth_cache, daemon=True)
    thread.start()
    return True


def vidux_truth_payload(*, force_refresh: bool = False) -> dict:
    now = time.monotonic()
    if not force_refresh and VIDUX_TRUTH_CACHE_TTL_SECONDS > 0:
        with _VIDUX_TRUTH_CACHE_LOCK:
            cached = _VIDUX_TRUTH_CACHE.get("payload")
            expires_at = float(_VIDUX_TRUTH_CACHE.get("expires_at", 0.0))
            generated_at = float(_VIDUX_TRUTH_CACHE.get("generated_monotonic", 0.0))
            refreshing = bool(_VIDUX_TRUTH_CACHE.get("refreshing"))
        if cached is not None and now < expires_at:
            return _truth_with_cache_status(
                cached,  # type: ignore[arg-type]
                status="fresh",
                refreshing=refreshing,
                age_seconds=now - generated_at,
            )

    payload = _collect_vidux_truth_payload()
    _cache_vidux_truth_payload(payload)
    return _truth_with_cache_status(payload, status="fresh", refreshing=False, age_seconds=0.0)


def vidux_truth_cached_payload(*, background: bool = True) -> dict:
    """Return quickly for browser/monitor callers, refreshing expensive truth off-thread."""
    now = time.monotonic()
    with _VIDUX_TRUTH_CACHE_LOCK:
        cached = _VIDUX_TRUTH_CACHE.get("payload")
        expires_at = float(_VIDUX_TRUTH_CACHE.get("expires_at", 0.0))
        generated_at = float(_VIDUX_TRUTH_CACHE.get("generated_monotonic", 0.0))
        refreshing = bool(_VIDUX_TRUTH_CACHE.get("refreshing"))

    if cached is not None and now < expires_at:
        return _truth_with_cache_status(
            cached,  # type: ignore[arg-type]
            status="fresh",
            refreshing=refreshing,
            age_seconds=now - generated_at,
        )

    if background:
        started = _start_vidux_truth_refresh()
        refreshing = refreshing or started

    if cached is not None:
        return _truth_with_cache_status(
            cached,  # type: ignore[arg-type]
            status="stale",
            refreshing=refreshing,
            age_seconds=now - generated_at,
        )
    return _warming_vidux_truth_payload(refreshing=refreshing)

# /vidux task-FSM markers. Used by task_stats() to compute completion-bar.
# Per /vidux doctrine: completion (X/Y tasks) is the headline; ETA is parsed
# but does not drive the UI (tasks vary in difficulty, ETA is fiction).
TASKS_SECTION_RE = re.compile(r"^##\s+Tasks\s*\n(.*?)(?=^##\s|\Z)", re.M | re.S)
TASK_LINE_RE = re.compile(r"^-\s+\[(pending|in_progress|in_review|completed|blocked)\]", re.M)
ETA_RE = re.compile(r"\[ETA:\s*([\d.]+)h\]")
INVESTIGATION_RE = re.compile(r"\[Investigation:\s*([^\]]+?)\]")
PLAN_BRIEF_TASK_RE = re.compile(
    r"^-\s+\[(?P<status>pending|in_progress|in_review|completed|blocked)\]\s+(?P<body>.+?)\s*$",
    re.M,
)
PLAN_BRIEF_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<body>.+?)\s*$")
PLAN_BRIEF_TAG_RE = re.compile(r"\s*\[[A-Za-z][A-Za-z0-9 _/-]*:\s*[^\]]+\]")
PLAN_BRIEF_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
DASHBOARD_TASK_RE = re.compile(
    r"^-\s+\[(?P<status>pending|in_progress|in_review|completed|blocked)\]\s+(?P<body>.+?)\s*$"
)
DASHBOARD_OPEN_HEADING_RE = re.compile(r"^[ \t]{0,3}#{3,6}\s+(?P<body>.+?)\s*#*\s*$")
DASHBOARD_ASK_HEADING_RE = re.compile(r"^[ \t]{0,3}##\s+(?P<body>Q\d+\b.+?)\s*#*\s*$", re.I)
DASHBOARD_ASK_RESOLVED_RE = re.compile(r"\b(?:resolved:\s*\S+|status:\s*resolved)\b", re.I)
DASHBOARD_SOURCE_TAG_RE = re.compile(r"\[Source:\s*(?P<source>[^,\]]+)(?:,[^\]]+)?\]", re.I)
EVIDENCE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-_].*)?\.md$")
DECISION_LOG_HEADING_RE = re.compile(
    r"^(?P<indent>[ \t]{0,3})(?P<marks>#{2,6})\s+decision(?:\s+log|s)\s*#*\s*$",
    re.I,
)
MARKDOWN_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})\s+\S")
DECISION_ENTRY_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<body>.+?)\s*$")
DECISION_KIND_RE = re.compile(r"^\[(?P<kind>[A-Z][A-Z0-9_-]{1,31})\]\s*(?P<rest>.*)$")
DECISION_DATE_RE = re.compile(r"^\[?(?P<date>\d{4}-\d{2}-\d{2}(?:[^\]]{0,60})?)\]?\s*(?P<rest>.*)$")
DECISION_DIRECTION_KINDS = frozenset({
    "DIRECTION",
    "PIVOT",
    "REFRAME",
    "DELETION",
    "MERGE",
    "STUCK",
})
# Sub-plan backlink: child plans declare their parent on a line near the top
# matching either `> Parent: <relpath>` or `**Parent:** <relpath>`. The relpath
# is taken verbatim and normalized to a string later.
PARENT_REF_RE = re.compile(
    r"^(?:>\s*Parent:|\*\*Parent:\*\*)\s*([^\s][^\n]*?)\s*$",
    re.M,
)
TASK_STATUSES = ("pending", "in_progress", "in_review", "completed", "blocked")


def claude_project_slug(repo_path: Path) -> str:
    return str(repo_path.expanduser().resolve(strict=False)).replace("/", "-")


def compact_session_text(value: str, limit: int = SESSION_EXCERPT_LIMIT) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    clipped = text[: max(0, limit - 3)].rsplit(" ", 1)[0].strip()
    return f"{clipped or text[: max(0, limit - 3)].strip()}..."


def extract_session_text(content: object) -> str:
    chunks: list[str] = []
    if isinstance(content, str):
        chunks.append(content)
    elif isinstance(content, dict):
        value = content.get("text")
        if isinstance(value, str):
            chunks.append(value)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            block_type = str(item.get("type", ""))
            value = item.get("text")
            if isinstance(value, str) and block_type in ("", "text", "input_text", "output_text"):
                chunks.append(value)
    return compact_session_text(" ".join(chunks))


def read_tail_lines(path: Path, max_bytes: int = SESSION_TAIL_BYTES) -> tuple[list[str], bool]:
    try:
        size = path.stat().st_size
        start = max(size - max_bytes, 0)
        with path.open("rb") as f:
            f.seek(start)
            raw = f.read()
    except OSError:
        return [], False
    text = raw.decode("utf-8", errors="replace")
    truncated = start > 0
    if truncated and "\n" in text:
        text = text.split("\n", 1)[1]
    return [line for line in text.splitlines() if line.strip()], truncated


def parse_claude_session_file(path: Path, limit: int = SESSION_TURN_LIMIT) -> dict:
    lines, truncated = read_tail_lines(path)
    turns: list[dict] = []
    parsed_lines = 0
    invalid_lines = 0
    turns_seen = 0
    session_id = path.stem
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(item, dict):
            continue
        parsed_lines += 1
        if item.get("sessionId"):
            session_id = str(item["sessionId"])
        message = item.get("message") if isinstance(item.get("message"), dict) else {}
        role = str(message.get("role") or item.get("role") or item.get("type") or "")
        if role not in ("user", "assistant"):
            continue
        text = extract_session_text(message.get("content", item.get("content")))
        if not text:
            continue
        turns_seen += 1
        turns.append({
            "role": role,
            "text": text,
            "timestamp": str(item.get("timestamp") or ""),
        })
        turns = turns[-limit:]
    return {
        "session_id": session_id,
        "turns": turns,
        "turns_seen": turns_seen,
        "parsed_lines": parsed_lines,
        "invalid_lines": invalid_lines,
        "tail_truncated": truncated,
    }


def missing_session_payload(repo: str, status: str = "missing") -> dict:
    project_dir = CLAUDE_PROJECTS_DIR / claude_project_slug(DEV_ROOT / repo)
    return {
        "available": False,
        "status": status,
        "repo": repo,
        "project_dir": str(project_dir),
        "path": "",
        "file": "",
        "session_id": "",
        "mtime": None,
        "age_days": None,
        "turns": [],
        "turns_seen": 0,
        "parsed_lines": 0,
        "invalid_lines": 0,
        "tail_truncated": False,
        "source": "~/.claude/projects/latest-jsonl",
    }


def latest_claude_session_for_repo(repo: str) -> dict:
    project_dir = CLAUDE_PROJECTS_DIR / claude_project_slug(DEV_ROOT / repo)
    if not project_dir.is_dir():
        return missing_session_payload(repo)
    try:
        candidates = [p for p in project_dir.glob("*.jsonl") if p.is_file()]
    except OSError:
        return missing_session_payload(repo, "unreadable")
    if not candidates:
        return missing_session_payload(repo, "empty")
    try:
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        mtime = latest.stat().st_mtime
    except OSError:
        return missing_session_payload(repo, "unreadable")
    session = parse_claude_session_file(latest)
    session.update({
        "available": True,
        "status": "ok",
        "repo": repo,
        "project_dir": str(project_dir),
        "path": str(latest),
        "file": latest.name,
        "mtime": mtime,
        "age_days": round((time.time() - mtime) / 86400, 1),
        "source": "~/.claude/projects/latest-jsonl",
    })
    return session


def discover_repo_sessions(repos: set[str]) -> dict[str, dict]:
    return {repo: latest_claude_session_for_repo(repo) for repo in sorted(repos)}


def compact_ledger_text(value: object, limit: int = 360) -> str:
    text = re.sub(r"[\x00-\x1f]+", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def ledger_path_candidates(value: object, repo: str) -> set[Path]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    try:
        raw_path = Path(raw).expanduser()
    except (OSError, ValueError):
        return set()

    candidates: set[Path] = set()
    try:
        if raw_path.is_absolute():
            candidates.add(raw_path.resolve(strict=False))
        else:
            candidates.add((DEV_ROOT / raw_path).resolve(strict=False))
            if repo:
                candidates.add((DEV_ROOT / repo / raw_path).resolve(strict=False))
    except (OSError, ValueError):
        return set()
    return candidates


def plan_ledger_match_paths(plan_path: Path) -> tuple[str, set[Path]]:
    resolved = plan_path.resolve(strict=False)
    paths = {resolved}
    try:
        rel = resolved.relative_to(DEV_ROOT)
    except (OSError, ValueError):
        return "", paths
    repo = rel.parts[0] if rel.parts else ""
    try:
        paths.add((DEV_ROOT / rel).resolve(strict=False))
    except (OSError, ValueError):
        pass
    if repo:
        try:
            paths.add((DEV_ROOT / repo / resolved.relative_to(DEV_ROOT / repo)).resolve(strict=False))
        except (OSError, ValueError):
            pass
    return repo, paths


def row_has_publish_or_checkpoint_event(row: dict) -> bool:
    event = str(row.get("event", ""))
    publish_kind = str(row.get("publish_kind", ""))
    return event in {"publish", "vidux_checkpoint"} or publish_kind == "checkpoint"


def ledger_row_matches_plan(row: dict, plan_paths: set[Path], repo: str) -> bool:
    row_repo = str(row.get("repo", ""))
    if row_repo and repo and row_repo != repo:
        return False
    path_fields: list[object] = [row.get("plan_path")]
    for key in ("files", "files_claimed"):
        values = row.get(key)
        if isinstance(values, list):
            path_fields.extend(values)

    for value in path_fields:
        candidate_repos = [row_repo]
        if repo and repo not in candidate_repos:
            candidate_repos.append(repo)
        for candidate_repo in candidate_repos:
            if ledger_path_candidates(value, candidate_repo) & plan_paths:
                return True
    return False


def compact_ledger_row(row: dict, line_number: int, scope: str) -> dict:
    files = row.get("files") if isinstance(row.get("files"), list) else []
    files_claimed = row.get("files_claimed") if isinstance(row.get("files_claimed"), list) else []
    return {
        "scope": scope,
        "line": line_number,
        "ts": compact_ledger_text(row.get("ts"), 80),
        "eid": compact_ledger_text(row.get("eid"), 140),
        "event": compact_ledger_text(row.get("event"), 80),
        "repo": compact_ledger_text(row.get("repo"), 120),
        "lane": compact_ledger_text(row.get("lane"), 160),
        "task_id": compact_ledger_text(row.get("task_id"), 120),
        "summary": compact_ledger_text(row.get("summary"), 260),
        "plan_path": compact_ledger_text(row.get("plan_path"), 220),
        "proof": compact_ledger_text(row.get("proof"), 320),
        "handoff_status": compact_ledger_text(row.get("handoff_status"), 80),
        "next_agent_resume": compact_ledger_text(row.get("next_agent_resume"), 320),
        "files_count": len(files),
        "files_claimed_count": len(files_claimed),
    }


def ledger_payload_for_plan(
    plan_path: Path,
    *,
    item_limit: int | None = None,
    scan_limit: int | None = None,
    ledger_file: Path | None = None,
) -> dict:
    item_limit = item_limit or LEDGER_ITEM_LIMIT
    scan_limit = scan_limit or LEDGER_SCAN_LIMIT
    ledger_file = ledger_file or LEDGER_FILE
    repo, plan_paths = plan_ledger_match_paths(plan_path)
    payload = {
        "available": False,
        "status": "missing",
        "read_only": True,
        "source": str(ledger_file),
        "plan_path": str(plan_path),
        "repo": repo,
        "scan_limit": scan_limit,
        "item_limit": item_limit,
        "scanned_rows": 0,
        "invalid_rows": 0,
        "plan_total": 0,
        "repo_total": 0,
        "returned": 0,
        "truncated": False,
        "items": [],
    }
    if not ledger_file.is_file():
        return payload

    recent: deque[tuple[int, str]] = deque(maxlen=scan_limit)
    try:
        with ledger_file.open("r", encoding="utf-8", errors="replace") as fh:
            for line_number, line in enumerate(fh, start=1):
                recent.append((line_number, line))
    except OSError:
        payload["status"] = "unreadable"
        return payload

    payload["available"] = True
    payload["status"] = "ok"
    payload["scanned_rows"] = len(recent)

    plan_items: list[dict] = []
    repo_items: list[dict] = []
    for line_number, line in reversed(recent):
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            payload["invalid_rows"] += 1
            continue
        if not isinstance(row, dict) or not row_has_publish_or_checkpoint_event(row):
            continue

        if ledger_row_matches_plan(row, plan_paths, repo):
            payload["plan_total"] += 1
            if len(plan_items) < item_limit:
                plan_items.append(compact_ledger_row(row, line_number, "plan"))
            continue

        if repo and str(row.get("repo", "")) == repo:
            payload["repo_total"] += 1
            if len(repo_items) < item_limit:
                repo_items.append(compact_ledger_row(row, line_number, "repo"))

    items = plan_items[:item_limit]
    if len(items) < item_limit:
        items.extend(repo_items[: item_limit - len(items)])
    payload["items"] = items
    payload["returned"] = len(items)
    payload["truncated"] = (payload["plan_total"] + payload["repo_total"]) > len(items)
    return payload


def resolve_ledger_plan_target(raw: str) -> Path | None:
    path = safe_resolve(raw)
    if path and path.name == "PLAN.md":
        return path
    return None


def discover_plans() -> list[dict]:
    """Walk DEV_ROOT and return one entry per PLAN.md found.

    Post-processing wires up:
      * `children`: list of child plan-dicts that backlink this plan via
        `> Parent: <relpath>`. The list lives directly on the parent so the
        client can render indented sidebar rows without a second pass.
      * `aggregate_stats`: rolled-up `task_stats` across this plan plus every
        descendant in the parent→children tree. Cycle-safe via visited-set.
    """
    seen: set[Path] = set()
    plans: list[dict] = []
    for pattern in PLAN_GLOBS:
        # recursive=True so `**` in patterns expands to "any depth"; deduped
        # against the seen-set below so the shallow + recursive variants
        # of the same pattern don't double-count.
        for hit in glob(str(DEV_ROOT / pattern), recursive=True):
            path = Path(hit).resolve()
            if path in seen:
                continue
            if "node_modules" in path.parts:
                continue
            seen.add(path)
            plans.append(plan_meta(path))
    plans = dedupe_legacy_repo_plans(plans)
    plans = attach_children(plans)
    aggregate_memo: dict[str, dict] = {}
    for plan in plans:
        plan["aggregate_stats"] = aggregate_stats(plan, _memo=aggregate_memo)
    sessions = discover_repo_sessions({plan["repo"] for plan in plans})
    for plan in plans:
        plan["session"] = sessions.get(plan["repo"], missing_session_payload(plan["repo"]))
    plans.sort(key=lambda p: (-p["mtime"], p["repo"], p["slug"]))
    return plans


def plan_list_payload(plans: list[dict]) -> list[dict]:
    """Return sidebar-safe plan metadata without recursively embedding children.

    `discover_plans()` keeps full child objects in memory because aggregate
    stats and tests use that shape. The HTTP list endpoint should not duplicate
    every child subtree in JSON; the browser can rehydrate child objects from
    these rels after one pass through the flat list.
    """
    payload: list[dict] = []
    for plan in plans:
        item = {
            k: v
            for k, v in plan.items()
            if k not in (
                "children",
                "dashboard_tasks",
                "dashboard_verdicts",
                "dashboard_inbox_entries",
                "dashboard_ask_leo_entries",
            )
        }
        item["child_rels"] = [child["rel"] for child in plan.get("children", [])]
        payload.append(item)
    return payload


def format_eta_hours(hours: float) -> str:
    value = round(float(hours), 2)
    if value.is_integer():
        return f"{int(value)}h"
    return f"{value:.2f}".rstrip("0").rstrip(".") + "h"


def build_fleet_summary(plans: list[dict]) -> dict:
    plans_count = len(plans)
    repos_count = len({plan.get("repo", "") for plan in plans if plan.get("repo")})
    completed = 0
    total = 0
    eta_remaining = 0.0
    eta_tagged = 0
    eta_eligible = 0
    for plan in plans:
        stats = plan.get("task_stats") or {}
        counts = stats.get("counts") or {}
        completed += int(counts.get("completed") or 0)
        total += int(stats.get("total") or 0)
        eta_remaining += float(stats.get("eta_total") or 0.0)
        eta_tagged += int(stats.get("eta_tagged") or 0)
        eta_eligible += int(stats.get("eta_eligible") or 0)

    pct = round((completed / total) * 100) if total else 0
    eta_remaining = round(eta_remaining, 2)
    return {
        "plans": plans_count,
        "repos": repos_count,
        "tasks_completed": completed,
        "tasks_total": total,
        "completion_pct": pct,
        "eta_remaining_hours": eta_remaining,
        "eta_remaining_label": f"{format_eta_hours(eta_remaining)} remaining",
        "eta_tagged": eta_tagged,
        "eta_eligible": eta_eligible,
    }


def dashboard_source_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(DEV_ROOT))
    except (OSError, ValueError):
        return str(path)


def dashboard_base_item(plan: dict, source_path: Path, raw: dict, *, kind: str, tab: str) -> dict:
    item = {
        "kind": kind,
        "repo": plan.get("repo", ""),
        "rel": plan.get("rel", ""),
        "path": plan.get("path", ""),
        "source_path": str(source_path),
        "source_rel": dashboard_source_rel(source_path),
        "tab": tab,
        "line": raw.get("line"),
        "label": raw.get("label", ""),
        "status": raw.get("status", ""),
    }
    proof_path = raw.get("proof_path", "")
    if proof_path:
        item["proof_path"] = proof_path
        if raw.get("proof_rel"):
            item["proof_rel"] = raw.get("proof_rel")
        elif Path(str(proof_path)).is_absolute():
            item["proof_rel"] = dashboard_source_rel(Path(str(proof_path)))
        else:
            item["proof_rel"] = proof_path
    return item


def build_dashboard(plans: list[dict], limit: int = DASHBOARD_ITEM_LIMIT) -> dict:
    categories: dict[str, dict] = {
        "in_progress": {"label": "In Progress", "items": [], "total": 0},
        "blocked": {"label": "Blocked", "items": [], "total": 0},
        "verdicts": {"label": "Verdicts", "items": [], "total": 0},
        "decisions": {"label": "Decisions", "items": [], "total": 0},
        "ask_leo": {"label": "ASK-LEO", "items": [], "total": 0},
        "inbox": {"label": "INBOX", "items": [], "total": 0},
    }

    def add(category: str, item: dict) -> None:
        bucket = categories[category]
        bucket["total"] += 1
        if len(bucket["items"]) < limit:
            bucket["items"].append(item)

    for plan in plans:
        plan_path = Path(plan.get("path", ""))
        for task in plan.get("dashboard_tasks", []) or []:
            status = task.get("status", "")
            if status in ("in_progress", "blocked"):
                add(status, dashboard_base_item(plan, plan_path, task, kind="task", tab="PLAN.md"))

        for verdict in plan.get("dashboard_verdicts", []) or []:
            add("verdicts", dashboard_base_item(plan, plan_path, verdict, kind="verdict", tab="PLAN.md"))

        for entry in (plan.get("decision_log") or {}).get("recent_directions", []) or []:
            label_parts = [part for part in [entry.get("date"), entry.get("body") or entry.get("raw")] if part]
            label = clean_plan_brief_text(" ".join(label_parts), 220)
            if label:
                add(
                    "decisions",
                    dashboard_base_item(
                        plan,
                        plan_path,
                        {
                            "label": label,
                            "line": entry.get("line"),
                            "status": (entry.get("kind") or "decision").lower(),
                        },
                        kind="decision",
                        tab="Decision Log",
                    ),
                )

        inbox_path = plan_path.parent / "INBOX.md"
        for entry in plan.get("dashboard_inbox_entries", []) or []:
            add("inbox", dashboard_base_item(plan, inbox_path, entry, kind="inbox", tab="INBOX.md"))

        ask_path = plan_path.parent / "ASK-LEO.md"
        for entry in plan.get("dashboard_ask_leo_entries", []) or []:
            add("ask_leo", dashboard_base_item(plan, ask_path, entry, kind="ask_leo", tab="ASK-LEO.md"))

    for bucket in categories.values():
        bucket["truncated"] = bucket["total"] > len(bucket["items"])
        bucket["limit"] = limit

    return {
        "generated_at": _truth_now(),
        "plans_scanned": len(plans),
        "repos": len({plan.get("repo", "") for plan in plans if plan.get("repo")}),
        "limit": limit,
        "categories": categories,
    }


def attach_children(plans: list[dict]) -> list[dict]:
    """Group plans by parent_rel and attach `children` lists in place.

    Lookup is two-tier: prefer an exact match against full DEV_ROOT-rel paths
    (e.g., `repo/vidux/foo/PLAN.md`), then fall back to a repo-scoped match
    where the backlink is written relative to the repo root (e.g.,
    `vidux/foo/PLAN.md` from a child living in the same repo). Authors write
    backlinks the natural way — relative to where they are — so the resolver
    has to bridge both shapes.

    Children are sorted by rel-path for deterministic UI order. Plans without
    a recognized parent get `children = []` so the frontend can branch on
    existence-only rather than presence checks.
    """
    by_rel: dict[str, dict] = {p["rel"]: p for p in plans}
    by_path: dict[Path, dict] = {Path(p["path"]).resolve(): p for p in plans}
    # Repo-scoped index: ('<repo>', '<repo-relative-rel>') → plan. The
    # repo-relative rel strips the leading `<repo>/` so a child's
    # `vidux/foo/PLAN.md` backlink finds `<repo>/vidux/foo/PLAN.md`.
    by_repo_rel: dict[tuple[str, str], dict] = {}
    for plan in plans:
        parts = plan["rel"].split("/")
        if len(parts) >= 2:
            by_repo_rel[(plan["repo"], "/".join(parts[1:]))] = plan
    for plan in plans:
        plan["children"] = []
    for plan in plans:
        parent_rel = plan.get("parent_rel")
        if not parent_rel:
            continue
        parent = by_rel.get(parent_rel)
        if parent is None:
            parent = resolve_relative_parent(plan, parent_rel, by_path)
        if parent is None:
            # Backlink wasn't a full DEV_ROOT-rel — try repo-scoped resolution.
            parent = by_repo_rel.get((plan["repo"], parent_rel))
        if parent is None:
            # Dangling backlink — child references a parent we didn't discover
            # in either repo. Leave it ungrouped at the sidebar root.
            continue
        if parent is plan:
            # Self-reference (a plan that says "Parent: <self>"). Ignore.
            continue
        parent["children"].append(plan)
    for plan in plans:
        plan["children"].sort(key=lambda c: c["rel"])
    return plans


def resolve_relative_parent(plan: dict, parent_ref: str, by_path: dict[Path, dict]) -> dict | None:
    """Resolve `Parent: ../../PLAN.md` style refs from the child plan's directory."""
    if not parent_ref.startswith(("./", "../")):
        return None
    try:
        candidate = (Path(plan["path"]).resolve().parent / parent_ref).resolve()
        candidate.relative_to(DEV_ROOT)
    except (OSError, ValueError):
        return None
    return by_path.get(candidate)


def aggregate_stats(
    plan: dict,
    _visited: set[str] | None = None,
    _memo: dict[str, dict] | None = None,
) -> dict:
    """Recursively roll up task_stats across a plan and all descendants.

    Returns the same shape as `task_stats()` (counts/total/eta_total/
    eta_tagged/eta_eligible) plus a `descendants` count. Cycle-safe: the
    visited set tracks rel-paths so a cyclic Parent: chain (broken plan
    authorship) never recurses forever.
    """
    if _visited is None:
        _visited = set()
    if _memo is None:
        _memo = {}
    rel = plan.get("rel", "")
    if rel in _memo:
        return _memo[rel]
    if rel in _visited:
        return {
            "counts": {s: 0 for s in TASK_STATUSES},
            "total": 0,
            "eta_total": 0.0,
            "eta_tagged": 0,
            "eta_eligible": 0,
            "descendants": 0,
        }
    _visited.add(rel)

    own = plan.get("task_stats") or {}
    counts = {s: int((own.get("counts") or {}).get(s, 0)) for s in TASK_STATUSES}
    total = int(own.get("total", 0))
    eta_total = float(own.get("eta_total", 0.0))
    eta_tagged = int(own.get("eta_tagged", 0))
    eta_eligible = int(own.get("eta_eligible", 0))
    descendants = 0

    for child in plan.get("children", []) or []:
        sub = aggregate_stats(child, _visited.copy(), _memo)
        for s in TASK_STATUSES:
            counts[s] += int((sub.get("counts") or {}).get(s, 0))
        total += int(sub.get("total", 0))
        eta_total += float(sub.get("eta_total", 0.0))
        eta_tagged += int(sub.get("eta_tagged", 0))
        eta_eligible += int(sub.get("eta_eligible", 0))
        descendants += 1 + int(sub.get("descendants", 0))

    result = {
        "counts": counts,
        "total": total,
        "eta_total": round(eta_total, 2),
        "eta_tagged": eta_tagged,
        "eta_eligible": eta_eligible,
        "descendants": descendants,
    }
    _memo[rel] = result
    return result


def dedupe_legacy_repo_plans(plans: list[dict]) -> list[dict]:
    """Drop legacy-checkout duplicates when a canonical repo has the same plan."""
    winners: dict[tuple[str, ...], dict] = {}
    for plan in plans:
        parts = Path(plan["rel"]).parts
        if not parts:
            continue
        canonical_repo = LEGACY_REPO_ALIASES.get(plan["repo"], plan["repo"])
        key = (canonical_repo, *parts[1:])
        current = winners.get(key)
        if current is None or plan_preference(plan) > plan_preference(current):
            winners[key] = plan
            continue
        if plan_preference(plan) == plan_preference(current) and plan["mtime"] > current["mtime"]:
            winners[key] = plan
    return list(winners.values())


def plan_preference(plan: dict) -> int:
    return 0 if plan["repo"] in LEGACY_REPO_ALIASES else 1


def plan_meta(path: Path) -> dict:
    rel = path.relative_to(DEV_ROOT)
    parts = rel.parts
    repo = parts[0]
    # Slug is the directory name containing PLAN.md, or "_root_" for repo-root plans.
    parent_dir = path.parent
    if parent_dir == DEV_ROOT / repo:
        slug = "_root_"
    else:
        slug = parent_dir.name
    mtime = path.stat().st_mtime
    age_days = (time.time() - mtime) / 86400
    if age_days <= HOT_DAYS:
        status = "hot"
    elif age_days <= STALE_DAYS:
        status = "stale"
    else:
        status = "cold"
    siblings = [f for f in SIBLING_FILES if (parent_dir / f).is_file()]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    purpose = extract_purpose_from_text(text)
    stats = task_stats(text)
    decision_log = parse_decision_log(text)
    investigations = discover_investigations(parent_dir, text)
    evidence = discover_evidence(parent_dir)
    parent_rel = extract_parent_rel(text)
    dashboard_inbox_entries = read_open_entries(parent_dir / "INBOX.md") if "INBOX.md" in siblings else []
    dashboard_ask_leo_entries = read_ask_leo_entries(parent_dir / "ASK-LEO.md") if "ASK-LEO.md" in siblings else []
    return {
        "repo": repo,
        "slug": slug,
        "path": str(path),
        "rel": str(rel),
        "size": path.stat().st_size,
        "mtime": mtime,
        "age_days": round(age_days, 1),
        "status": status,
        "siblings": siblings,
        "purpose": purpose,
        "task_stats": stats,
        "brief": plan_brief(text, purpose, stats, decision_log),
        "decision_log": decision_log,
        "investigations": investigations,
        "evidence": evidence,
        "parent_rel": parent_rel,
        "dashboard_tasks": extract_dashboard_tasks(text),
        "dashboard_verdicts": extract_dashboard_verdicts(text),
        "dashboard_inbox_entries": dashboard_inbox_entries,
        "dashboard_ask_leo_entries": dashboard_ask_leo_entries,
    }


def extract_parent_rel(text: str) -> str | None:
    """Pull the rel-path from a `> Parent:` or `**Parent:**` backlink.

    Returns a forward-slash rel-path (e.g., `vidux/design-overhaul/PLAN.md`)
    with surrounding backticks/quotes stripped. Anything after whitespace
    in the value (e.g., `... task D2`) is dropped — only the path is meaningful
    for parent→children grouping. Returns None if no backlink is present.
    """
    m = PARENT_REF_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Drop backticks/quotes/markdown emphasis around the path token.
    raw = raw.strip("`'\"")
    # Some plans extend the backlink with `... task D2` — keep only the path.
    token = raw.split()[0] if raw else ""
    token = token.strip("`'\",")
    if not token or token in (".", ".."):
        return None
    # Normalize to forward slashes; PLAN.md `rel` strings always use / on POSIX
    # because `Path.relative_to(...)` plus `str()` round-trips that way on macOS.
    return token.replace("\\", "/")


def task_stats(text: str) -> dict:
    """Parse the `## Tasks` section into status counts + ETA total.

    Returns counts for every known status, total tasks, ETA hours summed
    over pending+in_progress+in_review (ETAs on terminal states are ignored
    per /vidux), and how many of those eligible tasks actually have an ETA
    tag (eta_tagged) vs. how many should (eta_eligible).
    """
    counts = {s: 0 for s in TASK_STATUSES}
    eta_total = 0.0
    eta_tagged = 0
    eta_eligible = 0
    m = TASKS_SECTION_RE.search(text)
    if not m:
        return {
            "counts": counts,
            "total": 0,
            "eta_total": 0.0,
            "eta_tagged": 0,
            "eta_eligible": 0,
        }
    body = m.group(1)
    for line in body.splitlines():
        lm = TASK_LINE_RE.match(line)
        if not lm:
            continue
        status = lm.group(1)
        counts[status] += 1
        if status in ("pending", "in_progress", "in_review"):
            eta_eligible += 1
            em = ETA_RE.search(line)
            if em:
                eta_tagged += 1
                try:
                    eta_total += float(em.group(1))
                except ValueError:
                    pass
    return {
        "counts": counts,
        "total": sum(counts.values()),
        "eta_total": round(eta_total, 2),
        "eta_tagged": eta_tagged,
        "eta_eligible": eta_eligible,
    }


def section_body(text: str, heading: str) -> str:
    """Return a markdown section body by heading text."""
    lines = text.splitlines()
    start_index = None
    start_level = None
    heading_re = re.compile(
        rf"^[ \t]{{0,3}}(?P<marks>##{{1,6}})\s+{re.escape(heading)}\s*#*\s*$",
        re.I,
    )
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        start_index = i
        start_level = len(m.group("marks"))
        break
    if start_index is None or start_level is None:
        return ""
    body_lines: list[str] = []
    for line in lines[start_index + 1:]:
        hm = MARKDOWN_HEADING_RE.match(line)
        if hm and len(hm.group(1)) <= start_level:
            break
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def clean_plan_brief_text(value: str, limit: int = 180) -> str:
    """Compact markdown-ish plan text into a one-line UI summary."""
    text = PLAN_BRIEF_LINK_RE.sub(r"\1", value or "")
    text = PLAN_BRIEF_TAG_RE.sub("", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[*_#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    if len(text) <= limit:
        return text
    clipped = text[: max(0, limit - 3)].rsplit(" ", 1)[0].strip()
    return f"{clipped or text[: max(0, limit - 3)].strip()}..."


def markdown_section_lines(text: str, heading: str) -> list[tuple[int, str]]:
    """Return (1-based line, text) pairs for a markdown heading body."""
    lines = text.splitlines()
    start_index = None
    start_level = None
    heading_re = re.compile(
        rf"^[ \t]{{0,3}}(?P<marks>##{{1,6}})\s+{re.escape(heading)}\s*#*\s*$",
        re.I,
    )
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        start_index = i
        start_level = len(m.group("marks"))
        break
    if start_index is None or start_level is None:
        return []

    body: list[tuple[int, str]] = []
    for i, line in enumerate(lines[start_index + 1:], start=start_index + 2):
        hm = MARKDOWN_HEADING_RE.match(line)
        if hm and len(hm.group(1)) <= start_level:
            break
        body.append((i, line))
    return body


def extract_dashboard_tasks(text: str) -> list[dict]:
    tasks: list[dict] = []
    for line_number, line in markdown_section_lines(text, "Tasks"):
        m = DASHBOARD_TASK_RE.match(line)
        if not m:
            continue
        status = m.group("status")
        if status not in ("in_progress", "blocked"):
            continue
        label = clean_plan_brief_text(m.group("body"), 220)
        if label:
            tasks.append({"status": status, "label": label, "line": line_number})
    return tasks


def extract_dashboard_verdicts(text: str) -> list[dict]:
    verdicts: list[dict] = []
    for line_number, line in markdown_section_lines(text, "Evidence"):
        m = PLAN_BRIEF_BULLET_RE.match(line)
        if not m:
            continue
        body = m.group("body")
        lowered = body.lower()
        has_subject = any(
            phrase in lowered
            for phrase in (
                "planner-executor",
                "bakeoff",
                "h1/h2/h3",
                "kernel handoff",
                "kernel >= freeform",
            )
        )
        has_verdict = any(
            phrase in lowered
            for phrase in (
                "refuted",
                "lost to freeform",
                "kernel-cheaper=false",
                "decision.md",
            )
        )
        if not (has_subject and has_verdict):
            continue

        label = clean_plan_brief_text(body, 260)
        if not label:
            continue
        status = "refuted" if ("refuted" in lowered or "lost to freeform" in lowered) else "verdict"
        source = ""
        source_match = DASHBOARD_SOURCE_TAG_RE.search(body)
        if source_match:
            source = source_match.group("source").strip()
        verdict = {
            "status": status,
            "label": label,
            "line": line_number,
        }
        if source:
            verdict["proof_path"] = source
        verdicts.append(verdict)
    return verdicts


def open_entry_lines(text: str) -> list[tuple[int, str]]:
    open_lines = markdown_section_lines(text, "Open")
    if open_lines:
        return open_lines
    return list(enumerate(text.splitlines(), start=1))


def extract_open_entries(text: str) -> list[dict]:
    entries: list[dict] = []
    for line_number, line in open_entry_lines(text):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("```"):
            continue
        if MARKDOWN_HEADING_RE.match(line) and not DASHBOARD_OPEN_HEADING_RE.match(line):
            continue

        label = ""
        hm = DASHBOARD_OPEN_HEADING_RE.match(line)
        if hm:
            label = hm.group("body")
        else:
            bm = PLAN_BRIEF_BULLET_RE.match(line)
            if bm:
                label = bm.group("body")
        label = clean_plan_brief_text(label, 220)
        if label:
            entries.append({"label": label, "line": line_number})
    return entries


def read_open_entries(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return extract_open_entries(text)


def extract_ask_leo_entries(text: str) -> list[dict]:
    if markdown_section_lines(text, "Open"):
        return extract_open_entries(text)

    lines = text.splitlines()
    entries: list[dict] = []
    for index, line in enumerate(lines):
        m = DASHBOARD_ASK_HEADING_RE.match(line)
        if not m:
            continue
        section_lines: list[str] = []
        for next_line in lines[index + 1:]:
            if re.match(r"^[ \t]{0,3}##\s+\S", next_line):
                break
            section_lines.append(next_line)
        section_text = "\n".join(section_lines)
        if DASHBOARD_ASK_RESOLVED_RE.search(section_text):
            continue
        label = clean_plan_brief_text(m.group("body"), 220)
        if label:
            entries.append({"label": label, "line": index + 1})
    return entries if entries else extract_open_entries(text)


def read_ask_leo_entries(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return extract_ask_leo_entries(text)


def extract_focus_tasks(text: str, limit: int = 3) -> list[dict]:
    body = section_body(text, "Tasks")
    if not body:
        return []
    tasks: list[dict] = []
    for m in PLAN_BRIEF_TASK_RE.finditer(body):
        label = clean_plan_brief_text(m.group("body"), 170)
        if not label:
            continue
        tasks.append({"status": m.group("status"), "label": label})
    order = {"in_progress": 0, "in_review": 1, "blocked": 2, "pending": 3, "completed": 4}
    tasks.sort(key=lambda item: order.get(item["status"], 9))
    return tasks[:limit]


def extract_latest_bullets(text: str, heading: str, limit: int = 1) -> list[str]:
    body = section_body(text, heading)
    if not body:
        return []
    bullets: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if PLAN_BRIEF_TASK_RE.match(line):
            continue
        m = PLAN_BRIEF_BULLET_RE.match(line)
        if m:
            if current:
                bullets.append(clean_plan_brief_text(" ".join(current), 220))
            current = [m.group("body")]
        elif current and line.strip():
            current.append(line.strip())
    if current:
        bullets.append(clean_plan_brief_text(" ".join(current), 220))
    return [b for b in bullets if b][-limit:]


def plan_state_label(stats: dict) -> str:
    counts = stats.get("counts") or {}
    total = int(stats.get("total") or 0)
    completed = int(counts.get("completed") or 0)
    if total and completed == total:
        return "shipped"
    if int(counts.get("blocked") or 0):
        return "blocked"
    if int(counts.get("in_review") or 0):
        return "in review"
    if int(counts.get("in_progress") or 0):
        return "in flight"
    if int(counts.get("pending") or 0):
        return "queued"
    return "no tasks"


def plan_brief(text: str, purpose: str, stats: dict, decision_log: dict) -> dict:
    counts = stats.get("counts") or {}
    total = int(stats.get("total") or 0)
    completed = int(counts.get("completed") or 0)
    latest_decision = ""
    recent_directions = decision_log.get("recent_directions") or []
    if recent_directions:
        latest = recent_directions[-1]
        latest_decision = clean_plan_brief_text(latest.get("body") or latest.get("raw") or "", 220)
    latest_progress = extract_latest_bullets(text, "Progress", 1)
    return {
        "summary": clean_plan_brief_text(purpose or "", 220),
        "state": plan_state_label(stats),
        "open_count": max(total - completed, 0),
        "focus_tasks": extract_focus_tasks(text, 3),
        "latest_progress": latest_progress[0] if latest_progress else "",
        "latest_decision": latest_decision,
    }


def decision_log_body(text: str) -> tuple[str, int | None]:
    """Return the Decision Log section body plus its 1-based heading line."""
    lines = text.splitlines()
    start_index = None
    start_level = None
    for i, line in enumerate(lines):
        m = DECISION_LOG_HEADING_RE.match(line)
        if not m:
            continue
        start_index = i
        start_level = len(m.group("marks"))
        break
    if start_index is None or start_level is None:
        return "", None

    body_lines: list[str] = []
    for line in lines[start_index + 1:]:
        hm = MARKDOWN_HEADING_RE.match(line)
        if hm and len(hm.group(1)) <= start_level:
            break
        body_lines.append(line)
    return "\n".join(body_lines).strip(), start_index + 1


def normalize_decision_entry(raw: str, index: int, line_number: int | None) -> dict:
    """Parse one Decision Log bullet into UI-friendly fields."""
    text = re.sub(r"\s+", " ", raw).strip()
    kind = "NOTE"
    m = DECISION_KIND_RE.match(text)
    if m:
        kind = m.group("kind").upper()
        text = m.group("rest").strip()

    date = ""
    dm = DECISION_DATE_RE.match(text)
    if dm:
        date = dm.group("date").strip()
        text = dm.group("rest").strip()

    body = text or raw.strip()
    return {
        "index": index,
        "line": line_number,
        "kind": kind,
        "date": date,
        "body": body,
        "raw": raw.strip(),
        "is_direction": kind in DECISION_DIRECTION_KINDS,
        "is_recent": False,
    }


def parse_decision_log(text: str) -> dict:
    """Extract Decision Log bullets as first-class read-only plan metadata."""
    body, heading_line = decision_log_body(text)
    entries: list[dict] = []
    if body:
        current: list[str] = []
        current_line: int | None = None
        base_line = (heading_line or 0) + 1
        for offset, line in enumerate(body.splitlines(), start=base_line):
            m = DECISION_ENTRY_RE.match(line)
            if m:
                if current:
                    entries.append(normalize_decision_entry(" ".join(current), len(entries), current_line))
                current = [m.group("body").strip()]
                current_line = offset
                continue
            if current and line.strip():
                current.append(line.strip())
        if current:
            entries.append(normalize_decision_entry(" ".join(current), len(entries), current_line))

    recent_indexes = {entry["index"] for entry in entries[-3:]}
    for entry in entries:
        entry["is_recent"] = entry["index"] in recent_indexes

    recent_directions = [entry for entry in entries if entry["is_direction"]][-3:]
    return {
        "present": heading_line is not None,
        "heading_line": heading_line,
        "count": len(entries),
        "entries": entries,
        "recent_directions": recent_directions,
    }


def discover_investigations(plan_dir: Path, plan_text: str) -> list[str]:
    """Auto-discover .md files under plan_dir/investigations/ + explicit refs.

    Canonical /vidux nesting: a parent task can carry [Investigation: <relpath>]
    pointing at a sub-plan. We surface BOTH the auto-discovered files AND any
    explicit refs from task lines (deduped by resolved path), to handle plans
    that drop investigations without linking them and plans that link without
    a directory.
    """
    found: set[str] = set()
    inv_dir = plan_dir / "investigations"
    if inv_dir.is_dir():
        for f in inv_dir.glob("*.md"):
            if f.is_file():
                found.add(str(f.resolve()))
    for ref in INVESTIGATION_RE.findall(plan_text):
        rel = ref.strip().strip("`'\"")
        try:
            candidate = (plan_dir / rel).resolve()
            candidate.relative_to(plan_dir.resolve())
        except (OSError, ValueError):
            continue
        if candidate.is_file() and candidate.suffix == ".md":
            found.add(str(candidate))
    return sorted(found)


def evidence_label(path: Path) -> str:
    stem = path.stem.strip()
    if not stem:
        return path.name
    dated = re.match(r"^(\d{4}-\d{2}-\d{2})[-_](.+)$", stem)
    if dated:
        slug = re.sub(r"[-_]+", " ", dated.group(2)).strip()
        return f"{dated.group(1)} - {slug}" if slug else dated.group(1)
    return re.sub(r"[-_]+", " ", stem)


def discover_evidence(plan_dir: Path) -> list[dict]:
    """Discover markdown evidence files in chronological order.

    Canonical evidence names are `YYYY-MM-DD-<slug>.md`, but real plans
    accumulate hand-written receipts. Non-markdown files and nested directories
    are ignored; oddly named markdown is still surfaced after dated evidence
    with a readable label so the browser fails open for receipts, not the page.
    """
    evidence_dir = plan_dir / "evidence"
    if not evidence_dir.is_dir():
        return []
    items: list[dict] = []
    for path in evidence_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        st = path.stat()
        date_match = EVIDENCE_DATE_RE.match(path.name)
        items.append({
            "path": str(path.resolve()),
            "name": path.name,
            "label": evidence_label(path),
            "date": date_match.group(1) if date_match else "",
            "mtime": st.st_mtime,
            "size": st.st_size,
            "is_dated": bool(date_match),
        })
    items.sort(key=lambda item: (
        0 if item["is_dated"] else 1,
        item["date"] or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(item["mtime"])),
        item["name"].lower(),
    ))
    return items


def extract_purpose_from_text(text: str) -> str:
    """Pull the first non-heading paragraph under '## Purpose' from plan text."""
    # Strip leading Parent: metadata blockquote / bold line so it doesn't
    # leak into the sidebar purpose preview.
    text = re.sub(
        r"^(#[^\n]*\n+)?(?:>[ \t]*Parent:|\*\*Parent:\*\*)[^\n]*\n+",
        lambda m: m.group(1) or "",
        text,
        count=1,
    )
    m = re.search(r"##\s+Purpose\s*\n+([^\n#].+?)(?=\n\s*\n|\n##|\Z)", text, re.S)
    if not m:
        # Fall back to first non-heading paragraph after the title.
        m = re.search(r"^#[^\n]*\n+([^\n#].+?)(?=\n\s*\n|\n##|\Z)", text, re.S | re.M)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:240]


def extract_purpose(path: Path) -> str:
    """Compatibility wrapper for callers that only have a path."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return extract_purpose_from_text(text)


def safe_resolve(raw: str) -> Path | None:
    """Allow PLAN.md + canonical siblings + .md files in investigations/ or evidence/.

    The whitelist is the read-only contract. node_modules paths are rejected
    even when the filename matches. The `investigations/` + `evidence/` rules
    are the canonical /vidux nesting per DOCTRINE.md + guides/investigation.md
    + guides/evidence-format.md — surfacing them is part of the viewer's job.
    """
    try:
        p = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        p.relative_to(DEV_ROOT)
    except ValueError:
        return None
    if "node_modules" in p.parts:
        return None
    if not p.is_file():
        return None
    if p.name in ALLOWED_PLAN_FILES:
        return p
    if p.suffix == ".md" and ("investigations" in p.parts or "evidence" in p.parts):
        return p
    return None


def safe_resolve_any(raw: str) -> Path | None:
    """safe_resolve() OR an .html artifact under ARTIFACTS_DIR. Read-only either way."""
    p = safe_resolve(raw)
    if p:
        return p
    try:
        candidate = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(ARTIFACTS_DIR.resolve())
    except ValueError:
        return None
    if candidate.suffix.lower() != ".html":
        return None
    if not candidate.is_file():
        return None
    return candidate


def is_allowed_file_target(raw: str) -> bool:
    """Return True when a missing /api/file target would otherwise be allowed."""
    try:
        candidate = Path(raw).resolve(strict=False)
    except (OSError, ValueError):
        return False
    if "node_modules" in candidate.parts:
        return False
    try:
        candidate.relative_to(DEV_ROOT)
    except ValueError:
        pass
    else:
        if candidate.name in ALLOWED_PLAN_FILES:
            return True
        if candidate.suffix == ".md" and (
            "investigations" in candidate.parts or "evidence" in candidate.parts
        ):
            return True
    try:
        candidate.relative_to(ARTIFACTS_DIR.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return candidate.suffix.lower() == ".html"


def read_browser_file(path: Path) -> tuple[int, bytes | str]:
    try:
        return 200, path.read_bytes()
    except FileNotFoundError:
        return 404, f"file missing: {path.name}"
    except OSError as exc:
        return 500, f"file read failed: {exc}"


def discover_artifacts() -> list[dict]:
    """List ad-hoc HTML artifacts in ARTIFACTS_DIR, newest first."""
    if not ARTIFACTS_DIR.is_dir():
        return []
    items: list[dict] = []
    for path in ARTIFACTS_DIR.glob("*.html"):
        if not path.is_file():
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4096]
        except OSError:
            head = ""
        m = ARTIFACT_TITLE_RE.search(head)
        if m:
            raw_title = (m.group(1) or m.group(2) or "").strip()
            title = raw_title or path.stem
        else:
            title = path.stem
        st = path.stat()
        age_days = (time.time() - st.st_mtime) / 86400
        items.append({
            "slug": path.stem,
            "title": title[:200],
            "path": str(path),
            "size": st.st_size,
            "mtime": st.st_mtime,
            "age_days": round(age_days, 1),
        })
    items.sort(key=lambda a: -a["mtime"])
    return items


def write_artifact(slug: str, html: str) -> tuple[bool, str]:
    """Write an artifact. Returns (ok, message)."""
    if not ARTIFACT_SLUG_RE.match(slug):
        return False, "slug must match [a-z0-9][a-z0-9-]{0,63}"
    if len(html.encode("utf-8")) > ARTIFACT_MAX_BYTES:
        return False, f"html exceeds {ARTIFACT_MAX_BYTES} bytes"
    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        path = ARTIFACTS_DIR / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, str(path)


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


def request_host_hostname(host: str) -> str:
    """Hostname portion of a Host header, tolerating IPv6 literals like [::1]:7191."""
    netloc = (host or "").strip().lower()
    if not netloc:
        return ""
    if netloc.startswith("["):
        end = netloc.find("]")
        return netloc[: end + 1] if end != -1 else netloc
    return netloc.rsplit(":", 1)[0] if ":" in netloc else netloc


def is_private_lan_ip_literal(hostname: str) -> bool:
    """True when hostname is a raw private-use (RFC 1918 / RFC 4193) IP literal.

    DNS rebinding always presents Host as the attacker's registered domain
    name (that's what the browser's address bar held) -- never as a raw IP
    literal, since there is no reason for an attacker to own a private-range
    IP. A genuine LAN device is reached by IP on a home network (no local DNS
    entry for the vidux server), so requiring a private-IP literal here
    accepts real LAN peers while rejecting a rebound domain outright.
    """
    text = hostname.strip("[]")
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return False
    return addr.is_private and not addr.is_loopback and not addr.is_link_local


def is_allowed_request_host(host: str, bind_host: str) -> bool:
    """Reject requests whose Host header isn't a recognized loopback identity.

    Origin/Referer-must-match-Host (origin_matches_host) does not stop DNS
    rebinding: a rebound page's browser sends a Host header and an Origin
    header that agree with EACH OTHER (both reflect the attacker's domain),
    so that check passes even though the TCP connection actually lands on
    this loopback server. An independent Host allowlist is required because
    a rebound domain can never legitimately present as "127.0.0.1"/"localhost".

    Skipped when explicitly bound to 0.0.0.0/:: (documented trusted-LAN read
    mode, README/SKILL.md) -- LAN client Host headers are expected there by
    design; writes stay loopback-gated separately via client_address.
    """
    if bind_host in ("0.0.0.0", "::"):
        return True
    hostname = request_host_hostname(host)
    if not hostname:
        return False
    allowed = {"127.0.0.1", "localhost", "[::1]", "::1"}
    if bind_host not in ("0.0.0.0", "::"):
        allowed.add(bind_host.strip().lower())
    return hostname in allowed


def is_json_content_type(value: str | None) -> bool:
    return (value or "").split(";", 1)[0].strip().lower() == JSON_CONTENT_TYPE


def origin_matches_host(raw: str, host: str) -> bool:
    if not raw or raw == "null" or not host:
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return parsed.netloc.lower() == host.lower()


def clean_note_label(raw: object, default: str) -> str:
    text = str(raw or default).strip()
    text = PLAN_NOTE_SOURCE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return (text or default)[:120]


def clean_comment_author(raw: object) -> str:
    text = str(raw or "").strip()
    text = COMMENT_AUTHOR_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return (text or "Anonymous")[:COMMENT_AUTHOR_MAX_CHARS]


def clean_comment_anchor_text(raw: object, limit: int) -> str:
    text = str(raw or "").strip()
    text = COMMENT_ANCHOR_CONTROL_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def clean_comment_anchor(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    anchor: dict[str, object] = {"version": 1}
    for key, limit in COMMENT_ANCHOR_FIELD_LIMITS.items():
        value = clean_comment_anchor_text(raw.get(key), limit)
        if value:
            anchor[key] = value
    if "index" in raw:
        try:
            index = int(raw.get("index"))
        except (TypeError, ValueError):
            index = None
        if index is not None and 0 <= index <= 100_000:
            anchor["index"] = index
    return anchor if len(anchor) > 1 else None


def comment_target_kind(path: Path) -> str:
    try:
        path.relative_to(ARTIFACTS_DIR.resolve())
    except ValueError:
        return "plan"
    return "artifact"


def append_comment(
    target_path: Path,
    author: object,
    body: str,
    remote_address: str,
    anchor: object = None,
) -> tuple[bool, str | dict]:
    text = body.strip()
    if not text:
        return False, "comment must be non-empty"
    if len(text.encode("utf-8")) > COMMENT_BODY_MAX_BYTES:
        return False, f"comment exceeds {COMMENT_BODY_MAX_BYTES} bytes"

    record = {
        "id": str(uuid.uuid4()),
        "target_path": str(target_path),
        "target_kind": comment_target_kind(target_path),
        "author": clean_comment_author(author),
        "body": text,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "remote_address": remote_address,
    }
    clean_anchor = clean_comment_anchor(anchor)
    if clean_anchor:
        record["anchor"] = clean_anchor

    try:
        COMMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with COMMENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, record


def read_comments(target_path: Path, limit: int = 100) -> list[dict]:
    if not COMMENTS_FILE.is_file():
        return []
    target = str(target_path)
    comments: list[dict] = []
    try:
        for line in COMMENTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("target_path") == target:
                comments.append(item)
    except OSError:
        return []
    return comments[-limit:]


def resolve_plan_note_target(raw: str) -> Path | None:
    p = safe_resolve(raw)
    if not p or p.name != "PLAN.md":
        return None
    return p


def write_plan_note(
    plan_path: Path,
    note: str,
    source: str = "vidux-browse-local",
    agent: str = "",
) -> tuple[bool, str]:
    """Append a local note to the plan directory's INBOX.md."""
    body = note.strip()
    if not body:
        return False, "note must be non-empty"
    if len(body.encode("utf-8")) > PLAN_NOTE_MAX_BYTES:
        return False, f"note exceeds {PLAN_NOTE_MAX_BYTES} bytes"

    source = clean_note_label(source, "vidux-browse-local")
    agent = clean_note_label(agent, "") if agent else ""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    title = re.sub(r"\s+", " ", body.splitlines()[0]).strip()[:96]
    inbox = plan_path.parent / "INBOX.md"
    quote = "\n".join(f"> {line}" if line else ">" for line in body.splitlines())
    lines = [
        f"### {stamp} - {title}",
        f"- Source: {source}",
    ]
    if agent:
        lines.append(f"- Agent: {agent}")
    entry = "\n".join(lines) + "\n\n" + quote + "\n\n"

    if inbox.exists():
        try:
            text = inbox.read_text(encoding="utf-8")
        except OSError as e:
            return False, f"read failed: {e}"
    else:
        text = f"# {plan_path.parent.name} Inbox\n\n## Open\n\n## Processed\n"

    marker = re.search(r"(^## Open\s*\n)", text, re.M)
    if marker:
        insert_at = marker.end()
        text = text[:insert_at] + "\n" + entry + text[insert_at:]
    else:
        text = text.rstrip() + "\n\n## Open\n\n" + entry

    try:
        inbox.write_text(text, encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, str(inbox)


class Handler(BaseHTTPRequestHandler):
    server_version = "viduxBrowser/0.1"

    def log_message(self, fmt, *args):  # noqa: N802 — stdlib override
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def do_GET(self):  # noqa: N802 — stdlib override
        if not self._host_header_ok():
            return
        url = urlparse(self.path)
        route = url.path
        qs = parse_qs(url.query)
        if route == "/" or route == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif route == "/receipts" or route == "/receipts/":
            self._serve_static("receipts.html", "text/html; charset=utf-8")
        elif route.startswith("/static/"):
            name = route[len("/static/"):]
            self._serve_static(name)
        elif route == "/api/health":
            self._json({"ok": True, "dev_root": str(DEV_ROOT), "port": PORT,
                        "repo_root": str(VIDUX_ROOT),
                        "server_path": str(SERVER_FILE),
                        "server_mtime_ns": SERVER_MTIME_NS,
                        "artifacts_dir": str(ARTIFACTS_DIR)})
        elif route == "/api/plans":
            plans = discover_plans_cached()
            self._json({
                "plans": plan_list_payload(plans),
                "summary": build_fleet_summary(plans),
                "dashboard": build_dashboard(plans),
                "dev_root": str(DEV_ROOT),
            })
        elif route == "/api/artifacts":
            self._json({"artifacts": discover_artifacts(),
                        "artifacts_dir": str(ARTIFACTS_DIR)})
        elif route == "/api/vidux/truth":
            refresh = (qs.get("refresh") or [""])[0]
            self._json(
                vidux_truth_payload(force_refresh=True)
                if refresh == "sync"
                else vidux_truth_cached_payload()
            )
        elif route == "/api/ledger":
            raw = (qs.get("path") or [""])[0]
            plan_path = resolve_ledger_plan_target(raw)
            if not plan_path:
                self._send(403, "forbidden")
                return
            self._json(ledger_payload_for_plan(plan_path))
        elif route == "/api/comments":
            raw = (qs.get("path") or [""])[0]
            p = safe_resolve_any(raw)
            if not p:
                self._send(403, "forbidden")
                return
            self._json({
                "ok": True,
                "path": str(p),
                "target_kind": comment_target_kind(p),
                "comments": read_comments(p),
            })
        elif route == "/api/file":
            raw = (qs.get("path") or [""])[0]
            p = safe_resolve_any(raw)  # plans + artifacts
            if not p:
                if is_allowed_file_target(raw):
                    self._send(404, f"file missing: {Path(raw).name}")
                    return
                self._send(403, "forbidden")
                return
            ctype = ("text/html; charset=utf-8" if p.suffix.lower() == ".html"
                     else "text/markdown; charset=utf-8")
            status, body = read_browser_file(p)
            if status != 200:
                self._send(status, body if isinstance(body, str) else "file read failed")
                return
            self._send_with_type(body, ctype)
        elif route == "/api/receipts/list":
            status, body = _receipts_handler.handle_list()
            self._send(status, "") if status >= 400 else self._json(body)
        elif route.startswith("/api/receipts/") and route.endswith("/image"):
            row_id = route[len("/api/receipts/"):-len("/image")]
            status, ctype, data = _receipts_handler.handle_image(row_id)
            if status == 200:
                self._send_with_type(data, ctype)
            else:
                self._send(status, data.get("error", "error") if isinstance(data, dict) else "error")
        else:
            self._send(404, "not found")

    def do_HEAD(self):  # noqa: N802 — stdlib override
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_POST(self):  # noqa: N802 — stdlib override
        if not self._host_header_ok():
            return
        url = urlparse(self.path)
        if url.path == "/api/artifact":
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > ARTIFACT_MAX_BYTES + 1024:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            slug = str(payload.get("slug", "")).strip()
            html = payload.get("html", "")
            if not isinstance(html, str):
                self._send(400, "html must be a string")
                return
            ok, msg = write_artifact(slug, html)
            if not ok:
                self._send(400, msg)
                return
            self._json({"ok": True, "slug": slug, "path": msg})
        elif url.path == "/api/local-plan-note":
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > PLAN_NOTE_MAX_BYTES + 2048:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            plan_path = resolve_plan_note_target(str(payload.get("plan_path", "")))
            if not plan_path:
                self._send(403, "plan_path must be an allowed PLAN.md under dev_root")
                return
            note = payload.get("note", "")
            if not isinstance(note, str):
                self._send(400, "note must be a string")
                return
            ok, msg = write_plan_note(
                plan_path,
                note,
                source=str(payload.get("source", "vidux-browse-local")),
                agent=str(payload.get("agent", "")),
            )
            if not ok:
                self._send(400, msg)
                return
            self._json({"ok": True, "path": msg})
        elif url.path == "/api/upload-ref-audio":
            # Loopback-only personal use. Browser uploads a base64 audio sample
            # to be saved at /tmp/vidux-readaloud-ref-<sha8>.<ext> and the path
            # passed to mlx-audio.server's `ref_audio` field for voice cloning.
            # See projects/voxtral-reader-addon/PLAN.md M8.
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            # 15 MB cap — 30s of 24kHz 16-bit mono WAV is ~1.4 MB; large stereo
            # 48kHz samples can hit 5-8 MB; 15 MB has comfortable headroom.
            if length <= 0 or length > 15 * 1024 * 1024:
                self._send(400, "missing or oversized body (15 MB cap)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            b64 = payload.get("audio_base64", "")
            if not isinstance(b64, str) or not b64:
                self._send(400, "audio_base64 (string) is required")
                return
            ext = str(payload.get("ext", "wav")).lower().strip(".")
            if ext not in {"wav", "mp3", "m4a", "flac", "ogg"}:
                self._send(400, "ext must be one of wav|mp3|m4a|flac|ogg")
                return
            import base64 as _base64
            import hashlib as _hashlib
            import tempfile as _tempfile
            import time as _time
            try:
                audio_bytes = _base64.b64decode(b64, validate=True)
            except Exception as e:
                self._send(400, f"audio_base64 not valid base64: {e}")
                return
            if len(audio_bytes) < 1024:
                self._send(400, "audio sample too small (<1 KB)")
                return
            # Cheap sanity check: WAV files start with RIFF; MP3 with ID3 or 0xFFFB;
            # M4A with ftyp at offset 4. We don't reject on signature mismatch (some
            # tools omit headers), just refuse obviously not-audio (HTML/JSON/etc).
            head = audio_bytes[:8]
            if head[:1] in (b"<", b"{", b"["):
                self._send(400, "uploaded data does not look like audio")
                return
            sha = _hashlib.sha256(audio_bytes).hexdigest()[:12]
            tmp_dir = _tempfile.gettempdir()
            out_path = os.path.join(tmp_dir, f"vidux-readaloud-ref-{sha}.{ext}")
            try:
                with open(out_path, "wb") as f:
                    f.write(audio_bytes)
            except OSError as e:
                self._send(500, f"failed to write reference audio: {e}")
                return
            # Best-effort GC: prune our own tmp files older than 24 h. Bounded
            # work — only matches our prefix, so it can't sweep unrelated files.
            try:
                cutoff = _time.time() - 24 * 3600
                for entry in os.listdir(tmp_dir):
                    if entry.startswith("vidux-readaloud-ref-") and entry != f"vidux-readaloud-ref-{sha}.{ext}":
                        p = os.path.join(tmp_dir, entry)
                        try:
                            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                                os.remove(p)
                        except OSError:
                            pass
            except OSError:
                pass
            self._json({"ok": True, "path": out_path, "bytes": len(audio_bytes), "sha": sha})
        elif url.path == "/api/comments":
            if not self._require_comment_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > COMMENT_BODY_MAX_BYTES + 2048:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            target_path = safe_resolve_any(str(payload.get("target_path", "")))
            if not target_path:
                self._send(403, "target_path must be an allowed plan file or artifact")
                return
            body = payload.get("body", "")
            if not isinstance(body, str):
                self._send(400, "body must be a string")
                return
            ok, result = append_comment(
                target_path,
                payload.get("author", ""),
                body,
                self.client_address[0],
                anchor=payload.get("anchor"),
            )
            if not ok:
                self._send(400, str(result))
                return
            self._json({"ok": True, "comment": result})
        elif url.path == "/api/receipts/upload":
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            # Cap matches handler.MAX_IMAGE_BYTES (15 MB) + base64 overhead (~33%) + JSON wrapper.
            if length <= 0 or length > 22 * 1024 * 1024:
                self._send(400, "missing or oversized body (22 MB cap for base64-wrapped JSON)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            status, body = _receipts_handler.handle_upload(payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/tag"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/tag")]
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16 * 1024:
                self._send(400, "missing or oversized body (16 KB cap for tag payload)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            status, body = _receipts_handler.handle_tag(row_id, payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/ocr"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/ocr")]
            status, body = _receipts_handler.handle_ocr(row_id)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/expected"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/expected")]
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64 * 1024:
                self._send(400, "missing or oversized body (64 KB cap for expected payload)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            status, body = _receipts_handler.handle_set_expected(row_id, payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/delete"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/delete")]
            status, body = _receipts_handler.handle_delete(row_id)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/analyze"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/analyze")]
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4 * 1024:  # reject oversized — don't silently treat it as an empty body
                self._send(413, "analyze body too large")
                return
            payload = {}
            if length > 0:  # empty body is allowed (argless analyze uses provider defaults)
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    payload = {}
            # Multi-provider extract + compare (claude + qwen + azure). Blocks ~30s; the
            # ThreadingHTTPServer handles it on its own thread.
            status, body = _receipts_handler.handle_analyze(row_id, payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        else:
            self._send(404, "not found")

    def _host_header_ok(self) -> bool:
        if is_allowed_request_host(self.headers.get("Host") or "", HOST):
            return True
        self._send(403, "Host header not recognized")
        return False

    def _require_json_write(self) -> bool:
        if not is_loopback_host(self.client_address[0]):
            self._send(403, "write endpoints require loopback client")
            return False
        return self._require_browser_json()

    def _require_comment_write(self) -> bool:
        """/api/comments is the one write route that's meant to work from a
        real LAN peer too (SKILL.md: "Cross-machine LAN viewers may comment
        via the UI") -- unlike every other write route it can't just require
        is_loopback_host(client_address). Accept the real TCP loopback peer
        (matches every other write route) OR, only in the documented LAN-bind
        mode, a request whose Host header is a private-use IP literal (never
        what a DNS-rebound page's Host header looks like -- that's always the
        attacker's own registered domain name, not a raw private IP)."""
        if not is_loopback_host(self.client_address[0]):
            host = request_host_hostname(self.headers.get("Host") or "")
            if not (HOST in ("0.0.0.0", "::") and is_private_lan_ip_literal(host)):
                self._send(403, "comments require a loopback or private-LAN client")
                return False
        return self._require_browser_json(require_origin=True)

    def _require_browser_json(self, require_origin: bool = False) -> bool:
        if not is_json_content_type(self.headers.get("Content-Type")):
            self._send(415, "Content-Type must be application/json")
            return False
        ok, reason = self._same_origin_ok(require_origin=require_origin)
        if not ok:
            self._send(403, reason)
            return False
        return True

    def _same_origin_ok(self, require_origin: bool = False) -> tuple[bool, str]:
        host = (self.headers.get("Host") or "").strip()
        origin = (self.headers.get("Origin") or "").strip()
        referer = (self.headers.get("Referer") or "").strip()
        if origin:
            if origin_matches_host(origin, host):
                return True, ""
            return False, "Origin must match vidux-browse host"
        if referer:
            if origin_matches_host(referer, host):
                return True, ""
            return False, "Referer must match vidux-browse host"
        if require_origin:
            return False, "Origin or Referer required"
        return True, ""

    def _serve_static(self, name: str, ctype: str | None = None):
        if not name:
            self._send(404, "not found")
            return
        try:
            candidate = (STATIC_DIR / name).resolve()
            candidate.relative_to(STATIC_DIR.resolve())
        except (OSError, ValueError):
            self._send(404, "not found")
            return
        if not candidate.is_file():
            self._send(404, f"static asset missing: {name}")
            return
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or guess_content_type(candidate.name))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write_body(body)

    def _write_body(self, body: bytes) -> bool:
        if getattr(self, "_head_only", False):
            return True
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return False
        return True

    def _json(self, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write_body(body)

    def _send_with_type(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write_body(body)

    def _send_text(self, text: str):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write_body(body)

    def _send(self, code: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._write_body(body)


def guess_content_type(name: str) -> str:
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    if name.endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"


def main(argv=None):
    """Entry point. CLI flags override env defaults so test harnesses and
    Playwright `webServer` can launch the server hermetically against a
    fixture root + ephemeral port without mutating the user's shell env."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="vidux browser",
        description="Plan + artifact viewer for /vidux fleets. LAN-safe (loopback default).",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Dev-root directory to scan for PLAN.md files. Defaults to env "
             "VIDUX_DEV_ROOT or ~/Development.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind. Defaults to env VIDUX_BROWSER_PORT or 7191.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind. Defaults to env VIDUX_BROWSER_HOST or 127.0.0.1. "
             "Use 0.0.0.0 to expose on LAN.",
    )
    parser.add_argument(
        "--comments-path",
        type=str,
        default=None,
        help="Path to comments JSONL file. Defaults to env "
             "VIDUX_BROWSER_COMMENTS_FILE or ~/.vidux-browser/comments.jsonl.",
    )
    args = parser.parse_args(argv)

    # CLI overrides module-level globals. Re-resolve so the server uses the
    # passed values rather than the env defaults captured at import time.
    global HOST, PORT, DEV_ROOT, COMMENTS_FILE
    if args.host is not None:
        HOST = args.host
    if args.port is not None:
        PORT = args.port
    if args.root is not None:
        DEV_ROOT = Path(args.root).expanduser().resolve()
    if args.comments_path is not None:
        COMMENTS_FILE = Path(args.comments_path).expanduser()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    sys.stderr.write(f"vidux browser → {url}  (dev_root={DEV_ROOT})\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nstopped\n")
        server.server_close()


if __name__ == "__main__":
    main()
