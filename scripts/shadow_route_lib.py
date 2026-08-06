#!/usr/bin/env python3
"""Strict, path-free validation for one non-executing Shadow route packet."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Final


ROUTE_SCHEMA: Final = "shadow.route.v1"
ROUTE_REVISION: Final = 1
MAX_ROUTE_BYTES: Final = 32 * 1024
MAX_ALTERNATIVES: Final = 12
MAX_PRIORITY: Final = 1_000
ROLES: Final = frozenset({"lead", "planner", "dev", "debug", "review", "hard-dev"})
LEGACY_ROLE_ALIASES: Final = {"bulk": "dev", "critic": "review", "hard-ic": "hard-dev"}
ROLE_INPUTS: Final = frozenset((*ROLES, *LEGACY_ROLE_ALIASES))
HOSTS: Final = frozenset({"codex", "claude-code", "cursor", "manual"})
TASK_KINDS: Final = frozenset({"plan", "hard-dev", "dev", "debug", "review", "lead"})
TASK_KIND_ROLES: Final = {
    "plan": "planner",
    "hard-dev": "hard-dev",
    "dev": "dev",
    "debug": "debug",
    "review": "review",
    "lead": "lead",
}
AVAILABILITY: Final = frozenset({"probe", "assume"})
SELECTION_STATES: Final = frozenset({"available", "unprobed", "manual"})
ALTERNATIVE_STATES: Final = SELECTION_STATES | {"disabled", "unavailable"}
SELECTION_REASONS: Final = frozenset({"highest_enabled_priority", "explicit_host_constraint"})
ALTERNATIVE_REASONS: Final = frozenset({"lower_roster_priority", "disabled", "unavailable"})
NEXT_ACTIONS: Final = frozenset(
    {"explicit_host_run", "lead_manual_handoff", "choose_or_configure_a_same_role_slot"}
)
BLOCKED_KINDS: Final = frozenset({"no_declared_slot", "no_available_slot"})
ID_RE: Final = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")
PRIVATE_PATH_RE: Final = re.compile(r"(?:^|[\s\"'=])(?:~/|/Users/|/home/|/private/var/|file:///)", re.IGNORECASE)
SECRET_SHAPE_RE: Final = re.compile(
    r"(?:sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


class RoutePacketError(ValueError):
    """A route packet failed its small public evidence contract."""


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RoutePacketError("route packet has duplicate fields")
        result[key] = value
    return result


def _exact_object(value: object, fields: set[str], noun: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise RoutePacketError(f"route packet has an invalid {noun}")
    return value


def _identifier(value: object, noun: str) -> str:
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        raise RoutePacketError(f"route packet {noun} is invalid")
    return value


def _sha256(value: object, noun: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise RoutePacketError(f"route packet {noun} is invalid")
    return value


def _role(value: object, noun: str) -> str:
    if not isinstance(value, str) or value not in ROLE_INPUTS:
        raise RoutePacketError(f"route packet {noun} is invalid")
    return LEGACY_ROLE_ALIASES.get(value, value)


def _host(value: object, noun: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or value not in HOSTS:
        raise RoutePacketError(f"route packet {noun} is invalid")
    return value


def _text(value: object, noun: str, maximum: int = 280) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise RoutePacketError(f"route packet {noun} is invalid")
    text = " ".join(value.split())
    if (
        CONTROL_RE.search(text)
        or PRIVATE_PATH_RE.search(text)
        or SECRET_SHAPE_RE.search(text)
        or any(ord(character) > 126 for character in text)
    ):
        raise RoutePacketError(f"route packet {noun} is invalid")
    return text


def _selection(value: object) -> dict[str, Any]:
    selection = _exact_object(value, {"role", "host", "priority", "state", "reason"}, "selection")
    state = selection["state"]
    reason = selection["reason"]
    if not isinstance(state, str) or state not in SELECTION_STATES:
        raise RoutePacketError("route packet selection state is invalid")
    if not isinstance(reason, str) or reason not in SELECTION_REASONS:
        raise RoutePacketError("route packet selection reason is invalid")
    priority = selection["priority"]
    if type(priority) is not int or not (1 <= priority <= MAX_PRIORITY):
        raise RoutePacketError("route packet selection priority is invalid")
    return {
        "role": _role(selection["role"], "selection role"),
        "host": _host(selection["host"], "selection host") or "",
        "priority": priority,
        "state": state,
        "reason": reason,
    }


def _alternative(value: object) -> dict[str, str]:
    alternative = _exact_object(value, {"role", "host", "state", "reason"}, "alternative")
    state = alternative["state"]
    reason = alternative["reason"]
    if not isinstance(state, str) or state not in ALTERNATIVE_STATES:
        raise RoutePacketError("route packet alternative state is invalid")
    if not isinstance(reason, str) or reason not in ALTERNATIVE_REASONS:
        raise RoutePacketError("route packet alternative reason is invalid")
    expected_reason = (
        "lower_roster_priority" if state in SELECTION_STATES else state
    )
    if reason != expected_reason:
        raise RoutePacketError("route packet alternative reason disagrees with state")
    return {
        "role": _role(alternative["role"], "alternative role"),
        "host": _host(alternative["host"], "alternative host") or "",
        "state": state,
        "reason": reason,
    }


def validate_route_packet(value: object) -> dict[str, Any]:
    """Validate and detach one route packet before a host can trust it."""

    root = _exact_object(
        value,
        {
            "schema",
            "revision",
            "status",
            "binding",
            "requested",
            "selection",
            "alternatives",
            "escalation",
            "execution",
            "blocked",
        },
        "root object",
    )
    if root["schema"] != ROUTE_SCHEMA or root["revision"] != ROUTE_REVISION:
        raise RoutePacketError("route packet schema is unsupported")
    status = root["status"]
    if not isinstance(status, str) or status not in {"ready", "manual", "blocked"}:
        raise RoutePacketError("route packet status is invalid")
    binding = _exact_object(
        root["binding"], {"task_id", "task_sha256", "roster_revision", "route_roster_sha256"}, "binding"
    )
    roster_revision = binding["roster_revision"]
    if type(roster_revision) is not int or roster_revision < 1:
        raise RoutePacketError("route packet roster revision is invalid")
    requested = _exact_object(root["requested"], {"task_kind", "role", "host", "availability"}, "request")
    task_kind = requested["task_kind"]
    if task_kind is not None and (not isinstance(task_kind, str) or task_kind not in TASK_KINDS):
        raise RoutePacketError("route packet task kind is invalid")
    availability = requested["availability"]
    if not isinstance(availability, str) or availability not in AVAILABILITY:
        raise RoutePacketError("route packet availability is invalid")
    requested_role = _role(requested["role"], "requested role")
    requested_host = _host(requested["host"], "requested host", nullable=True)
    if task_kind is not None and TASK_KIND_ROLES[task_kind] != requested_role:
        raise RoutePacketError("route packet task kind and role disagree")
    alternatives_value = root["alternatives"]
    if not isinstance(alternatives_value, list) or len(alternatives_value) > MAX_ALTERNATIVES:
        raise RoutePacketError("route packet alternatives are invalid")
    escalation = _exact_object(root["escalation"], {"role", "when"}, "escalation")
    execution = _exact_object(root["execution"], {"performed", "automatic_reroute", "next_action"}, "execution")
    if execution["performed"] is not False or execution["automatic_reroute"] is not False:
        raise RoutePacketError("route packet execution state is invalid")
    if not isinstance(execution["next_action"], str) or execution["next_action"] not in NEXT_ACTIONS:
        raise RoutePacketError("route packet next action is invalid")

    selection_value = root["selection"]
    blocked_value = root["blocked"]
    if status == "blocked":
        if selection_value is not None:
            raise RoutePacketError("blocked route packet must not select a slot")
        blocked = _exact_object(blocked_value, {"kind", "summary"}, "blocked state")
        if not isinstance(blocked["kind"], str) or blocked["kind"] not in BLOCKED_KINDS:
            raise RoutePacketError("route packet blocked kind is invalid")
        safe_selection = None
        safe_blocked: dict[str, str] | None = {
            "kind": blocked["kind"],
            "summary": _text(blocked["summary"], "blocked summary"),
        }
        if execution["next_action"] != "choose_or_configure_a_same_role_slot":
            raise RoutePacketError("blocked route packet next action is invalid")
    else:
        if blocked_value is not None:
            raise RoutePacketError("ready route packet must not be blocked")
        safe_selection = _selection(selection_value)
        if safe_selection["role"] != requested_role:
            raise RoutePacketError("route packet selection role disagrees with request")
        if requested_host is not None and safe_selection["host"] != requested_host:
            raise RoutePacketError("route packet selection host disagrees with request")
        if status == "manual" and safe_selection["host"] != "manual":
            raise RoutePacketError("manual route packet must select manual")
        if status == "manual" and safe_selection["state"] != "manual":
            raise RoutePacketError("manual route packet selection state is invalid")
        if status == "manual" and execution["next_action"] != "lead_manual_handoff":
            raise RoutePacketError("manual route packet next action is invalid")
        if status == "ready" and safe_selection["host"] == "manual":
            raise RoutePacketError("ready route packet must select a native host")
        if status == "ready" and safe_selection["state"] == "manual":
            raise RoutePacketError("ready route packet selection state is invalid")
        if status == "ready" and execution["next_action"] != "explicit_host_run":
            raise RoutePacketError("ready route packet next action is invalid")
        if requested_host is None and safe_selection["reason"] != "highest_enabled_priority":
            raise RoutePacketError("route packet selection reason disagrees with request")
        if requested_host is not None and safe_selection["reason"] != "explicit_host_constraint":
            raise RoutePacketError("route packet selection reason disagrees with request")
        safe_blocked = None

    safe_alternatives = [_alternative(item) for item in alternatives_value]
    if any(item["role"] != requested_role for item in safe_alternatives):
        raise RoutePacketError("route packet alternatives cross roles")

    return {
        "schema": ROUTE_SCHEMA,
        "revision": ROUTE_REVISION,
        "status": status,
        "binding": {
            "task_id": _identifier(binding["task_id"], "task id"),
            "task_sha256": _sha256(binding["task_sha256"], "task hash"),
            "roster_revision": roster_revision,
            "route_roster_sha256": _sha256(binding["route_roster_sha256"], "route roster hash"),
        },
        "requested": {
            "task_kind": task_kind,
            "role": requested_role,
            "host": requested_host,
            "availability": availability,
        },
        "selection": safe_selection,
        "alternatives": safe_alternatives,
        "escalation": {
            "role": _role(escalation["role"], "escalation role"),
            "when": _text(escalation["when"], "escalation condition"),
        },
        "execution": {
            "performed": False,
            "automatic_reroute": False,
            "next_action": execution["next_action"],
        },
        "blocked": safe_blocked,
    }


def _read_bounded(path: Path) -> bytes:
    try:
        information = os.lstat(path)
    except OSError:
        raise RoutePacketError("route packet is unavailable") from None
    if stat.S_ISLNK(information.st_mode):
        raise RoutePacketError("route packet is unsafe")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise RoutePacketError("route packet is unavailable") from None
    try:
        information = os.fstat(descriptor)
        if not stat.S_ISREG(information.st_mode):
            raise RoutePacketError("route packet is unsafe")
        if information.st_size > MAX_ROUTE_BYTES:
            raise RoutePacketError("route packet is too large")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_ROUTE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_ROUTE_BYTES:
                raise RoutePacketError("route packet is too large")
        return b"".join(chunks)
    except OSError:
        raise RoutePacketError("route packet is unavailable") from None
    finally:
        os.close(descriptor)


def load_route_packet(value: str | Path) -> dict[str, Any]:
    """Load one bounded regular route file without preserving its path."""

    raw = _read_bounded(Path(value).expanduser())
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, RoutePacketError):
        raise RoutePacketError("route packet is invalid") from None
    return validate_route_packet(parsed)


def route_sha256(value: object) -> str:
    """Return a canonical route hash without retaining source-file paths."""

    safe = validate_route_packet(value)
    encoded = json.dumps(safe, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
