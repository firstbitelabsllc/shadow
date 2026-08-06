#!/usr/bin/env python3
"""Validate one closed Shadow Outcome document without side effects."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys
import unicodedata
from typing import Any
from urllib.parse import urlparse


VALIDATION_SCHEMA = "shadow.outcome-validation.v1"
DOCUMENT_SCHEMA = "shadow.outcome.v1"
MAX_INPUT_BYTES = 1_000_000
MAX_REVISION = 2_147_483_647
MAX_DEPTH = 32
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$")
RELATIVE_RE = re.compile(r"^(?!\.\.(?:/|$))(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$")
SECRET_RE = re.compile(
    r"(?:sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
PRIVATE_PATH_RE = re.compile(
    r"(?:^|[\s\"'=])(?:~/|/Users/|/home/|file:///|\$HOME(?:[/\\]|$)|[A-Za-z]:[\\/]Users[\\/])",
    re.IGNORECASE,
)
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\"'=])/(?!/)[A-Za-z0-9._-]+(?:/[^\s\"']*)?")
OUTCOME_STATES = {"working", "needs_input", "blocked", "finished_with_proof", "not_delivered"}
CATEGORIES = {"product_choice", "security", "money", "external_communication", "irreversible_action"}
PROOF_TYPES = {"test", "runtime", "ui", "release", "document", "other"}
DELIVERIES = {"delivered", "not_delivered"}


class DuplicateKey(ValueError):
    pass


def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey(key)
        result[key] = value
    return result


def issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def exact(value: Any, fields: set[str], path: str, errors: list[dict[str, str]]) -> bool:
    if type(value) is not dict:
        errors.append(issue("type", path, "expected object"))
        return False
    missing = fields - set(value)
    extra = set(value) - fields
    for key in sorted(missing):
        errors.append(issue("required", f"{path}/{key}", "required field is missing"))
    for key in sorted(extra):
        errors.append(issue("additional", f"{path}/{key}", "field is outside the closed contract"))
    return not missing and not extra


def public_text(value: Any, path: str, errors: list[dict[str, str]], *, maximum: int) -> str | None:
    if type(value) is not str or not value.strip():
        errors.append(issue("type", path, "expected nonblank string"))
        return None
    if len(value) > maximum:
        errors.append(issue("bounds", path, f"text exceeds {maximum} characters"))
    if unicodedata.normalize("NFC", value) != value:
        errors.append(issue("unicode", path, "text must be NFC-normalized"))
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
        errors.append(issue("unicode", path, "text contains a control or format character"))
    if SECRET_RE.search(value):
        errors.append(issue("privacy", path, "text contains a secret-shaped value"))
    if PRIVATE_PATH_RE.search(value) or ABSOLUTE_PATH_RE.search(value):
        errors.append(issue("privacy", path, "text contains an absolute private path"))
    return value


def identifier(value: Any, path: str, errors: list[dict[str, str]], ids: set[str]) -> None:
    text = public_text(value, path, errors, maximum=64)
    if text is None:
        return
    if ID_RE.fullmatch(text) is None:
        errors.append(issue("format", path, "identifier is not public-safe"))
    elif text in ids:
        errors.append(issue("duplicate_id", path, "identifier is already used"))
    else:
        ids.add(text)


def validate_timestamp(value: Any, errors: list[dict[str, str]]) -> None:
    if type(value) is not str or UTC_RE.fullmatch(value) is None:
        errors.append(issue("format", "/updated_at", "expected RFC3339 UTC timestamp"))
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(issue("format", "/updated_at", "timestamp is not a real date"))
        return
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        errors.append(issue("format", "/updated_at", "timestamp must be UTC"))


def validate_locator(value: Any, path: str, errors: list[dict[str, str]]) -> None:
    text = public_text(value, path, errors, maximum=512)
    if text is None:
        return
    if text.startswith("https://"):
        parsed = urlparse(text)
        if not parsed.netloc or parsed.username or parsed.password:
            errors.append(issue("format", path, "HTTPS locator is invalid"))
    elif RELATIVE_RE.fullmatch(text) is None:
        errors.append(issue("format", path, "locator must be HTTPS or repository-relative"))


def depth(value: Any, level: int = 0) -> int:
    if level > MAX_DEPTH:
        return level
    if type(value) is dict:
        return max([level, *(depth(item, level + 1) for item in value.values())])
    if type(value) is list:
        return max([level, *(depth(item, level + 1) for item in value)])
    return level


def scalar_strings(value: Any) -> list[str]:
    if type(value) is str:
        return [value]
    if type(value) is list:
        return [text for item in value for text in scalar_strings(item)]
    if type(value) is dict:
        return [text for item in value.values() for text in scalar_strings(item)]
    return []


def validate_document(root: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if depth(root) > MAX_DEPTH:
        return [issue("bounds", "", f"JSON depth exceeds {MAX_DEPTH}")]
    fields = {"schema", "revision", "updated_at", "outcome", "ask", "proof"}
    if not exact(root, fields, "", errors):
        if type(root) is not dict:
            return errors
    assert type(root) is dict
    if root.get("schema") != DOCUMENT_SCHEMA:
        errors.append(issue("const", "/schema", f"must equal {DOCUMENT_SCHEMA}"))
    revision = root.get("revision")
    if type(revision) is not int or not 0 <= revision <= MAX_REVISION:
        errors.append(issue("type", "/revision", "expected bounded integer"))
    validate_timestamp(root.get("updated_at"), errors)
    ids: set[str] = set()

    outcome = root.get("outcome")
    outcome_state = None
    if exact(outcome, {"id", "summary", "state", "current_move"}, "/outcome", errors):
        identifier(outcome["id"], "/outcome/id", errors, ids)
        public_text(outcome["summary"], "/outcome/summary", errors, maximum=280)
        outcome_state = outcome["state"]
        if outcome_state not in OUTCOME_STATES:
            errors.append(issue("enum", "/outcome/state", "unsupported Outcome state"))
        public_text(outcome["current_move"], "/outcome/current_move", errors, maximum=280)

    ask = root.get("ask")
    if ask is None:
        if outcome_state == "needs_input":
            errors.append(issue("state", "/ask", "needs_input requires an open A/B/C choice"))
    elif exact(ask, {"id", "category", "question", "options", "state", "answer_option_id"}, "/ask", errors):
        identifier(ask["id"], "/ask/id", errors, ids)
        if ask["category"] not in CATEGORIES:
            errors.append(issue("enum", "/ask/category", "unsupported choice category"))
        public_text(ask["question"], "/ask/question", errors, maximum=280)
        if ask["state"] != "open" or ask["answer_option_id"] is not None:
            errors.append(issue("state", "/ask", "the bounded choice must be open and unanswered"))
        if outcome_state != "needs_input":
            errors.append(issue("state", "/ask", "an open choice requires needs_input"))
        options = ask["options"]
        if type(options) is not list or len(options) != 3:
            errors.append(issue("bounds", "/ask/options", "choice must contain exactly A/B/C"))
        else:
            for index, option in enumerate(options):
                path = f"/ask/options/{index}"
                if exact(option, {"id", "label", "consequence"}, path, errors):
                    identifier(option["id"], f"{path}/id", errors, ids)
                    public_text(option["label"], f"{path}/label", errors, maximum=80)
                    public_text(option["consequence"], f"{path}/consequence", errors, maximum=280)

    proofs = root.get("proof")
    delivered = 0
    if type(proofs) is not list:
        errors.append(issue("type", "/proof", "expected array"))
    elif len(proofs) > 64:
        errors.append(issue("bounds", "/proof", "proof exceeds 64 references"))
    else:
        for index, proof in enumerate(proofs):
            path = f"/proof/{index}"
            if not exact(proof, {"id", "type", "locator", "verification_summary", "delivery"}, path, errors):
                continue
            identifier(proof["id"], f"{path}/id", errors, ids)
            if proof["type"] not in PROOF_TYPES:
                errors.append(issue("enum", f"{path}/type", "unsupported proof type"))
            validate_locator(proof["locator"], f"{path}/locator", errors)
            public_text(proof["verification_summary"], f"{path}/verification_summary", errors, maximum=500)
            if proof["delivery"] not in DELIVERIES:
                errors.append(issue("enum", f"{path}/delivery", "unsupported proof delivery"))
            elif proof["delivery"] == "delivered":
                delivered += 1
    if outcome_state == "finished_with_proof" and delivered == 0:
        errors.append(issue("state", "/proof", "finished_with_proof requires delivered proof"))

    strings = scalar_strings(root)
    for start in range(len(strings)):
        combined = ""
        for item in strings[start : start + 4]:
            combined += item
            if SECRET_RE.search(combined):
                errors.append(issue("privacy", "", "adjacent fields form a secret-shaped value"))
                break
    unique = {(item["code"], item["path"], item["message"]): item for item in errors}
    return sorted(unique.values(), key=lambda item: (item["path"], item["code"], item["message"]))


def result(valid: bool, errors: list[dict[str, str]]) -> dict[str, Any]:
    return {"schema": VALIDATION_SCHEMA, "valid": valid, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="-", help="JSON path or - for stdin")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with open(args.input, "rb") as stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        print(json.dumps(result(False, [issue("io", "", str(exc))]), separators=(",", ":"), sort_keys=True))
        return 2
    if len(raw) > MAX_INPUT_BYTES:
        print(json.dumps(result(False, [issue("bounds", "", "input exceeds size limit")]), separators=(",", ":"), sort_keys=True))
        return 1
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKey) as exc:
        print(json.dumps(result(False, [issue("json", "", str(exc))]), separators=(",", ":"), sort_keys=True))
        return 1
    errors = validate_document(document)
    print(json.dumps(result(not errors, errors), separators=(",", ":"), sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
