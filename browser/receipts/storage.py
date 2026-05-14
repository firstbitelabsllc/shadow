"""JSONL read/write for receipt corpus rows.

Each line in corpus.jsonl is one Receipt record (schema in __init__.py docstring).
Operations are append-only by default; explicit `replace_row(...)` updates a single row by id.

Idempotency contract: same image bytes always produce same `id` (first 12 hex of SHA-256),
so re-ingesting an already-stored image is a no-op (storage detects and skips).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def compute_id(image_bytes: bytes) -> str:
    """SHA-256 first 12 hex chars — deterministic dedupe key matching corpus.jsonl convention."""
    return hashlib.sha256(image_bytes).hexdigest()[:12]


def iso_now() -> str:
    """ISO8601 UTC timestamp for annotations.imported_at."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_all(corpus_path: Path) -> list[dict[str, Any]]:
    """Read every row from corpus.jsonl. Missing file → empty list."""
    if not corpus_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"corpus.jsonl line {line_no} is invalid JSON: {exc}") from exc
    return rows


def iter_rows(corpus_path: Path) -> Iterator[dict[str, Any]]:
    """Streaming variant of read_all — yields one row at a time without loading the whole file."""
    if not corpus_path.exists():
        return
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"corpus.jsonl line {line_no} is invalid JSON: {exc}") from exc


def find_by_id(corpus_path: Path, row_id: str) -> dict[str, Any] | None:
    """Return the first row matching `id`, else None."""
    for row in iter_rows(corpus_path):
        if row.get("id") == row_id:
            return row
    return None


def append_row(corpus_path: Path, row: dict[str, Any]) -> bool:
    """Append a row to corpus.jsonl. Returns True if appended, False if id already exists (idempotent)."""
    row_id = row.get("id")
    if not row_id:
        raise ValueError("row must have an 'id' field")
    if find_by_id(corpus_path, row_id) is not None:
        return False
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with corpus_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    return True


def replace_row(corpus_path: Path, row_id: str, new_row: dict[str, Any]) -> bool:
    """Update a single row in-place. Returns True if replaced, False if id not found.

    Rewrites the entire file — fine for corpora up to ~10K rows; if we ever
    grow past that, switch to an indexed format (SQLite or LMDB).
    """
    if not corpus_path.exists():
        return False
    new_row["id"] = row_id  # defensive — caller must not mutate id
    rows = read_all(corpus_path)
    found = False
    for index, row in enumerate(rows):
        if row.get("id") == row_id:
            rows[index] = new_row
            found = True
            break
    if not found:
        return False
    tmp = corpus_path.with_suffix(corpus_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    tmp.replace(corpus_path)
    return True


def make_row(
    *,
    image_bytes: bytes,
    name: str,
    image_path: str | None,
    source: str,
    tags: list[str] | None = None,
    leo_note: str | None = None,
    private: bool = False,
) -> dict[str, Any]:
    """Build a fresh corpus row from raw image bytes + metadata.

    `expected` starts null — populated once the paired Azure response is captured
    and a ground-truth ScannedReceipt is human-confirmed.
    """
    if private and image_path is not None:
        raise ValueError("private=True requires image_path=None (PII guard)")
    row: dict[str, Any] = {
        "id": compute_id(image_bytes),
        "name": name,
        "image_path": image_path,
        "expected": None,
        "annotations": {
            "source": source,
            "imported_at": iso_now(),
            "tags": tags or [],
            "known_issues": [],
        },
    }
    if leo_note:
        row["annotations"]["leo_note"] = leo_note
    if private:
        row["private"] = True
    return row
