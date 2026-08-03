"""Pure projection and compare-and-set receipt for one A/B/C choice."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import re
from typing import Any


OUTCOME_SCHEMA = "pilot-puppy.outcome.v1"
DECISION_SCHEMA = "pilot-puppy.decision.v1"
CHOICE_SCHEMA = "pilot-puppy.decision-choice.v1"
RECEIPT_SCHEMA = "pilot-puppy.decision-receipt.v1"
MAX_REVISION = 2_147_483_647
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$")


class DecisionInputError(ValueError):
    pass


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DecisionInputError(f"{label} must be an object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionInputError(f"{label} must be a nonblank string")
    return value


def identifier(value: Any, label: str) -> str:
    value = text(value, label)
    if IDENTIFIER_RE.fullmatch(value) is None:
        raise DecisionInputError(f"{label} must be a public identifier")
    return value


def revision(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_REVISION:
        raise DecisionInputError(f"{label} must be a public integer")
    return value


def outcome_document(value: Any) -> Mapping[str, Any]:
    document = mapping(value, "document")
    if document.get("schema") != OUTCOME_SCHEMA:
        raise DecisionInputError(f"document schema must equal {OUTCOME_SCHEMA}")
    if set(document) != {"schema", "revision", "updated_at", "outcome", "ask", "proof"}:
        raise DecisionInputError("document contains fields outside the Outcome contract")
    revision(document.get("revision"), "document.revision")
    if not isinstance(document.get("updated_at"), str) or UTC_RE.fullmatch(document["updated_at"]) is None:
        raise DecisionInputError("document.updated_at must be an RFC3339 UTC timestamp")
    return document


def project_outcome(document: Mapping[str, Any]) -> dict[str, Any]:
    source = mapping(document.get("outcome"), "outcome")
    return {
        "id": identifier(source.get("id"), "outcome.id"),
        "summary": text(source.get("summary"), "outcome.summary"),
        "state": text(source.get("state"), "outcome.state"),
        "current_move": text(source.get("current_move"), "outcome.current_move"),
    }


def project_ask(document: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = document.get("ask")
    if raw is None:
        if outcome["state"] == "needs_input":
            raise DecisionInputError("a needs_input Outcome requires an open A/B/C choice")
        return None
    source = mapping(raw, "ask")
    if source.get("state") != "open" or outcome["state"] != "needs_input":
        raise DecisionInputError("only a needs_input Outcome may expose an open A/B/C choice")
    options = source.get("options")
    if not isinstance(options, Sequence) or isinstance(options, (str, bytes)) or len(options) != 3:
        raise DecisionInputError("an open choice must contain exactly A/B/C")
    projected = []
    seen = set()
    for index, raw_option in enumerate(options):
        option = mapping(raw_option, f"ask.options[{index}]")
        option_id = identifier(option.get("id"), f"ask.options[{index}].id")
        if option_id in seen:
            raise DecisionInputError("choice option IDs must be unique")
        seen.add(option_id)
        projected.append(
            {
                "id": option_id,
                "label": text(option.get("label"), f"ask.options[{index}].label"),
                "consequence": text(option.get("consequence"), f"ask.options[{index}].consequence"),
            }
        )
    return {
        "id": identifier(source.get("id"), "ask.id"),
        "category": text(source.get("category"), "ask.category"),
        "question": text(source.get("question"), "ask.question"),
        "state": "open",
        "answer_option_id": None,
        "options": projected,
    }


def project_proof(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("proof")
    if not isinstance(raw, list):
        raise DecisionInputError("proof must be an array")
    return [deepcopy(dict(mapping(item, f"proof[{index}]"))) for index, item in enumerate(raw)]


def project_decision(value: Any) -> dict[str, Any]:
    document = outcome_document(value)
    outcome = project_outcome(document)
    return {
        "schema": DECISION_SCHEMA,
        "revision": document["revision"],
        "updated_at": document["updated_at"],
        "outcome": outcome,
        "ask": project_ask(document, outcome),
        "proof": project_proof(document),
    }


def build_choice(value: Any, option_id: Any) -> dict[str, Any]:
    decision = project_decision(value)
    ask = decision["ask"]
    if ask is None:
        raise DecisionInputError("a choice requires an open A/B/C question")
    option_id = identifier(option_id, "option_id")
    if option_id not in {option["id"] for option in ask["options"]}:
        raise DecisionInputError("option_id is not present in the open choice")
    return {
        "schema": CHOICE_SCHEMA,
        "kind": "answer",
        "revision": decision["revision"],
        "outcome_id": decision["outcome"]["id"],
        "ask_id": ask["id"],
        "option_id": option_id,
    }


def receive_choice(value: Any, envelope: Any, *, updated_at: str | None = None) -> dict[str, Any]:
    decision = project_decision(value)
    choice = mapping(envelope, "choice")
    expected = {"schema", "kind", "revision", "outcome_id", "ask_id", "option_id"}
    if set(choice) != expected or choice.get("schema") != CHOICE_SCHEMA or choice.get("kind") != "answer":
        raise DecisionInputError("choice contains fields outside the closed choice contract")
    observed = revision(choice.get("revision"), "choice.revision")
    outcome_id = identifier(choice.get("outcome_id"), "choice.outcome_id")
    ask_id = identifier(choice.get("ask_id"), "choice.ask_id")
    option_id = identifier(choice.get("option_id"), "choice.option_id")
    ask = decision["ask"]
    if outcome_id != decision["outcome"]["id"] or ask is None or ask_id != ask["id"]:
        state, reason = "not_delivered", "identity_mismatch"
    elif option_id not in {option["id"] for option in ask["options"]}:
        state, reason = "not_delivered", "option_not_visible"
    elif observed != decision["revision"]:
        state, reason = "superseded", "stale_revision"
    else:
        state, reason = "received", "accepted"
    if updated_at is not None and UTC_RE.fullmatch(updated_at) is None:
        raise DecisionInputError("updated_at must be an RFC3339 UTC timestamp")
    return {
        "receipt": {
            "schema": RECEIPT_SCHEMA,
            "state": state,
            "reason": reason,
            "observed_revision": observed,
            "authority_revision": decision["revision"],
            "outcome_id": outcome_id,
            "ask_id": ask_id,
            "option_id": option_id,
        }
    }


__all__ = [
    "CHOICE_SCHEMA",
    "DECISION_SCHEMA",
    "DecisionInputError",
    "OUTCOME_SCHEMA",
    "RECEIPT_SCHEMA",
    "build_choice",
    "project_decision",
    "receive_choice",
]
