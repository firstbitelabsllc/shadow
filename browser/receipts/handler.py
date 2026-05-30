"""Request handlers for vidux-browse `/api/receipts/*` routes.

Each handler is a pure function that takes a parsed JSON dict and returns
`(ok: bool, message_or_payload)`. Server.py wires these into BaseHTTPRequestHandler
do_POST/do_GET dispatch.

Convention matches `/api/artifact` and `/api/local-plan-note` handlers in server.py:
- Loopback-only enforcement happens in server.py via `_require_json_write()`.
- Size caps happen in server.py before parsing.
- Handlers receive already-parsed JSON dicts; they validate field shape + business rules.
"""

from __future__ import annotations

import base64
import binascii
import functools
import os
from pathlib import Path
from typing import Any

from . import contract, ocr, storage


def _corpus_safe(fn):
    """Turn a malformed-corpus CorpusError into a clean (500, {error}) instead of an
    unhandled traceback the HTTP server would surface as a bare 500 with no body."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except storage.CorpusError as exc:
            return 500, {"error": str(exc)}

    return wrapper


# Default corpus path — sits alongside artifacts/ in the vidux-browse dir.
# Operator overrides via `RECEIPT_CORPUS_PATH` env var.
DEFAULT_CORPUS_PATH = Path(
    os.environ.get(
        "RECEIPT_CORPUS_PATH",
        str(Path.home() / "Development" / "vidux" / "browser" / "receipts" / "corpus.jsonl"),
    )
).expanduser()

DEFAULT_IMAGES_DIR = DEFAULT_CORPUS_PATH.parent / "images"

# Upload size cap: 15 MB. Modern receipt photos are ~3-8 MB; 15 MB has headroom
# without enabling abuse uploads.
MAX_IMAGE_BYTES = 15 * 1024 * 1024


@_corpus_safe
def handle_upload(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST /api/receipts/upload — decode base64 image, OCR, write row to corpus.

    Payload shape:
        {
          "name": "<human label>",
          "image_base64": "<base64-encoded JPEG bytes>",
          "tags": ["..."],          # optional
          "leo_note": "...",        # optional
          "private": false           # optional; if true, image bytes are NOT saved to disk
        }
    """
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return 400, {"error": "name (non-empty string) is required"}

    b64 = payload.get("image_base64")
    if not isinstance(b64, str) or not b64:
        return 400, {"error": "image_base64 (string) is required"}

    try:
        image_bytes = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        return 400, {"error": f"image_base64 not valid base64: {exc}"}

    if len(image_bytes) < 1024:
        return 400, {"error": "image too small (<1 KB)"}
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return 400, {"error": f"image too large (>{MAX_IMAGE_BYTES} bytes)"}

    # Cheap sanity check: JPEG starts with FFD8FF, PNG with 89 50 4E 47.
    head = image_bytes[:4]
    if not (head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG")):
        return 400, {"error": "image bytes don't look like JPEG or PNG"}

    private = bool(payload.get("private", False))
    tags = payload.get("tags", []) or []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return 400, {"error": "tags must be a list of strings"}
    leo_note = payload.get("leo_note")

    # Compute id first so we can short-circuit on duplicate.
    row_id = storage.compute_id(image_bytes)
    if storage.find_by_id(DEFAULT_CORPUS_PATH, row_id) is not None:
        return 200, {"ok": True, "id": row_id, "duplicate": True}

    # Save image to disk unless private.
    image_path: str | None = None
    if not private:
        DEFAULT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        ext = "jpg" if head.startswith(b"\xff\xd8\xff") else "png"
        image_file = DEFAULT_IMAGES_DIR / f"{row_id}.{ext}"
        image_file.write_bytes(image_bytes)
        image_path = str(image_file.relative_to(DEFAULT_CORPUS_PATH.parent))

    # Build the row (OCR happens lazily — `expected` stays null until human-confirmed).
    row = storage.make_row(
        image_bytes=image_bytes,
        name=name,
        image_path=image_path,
        source=str(payload.get("source", "vidux-browse:manual-upload")),
        tags=tags,
        leo_note=leo_note,
        private=private,
    )

    storage.append_row(DEFAULT_CORPUS_PATH, row)
    return 200, {"ok": True, "id": row_id, "row": row}


@_corpus_safe
def handle_list() -> tuple[int, dict[str, Any]]:
    """GET /api/receipts/list — return every row from corpus.jsonl."""
    rows = storage.read_all(DEFAULT_CORPUS_PATH)
    return 200, {"ok": True, "count": len(rows), "rows": rows}


@_corpus_safe
def handle_tag(row_id: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST /api/receipts/<id>/tag — patch tags / known_issues / leo_note on an existing row."""
    if not row_id:
        return 400, {"error": "row_id required"}

    existing = storage.find_by_id(DEFAULT_CORPUS_PATH, row_id)
    if existing is None:
        return 404, {"error": f"row {row_id} not found"}

    annotations = existing.get("annotations", {})
    if "tags" in payload:
        new_tags = payload["tags"]
        if not isinstance(new_tags, list) or not all(isinstance(t, str) for t in new_tags):
            return 400, {"error": "tags must be a list of strings"}
        annotations["tags"] = new_tags
    if "known_issues" in payload:
        new_issues = payload["known_issues"]
        if not isinstance(new_issues, list) or not all(isinstance(t, str) for t in new_issues):
            return 400, {"error": "known_issues must be a list of strings"}
        annotations["known_issues"] = new_issues
    if "leo_note" in payload:
        new_note = payload["leo_note"]
        if new_note is not None and not isinstance(new_note, str):
            return 400, {"error": "leo_note must be a string or null"}
        if new_note is None:
            annotations.pop("leo_note", None)
        else:
            annotations["leo_note"] = new_note

    existing["annotations"] = annotations
    storage.replace_row(DEFAULT_CORPUS_PATH, row_id, existing)
    return 200, {"ok": True, "row": existing}


@_corpus_safe
def handle_ocr(row_id: str) -> tuple[int, dict[str, Any]]:
    """POST /api/receipts/<id>/ocr — fetch image from disk, call Azure, store the response.

    Stores the full Azure analyzeResults JSON in `annotations.azure_response`.
    `expected` stays null — human must promote to ground-truth in a tagging step.
    """
    existing = storage.find_by_id(DEFAULT_CORPUS_PATH, row_id)
    if existing is None:
        return 404, {"error": f"row {row_id} not found"}

    image_path = existing.get("image_path")
    if not image_path:
        return 400, {"error": "row has no image_path (private?); cannot OCR"}

    abs_path = storage.safe_image_abs(DEFAULT_CORPUS_PATH.parent, DEFAULT_IMAGES_DIR, image_path)
    if abs_path is None:
        return 400, {"error": "image_path escapes images dir"}
    if not abs_path.exists():
        return 410, {"error": f"image file missing on disk: {image_path}"}

    ready, msg = ocr.config_ready()
    if not ready:
        return 503, {"error": f"OCR not configured: {msg}"}

    try:
        image_bytes = abs_path.read_bytes()
        result = ocr.analyze_receipt(image_bytes)
    except (ocr.OCRConfigError, ocr.OCRRequestError, ocr.OCRPollTimeout) as exc:
        return 502, {"error": f"OCR failed: {exc}"}

    existing.setdefault("annotations", {})["azure_response"] = result
    storage.replace_row(DEFAULT_CORPUS_PATH, row_id, existing)
    return 200, {"ok": True, "row_id": row_id, "azure_response_keys": list(result.keys())}


@_corpus_safe
def handle_set_expected(row_id: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST /api/receipts/<id>/expected — set the ground-truth ScannedReceipt.

    A non-null, contract-valid `expected` is what flips a fixture from skipped to
    load-bearing on the iOS corpus runner. Validates against the ScannedReceipt decode
    contract so a malformed object can never reach the repo fixture and red the corpus.
    Pass `{"expected": null}` to clear it back to a stub.
    """
    if not row_id:
        return 400, {"error": "row_id required"}
    if "expected" not in payload:
        return 400, {"error": "payload must include 'expected' (object or null)"}

    existing = storage.find_by_id(DEFAULT_CORPUS_PATH, row_id)
    if existing is None:
        return 404, {"error": f"row {row_id} not found"}

    expected = payload["expected"]
    if expected is not None:
        problems = contract.validate_expected(expected)
        if problems:
            return 400, {"error": "expected failed the ScannedReceipt contract", "problems": problems}

    existing["expected"] = expected
    storage.replace_row(DEFAULT_CORPUS_PATH, row_id, existing)
    return 200, {"ok": True, "row": existing}


@_corpus_safe
def handle_delete(row_id: str) -> tuple[int, dict[str, Any]]:
    """DELETE /api/receipts/<id> — remove the row and its (non-private) image from disk."""
    if not row_id:
        return 400, {"error": "row_id required"}
    existing = storage.find_by_id(DEFAULT_CORPUS_PATH, row_id)
    if existing is None:
        return 404, {"error": f"row {row_id} not found"}

    image_path = existing.get("image_path")
    if image_path:
        abs_path = storage.safe_image_abs(DEFAULT_CORPUS_PATH.parent, DEFAULT_IMAGES_DIR, image_path)
        if abs_path is not None and abs_path.exists():
            abs_path.unlink()

    storage.delete_row(DEFAULT_CORPUS_PATH, row_id)
    return 200, {"ok": True, "deleted": row_id}
