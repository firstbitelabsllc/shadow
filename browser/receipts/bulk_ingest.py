#!/usr/bin/env python3
"""Bulk-ingest a folder of receipt photos into the corpus.

Walks a directory for `.jpg` / `.jpeg` / `.png` files and feeds each through
`handler.handle_upload`. Idempotent via SHA-256 prefix id — re-running over the
same folder is safe (duplicates are skipped, not re-uploaded).

Usage:
    python3 -m receipts.bulk_ingest --folder ~/Receipts/2026-05 --tag thermal --tag USD
    python3 -m receipts.bulk_ingest --folder ~/Receipts --recursive --private

Per math-fortress T9.2. Rate-limiting + Azure pre-OCR are explicitly NOT in this
slice — the CLI just ingests + tags. OCR runs on-demand later via
`POST /api/receipts/<id>/ocr`, not at ingest time.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

# Run as `python3 -m receipts.bulk_ingest` from ~/Development/vidux/browser
# OR `python3 bulk_ingest.py` from .../receipts/. Add parent dir to sys.path
# in case the script is invoked directly.
if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts import handler

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def iter_image_paths(root: Path, recursive: bool) -> list[Path]:
    """Sort-stable image discovery — alphabetical so re-runs are deterministic."""
    if recursive:
        paths = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    else:
        paths = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-ingest receipts into the vidux corpus.")
    parser.add_argument("--folder", required=True, type=Path, help="Directory containing .jpg/.png images.")
    parser.add_argument("--recursive", action="store_true", help="Walk subdirectories.")
    parser.add_argument("--tag", action="append", default=[], help="Tag every ingested row (repeatable).")
    parser.add_argument("--private", action="store_true", help="Don't save image bytes to disk (image_path=null).")
    parser.add_argument("--source", default="vidux-cli:bulk_ingest", help="Provenance string for annotations.source.")
    parser.add_argument("--dry-run", action="store_true", help="Walk + print, but don't actually upload.")
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        print(f"error: --folder {folder} is not a directory", file=sys.stderr)
        return 2

    paths = iter_image_paths(folder, args.recursive)
    if not paths:
        print(f"no .jpg/.jpeg/.png files under {folder}")
        return 0

    print(f"found {len(paths)} image(s) under {folder}")

    new_count = 0
    duplicate_count = 0
    error_count = 0

    for path in paths:
        relative = path.relative_to(folder)
        if args.dry_run:
            print(f"  [dry-run] would ingest {relative}")
            continue

        try:
            image_bytes = path.read_bytes()
        except OSError as exc:
            print(f"  [error] {relative}: read failed: {exc}")
            error_count += 1
            continue

        payload = {
            "name": path.stem,
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "tags": args.tag,
            "private": args.private,
            "source": f"{args.source}:{relative}",
        }
        status, body = handler.handle_upload(payload)

        if status != 200:
            print(f"  [error] {relative}: {body.get('error', 'unknown')}")
            error_count += 1
            continue

        if body.get("duplicate"):
            print(f"  [skip] {relative}: already in corpus as {body['id']}")
            duplicate_count += 1
        else:
            print(f"  [ingest] {relative} → {body['id']}")
            new_count += 1

    print(f"\nsummary: {new_count} new, {duplicate_count} duplicate, {error_count} error")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
