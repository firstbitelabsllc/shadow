#!/usr/bin/env python3
"""Photo retention — toss old receipt JPEGs while keeping JSONL rows.

For each row whose `image_path` points to a file older than `--older-than DAYS`, deletes
the underlying image bytes from disk and updates the row in place:
- `image_path` -> null
- `private` -> true (matches the storage.make_row PII guard)
- `annotations.tossed_at` -> ISO8601 timestamp

Safety:
- A row that is NOT capture-complete (no `expected` ground-truth AND no cached
  `azure_response`) is HELD, not tossed — deleting its only image would make the corpus
  entry irrecoverable. Use `--force` to override.
- `image_path` is resolved through the images jail (storage.safe_image_abs); a row whose
  path escapes the images dir is skipped, never unlinked.
- Honors `RECEIPT_CORPUS_PATH` so it shares the fleet's isolation convention.

Usage:
    python3 -m receipts.toss --older-than 90
    python3 -m receipts.toss --older-than 30 --dry-run
    python3 -m receipts.toss --older-than 90 --force   # also toss un-captured rows
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import storage

DEFAULT_CORPUS = Path(
    os.environ.get(
        "RECEIPT_CORPUS_PATH",
        str(Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"),
    )
).expanduser()


def _capture_complete(row: dict) -> bool:
    """A row is safe to toss once its data survives without the image bytes."""
    if row.get("expected") is not None:
        return True
    return "azure_response" in (row.get("annotations") or {})


def toss_old_images(corpus_path: Path, older_than_days: int, *, dry_run: bool, force: bool) -> dict:
    """Toss image bytes older than N days. Returns a summary dict."""
    corpus_path = corpus_path.expanduser().resolve()
    images_dir = corpus_path.parent / "images"
    threshold_ts = time.time() - (older_than_days * 86400)

    counts = {
        "tossed": 0,
        "too_new": 0,
        "no_image": 0,
        "already_gone": 0,
        "held_uncaptured": 0,
        "escaped": 0,
    }

    for row in storage.read_all(corpus_path):
        image_path = row.get("image_path")
        if not image_path:
            counts["no_image"] += 1
            continue

        abs_path = storage.safe_image_abs(corpus_path.parent, images_dir, image_path)
        if abs_path is None:
            counts["escaped"] += 1  # corrupt/hand-edited row — never unlink
            continue

        if not abs_path.exists():
            counts["already_gone"] += 1
            if not dry_run:
                row["image_path"] = None
                row["private"] = True
                row.setdefault("annotations", {})["tossed_at"] = storage.iso_now()
                storage.replace_row(corpus_path, row["id"], row)
            continue

        if abs_path.stat().st_mtime > threshold_ts:
            counts["too_new"] += 1
            continue

        if not force and not _capture_complete(row):
            counts["held_uncaptured"] += 1
            continue

        if dry_run:
            age_days = (time.time() - abs_path.stat().st_mtime) / 86400
            print(f"  [dry-run] toss {abs_path.name} (age {age_days:.0f}d, id {row['id']})")
        else:
            abs_path.unlink()
            row["image_path"] = None
            row["private"] = True
            row.setdefault("annotations", {})["tossed_at"] = storage.iso_now()
            storage.replace_row(corpus_path, row["id"], row)
            print(f"  tossed {abs_path.name} (id {row['id']})")
        counts["tossed"] += 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Toss old receipt image files; keep JSONL rows.")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, type=Path, help="Path to corpus.jsonl.")
    parser.add_argument("--older-than", type=int, required=True, help="Toss images older than N days.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be tossed; don't delete.")
    parser.add_argument(
        "--force", action="store_true", help="Also toss rows with no expected/azure_response (un-captured)."
    )
    args = parser.parse_args()

    corpus_path = args.corpus.expanduser().resolve()
    if not corpus_path.exists():
        print(f"error: corpus {corpus_path} does not exist", file=sys.stderr)
        return 2

    threshold_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - args.older_than * 86400))
    print(f"threshold: {args.older_than} days ago ({threshold_iso})")

    c = toss_old_images(corpus_path, args.older_than, dry_run=args.dry_run, force=args.force)

    print(
        f"\nsummary: {c['tossed']} tossed, {c['too_new']} too-new, {c['no_image']} already-tossed, "
        f"{c['already_gone']} file-already-gone, {c['held_uncaptured']} held (un-captured), "
        f"{c['escaped']} escaped-path-skipped"
    )
    if c["held_uncaptured"]:
        print(f"  ⚠ {c['held_uncaptured']} receipt(s) held — OCR or set `expected` before tossing, or use --force.")
    if args.dry_run and c["tossed"] > 0:
        print("(dry-run — no files deleted, no rows updated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
