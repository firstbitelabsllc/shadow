#!/usr/bin/env python3
"""Export the vidux lab corpus to the resplit-ios test fixture file.

Merges lab corpus rows (this machine's `~/Development/vidux/browser/receipts/corpus.jsonl`)
into the resplit-ios repo's `Tests/Fixtures/Receipts/corpus.jsonl` test fixture.

Merge rules:
- Existing repo rows are preserved exactly (by id) — never overwritten.
- New lab rows (id not in repo) are appended.
- Lab rows that share an id with a repo row are SKIPPED (operator manually
  promotes lab→repo if they want to overwrite — usually because they hand-
  edited the `expected` field to the ground-truth ScannedReceipt).

Per math-fortress T9.4. The output of this script is what runs through
`tuist test "ResplitCore Corpus Tests"` on the next iOS test cycle —
every tagged receipt Leo adds to the lab becomes a regression-test fixture.

Usage:
    python3 -m receipts.export --dry-run
    python3 -m receipts.export --out /custom/path/corpus.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import storage

DEFAULT_LAB_CORPUS = Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"
DEFAULT_REPO_CORPUS = (
    Path.home() / "Development" / "resplit-ios" / "Tests" / "Fixtures" / "Receipts" / "corpus.jsonl"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge vidux lab corpus into resplit-ios test fixture.")
    parser.add_argument("--lab", default=DEFAULT_LAB_CORPUS, type=Path, help="Source: vidux lab corpus.")
    parser.add_argument("--out", default=DEFAULT_REPO_CORPUS, type=Path, help="Destination: repo test fixture.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing the output file.")
    args = parser.parse_args()

    lab_path = args.lab.expanduser().resolve()
    out_path = args.out.expanduser().resolve()

    lab_rows = storage.read_all(lab_path)
    repo_rows = storage.read_all(out_path)

    repo_ids = {row.get("id") for row in repo_rows if row.get("id")}

    to_append: list[dict] = []
    duplicate_count = 0
    for lab_row in lab_rows:
        lab_id = lab_row.get("id")
        if not lab_id:
            continue
        if lab_id in repo_ids:
            duplicate_count += 1
            continue
        to_append.append(lab_row)

    print(f"lab    {lab_path}:  {len(lab_rows)} rows")
    print(f"repo   {out_path}: {len(repo_rows)} rows (existing)")
    print(f"plan:  +{len(to_append)} new, {duplicate_count} already in repo (preserved)")

    if not to_append:
        print("\nNothing to merge.")
        return 0

    if args.dry_run:
        print("\n--dry-run — no write. New ids:")
        for row in to_append[:20]:
            print(f"  {row.get('id')}  {row.get('name')}")
        if len(to_append) > 20:
            print(f"  ... and {len(to_append) - 20} more")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as handle:
        for row in to_append:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    print(f"\nWrote {len(to_append)} new row(s) to {out_path}")
    print("Next: review the diff via `git diff` in the resplit-ios repo + commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
