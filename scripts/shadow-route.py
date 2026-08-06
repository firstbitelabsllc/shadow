#!/usr/bin/env python3
"""Resolve one local work role without launching a coding host.

This foreground command deliberately makes no provider, account, model, or
quota claim. It reads a bounded local roster, chooses one declared role/host
surface deterministically, and can write a small route packet that a later
sealed host handoff may verify. It never starts a host, creates a worktree,
contacts a network service, or owns a queue.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from shadow_roster_lib import (  # type: ignore[import-not-found]
    RosterError,
    canonical_role,
    default_roster_path,
    load_roster,
    route_roster_sha256,
    validate_roster,
)
from shadow_route_lib import (  # type: ignore[import-not-found]
    HOSTS,
    ROLE_INPUTS as ROUTE_ROLE_INPUTS,
    ROUTE_SCHEMA,
    TASK_KIND_ROLES,
    RoutePacketError,
    validate_route_packet,
)
from shadow_task_lib import TaskError, frozen_task_sha256  # type: ignore[import-not-found]
import shadow_telemetry as telemetry  # type: ignore[import-not-found]


ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_PROBE_CACHE: dict[str, bool] = {}


class RouteError(ValueError):
    """A route input or local output did not meet the bounded contract."""


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        raise RouteError(f"{label} must be a public identifier")
    return value


def exact_git_root(value: Path) -> Path:
    """Return one existing worktree root without exposing its private path."""

    candidate = value.expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise RouteError("repo must be a regular Git worktree root")
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RouteError("repo is not a readable Git worktree root") from exc
    if result.returncode:
        raise RouteError("repo is not a readable Git worktree root")
    try:
        root = Path(result.stdout.strip()).resolve(strict=True)
    except OSError as exc:
        raise RouteError("repo is not a readable Git worktree root") from exc
    if root != candidate.resolve():
        raise RouteError("repo must be an exact Git worktree root")
    return root


def probe_host(host: str) -> bool:
    """Perform the same local, bounded version probe concept as host probe.

    Output, binary paths, and errors are intentionally discarded: availability
    is a local hint, not host authentication or provider-account proof.
    """

    if host == "manual":
        return False
    if host in _PROBE_CACHE:
        return _PROBE_CACHE[host]
    configured = os.environ.get(f"SHADOW_{host.upper().replace('-', '_')}_BIN")
    if configured:
        supplied = Path(configured).expanduser()
        binary = str(supplied) if "/" in configured else shutil.which(configured)
        if binary is None or not supplied.is_file() and "/" in configured:
            _PROBE_CACHE[host] = False
            return False
    else:
        binary = shutil.which({"claude-code": "claude", "cursor": "cursor-agent"}.get(host, host))
    if not binary:
        _PROBE_CACHE[host] = False
        return False
    try:
        result = subprocess.run(
            [binary, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        _PROBE_CACHE[host] = False
        return False
    _PROBE_CACHE[host] = result.returncode == 0
    return _PROBE_CACHE[host]


def slot_state(slot: dict[str, Any], availability: str) -> str:
    if not slot["enabled"]:
        return "disabled"
    if slot["host"] == "manual":
        return "manual"
    if availability == "assume":
        return "unprobed"
    return "available" if probe_host(slot["host"]) else "unavailable"


def compact_slot(slot: dict[str, Any], state: str, reason: str) -> dict[str, str]:
    return {
        "role": slot["role"],
        "host": slot["host"],
        "state": state,
        "reason": reason,
    }


def select_slot(
    slots: list[dict[str, Any]], *, role: str, host: str | None, availability: str
) -> tuple[dict[str, Any] | None, str | None, list[dict[str, str]], str | None]:
    """Choose only among same-role slots and expose every same-role fallback."""

    role_slots = [slot for slot in slots if slot["role"] == role]
    constrained = [slot for slot in role_slots if host is None or slot["host"] == host]
    if not constrained:
        return None, None, [], "no_declared_slot"

    evaluated = [(slot, slot_state(slot, availability)) for slot in constrained]
    selected: tuple[dict[str, Any], str] | None = None
    for candidate in evaluated:
        if candidate[1] in {"available", "unprobed", "manual"}:
            selected = candidate
            break
    alternatives: list[dict[str, str]] = []
    for slot, state in evaluated:
        if selected is not None and slot["id"] == selected[0]["id"]:
            continue
        reason = "lower_roster_priority" if state in {"available", "unprobed", "manual"} else state
        alternatives.append(compact_slot(slot, state, reason))
    if selected is None:
        return None, None, alternatives, "no_available_slot"
    return selected[0], selected[1], alternatives, None


def route_document(
    *,
    task_id: str,
    task_hash: str,
    roster: dict[str, Any],
    task_kind: str | None,
    role: str,
    host: str | None,
    availability: str,
) -> dict[str, Any]:
    safe_roster = validate_roster(roster)
    role = canonical_role(role)
    slots = sorted(safe_roster["slots"], key=lambda slot: (slot["priority"], slot["id"]))
    slot, state, alternatives, blocked_kind = select_slot(
        slots, role=role, host=host, availability=availability
    )
    binding = {
        "task_id": task_id,
        "task_sha256": task_hash,
        "roster_revision": safe_roster["revision"],
        "route_roster_sha256": route_roster_sha256(safe_roster),
    }
    requested = {
        "task_kind": task_kind,
        "role": role,
        "host": host,
        "availability": availability,
    }
    escalation = {
        "role": "hard-dev" if role != "hard-dev" else "lead",
        "when": "Create a new explicit route only when the declared packet is exceeded or bounded proof fails twice.",
    }
    if slot is None:
        document = {
            "schema": ROUTE_SCHEMA,
            "revision": 1,
            "status": "blocked",
            "binding": binding,
            "requested": requested,
            "selection": None,
            "alternatives": alternatives,
            "escalation": escalation,
            "execution": {
                "performed": False,
                "automatic_reroute": False,
                "next_action": "choose_or_configure_a_same_role_slot",
            },
            "blocked": {"kind": blocked_kind, "summary": "No eligible declared local slot is available."},
        }
        return validate_route_packet(document)
    selection = {
        "role": slot["role"],
        "host": slot["host"],
        "priority": slot["priority"],
        "state": state,
        "reason": "explicit_host_constraint" if host is not None else "highest_enabled_priority",
    }
    if state == "manual":
        status = "manual"
        next_action = "lead_manual_handoff"
    else:
        status = "ready"
        next_action = "explicit_host_run"
    document = {
        "schema": ROUTE_SCHEMA,
        "revision": 1,
        "status": status,
        "binding": binding,
        "requested": requested,
        "selection": selection,
        "alternatives": alternatives,
        "escalation": escalation,
        "execution": {
            "performed": False,
            "automatic_reroute": False,
            "next_action": next_action,
        },
        "blocked": None,
    }
    return validate_route_packet(document)


def output_path(repo: Path, raw: str) -> Path | None:
    if raw == "-":
        return None
    target = (repo / raw).resolve(strict=False) if not Path(raw).is_absolute() else Path(raw).resolve(strict=False)
    evidence = repo / ".shadow" / "evidence"
    if evidence.is_symlink() or (repo / ".shadow").is_symlink():
        raise RouteError("project evidence path must not be a symlink")
    try:
        target.relative_to(evidence)
    except ValueError as exc:
        raise RouteError("route output must stay inside project evidence") from exc
    if target.parent != evidence or target.suffix != ".json" or target.name == ".json":
        raise RouteError("route output must be one JSON file directly inside project evidence")
    if target.exists() or target.is_symlink():
        raise FileExistsError
    return target


def write_exclusive(path: Path, document: dict[str, Any]) -> None:
    state = path.parent.parent
    if (state.exists() and not state.is_dir()) or state.is_symlink():
        raise RouteError("project evidence state must be a regular directory")
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise RouteError("project evidence directory must be a regular directory")
    state.mkdir(exist_ok=True, mode=0o700)
    path.parent.mkdir(exist_ok=True, mode=0o700)
    if path.exists() or path.is_symlink():
        raise FileExistsError
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=".route.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            raise FileExistsError from None
    finally:
        temporary_path.unlink(missing_ok=True)


def render(document: dict[str, Any]) -> str:
    selection = document["selection"]
    alternatives = document["alternatives"]
    alternatives_text = "none" if not alternatives else "; ".join(
        f"{item['role']} via {item['host']} ({item['state']}; {item['reason']})"
        for item in alternatives
    )
    escalation = document["escalation"]
    if selection is None:
        return (
            "Shadow route blocked: no eligible declared local slot.\n"
            f"Alternatives: {alternatives_text}.\n"
            f"Escalate: {escalation['role']} when {escalation['when']}\n"
            f"Next: {document['execution']['next_action']}.\n"
        )
    line = (
        f"Shadow route: {selection['role']} via {selection['host']} "
        f"({selection['state']}; {selection['reason']})"
    )
    return (
        f"{line}\n"
        f"Reason: explicit {document['requested']['task_kind'] or 'role'} route; no work was launched.\n"
        f"Alternatives: {alternatives_text}.\n"
        f"Escalate: {escalation['role']} when {escalation['when']}\n"
        f"Next: {document['execution']['next_action']}.\n"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="shadow route",
        description="Resolve one declared local role without starting a coding host.",
    )
    result.add_argument("--repo", required=True, type=Path, help="exact Git worktree root")
    result.add_argument("--task-id", required=True, help="public bounded task identifier")
    result.add_argument("--task-file", required=True, type=Path, help="frozen task file")
    choice = result.add_mutually_exclusive_group(required=True)
    choice.add_argument("--task-kind", choices=sorted(TASK_KIND_ROLES), help="declared task shape")
    choice.add_argument("--role", choices=sorted(ROUTE_ROLE_INPUTS), help="explicit role override")
    result.add_argument("--host", choices=sorted(HOSTS), help="hard same-role host constraint")
    result.add_argument(
        "--roster-file", type=Path, default=default_roster_path(), help="trusted local roster override"
    )
    result.add_argument(
        "--availability", choices=("probe", "assume"), default="probe", help="local host availability mode"
    )
    result.add_argument(
        "--out", default="-", help="one new .shadow/evidence JSON path, or '-' for no file"
    )
    result.add_argument("--json", action="store_true", help="print the bounded route JSON")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repo = exact_git_root(args.repo)
        task_id = identifier(args.task_id, "task_id")
        _, task_hash = frozen_task_sha256(args.task_file)
        roster = load_roster(args.roster_file.expanduser())
        role = args.role or TASK_KIND_ROLES[args.task_kind]
        document = route_document(
            task_id=task_id,
            task_hash=task_hash,
            roster=roster,
            task_kind=args.task_kind,
            role=role,
            host=args.host,
            availability=args.availability,
        )
        destination = output_path(repo, args.out)
        if destination is not None:
            write_exclusive(destination, document)
            telemetry.record_route(document)
        if args.json:
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(render(document), end="")
        return 0 if document["status"] != "blocked" else 1
    except FileExistsError:
        print("shadow route: route output already exists; refusing to overwrite", file=sys.stderr)
        return 1
    except (OSError, RosterError, RouteError, RoutePacketError, TaskError):
        print("shadow route: local route could not be resolved safely", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
