#!/usr/bin/env python3
"""Closed expiring contacts for optional Huddle delivery (Plan B registration).

This module is the registration-side half of the confined Plan-B runner. It
owns the contact model only: strict structural validation, the ten-minute
maximum lease, and the exclusive single-write into the owner-local contacts
directory. It never reads the board and never opens a transport; currency of
``claim_keys`` against the live board remains the parent runner's predicate,
and the confined child re-checks it from its own atomic board re-read before
any delivery attempt.

The structural rules here deliberately mirror the shipped parent validator
``shadow_huddle_event._contact``. They are duplicated, not shared, so the
confined child depends on the smallest possible surface; a drift-guard test
in ``tests/test_huddle_planb.py`` fails the build if the two ever disagree
on the structural corpus.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
import uuid

import shadow_board_schema as board_schema

CONTACT_SCHEMA = "shadow.huddle-contact.v1"
UNSTORED_FIELDS = frozenset(
    {"schema", "instance_nonce", "provider", "capability", "endpoint", "claim_keys"})
STORED_FIELDS = frozenset(
    {"schema", "instance_nonce", "provider", "capability", "endpoint", "claim_keys",
     "seat", "registered_at", "refreshed_at", "expires_at"})
PROVIDERS = frozenset({"codex", "cmux", "grok"})
ENDPOINT_FIELDS = {
    "codex": {"thread_id", "turn_id"},
    "cmux": {"surface_uuid"},
    "grok": {"endpoint_uri"},
}
IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
CONTACT_NAME = re.compile(r"[0-9a-f-]{36}\.json\Z")
MAX_CONTACT_BYTES = 8192
LEASE = timedelta(minutes=10)


class ContactRefused(ValueError):
    """A registration request or stored contact violated the closed model."""


def utc_stamp(value: datetime) -> str:
    """Canonical second-resolution UTC stamp; the parent validator's format."""
    if not isinstance(value, datetime) or value.tzinfo != timezone.utc:
        raise ContactRefused("contact timestamps must be timezone-aware UTC")
    return value.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_canonical_utc(value: object) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        raise ContactRefused("contact timestamp is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContactRefused("contact timestamp is invalid") from exc
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise ContactRefused("contact timestamp is not canonical UTC")
    return parsed


def parse_registration(raw: bytes) -> dict:
    """Parse one bounded registration request: strict JSON, closed fields."""
    if not isinstance(raw, bytes) or not raw or len(raw) > 16 * 1024:
        raise ContactRefused("registration input must be bounded bytes")
    try:
        value = json.loads(raw, object_pairs_hook=board_schema._strict_json_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContactRefused("registration input is not strict JSON") from exc
    if not isinstance(value, dict) or set(value) != UNSTORED_FIELDS:
        raise ContactRefused("registration must have exactly the unstored fields")
    if value["schema"] != CONTACT_SCHEMA:
        raise ContactRefused("unknown contact schema")
    return value


def _canonical_nonce(value: object) -> str:
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContactRefused("contact nonce is not canonical") from exc
    return value


def _valid_seat(seat: object) -> bool:
    try:
        board_schema.validate_owner(seat)
        return True
    except Exception:
        return False


def _endpoint(provider: str, endpoint: object) -> None:
    if not isinstance(endpoint, dict) or set(endpoint) != ENDPOINT_FIELDS[provider]:
        raise ContactRefused("contact endpoint fields are invalid")
    for scalar in endpoint.values():
        if (not isinstance(scalar, str) or not scalar
                or len(scalar.encode("utf-8")) > 512
                or board_schema.CONTROL.search(scalar)
                or board_schema.SECRET_SHAPE_RE.search(scalar)):
            raise ContactRefused("contact endpoint is unsafe")
    if provider == "cmux":
        _canonical_nonce(endpoint["surface_uuid"])
    if provider == "grok":
        # No undocumented URI scheme or broad transport allowance is inferred;
        # the parent validator refuses Grok endpoints for the same reason.
        raise ContactRefused("Grok endpoint scheme has no admitted transport")


def _validate_common(value: dict, *, seat: str) -> None:
    """Validate the fields shared by unstored requests and stored records."""
    _canonical_nonce(value["instance_nonce"])
    provider, capability = value["provider"], value["capability"]
    if (not isinstance(provider, str) or provider not in PROVIDERS
            or not isinstance(capability, str) or not IDENTIFIER.fullmatch(capability)):
        raise ContactRefused("contact capability is invalid")
    _endpoint(provider, value["endpoint"])
    refs = value["claim_keys"]
    if not isinstance(refs, list) or len(refs) > 64:
        raise ContactRefused("contact claim count is invalid")
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"entity", "row", "claim_revision", "owner"}:
            raise ContactRefused("contact claim key is not closed")
        if (not isinstance(ref["entity"], str)
                or not board_schema.ENTITY_ID.fullmatch(ref["entity"])
                or not isinstance(ref["row"], str)
                or not board_schema.ROW_ID.fullmatch(ref["row"])
                or type(ref["claim_revision"]) is not int
                or ref["claim_revision"] < 0
                or ref["owner"] != seat):
            raise ContactRefused("contact claim identity is invalid")
        key = tuple(ref[k] for k in ("entity", "row", "claim_revision", "owner"))
        if key in seen:
            raise ContactRefused("contact claim is duplicated")
        seen.add(key)


def validate_registration(request: dict, *, seat: str) -> None:
    """Structurally validate one unstored registration request.

    Board currency of ``claim_keys`` is intentionally not checked here: the
    confined child cannot and must not become a second board authority. The
    parent runner validated currency at arming time, and delivery re-checks
    it against the child's own atomic board re-read.
    """
    if not isinstance(request, dict) or set(request) != UNSTORED_FIELDS:
        raise ContactRefused("registration must have exactly the unstored fields")
    if request["schema"] != CONTACT_SCHEMA:
        raise ContactRefused("unknown contact schema")
    _validate_common(request, seat=seat)


def validate_stored_contact(contact: object, *, seat: str, now: datetime) -> None:
    """Validate one stored contact record, including its current lease."""
    if not isinstance(contact, dict) or set(contact) != STORED_FIELDS:
        raise ContactRefused("stored contact must have exactly the stored fields")
    if contact["schema"] != CONTACT_SCHEMA or contact["seat"] != seat:
        raise ContactRefused("stored contact identity is invalid")
    if not _valid_seat(seat):
        raise ContactRefused("stored contact seat is invalid")
    registered = parse_canonical_utc(contact["registered_at"])
    refreshed = parse_canonical_utc(contact["refreshed_at"])
    expires = parse_canonical_utc(contact["expires_at"])
    if not registered <= refreshed <= now < expires <= refreshed + LEASE:
        raise ContactRefused("contact lease is not current")
    _validate_common(contact, seat=seat)


def stored_registration(request: dict, *, seat: str, now: datetime) -> dict:
    """Project one validated request into its stored record at one instant."""
    validate_registration(request, seat=seat)
    stamp = utc_stamp(now)
    return dict(request, seat=seat, registered_at=stamp, refreshed_at=stamp,
                expires_at=utc_stamp(now + LEASE))


def capability_pair(provider: str, capability: str, entries) -> dict:
    """Return the single armed capability entry matching the pair, or refuse."""
    matches = [entry for entry in entries
               if entry["provider"] == provider and entry["capability"] == capability]
    if len(matches) != 1:
        raise ContactRefused("registration pair is not armed exactly once")
    return matches[0]


def write_contact(dir_fd: int, contact: dict, *, now: datetime | None = None) -> str:
    """Write one stored contact as ``<nonce>.json`` (0600, exclusive, bounded).

    The confined registration child holds the contacts directory as its only
    writable descriptor; this is the single write it may perform.
    """
    name = contact["instance_nonce"] + ".json"
    if CONTACT_NAME.fullmatch(name) is None:
        raise ContactRefused("contact filename is not a canonical nonce record")
    payload = json.dumps(contact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_CONTACT_BYTES:
        raise ContactRefused("stored contact exceeds the bounded size")
    if now is not None:
        # Refuse at write time when the lease is already unconstrained.
        expires = parse_canonical_utc(contact["expires_at"])
        if not now < expires:
            raise ContactRefused("contact lease is already expired")
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=dir_fd)
    try:
        written = 0
        while written < len(payload):
            written += os.write(fd, payload[written:])
    finally:
        os.close(fd)
    return name
