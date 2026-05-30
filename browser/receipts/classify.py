#!/usr/bin/env python3
"""Classify a receipt's OCR text as dining / retail / invoice / unsure.

Resplit splits RESTAURANT bills, so the corpus must hold dining receipts only — not grocery,
gas, parking, cosmetics, or formal tax-invoices. This is the fast keyword gate (the Vision OCR
heuristic, ported to a pure, testable function); borderline `unsure` rows get an LLM second pass.

CLI (macOS, needs the Vision OCR via vision_ocr.swift):
    python3 -m receipts.classify <image1.jpg> <image2.jpg> ...
Pure use (any platform):
    from receipts.classify import classify_text
    classify_text(ocr_text)  # -> {"verdict": ..., "dining": n, "retail": n, "invoice": n, "money": bool}
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DINING_KW = frozenset({
    "server", "table", "guest", "gratuity", "tip", "guest check", "dine in", "dine-in", "to go",
    "to-go", "check #", "order #", "covers", "party of", "seat", "host", "menu", "appetizer",
    "entree", "entrée", "beverage", "cocktail", "beer", "wine", "soda", "coffee", "tea", "lunch",
    "dinner", "brunch", "kitchen", "grill", "cafe", "café", "bar", "bistro", "pizzeria", "sushi",
    "ramen", "taco", "diner", "restaurant", "eatery", "subtotal", "sub total",
})
RETAIL_KW = frozenset({
    "sku", "upc", "size", "cashier", "store #", "store#", "you saved", "member", "membership",
    "return policy", "aisle", "dept", "style #", "qty @", "reg price", "clearance", "fitting room",
    "shoe", "apparel", "pharmacy", "rx", "grocery", "supermarket",
})
INVOICE_KW = frozenset({
    "invoice", "bill to", "bill-to", "net 30", "net30", "p.o.", "purchase order", "amount due",
    "remit", "due date", "account #", "terms", "statement",
})
_MONEY = re.compile(r"\$\s?\d|\d+\.\d{2}")


def classify_text(text: str) -> dict:
    """Pure keyword classifier. Returns the verdict + per-category hit counts."""
    low = (text or "").lower()
    d = sum(1 for k in DINING_KW if k in low)
    r = sum(1 for k in RETAIL_KW if k in low)
    i = sum(1 for k in INVOICE_KW if k in low)
    money = bool(_MONEY.search(low))
    if money and d >= 3 and d > r and d > i:
        verdict = "dining"
    elif i >= 2 and i >= d:
        verdict = "invoice"
    elif r >= 2 and r >= d:
        verdict = "retail"
    else:
        verdict = "unsure"
    return {"verdict": verdict, "dining": d, "retail": r, "invoice": i, "money": money}


def _ocr(image_paths: list[Path]) -> dict[str, str]:
    """OCR images via the bundled Vision swift (macOS). Returns {path: text}. Empty if unavailable."""
    swift_src = Path(__file__).with_name("vision_ocr.swift")
    if not swift_src.exists():
        return {}
    binary = Path("/tmp/receipts_vision_ocr")
    if not binary.exists():
        subprocess.run(["swiftc", str(swift_src), "-o", str(binary)], capture_output=True)
    if not binary.exists():
        return {}
    out: dict[str, str] = {}
    for p in image_paths:
        proc = subprocess.run([str(binary), str(p)], capture_output=True, text=True, timeout=60)
        out[str(p)] = proc.stdout
    return out


def main() -> int:
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        print("usage: python3 -m receipts.classify <image>...", file=sys.stderr)
        return 2
    texts = _ocr(paths)
    if not texts:
        print("error: Vision OCR unavailable (macOS + vision_ocr.swift required)", file=sys.stderr)
        return 2
    for path, text in texts.items():
        c = classify_text(text)
        first = " | ".join(text.splitlines()[:2])[:50]
        print(f"{c['verdict']}\t{Path(path).name}\td={c['dining']} r={c['retail']} i={c['invoice']} $={c['money']}\t{first}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
