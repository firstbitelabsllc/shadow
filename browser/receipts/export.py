#!/usr/bin/env python3
"""Export the vidux lab corpus to the resplit-ios test fixture tree.

Closes the scan -> unit-test loop. For each NEW lab row (id not already in the repo
fixture) this:
  1. copies the image bytes to `Tests/Fixtures/Receipts/images/<id>-<yyyyMMdd>.jpg`
     and rewrites `image_path` to that repo-relative path (skips `private` rows),
  2. writes `annotations.azure_response` (if present) to
     `Tests/Fixtures/Receipts/azure-v4-responses/<id>.json` (what FixtureReplayProvider
     replays), and strips it from the corpus row to keep corpus.jsonl lean,
  3. appends the cleaned row to the repo `corpus.jsonl`.

Merge rules: existing repo rows are preserved by id (never overwritten); lab rows whose
id already exists in the repo are skipped (the operator promotes lab->repo manually if they
hand-edited `expected`). A non-private row whose image file is missing is SKIPPED + warned —
a broken row never reaches the iOS corpus. A row whose non-null `expected` fails the
ScannedReceipt contract is SKIPPED + warned (it would red the whole corpus on decode).

Usage:
    python3 -m receipts.export --dry-run
    python3 -m receipts.export --out /custom/path/corpus.jsonl
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import contract, storage

DEFAULT_LAB_CORPUS = Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"
DEFAULT_REPO_CORPUS = (
    Path.home() / "Development" / "resplit-ios" / "Tests" / "Fixtures" / "Receipts" / "corpus.jsonl"
)
REPO_IMAGES_PREFIX = "Tests/Fixtures/Receipts/images"


def _yyyymmdd(row: dict) -> str:
    """Derive a yyyyMMdd suffix from annotations.imported_at, else empty."""
    imported = (row.get("annotations") or {}).get("imported_at", "")
    return imported[:10].replace("-", "") if len(imported) >= 10 else ""


def export_corpus(lab_path: Path, out_path: Path, *, dry_run: bool = False) -> dict:
    """Plan + (unless dry_run) apply the lab->repo merge. Returns a summary dict."""
    lab_path = lab_path.expanduser().resolve()
    out_path = out_path.expanduser().resolve()
    lab_images = lab_path.parent / "images"
    repo_dir = out_path.parent
    repo_images = repo_dir / "images"
    repo_azure = repo_dir / "azure-v4-responses"

    repo_ids = {r.get("id") for r in storage.read_all(out_path) if r.get("id")}

    appended: list[dict] = []  # cleaned corpus rows to append
    image_copies: list[tuple[Path, Path]] = []  # (src, dest)
    azure_writes: list[tuple[Path, dict]] = []  # (dest, payload)
    duplicates = grounded = stubs = 0
    skipped_missing_image: list[str] = []
    skipped_bad_expected: list[str] = []

    for row in storage.read_all(lab_path):
        rid = row.get("id")
        if not rid:
            continue
        if rid in repo_ids:
            duplicates += 1
            continue

        new_row = json.loads(json.dumps(row))  # deep copy
        annotations = new_row.get("annotations") or {}
        azure = annotations.pop("azure_response", None)  # strip from corpus row
        new_row["annotations"] = annotations

        expected = new_row.get("expected")
        if expected is not None:
            problems = contract.validate_expected(expected)
            if problems:
                skipped_bad_expected.append(f"{rid}: {problems[0]}")
                continue
            grounded += 1
        else:
            stubs += 1

        if new_row.get("private") or not row.get("image_path"):
            new_row["image_path"] = None
        else:
            src = storage.safe_image_abs(lab_path.parent, lab_images, row["image_path"])
            if src is None or not src.exists():
                skipped_missing_image.append(rid)
                continue
            ext = src.suffix.lstrip(".") or "jpg"
            date = _yyyymmdd(row)
            dest_name = f"{rid}-{date}.{ext}" if date else f"{rid}.{ext}"
            new_row["image_path"] = f"{REPO_IMAGES_PREFIX}/{dest_name}"
            image_copies.append((src, repo_images / dest_name))

        if azure is not None:
            azure_writes.append((repo_azure / f"{rid}.json", azure))

        appended.append(new_row)

    if not dry_run and appended:
        repo_images.mkdir(parents=True, exist_ok=True)
        repo_azure.mkdir(parents=True, exist_ok=True)
        for src, dest in image_copies:
            shutil.copy2(src, dest)
        for dest, payload in azure_writes:
            dest.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as handle:
            for new_row in appended:
                handle.write(json.dumps(new_row, separators=(",", ":")) + "\n")

    return {
        "appended": len(appended),
        "grounded": grounded,
        "stubs": stubs,
        "images_copied": len(image_copies),
        "azure_written": len(azure_writes),
        "duplicates": duplicates,
        "skipped_missing_image": skipped_missing_image,
        "skipped_bad_expected": skipped_bad_expected,
        "new_ids": [r["id"] for r in appended],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge vidux lab corpus into resplit-ios test fixture.")
    parser.add_argument("--lab", default=DEFAULT_LAB_CORPUS, type=Path, help="Source: vidux lab corpus.")
    parser.add_argument("--out", default=DEFAULT_REPO_CORPUS, type=Path, help="Destination: repo test fixture.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing.")
    args = parser.parse_args()

    result = export_corpus(args.lab, args.out, dry_run=args.dry_run)

    print(f"plan:  +{result['appended']} new ({result['grounded']} grounded, {result['stubs']} stubs), "
          f"{result['duplicates']} already in repo")
    print(f"       {result['images_copied']} image(s), {result['azure_written']} azure response(s)")
    if result["skipped_missing_image"]:
        print(f"  ⚠ skipped {len(result['skipped_missing_image'])} non-private row(s) missing an image: "
              f"{result['skipped_missing_image']}")
    if result["skipped_bad_expected"]:
        print("  ⚠ skipped row(s) with an invalid `expected` (would red the corpus):")
        for line in result["skipped_bad_expected"]:
            print(f"      {line}")
    if args.dry_run:
        print("\n--dry-run — nothing written. New ids:")
        for rid in result["new_ids"][:20]:
            print(f"  {rid}")
    elif result["appended"]:
        print(f"\nWrote {result['appended']} row(s) to {args.out.expanduser().resolve()}")
        print("Next: review `git diff` in resplit-ios + commit corpus.jsonl + images/ + azure-v4-responses/.")
    else:
        print("\nNothing to merge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
