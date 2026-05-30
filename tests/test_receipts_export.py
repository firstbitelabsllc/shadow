"""Unit tests for receipts.export — the lab -> resplit-ios fixture round-trip.

Runs entirely against tempdirs; the real lab corpus and resplit-ios repo are never touched.
"""

import sys
import tempfile
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import export, storage  # noqa: E402

VALID_EXPECTED = {
    "lineItems": [{"name": "Coffee", "amount": 3.5, "quantity": 1}],
    "extras": [{"label": "Tax", "amount": 0.3, "kind": "tax"}],
    "provenance": {
        "providerName": "azure-di",
        "providerVersion": "4",
        "scannedAt": "2026-05-30T00:00:00Z",
        "latencyMs": 120,
        "retryCount": 0,
    },
    "currencyCode": "USD",
    "currencySymbol": "$",
    "subtotal": 3.5,
    "total": 3.8,
}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.lab = root / "lab" / "corpus.jsonl"
        self.lab_images = root / "lab" / "images"
        self.lab_images.mkdir(parents=True)
        self.out = root / "repo" / "corpus.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, name, *, expected=None, image=True, private=False, azure=None):
        body = b"\xff\xd8\xff\xe0" + name.encode() + b"\x00" * 2048 + b"\xff\xd9"
        rid = storage.compute_id(body)
        image_path = None if (private or not image) else f"images/{rid}.jpg"
        row = storage.make_row(
            image_bytes=body, name=name, image_path=image_path, source="t", private=private
        )
        row["expected"] = expected
        if azure is not None:
            row["annotations"]["azure_response"] = azure
        if image and not private:
            (self.lab_images / f"{rid}.jpg").write_bytes(body)
        storage.append_row(self.lab, row)
        return rid

    def test_round_trip_copies_image_azure_and_rewrites_path(self):
        a = self._add("grounded", expected=VALID_EXPECTED, azure={"analyzeResult": {"x": 1}})
        self._add("stub")  # no expected, has image
        self._add("priv", private=True)  # private, no image
        self._add("missing-image", image=False)  # image_path implied None -> treated as stub w/o image
        self._add("bad-expected", expected={"lineItems": [], "extras": [], "provenance": {}})

        result = export.export_corpus(self.lab, self.out)

        self.assertEqual(result["grounded"], 1)
        self.assertEqual(result["images_copied"], 2)  # grounded + stub (priv/missing have no image)
        self.assertEqual(result["azure_written"], 1)
        self.assertEqual(len(result["skipped_bad_expected"]), 1)

        repo_dir = self.out.parent
        date = storage.iso_now()[:10].replace("-", "")
        img = repo_dir / "images" / f"{a}-{date}.jpg"
        azure = repo_dir / "azure-v4-responses" / f"{a}.json"
        self.assertTrue(img.exists(), "image copied to repo images/")
        self.assertTrue(azure.exists(), "azure response written")

        rows = {r["id"]: r for r in storage.read_all(self.out)}
        self.assertEqual(rows[a]["image_path"], f"Tests/Fixtures/Receipts/images/{a}-{date}.jpg")
        self.assertNotIn("azure_response", rows[a]["annotations"])  # stripped from corpus row
        self.assertEqual(rows[a]["expected"], VALID_EXPECTED)

    def test_idempotent_second_run_appends_nothing(self):
        self._add("grounded", expected=VALID_EXPECTED, azure={"analyzeResult": {}})
        first = export.export_corpus(self.lab, self.out)
        self.assertEqual(first["appended"], 1)
        second = export.export_corpus(self.lab, self.out)
        self.assertEqual(second["appended"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(len(storage.read_all(self.out)), 1)

    def test_dry_run_writes_nothing(self):
        self._add("grounded", expected=VALID_EXPECTED, azure={"analyzeResult": {}})
        result = export.export_corpus(self.lab, self.out, dry_run=True)
        self.assertEqual(result["appended"], 1)
        self.assertFalse(self.out.exists())
        self.assertFalse((self.out.parent / "images").exists())

    def test_grounded_without_azure_is_skipped(self):
        # P1: a grounded, replayable row with no azure response would red the iOS corpus.
        a = self._add("grounded-no-azure", expected=VALID_EXPECTED)  # has image, no azure
        result = export.export_corpus(self.lab, self.out)
        self.assertIn(a, result["skipped_missing_azure"])
        self.assertEqual(result["appended"], 0)
        self.assertFalse(self.out.exists())

    def test_private_grounded_writes_no_azure(self):
        # P1: private rows must not leak their azure response (PII) into the repo.
        self._add("priv-grounded", expected=VALID_EXPECTED, private=True, azure={"analyzeResult": {"pii": 1}})
        result = export.export_corpus(self.lab, self.out)
        self.assertEqual(result["appended"], 1)  # appended (iOS skips private), but...
        self.assertEqual(result["azure_written"], 0)  # ...no azure file written
        self.assertEqual(list((self.out.parent / "azure-v4-responses").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
