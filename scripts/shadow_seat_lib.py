#!/usr/bin/env python3
"""Safe owner-local selectors for one already-declared Shadow seat.

The public roster deliberately names only generic roles and native host
surfaces.  This separate, owner-only overlay can bind an existing non-manual
slot to one native CLI selector after a route has chosen that slot.  It is not
a provider registry, account store, pricing database, command template, or
credential store.  It is never read by browse, status, route, plans, or task
evidence.

``SHADOW_SEATS_FILE`` and ``--file`` are explicit local overrides.  As
with the roster, symlinked parents, non-regular files, and group/world-readable
configuration are refused instead of followed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Final

from shadow_roster_lib import (
    HOSTS,
    MAX_REVISION,
    RosterError,
    _read_bounded,
    _sync_directory,
    _walk_safe_parent,
    lexical_absolute,
    load_roster,
    validate_roster,
)


SEAT_SCHEMA: Final = "shadow.seat-overlay.v1"
SEAT_VIEW_SCHEMA: Final = "shadow.seat-overlay-view.v1"
MAX_SEATS: Final = 12
# root → seats → seat → selector → scalar is the intended deepest shape.
MAX_JSON_DEPTH: Final = 5
MAX_SEAT_BYTES: Final = 32 * 1024
_SLOT_RE: Final = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_SELECTOR_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+,=\[\]-]{0,127}$")
_SECRET_WORDS: Final = ("api_key", "apikey", "token", "secret", "password", "credential", "bearer")

DEFAULT_SEAT_OVERLAY: Final[dict[str, Any]] = {
    "schema": SEAT_SCHEMA,
    "revision": 1,
    "seats": [],
}


class SeatError(ValueError):
    """A local seat configuration failure safe to collapse at a CLI boundary."""


class SeatExistsError(SeatError):
    """The caller asked to create a seat overlay that already exists."""


def default_seat_path() -> Path:
    """Return the lexical default path without resolving or displaying it."""

    override = os.environ.get("SHADOW_SEATS_FILE")
    if override:
        return lexical_absolute(Path(override))
    current = lexical_absolute(Path.home() / ".config" / "shadow" / "seats.json")
    if not current.exists():
        legacy = lexical_absolute(Path.home() / ".config" / "pilot-puppy" / "seats.json")
        if legacy.exists():
            return legacy
    return current


def configuration_path(value: str | Path | None = None) -> Path:
    """Return one trusted explicit local configuration location."""

    return default_seat_path() if value is None else lexical_absolute(Path(value))


def _seat_error() -> SeatError:
    return SeatError("local seat configuration is unavailable or unsafe")


def _safe_config_path(value: str | Path | None, *, create_parent: bool) -> Path:
    path = configuration_path(value)
    try:
        _walk_safe_parent(path, create=create_parent)
    except RosterError:
        raise _seat_error() from None
    return path


def _read_private(path: Path) -> bytes:
    try:
        raw = _read_bounded(path)
    except RosterError:
        raise _seat_error() from None
    if len(raw) > MAX_SEAT_BYTES:
        raise SeatError("local seat configuration is too large")
    return raw


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SeatError("local seat configuration has duplicate fields")
        result[key] = value
    return result


def _check_json_depth(value: object, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        raise SeatError("local seat configuration is too deeply nested")
    if isinstance(value, dict):
        for child in value.values():
            _check_json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_json_depth(child, depth + 1)


def _exact_object(value: object, fields: set[str], noun: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise SeatError(f"local seat configuration has an invalid {noun}")
    return value


def _selector(value: object, host: str) -> dict[str, str]:
    selector = _exact_object(value, {"kind", "value"}, "selector")
    kind = selector["kind"]
    selected = selector["value"]
    if kind not in {"model", "profile"}:
        raise SeatError("local seat selector kind is invalid")
    if kind == "profile" and host != "codex":
        raise SeatError("local seat selector is unsupported for this host")
    if not isinstance(selected, str) or _SELECTOR_RE.fullmatch(selected) is None:
        raise SeatError("local seat selector value is invalid")
    lowered = selected.lower()
    if any(word in lowered for word in _SECRET_WORDS):
        raise SeatError("local seat selector value is invalid")
    return {"kind": kind, "value": selected}


def validate_seat_overlay(value: object) -> dict[str, Any]:
    """Validate a bounded overlay independent of one current roster snapshot."""

    _check_json_depth(value)
    root = _exact_object(value, {"schema", "revision", "seats"}, "root object")
    if root["schema"] not in (SEAT_SCHEMA, "pilot-puppy.seats.v1"):
        raise SeatError("local seat schema is unsupported")
    revision = root["revision"]
    if type(revision) is not int or not (1 <= revision <= MAX_REVISION):
        raise SeatError("local seat revision is invalid")
    seats = root["seats"]
    if not isinstance(seats, list) or len(seats) > MAX_SEATS:
        raise SeatError("local seat entries are invalid")
    safe_seats: list[dict[str, Any]] = []
    seen_slots: set[str] = set()
    for value in seats:
        seat = _exact_object(value, {"slot", "host", "selector"}, "seat")
        slot = seat["slot"]
        host = seat["host"]
        if not isinstance(slot, str) or _SLOT_RE.fullmatch(slot) is None:
            raise SeatError("local seat slot is invalid")
        if slot in seen_slots:
            raise SeatError("local seat configuration maps a slot more than once")
        if not isinstance(host, str) or host not in HOSTS or host == "manual":
            raise SeatError("local seat host is invalid")
        safe_seats.append({"slot": slot, "host": host, "selector": _selector(seat["selector"], host)})
        seen_slots.add(slot)
    return {"schema": SEAT_SCHEMA, "revision": revision, "seats": safe_seats}


def canonical_seat_bytes(value: object) -> bytes:
    safe = validate_seat_overlay(value)
    return json.dumps(safe, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def load_seat_overlay(value: str | Path | None = None) -> dict[str, Any]:
    """Load one private overlay without ever retaining its configuration path."""

    path = _safe_config_path(value, create_parent=False)
    raw = _read_private(path)
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, SeatError):
        raise SeatError("local seat configuration is invalid") from None
    return validate_seat_overlay(parsed)


def _replace_private_overlay(path: Path, overlay: object) -> None:
    safe = validate_seat_overlay(overlay)
    try:
        parent = _walk_safe_parent(path, create=False)
        os.chmod(parent, 0o700)
        information = os.lstat(path)
    except (OSError, RosterError):
        raise _seat_error() from None
    if (
        stat.S_ISLNK(information.st_mode)
        or not stat.S_ISREG(information.st_mode)
        or stat.S_IMODE(information.st_mode) & 0o077
    ):
        raise _seat_error()

    descriptor, temporary_name = tempfile.mkstemp(prefix=".seats-", dir=parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_seat_bytes(safe) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            current = os.lstat(path)
        except OSError:
            raise _seat_error() from None
        if (
            stat.S_ISLNK(current.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or stat.S_IMODE(current.st_mode) & 0o077
        ):
            raise _seat_error()
        try:
            os.replace(temporary_path, path)
        except OSError:
            raise _seat_error() from None
        _sync_directory(parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def initialize_seat_overlay(value: str | Path | None = None) -> dict[str, Any]:
    """Atomically create an empty private overlay without overwriting one."""

    path = _safe_config_path(value, create_parent=True)
    parent = path.parent
    try:
        os.chmod(parent, 0o700)
        information = os.lstat(path)
    except FileNotFoundError:
        information = None
    except OSError:
        raise _seat_error() from None
    if information is not None:
        if stat.S_ISLNK(information.st_mode):
            raise _seat_error()
        raise SeatExistsError("local seat configuration already exists")

    descriptor, temporary_name = tempfile.mkstemp(prefix=".seats-", dir=parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_seat_bytes(DEFAULT_SEAT_OVERLAY) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            raise SeatExistsError("local seat configuration already exists") from None
        _sync_directory(parent)
    finally:
        temporary_path.unlink(missing_ok=True)
    return validate_seat_overlay(DEFAULT_SEAT_OVERLAY)


def validate_overlay_against_roster(overlay: object, roster: object) -> dict[str, Any]:
    """Reject stale or unsafe mappings against one already-loaded roster snapshot."""

    safe_overlay = validate_seat_overlay(overlay)
    safe_roster = validate_roster(roster)
    slots = {slot["id"]: slot for slot in safe_roster["slots"]}
    for seat in safe_overlay["seats"]:
        slot = slots.get(seat["slot"])
        if slot is None or not slot["enabled"] or slot["host"] == "manual":
            raise SeatError("local seat mapping is not an enabled declared native slot")
        if slot["host"] != seat["host"]:
            raise SeatError("local seat mapping does not match its declared host")
    return safe_overlay


def set_seat_selector(
    slot_id: str,
    selector_kind: str,
    selector_value: str,
    *,
    overlay_path: str | Path | None = None,
    roster_path: str | Path | None = None,
) -> dict[str, Any]:
    """Bind one existing enabled native roster slot to one safe local selector."""

    if not isinstance(slot_id, str) or _SLOT_RE.fullmatch(slot_id) is None:
        raise SeatError("local seat slot is invalid")
    roster = load_roster(roster_path)
    slots = {slot["id"]: slot for slot in roster["slots"]}
    slot = slots.get(slot_id)
    if slot is None or not slot["enabled"] or slot["host"] == "manual":
        raise SeatError("local seat slot is not an enabled declared native slot")
    selector = _selector({"kind": selector_kind, "value": selector_value}, slot["host"])
    path = _safe_config_path(overlay_path, create_parent=False)
    current = validate_overlay_against_roster(load_seat_overlay(path), roster)
    existing = {seat["slot"]: seat for seat in current["seats"]}
    requested = {"slot": slot_id, "host": slot["host"], "selector": selector}
    if existing.get(slot_id) == requested:
        return current
    if current["revision"] >= MAX_REVISION:
        raise SeatError("local seat revision is exhausted")
    seats = [requested if seat["slot"] == slot_id else seat for seat in current["seats"]]
    if slot_id not in existing:
        seats.append(requested)
    updated = validate_seat_overlay(
        {"schema": SEAT_SCHEMA, "revision": current["revision"] + 1, "seats": seats}
    )
    validate_overlay_against_roster(updated, roster)
    _replace_private_overlay(path, updated)
    return updated


def selector_for_route(
    overlay: object, roster: object, slot_id: str, expected_host: str
) -> dict[str, str]:
    """Return exactly one safe selector for a route-selected local slot."""

    safe_overlay = validate_overlay_against_roster(overlay, roster)
    safe_roster = validate_roster(roster)
    slots = {slot["id"]: slot for slot in safe_roster["slots"]}
    slot = slots.get(slot_id)
    if slot is None or not slot["enabled"] or slot["host"] != expected_host or expected_host == "manual":
        raise SeatError("local seat route does not match an enabled native slot")
    matches = [seat for seat in safe_overlay["seats"] if seat["slot"] == slot_id]
    if len(matches) != 1 or matches[0]["host"] != expected_host:
        raise SeatError("local seat selector is not configured for the selected route")
    return dict(matches[0]["selector"])


def seat_view(overlay: object, roster: object | None = None) -> dict[str, Any]:
    """Return the explicit owner-local view with no source path or project data.

    An empty overlay may be initialized before a roster exists.  Any configured
    mapping still requires the current roster, so a stale selector never gets a
    free-standing display or execution path.
    """

    safe = validate_seat_overlay(overlay)
    if roster is not None:
        safe = validate_overlay_against_roster(safe, roster)
    elif safe["seats"]:
        raise SeatError("local seat mappings require a current local roster")
    return {"schema": SEAT_VIEW_SCHEMA, "overlay": safe}
