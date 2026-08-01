"""Pure helpers for the provider-neutral Vidux Drive / 90 boundary.

This module deliberately does not read a plan, write a mailbox, invoke a
provider, or retain input.  It projects one already-validated
``vidux.outcome.v1`` document into the small semantic surface a native voice
client needs, and builds one typed choice envelope for the owning host.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
import re
from typing import Any


OUTCOME_SCHEMA = "vidux.outcome.v1"
DRIVE_SCHEMA = "vidux.drive.v1"
STEER_SCHEMA = "vidux.drive-steer.v1"
RECEIPT_SCHEMA = "vidux.drive-receipt.v1"
MAX_PRESENTED_OPTIONS = 3
NONTERMINAL_STEER_STATES = frozenset({"received", "applied", "working", "blocked"})
RECEIPT_STATES = frozenset({"received", "superseded", "not_delivered"})
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
MAX_REVISION = 2147483647


class DriveInputError(ValueError):
    """Raised when a client receives a document outside the typed boundary."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DriveInputError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DriveInputError(f"{label} must be a nonblank string")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _text(value, label)
    if not IDENTIFIER_RE.fullmatch(value):
        raise DriveInputError(f"{label} must be a public identifier")
    return value


def _document(document: Any) -> Mapping[str, Any]:
    document = _mapping(document, "document")
    if document.get("schema") != OUTCOME_SCHEMA:
        raise DriveInputError(f"document schema must equal {OUTCOME_SCHEMA}")
    return document


def _revision(document: Mapping[str, Any]) -> int:
    revision = document.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or not 0 <= revision <= MAX_REVISION:
        raise DriveInputError("document.revision must be a public integer")
    return revision


def _choice(envelope: Any) -> dict[str, Any]:
    envelope = _mapping(envelope, "choice")
    expected = {"schema", "kind", "revision", "outcome_id", "ask_id", "option_id"}
    if set(envelope) != expected:
        raise DriveInputError("choice must contain only the typed Drive fields")
    if envelope.get("schema") != STEER_SCHEMA or envelope.get("kind") != "answer":
        raise DriveInputError("choice has an invalid Drive schema or kind")
    revision = envelope.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or not 0 <= revision <= MAX_REVISION:
        raise DriveInputError("choice.revision must be a public integer")
    return {
        "revision": revision,
        "outcome_id": _identifier(envelope.get("outcome_id"), "choice.outcome_id"),
        "ask_id": _identifier(envelope.get("ask_id"), "choice.ask_id"),
        "option_id": _identifier(envelope.get("option_id"), "choice.option_id"),
    }


def _timestamp(document: Mapping[str, Any], updated_at: Any) -> str:
    value = document.get("updated_at") if updated_at is None else updated_at
    if not isinstance(value, str) or not UTC_TIMESTAMP_RE.fullmatch(value):
        raise DriveInputError("updated_at must be an RFC3339 UTC timestamp")
    return value


