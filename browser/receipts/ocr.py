"""Azure Document Intelligence v4 — prebuilt-receipt OCR.

Mirrors the iOS app's `OCRConfiguration` + `ReceiptScanner` endpoints so corpus
rows captured here are byte-identical to what production captures.

Stdlib only (urllib) — vidux-browse zero-deps policy.

Environment:
    AZURE_OCR_ENDPOINT       — Cognitive Services endpoint URL (no trailing /)
                                fallback: https://superfit.cognitiveservices.azure.com
    AZURE_OCR_SUBSCRIPTION_KEY — Ocp-Apim-Subscription-Key value
                                fallback: contents of ~/.config/resplit/azure-ocr.key
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_ENDPOINT = "https://superfit.cognitiveservices.azure.com"
DEFAULT_KEY_FILE = Path.home() / ".config" / "resplit" / "azure-ocr.key"
API_VERSION = "2024-11-30"
MODEL = "prebuilt-receipt"
POLL_INTERVAL_S = 5.0
POLL_MAX_RETRIES = 10


class OCRConfigError(RuntimeError):
    """Missing Azure endpoint or subscription key."""


class OCRRequestError(RuntimeError):
    """Azure returned a non-2xx response on the analyze POST."""


class OCRPollTimeout(RuntimeError):
    """Azure operation never returned a terminal status within POLL_MAX_RETRIES."""


def _resolve_endpoint() -> str:
    return os.environ.get("AZURE_OCR_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")


def _resolve_key() -> str:
    env = os.environ.get("AZURE_OCR_SUBSCRIPTION_KEY")
    if env:
        return env.strip()
    if DEFAULT_KEY_FILE.exists():
        return DEFAULT_KEY_FILE.read_text(encoding="utf-8").strip()
    raise OCRConfigError(
        "Missing Azure subscription key. Set AZURE_OCR_SUBSCRIPTION_KEY env var "
        f"or write the key to {DEFAULT_KEY_FILE}."
    )


# P8.4: the v4-supported way to capture "arbitrary key-value post-subtotal" extras on
# prebuilt-receipt (keyValuePairs is NOT available on this model — queryFields IS). Premium/billed,
# so pass query_fields explicitly to opt in; default off keeps the bare (free) call.
DEFAULT_QUERY_FIELDS = ["ServiceCharge", "Gratuity", "Surcharge", "Fee", "Deposit", "DeliveryFee"]


def analyze_receipt(image_bytes: bytes, *, locale: str = "en", query_fields: list[str] | None = None) -> dict[str, Any]:
    """POST raw JPEG to Azure, poll the operation-location, return the parsed analyzeResults JSON.

    Mirrors ReceiptScanner.swift's request shape. `query_fields` opts into the v4 `queryFields`
    add-on (premium) to extract named extras (service charge / gratuity / surcharge / fee /
    deposit) the structured receipt schema otherwise drops; default None = the free bare call.
    Synchronous + blocking; OK for the MVP (~50-receipt batches).
    """
    endpoint = _resolve_endpoint()
    key = _resolve_key()
    content_type = "image/png" if image_bytes[:4] == b"\x89PNG" else "image/jpeg"

    analyze_url = (
        f"{endpoint}/documentintelligence/documentModels/{MODEL}:analyze"
        f"?api-version={API_VERSION}&locale={locale}"
    )
    if query_fields:
        from urllib.parse import quote
        # Keep the comma delimiter LITERAL — encoding it (%2C) makes Azure read one giant field
        # name and the queryFields add-on silently returns nothing. Encode each field, join raw.
        joined = ",".join(quote(f, safe="") for f in query_fields)
        analyze_url += f"&features=queryFields&queryFields={joined}"
    request = urllib.request.Request(
        analyze_url,
        data=image_bytes,
        method="POST",
        headers={
            "Content-Type": content_type,
            "Ocp-Apim-Subscription-Key": key,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 202):
                raise OCRRequestError(f"analyze POST returned {response.status}")
            operation_location = response.headers.get("operation-location")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise OCRRequestError(f"analyze POST failed: HTTP {exc.code} — {body}") from exc

    if not operation_location:
        raise OCRRequestError("analyze POST returned no operation-location header")

    return _poll_operation(operation_location, key)


def _poll_operation(operation_location: str, key: str) -> dict[str, Any]:
    """Poll the operation-location URL until status is 'succeeded' / 'failed' or retries exhausted."""
    for _ in range(POLL_MAX_RETRIES):
        request = urllib.request.Request(
            operation_location,
            headers={"Ocp-Apim-Subscription-Key": key},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise OCRRequestError(f"poll failed: HTTP {exc.code}") from exc

        status = payload.get("status", "").lower()
        if status == "succeeded":
            return payload
        if status == "failed":
            raise OCRRequestError(f"Azure analyze failed: {payload.get('error')}")
        # "running" / "notStarted" — wait and retry
        time.sleep(POLL_INTERVAL_S)

    raise OCRPollTimeout(
        f"operation did not terminate within {POLL_MAX_RETRIES * POLL_INTERVAL_S:.0f}s"
    )


def config_ready() -> tuple[bool, str]:
    """Smoke-checks the config without making a network call. Returns (ok, reason).

    Useful for handlers to short-circuit with a clean error before attempting an upload.
    """
    try:
        endpoint = _resolve_endpoint()
        _resolve_key()
        return True, f"ok: endpoint={endpoint}"
    except OCRConfigError as exc:
        return False, str(exc)
