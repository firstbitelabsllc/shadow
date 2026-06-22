"""Unit tests for receipts.compare storage behavior.

Run from repo root: python3 -m unittest tests.test_receipts_compare
"""

import sys
import tempfile
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import compare, storage  # noqa: E402


SAMPLE_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 2048 + b"\xff\xd9"


class StoreExtractionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus.jsonl"
        self.row = storage.make_row(
            image_bytes=SAMPLE_BYTES,
            name="receipt",
            image_path="images/receipt.jpg",
            source="test",
        )
        self.row["annotations"]["extractions"] = {
            "azure": {"expected": {"total": 10.0}, "latency_ms": 1, "error": None, "problems": []},
            "claude": {"expected": {"total": 10.0}, "latency_ms": 2, "error": None, "problems": []},
        }
        storage.append_row(self.corpus, self.row)

    def tearDown(self):
        self.tmp.cleanup()

    def test_store_extractions_merges_subset_provider_reruns(self):
        updated = compare.store_extractions(self.corpus, self.row["id"], {
            "qwen": {"expected": {"total": 10.0}, "latency_ms": 3, "error": None, "problems": []},
        })

        self.assertIsNotNone(updated)
        got = storage.find_by_id(self.corpus, self.row["id"])
        self.assertEqual(sorted(got["annotations"]["extractions"]), ["azure", "claude", "qwen"])
        self.assertEqual(got["annotations"]["extractions"]["azure"]["expected"]["total"], 10.0)
        self.assertEqual(got["annotations"]["extractions"]["qwen"]["latency_ms"], 3)


if __name__ == "__main__":
    unittest.main()
