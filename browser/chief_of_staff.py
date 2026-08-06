"""Pure Chief-of-Staff projection for the Shadow semantic boundary.

The Chief of Staff is a report, not another runtime.  This module accepts the
same validated ``shadow.outcome.v1`` document used by the decision view and an optional,
already-redacted plan summary.  It returns one bounded, provider-neutral brief
that a desk view and a compact client can render identically.

It does not read plans, write receipts, invoke hosts, choose providers, or keep
transcripts.  The caller owns validation and durable foldback.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

try:  # The browser server runs with its sibling directory on sys.path.
    from decision_mode import DecisionInputError, project_decision
except ModuleNotFoundError:  # Also support ``import browser.chief_of_staff``.
    from browser.decision_mode import DecisionInputError, project_decision


BRIEF_SCHEMA = "shadow.chief-of-staff.v1"
MAX_TEXT = 280
PRIVATE_TEXT_RE = re.compile(
    r"(?:/Users/|/home/|/private/var/|[A-Za-z]:[\\/]|\\\\|~/|\$HOME|file://|"
    r"\b(?:provider|model|prompt|transcript|credential|secret|password|token)\b|"
    r"sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)

_STATE_MAP = {
    "working": "working",
    "needs_input": "needs_you",
    "blocked": "blocked",
    "finished_with_proof": "finished_with_proof",
    "not_delivered": "not_delivered",
}


def _public_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise DecisionInputError(f"{label} must be a string")
    text = " ".join(value.split())
    if not text:
        raise DecisionInputError(f"{label} must be nonblank")
    if len(text) > MAX_TEXT:
        raise DecisionInputError(f"{label} exceeds {MAX_TEXT} characters")
    if PRIVATE_TEXT_RE.search(text):
        raise DecisionInputError(f"{label} contains private or implementation detail")
    return text


def _plan_brief(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DecisionInputError("plan_brief must be an object")
    allowed = {"summary", "latest_change", "latest_decision", "recommendation"}
    if set(value) - allowed:
        raise DecisionInputError("plan_brief contains an unknown field")
    return {
        key: _public_text(raw, f"plan_brief.{key}")
        for key, raw in value.items()
        if raw is not None
    }


def _state(outcome_state: str) -> str:
    try:
        return _STATE_MAP[outcome_state]
    except KeyError as exc:  # project_decision normally catches this via text validation.
        raise DecisionInputError("outcome.state is not a supported public state") from exc


def _recommendation(state: str, *, has_proof: bool, has_choice: bool) -> str:
    if state == "needs_you" or has_choice:
        return "Choose one of the listed options."
    if state == "blocked":
        return "Address the blocker before continuing."
    if state == "not_delivered":
        return "Review the non-delivery proof before retrying."
    if state == "finished_with_proof":
        return "Review the proof and keep the outcome closed."
    return "Continue the current move."


def project_chief_of_staff(document: Any, *, plan_brief: Any = None) -> dict[str, Any]:
    """Return one bounded five-question brief from the shared semantic source.

    ``plan_brief`` is a tiny, already-redacted projection of the owning plan;
    it is never read from disk here.  The returned ``proof`` is limited to one
    reference and ``choices`` to three options so the same payload works for a
    desk report and a voice client.
    """

    decision = project_decision(document)
    plan = _plan_brief(plan_brief)
    outcome = decision["outcome"]
    state = _state(outcome["state"])
    ask = decision["ask"]
    choices = []
    if ask is not None and ask["state"] == "open":
        choices = [
            {
                "id": option["id"],
                "label": option["label"],
                "consequence": option["consequence"],
            }
            for option in ask["options"][:3]
        ]

    proof = next((item for item in decision["proof"] if item["delivery"] == "delivered"), None)
    if proof is None and decision["proof"]:
        proof = decision["proof"][0]

    changed = plan.get("latest_change") or outcome.get("current_move") or outcome["summary"]
    matters = plan.get("summary") or outcome["summary"]
    blocker = None
    action = None
    if state == "needs_you" and ask is not None:
        blocker = ask["question"]
        action = "Choose one option for the next move."
    elif state == "blocked":
        blocker = outcome.get("current_move") or "The outcome is blocked."
        action = "Review the blocker and choose the next move."
    elif state == "not_delivered":
        blocker = "The last move did not deliver a terminal result."
        action = "Review the non-delivery proof before retrying."

    recommendation = plan.get("recommendation") or _recommendation(
        state,
        has_proof=proof is not None,
        has_choice=bool(choices),
    )
    brief = {
        "schema": BRIEF_SCHEMA,
        "revision": decision["revision"],
        "outcome_id": outcome["id"],
        "state": state,
        "changed": _public_text(changed, "changed"),
        "matters": _public_text(matters, "matters"),
        "blocker": _public_text(blocker, "blocker") if blocker else None,
        "action": _public_text(action, "action") if action else None,
        "recommendation": _public_text(recommendation, "recommendation"),
        "choices": choices,
        "proof": proof,
    }
    return brief


__all__ = ["BRIEF_SCHEMA", "project_chief_of_staff"]
