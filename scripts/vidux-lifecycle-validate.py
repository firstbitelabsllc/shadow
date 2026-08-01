#!/usr/bin/env python3
"""Read-only validator for the vidux.lifecycle.v1 transition receipt."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timezone
from typing import Any

VALIDATION_SCHEMA = "vidux.lifecycle-validation.v1"
DOCUMENT_SCHEMA = "vidux.lifecycle.v1"
MAX_INPUT_BYTES = 1 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_REVISION = 2147483647
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
RFC3339_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$"
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
SECRET_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|sk-ant-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
    r"ASIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
HOME_PATH_RE = re.compile(
    r"(?:^|[\s\"'=])(?:~/|/Users/|/home/|[A-Za-z]:[\\/]Users[\\/]|file://|\$(?:HOME|\{HOME\})(?:[/\\]|$))",
    re.IGNORECASE,
)
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\"'=])/(?!/)[A-Za-z0-9._-]+(?:/[^\s\"']*)?")
FORBIDDEN_KEY_FRAGMENTS = (
    "prompt",
    "transcript",
    "secret",
    "password",
    "credential",
    "provider",
    "model",
    "host",
    "account",
    "quota",
    "command",
    "shell",
    "raw",
)
STATES = frozenset(
    {
        "planned",
        "dispatched",
        "working",
        "needs_you",
        "proving",
        "blocked",
        "finished_with_proof",
        "not_delivered",
        "handed_off",
    }
)
ACTORS = frozenset({"pilot", "native_host", "user", "system"})
TERMINAL_STATES = frozenset({"finished_with_proof", "not_delivered", "handed_off"})
ALLOWED_TRANSITIONS = {
    "planned": {"dispatched", "blocked", "not_delivered"},
    "dispatched": {"working", "blocked", "not_delivered"},
    "working": {"needs_you", "proving", "blocked", "not_delivered"},
    "needs_you": {"working", "dispatched", "blocked", "not_delivered"},
    "proving": {"finished_with_proof", "blocked", "not_delivered"},
    "blocked": {"dispatched", "working", "needs_you", "not_delivered"},
    "finished_with_proof": set(),
    "not_delivered": set(),
    "handed_off": set(),
}
TOP_LEVEL_FIELDS = {
    "schema",
    "revision",
    "outcome_id",
    "plan_revision",
    "updated_at",
    "events",
}
EVENT_FIELDS = {
    "id",
    "from_state",
    "to_state",
    "at",
    "actor",
    "summary",
    "proof_ref",
}


def json_pointer(parts: list[str | int]) -> str:
    return "".join(
        "/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts
    )


def result_payload(valid: bool, errors: list[dict[str, str]]) -> dict[str, Any]:
    ordered = sorted(
        errors,
        key=lambda item: (item.get("path", ""), item.get("code", ""), item.get("message", "")),
    )
    return {"errors": ordered, "schema": VALIDATION_SCHEMA, "valid": valid}


def emit(payload: dict[str, Any], exit_code: int) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    sys.stdout.write("\n")
    return exit_code


def add(errors: list[dict[str, str]], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def parse_timestamp(value: Any, path: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or not RFC3339_UTC_RE.fullmatch(value):
        add(errors, "timestamp", path, "must be an RFC 3339 UTC timestamp ending in Z")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        add(errors, "timestamp", path, "must be a real calendar timestamp")
        return
    if parsed.tzinfo != timezone.utc:
        add(errors, "timestamp", path, "must use UTC")


def check_string(value: Any, path: str, errors: list[dict[str, str]], *, max_length: int) -> None:
    if not isinstance(value, str):
        add(errors, "type", path, "must be a string")
        return
    if not value.strip() or len(value) > max_length:
        add(errors, "string", path, f"must be nonblank and at most {max_length} characters")
    if CONTROL_CHAR_RE.search(value):
        add(errors, "control_character", path, "must not contain control characters")
    if any(unicodedata.category(char) in {"Cf", "Cc"} for char in value):
        add(errors, "unsafe_unicode", path, "must not contain format or control characters")
    if value != unicodedata.normalize("NFC", value):
        add(errors, "non_nfc", path, "must use NFC-normalized Unicode")
    if HOME_PATH_RE.search(value) or ABSOLUTE_PATH_RE.search(value):
        add(errors, "absolute_path", path, "must not contain an absolute or home-relative path")
    if SECRET_RE.search(value):
        add(errors, "secret", path, "must not contain a credential or secret token")


def walk_privacy(value: Any, parts: list[str | int], errors: list[dict[str, str]], depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        add(errors, "depth", json_pointer(parts), f"JSON nesting exceeds {MAX_JSON_DEPTH} levels")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = json_pointer(parts + [key])
            lowered = key.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                add(errors, "forbidden_field", key_path, "field is outside the public receipt boundary")
            walk_privacy(child, parts + [key], errors, depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_privacy(child, parts + [index], errors, depth + 1)
    elif isinstance(value, str):
        check_string(value, json_pointer(parts), errors, max_length=4096)
    elif isinstance(value, float) and not math.isfinite(value):
        add(errors, "number", json_pointer(parts), "must be finite")


def validate(document: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(document, dict):
        add(errors, "type", "", "document must be an object")
        return errors
    unknown = sorted(set(document) - TOP_LEVEL_FIELDS)
    for key in unknown:
        add(errors, "unknown_field", json_pointer([key]), "field is not allowed")
    required = TOP_LEVEL_FIELDS - set(document)
    for key in sorted(required):
        add(errors, "missing_field", json_pointer([key]), "field is required")
    if document.get("schema") != DOCUMENT_SCHEMA:
        add(errors, "schema", "/schema", f"must equal {DOCUMENT_SCHEMA}")
    for key in ("revision", "plan_revision"):
        value = document.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_REVISION:
            add(errors, "type", f"/{key}", "must be an integer from 0 through 2147483647")
    for key in ("outcome_id",):
        value = document.get(key)
        if not isinstance(value, str) or not ID_RE.fullmatch(value):
            add(errors, "identifier", f"/{key}", "must match the public identifier pattern")
    parse_timestamp(document.get("updated_at"), "/updated_at", errors)
    events = document.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= 32:
        add(errors, "array", "/events", "must contain between 1 and 32 events")
        events = []
    seen_ids: set[str] = set()
    previous_state: str | None = None
    previous_terminal = False
    for index, event in enumerate(events):
        path = f"/events/{index}"
        if not isinstance(event, dict):
            add(errors, "type", path, "event must be an object")
            continue
        for key in sorted(set(event) - EVENT_FIELDS):
            add(errors, "unknown_field", json_pointer(["events", index, key]), "field is not allowed")
        for key in sorted(EVENT_FIELDS - set(event)):
            add(errors, "missing_field", json_pointer(["events", index, key]), "field is required")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not ID_RE.fullmatch(event_id):
            add(errors, "identifier", f"{path}/id", "must match the public identifier pattern")
        elif event_id in seen_ids:
            add(errors, "duplicate_id", f"{path}/id", "event IDs must be unique")
        else:
            seen_ids.add(event_id)
        from_state = event.get("from_state")
        to_state = event.get("to_state")
        if from_state is not None and from_state not in STATES:
            add(errors, "state", f"{path}/from_state", "must be null or a known lifecycle state")
        if to_state not in STATES:
            add(errors, "state", f"{path}/to_state", "must be a known lifecycle state")
        parse_timestamp(event.get("at"), f"{path}/at", errors)
        if event.get("actor") not in ACTORS:
            add(errors, "actor", f"{path}/actor", "must be a provider-neutral actor")
        check_string(event.get("summary"), f"{path}/summary", errors, max_length=280)
        proof_ref = event.get("proof_ref")
        if proof_ref is not None and (not isinstance(proof_ref, str) or not ID_RE.fullmatch(proof_ref)):
            add(errors, "identifier", f"{path}/proof_ref", "must be null or a public identifier")
        if index == 0:
            if from_state is not None:
                add(errors, "sequence", f"{path}/from_state", "first event must start from null")
            if to_state != "planned":
                add(errors, "sequence", f"{path}/to_state", "first event must enter planned")
        else:
            if from_state != previous_state:
                add(errors, "sequence", f"{path}/from_state", "must equal the previous event's to_state")
            if previous_terminal:
                add(errors, "sequence", path, "terminal lifecycle states cannot have later events")
            if isinstance(previous_state, str) and to_state in STATES:
                if to_state not in ALLOWED_TRANSITIONS.get(previous_state, set()):
                    add(errors, "transition", f"{path}/to_state", f"transition from {previous_state} is not allowed")
        if to_state in TERMINAL_STATES and proof_ref is None:
            add(errors, "proof_required", f"{path}/proof_ref", "terminal events require a proof reference")
        if to_state not in TERMINAL_STATES and proof_ref is not None:
            add(errors, "proof_early", f"{path}/proof_ref", "proof references are only allowed on terminal events")
        previous_state = to_state if isinstance(to_state, str) else previous_state
        previous_terminal = to_state in TERMINAL_STATES
    if events and isinstance(events[-1], dict) and document.get("updated_at") != events[-1].get("at"):
        add(errors, "updated_at", "/updated_at", "must equal the timestamp of the last event")
    walk_privacy(document, [], errors)
    return sorted(errors, key=lambda item: (item["path"], item["code"], item["message"]))


def parse_json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--input", default="-")
    try:
        args, extra = parser.parse_known_args()
        if extra:
            raise ValueError("unknown arguments")
    except (SystemExit, ValueError):
        return emit(result_payload(False, [{"code": "usage", "path": "", "message": "invalid command line"}]), 2)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with open(args.input, "rb") as handle:
                raw = handle.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            return emit(result_payload(False, [{"code": "size_error", "path": "", "message": "input exceeds 1 MiB"}]), 2)
        document = parse_json(raw)
    except FileNotFoundError:
        return emit(result_payload(False, [{"code": "io_error", "path": "", "message": "input file not found"}]), 2)
    except (OSError, UnicodeDecodeError) as exc:
        return emit(result_payload(False, [{"code": "io_error", "path": "", "message": str(exc)}]), 2)
    except (json.JSONDecodeError, ValueError) as exc:
        return emit(result_payload(False, [{"code": "parse_error", "path": "", "message": str(exc)}]), 2)
    errors = validate(document)
    return emit(result_payload(not errors, errors), 1 if errors else 0)


if __name__ == "__main__":
    raise SystemExit(main())
