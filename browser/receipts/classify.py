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

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DINING_KW = frozenset({
    "server", "table", "guest", "gratuity", "tip", "guest check", "dine in", "dine-in", "to go",
    "to-go", "check #", "order #", "covers", "party of", "seat", "host", "menu", "appetizer",
    "entree", "entrée", "beverage", "cocktail", "beer", "wine", "soda", "coffee", "tea", "lunch",
    "dinner", "brunch", "kitchen", "grill", "cafe", "café", "bar", "bistro", "pizzeria", "sushi",
    "ramen", "taco", "diner", "restaurant", "eatery",
})
# A dining verdict REQUIRES >=1 of these unambiguous dining-only tokens. The generic beverage/
# venue nouns above (coffee/tea/bar/wine/grill) appear on grocery + convenience receipts too and
# can't be allowed to carry the verdict alone. `subtotal` was dropped entirely — it's on every
# itemized receipt and carries zero dining-vs-other signal (the load-bearing false positive).
STRONG_DINING_KW = frozenset({
    "server", "gratuity", "tip", "table", "guest check", "dine in", "dine-in", "to go", "to-go",
    "covers", "party of", "entree", "entrée", "waiter", "waitress",
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


def _hits(low: str, tokens: set[str], keywords) -> int:
    """Count keyword hits with word boundaries. Single plain-ASCII words match the token set
    (so `bar` can't fire inside BARCODE, `host` inside GHOST, `tea` inside STEAK); phrases,
    symbols, and accented words ('guest check', 'store #', 'café') fall back to substring."""
    n = 0
    for k in keywords:
        if k.isalpha() and k.isascii():
            if k in tokens:
                n += 1
        elif k in low:
            n += 1
    return n


def classify_text(text: str) -> dict:
    """Pure keyword classifier. Returns the verdict + per-category hit counts."""
    low = (text or "").lower()
    tokens = set(re.findall(r"[a-z]+", low))
    d = _hits(low, tokens, DINING_KW)
    strong = _hits(low, tokens, STRONG_DINING_KW)
    r = _hits(low, tokens, RETAIL_KW)
    i = _hits(low, tokens, INVOICE_KW)
    money = bool(_MONEY.search(low))
    # Dining must clear a real margin over retail AND carry a strong dining-only signal — a
    # grocery/convenience receipt with a couple of generic beverage words can't reach it.
    if money and d >= 3 and strong >= 1 and d >= r + 2 and d > i:
        verdict = "dining"
    elif i >= 2 and i >= d:
        verdict = "invoice"
    elif r >= 2 and r >= d:
        verdict = "retail"
    else:
        verdict = "unsure"
    return {"verdict": verdict, "dining": d, "strong": strong, "retail": r, "invoice": i, "money": money}


def _ocr(image_paths: list[Path]) -> dict[str, str]:
    """OCR images via the bundled Vision swift (macOS). Returns {path: text}. Empty if unavailable."""
    swift_src = Path(__file__).with_name("vision_ocr.swift")
    if not swift_src.exists():
        return {}
    # Content-addressed binary in a per-user 0700 dir: a changed source compiles to a NEW path
    # (no stale-cache footgun), the digest avoids cross-version collisions, and the private dir
    # closes the predictable-/tmp-path pre-seed hazard. Compile to a unique temp then os.replace
    # atomically so a concurrent run never execs a half-linked binary.
    digest = hashlib.sha256(swift_src.read_bytes()).hexdigest()[:16]
    cache_dir = Path(tempfile.gettempdir()) / f"receipts-vision-{os.getuid()}"
    cache_dir.mkdir(mode=0o700, exist_ok=True)
    binary = cache_dir / f"ocr_{digest}"
    if not binary.exists():
        fd, tmp_out = tempfile.mkstemp(prefix="ocr_", dir=cache_dir)
        os.close(fd)
        proc = subprocess.run(
            ["swiftc", str(swift_src), "-o", tmp_out], capture_output=True, text=True
        )
        if proc.returncode != 0 or Path(tmp_out).stat().st_size == 0:
            Path(tmp_out).unlink(missing_ok=True)
            print(f"receipts.classify: swiftc failed: {proc.stderr.strip()[:300]}", file=sys.stderr)
            return {}
        os.replace(tmp_out, binary)
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
