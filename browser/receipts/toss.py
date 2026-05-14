#!/usr/bin/env python3
"""Photo retention — toss old receipt JPEGs while keeping JSONL rows.

For each row in corpus.jsonl whose `image_path` points to a file older than
`--older-than DAYS`, deletes the underlying image bytes from disk and updates
the row in place:
- `image_path` → `null`
- `private` → `true` (matches the storage.make_row PII guard)
- `annotations.tossed_at` → ISO8601 timestamp

The JSONL row stays — it's still a valid corpus entry, just without bytes.
`expected` ground-truth fields (if populated) remain usable for invariant tests.

Per math-fortress T9.5. Leo verbatim: "process store toss out old receipts."

Usage:
    python3 -m receipts.toss --older-than 90        # delete images > 90 days old
    python3 -m receipts.toss --older-than 30 --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import storage

DEFAULT_CORPUS = Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Toss old receipt image files; keep JSONL rows.")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, type=Path, help="Path to corpus.jsonl.")
    parser.add_argument("--older-than", type=int, required=True, help="Toss images older than N days.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be tossed; don't delete.")
    args = parser.parse_args()

    corpus_path = args.corpus.expanduser().resolve()
    if not corpus_path.exists():
        print(f"error: corpus {corpus_path} does not exist", file=sys.stderr)
        return 2

    threshold_ts = time.time() - (args.older_than * 86400)
    threshold_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(threshold_ts))
    print(f"threshold: {args.older_than} days ago ({threshold_iso})")

    rows = storage.read_all(corpus_path)
    tossed_count = 0
    skipped_no_image = 0
    skipped_too_new = 0
    skipped_missing = 0

    for row in rows:
        image_path = row.get("image_path")
        if not image_path:
            skipped_no_image += 1
            continue

        abs_path = (corpus_path.parent / image_path).resolve()
        if not abs_path.exists():
            skipped_missing += 1
            # File already gone — still tidy the row so it doesn't re-trigger.
            if not args.dry_run:
                row["image_path"] = None
                row["private"] = True
                row.setdefault("annotations", {})["tossed_at"] = storage.iso_now()
                storage.replace_row(corpus_path, row["id"], row)
            continue

        mtime = abs_path.stat().st_mtime
        if mtime > threshold_ts:
            skipped_too_new += 1
            continue

        if args.dry_run:
            age_days = (time.time() - mtime) / 86400
            print(f"  [dry-run] toss {abs_path.name} (age {age_days:.0f}d, id {row['id']})")
        else:
            abs_path.unlink()
            row["image_path"] = None
            row["private"] = True
            row.setdefault("annotations", {})["tossed_at"] = storage.iso_now()
            storage.replace_row(corpus_path, row["id"], row)
            print(f"  tossed {abs_path.name} (id {row['id']})")

        tossed_count += 1

    print(
        f"\nsummary: {tossed_count} tossed, "
        f"{skipped_too_new} too-new, "
        f"{skipped_no_image} already-tossed, "
        f"{skipped_missing} file-already-gone"
    )
    if args.dry_run and tossed_count > 0:
        print("(dry-run — no files deleted, no rows updated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
