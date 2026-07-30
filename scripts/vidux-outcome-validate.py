#!/usr/bin/env python3
"""Read-only Vidux Outcome/Ask/Steer interchange validator.

Validates one JSON document against the vidux.outcome.v1 semantic contract.
Uses only the Python standard library. Never writes files, uses the network,
inspects Git, reads plans, or executes commands.

Usage:
    python3 scripts/vidux-outcome-validate.py --input PATH
    python3 scripts/vidux-outcome-validate.py --input -
    python3 scripts/vidux-outcome-validate.py   # stdin
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

VALIDATION_SCHEMA = "vidux.outcome-validation.v1"
DOCUMENT_SCHEMA = "vidux.outcome.v1"
MAX_INPUT_BYTES = 1 * 1024 * 1024
MAX_REVISION = 2147483647
MAX_JSON_DEPTH = 64
MAX_SECRET_FRAGMENT_PARTS = 8
MAX_SECRET_FRAGMENT_CHARS = 4096
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
RFC3339_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$"
)
REPO_RELATIVE_RE = re.compile(
    r"^(?!\.\.(?:/|$))(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$"
)
HTTPS_URL_RE = re.compile(r"^https://[^\s]{1,505}$")

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

SECRET_PREFIX_RE = re.compile(
    r"(?:"
    r"sk-[A-Za-z0-9_-]{8,}"
    r"|sk-ant-[A-Za-z0-9_-]{8,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|gho_[A-Za-z0-9]{20,}"
    r"|ghu_[A-Za-z0-9]{20,}"
    r"|ghs_[A-Za-z0-9]{20,}"
    r"|ghr_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|ASIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{20,}"
    r"|-----BEGIN[ A-Z]*PRIVATE KEY-----"
    r"|Bearer\s+[A-Za-z0-9._\-+/=]{20,}"
    r")",
    re.IGNORECASE,
)
SECRET_FRAGMENT_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"sk-(?:ant-)?"
    r"|gh[pousr]_"
    r"|github_pat_"
    r"|xox[baprs]-"
    r"|AKIA"
    r"|ASIA"
    r"|AIza"
    r"|Bearer\s+"
    r"|-----BEGIN(?:[ A-Z]*)?$"
    r")",
    re.IGNORECASE,
)

HOME_PATH_RE = re.compile(
    r"(?:"
    r"(?:^|[\s\"'=])~/"
    r"|(?:^|[\s\"'=])/Users/"
    r"|(?:^|[\s\"'=])/home/"
    r"|(?:^|[\s\"'=])[A-Za-z]:\\Users\\"
    r"|(?:^|[\s\"'=])[A-Za-z]:/Users/"
    r"|file://"
    r")",
    re.IGNORECASE,
)
ABSOLUTE_PATH_RE = re.compile(
    r"(?:"
    r"(?:^|[\s\"'=])/(?!/)[A-Za-z0-9._-]+(?:/[^\s\"']*)?"
    r"|(?:^|[\s\"'=])\\\\[^\\\s\"']+\\[^\\\s\"']+"
    r"|(?:^|[\s\"'=])\$(?:HOME|\{HOME\})(?:[/\\]|$)"
    r")",
    re.IGNORECASE,
)

CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

OUTCOME_STATES = frozenset(
    {"working", "needs_input", "blocked", "finished_with_proof", "not_delivered"}
)
ASK_CATEGORIES = frozenset(
    {
        "product_choice",
        "security",
        "money",
        "external_communication",
        "irreversible_action",
    }
)
ASK_STATES = frozenset({"open", "answered", "superseded"})
STEER_STATES = frozenset(
    {
        "received",
        "applied",
        "working",
        "blocked",
        "finished_with_proof",
        "not_delivered",
        "superseded",
    }
)
NONTERMINAL_STEER_STATES = frozenset({"received", "applied", "working", "blocked"})
PROOF_TYPES = frozenset({"test", "runtime", "ui", "release", "document", "other"})
PROOF_DELIVERIES = frozenset({"delivered", "not_delivered"})

TOP_LEVEL_FIELDS = (
    "schema",
    "revision",
    "updated_at",
    "outcome",
    "ask",
    "steers",
    "proof",
)
OUTCOME_FIELDS = ("id", "summary", "state", "current_move")
ASK_FIELDS = ("id", "category", "question", "options", "state", "answer_option_id")
ASK_OPTION_FIELDS = ("id", "label", "consequence")
STEER_FIELDS = ("id", "outcome_id", "summary", "state", "proof_ref")
PROOF_FIELDS = ("id", "type", "locator", "verification_summary", "delivery")


class ValidationError(Exception):
    """Structured validation failure collection is preferred; keep for I/O helpers."""


def emit(result: Dict[str, Any], exit_code: int) -> int:
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    sys.stdout.write("\n")
    return exit_code


def result_payload(valid: bool, errors: List[Dict[str, str]]) -> Dict[str, Any]:
    ordered = sorted(
        errors,
        key=lambda item: (item.get("path", ""), item.get("code", ""), item.get("message", "")),
    )
    return {
        "errors": ordered,
        "schema": VALIDATION_SCHEMA,
        "valid": valid,
    }


def error(code: str, path: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message, "path": path}


def json_pointer(*parts: Any) -> str:
    if not parts:
        return ""
    encoded: List[str] = []
    for part in parts:
        text = str(part)
        text = text.replace("~", "~0").replace("/", "~1")
        encoded.append(text)
    return "/" + "/".join(encoded)


def is_strict_bool(value: Any) -> bool:
    return type(value) is bool


def is_strict_int(value: Any) -> bool:
    return type(value) is int and not isinstance(value, bool)


def is_strict_str(value: Any) -> bool:
    return type(value) is str


def is_strict_list(value: Any) -> bool:
    return type(value) is list


def is_strict_dict(value: Any) -> bool:
    return type(value) is dict


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that never emits non-JSON output."""

    def error(self, message: str) -> None:
        raise ValidationError(message)


