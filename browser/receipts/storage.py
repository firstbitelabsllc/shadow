"""JSONL read/write for receipt corpus rows.

Each line in corpus.jsonl is one Receipt record (schema in __init__.py docstring).
Operations are append-only by default; explicit `replace_row(...)` updates a single row by id.

Idempotency contract: same image bytes always produce same `id` (first 12 hex of SHA-256),
so re-ingesting an already-stored image is a no-op (storage detects and skips).

Concurrency: append_row / replace_row / delete_row take an exclusive flock on a sidecar
`.lock` file for the whole read-modify-write, so overlapping writers (bulk_ingest + a UI
edit, or two threads) never lose updates or race on the temp file.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from safe_files import (
    UnsafeFileAliasError,
    atomic_write_text,
    open_regular_fd,
    read_text,
)


class CorpusError(ValueError):
    """corpus.jsonl is malformed (e.g. a non-JSON line). Subclasses ValueError for back-compat."""


def compute_id(image_bytes: bytes) -> str:
    """SHA-256 first 12 hex chars — deterministic dedupe key matching corpus.jsonl convention."""
    return hashlib.sha256(image_bytes).hexdigest()[:12]


def iso_now() -> str:
    """ISO8601 UTC timestamp for annotations.imported_at."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _corpus_lock(corpus_path: Path) -> Iterator[None]:
    """Exclusive cross-process + cross-thread lock for a corpus's read-modify-write."""
    lock_path = corpus_path.with_suffix(corpus_path.suffix + ".lock")
    with open_regular_fd(
        lock_path,
        os.O_RDWR | os.O_CREAT,
        create_parent=True,
    ) as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def read_all(corpus_path: Path) -> list[dict[str, Any]]:
    """Read every row from corpus.jsonl. Missing file → empty list. Bad line → CorpusError."""
    try:
        contents = read_text(corpus_path)
    except FileNotFoundError:
        return []
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(contents.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise CorpusError(f"corpus.jsonl line {line_no} is invalid JSON: {exc}") from exc
    return rows


def find_by_id(corpus_path: Path, row_id: str) -> dict[str, Any] | None:
    """Return the first row matching `id`, else None."""
    for row in read_all(corpus_path):
        if row.get("id") == row_id:
            return row
    return None


def append_row(corpus_path: Path, row: dict[str, Any]) -> bool:
    """Append a row to corpus.jsonl. Returns True if appended, False if id already exists (idempotent)."""
    row_id = row.get("id")
    if not row_id:
        raise ValueError("row must have an 'id' field")
    with _corpus_lock(corpus_path):
        rows = read_all(corpus_path)
        if any(existing.get("id") == row_id for existing in rows):
            return False
        rows.append(row)
        _rewrite(corpus_path, rows)
    return True


def _rewrite(corpus_path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomically replace corpus.jsonl with `rows` via a unique temp file + rename.

    Caller must hold _corpus_lock. The temp name is per-process/per-call unique so
    concurrent writers never consume each other's temp file.
    """
    contents = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    atomic_write_text(corpus_path, contents)


def replace_row(corpus_path: Path, row_id: str, new_row: dict[str, Any]) -> bool:
    """Update a single row in-place. Returns True if replaced, False if id not found.

    Rewrites the entire file — fine for corpora up to ~10K rows.
    """
    new_row["id"] = row_id  # defensive — caller must not mutate id
    with _corpus_lock(corpus_path):
        rows = read_all(corpus_path)
        found = False
        for index, row in enumerate(rows):
            if row.get("id") == row_id:
                rows[index] = new_row
                found = True
                break
        if not found:
            return False
        _rewrite(corpus_path, rows)
    return True


def update_row(corpus_path: Path, row_id: str, mutator) -> dict[str, Any] | None:
    """Atomically read-modify-write one row under a SINGLE lock. `mutator(row) -> row`.

    Returns the new row, or None if id not found. Use this instead of find_by_id() + replace_row()
    when a handler reads, mutates, and writes the same row — the two-call pattern releases the lock
    between read and write, so two concurrent edits to the same row lose one update.
    """
    with _corpus_lock(corpus_path):
        rows = read_all(corpus_path)
        for index, row in enumerate(rows):
            if row.get("id") == row_id:
                new_row = mutator(dict(row))
                new_row["id"] = row_id
                rows[index] = new_row
                _rewrite(corpus_path, rows)
                return new_row
    return None


def delete_row(corpus_path: Path, row_id: str) -> bool:
    """Remove a single row by id. Returns True if removed, False if id not found."""
    with _corpus_lock(corpus_path):
        rows = read_all(corpus_path)
        kept = [row for row in rows if row.get("id") != row_id]
        if len(kept) == len(rows):
            return False
        _rewrite(corpus_path, kept)
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
    and a ground-truth ScannedReceipt is human-confirmed (see receipts.promote).
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


def safe_image_abs(corpus_parent: Path, images_dir: Path, image_path: str) -> Path | None:
    """Resolve a row's image_path and return it ONLY if it stays inside the images jail.

    Returns None on any traversal escape ('../', absolute paths, symlink-out). Callers that
    read or unlink image bytes (handle_ocr, toss) MUST go through this — corpus.jsonl is a
    plain file multiple tools write, so a hand-edited / round-tripped row is not trusted.
    """
    images_root = images_dir.resolve()
    candidate = corpus_parent / image_path
    abs_path = candidate.parent.resolve() / candidate.name
    try:
        abs_path.relative_to(images_root)
    except ValueError:
        return None
    try:
        target_stat = abs_path.lstat()
    except FileNotFoundError:
        return abs_path
    if (
        stat.S_ISLNK(target_stat.st_mode)
        or not stat.S_ISREG(target_stat.st_mode)
        or target_stat.st_nlink != 1
    ):
        return None
    return abs_path
