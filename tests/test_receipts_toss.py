"""Unit tests for receipts.toss — retention with a capture-completeness guard + path jail."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import storage, toss  # noqa: E402

VALID_EXPECTED = {
    "lineItems": [],
    "extras": [],
    "provenance": {
        "providerName": "a",
        "providerVersion": "4",
        "scannedAt": "2026-05-30T00:00:00Z",
        "latencyMs": 0,
        "retryCount": 0,
    },
}


class TossTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus.jsonl"
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _old_image_row(self, name, *, expected=None, azure=None):
        body = b"\xff\xd8\xff\xe0" + name.encode() + b"\x00" * 64 + b"\xff\xd9"
        rid = storage.compute_id(body)
        img = self.images / f"{rid}.jpg"
        img.write_bytes(body)
        old = time.time() - 200 * 86400
        os.utime(img, (old, old))  # make the file 200 days old
        row = storage.make_row(
            image_bytes=body, name=name, image_path=f"images/{rid}.jpg", source="t"
        )
        row["expected"] = expected
        if azure is not None:
            row["annotations"]["azure_response"] = azure
        storage.append_row(self.corpus, row)
        return rid, img

    def test_held_when_uncaptured(self):
        rid, img = self._old_image_row("uncaptured")
        counts = toss.toss_old_images(self.corpus, 90, dry_run=False, force=False)
        self.assertEqual(counts["held_uncaptured"], 1)
        self.assertEqual(counts["tossed"], 0)
        self.assertTrue(img.exists(), "un-captured image must NOT be deleted")

    def test_tossed_when_captured_via_expected(self):
        rid, img = self._old_image_row("grounded", expected=VALID_EXPECTED)
        counts = toss.toss_old_images(self.corpus, 90, dry_run=False, force=False)
        self.assertEqual(counts["tossed"], 1)
        self.assertFalse(img.exists())
        row = storage.find_by_id(self.corpus, rid)
        self.assertIsNone(row["image_path"])
        self.assertTrue(row["private"])
        self.assertIn("tossed_at", row["annotations"])

    def test_tossed_when_captured_via_azure(self):
        rid, img = self._old_image_row("ocrd", azure={"analyzeResult": {}})
        counts = toss.toss_old_images(self.corpus, 90, dry_run=False, force=False)
        self.assertEqual(counts["tossed"], 1)
        self.assertFalse(img.exists())

    def test_force_tosses_uncaptured(self):
        rid, img = self._old_image_row("uncaptured")
        counts = toss.toss_old_images(self.corpus, 90, dry_run=False, force=True)
        self.assertEqual(counts["tossed"], 1)
        self.assertFalse(img.exists())

    def test_dry_run_deletes_nothing(self):
        rid, img = self._old_image_row("grounded", expected=VALID_EXPECTED)
        counts = toss.toss_old_images(self.corpus, 90, dry_run=True, force=False)
        self.assertEqual(counts["tossed"], 1)
        self.assertTrue(img.exists())

    def test_escaped_path_is_skipped_not_unlinked(self):
        # Hand-craft a row whose image_path escapes the images jail.
        outside = Path(self.tmp.name) / "secret.txt"
        outside.write_text("do not delete", encoding="utf-8")
        body = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"
        row = storage.make_row(image_bytes=body, name="evil", image_path=None, source="t")
        row["image_path"] = "../secret.txt"
        storage.append_row(self.corpus, row)
        counts = toss.toss_old_images(self.corpus, 0, dry_run=False, force=True)
        self.assertEqual(counts["escaped"], 1)
        self.assertEqual(counts["tossed"], 0)
        self.assertTrue(outside.exists(), "escaped path must never be unlinked")


if __name__ == "__main__":
    unittest.main()
