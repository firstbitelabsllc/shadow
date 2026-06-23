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

from receipts import classify, storage

DEFAULT_CORPUS = Path(
    os.environ.get(
        "RECEIPT_CORPUS_PATH",
        str(Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"),
    )
).expanduser()

RECONCILE_TOL = 0.02
PROVIDER_ORDER = {"azure": 0, "claude": 1, "qwen": 2, "codex": 3, "gemma3": 4}
TRACKED_PROVIDERS = ("azure", "claude", "qwen")
STATE_ORDER = {"needs_review": 0, "ready_candidate": 1, "grounded_consistent": 2, "no_extractions": 3}
DOMAIN_ORDER = {"dining": 0, "unsure": 1, "retail": 2, "invoice": 3}
INFORMATIONAL_TAX_KINDS = {"tax"}


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


def _is_informational_tax(extra: dict[str, Any]) -> bool:
    return str(extra.get("kind") or "").lower() in INFORMATIONAL_TAX_KINDS


def reconciles(expected: dict | None) -> bool | None:
    """Return whether subtotal + extras approximately equals total."""
    if not isinstance(expected, dict):
        return None
    total = _money(expected.get("total"))
    subtotal = _money(expected.get("subtotal"))
    if total is None or subtotal is None:
        return None
    tolerance = max(RECONCILE_TOL, 0.005 * abs(total))
    extras = [extra for extra in expected.get("extras", []) if isinstance(extra, dict)]
    extras_sum = sum(
        amount
        for extra in extras
        for amount in [_money(extra.get("amount"))]
        if amount is not None
    )
    if abs(total - (subtotal + extras_sum)) <= tolerance:
        return True

    # Some VAT/GST receipts report subtotal as the tax-inclusive amount and
    # include tax as an informational disclosure. In those cases, subtotal plus
    # non-tax extras should reconcile to total while tax extras remain present
    # for evidence and display review.
    has_tax_extra = any(_is_informational_tax(extra) for extra in extras)
    if has_tax_extra:
        non_tax_extras_sum = sum(
            amount
            for extra in extras
            if not _is_informational_tax(extra)
            for amount in [_money(extra.get("amount"))]
            if amount is not None
        )
        if abs(total - (subtotal + non_tax_extras_sum)) <= tolerance:
            return True

    return False


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


def _domain_text(row: dict[str, Any], providers: dict[str, dict[str, Any]]) -> str:
    """Return stored OCR/provider text used only for read-only domain triage."""
    annotations = row.get("annotations") if isinstance(row.get("annotations"), dict) else {}
    azure = annotations.get("azure_response") if isinstance(annotations.get("azure_response"), dict) else {}
    analyze = azure.get("analyzeResult") if isinstance(azure.get("analyzeResult"), dict) else {}
    content = analyze.get("content")
    if isinstance(content, str) and content.strip():
        return content

    parts: list[str] = []
    for summary in providers.values():
        merchant = summary.get("merchantName")
        if isinstance(merchant, str):
            parts.append(merchant)
        parts.extend(summary.get("extrasKinds") or [])
        subtotal = summary.get("subtotal")
        total = summary.get("total")
        if isinstance(subtotal, (int, float)):
            parts.append(f"Subtotal {subtotal:.2f}")
        if isinstance(total, (int, float)):
            parts.append(f"Total {total:.2f}")
    return "\n".join(parts)


def domain_summary(row: dict[str, Any], providers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Classify dining/retail/invoice without running OCR or providers."""
    domain = classify.classify_text(_domain_text(row, providers))
    return {
        "verdict": domain["verdict"],
        "dining": domain["dining"],
        "strong": domain["strong"],
        "retail": domain["retail"],
        "invoice": domain["invoice"],
        "money": domain["money"],
    }


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


def _supported_total_consensus(summaries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a reconciled total supported by at least two providers.

    This catches rows where one provider picked a tip guide/order marker as the
    total while two independent providers agree on a reconciling printed total.
    It intentionally only handles total disagreement; subtotal, currency, and
    extras disagreements still stay on the review pile.
    """
    groups: list[dict[str, Any]] = []
    for summary in summaries:
        total = summary.get("total")
        if total is None or summary.get("totalReconciles") is not True:
            continue
        group = next(
            (
                candidate
                for candidate in groups
                if _money_agrees([*candidate["totals"], total])
            ),
            None,
        )
        if group is None:
            group = {"totals": [], "providers": []}
            groups.append(group)
        group["totals"].append(total)
        group["providers"].append(summary["provider"])

    groups = [group for group in groups if len(group["providers"]) >= 2]
    if not groups:
        return None
    groups.sort(
        key=lambda group: (-len(group["providers"]), _provider_key(group["providers"][0]))
    )
    best = groups[0]
    supporting = set(best["providers"])
    return {
        "total": round(sum(best["totals"]) / len(best["totals"]), 2),
        "supportingProviders": best["providers"],
        "outlierProviders": [
            summary["provider"]
            for summary in summaries
            if summary["provider"] not in supporting
        ],
    }


def _looks_like_order_ticket_without_amount(
    *,
    grounded: bool,
    domain: dict[str, Any],
    successes: list[dict[str, Any]],
    totals: list[float],
    supported_total: dict[str, Any] | None,
) -> bool:
    """Return true when provider money is likely an order number hallucination."""
    if grounded or supported_total is not None:
        return False
    if domain.get("money") is True:
        return False
    return len(successes) > 1 and len(totals) == 1


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
        "no_total_evidence": 58,
        "insufficient_total_agreement": 55,
        "insufficient_provider_agreement": 50,
        "no_successful_provider": 45,
        "no_stored_extractions": 40,
    }
    if state != "needs_review":
        return 0
    return max((weights.get(reason, 10) for reason in reasons), default=10)


def _provider_signal(reason: str, grounded: bool, reasons: list[str], warnings: list[str]) -> None:
    if not grounded:
        reasons.append(reason)
    else:
        warnings.append(reason if reason.startswith("provider_") else f"provider_{reason}")


def _grounded_mismatch_signal(
    reason: str,
    repo_grounded: bool,
    reasons: list[str],
    warnings: list[str],
) -> None:
    if repo_grounded:
        warnings.append(f"repo_{reason}")
    else:
        reasons.append(reason)


def load_repo_fixture_index(corpus_path: Path | None) -> dict[str, dict[str, Any]]:
    if corpus_path is None:
        return {}
    fixtures: dict[str, dict[str, Any]] = {}
    for fixture in storage.read_all(corpus_path):
        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not fixture_id:
            continue
        fixtures[fixture_id] = {
            "inRepo": True,
            "grounded": isinstance(fixture.get("expected"), dict),
            "imagePath": fixture.get("image_path"),
        }
    return fixtures


def review_row(
    row: dict[str, Any],
    *,
    repo_fixtures: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    annotations = row.get("annotations") if isinstance(row.get("annotations"), dict) else {}
    extraction_map = annotations.get("extractions") if isinstance(annotations.get("extractions"), dict) else {}
    expected = row.get("expected") if isinstance(row.get("expected"), dict) else None
    fixture = (repo_fixtures or {}).get(row.get("id")) or {}
    repo_grounded = bool(fixture.get("grounded"))
    grounded = expected is not None or repo_grounded
    provider_names = sorted(
        [provider for provider, result in extraction_map.items() if isinstance(result, dict)],
        key=_provider_key,
    )
    providers = {
        provider: provider_summary(provider, extraction_map[provider])
        for provider in provider_names
        if isinstance(extraction_map.get(provider), dict)
    }
    domain = domain_summary(row, providers)
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
    supported_total = _supported_total_consensus(successes) if not grounded else None
    order_ticket_without_amount = _looks_like_order_ticket_without_amount(
        grounded=grounded,
        domain=domain,
        successes=successes,
        totals=totals,
        supported_total=supported_total,
    )

    reasons: list[str] = []
    warnings: list[str] = []
    if repo_grounded and expected is None:
        warnings.append("in_repo_grounded")
    elif fixture.get("inRepo") and expected is None:
        warnings.append("in_repo_stub")
    if not providers:
        reasons.append("no_stored_extractions")
    if any(summary["error"] for summary in providers.values()):
        _provider_signal("provider_error", grounded, reasons, warnings)
    if any(summary["problemCount"] for summary in providers.values()):
        _provider_signal("provider_problem", grounded, reasons, warnings)
    if providers and not successes:
        reasons.append("no_successful_provider")
    if len(successes) == 1:
        _provider_signal("insufficient_provider_agreement", grounded, reasons, warnings)
    if not grounded and successes:
        if not totals:
            reasons.append("no_total_evidence")
        elif len(totals) == 1 and len(successes) > 1:
            reasons.append("insufficient_total_agreement")
    if order_ticket_without_amount:
        reasons.append("non_receipt_order_ticket")
    if totals and not _money_agrees(totals):
        if supported_total is not None:
            warnings.append("provider_outlier_total")
        else:
            _provider_signal("total_disagreement", grounded, reasons, warnings)
    if subtotals and not _money_agrees(subtotals):
        _provider_signal("subtotal_disagreement", grounded, reasons, warnings)
    if len(currencies) > 1:
        _provider_signal("currency_disagreement", grounded, reasons, warnings)
    if len(extra_signatures) > 1:
        _provider_signal("extras_disagreement", grounded, reasons, warnings)
    if successes and not any(summary["totalReconciles"] is True for summary in successes):
        _provider_signal("no_reconciled_provider", grounded, reasons, warnings)

    expected_total = _money(expected.get("total")) if expected else None
    expected_subtotal = _money(expected.get("subtotal")) if expected else None
    expected_currency = expected.get("currencyCode") if expected else None
    expected_signature = extras_signature(expected)
    consensus_total = _consensus_value(totals)
    consensus_subtotal = _consensus_value(subtotals)
    if consensus_total is None and supported_total is not None:
        consensus_total = supported_total["total"]

    if expected and consensus_total is not None and expected_total is not None:
        if not _money_agrees([expected_total, consensus_total]):
            _grounded_mismatch_signal("grounded_total_disagreement", repo_grounded, reasons, warnings)
    if expected and consensus_subtotal is not None and expected_subtotal is not None:
        if not _money_agrees([expected_subtotal, consensus_subtotal]):
            _grounded_mismatch_signal("grounded_subtotal_disagreement", repo_grounded, reasons, warnings)
    if expected and len(currencies) == 1 and expected_currency and expected_currency != currencies[0]:
        _grounded_mismatch_signal("grounded_currency_disagreement", repo_grounded, reasons, warnings)
    if expected and expected_signature and extra_signatures and tuple(expected_signature) not in extra_signatures:
        _grounded_mismatch_signal("grounded_extras_disagreement", repo_grounded, reasons, warnings)

    if order_ticket_without_amount:
        state = "no_extractions"
    elif not providers:
        state = "no_extractions"
    elif reasons:
        state = "needs_review"
    elif grounded:
        state = "grounded_consistent"
    else:
        state = "ready_candidate"

    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "importedAt": annotations.get("imported_at"),
        "imagePath": row.get("image_path"),
        "private": bool(row.get("private")),
        "domain": domain,
        "grounded": grounded,
        "repoFixture": fixture or {"inRepo": False, "grounded": False, "imagePath": None},
        "state": state,
        "priority": _priority(reasons, state),
        "reasons": reasons,
        "warnings": warnings,
        "providerCount": len(providers),
        "successfulProviderCount": len(successes),
        "providerOrder": provider_names,
        "consensus": {
            "total": consensus_total,
            "subtotal": consensus_subtotal,
            "currencyCode": currencies[0] if len(currencies) == 1 else None,
            "anyReconciles": any(summary["totalReconciles"] is True for summary in successes),
            "totalSupportingProviders": supported_total["supportingProviders"] if supported_total else [],
            "totalOutlierProviders": supported_total["outlierProviders"] if supported_total else [],
        },
        "providers": providers,
    }


def review_corpus(
    corpus_path: Path,
    *,
    repo_fixture_corpus_path: Path | None = None,
    imported_since: str | None = None,
) -> dict[str, Any]:
    rows = storage.read_all(corpus_path)
    if imported_since:
        rows = [
            row for row in rows
            if str((row.get("annotations") or {}).get("imported_at") or "") >= imported_since
        ]
    repo_fixtures = load_repo_fixture_index(repo_fixture_corpus_path)
    reviews = [review_row(row, repo_fixtures=repo_fixtures) for row in rows]
    reviews.sort(
        key=lambda row: (
            STATE_ORDER.get(row["state"], 99),
            DOMAIN_ORDER.get(row["domain"]["verdict"], 99),
            -row["priority"],
            str(row.get("id") or ""),
        )
    )
    counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    for review in reviews:
        counts[review["state"]] = counts.get(review["state"], 0) + 1
        verdict = review["domain"]["verdict"]
        domain_counts[verdict] = domain_counts.get(verdict, 0) + 1
    provider_errors: dict[str, int] = {}
    for review in reviews:
        for provider, summary in review["providers"].items():
            if summary["error"]:
                provider_errors[provider] = provider_errors.get(provider, 0) + 1
    provider_coverage = provider_coverage_summary(reviews)
    return {
        "corpus": str(corpus_path),
        "repoFixtureCorpus": str(repo_fixture_corpus_path) if repo_fixture_corpus_path else None,
        "importedSince": imported_since,
        "repoFixtureCount": len(repo_fixtures),
        "repoGroundedFixtureCount": sum(
            1 for fixture in repo_fixtures.values() if fixture.get("grounded")
        ),
        "rowCount": len(rows),
        "withExtractions": sum(1 for review in reviews if review["providerCount"]),
        "counts": counts,
        "domainCounts": domain_counts,
        "providerErrors": provider_errors,
        "providerCoverage": provider_coverage,
        "rows": reviews,
    }


def provider_coverage_summary(reviews: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    coverage = {
        provider: {"present": 0, "success": 0, "error": 0, "missing": 0}
        for provider in TRACKED_PROVIDERS
    }
    for review in reviews:
        providers = review.get("providers") or {}
        for provider in TRACKED_PROVIDERS:
            summary = providers.get(provider)
            if summary is None:
                coverage[provider]["missing"] += 1
                continue
            coverage[provider]["present"] += 1
            if summary.get("error"):
                coverage[provider]["error"] += 1
            else:
                coverage[provider]["success"] += 1
    return coverage


def _format_money(value: Any) -> str:
    return "-" if value is None else f"{value:.2f}"


def render_table(
    report: dict[str, Any],
    *,
    limit: int | None = 20,
    state: str | None = None,
    domain: str | None = None,
) -> str:
    rows = [
        row for row in report["rows"]
        if (state is None or row["state"] == state)
        and (domain is None or row["domain"]["verdict"] == domain)
    ]
    if limit is not None:
        rows = rows[:limit]
    lines = [
        f"corpus: {report['corpus']}",
        (
            f"rows: {report['rowCount']}  with_extractions: {report['withExtractions']}  "
            f"states: {json.dumps(report['counts'], sort_keys=True)}  "
            f"domains: {json.dumps(report.get('domainCounts', {}), sort_keys=True)}"
        ),
        f"provider_coverage: {json.dumps(report.get('providerCoverage', {}), sort_keys=True)}",
        "",
        "state                domain    id            providers  total   curr  reasons",
        "-" * 90,
    ]
    for row in rows:
        consensus = row["consensus"]
        providers = f"{row['successfulProviderCount']}/{row['providerCount']}"
        domain_text = row["domain"]["verdict"]
        notes = [*row["reasons"], *row.get("warnings", [])]
        reasons = ",".join(notes) or "-"
        name = f"  {row['name']}" if row.get("name") else ""
        lines.append(
            f"{row['state']:<20} {domain_text:<9} {str(row.get('id') or '-'):<12} {providers:<9} "
            f"{_format_money(consensus['total']):>7} {str(consensus['currencyCode'] or '-'):>5}  "
            f"{reasons}{name}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review stored receipt corpus extraction evidence.")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, type=Path)
    parser.add_argument(
        "--ios-corpus",
        type=Path,
        help="Optional resplit-ios fixture corpus; rows grounded there are demoted from active provider-only review noise.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the full review report as JSON.")
    parser.add_argument("--limit", type=int, default=20, help="Table rows to show; use 0 for no limit.")
    parser.add_argument("--state", choices=sorted(STATE_ORDER), help="Only show rows in one state.")
    parser.add_argument("--domain", choices=sorted(DOMAIN_ORDER), help="Only show rows in one domain.")
    parser.add_argument(
        "--imported-since",
        help="Only review rows whose annotations.imported_at ISO timestamp is >= this value.",
    )
    args = parser.parse_args(argv)

    corpus = args.corpus.expanduser().resolve()
    ios_corpus = args.ios_corpus.expanduser().resolve() if args.ios_corpus else None
    report = review_corpus(
        corpus,
        repo_fixture_corpus_path=ios_corpus,
        imported_since=args.imported_since,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        limit = None if args.limit == 0 else args.limit
        print(render_table(report, limit=limit, state=args.state, domain=args.domain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
