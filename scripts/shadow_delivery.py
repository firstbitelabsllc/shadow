#!/usr/bin/env python3
"""Exact-target delivery adapters for the confined Huddle event runner.

The confined child owns no authority: it re-reads the board atomically,
re-derives eligibility exactly as the parent runner did, and attempts one
bounded delivery per (contact, armed capability) pair by executing the
capability's single registered native target with the envelope on stdin.
Nothing here writes the board, the plan, or any contact other than reading
the selected ones; availability and receipts are ephemeral child output and
never become board authority.

Privacy-safe projection: an envelope carries only the event identity, the
recipient contact's own provider/capability/endpoint, and the idempotency
key. It never carries the board path, seat names, claim payloads, other
contacts' endpoints, or free-form prose.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import subprocess
import time

import shadow_board_schema as board_schema
import shadow_contacts as contacts

ENVELOPE_SCHEMA = "shadow.huddle-delivery-envelope.v1"
CAPABILITIES_SCHEMA = "shadow.huddle-provider-capabilities.v1"
MAX_CAPABILITY_BYTES = 16 * 1024
MAX_CAPABILITY_ENTRIES = 32
ENVELOPE_FIELDS = frozenset(
    {"schema", "event", "huddle_id", "generation", "provider", "capability",
     "instance_nonce", "endpoint", "idempotency_key", "attempted_at"})
MAX_ENVELOPE_BYTES = 4096
MAX_CONTACT_FILES = 256
MAX_RECEIPTS = 256
# Exit-code protocol with the registered native target. Anything else —
# signals, timeouts, spawn failures — is unhealthy, never a silent success.
OUTCOME_BY_EXIT = {0: "accepted", 1: "refused", 2: "unsupported", 3: "unhealthy"}
MAX_ATTEMPT_SECONDS = 1.0


def canonical_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_armed_entries(raw: bytes, expected_digests, *, now: datetime) -> tuple[dict, ...]:
    """Strict child-side read of the armed capability descriptor.

    Mirrors the parent validator's closed structure and ten-minute TTL but
    never re-opens targets: the parent already resolved and identity-bound
    every native target, and a confined child cannot walk path components.
    Instead each entry is bound to the digest the parent computed over it;
    an entry the parent did not arm is refused.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_CAPABILITY_BYTES:
        raise contacts.ContactRefused("capability descriptor exceeds the bounded size")
    try:
        value = json.loads(raw, object_pairs_hook=board_schema._strict_json_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise contacts.ContactRefused("malformed capability descriptor") from exc
    if (not isinstance(value, dict)
            or set(value) != {"schema", "generated_at", "expires_at", "entries"}
            or value["schema"] != CAPABILITIES_SCHEMA):
        raise contacts.ContactRefused("closed capability descriptor required")
    generated = contacts.parse_canonical_utc(value["generated_at"])
    expires = contacts.parse_canonical_utc(value["expires_at"])
    if generated > now or expires <= now or expires > generated + timedelta(minutes=10):
        raise contacts.ContactRefused("capability descriptor is expired or future dated")
    entries = value["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_CAPABILITY_ENTRIES:
        raise contacts.ContactRefused("invalid capability entry count")
    expected = set(expected_digests)
    pairs = set()
    normalized = []
    for entry in entries:
        if (not isinstance(entry, dict)
                or set(entry) != {"provider", "capability", "transport", "target"}):
            raise contacts.ContactRefused("closed capability entry required")
        provider, capability = entry["provider"], entry["capability"]
        if (not all(isinstance(v, str) and contacts.IDENTIFIER.fullmatch(v)
                    for v in (provider, capability))
                or provider not in contacts.PROVIDERS):
            raise contacts.ContactRefused("invalid capability identity")
        if (provider, capability) in pairs:
            raise contacts.ContactRefused("duplicate provider capability")
        pairs.add((provider, capability))
        if entry["transport"] != "exec" or not isinstance(entry["target"], str) \
                or not entry["target"] or "\x00" in entry["target"]:
            raise contacts.ContactRefused("only exact exec targets are admitted")
        if hashlib.sha256(canonical_bytes(entry)).hexdigest() not in expected:
            raise contacts.ContactRefused("capability entry is not armed by the parent")
        normalized.append(dict(entry))
    return tuple(normalized)


def idempotency_key(*, provider: str, capability: str, instance_nonce: str,
                    huddle_id: str, generation: int, event: str, endpoint: dict) -> str:
    """Deterministic 64-hex key so retried events dedupe at the recipient."""
    material = canonical_bytes({
        "provider": provider, "capability": capability,
        "instance_nonce": instance_nonce, "huddle_id": huddle_id,
        "generation": generation, "event": event, "endpoint": endpoint})
    return hashlib.sha256(material).hexdigest()


def build_envelope(*, event: dict, provider: str, capability: str,
                   instance_nonce: str, endpoint: dict, now: datetime) -> dict:
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "event": event["event"],
        "huddle_id": event["huddle_id"],
        "generation": event["generation"],
        "provider": provider,
        "capability": capability,
        "instance_nonce": instance_nonce,
        "endpoint": endpoint,
        "idempotency_key": idempotency_key(
            provider=provider, capability=capability, instance_nonce=instance_nonce,
            huddle_id=event["huddle_id"], generation=event["generation"],
            event=event["event"], endpoint=endpoint),
        "attempted_at": contacts.utc_stamp(now),
    }
    if set(envelope) != ENVELOPE_FIELDS:
        raise contacts.ContactRefused("envelope fields are not closed")
    if len(canonical_bytes(envelope)) > MAX_ENVELOPE_BYTES:
        raise contacts.ContactRefused("envelope exceeds the bounded size")
    return envelope


def attempt(target: str, envelope: dict, *, deadline_seconds: float) -> str:
    """Execute the exact native target once; classify the exit, never parse prose."""
    budget = min(MAX_ATTEMPT_SECONDS, max(0.05, float(deadline_seconds)))
    try:
        result = subprocess.run([target], input=canonical_bytes(envelope),
                                capture_output=True, timeout=budget)
    except (subprocess.TimeoutExpired, OSError):
        return "unhealthy"
    return OUTCOME_BY_EXIT.get(result.returncode, "unhealthy")


def eligible_claim_keys(huddle: dict) -> set:
    """Mirror the parent runner's eligibility, including handoff successors."""
    eligible = {board_schema._claim_key(board_schema._terminal_ref(huddle, claim))
                for claim in huddle["claims"]}
    resolution = huddle.get("resolution")
    if resolution and resolution.get("handoff"):
        successor = board_schema._terminal_ref(huddle, resolution["handoff"]["successor_claim"])
        eligible.add(board_schema._claim_key(successor))
    return eligible


def deliver(*, event: dict, huddle: dict, current_claims: dict, capability_entries,
            contacts_dir_fd: int, now: datetime, deadline_seconds: float) -> list[dict]:
    """Attempt delivery to every current, eligible, armed contact recipient."""
    started = time.monotonic()
    eligible = eligible_claim_keys(huddle)
    armed = {(entry["provider"], entry["capability"]): entry for entry in capability_entries}
    receipts: list[dict] = []
    with os.scandir(contacts_dir_fd) as names:
        for index, entry in enumerate(names):
            if index >= MAX_CONTACT_FILES:
                raise contacts.ContactRefused("contact directory exceeds selection bound")
            if contacts.CONTACT_NAME.fullmatch(entry.name) is None:
                continue
            fd = -1
            try:
                # The seatbelt admits only the parent-selected contact files;
                # an unrelated same-provider contact is refused by the kernel.
                fd = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=contacts_dir_fd)
                contact = json.loads(_read_bounded(fd, contacts.MAX_CONTACT_BYTES),
                                     object_pairs_hook=board_schema._strict_json_object)
                seat = contact.get("seat")
                contacts.validate_stored_contact(contact, seat=seat, now=now)
                if entry.name != contact["instance_nonce"] + ".json":
                    continue
                keys = {tuple(ref[k] for k in ("entity", "row", "claim_revision", "owner"))
                        for ref in contact["claim_keys"]}
                if any(key not in current_claims for key in keys):
                    continue
                if not keys & eligible:
                    continue
                capability = armed.get((contact["provider"], contact["capability"]))
                if capability is None:
                    continue
            except (OSError, ValueError, TypeError, KeyError,
                    contacts.ContactRefused):
                continue
            finally:
                if fd >= 0:
                    os.close(fd)
            if len(receipts) >= MAX_RECEIPTS:
                break
            remaining = deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            attempted = datetime.now(timezone.utc)
            envelope = build_envelope(
                event=event, provider=contact["provider"],
                capability=contact["capability"],
                instance_nonce=contact["instance_nonce"],
                endpoint=contact["endpoint"], now=attempted)
            outcome = attempt(capability["target"], envelope, deadline_seconds=remaining)
            receipts.append({
                "adapter": contact["provider"],
                "huddle_id": event["huddle_id"],
                "idempotency_key": envelope["idempotency_key"],
                "contact_nonce": contact["instance_nonce"],
                "attempted_at": contacts.utc_stamp(attempted),
                "outcome": outcome,
            })
    return receipts


def _read_bounded(fd: int, limit: int) -> bytes:
    import stat as stat_module
    before = os.fstat(fd)
    if (not stat_module.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
            or before.st_nlink != 1 or before.st_size > limit):
        raise contacts.ContactRefused("unsafe bounded contact file")
    chunks = []
    remaining = limit + 1
    while remaining:
        part = os.read(fd, min(65536, remaining))
        if not part:
            break
        chunks.append(part)
        remaining -= len(part)
    value = b"".join(chunks)
    if len(value) > limit or len(value) != before.st_size:
        raise contacts.ContactRefused("contact file changed during bounded read")
    return value
