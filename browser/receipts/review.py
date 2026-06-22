#!/usr/bin/env python3
"""Review stored receipt corpus extractions for grounding candidates and risks.

This is a read-only triage layer over ``annotations.extractions``. It does not
run providers and it never mutates the corpus; it turns stored Azure/Claude/Qwen
evidence into a short queue of rows that are ready to promote or need human
review before they teach the iOS fixture harness bad receipt math.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import storage

DEFAULT_CORPUS = Path(
    os.environ.get(
        "RECEIPT_CORPUS_PATH",
        str(Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"),
    )
).expanduser()

RECONCILE_TOL = 0.02
PROVIDER_ORDER = {"azure": 0, "claude": 1, "qwen": 2, "codex": 3, "gemma3": 4}
STATE_ORDER = {"needs_review": 0, "ready_candidate": 1, "grounded_consistent": 2, "no_extractions": 3}


def _provider_key(provider: str) -> tuple[int, str]:
    return (PROVIDER_ORDER.get(provider, 100), provider)


def _money(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _money_agrees(values: list[float]) -> bool:
    if len(values) <= 1:
        return True
    low = min(values)
    high = max(values)
    tolerance = max(RECONCILE_TOL, 0.005 * max(abs(low), abs(high), 1.0))
    return high - low <= tolerance


def reconciles(expected: dict | None) -> bool | None:
    """Return whether subtotal + extras approximately equals total."""
    if not isinstance(expected, dict):
        return None
    total = _money(expected.get("total"))
    subtotal = _money(expected.get("subtotal"))
    if total is None or subtotal is None:
        return None
    extras_sum = sum(
        amount
        for extra in expected.get("extras", [])
        if isinstance(extra, dict)
        for amount in [_money(extra.get("amount"))]
        if amount is not None
    )
    tolerance = max(RECONCILE_TOL, 0.005 * abs(total))
    return abs(total - (subtotal + extras_sum)) <= tolerance


def extras_signature(expected: dict | None) -> list[str]:
    """Stable kind+amount signature; labels are intentionally ignored."""
    if not isinstance(expected, dict):
        return []
    signature: list[str] = []
    for extra in expected.get("extras", []):
        if not isinstance(extra, dict):
            continue
        kind = str(extra.get("kind") or "unknown")
        amount = _money(extra.get("amount"))
        amount_text = "?" if amount is None else f"{amount:.2f}"
        signature.append(f"{kind}:{amount_text}")
    return sorted(signature)


def _extras_kinds(expected: dict | None) -> list[str]:
    if not isinstance(expected, dict):
        return []
    return sorted({
        str(extra.get("kind") or "unknown")
        for extra in expected.get("extras", [])
        if isinstance(extra, dict)
    })


def provider_summary(provider: str, result: dict[str, Any]) -> dict[str, Any]:
    expected = result.get("expected") if isinstance(result.get("expected"), dict) else None
    problems = result.get("problems") if isinstance(result.get("problems"), list) else []
    error = result.get("error") or None
    return {
        "provider": provider,
        "error": error,
        "problemCount": len(problems),
        "valid": expected is not None and error is None and not problems,
        "latencyMs": result.get("latency_ms"),
        "merchantName": expected.get("merchantName") if expected else None,
        "currencyCode": expected.get("currencyCode") if expected else None,
        "subtotal": _money(expected.get("subtotal")) if expected else None,
        "total": _money(expected.get("total")) if expected else None,
        "totalReconciles": reconciles(expected),
        "extrasKinds": _extras_kinds(expected),
        "extrasSignature": extras_signature(expected),
    }


def _consensus_value(values: list[float]) -> float | None:
    if not values or not _money_agrees(values):
        return None
    return round(sum(values) / len(values), 2)


def _priority(reasons: list[str], state: str) -> int:
    weights = {
        "provider_error": 100,
        "provider_problem": 95,
        "total_disagreement": 90,
        "currency_disagreement": 85,
        "grounded_total_disagreement": 82,
        "grounded_currency_disagreement": 80,
        "no_reconciled_provider": 75,
        "subtotal_disagreement": 70,
        "grounded_subtotal_disagreement": 68,
        "extras_disagreement": 65,
        "grounded_extras_disagreement": 62,
        "insufficient_provider_agreement": 50,
        "no_successful_provider": 45,
        "no_stored_extractions": 40,
    }
    if state != "needs_review":
        return 0
    return max((weights.get(reason, 10) for reason in reasons), default=10)


def review_row(row: dict[str, Any]) -> dict[str, Any]:
    annotations = row.get("annotations") if isinstance(row.get("annotations"), dict) else {}
    extraction_map = annotations.get("extractions") if isinstance(annotations.get("extractions"), dict) else {}
    provider_names = sorted(
        [provider for provider, result in extraction_map.items() if isinstance(result, dict)],
        key=_provider_key,
    )
    providers = {
        provider: provider_summary(provider, extraction_map[provider])
        for provider in provider_names
        if isinstance(extraction_map.get(provider), dict)
    }
    successes = [summary for summary in providers.values() if summary["valid"]]
    totals = [summary["total"] for summary in successes if summary["total"] is not None]
    subtotals = [summary["subtotal"] for summary in successes if summary["subtotal"] is not None]
    currencies = sorted({
        summary["currencyCode"] for summary in successes if isinstance(summary.get("currencyCode"), str)
    })
    extra_signatures = {
        tuple(summary["extrasSignature"])
        for summary in successes
        if summary["extrasSignature"] or summary["total"] is not None
    }

    reasons: list[str] = []
    if not providers:
        reasons.append("no_stored_extractions")
    if any(summary["error"] for summary in providers.values()):
        reasons.append("provider_error")
    if any(summary["problemCount"] for summary in providers.values()):
        reasons.append("provider_problem")
    if providers and not successes:
        reasons.append("no_successful_provider")
    if len(successes) == 1:
        reasons.append("insufficient_provider_agreement")
    if totals and not _money_agrees(totals):
        reasons.append("total_disagreement")
    if subtotals and not _money_agrees(subtotals):
        reasons.append("subtotal_disagreement")
    if len(currencies) > 1:
        reasons.append("currency_disagreement")
    if len(extra_signatures) > 1:
        reasons.append("extras_disagreement")
    if successes and not any(summary["totalReconciles"] is True for summary in successes):
        reasons.append("no_reconciled_provider")

    expected = row.get("expected") if isinstance(row.get("expected"), dict) else None
    expected_total = _money(expected.get("total")) if expected else None
    expected_subtotal = _money(expected.get("subtotal")) if expected else None
    expected_currency = expected.get("currencyCode") if expected else None
    expected_signature = extras_signature(expected)
    consensus_total = _consensus_value(totals)
    consensus_subtotal = _consensus_value(subtotals)

    if expected and consensus_total is not None and expected_total is not None:
        if not _money_agrees([expected_total, consensus_total]):
            reasons.append("grounded_total_disagreement")
    if expected and consensus_subtotal is not None and expected_subtotal is not None:
        if not _money_agrees([expected_subtotal, consensus_subtotal]):
            reasons.append("grounded_subtotal_disagreement")
    if expected and len(currencies) == 1 and expected_currency and expected_currency != currencies[0]:
        reasons.append("grounded_currency_disagreement")
    if expected and expected_signature and extra_signatures and tuple(expected_signature) not in extra_signatures:
        reasons.append("grounded_extras_disagreement")

    if not providers:
        state = "no_extractions"
    elif reasons:
        state = "needs_review"
    elif expected:
        state = "grounded_consistent"
    else:
        state = "ready_candidate"

    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "imagePath": row.get("image_path"),
        "private": bool(row.get("private")),
        "grounded": expected is not None,
        "state": state,
        "priority": _priority(reasons, state),
        "reasons": reasons,
        "providerCount": len(providers),
        "successfulProviderCount": len(successes),
        "providerOrder": provider_names,
        "consensus": {
            "total": consensus_total,
            "subtotal": consensus_subtotal,
            "currencyCode": currencies[0] if len(currencies) == 1 else None,
            "anyReconciles": any(summary["totalReconciles"] is True for summary in successes),
        },
        "providers": providers,
    }


def review_corpus(corpus_path: Path) -> dict[str, Any]:
    rows = storage.read_all(corpus_path)
    reviews = [review_row(row) for row in rows]
    reviews.sort(key=lambda row: (STATE_ORDER.get(row["state"], 99), -row["priority"], str(row.get("id") or "")))
    counts: dict[str, int] = {}
    for review in reviews:
        counts[review["state"]] = counts.get(review["state"], 0) + 1
    provider_errors: dict[str, int] = {}
    for review in reviews:
        for provider, summary in review["providers"].items():
            if summary["error"]:
                provider_errors[provider] = provider_errors.get(provider, 0) + 1
    return {
        "corpus": str(corpus_path),
        "rowCount": len(rows),
        "withExtractions": sum(1 for review in reviews if review["providerCount"]),
        "counts": counts,
        "providerErrors": provider_errors,
        "rows": reviews,
    }


def _format_money(value: Any) -> str:
    return "-" if value is None else f"{value:.2f}"


def render_table(report: dict[str, Any], *, limit: int | None = 20, state: str | None = None) -> str:
    rows = [row for row in report["rows"] if state is None or row["state"] == state]
    if limit is not None:
        rows = rows[:limit]
    lines = [
        f"corpus: {report['corpus']}",
        (
            f"rows: {report['rowCount']}  with_extractions: {report['withExtractions']}  "
            f"states: {json.dumps(report['counts'], sort_keys=True)}"
        ),
        "",
        "state                id            providers  total   curr  reasons",
        "-" * 80,
    ]
    for row in rows:
        consensus = row["consensus"]
        providers = f"{row['successfulProviderCount']}/{row['providerCount']}"
        reasons = ",".join(row["reasons"]) or "-"
        name = f"  {row['name']}" if row.get("name") else ""
        lines.append(
            f"{row['state']:<20} {str(row.get('id') or '-'):<12} {providers:<9} "
            f"{_format_money(consensus['total']):>7} {str(consensus['currencyCode'] or '-'):>5}  "
            f"{reasons}{name}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review stored receipt corpus extraction evidence.")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, type=Path)
    parser.add_argument("--json", action="store_true", help="Emit the full review report as JSON.")
    parser.add_argument("--limit", type=int, default=20, help="Table rows to show; use 0 for no limit.")
    parser.add_argument("--state", choices=sorted(STATE_ORDER), help="Only show rows in one state.")
    args = parser.parse_args(argv)

    corpus = args.corpus.expanduser().resolve()
    report = review_corpus(corpus)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        limit = None if args.limit == 0 else args.limit
        print(render_table(report, limit=limit, state=args.state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
