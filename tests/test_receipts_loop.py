"""End-to-end proof that the scan -> unit-test loop closes.

Chains the real modules (handler ingest + OCR + promote.set_expected + export + toss)
against isolated tempdirs and asserts a RUNNABLE iOS fixture lands: non-private, non-null
`expected`, image on disk at the repo-relative path, and a paired azure-v4-responses/<id>.json.
"""

import base64
import sys
import tempfile
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import export, handler, promote, storage, toss  # noqa: E402

EXPECTED = {
    "merchantName": "Café de Berlin",
    "currencyCode": "EUR",
    "currencySymbol": "€",
    "lineItems": [{"name": "Brötchen", "amount": 2.5, "quantity": 1}],
    "subtotal": 10.0,
    "total": 12.5,
    "extras": [{"label": "MwSt 19%", "amount": 2.0, "kind": "tax"}],
    "provenance": {
        "providerName": "azure-di",
        "providerVersion": "4",
        "scannedAt": "2026-05-30T00:00:00Z",
        "latencyMs": 90,
        "retryCount": 0,
    },
}


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self._saved = (handler.DEFAULT_CORPUS_PATH, handler.DEFAULT_IMAGES_DIR)
        self.lab = root / "lab" / "corpus.jsonl"
        handler.DEFAULT_CORPUS_PATH = self.lab
        handler.DEFAULT_IMAGES_DIR = root / "lab" / "images"
        self.repo = root / "repo" / "corpus.jsonl"

    def tearDown(self):
        handler.DEFAULT_CORPUS_PATH, handler.DEFAULT_IMAGES_DIR = self._saved
        self.tmp.cleanup()

    def test_full_loop_produces_runnable_fixture(self):
        jpeg = b"\xff\xd8\xff\xe0" + b"de-DE-comma-decimal" + b"\x00" * 3000 + b"\xff\xd9"

        # 1. INGEST
        s, body = handler.handle_upload(
            {"name": "de-DE-comma-decimal", "image_base64": base64.b64encode(jpeg).decode(),
             "tags": ["german", "EUR", "comma-decimal"]}
        )
        self.assertEqual(s, 200)
        rid = body["id"]

        # 2. OCR (mocked Azure) — stores annotations.azure_response
        sr, sa = handler.ocr.config_ready, handler.ocr.analyze_receipt
        seen = {}
        handler.ocr.config_ready = lambda: (True, "ok")

        def fake_analyze_receipt(b, **kwargs):
            seen["query_fields"] = kwargs.get("query_fields")
            return {"analyzeResult": {"documents": [{"fields": {}}]}}

        handler.ocr.analyze_receipt = fake_analyze_receipt
        try:
            self.assertEqual(handler.handle_ocr(rid)[0], 200)
            self.assertIn("TotalBeforeVAT", seen["query_fields"])
            self.assertIn("VAT", seen["query_fields"])
        finally:
            handler.ocr.config_ready, handler.ocr.analyze_receipt = sr, sa

        # 3. TOSS would refuse here? No — it's now capture-complete via azure_response.
        #    Prove the guard the other way: a freshly-uploaded row with no OCR is HELD.
        s2, b2 = handler.handle_upload(
            {"name": "uncaptured", "image_base64": base64.b64encode(jpeg + b"x").decode()}
        )
        held = toss.toss_old_images(self.lab, 0, dry_run=True, force=False)
        self.assertGreaterEqual(held["held_uncaptured"], 1)  # the uncaptured upload is held

        # 4. PROMOTE — set the ground-truth expected (validated)
        ok, msg = promote.set_expected(self.lab, rid, EXPECTED)
        self.assertTrue(ok, msg)

        # 5. EXPORT to the repo fixture tree
        result = export.export_corpus(self.lab, self.repo)
        self.assertEqual(result["grounded"], 1)
        self.assertIn(rid, result["new_ids"])

        # 6. ASSERT a RUNNABLE fixture landed
        rows = {r["id"]: r for r in storage.read_all(self.repo)}
        fixture = rows[rid]
        self.assertFalse(fixture.get("private", False))
        self.assertIsNotNone(fixture["expected"])  # load-bearing, not skipped
        self.assertTrue(fixture["image_path"].startswith("Tests/Fixtures/Receipts/images/"))
        repo_dir = self.repo.parent
        landed_image = repo_dir / Path(fixture["image_path"]).relative_to("Tests/Fixtures/Receipts")
        self.assertTrue(landed_image.exists(), "image bytes landed in repo images/")
        self.assertTrue((repo_dir / "azure-v4-responses" / f"{rid}.json").exists(), "azure response landed")

        # 7. Now that it's captured, toss releases the LAN image (paper-safe)
        tossed = toss.toss_old_images(self.lab, 0, dry_run=False, force=False)
        self.assertEqual(tossed["tossed"], 1)  # only the grounded row; the uncaptured stays held
        self.assertEqual(tossed["held_uncaptured"], 1)


if __name__ == "__main__":
    unittest.main()
