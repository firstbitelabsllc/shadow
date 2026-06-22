#!/usr/bin/env python3
"""Compare receipt extractors — flagship LLM vs prebuilt OCR — on one image.

Runs each provider through receipts.extract (same ScannedReceipt contract), then prints a
field-by-field side-by-side so the quality difference is legible as Leo sends images.

Usage:
    python3 -m receipts.compare --image /path/to/receipt.jpg
    python3 -m receipts.compare --image r.jpg --providers azure,claude
    python3 -m receipts.compare --id <corpus-id> --store     # store results into the corpus row
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import extract, storage

DEFAULT_CORPUS = Path(
    os.environ.get(
        "RECEIPT_CORPUS_PATH",
        str(Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"),
    )
).expanduser()

# Fields surfaced in the comparison table.
SCALAR_FIELDS = ["merchantName", "currencyCode", "subtotal", "total"]


def extraction_summaries(results: dict) -> dict:
    """Keep only the stable corpus fields from raw provider results."""
    return {
        p: {"expected": r.get("expected"), "latency_ms": r.get("latency_ms"),
            "error": r.get("error"), "problems": r.get("problems")}
        for p, r in results.items()
    }


def store_extractions(corpus: Path, row_id: str, results: dict) -> dict | None:
    """Merge provider results into one corpus row without erasing other providers."""
    updates = extraction_summaries(results)

    def _store(row: dict) -> dict:
        annotations = row.setdefault("annotations", {})
        existing = annotations.get("extractions")
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged.update(updates)
        annotations["extractions"] = merged
        return row

    return storage.update_row(corpus, row_id, _store)


def compare_image(image_path: Path, providers: list[str]) -> dict:
    """Run each provider on the image CONCURRENTLY. Returns {provider: extract-result-dict}.

    Cloud (claude) + prebuilt (azure) + local (qwen) run in parallel, so wall-clock is the slowest
    single provider (~the local model) rather than the sum. A provider that raises is captured as an
    error result rather than failing the whole comparison.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _run(p: str) -> dict:
        try:
            return extract.extract(p, image_path)
        except Exception as exc:  # noqa: BLE001 — one provider must not sink the comparison
            return {"provider": p, "latency_ms": 0, "expected": None, "problems": [], "error": str(exc), "raw": ""}

    with ThreadPoolExecutor(max_workers=max(1, len(providers))) as pool:
        futures = {p: pool.submit(_run, p) for p in providers}
        return {p: futures[p].result() for p in providers}


def _cell(result: dict, field: str) -> str:
    if result.get("error"):
        return "ERR"
    exp = result.get("expected") or {}
    val = exp.get(field)
    return "—" if val is None else str(val)


def render_table(results: dict) -> str:
    providers = list(results.keys())
    lines = []
    width = 16
    header = "field".ljust(20) + "".join(p.ljust(width) for p in providers)
    lines.append(header)
    lines.append("-" * len(header))
    for field in SCALAR_FIELDS:
        row = field.ljust(20) + "".join(_cell(results[p], field).ljust(width) for p in providers)
        lines.append(row)
    # derived counts
    lines.append("lineItems(#)".ljust(20) + "".join(
        ("ERR" if results[p].get("error") else str(len((results[p].get("expected") or {}).get("lineItems", [])))).ljust(width)
        for p in providers))
    lines.append("extras(kinds)".ljust(20) + "".join(
        ("ERR" if results[p].get("error") else ",".join(
            e.get("kind", "?") for e in (results[p].get("expected") or {}).get("extras", [])) or "—").ljust(width)
        for p in providers))
    lines.append("latency(ms)".ljust(20) + "".join(str(results[p].get("latency_ms", "?")).ljust(width) for p in providers))
    lines.append("valid?".ljust(20) + "".join(
        ("ERR" if results[p].get("error") else ("yes" if not results[p].get("problems") else f"no({len(results[p]['problems'])})")).ljust(width)
        for p in providers))
    # agreement on total
    totals = {p: (results[p].get("expected") or {}).get("total") for p in providers if not results[p].get("error")}
    distinct = {round(t, 2) for t in totals.values() if isinstance(t, (int, float))}
    lines.append("")
    lines.append(f"TOTAL agreement: {'✓ all agree' if len(distinct) <= 1 and distinct else '✗ disagree: ' + str(totals)}")
    for p in providers:
        if results[p].get("error"):
            lines.append(f"  {p} error: {results[p]['error']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare receipt extractors on one image.")
    parser.add_argument("--image", type=Path, help="Path to a receipt image.")
    parser.add_argument("--id", help="Corpus row id (reads its stored image instead of --image).")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, type=Path)
    parser.add_argument("--providers", default="azure,claude,qwen",
                        help="Comma list: azure,claude,qwen,gemma3,codex (codex is quota-gated; gemma3 hallucinates).")
    parser.add_argument("--store", action="store_true", help="Store results into the corpus row's annotations.extractions.")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON instead of the table.")
    args = parser.parse_args()

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]

    if args.id:
        row = storage.find_by_id(args.corpus.expanduser().resolve(), args.id)
        if not row or not row.get("image_path"):
            print(f"error: row {args.id} not found or has no image", file=sys.stderr)
            return 2
        image_path = (args.corpus.expanduser().resolve().parent / row["image_path"]).resolve()
    elif args.image:
        image_path = args.image.expanduser().resolve()
    else:
        print("error: pass --image <path> or --id <corpus-id>", file=sys.stderr)
        return 2

    if not image_path.exists():
        print(f"error: image {image_path} does not exist", file=sys.stderr)
        return 2

    print(f"comparing {providers} on {image_path.name}…", file=sys.stderr)
    results = compare_image(image_path, providers)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(render_table(results))

    if args.store and args.id:
        corpus = args.corpus.expanduser().resolve()
        if store_extractions(corpus, args.id, results) is None:
            print(f"\nerror: row {args.id} deleted during store", file=sys.stderr)
            return 2
        print(f"\nstored {len(results)} extraction(s) into row {args.id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
