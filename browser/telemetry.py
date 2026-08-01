"""Bounded, local-only telemetry projection for Pilot Puppy.

The module creates a small OpenTelemetry-shaped event from already-known
semantic lifecycle facts. It never accepts prompts, transcripts, file content,
credentials, or machine paths. Export is disabled unless a caller explicitly
supplies a loopback endpoint; the caller still owns whether an event is sent.

This is the public contract seed for F5. It is not a collector, scheduler, or
provider runtime, and it does not claim the F5 collector gate by itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SCHEMA = "vidux.telemetry.v1"
_EVENT_RE = re.compile(r"^outcome\.(?:started|working|needs_you|finished|failed|not_delivered)$")
_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_FAILURE_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_PRIVATE_RE = re.compile(
    r"(?:/Users/|/home/|/private/var/|[A-Za-z]:[\\/]|\\\\|~/|\$HOME|file://|"
    r"\b(?:prompt|transcript|credential|secret|password|token|authorization|cookie)\b)",
    re.IGNORECASE,
)
_HOSTS = {"codex", "claude", "cursor", "unknown"}
_STATES = {
    "planned",
    "dispatched",
    "working",
    "needs_you",
    "proving",
    "finished_with_proof",
    "blocked",
    "not_delivered",
}
_PROOF_STATUSES = {"delivered", "missing", "not_delivered", "unknown"}
_ALLOWED_FIELDS = {
    "event",
    "outcome_id",
    "plan_revision",
    "native_host",
    "model_label",
    "state",
    "proof_status",
    "failure_class",
    "attempt",
    "retries",
    "compactions",
    "time_to_first_progress_ms",
    "time_to_terminal_ms",
    "at",
}
_REQUIRED_FIELDS = {"event", "outcome_id", "plan_revision", "state"}


class TelemetryInputError(ValueError):
    """Raised when an event would violate the public telemetry boundary."""


class TelemetryConfigError(ValueError):
    """Raised when export is configured outside the local-only boundary."""


def _public_text(value: Any, label: str, *, maximum: int = 120) -> str:
    if not isinstance(value, str):
        raise TelemetryInputError(f"{label} must be a string")
    text = " ".join(value.split())
    if not text:
        raise TelemetryInputError(f"{label} must be nonblank")
    if len(text) > maximum:
        raise TelemetryInputError(f"{label} exceeds {maximum} characters")
    if _PRIVATE_RE.search(text):
        raise TelemetryInputError(f"{label} contains private or implementation detail")
    return text


def _public_id(value: Any, label: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise TelemetryInputError(f"{label} must be a public identifier")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 2_147_483_647:
        raise TelemetryInputError(f"{label} must be a nonnegative integer")
    return value


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise TelemetryInputError("at must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TelemetryInputError("at must be an RFC3339 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TelemetryInputError("at must include a UTC offset")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_event(payload: Mapping[str, Any], *, at: str | None = None) -> dict[str, Any]:
    """Return one allowlisted event from bounded semantic lifecycle facts."""

    if not isinstance(payload, Mapping):
        raise TelemetryInputError("event must be an object")
    unknown = set(payload) - _ALLOWED_FIELDS
    if unknown:
        raise TelemetryInputError(f"event contains unknown fields: {', '.join(sorted(unknown))}")
    missing = _REQUIRED_FIELDS - set(payload)
    if missing:
        raise TelemetryInputError(f"event is missing fields: {', '.join(sorted(missing))}")

    event = _public_text(payload["event"], "event", maximum=40)
    if not _EVENT_RE.fullmatch(event):
        raise TelemetryInputError("event is not a supported lifecycle event")
    state = _public_text(payload["state"], "state", maximum=32)
    if state not in _STATES:
        raise TelemetryInputError("state is not a supported lifecycle state")

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "event": event,
        "outcome_id": _public_id(payload["outcome_id"], "outcome_id", _ID_RE),
        "plan_revision": _nonnegative_int(payload["plan_revision"], "plan_revision"),
        "state": state,
        "at": _timestamp(payload.get("at", at or _now())),
    }
    if "native_host" in payload:
        host = _public_text(payload["native_host"], "native_host", maximum=16)
        if host not in _HOSTS:
            raise TelemetryInputError("native_host is not a supported native host")
        result["native_host"] = host
    if "model_label" in payload:
        result["model_label"] = _public_text(payload["model_label"], "model_label")
    if "proof_status" in payload:
        proof_status = _public_text(payload["proof_status"], "proof_status", maximum=20)
        if proof_status not in _PROOF_STATUSES:
            raise TelemetryInputError("proof_status is not supported")
        result["proof_status"] = proof_status
    if "failure_class" in payload:
        result["failure_class"] = _public_id(payload["failure_class"], "failure_class", _FAILURE_RE)
    for field in (
        "attempt",
        "retries",
        "compactions",
        "time_to_first_progress_ms",
        "time_to_terminal_ms",
    ):
        if field in payload:
            result[field] = _nonnegative_int(payload[field], field)
    return result


def _unix_nanos(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return str(int(parsed.timestamp() * 1_000_000_000))


def _attribute(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def to_otlp(event: Mapping[str, Any]) -> dict[str, Any]:
    """Wrap a validated event in a small OTLP/HTTP JSON trace envelope."""

    if not isinstance(event, Mapping) or event.get("schema") != SCHEMA:
        raise TelemetryInputError("event must be built with build_event")
    payload = {key: value for key, value in event.items() if key != "schema"}
    if build_event(payload) != dict(event):
        raise TelemetryInputError("event must be built with build_event")
    event_copy = dict(event)
    timestamp = event_copy.pop("at")
    event_name = event_copy.pop("event")
    outcome_id = event_copy["outcome_id"]
    revision = event_copy["plan_revision"]
    digest = hashlib.sha256(f"{outcome_id}:{revision}:{event_name}".encode()).hexdigest()
    attributes = [_attribute(f"vidux.{key}", value) for key, value in event_copy.items()]
    start = _unix_nanos(timestamp)
    status_code = 2 if event_name in {"outcome.failed", "outcome.not_delivered"} else 1
    span = {
        "traceId": digest[:32],
        "spanId": digest[32:48],
        "name": event_name,
        "startTimeUnixNano": start,
        "endTimeUnixNano": start,
        "attributes": attributes,
        "status": {"code": status_code},
    }
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [_attribute("service.name", "vidux")]},
                "scopeSpans": [{"scope": {"name": "vidux"}, "spans": [span]}],
            }
        ]
    }


def emit_local(
    event: Mapping[str, Any],
    *,
    endpoint: str | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Send one event only to an explicitly configured loopback collector.

    With no endpoint, export is deliberately disabled and no network call is
    attempted. The opener is injectable so tests can prove the payload without
    starting a collector or contacting a service.
    """

    target = endpoint if endpoint is not None else os.environ.get("VIDUX_TELEMETRY_ENDPOINT", "")
    if not target:
        return {"status": "disabled"}
    parsed = urlparse(target)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise TelemetryConfigError("telemetry endpoint must be an explicit loopback URL")
    body = json.dumps(to_otlp(event), separators=(",", ":")).encode("utf-8")
    request = Request(target, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with opener(request, timeout=2) as response:
        response_status = getattr(response, "status", None)
        status = int(response_status if response_status is not None else response.getcode())
    if status < 200 or status >= 300:
        raise TelemetryConfigError(f"telemetry collector returned HTTP {status}")
    return {"status": "sent", "status_code": status}


__all__ = [
    "SCHEMA",
    "TelemetryConfigError",
    "TelemetryInputError",
    "build_event",
    "emit_local",
    "to_otlp",
]
