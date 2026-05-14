"""Receipt corpus lab — vidux-browse `/receipts/` sub-route.

Owner: resplit-ios math fortress T9 sub-plan.
Authority store: ~/Development/resplit-ios/vidux/receipt-math-fortress/T9-receipt-corpus-lab/PLAN.md

Provides:
- storage: JSONL read/write for the corpus.jsonl format (id, name, image_path, expected, annotations).
- ocr: Azure Document Intelligence v4 wrapper (POST raw JPEG, poll operation-location, decode response).
- handler: HTTP request handlers wired into vidux-browse server.py.

Schema (matches Tests/Fixtures/Receipts/corpus.jsonl in resplit-ios):
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
