#!/usr/bin/env python3
"""Promote a corpus row to a runnable fixture by setting its `expected` ScannedReceipt.

`expected` is the human-confirmed ground truth — the only thing that flips a fixture from
skipped to load-bearing on the iOS corpus runner. This CLI validates the object against the
ScannedReceipt decode contract before writing, so a malformed `expected` can never reach the
repo fixture and red the whole corpus.

Usage:
    python3 -m receipts.promote --scaffold                 # print a blank expected skeleton
    python3 -m receipts.promote --id <id> --from-json expected.json
    python3 -m receipts.promote --id <id> --clear          # back to a stub (expected=null)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import contract, storage

DEFAULT_CORPUS = Path(
    os.environ.get(
        "RECEIPT_CORPUS_PATH",
        str(Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"),
    )
).expanduser()

SKELETON = {
    "merchantName": "",
    "currencyCode": "USD",
    "currencySymbol": "$",
    "lineItems": [{"name": "", "amount": 0.0, "quantity": 1}],
    "subtotal": 0.0,
    "total": 0.0,
    "extras": [{"label": "Tax", "amount": 0.0, "kind": "tax"}],
    "provenance": {
        "providerName": "azure-di",
        "providerVersion": "4",
        "scannedAt": "2026-01-01T00:00:00Z",
        "latencyMs": 0,
        "retryCount": 0,
    },
}


def set_expected(corpus_path: Path, row_id: str, expected: dict | None) -> tuple[bool, str]:
    """Validate + write `expected` for a row. Returns (ok, message)."""
    row = storage.find_by_id(corpus_path, row_id)
    if row is None:
        return False, f"row {row_id} not found"
    if expected is not None:
        problems = contract.validate_expected(expected)
        if problems:
            return False, "expected failed the ScannedReceipt contract:\n  - " + "\n  - ".join(problems)
    row["expected"] = expected
    storage.replace_row(corpus_path, row_id, row)
    return True, f"row {row_id} expected {'cleared' if expected is None else 'set'}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Set a corpus row's ground-truth `expected`.")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, type=Path)
    parser.add_argument("--id", help="Row id (first 12 hex of the image SHA-256).")
    parser.add_argument("--from-json", type=Path, help="Path to a JSON file with the expected object.")
    parser.add_argument("--clear", action="store_true", help="Clear expected back to null (stub).")
    parser.add_argument("--scaffold", action="store_true", help="Print a blank expected skeleton and exit.")
    args = parser.parse_args()

    if args.scaffold:
        print(json.dumps(SKELETON, indent=2))
        return 0

    if not args.id:
        print("error: --id is required (or use --scaffold)", file=sys.stderr)
        return 2

    corpus_path = args.corpus.expanduser().resolve()
    if not corpus_path.exists():
        print(f"error: corpus {corpus_path} does not exist", file=sys.stderr)
        return 2

    if args.clear:
        expected = None
    elif args.from_json:
        expected = json.loads(args.from_json.read_text(encoding="utf-8"))
    else:
        print("error: pass --from-json <file> or --clear", file=sys.stderr)
        return 2

    ok, message = set_expected(corpus_path, args.id, expected)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
