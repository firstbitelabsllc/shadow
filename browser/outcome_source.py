"""Pure projection from an owning PLAN.md Brief to one Outcome.

The browser may read plans, but it must not turn the whole plan, a path, a
session, or provider metadata into durable Outcome state.  This module accepts
only the already-parsed Brief fields needed for the semantic contract
and returns a fresh, closed ``shadow.outcome.v1`` document.  It never reads or
writes files, invokes a host, selects a provider, or creates a queue.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Any
import unicodedata


OUTCOME_SCHEMA = "shadow.outcome.v1"
MAX_REVISION = 2_147_483_647
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
OUTCOME_STATES = frozenset(
    {"working", "needs_input", "blocked", "finished_with_proof", "not_delivered"}
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
HOME_PATH_RE = re.compile(
    r"(?:^|[\s\"'=])(?:~/|/Users/|/home/|file://|\$HOME(?:[/\\]|$))",
    re.IGNORECASE,
)
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s\"'=])/(?!/)[A-Za-z0-9._-]+(?:/[^\s\"']*)?",
    re.IGNORECASE,
)
SECRET_SHAPE_RE = re.compile(
    r"(?:sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


class OutcomeSourceError(ValueError):
    """Raised when a plan does not declare a complete canonical Outcome."""


def _text(value: Any, label: str, *, max_length: int = 280) -> str:
    if not isinstance(value, str):
        raise OutcomeSourceError(f"{label} must be a string")
    value = " ".join(value.split())
    if not value:
        raise OutcomeSourceError(f"{label} must be nonblank")
    if len(value) > max_length:
        raise OutcomeSourceError(f"{label} exceeds {max_length} characters")
    if CONTROL_CHAR_RE.search(value):
        raise OutcomeSourceError(f"{label} contains a control character")
    if any(
        unicodedata.category(character) == "Cf"
        or unicodedata.bidirectional(character)
        in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI", "BN"}
        for character in value
    ):
        raise OutcomeSourceError(f"{label} contains a Unicode format control")
    if unicodedata.normalize("NFC", value) != value:
        raise OutcomeSourceError(f"{label} is not NFC-normalized")
    if HOME_PATH_RE.search(value) or ABSOLUTE_PATH_RE.search(value):
        raise OutcomeSourceError(f"{label} contains a private filesystem path")
    if SECRET_SHAPE_RE.search(value):
        raise OutcomeSourceError(f"{label} contains a secret-shaped value")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _text(value, label, max_length=64)
    if IDENTIFIER_RE.fullmatch(value) is None:
        raise OutcomeSourceError(f"{label} must be a public identifier")
    return value


def _revision(value: Any) -> int:
    if isinstance(value, bool):
        raise OutcomeSourceError("outcome_revision must be an integer")
    try:
        revision = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise OutcomeSourceError("outcome_revision must be an integer") from exc
    if not 0 <= revision <= MAX_REVISION:
        raise OutcomeSourceError("outcome_revision is outside the public range")
    return revision


def _updated_at(value: Any) -> str:
    value = _text(value, "outcome_updated_at", max_length=40)
    if UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise OutcomeSourceError("outcome_updated_at must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeSourceError("outcome_updated_at is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise OutcomeSourceError("outcome_updated_at must be UTC")
    return value


def project_plan_outcome(brief: Mapping[str, Any]) -> dict[str, Any]:
    """Project one complete canonical Brief into a closed Outcome.

    The four ``outcome_*`` fields are intentionally explicit.  Deriving a
    revision from file mtime or a path would make two clients disagree after a
    checkout, and silently accepting a missing field would create a false
    green. Incomplete briefs therefore return ``OutcomeSourceError``.
    """

    if not isinstance(brief, Mapping):
        raise OutcomeSourceError("operator brief must be an object")

    summary = _text(brief.get("outcome"), "outcome")
    current_move = _text(brief.get("next"), "next")
    outcome_id = _identifier(brief.get("outcome_id"), "outcome_id")
    revision = _revision(brief.get("outcome_revision"))
    updated_at = _updated_at(brief.get("outcome_updated_at"))
    state = _text(brief.get("outcome_state"), "outcome_state", max_length=32)
    if state not in OUTCOME_STATES:
        raise OutcomeSourceError("outcome_state is not a supported public state")

    ask = None
    if state == "needs_input":
        ask_id = _identifier(brief.get("decision_id"), "decision_id")
        question = _text(brief.get("decision"), "decision")
        options = []
        for letter in ("a", "b", "c"):
            options.append(
                {
                    "id": _identifier(brief.get(f"option_{letter}_id"), f"option_{letter}_id"),
                    "label": _text(brief.get(f"option_{letter}"), f"option_{letter}"),
                    "consequence": _text(
                        brief.get(f"option_{letter}_consequence"),
                        f"option_{letter}_consequence",
                    ),
                }
            )
        ask = {
            "id": ask_id,
            "category": "product_choice",
            "question": question,
            "options": options,
            "state": "open",
            "answer_option_id": None,
        }

    proof = []
    if brief.get("proof") is not None or brief.get("proof_summary") is not None:
        proof.append(
            {
                "id": _identifier(brief.get("proof_id"), "proof_id"),
                "type": "test",
                "locator": _text(brief.get("proof"), "proof"),
                "verification_summary": _text(brief.get("proof_summary"), "proof_summary"),
                "delivery": _text(brief.get("proof_delivery"), "proof_delivery", max_length=32),
            }
        )

    return {
        "schema": OUTCOME_SCHEMA,
        "revision": revision,
        "updated_at": updated_at,
        "outcome": {
            "id": outcome_id,
            "summary": summary,
            "state": state,
            "current_move": current_move,
        },
        "ask": ask,
        "proof": proof,
    }


__all__ = ["OUTCOME_SCHEMA", "OutcomeSourceError", "project_plan_outcome"]
