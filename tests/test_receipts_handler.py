"""Unit tests for receipts.handler — the (status, body) request handlers.

Run from repo root: python3 -m unittest tests.test_receipts_handler
Isolation: setUp reassigns handler.DEFAULT_CORPUS_PATH / DEFAULT_IMAGES_DIR to a
tempdir and asserts they point under it, so the real corpus is never written.
"""

import base64
import sys
import tempfile
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import handler, storage  # noqa: E402


def _jpeg(n=4096):
    """A byte string that passes the JPEG magic-byte + size gates."""
    body = b"\xff\xd8\xff\xe0" + b"\x00" * max(0, n - 6) + b"\xff\xd9"
    return body


def _b64(data):
    return base64.b64encode(data).decode("ascii")


class HandlerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self._saved = (handler.DEFAULT_CORPUS_PATH, handler.DEFAULT_IMAGES_DIR)
        handler.DEFAULT_CORPUS_PATH = root / "corpus.jsonl"
        handler.DEFAULT_IMAGES_DIR = root / "images"
        # Hard isolation assertion — mirror the loopback-guard discipline.
        assert str(handler.DEFAULT_CORPUS_PATH).startswith(self.tmp.name)

    def tearDown(self):
        handler.DEFAULT_CORPUS_PATH, handler.DEFAULT_IMAGES_DIR = self._saved
        self.tmp.cleanup()

    def upload(self, **over):
        payload = {"name": "lunch", "image_base64": _b64(_jpeg())}
        payload.update(over)
        return handler.handle_upload(payload)


class UploadTests(HandlerTestCase):
    def test_happy_path_writes_row_and_image(self):
        status, body = self.upload(tags=["food"])
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["id"]), 12)
        self.assertIsNone(body["row"]["expected"])
        self.assertEqual(body["row"]["annotations"]["tags"], ["food"])
        # image landed on disk under the isolated images dir
        img = handler.DEFAULT_IMAGES_DIR / f"{body['id']}.jpg"
        self.assertTrue(img.exists())

    def test_dedupe_same_bytes(self):
        s1, b1 = self.upload()
        s2, b2 = self.upload(name="different-name")
        self.assertEqual(s2, 200)
        self.assertTrue(b2["duplicate"])
        self.assertEqual(b1["id"], b2["id"])
        _, listing = handler.handle_list()
        self.assertEqual(listing["count"], 1)

    def test_private_skips_disk_write(self):
        status, body = self.upload(private=True)
        self.assertEqual(status, 200)
        self.assertIsNone(body["row"]["image_path"])
        self.assertTrue(body["row"]["private"])
        self.assertFalse((handler.DEFAULT_IMAGES_DIR).exists())

    def test_rejects_empty_name(self):
        self.assertEqual(self.upload(name="  ")[0], 400)

    def test_rejects_missing_b64(self):
        s, _ = handler.handle_upload({"name": "x"})
        self.assertEqual(s, 400)

    def test_rejects_bad_base64(self):
        self.assertEqual(self.upload(image_base64="not base64!!")[0], 400)

    def test_rejects_too_small(self):
        self.assertEqual(self.upload(image_base64=_b64(b"\xff\xd8\xff" + b"\x00" * 10))[0], 400)

    def test_rejects_too_large(self):
        big = b"\xff\xd8\xff\xe0" + b"\x00" * (handler.MAX_IMAGE_BYTES + 10) + b"\xff\xd9"
        self.assertEqual(self.upload(image_base64=_b64(big))[0], 400)

    def test_rejects_non_image_magic(self):
        gif = b"GIF89a" + b"\x00" * 2048
        self.assertEqual(self.upload(image_base64=_b64(gif))[0], 400)

    def test_rejects_tags_not_list(self):
        self.assertEqual(self.upload(tags="food")[0], 400)


class ListTests(HandlerTestCase):
    def test_empty_then_one(self):
        s, body = handler.handle_list()
        self.assertEqual(s, 200)
        self.assertEqual(body["count"], 0)
        self.upload()
        _, body2 = handler.handle_list()
        self.assertEqual(body2["count"], 1)


class TagTests(HandlerTestCase):
    def test_patches_tags_known_issues_leo_note(self):
        _, body = self.upload()
        rid = body["id"]
        s, out = handler.handle_tag(
            rid, {"tags": ["t1"], "known_issues": ["k1"], "leo_note": "note"}
        )
        self.assertEqual(s, 200)
        row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, rid)
        self.assertEqual(row["annotations"]["tags"], ["t1"])
        self.assertEqual(row["annotations"]["known_issues"], ["k1"])
        self.assertEqual(row["annotations"]["leo_note"], "note")

    def test_404_unknown_id(self):
        self.assertEqual(handler.handle_tag("nope", {"tags": []})[0], 404)

    def test_400_empty_id(self):
        self.assertEqual(handler.handle_tag("", {"tags": []})[0], 400)

    def test_400_tags_not_list(self):
        _, body = self.upload()
        self.assertEqual(handler.handle_tag(body["id"], {"tags": "x"})[0], 400)


class CorruptCorpusTests(HandlerTestCase):
    def test_corrupt_line_returns_clean_500_not_crash(self):
        handler.DEFAULT_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler.DEFAULT_CORPUS_PATH.write_text(
            '{"id":"a","name":"ok"}\nnot valid json\n', encoding="utf-8"
        )
        for fn in (
            lambda: handler.handle_list(),
            lambda: self.upload(),
            lambda: handler.handle_tag("a", {"tags": []}),
            lambda: handler.handle_ocr("a"),
        ):
            status, body = fn()
            self.assertEqual(status, 500)
            self.assertIn("line 2", body["error"])


