"""Python mirror of the resplit-ios `ScannedReceipt` Codable contract.

A fixture only runs an iOS unit test when `expected` is a non-null, decode-clean
ScannedReceipt. The Swift decode is strict: a malformed `expected` (missing
`provenance`, a numeric `scannedAt`, an unknown `extras.kind`) throws and reds the
WHOLE corpus test. So we validate `expected` here — at the lab/export boundary —
and never let a broken row reach the repo fixture.

Source of truth: resplit-ios/ResplitCore/OCR/ScannedReceipt.swift.
"""

from __future__ import annotations

import re
from typing import Any

# resplit-ios ScannedExtraKind rawValues (ScannedReceipt.swift:118-127).
EXTRA_KINDS = frozenset(
    {"tax", "tip", "fee", "serviceCharge", "mandate", "surcharge", "discount", "credit", "unknown"}
)

# ReceiptFixtureCorpus.swift:145 uses `.iso8601`, whose default options are
# `[.withInternetDateTime]` — NO fractional seconds. So `...:00.5Z` would throw on decode.
# Require a timezone, reject fractional seconds, reject a numeric scannedAt.
_ISO8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")


def validate_expected(expected: Any) -> list[str]:
    """Return a list of contract violations for an `expected` object. Empty list = valid.

    Mirrors the required/optional shape of ScannedReceipt + ScannedLineItem + ScannedExtra +
    ScanProvenance so a populated `expected` decodes on the Swift side without reddening the corpus.
    """
    problems: list[str] = []
    if not isinstance(expected, dict):
        return ["expected must be an object"]

    # lineItems: [ScannedLineItem] — required array; each item needs a string `name`.
    line_items = expected.get("lineItems")
    if not isinstance(line_items, list):
        problems.append("lineItems must be a list (use [] for none)")
    else:
        for i, item in enumerate(line_items):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                problems.append(f"lineItems[{i}].name must be a string")
            if "amount" in item and not _is_number_or_none(item["amount"]):
                problems.append(f"lineItems[{i}].amount must be a number")
            # quantity is Swift `Int?` — a fractional number (e.g. 0.452 kg produce) throws
            # Int decode and reds the WHOLE corpus. Accept int / integral-float / null only.
            if "quantity" in item and not _is_intish_or_none(item.get("quantity")):
                problems.append(f"lineItems[{i}].quantity must be an integer or null (Swift Int?)")
            # confidence is Swift `Double?`.
            if "confidence" in item and not _is_number_or_none(item.get("confidence")):
                problems.append(f"lineItems[{i}].confidence must be a number or null")

    # extras: [ScannedExtra] — required array; each needs label(str), amount(number), kind(enum).
    extras = expected.get("extras")
    if not isinstance(extras, list):
        problems.append("extras must be a list (use [] for none)")
    else:
        for i, extra in enumerate(extras):
            if not isinstance(extra, dict):
                problems.append(f"extras[{i}] must be an object")
                continue
            if not isinstance(extra.get("label"), str):
                problems.append(f"extras[{i}].label must be a string")
            if not _is_number(extra.get("amount")):
                problems.append(f"extras[{i}].amount must be a number")
            if extra.get("kind") not in EXTRA_KINDS:
                problems.append(
                    f"extras[{i}].kind must be one of {sorted(EXTRA_KINDS)} (got {extra.get('kind')!r})"
                )
            if "confidence" in extra and not _is_number_or_none(extra.get("confidence")):
                problems.append(f"extras[{i}].confidence must be a number or null")

    # provenance: ScanProvenance — required object.
    prov = expected.get("provenance")
    if not isinstance(prov, dict):
        problems.append("provenance is required (object)")
    else:
        for key in ("providerName", "providerVersion"):
            if not isinstance(prov.get(key), str):
                problems.append(f"provenance.{key} must be a string")
        for key in ("latencyMs", "retryCount"):
            if not isinstance(prov.get(key), int) or isinstance(prov.get(key), bool):
                problems.append(f"provenance.{key} must be an integer")
        scanned_at = prov.get("scannedAt")
        if not isinstance(scanned_at, str) or not _ISO8601.match(scanned_at):
            problems.append(
                "provenance.scannedAt must be an ISO-8601 string with timezone, no fractional "
                "seconds (e.g. 2026-05-30T00:00:00Z)"
            )
        # operationId is Swift `String?` — if present it must be a string (or null).
        if prov.get("operationId") is not None and not isinstance(prov.get("operationId"), str):
            problems.append("provenance.operationId must be a string or null")

    # Optional numeric top-level fields.
    for key in ("subtotal", "total"):
        if key in expected and not _is_number_or_none(expected[key]):
            problems.append(f"{key} must be a number or null")

    return problems


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_number_or_none(value: Any) -> bool:
    return value is None or _is_number(value)


def _is_intish_or_none(value: Any) -> bool:
    """True for None, a real int, or an integral float (Swift `Int?` decode-safe)."""
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    return False
