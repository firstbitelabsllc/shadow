"""Receipt corpus lab — vidux-browse `/receipts/` sub-route.

Authority store: ~/Development/vidux/projects/ocr-moat/tasks/P6-receipt-corpus-lab-web/PLAN.md
(the "Moussey admin scanner that stores all receipt images on the LAN"; web sibling of
ocr-moat P5's dev-app corpus loop).

Provides:
- storage: JSONL read/write for the corpus.jsonl format (id, name, image_path, expected, annotations).
- ocr: Azure Document Intelligence v4 wrapper (POST raw JPEG, poll operation-location, decode response).
- handler: HTTP request handlers wired into vidux-browse server.py.

Schema (mirrors a downstream iOS receipt app's test-fixture corpus):
    {
      "id": "<first 12 hex of SHA-256(image bytes)>",
      "name": "<human label>",
      "image_path": "<relative path or null>",
      "expected": <ScannedReceipt-shaped object or null>,
      "annotations": {
        "source": "<provenance>",
        "imported_at": "<ISO8601>",
        "tags": ["..."],
        "known_issues": ["..."],
        "leo_note": "<optional>"
      },
      "private": <bool — if true, image_path MUST be null>
    }
"""

__version__ = "0.1.0"