class OcrTests(HandlerTestCase):
    def test_404_unknown_id(self):
        self.assertEqual(handler.handle_ocr("nope")[0], 404)

    def test_400_when_image_path_escapes_jail(self):
        # Seed a hand-crafted row whose image_path traverses out of the images dir.
        handler.DEFAULT_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = storage.make_row(
            image_bytes=_jpeg(), name="evil", image_path="../../../../etc/passwd", source="t"
        )
        storage.append_row(handler.DEFAULT_CORPUS_PATH, row)
        saved = handler.ocr.config_ready
        handler.ocr.config_ready = lambda: (True, "ok")
        try:
            status, body = handler.handle_ocr(row["id"])
            self.assertEqual(status, 400)
            self.assertIn("escapes", body["error"])
        finally:
            handler.ocr.config_ready = saved

    def test_400_private_no_image_path(self):
        _, body = self.upload(private=True)
        self.assertEqual(handler.handle_ocr(body["id"])[0], 400)

    def test_503_when_unconfigured(self):
        _, body = self.upload()
        saved = handler.ocr.config_ready
        handler.ocr.config_ready = lambda: (False, "no key")
        try:
            self.assertEqual(handler.handle_ocr(body["id"])[0], 503)
        finally:
            handler.ocr.config_ready = saved

    def test_200_stores_azure_response_when_configured(self):
        _, body = self.upload()
        saved_ready, saved_analyze = handler.ocr.config_ready, handler.ocr.analyze_receipt
        handler.ocr.config_ready = lambda: (True, "ok")
        handler.ocr.analyze_receipt = lambda b: {"analyzeResult": {"documents": []}}
        try:
            s, out = handler.handle_ocr(body["id"])
            self.assertEqual(s, 200)
            row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, body["id"])
            self.assertIn("azure_response", row["annotations"])
        finally:
            handler.ocr.config_ready, handler.ocr.analyze_receipt = saved_ready, saved_analyze


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
    "total": 3.8,
}


class SetExpectedTests(HandlerTestCase):
    def test_valid_expected_persists(self):
        _, body = self.upload()
        s, out = handler.handle_set_expected(body["id"], {"expected": VALID_EXPECTED})
        self.assertEqual(s, 200)
        row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, body["id"])
        self.assertEqual(row["expected"], VALID_EXPECTED)

    def test_missing_provenance_rejected(self):
        _, body = self.upload()
        bad = {"lineItems": [], "extras": [], "provenance": {}}
        s, out = handler.handle_set_expected(body["id"], {"expected": bad})
        self.assertEqual(s, 400)
        self.assertTrue(out["problems"])

    def test_numeric_scanned_at_rejected(self):
        _, body = self.upload()
        bad = dict(VALID_EXPECTED, provenance=dict(VALID_EXPECTED["provenance"], scannedAt=0))
        s, _ = handler.handle_set_expected(body["id"], {"expected": bad})
        self.assertEqual(s, 400)

    def test_bad_extra_kind_rejected(self):
        _, body = self.upload()
        bad = dict(VALID_EXPECTED, extras=[{"label": "x", "amount": 1.0, "kind": "gratuity"}])
        s, _ = handler.handle_set_expected(body["id"], {"expected": bad})
        self.assertEqual(s, 400)

    def test_null_clears_to_stub(self):
        _, body = self.upload()
        handler.handle_set_expected(body["id"], {"expected": VALID_EXPECTED})
        s, _ = handler.handle_set_expected(body["id"], {"expected": None})
        self.assertEqual(s, 200)
        row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, body["id"])
        self.assertIsNone(row["expected"])

    def test_404_unknown_id(self):
        self.assertEqual(handler.handle_set_expected("nope", {"expected": None})[0], 404)

    def test_400_missing_expected_key(self):
        _, body = self.upload()
        self.assertEqual(handler.handle_set_expected(body["id"], {})[0], 400)


class ImageTests(HandlerTestCase):
    def test_serves_bytes_for_stored_image(self):
        _, body = self.upload()
        status, ctype, data = handler.handle_image(body["id"])
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "image/jpeg")
        self.assertTrue(data.startswith(b"\xff\xd8\xff"))

    def test_404_for_private_row(self):
        _, body = self.upload(private=True)
        self.assertEqual(handler.handle_image(body["id"])[0], 404)

    def test_404_for_unknown(self):
        self.assertEqual(handler.handle_image("nope")[0], 404)

    def test_404_for_jail_escape_image_path(self):
        handler.DEFAULT_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = storage.make_row(image_bytes=_jpeg(), name="evil", image_path="../../../../etc/passwd", source="t")
        storage.append_row(handler.DEFAULT_CORPUS_PATH, row)
        status, ctype, data = handler.handle_image(row["id"])
        self.assertEqual(status, 404)
        self.assertEqual(ctype, "")

    def test_500_on_corrupt_corpus(self):
        handler.DEFAULT_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler.DEFAULT_CORPUS_PATH.write_text('{"id":"a"}\nnot json\n', encoding="utf-8")
        status, ctype, data = handler.handle_image("a")
        self.assertEqual(status, 500)
        self.assertIn("line 2", data["error"])


class DeleteTests(HandlerTestCase):
    def test_delete_removes_row_and_image(self):
        _, body = self.upload()
        rid = body["id"]
        img = handler.DEFAULT_IMAGES_DIR / f"{rid}.jpg"
        self.assertTrue(img.exists())
        s, out = handler.handle_delete(rid)
        self.assertEqual(s, 200)
        self.assertIsNone(storage.find_by_id(handler.DEFAULT_CORPUS_PATH, rid))
        self.assertFalse(img.exists())

    def test_delete_404_unknown(self):
        self.assertEqual(handler.handle_delete("nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
