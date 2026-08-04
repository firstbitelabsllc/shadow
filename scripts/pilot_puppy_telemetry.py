#!/usr/bin/env python3
"""Optional, metadata-only lifecycle observation for Pilot Puppy.

This module is deliberately a one-way side effect.  It is disabled unless a
local operator explicitly sets ``PILOT_PUPPY_TELEMETRY=langfuse`` and supplies
all Langfuse connection variables.  It never changes a route, host result,
receipt, exit code, or local acceptance decision.

Only the closed metadata schema below may leave the local machine.  In
particular, this adapter never sends task text or IDs, prompts, code, diffs,
files, paths, commands, host output, provider payloads, model/account data,
or credentials.  Langfuse input and output are always ``None``.
"""

from __future__ import annotations

import importlib
import os
import re
from typing import Any, Final


TELEMETRY_MODE_ENV: Final = "PILOT_PUPPY_TELEMETRY"
TELEMETRY_MODE: Final = "langfuse"
REQUIRED_ENV: Final = ("LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
SCHEMA: Final = "pilot-puppy.telemetry.v1"
EVENTS: Final = frozenset({"route_prepared", "host_finished", "drive_started", "drive_finished", "drive_accepted"})
ROLES: Final = frozenset({"lead", "planner", "dev", "debug", "review", "hard-dev"})
HOSTS: Final = frozenset({"codex", "claude-code", "cursor", "manual"})
STATES: Final = frozenset({"ready", "manual", "running", "blocked", "ok", "failed", "finished"})
DURATION_BUCKETS: Final = frozenset({"lt_1m", "1_5m", "5_15m", "gte_15m"})
ID_RE: Final = re.compile(r"^[a-z0-9]{12,64}$")


def _optional_member(value: Any, allowed: frozenset[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise ValueError("invalid telemetry metadata")
    return value


def _optional_identifier(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        raise ValueError("invalid telemetry metadata")
    return value


def _optional_lane_count(value: Any) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 3:
        raise ValueError("invalid telemetry metadata")
    return value


def _optional_path_count(value: Any) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 64:
        raise ValueError("invalid telemetry metadata")
    return value


def _optional_bool(value: Any) -> bool | None:
    if value is None or type(value) is bool:
        return value
    raise ValueError("invalid telemetry metadata")


def validate_metadata(value: object) -> dict[str, Any]:
    """Return only the exact, non-content lifecycle metadata contract."""

    fields = {
        "schema",
        "event",
        "session_id",
        "lane_id",
        "role",
        "host",
        "state",
        "duration_bucket",
        "lane_count",
        "path_count",
        "scope_ok",
        "proof_ok",
        "merge_ok",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid telemetry metadata")
    if value.get("schema") != SCHEMA:
        raise ValueError("invalid telemetry metadata")
    if not isinstance(value.get("event"), str) or value["event"] not in EVENTS:
        raise ValueError("invalid telemetry metadata")
    return {
        "schema": SCHEMA,
        "event": value["event"],
        "session_id": _optional_identifier(value["session_id"]),
        "lane_id": _optional_identifier(value["lane_id"]),
        "role": _optional_member(value["role"], ROLES),
        "host": _optional_member(value["host"], HOSTS),
        "state": _optional_member(value["state"], STATES),
        "duration_bucket": _optional_member(value["duration_bucket"], DURATION_BUCKETS),
        "lane_count": _optional_lane_count(value["lane_count"]),
        "path_count": _optional_path_count(value["path_count"]),
        "scope_ok": _optional_bool(value["scope_ok"]),
        "proof_ok": _optional_bool(value["proof_ok"]),
        "merge_ok": _optional_bool(value["merge_ok"]),
    }


def duration_bucket(value: Any) -> str | None:
    """Reduce a local duration to a non-identifying coarse bucket."""

    if type(value) not in {int, float} or value < 0:
        return None
    if value < 60:
        return "lt_1m"
    if value < 300:
        return "1_5m"
    if value < 900:
        return "5_15m"
    return "gte_15m"


def _metadata(
    *,
    event: str,
    role: str | None = None,
    host: str | None = None,
    state: str | None = None,
    duration: Any = None,
    lane_count: int | None = None,
    path_count: int | None = None,
    scope_ok: bool | None = None,
    proof_ok: bool | None = None,
    merge_ok: bool | None = None,
    session_id: str | None = None,
    lane_id: str | None = None,
) -> dict[str, Any]:
    return validate_metadata(
        {
            "schema": SCHEMA,
            "event": event,
            "session_id": session_id,
            "lane_id": lane_id,
            "role": role,
            "host": host,
            "state": state,
            "duration_bucket": duration_bucket(duration),
            "lane_count": lane_count,
            "path_count": path_count,
            "scope_ok": scope_ok,
            "proof_ok": proof_ok,
            "merge_ok": merge_ok,
        }
    )


def emit(metadata: object) -> bool:
    """Best-effort export after local evidence is safely written.

    The telemetry seam is intentionally fail-open.  Missing configuration, a
    missing optional SDK, or a remote failure returns ``False`` without output
    or an exception, so it cannot alter local product behavior.
    """

    try:
        safe_metadata = validate_metadata(metadata)
    except ValueError:
        return False
    if os.environ.get(TELEMETRY_MODE_ENV, "off").strip().lower() != TELEMETRY_MODE:
        return False
    connection = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENV}
    if any(not value for value in connection.values()):
        return False
    try:
        module = importlib.import_module("langfuse")
        client_class = getattr(module, "Langfuse")
        client = client_class(
            public_key=connection["LANGFUSE_PUBLIC_KEY"],
            secret_key=connection["LANGFUSE_SECRET_KEY"],
            base_url=connection["LANGFUSE_BASE_URL"],
            environment="local",
        )
        with client.start_as_current_observation(
            as_type="span",
            name=f"pilot-puppy.{safe_metadata['event']}",
            input=None,
            output=None,
            metadata=safe_metadata,
        ):
            pass
        client.flush()
    except Exception:
        return False
    return True


def record_route(document: dict[str, Any]) -> bool:
    """Observe a persisted route without passing route bindings or task data."""

    selection = document.get("selection")
    return emit(
        _metadata(
            event="route_prepared",
            role=selection.get("role") if isinstance(selection, dict) else None,
            host=selection.get("host") if isinstance(selection, dict) else None,
            state=document.get("status"),
            lane_count=1,
            path_count=0,
        )
    )


def _host_result_flags(payload: dict[str, Any]) -> tuple[bool | None, bool | None]:
    status = payload.get("status")
    blocked = payload.get("blocked")
    kind = blocked.get("kind") if isinstance(blocked, dict) else None
    if status == "ok":
        return True, True
    if kind in {"scope_violation", "worktree_unsealed"}:
        return False, None
    if kind in {"proof_missing", "host_receipt_invalid", "host_receipt_missing"}:
        return None, False
    return None, None


def record_host(payload: dict[str, Any], *, allowed_path_count: int) -> bool:
    """Observe a persisted host result without passing its receipt contents."""

    route = payload.get("route")
    scope_ok, proof_ok = _host_result_flags(payload)
    return emit(
        _metadata(
            event="host_finished",
            role=route.get("role") if isinstance(route, dict) else None,
            host=payload.get("host"),
            state=payload.get("status"),
            duration=payload.get("duration_s"),
            lane_count=1,
            path_count=allowed_path_count,
            scope_ok=scope_ok,
            proof_ok=proof_ok,
        )
    )


def record_drive(
    *,
    event: str,
    session_id: str,
    lane_id: str | None,
    role: str | None,
    host: str | None,
    state: str,
    duration: Any,
    lane_count: int,
    path_count: int | None,
    scope_ok: bool | None,
    proof_ok: bool | None,
    merge_ok: bool | None,
) -> bool:
    """Observe a locally persisted Drive lifecycle transition, never its work."""

    return emit(
        _metadata(
            event=event,
            session_id=session_id,
            lane_id=lane_id,
            role=role,
            host=host,
            state=state,
            duration=duration,
            lane_count=lane_count,
            path_count=path_count,
            scope_ok=scope_ok,
            proof_ok=proof_ok,
            merge_ok=merge_ok,
        )
    )
