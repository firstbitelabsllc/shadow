"""Unit tests for receipts.compare storage behavior.

Run from repo root: python3 -m unittest tests.test_receipts_compare
"""

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
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


class FailedProvidersTests(unittest.TestCase):
    def test_failed_providers_returns_only_error_entries(self):
        row = {
            "annotations": {
                "extractions": {
                    "azure": {"expected": {"total": 10.0}, "error": None},
                    "claude": {"expected": {"total": 10.0}, "error": ""},
                    "qwen": {"expected": None, "error": "timed out"},
                    "hand_note": "not a provider result",
                }
            }
        }

        self.assertEqual(compare.failed_providers(row), ["qwen"])

    def test_failed_providers_missing_extractions_empty(self):
        self.assertEqual(compare.failed_providers({}), [])
        self.assertEqual(compare.failed_providers({"annotations": {"extractions": []}}), [])


class FailedOnlyCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus.jsonl"
        self.image = Path(self.tmp.name) / "images" / "receipt.jpg"
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(SAMPLE_BYTES)
        self.row = storage.make_row(
            image_bytes=SAMPLE_BYTES,
            name="receipt",
            image_path="images/receipt.jpg",
            source="test",
        )
        self.row["annotations"]["extractions"] = {
            "azure": {"expected": {"total": 10.0}, "latency_ms": 1, "error": None, "problems": []},
            "claude": {"expected": {"total": 10.0}, "latency_ms": 2, "error": None, "problems": []},
            "qwen": {"expected": None, "latency_ms": 300_000, "error": "timed out", "problems": []},
        }
        storage.append_row(self.corpus, self.row)

    def tearDown(self):
        self.tmp.cleanup()

    def test_main_failed_only_reruns_and_stores_only_failed_providers(self):
        calls = []
        original_compare_image = compare.compare_image

        def _fake_compare_image(image_path, providers):
            calls.append((image_path, providers))
            return {
                "qwen": {
                    "expected": {"merchantName": "Receipt", "total": 10.0},
                    "latency_ms": 4,
                    "error": None,
                    "problems": [],
                }
            }

        compare.compare_image = _fake_compare_image
        try:
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = compare.main([
                    "--corpus", str(self.corpus),
                    "--id", self.row["id"],
                    "--providers", "azure,claude,qwen",
                    "--failed-only",
                    "--store",
                ])
        finally:
            compare.compare_image = original_compare_image

        self.assertEqual(rc, 0)
        self.assertEqual(calls, [(self.image.resolve(), ["qwen"])])
        self.assertIn("stored 1 extraction(s)", stderr.getvalue())
        got = storage.find_by_id(self.corpus, self.row["id"])
        self.assertEqual(sorted(got["annotations"]["extractions"]), ["azure", "claude", "qwen"])
        self.assertIsNone(got["annotations"]["extractions"]["qwen"]["error"])
        self.assertEqual(got["annotations"]["extractions"]["azure"]["expected"]["total"], 10.0)

    def test_main_failed_only_with_no_failures_is_noop(self):
        row = storage.find_by_id(self.corpus, self.row["id"])
        row["annotations"]["extractions"]["qwen"] = {
            "expected": {"total": 10.0},
            "latency_ms": 4,
            "error": None,
            "problems": [],
        }
        storage.replace_row(self.corpus, self.row["id"], row)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = compare.main(["--corpus", str(self.corpus), "--id", self.row["id"], "--failed-only"])

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(f"no failed providers stored for row {self.row['id']}", stderr.getvalue())

    def test_main_failed_only_requires_corpus_id(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            rc = compare.main(["--image", str(self.image), "--failed-only"])

        self.assertEqual(rc, 2)
        self.assertIn("--failed-only requires --id", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
