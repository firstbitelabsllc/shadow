#!/usr/bin/env python3
"""Safe local roster primitives for Pilot Puppy.

This module stores only a small, provider-neutral list of role/host slots.  It
does not store model names, accounts, credentials, prompts, provider payloads,
or machine paths. A later foreground router can consume ``load_roster`` and a
route-safe fingerprint without learning where the local configuration lives or
publishing local slot identifiers.

``PILOT_PUPPY_ROSTER_FILE`` and the CLI ``--file`` flag are deliberately
trusted, explicit local overrides.  The default lives under the current user's
configuration directory.  Every existing directory from the filesystem root
through the immediate configuration parent is checked with ``lstat`` and a
symlink anywhere in that chain is refused.  Missing configuration directories
are created as private directories.  This is intentionally stricter than
silently following a user-controlled symlink.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Final


ROSTER_SCHEMA: Final = "pilot-puppy.roster.v1"
ROSTER_VIEW_SCHEMA: Final = "pilot-puppy.roster-view.v1"
ROSTER_FINGERPRINT_SCHEMA: Final = "pilot-puppy.roster-fingerprint.v1"
ROLES: Final = ("lead", "planner", "bulk", "debug", "critic", "hard-ic")
HOSTS: Final = ("codex", "claude-code", "cursor", "manual")
MAX_ROSTER_BYTES: Final = 32 * 1024
MAX_SLOTS: Final = 12
MAX_JSON_DEPTH: Final = 4
MAX_REVISION: Final = 2_147_483_647
MAX_PRIORITY: Final = 1_000
_ID_MIN_LENGTH: Final = 3
_ID_MAX_LENGTH: Final = 64

DEFAULT_ROSTER: Final[dict[str, Any]] = {
    "schema": ROSTER_SCHEMA,
    "revision": 1,
    "slots": [
        {"id": "lead-local", "role": "lead", "host": "manual", "priority": 1, "enabled": True},
        {"id": "planner-local", "role": "planner", "host": "manual", "priority": 1, "enabled": True},
        {"id": "bulk-cursor", "role": "bulk", "host": "cursor", "priority": 1, "enabled": True},
        {"id": "bulk-codex", "role": "bulk", "host": "codex", "priority": 2, "enabled": True},
        {"id": "debug-codex", "role": "debug", "host": "codex", "priority": 1, "enabled": True},
        {"id": "critic-local", "role": "critic", "host": "manual", "priority": 1, "enabled": True},
        {"id": "hard-ic-claude", "role": "hard-ic", "host": "claude-code", "priority": 1, "enabled": True},
    ],
}


class RosterError(ValueError):
    """A safe, public-facing local roster failure."""


class RosterExistsError(RosterError):
    """The caller asked to create a roster that already exists."""


def default_roster_path() -> Path:
    """Return the lexical default path without resolving or exposing it."""

    override = os.environ.get("PILOT_PUPPY_ROSTER_FILE")
    if override:
        return lexical_absolute(Path(override))
    return lexical_absolute(Path.home() / ".config" / "pilot-puppy" / "roster.json")


def configuration_path(value: str | Path | None = None) -> Path:
    """Return a lexical configuration path from a trusted explicit override."""

    if value is None:
        return default_roster_path()
    return lexical_absolute(Path(value))


def lexical_absolute(path: Path) -> Path:
    """Make ``path`` absolute without following symlinks."""

    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _is_safe_identifier(value: object) -> bool:
    if not isinstance(value, str) or not (_ID_MIN_LENGTH <= len(value) <= _ID_MAX_LENGTH):
        return False
    if not ("a" <= value[0] <= "z"):
        return False
    return all(
        ("a" <= character <= "z") or ("0" <= character <= "9") or character == "-" for character in value
    )


def _check_json_depth(value: object, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        raise RosterError("local roster structure is too deeply nested")
    if isinstance(value, dict):
        for child in value.values():
            _check_json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_json_depth(child, depth + 1)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RosterError("local roster has duplicate fields")
        result[key] = value
    return result


def _expect_exact_fields(value: object, expected: set[str], noun: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise RosterError(f"local roster has an invalid {noun}")
    return value


def validate_roster(value: object) -> dict[str, Any]:
    """Validate one bounded roster and return a safe detached copy.

    Each role has unique priorities so a future deterministic route can select
    an enabled slot without adding provider data that does not belong here.
    """

    _check_json_depth(value)
    roster = _expect_exact_fields(value, {"schema", "revision", "slots"}, "root object")
    if roster["schema"] != ROSTER_SCHEMA:
        raise RosterError("local roster schema is unsupported")
    revision = roster["revision"]
    if type(revision) is not int or not (1 <= revision <= MAX_REVISION):
        raise RosterError("local roster revision is invalid")
    slots = roster["slots"]
    if not isinstance(slots, list) or not (1 <= len(slots) <= MAX_SLOTS):
        raise RosterError("local roster slots are invalid")

    seen_ids: set[str] = set()
    seen_role_priorities: set[tuple[str, int]] = set()
    safe_slots: list[dict[str, Any]] = []
    for slot in slots:
        record = _expect_exact_fields(slot, {"id", "role", "host", "priority", "enabled"}, "slot")
        identifier = record["id"]
        role = record["role"]
        host = record["host"]
        priority = record["priority"]
        enabled = record["enabled"]
        if not _is_safe_identifier(identifier):
            raise RosterError("local roster slot identifier is invalid")
        if not isinstance(role, str) or role not in ROLES:
            raise RosterError("local roster slot role is invalid")
        if not isinstance(host, str) or host not in HOSTS:
            raise RosterError("local roster slot host is invalid")
        if type(priority) is not int or not (1 <= priority <= MAX_PRIORITY):
            raise RosterError("local roster slot priority is invalid")
        if type(enabled) is not bool:
            raise RosterError("local roster slot enabled state is invalid")
        if identifier in seen_ids or (role, priority) in seen_role_priorities:
            raise RosterError("local roster has ambiguous slots")
        seen_ids.add(identifier)
        seen_role_priorities.add((role, priority))
        safe_slots.append(
            {"id": identifier, "role": role, "host": host, "priority": priority, "enabled": enabled}
        )

    return {"schema": ROSTER_SCHEMA, "revision": revision, "slots": safe_slots}


def canonical_roster_bytes(roster: object) -> bytes:
    """Return the exact canonical bytes used for a roster fingerprint."""

    safe = validate_roster(roster)
    return json.dumps(safe, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def roster_sha256(roster: object) -> str:
    """Return the canonical roster content hash for a later route receipt."""

    return hashlib.sha256(canonical_roster_bytes(roster)).hexdigest()


def route_roster_projection(roster: object) -> dict[str, Any]:
    """Return the route-relevant roster projection without local slot IDs.

    Slot IDs are intentionally local display/configuration text and may carry
    a personal seat nickname. They cannot affect selection because priorities
    are unique within a role, so evidence binds only the fields that can
    actually change routing.
    """

    safe = validate_roster(roster)
    slots = [
        {
            "role": slot["role"],
            "host": slot["host"],
            "priority": slot["priority"],
            "enabled": slot["enabled"],
        }
        for slot in safe["slots"]
    ]
    return {
        "revision": safe["revision"],
        "slots": sorted(slots, key=lambda slot: (slot["role"], slot["priority"], slot["host"])),
    }


def route_roster_sha256(roster: object) -> str:
    """Return a route binding hash that cannot reveal local slot identifiers."""

    projection = route_roster_projection(roster)
    encoded = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def roster_fingerprint(roster: object) -> dict[str, Any]:
    """Return a path-free content/revision reference for a later route receipt."""

    safe = validate_roster(roster)
    return {
        "schema": ROSTER_FINGERPRINT_SCHEMA,
        "revision": safe["revision"],
        "sha256": roster_sha256(safe),
    }


def roster_view(roster: object) -> dict[str, Any]:
    """Return the bounded local display projection; never include config paths."""

    safe = validate_roster(roster)
    return {
        "schema": ROSTER_VIEW_SCHEMA,
        "roster": safe,
        "fingerprint": roster_fingerprint(safe),
    }


def _walk_safe_parent(path: Path, *, create: bool) -> Path:
    """Refuse symlink ancestors and optionally create a private parent chain."""

    if not path.is_absolute():  # ``configuration_path`` always makes it absolute.
        raise RosterError("local roster configuration is unsafe")
    parent = path.parent
    current = Path(path.anchor)
    parts = parent.parts
    start = 1 if path.anchor else 0
    for part in parts[start:]:
        current = current / part
        try:
            information = os.lstat(current)
        except FileNotFoundError:
            if not create:
                raise RosterError("local roster configuration is unavailable") from None
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
            try:
                information = os.lstat(current)
            except OSError:
                raise RosterError("local roster configuration is unsafe") from None
        except OSError:
            raise RosterError("local roster configuration is unavailable") from None
        if stat.S_ISLNK(information.st_mode) or not stat.S_ISDIR(information.st_mode):
            raise RosterError("local roster configuration is unsafe")
    return parent


def _safe_config_path(value: str | Path | None, *, create_parent: bool) -> Path:
    path = configuration_path(value)
    _walk_safe_parent(path, create=create_parent)
    return path


def _read_bounded(path: Path) -> bytes:
    try:
        link_information = os.lstat(path)
    except FileNotFoundError:
        raise RosterError("local roster configuration is unavailable") from None
    except OSError:
        raise RosterError("local roster configuration is unavailable") from None
    if stat.S_ISLNK(link_information.st_mode):
        raise RosterError("local roster configuration is unsafe")

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise RosterError("local roster configuration is unavailable") from None
    try:
        information = os.fstat(descriptor)
        if not stat.S_ISREG(information.st_mode):
            raise RosterError("local roster configuration is unsafe")
        if stat.S_IMODE(information.st_mode) & 0o077:
            raise RosterError("local roster configuration must not be group or world readable")
        if information.st_size > MAX_ROSTER_BYTES:
            raise RosterError("local roster configuration is too large")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_ROSTER_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_ROSTER_BYTES:
                raise RosterError("local roster configuration is too large")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def load_roster(value: str | Path | None = None) -> dict[str, Any]:
    """Load, bound, parse, and validate one local roster without revealing its path."""

    path = _safe_config_path(value, create_parent=False)
    raw = _read_bounded(path)
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, RosterError):
        raise RosterError("local roster configuration is invalid") from None
    return validate_roster(parsed)


def _sync_directory(parent: Path) -> None:
    try:
        descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def initialize_roster(value: str | Path | None = None) -> dict[str, Any]:
    """Atomically create the default local roster, refusing every overwrite."""

    path = _safe_config_path(value, create_parent=True)
    parent = path.parent
    try:
        os.chmod(parent, 0o700)
        information = os.lstat(path)
    except FileNotFoundError:
        information = None
    except OSError:
        raise RosterError("local roster configuration is unsafe") from None
    if information is not None:
        if stat.S_ISLNK(information.st_mode):
            raise RosterError("local roster configuration is unsafe")
        raise RosterExistsError("local roster already exists")

    serialized = canonical_roster_bytes(DEFAULT_ROSTER) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".roster-", dir=parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            raise RosterExistsError("local roster already exists") from None
        _sync_directory(parent)
    finally:
        temporary_path.unlink(missing_ok=True)
    return validate_roster(DEFAULT_ROSTER)