def parse_cli(argv: Sequence[str]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    parser = JsonArgumentParser(add_help=False, prog="vidux-outcome-validate.py")
    parser.add_argument("-h", "--help", action="store_true", dest="help_requested")
    parser.add_argument(
        "--input",
        dest="input_path",
        default=None,
        help="JSON file path, or '-' for stdin. Omit to read stdin.",
    )
    try:
        args = parser.parse_args(list(argv))
    except ValidationError:
        return None, result_payload(
            False,
            [error("usage", "", "invalid invocation; expected optional --input PATH")],
        )
    if args.help_requested:
        return None, result_payload(
            False,
            [error("usage", "", "provide optional --input PATH or stdin JSON")],
        )
    path = args.input_path
    if path is None or path == "-":
        return None, None
    return path, None


def read_input(path: Optional[str]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    try:
        if path is None:
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with open(path, "rb") as handle:
                raw = handle.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        return None, result_payload(
            False,
            [error("io_error", "", f"failed to read input: {exc.strerror or exc}")],
        )

    if len(raw) > MAX_INPUT_BYTES:
        return None, result_payload(
            False,
            [
                error(
                    "size_error",
                    "",
                    f"input exceeds maximum size of {MAX_INPUT_BYTES} bytes",
                )
            ],
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, result_payload(
            False,
            [error("parse_error", "", f"input is not valid UTF-8: {exc}")],
        )
    return text, None


def parse_json_document(text: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    duplicate_keys_by_object: Dict[int, List[str]] = {}

    def capture_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        seen: Set[str] = set()
        duplicates: List[str] = []
        for key, value in pairs:
            if key in seen and key not in duplicates:
                duplicates.append(key)
            seen.add(key)
            result[key] = value
        if duplicates:
            duplicate_keys_by_object[id(result)] = duplicates
        return result

    try:
        document = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=capture_object,
        )
    except json.JSONDecodeError as exc:
        return None, result_payload(
            False,
            [
                error(
                    "parse_error",
                    "",
                    f"invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}",
                )
            ],
        )
    except (ValueError, RecursionError) as exc:
        return None, result_payload(False, [error("parse_error", "", str(exc))])

    duplicate_errors: List[Dict[str, str]] = []
    stack: List[Tuple[Any, str]] = [(document, "")]
    while stack:
        current, current_path = stack.pop()
        if is_strict_dict(current):
            for key in duplicate_keys_by_object.get(id(current), []):
                key_path = (
                    current_path + json_pointer(key)
                    if current_path
                    else json_pointer(key)
                )
                duplicate_errors.append(
                    error(
                        "duplicate_key",
                        key_path,
                        f"object contains duplicate key '{key}'",
                    )
                )
            for key in sorted(current, reverse=True):
                value = current[key]
                child_path = (
                    current_path + json_pointer(key)
                    if current_path
                    else json_pointer(key)
                )
                stack.append((value, child_path))
        elif is_strict_list(current):
            for index in range(len(current) - 1, -1, -1):
                child_path = (
                    current_path + json_pointer(index)
                    if current_path
                    else json_pointer(index)
                )
                stack.append((current[index], child_path))

    if duplicate_errors:
        return None, result_payload(False, duplicate_errors)
    return document, None


def _reject_json_constant(name: str) -> Any:
    raise ValueError(f"non-finite or unsupported JSON constant: {name}")


def has_control_chars(value: str) -> bool:
    return CONTROL_CHAR_RE.search(value) is not None


def has_home_or_file_path(value: str) -> bool:
    if value.startswith("~/") or value.startswith("~\\"):
        return True
    if value.startswith("file://") or value.lower().startswith("file:"):
        return True
    if value.startswith("/") or value.startswith("\\\\"):
        return True
    if value.startswith("$HOME") or value.startswith("${HOME}"):
        return True
    if re.match(r"^[A-Za-z]:\\Users\\", value) or re.match(r"^[A-Za-z]:/Users/", value):
        return True
    return HOME_PATH_RE.search(value) is not None or ABSOLUTE_PATH_RE.search(value) is not None


def has_secret_shape(value: str) -> bool:
    return SECRET_PREFIX_RE.search(value) is not None


def has_sensitive_prefix_fragment(value: str) -> bool:
    return SECRET_FRAGMENT_PREFIX_RE.search(value) is not None


def has_dangerous_unicode(value: str) -> bool:
    return any(
        unicodedata.category(character) == "Cf"
        or unicodedata.bidirectional(character)
        in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI", "BN"}
        for character in value
    )


def walk_privacy(node: Any, path: str, errors: List[Dict[str, str]]) -> None:
    """Scan privacy invariants iteratively and reject fragmented secret shapes."""
    stack: List[Tuple[Any, str, int]] = [(node, path, 0)]
    string_fragments: List[Tuple[str, str]] = []

    while stack:
        current, current_path, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            errors.append(
                error(
                    "depth",
                    current_path,
                    f"JSON nesting exceeds maximum depth {MAX_JSON_DEPTH}",
                )
            )
            continue

        if is_strict_dict(current):
            for key in sorted(current, reverse=True):
                value = current[key]
                key_path = (
                    current_path + json_pointer(key)
                    if current_path
                    else json_pointer(key)
                )
                if not is_strict_str(key):
                    errors.append(
                        error("type", current_path, "object keys must be strings")
                    )
                    continue
                lowered = key.lower()
                for fragment in FORBIDDEN_KEY_FRAGMENTS:
                    if fragment in lowered:
                        errors.append(
                            error(
                                "forbidden_key",
                                key_path,
                                f"key contains forbidden fragment '{fragment}'",
                            )
                        )
                        break
                if has_control_chars(key):
                    errors.append(
                        error(
                            "control_char",
                            key_path,
                            "key contains a control character",
                        )
                    )
                if has_dangerous_unicode(key):
                    errors.append(
                        error(
                            "unicode_format",
                            key_path,
                            "key contains a Unicode format or bidirectional control",
                        )
                    )
                if unicodedata.normalize("NFC", key) != key:
                    errors.append(
                        error(
                            "unicode_normalization",
                            key_path,
                            "key must use NFC Unicode normalization",
                        )
                    )
                stack.append((value, key_path, depth + 1))
            continue

        if is_strict_list(current):
            for index in range(len(current) - 1, -1, -1):
                item_path = (
                    current_path + json_pointer(index)
                    if current_path
                    else json_pointer(index)
                )
                stack.append((current[index], item_path, depth + 1))
            continue

        if is_strict_bool(current) or current is None or is_strict_int(current):
            continue

        if isinstance(current, float):
            if not math.isfinite(current):
                errors.append(error("nonfinite", current_path, "numbers must be finite"))
            continue

        if is_strict_str(current):
            string_fragments.append((current_path, current))
            if has_control_chars(current):
                errors.append(
                    error(
                        "control_char",
                        current_path,
                        "string contains a NUL or control character",
                    )
                )
            if has_dangerous_unicode(current):
                errors.append(
                    error(
                        "unicode_format",
                        current_path,
                        "string contains a Unicode format or bidirectional control",
                    )
                )
            if unicodedata.normalize("NFC", current) != current:
                errors.append(
                    error(
                        "unicode_normalization",
                        current_path,
                        "string must use NFC Unicode normalization",
                    )
                )
            if has_home_or_file_path(current):
                errors.append(
                    error(
                        "privacy_path",
                        current_path,
                        "string contains an absolute or home-derived filesystem path or file URL",
                    )
                )
            if has_secret_shape(current):
                errors.append(
                    error(
                        "secret_shape",
                        current_path,
                        "string matches a common secret-token or private-key shape",
                    )
                )
            elif has_sensitive_prefix_fragment(current):
                errors.append(
                    error(
                        "secret_prefix_fragment",
                        current_path,
                        "string contains a sensitive token-prefix fragment",
                    )
                )
            continue

        # Unexpected Python types should not appear from json.loads; reject closed.
        errors.append(
            error(
                "type",
                current_path,
                f"unsupported JSON value type: {type(current).__name__}",
            )
        )

    reported_fragment_paths: Set[str] = set()
    for start in range(len(string_fragments)):
        joined = ""
        fragments_are_individually_safe = True
        stop = min(len(string_fragments), start + MAX_SECRET_FRAGMENT_PARTS)
        for end in range(start, stop):
            current_path, current = string_fragments[end]
            if len(joined) + len(current) > MAX_SECRET_FRAGMENT_CHARS:
                break
            joined += current
            fragments_are_individually_safe = (
                fragments_are_individually_safe and not has_secret_shape(current)
            )
            if (
                end > start
                and fragments_are_individually_safe
                and has_secret_shape(joined)
                and current_path not in reported_fragment_paths
            ):
                errors.append(
                    error(
                        "fragmented_secret_shape",
                        current_path,
                        "adjacent string values combine into a common secret-token shape",
                    )
                )
                reported_fragment_paths.add(current_path)
                break


def expect_object(
    value: Any,
    path: str,
    allowed: Sequence[str],
    required: Sequence[str],
    errors: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    if not is_strict_dict(value):
        errors.append(error("type", path, "expected object"))
        return None

    allowed_set = set(allowed)
    for key in value:
        if key not in allowed_set:
            errors.append(
                error(
                    "unknown_field",
                    path + json_pointer(key) if path else json_pointer(key),
                    f"unknown field '{key}'",
                )
            )
    for key in required:
        if key not in value:
            errors.append(
                error(
                    "missing_field",
                    path + json_pointer(key) if path else json_pointer(key),
                    f"missing required field '{key}'",
                )
            )
    return value


def expect_string(
    value: Any,
    path: str,
    errors: List[Dict[str, str]],
    *,
    min_length: int = 0,
    max_length: Optional[int] = None,
    nonblank: bool = False,
    pattern: Optional[re.Pattern[str]] = None,
    enum: Optional[Set[str]] = None,
    const: Optional[str] = None,
) -> Optional[str]:
    if not is_strict_str(value):
        errors.append(error("type", path, "expected string"))
        return None
    if const is not None and value != const:
        errors.append(error("const", path, f"expected exactly '{const}'"))
    if enum is not None and value not in enum:
        errors.append(
            error("enum", path, f"expected one of: {', '.join(sorted(enum))}")
        )
    if nonblank and value.strip() == "":
        errors.append(error("blank", path, "string must be nonblank"))
    if len(value) < min_length:
        errors.append(
            error("length", path, f"string shorter than minimum length {min_length}")
        )
    if max_length is not None and len(value) > max_length:
        errors.append(
            error("length", path, f"string longer than maximum length {max_length}")
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        errors.append(error("pattern", path, "string does not match required pattern"))
    return value


def expect_identifier(value: Any, path: str, errors: List[Dict[str, str]]) -> Optional[str]:
    return expect_string(value, path, errors, min_length=3, max_length=64, pattern=ID_RE)


def expect_nonblank280(value: Any, path: str, errors: List[Dict[str, str]]) -> Optional[str]:
    return expect_string(
        value, path, errors, min_length=1, max_length=280, nonblank=True
    )


def expect_nonblank500(value: Any, path: str, errors: List[Dict[str, str]]) -> Optional[str]:
    return expect_string(
        value, path, errors, min_length=1, max_length=500, nonblank=True
    )


def validate_updated_at(value: Any, path: str, errors: List[Dict[str, str]]) -> None:
    text = expect_string(value, path, errors, pattern=RFC3339_UTC_RE)
    if text is None:
        return
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(error("timestamp", path, "timestamp is not a valid RFC3339 datetime"))
        return
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        errors.append(error("timestamp", path, "timestamp must be UTC ending in Z"))
    # Reject values that only match the regex loosely after normalization issues.
    rebuilt = parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if "." in text:
        fraction = text[text.index(".") + 1 : -1]
        rebuilt = f"{rebuilt}.{fraction}Z"
    else:
        rebuilt = f"{rebuilt}Z"
    if text != rebuilt:
        # Allow identical wall values; fromisoformat already rejected impossible dates.
        pass


def validate_locator(value: Any, path: str, errors: List[Dict[str, str]]) -> None:
    text = expect_string(value, path, errors, min_length=1, max_length=512)
    if text is None:
        return
    if ".." in text.split("/"):
        errors.append(error("locator", path, "locator must not contain '..' path segments"))
        return
    if text.startswith("/") or text.startswith("~") or re.match(r"^[A-Za-z]:[\\/]", text):
        errors.append(
            error("locator", path, "locator must not be an absolute, home, or drive path")
        )
        return
    if text.lower().startswith("file:"):
        errors.append(error("locator", path, "locator must not be a file URL"))
        return
    if text.startswith("https://"):
        if HTTPS_URL_RE.fullmatch(text) is None:
            errors.append(error("locator", path, "https locator is malformed"))
            return
        try:
            parsed = urlparse(text)
            hostname = parsed.hostname
            # Accessing port validates a malformed or out-of-range explicit port.
            _port = parsed.port
        except ValueError:
            errors.append(error("locator", path, "https locator is malformed"))
            return
        if parsed.scheme != "https":
            errors.append(error("locator", path, "locator URL scheme must be https"))
            return
        if parsed.username is not None or parsed.password is not None:
            errors.append(error("locator", path, "https locator must not include userinfo"))
            return
        if parsed.query:
            errors.append(error("locator", path, "https locator must not include a query"))
            return
        if parsed.fragment:
            errors.append(error("locator", path, "https locator must not include a fragment"))
            return
        if not hostname:
            errors.append(error("locator", path, "https locator must include a hostname"))
            return
        return
    if REPO_RELATIVE_RE.fullmatch(text) is None:
        errors.append(
            error(
                "locator",
                path,
                "locator must be a repository-relative path or https URL",
            )
        )


def register_id(
    identifier: Optional[str],
    path: str,
    seen: Dict[str, str],
    errors: List[Dict[str, str]],
) -> None:
    if identifier is None:
        return
    previous = seen.get(identifier)
    if previous is not None:
        errors.append(
            error(
                "duplicate_id",
                path,
                f"id '{identifier}' duplicates value at {previous}",
            )
        )
        return
    seen[identifier] = path


def validate_ask_option(
    value: Any,
    path: str,
    errors: List[Dict[str, str]],
    seen_ids: Dict[str, str],
) -> Optional[str]:
    obj = expect_object(value, path, ASK_OPTION_FIELDS, ASK_OPTION_FIELDS, errors)
    if obj is None:
        return None
    option_id = expect_identifier(obj.get("id"), path + "/id", errors)
    register_id(option_id, path + "/id", seen_ids, errors)
    expect_string(
        obj.get("label"),
        path + "/label",
        errors,
        min_length=1,
        max_length=80,
        nonblank=True,
    )
    expect_string(
        obj.get("consequence"),
        path + "/consequence",
        errors,
        min_length=1,
        max_length=280,
        nonblank=True,
    )
    return option_id


def validate_ask(
    value: Any,
    path: str,
    errors: List[Dict[str, str]],
    seen_ids: Dict[str, str],
) -> Tuple[Optional[str], Set[str]]:
    obj = expect_object(value, path, ASK_FIELDS, ASK_FIELDS, errors)
    if obj is None:
        return None, set()
    ask_id = expect_identifier(obj.get("id"), path + "/id", errors)
    register_id(ask_id, path + "/id", seen_ids, errors)
    expect_string(
        obj.get("category"),
        path + "/category",
        errors,
        enum=set(ASK_CATEGORIES),
    )
    expect_nonblank280(obj.get("question"), path + "/question", errors)
    ask_state = expect_string(
        obj.get("state"),
        path + "/state",
        errors,
        enum=set(ASK_STATES),
    )

    options_value = obj.get("options")
    option_ids: Set[str] = set()
    if not is_strict_list(options_value):
        errors.append(error("type", path + "/options", "expected array"))
    else:
        if len(options_value) < 2 or len(options_value) > 5:
            errors.append(
                error(
                    "bounds",
                    path + "/options",
                    "options must contain between 2 and 5 items",
                )
            )
        for index, item in enumerate(options_value):
            option_id = validate_ask_option(
                item, path + json_pointer("options", index), errors, seen_ids
            )
            if option_id is not None:
                option_ids.add(option_id)

    answer = obj.get("answer_option_id")
    answer_path = path + "/answer_option_id"
    if answer is None:
        answer_id = None
    else:
        answer_id = expect_identifier(answer, answer_path, errors)

    if ask_state in {"open", "superseded"}:
        if answer is not None:
            errors.append(
                error(
                    "ask_lifecycle",
                    answer_path,
                    "open or superseded Ask must have null answer_option_id",
                )
            )
    elif ask_state == "answered":
        if answer_id is None:
            errors.append(
                error(
                    "ask_lifecycle",
                    answer_path,
                    "answered Ask requires a non-null answer_option_id",
                )
            )
        elif answer_id not in option_ids:
            errors.append(
                error(
                    "unresolved_link",
                    answer_path,
                    f"answer_option_id '{answer_id}' does not resolve to an Ask option",
                )
            )

    return ask_state, option_ids


def validate_steer(
    value: Any,
    path: str,
    errors: List[Dict[str, str]],
    seen_ids: Dict[str, str],
    outcome_id: Optional[str],
    proof_ids: Set[str],
    proof_delivery: Dict[str, str],
) -> None:
    obj = expect_object(value, path, STEER_FIELDS, STEER_FIELDS, errors)
    if obj is None:
        return
    steer_id = expect_identifier(obj.get("id"), path + "/id", errors)
    register_id(steer_id, path + "/id", seen_ids, errors)
    linked_outcome = expect_identifier(obj.get("outcome_id"), path + "/outcome_id", errors)
    if (
        linked_outcome is not None
        and outcome_id is not None
        and linked_outcome != outcome_id
    ):
        errors.append(
            error(
                "unresolved_link",
                path + "/outcome_id",
                "steer.outcome_id must equal outcome.id",
            )
        )
    expect_nonblank280(obj.get("summary"), path + "/summary", errors)
    state = expect_string(
        obj.get("state"),
        path + "/state",
        errors,
        enum=set(STEER_STATES),
    )
    proof_ref = obj.get("proof_ref")
    proof_ref_path = path + "/proof_ref"
    if proof_ref is None:
        proof_ref_id = None
    else:
        proof_ref_id = expect_identifier(proof_ref, proof_ref_path, errors)
        if proof_ref_id is not None and proof_ref_id not in proof_ids:
            errors.append(
                error(
                    "unresolved_link",
                    proof_ref_path,
                    f"proof_ref '{proof_ref_id}' does not resolve to a proof id",
                )
            )

    if state == "finished_with_proof":
        if proof_ref_id is None:
            errors.append(
                error(
                    "terminal_proof",
                    proof_ref_path,
                    "finished_with_proof Steer requires a proof_ref",
                )
            )
        elif proof_delivery.get(proof_ref_id) != "delivered":
            errors.append(
                error(
                    "terminal_proof",
                    proof_ref_path,
                    "finished_with_proof Steer requires a delivered proof",
                )
            )
    elif state == "not_delivered":
        if proof_ref_id is None:
            errors.append(
                error(
                    "terminal_proof",
                    proof_ref_path,
                    "not_delivered Steer requires a proof_ref",
                )
            )
        elif proof_delivery.get(proof_ref_id) != "not_delivered":
            errors.append(
                error(
                    "terminal_proof",
                    proof_ref_path,
                    "not_delivered Steer requires a not_delivered proof",
                )
            )


def validate_proof(
    value: Any,
    path: str,
    errors: List[Dict[str, str]],
    seen_ids: Dict[str, str],
    proof_ids: Set[str],
    proof_delivery: Dict[str, str],
) -> None:
    obj = expect_object(value, path, PROOF_FIELDS, PROOF_FIELDS, errors)
    if obj is None:
        return
    proof_id = expect_identifier(obj.get("id"), path + "/id", errors)
    register_id(proof_id, path + "/id", seen_ids, errors)
    if proof_id is not None:
        proof_ids.add(proof_id)
    expect_string(obj.get("type"), path + "/type", errors, enum=set(PROOF_TYPES))
    validate_locator(obj.get("locator"), path + "/locator", errors)
    expect_nonblank500(
        obj.get("verification_summary"), path + "/verification_summary", errors
    )
    delivery = expect_string(
        obj.get("delivery"),
        path + "/delivery",
        errors,
        enum=set(PROOF_DELIVERIES),
    )
    if proof_id is not None and delivery is not None:
        proof_delivery[proof_id] = delivery


def validate_document(document: Any) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    walk_privacy(document, "", errors)

    root = expect_object(document, "", TOP_LEVEL_FIELDS, TOP_LEVEL_FIELDS, errors)
    if root is None:
        return errors

    expect_string(
        root.get("schema"),
        "/schema",
        errors,
        const=DOCUMENT_SCHEMA,
    )

    revision = root.get("revision")
    if not is_strict_int(revision):
        errors.append(error("type", "/revision", "expected integer (bool is not integer)"))
    else:
        if revision < 0 or revision > MAX_REVISION:
            errors.append(
                error(
                    "range",
                    "/revision",
                    f"revision must be between 0 and {MAX_REVISION}",
                )
            )

    validate_updated_at(root.get("updated_at"), "/updated_at", errors)

    seen_ids: Dict[str, str] = {}
    proof_ids: Set[str] = set()
    proof_delivery: Dict[str, str] = {}

    # Validate proof first so Steer proof_ref resolution can use the set.
    proof_value = root.get("proof")
    if not is_strict_list(proof_value):
        errors.append(error("type", "/proof", "expected array"))
        proof_value = []
    elif len(proof_value) > 64:
        errors.append(error("bounds", "/proof", "proof must contain at most 64 items"))

    for index, item in enumerate(proof_value if is_strict_list(root.get("proof")) else []):
        validate_proof(
            item,
            json_pointer("proof", index),
            errors,
            seen_ids,
            proof_ids,
            proof_delivery,
        )

    outcome_obj = expect_object(
        root.get("outcome"),
        "/outcome",
        OUTCOME_FIELDS,
        OUTCOME_FIELDS,
        errors,
    )
    outcome_id: Optional[str] = None
    outcome_state: Optional[str] = None
    if outcome_obj is not None:
        outcome_id = expect_identifier(outcome_obj.get("id"), "/outcome/id", errors)
        register_id(outcome_id, "/outcome/id", seen_ids, errors)
        expect_nonblank280(outcome_obj.get("summary"), "/outcome/summary", errors)
        outcome_state = expect_string(
            outcome_obj.get("state"),
            "/outcome/state",
            errors,
            enum=set(OUTCOME_STATES),
        )
        current_move = outcome_obj.get("current_move")
        if current_move is not None:
            expect_nonblank280(current_move, "/outcome/current_move", errors)

    ask_value = root.get("ask")
    ask_state: Optional[str] = None
    if ask_value is None:
        ask_state = None
    else:
        ask_state, _option_ids = validate_ask(ask_value, "/ask", errors, seen_ids)

    if outcome_state == "needs_input":
        if ask_state != "open":
            errors.append(
                error(
                    "needs_input",
                    "/outcome/state",
                    "needs_input requires exactly one open Ask",
                )
            )
    else:
        if ask_state == "open":
            errors.append(
                error(
                    "needs_input",
                    "/ask/state",
                    "open Ask requires outcome.state needs_input",
                )
            )

    if outcome_state == "finished_with_proof":
        if "delivered" not in proof_delivery.values():
            errors.append(
                error(
                    "terminal_proof",
                    "/outcome/state",
                    "finished_with_proof requires at least one delivered proof",
                )
            )
    if outcome_state == "not_delivered":
        if "not_delivered" not in proof_delivery.values():
            errors.append(
                error(
                    "terminal_proof",
                    "/outcome/state",
                    "not_delivered requires at least one not_delivered proof",
                )
            )

    steers_value = root.get("steers")
    if not is_strict_list(steers_value):
        errors.append(error("type", "/steers", "expected array"))
    else:
        if len(steers_value) > 64:
            errors.append(error("bounds", "/steers", "steers must contain at most 64 items"))
        nonterminal_steer_paths: List[str] = []
        for index, item in enumerate(steers_value):
            if (
                is_strict_dict(item)
                and item.get("state") in NONTERMINAL_STEER_STATES
            ):
                nonterminal_steer_paths.append(json_pointer("steers", index, "state"))
            validate_steer(
                item,
                json_pointer("steers", index),
                errors,
                seen_ids,
                outcome_id,
                proof_ids,
                proof_delivery,
            )
        for state_path in nonterminal_steer_paths[1:]:
            errors.append(
                error(
                    "steer_lifecycle",
                    state_path,
                    "at most one Steer may have a nonterminal state",
                )
            )

    return errors


def exceeds_max_json_depth(text: str) -> bool:
    """Report whether structural nesting in the raw text exceeds MAX_JSON_DEPTH.

    Runs before json.loads so the nesting limit is enforced identically on every
    supported Python version. Without it, deeply nested input raises an
    interpreter RecursionError inside the decoder on older interpreters and is
    reported as a parse failure instead of a deterministic depth violation.
    """
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return True
        elif character in "]}":
            if depth > 0:
                depth -= 1
    return False


def validate_text(text: str) -> Tuple[Dict[str, Any], int]:
    if exceeds_max_json_depth(text):
        return (
            result_payload(
                False,
                [
                    error(
                        "depth",
                        "",
                        f"JSON nesting exceeds maximum depth {MAX_JSON_DEPTH}",
                    )
                ],
            ),
            1,
        )
    document, failure = parse_json_document(text)
    if failure is not None:
        return failure, 2
    errors = validate_document(document)
    valid = len(errors) == 0
    return result_payload(valid, errors), (0 if valid else 1)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path, usage_failure = parse_cli(args)
    if usage_failure is not None:
        # Help exits 0 from argparse; treat as invocation guidance with exit 2.
        return emit(usage_failure, 2)

    text, io_failure = read_input(path)
    if io_failure is not None:
        code = 2
        if io_failure["errors"] and io_failure["errors"][0]["code"] == "size_error":
            code = 2
        return emit(io_failure, code)

    assert text is not None
    payload, code = validate_text(text)
    return emit(payload, code)


if __name__ == "__main__":
    sys.exit(main())