def _new_identifier(document: Mapping[str, Any], prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    base = f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"
    seen: set[str] = set()
    outcome = document.get("outcome")
    if isinstance(outcome, Mapping) and isinstance(outcome.get("id"), str):
        seen.add(outcome["id"])
    ask = document.get("ask")
    if isinstance(ask, Mapping) and isinstance(ask.get("id"), str):
        seen.add(ask["id"])
        for option in ask.get("options", []):
            if isinstance(option, Mapping) and isinstance(option.get("id"), str):
                seen.add(option["id"])
    for collection_name in ("steers", "proof"):
        collection = document.get(collection_name, [])
        if isinstance(collection, Sequence) and not isinstance(collection, (str, bytes)):
            for item in collection:
                if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                    seen.add(item["id"])
    candidate = base
    suffix = 2
    while candidate in seen:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _outcome(document: Mapping[str, Any]) -> Mapping[str, Any]:
    outcome = _mapping(document.get("outcome"), "outcome")
    return {
        "id": _identifier(outcome.get("id"), "outcome.id"),
        "summary": _text(outcome.get("summary"), "outcome.summary"),
        "state": _text(outcome.get("state"), "outcome.state"),
        "current_move": outcome.get("current_move"),
    }


def _ask(document: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = document.get("ask")
    if raw is None:
        return None
    ask = _mapping(raw, "ask")
    ask_id = _identifier(ask.get("id"), "ask.id")
    state = _text(ask.get("state"), "ask.state")
    options = ask.get("options")
    if not isinstance(options, Sequence) or isinstance(options, (str, bytes)):
        raise DriveInputError("ask.options must be an array")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw_option in enumerate(options):
        option = _mapping(raw_option, f"ask.options[{index}]")
        option_id = _identifier(option.get("id"), f"ask.options[{index}].id")
        if option_id in seen:
            raise DriveInputError("ask option IDs must be unique")
        seen.add(option_id)
        normalized.append(
            {
                "id": option_id,
                "label": _text(option.get("label"), f"ask.options[{index}].label"),
                "consequence": _text(
                    option.get("consequence"),
                    f"ask.options[{index}].consequence",
                ),
            }
        )
    if state == "open" and outcome.get("state") != "needs_input":
        raise DriveInputError("an open Ask requires an outcome in needs_input state")
    if state != "open" and outcome.get("state") == "needs_input":
        raise DriveInputError("a needs_input outcome requires an open Ask")
    visible = normalized[:MAX_PRESENTED_OPTIONS] if state == "open" else []
    return {
        "id": ask_id,
        "category": _text(ask.get("category"), "ask.category"),
        "question": _text(ask.get("question"), "ask.question"),
        "state": state,
        "answer_option_id": ask.get("answer_option_id"),
        "options": visible,
        "options_total": len(normalized),
        "options_truncated": len(visible) < len(normalized) if state == "open" else False,
    }


def _steers(document: Mapping[str, Any], outcome_id: str) -> list[dict[str, Any]]:
    raw_steers = document.get("steers", [])
    if not isinstance(raw_steers, Sequence) or isinstance(raw_steers, (str, bytes)):
        raise DriveInputError("steers must be an array")
    result: list[dict[str, Any]] = []
    for index, raw_steer in enumerate(raw_steers):
        steer = _mapping(raw_steer, f"steers[{index}]")
        if steer.get("outcome_id") != outcome_id:
            raise DriveInputError("every Steer must target the current Outcome")
        result.append(
            {
                "id": _identifier(steer.get("id"), f"steers[{index}].id"),
                "outcome_id": outcome_id,
                "summary": _text(steer.get("summary"), f"steers[{index}].summary"),
                "state": _text(steer.get("state"), f"steers[{index}].state"),
                "proof_ref": steer.get("proof_ref"),
            }
        )
    return result


def _proof(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_proof = document.get("proof", [])
    if not isinstance(raw_proof, Sequence) or isinstance(raw_proof, (str, bytes)):
        raise DriveInputError("proof must be an array")
    result: list[dict[str, Any]] = []
    for index, raw_reference in enumerate(raw_proof):
        reference = _mapping(raw_reference, f"proof[{index}]")
        result.append(
            {
                "id": _identifier(reference.get("id"), f"proof[{index}].id"),
                "type": _text(reference.get("type"), f"proof[{index}].type"),
                "locator": _text(reference.get("locator"), f"proof[{index}].locator"),
                "verification_summary": _text(
                    reference.get("verification_summary"),
                    f"proof[{index}].verification_summary",
                ),
                "delivery": _text(reference.get("delivery"), f"proof[{index}].delivery"),
            }
        )
    return result


def project_drive(document: Any) -> dict[str, Any]:
    """Return the bounded semantic view consumed by a native 90 client.

    The returned object is newly allocated and contains only allowlisted
    semantic fields.  In particular, provider/model/prompt/transcript and
    arbitrary host fields can never pass through this projection.
    """

    source = _document(document)
    revision = _revision(source)
    outcome = _outcome(source)
    ask = _ask(source, outcome)
    steers = _steers(source, outcome["id"])
    proof = _proof(source)
    active = next((item for item in steers if item["state"] in NONTERMINAL_STEER_STATES), None)
    return {
        "schema": DRIVE_SCHEMA,
        "revision": revision,
        "updated_at": source.get("updated_at"),
        "outcome": deepcopy(outcome),
        "ask": ask,
        "active_steer_id": active["id"] if active else None,
        "steers": steers,
        "proof": proof,
    }


def build_choice(document: Any, option_id: Any) -> dict[str, Any]:
    """Build one ephemeral typed answer for the owning host.

    This is an intent envelope, not a durable Steer record.  The host that
    owns the Outcome decides whether to accept it and records the resulting
    Steer/proof in the existing authority.  There is intentionally no free
    text, provider, model, command, or queue field.
    """

    source = _document(document)
    revision = _revision(source)
    outcome = _outcome(source)
    ask = _ask(source, outcome)
    if ask is None or ask["state"] != "open":
        raise DriveInputError("a choice requires an open Ask")
    option_id = _identifier(option_id, "option_id")
    if not any(option["id"] == option_id for option in ask["options"]):
        raise DriveInputError("option_id is not present in the open Ask")
    return {
        "schema": STEER_SCHEMA,
        "kind": "answer",
        "revision": revision,
        "outcome_id": outcome["id"],
        "ask_id": ask["id"],
        "option_id": option_id,
    }


def receive_choice(
    document: Any,
    envelope: Any,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Record one local compare-and-set handshake in the same Outcome document.

    This function is deliberately a pure local boundary: it returns a new
    ``vidux.outcome.v1`` document and a bounded receipt, but never writes a
    file, creates a queue, invokes a host, or selects a provider.  A current,
    visible choice becomes ``received``.  A stale choice becomes
    ``superseded``; an identity or hidden-option mismatch becomes
    ``not_delivered`` with a local proof reference.  The caller must run the
    canonical Outcome validator before using the returned document.
    """

    source = _document(document)
    choice = _choice(envelope)
    authority_revision = _revision(source)
    outcome = _outcome(source)
    ask = _ask(source, outcome)
    timestamp = _timestamp(source, updated_at)

    if choice["outcome_id"] != outcome["id"] or ask is None or choice["ask_id"] != ask["id"]:
        state = "not_delivered"
        reason = "identity_mismatch"
    elif ask["state"] != "open" or outcome["state"] != "needs_input":
        state = "superseded"
        reason = "ask_closed"
    elif not any(option["id"] == choice["option_id"] for option in ask["options"]):
        state = "not_delivered"
        reason = "option_not_visible"
    elif choice["revision"] != authority_revision:
        state = "superseded"
        reason = "stale_revision"
    else:
        state = "received"
        reason = "accepted"

    next_revision = authority_revision + 1
    if next_revision > MAX_REVISION:
        raise DriveInputError("document.revision cannot advance")
    if not isinstance(source.get("steers"), list) or not isinstance(source.get("proof"), list):
        raise DriveInputError("document steers and proof must be arrays")
    if len(source["steers"]) >= 64 or len(source["proof"]) >= 64:
        raise DriveInputError("document has no room for another handshake record")

    updated = deepcopy(source)
    proof_ref: str | None = None
    if state == "received":
        for existing in updated["steers"]:
            if isinstance(existing, dict) and existing.get("state") in NONTERMINAL_STEER_STATES:
                existing["state"] = "superseded"
    elif state == "not_delivered":
        proof_ref = _new_identifier(
            updated,
            "drive-proof",
            {"choice": choice, "revision": authority_revision, "reason": reason},
        )
        updated["proof"].append(
            {
                "id": proof_ref,
                "type": "other",
                "locator": "docs/reference/drive-mode.md",
                "verification_summary": f"Drive choice was not delivered: {reason}.",
                "delivery": "not_delivered",
            }
        )

    steer_id = _new_identifier(
        updated,
        "drive-steer",
        {"choice": choice, "revision": authority_revision, "state": state},
    )
    summaries = {
        "received": f"Drive choice {choice['option_id']} received at revision {choice['revision']}.",
        "superseded": "Drive choice was superseded by a newer authority state.",
        "not_delivered": f"Drive choice {choice['option_id']} was not delivered: {reason}.",
    }
    updated["steers"].append(
        {
            "id": steer_id,
            "outcome_id": outcome["id"],
            "summary": summaries[state],
            "state": state,
            "proof_ref": proof_ref,
        }
    )
    updated["revision"] = next_revision
    updated["updated_at"] = timestamp
    return {
        "document": updated,
        "receipt": {
            "schema": RECEIPT_SCHEMA,
            "state": state,
            "reason": reason,
            "observed_revision": choice["revision"],
            "authority_revision": authority_revision,
            "next_revision": next_revision,
            "outcome_id": choice["outcome_id"],
            "ask_id": choice["ask_id"],
            "option_id": choice["option_id"],
            "steer_id": steer_id,
            "proof_ref": proof_ref,
        },
    }


__all__ = [
    "DRIVE_SCHEMA",
    "MAX_PRESENTED_OPTIONS",
    "OUTCOME_SCHEMA",
    "RECEIPT_SCHEMA",
    "STEER_SCHEMA",
    "DriveInputError",
    "build_choice",
    "project_drive",
    "receive_choice",
]
