#!/usr/bin/env python3
"""P8.5 — OCR observability. Turn a multi-provider analyze result into queryable events.

This is the "where is Azure weak, in aggregate" layer from ocr-moat P4. Every analyze pass
emits one `ocr.scan.completed` per provider (latency, item count, extras-kind distribution,
unknown-extra count, currency, reconcile bool) plus one `ocr.divergence` per prebuilt-vs-flagship
field disagreement (the P7 oracle signal — "Azure dropped the CC fee" becomes a trackable metric
instead of an anecdote).

Transport is best-effort and NEVER raises into the analyze path:
  * POSTHOG_API_KEY set  -> POST to PostHog's capture endpoint (stdlib urllib).
  * otherwise (default)  -> append one JSON line per event to a LAN-local jsonl. No key, no
                            network, no spend — the corpus side captures locally from day one.

Stdlib only (vidux-browse zero-deps policy).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from receipts.contract import EXTRA_KINDS  # the 9 valid ScannedExtraKind values

POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com").rstrip("/")
LOCAL_EVENTS_PATH = Path(
    os.environ.get("RECEIPT_TELEMETRY_PATH", str(Path.home() / ".config" / "resplit" / "ocr-events.jsonl"))
).expanduser()

# Fields whose prebuilt-vs-flagship disagreement is worth tracking as a funnel.
DIVERGENCE_FIELDS = ("total", "subtotal", "currencyCode")
# Absolute money tolerance for "does subtotal + extras reconcile to total". Minor-unit-naive
# (a no-decimal currency like JPY/KRW would want 1.0); good enough for an aggregate metric.
RECONCILE_TOL = 0.02


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reconciles(expected: dict | None) -> bool | None:
    """subtotal + sum(extra amounts) ≈ total? None when the inputs aren't both present."""
    if not isinstance(expected, dict):
        return None
    total = expected.get("total")
    subtotal = expected.get("subtotal")
    if not isinstance(total, (int, float)) or not isinstance(subtotal, (int, float)):
        return None
    extras_sum = sum(
        e.get("amount", 0) for e in expected.get("extras", []) if isinstance(e.get("amount"), (int, float))
    )
    return abs(total - (subtotal + extras_sum)) <= max(RECONCILE_TOL, 0.005 * abs(total))


def _scan_props(provider: str, result: dict, row_id: str) -> dict[str, Any]:
    expected = result.get("expected") or {}
    extras = expected.get("extras", []) if isinstance(expected, dict) else []
    kinds = [e.get("kind", "unknown") for e in extras]
    return {
        "receiptId": row_id,
        "provider": provider,
        "latencyMs": result.get("latency_ms"),
        "error": result.get("error"),
        "valid": not result.get("problems") and not result.get("error"),
        "itemCount": len(expected.get("lineItems", [])) if isinstance(expected, dict) else 0,
        "extrasKinds": sorted(set(kinds)),
        "extrasCount": len(extras),
        # The signal: extras beyond [tax, tip] (the V1 ceiling) and the catch-all bucket.
        "hasExtraBeyondTaxTip": any(k not in ("tax", "tip") for k in kinds),
        "unknownExtraCount": sum(1 for k in kinds if k not in EXTRA_KINDS or k == "unknown"),
        "currencyCode": expected.get("currencyCode") if isinstance(expected, dict) else None,
        "totalReconciles": _reconciles(expected),
    }


def build_scan_events(results: dict[str, dict], *, row_id: str) -> list[dict[str, Any]]:
    """Pure: turn {provider: extract-result} into the event list. No I/O — unit-testable."""
    events: list[dict[str, Any]] = []
    for provider, result in results.items():
        events.append({"event": "ocr.scan.completed", "properties": _scan_props(provider, result, row_id)})

    # Divergence: prebuilt (azure) is the baseline; compare each flagship against it.
    azure = results.get("azure")
    azure_exp = (azure or {}).get("expected") or {} if azure and not azure.get("error") else None
    if azure_exp:
        for provider, result in results.items():
            if provider == "azure" or result.get("error"):
                continue
            flag_exp = result.get("expected") or {}
            for field in DIVERGENCE_FIELDS:
                a, f = azure_exp.get(field), flag_exp.get(field)
                if a is None and f is None:
                    continue
                agree = a == f if not isinstance(a, (int, float)) else (
                    isinstance(f, (int, float)) and abs(a - f) <= RECONCILE_TOL
                )
                if not agree:
                    events.append({"event": "ocr.divergence", "properties": {
                        "receiptId": row_id, "field": field, "flagship": provider,
                        "azureValue": a, "flagshipValue": f, "agree": False,
                    }})
            # The headline P7 finding: a flagship caught an extra Azure dropped.
            a_kinds = {e.get("kind") for e in azure_exp.get("extras", [])}
            f_kinds = {e.get("kind") for e in flag_exp.get("extras", [])}
            missed = sorted(f_kinds - a_kinds)
            if missed:
                events.append({"event": "ocr.divergence", "properties": {
                    "receiptId": row_id, "field": "extras", "flagship": provider,
                    "azureValue": sorted(k for k in a_kinds if k), "flagshipValue": sorted(k for k in f_kinds if k),
                    "azureMissedKinds": missed, "agree": False,
                }})
    return events


def _capture_posthog(api_key: str, event: dict, distinct_id: str) -> None:
    body = json.dumps({
        "api_key": api_key,
        "event": event["event"],
        "distinct_id": distinct_id,
        "properties": event.get("properties", {}),
        "timestamp": _now_iso(),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{POSTHOG_HOST}/capture/", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=2).close()


def _capture_local(event: dict, distinct_id: str) -> None:
    LOCAL_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": _now_iso(), "distinct_id": distinct_id, **event}, ensure_ascii=False)
    with LOCAL_EVENTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def emit_scan(results: dict[str, dict], *, row_id: str, distinct_id: str = "corpus") -> int:
    """Build + capture all events for one analyze pass. Best-effort: returns the count captured,
    swallows every transport error so telemetry never breaks the analyze response."""
    events = build_scan_events(results, row_id=row_id)
    api_key = os.environ.get("POSTHOG_API_KEY", "").strip()
    captured = 0
    for ev in events:
        try:
            if api_key:
                _capture_posthog(api_key, ev, distinct_id)
            else:
                _capture_local(ev, distinct_id)
            captured += 1
        except (urllib.error.URLError, OSError, ValueError):
            continue  # observability must never sink the request
    return captured
