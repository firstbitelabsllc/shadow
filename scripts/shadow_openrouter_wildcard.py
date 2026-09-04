#!/usr/bin/env python3
"""Validate the inert OpenRouter wildcard request and result contracts.

This module deliberately has no dispatch, process, network, credential, or
configuration-write capability.  A valid document proves only that its closed
shape is suitable for a future adapter; it does not prove provider execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


REQUEST_SCHEMA = "shadow.openrouter-wildcard-request.v1"
RESULT_SCHEMA = "shadow.openrouter-wildcard-result.v1"
ERROR_SCHEMA = "shadow.openrouter-wildcard-error.v1"
ACTIVATION_WAKE = "openrouter_runtime_boundary_unproved"
CONTRACT_INVALID = "openrouter_contract_invalid"
MAX_DOCUMENT_BYTES = 64 * 1024

WORK_CLASSES = frozenset({"planning", "review", "lightweight"})
REQUEST_FIELDS = frozenset(
    {
        "schema",
        "task_sha256",
        "work_class",
        "operation",
        "data_class",
        "admission",
        "required_capabilities",
        "request",
    }
)
PROVIDER_FIELDS = frozenset(
    {
        "zdr",
        "data_collection",
        "require_parameters",
        "allow_fallbacks",
        "max_price",
    }
)
PRICE_FIELDS = frozenset({"prompt", "completion", "request", "image"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONCRETE_MODEL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._:+/-]{0,191}$"
)


class WildcardContractError(ValueError):
    """One public, fail-closed contract refusal."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def _invalid() -> None:
    raise WildcardContractError(CONTRACT_INVALID)


def _runtime_boundary() -> None:
    raise WildcardContractError(ACTIVATION_WAKE)


def _closed_object(
    raw: object,
    fields: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != fields:
        _invalid()
    return raw


def _zero_number(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        _invalid()
    if not math.isfinite(raw) or raw != 0:
        _invalid()
    return 0


def _canonical_json(raw: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            raw,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        _invalid()


def canonical_request(raw: object) -> bytes:
    """Return canonical bytes for one inactive, explicit advisory request."""

    request = _closed_object(raw, REQUEST_FIELDS)
    if request.get("schema") != REQUEST_SCHEMA:
        _invalid()

    task_sha256 = request.get("task_sha256")
    if not isinstance(task_sha256, str) or SHA256_RE.fullmatch(task_sha256) is None:
        _invalid()

    work_class = request.get("work_class")
    if not isinstance(work_class, str):
        _invalid()
    if work_class not in WORK_CLASSES:
        _runtime_boundary()
    if request.get("operation") != "advisory":
        _runtime_boundary()
    if request.get("data_class") != "non-sensitive":
        _runtime_boundary()

    admission_raw = request.get("admission")
    if not isinstance(admission_raw, dict):
        _invalid()
    if admission_raw.get("mode") != "explicit":
        _runtime_boundary()
    admission = _closed_object(admission_raw, frozenset({"mode"}))

    if request.get("required_capabilities") != ["text"]:
        _runtime_boundary()

    provider_request = _closed_object(
        request.get("request"),
        frozenset({"model", "provider"}),
    )
    if provider_request.get("model") != "openrouter/free":
        _invalid()
    provider = _closed_object(provider_request.get("provider"), PROVIDER_FIELDS)
    if provider.get("zdr") is not True:
        _invalid()
    if provider.get("data_collection") != "deny":
        _invalid()
    if provider.get("require_parameters") is not True:
        _invalid()
    if provider.get("allow_fallbacks") is not False:
        _invalid()
    prices = _closed_object(provider.get("max_price"), PRICE_FIELDS)
    normalized_prices = {
        field: _zero_number(prices[field])
        for field in ("prompt", "completion", "request", "image")
    }

    normalized = {
        "schema": REQUEST_SCHEMA,
        "task_sha256": task_sha256,
        "work_class": work_class,
        "operation": "advisory",
        "data_class": "non-sensitive",
        "admission": {"mode": admission["mode"]},
        "required_capabilities": ["text"],
        "request": {
            "model": "openrouter/free",
            "provider": {
                "zdr": True,
                "data_collection": "deny",
                "require_parameters": True,
                "allow_fallbacks": False,
                "max_price": normalized_prices,
            },
        },
    }
    return _canonical_json(normalized)


def validate_result(request: object, raw: object) -> dict[str, Any]:
    """Validate and sanitize result data without asserting its provenance."""

    request_bytes = canonical_request(request)
    result = _closed_object(
        raw,
        frozenset({"schema", "request_sha256", "response"}),
    )
    if result.get("schema") != RESULT_SCHEMA:
        _invalid()

    request_sha256 = result.get("request_sha256")
    expected_digest = hashlib.sha256(request_bytes).hexdigest()
    if request_sha256 != expected_digest:
        _invalid()

    response = _closed_object(
        result.get("response"),
        frozenset({"model", "usage"}),
    )
    model = response.get("model")
    if (
        not isinstance(model, str)
        or model != model.strip()
        or CONCRETE_MODEL_RE.fullmatch(model) is None
        or model.partition("/")[0].casefold() == "openrouter"
    ):
        _invalid()
    usage = _closed_object(response.get("usage"), frozenset({"cost"}))
    cost = _zero_number(usage.get("cost"))

    return {
        "schema": RESULT_SCHEMA,
        "request_sha256": expected_digest,
        "response": {
            "model": model,
            "usage": {"cost": cost},
        },
    }


def _decode_json(text: str) -> object:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                _invalid()
            value[key] = item
        return value

    def reject_constant(_value: str) -> None:
        _invalid()

    try:
        return json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        _invalid()


def _read_json(path: Path) -> object:
    try:
        with path.open("rb") as source:
            document = source.read(MAX_DOCUMENT_BYTES + 1)
        if len(document) > MAX_DOCUMENT_BYTES:
            _invalid()
        return _decode_json(document.decode("utf-8"))
    except (OSError, UnicodeError):
        _invalid()


def _error_payload(error: WildcardContractError) -> dict[str, object]:
    blocked: dict[str, str] = {"kind": error.kind}
    if error.kind == ACTIVATION_WAKE:
        blocked["wake"] = ACTIVATION_WAKE
    return {
        "schema": ERROR_SCHEMA,
        "status": "blocked",
        "blocked": blocked,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    request = sub.add_parser("request")
    request.add_argument("--input", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--request", type=Path, required=True)
    verify.add_argument("--result", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        request = _read_json(args.input if args.command == "request" else args.request)
        if args.command == "request":
            output = canonical_request(request)
        else:
            result = _read_json(args.result)
            output = _canonical_json(validate_result(request, result))
    except WildcardContractError as error:
        sys.stderr.write(_canonical_json(_error_payload(error)).decode("utf-8") + "\n")
        return 1
    sys.stdout.write(output.decode("utf-8") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
