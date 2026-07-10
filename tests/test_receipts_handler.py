"""Unit tests for receipts.handler — the (status, body) request handlers.

Run from repo root: python3 -m unittest tests.test_receipts_handler
Isolation: setUp reassigns handler.DEFAULT_CORPUS_PATH / DEFAULT_IMAGES_DIR to a
tempdir and asserts they point under it, so the real corpus is never written.
"""

import base64
import os
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

    def test_upload_rejects_symlink_image_without_touching_referent(self):
        image_bytes = _jpeg()
        row_id = storage.compute_id(image_bytes)
        handler.DEFAULT_IMAGES_DIR.mkdir(parents=True)
        outside = handler.DEFAULT_CORPUS_PATH.parent / "outside-image.jpg"
        outside.write_bytes(b"outside sentinel")
        (handler.DEFAULT_IMAGES_DIR / f"{row_id}.jpg").symlink_to(outside)

        status, _ = self.upload(image_base64=_b64(image_bytes))

        self.assertEqual(status, 409)
        self.assertEqual(outside.read_bytes(), b"outside sentinel")
        self.assertFalse(handler.DEFAULT_CORPUS_PATH.exists())

    def test_upload_rejects_hardlink_image_without_touching_referent(self):
        image_bytes = _jpeg()
        row_id = storage.compute_id(image_bytes)
        handler.DEFAULT_IMAGES_DIR.mkdir(parents=True)
        outside = handler.DEFAULT_CORPUS_PATH.parent / "outside-image.jpg"
        outside.write_bytes(b"outside sentinel")
        os.link(outside, handler.DEFAULT_IMAGES_DIR / f"{row_id}.jpg")

        status, _ = self.upload(image_base64=_b64(image_bytes))

        self.assertEqual(status, 409)
        self.assertEqual(outside.read_bytes(), b"outside sentinel")
        self.assertFalse(handler.DEFAULT_CORPUS_PATH.exists())

    def test_upload_rejects_symlinked_images_directory(self):
        outside = handler.DEFAULT_CORPUS_PATH.parent / "outside-images"
        outside.mkdir()
        handler.DEFAULT_IMAGES_DIR.symlink_to(outside, target_is_directory=True)

        status, _ = self.upload()

        self.assertEqual(status, 409)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(handler.DEFAULT_CORPUS_PATH.exists())

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

    def test_private_row_omitted_by_default(self):
        # Round-10 panel finding: handle_list() used to return every row
        # unconditionally, including private:true ones (name + annotations
        # like leo_note) to any Host-header-allowlisted caller -- bypassing
        # the same guard handle_image() enforces (404 for private rows) and
        # handle_upload() enforces (no image bytes to disk for private
        # rows). include_private defaults to False, matching what
        # server.py passes for a non-loopback caller.
        self.upload(
            name="PRIVATE: do not show anyone", private=True, leo_note="sensitive",
            image_base64=_b64(_jpeg(4096)),
        )
        self.upload(name="public receipt", image_base64=_b64(_jpeg(4100)))
        _, body = handler.handle_list()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["rows"][0]["name"], "public receipt")
        names = [row["name"] for row in body["rows"]]
        self.assertNotIn("PRIVATE: do not show anyone", names)

    def test_private_row_included_when_include_private_true(self):
        # The loopback-verified caller path (server.py passes
        # include_private=is_loopback_host(...)) must still see everything.
        self.upload(
            name="PRIVATE: do not show anyone", private=True, leo_note="sensitive",
            image_base64=_b64(_jpeg(4096)),
        )
        self.upload(name="public receipt", image_base64=_b64(_jpeg(4100)))
        _, body = handler.handle_list(include_private=True)
        self.assertEqual(body["count"], 2)
        names = [row["name"] for row in body["rows"]]
        self.assertIn("PRIVATE: do not show anyone", names)


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
        seen = {}
        handler.ocr.config_ready = lambda: (True, "ok")

        def fake_analyze(image_bytes, **kwargs):
            seen["query_fields"] = kwargs.get("query_fields")
            return {"analyzeResult": {"documents": []}}

        handler.ocr.analyze_receipt = fake_analyze
        try:
            s, out = handler.handle_ocr(body["id"])
            self.assertEqual(s, 200)
            self.assertEqual(seen["query_fields"], handler.ocr.DEFAULT_QUERY_FIELDS)
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


class AnalyzeTests(HandlerTestCase):
    def _fake_compare(self):
        from receipts import compare
        saved = compare.compare_image

        def fake_compare(path, providers):
            results = {}
            for p in providers:
                result = {
                    "expected": {"lineItems": [], "extras": [], "total": 9.9},
                    "latency_ms": 10,
                    "error": None,
                    "problems": [],
                }
                if p == "azure":
                    result["azure_response"] = {"analyzeResult": {"documents": []}}
                results[p] = result
            return results

        compare.compare_image = fake_compare
        return compare, saved

    def test_stores_extractions(self):
        _, body = self.upload()
        compare, saved = self._fake_compare()
        try:
            s, out = handler.handle_analyze(body["id"], {"providers": ["azure", "claude"]})
            self.assertEqual(s, 200)
            self.assertEqual(sorted(out["providers"]), ["azure", "claude"])
            row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, body["id"])
            self.assertEqual(sorted(row["annotations"]["extractions"]), ["azure", "claude"])
            self.assertEqual(row["annotations"]["azure_response"], {"analyzeResult": {"documents": []}})
        finally:
            compare.compare_image = saved

    def test_subset_analyze_preserves_existing_provider_extractions(self):
        _, body = self.upload()
        rid = body["id"]
        row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, rid)
        row.setdefault("annotations", {})["azure_response"] = {"analyzeResult": {"documents": [{"old": True}]}}
        row.setdefault("annotations", {})["extractions"] = {
            "azure": {"expected": {"total": 10}, "latency_ms": 1, "error": None, "problems": []},
            "claude": {"expected": {"total": 10}, "latency_ms": 2, "error": None, "problems": []},
        }
        storage.replace_row(handler.DEFAULT_CORPUS_PATH, rid, row)

        compare, saved = self._fake_compare()
        try:
            s, out = handler.handle_analyze(rid, {"providers": ["qwen"]})
            self.assertEqual(s, 200)
            self.assertEqual(out["providers"], ["qwen"])
            row = storage.find_by_id(handler.DEFAULT_CORPUS_PATH, rid)
            self.assertEqual(sorted(row["annotations"]["extractions"]), ["azure", "claude", "qwen"])
            self.assertEqual(row["annotations"]["extractions"]["azure"]["expected"]["total"], 10)
            self.assertEqual(row["annotations"]["extractions"]["qwen"]["expected"]["total"], 9.9)
            self.assertEqual(row["annotations"]["azure_response"], {"analyzeResult": {"documents": [{"old": True}]}})
        finally:
            compare.compare_image = saved

    def test_404_unknown(self):
        compare, saved = self._fake_compare()
        try:
            self.assertEqual(handler.handle_analyze("nope", {})[0], 404)
        finally:
            compare.compare_image = saved

    def test_400_private_no_image(self):
        _, body = self.upload(private=True)
        self.assertEqual(handler.handle_analyze(body["id"], {})[0], 400)


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


class OcrConfigLeakGuardTests(unittest.TestCase):
    """Round-11 panel finding: browser/receipts/ocr.py shipped in the public
    npm package with a hardcoded live Azure endpoint
    (superfit.cognitiveservices.azure.com) and a secret-key-file path naming a
    separate private product (~/.config/resplit/azure-ocr.key) -- invisible to
    the text grep-gate, which had no rule for hardcoded external hostnames or
    secret-path conventions. Guards against reintroduction: OCR must require
    explicit env config, with no private infra names in the source."""

    def setUp(self):
        from receipts import ocr as _ocr  # noqa: E402
        self.ocr = _ocr
        self.src = (BROWSER_DIR / "receipts" / "ocr.py").read_text(encoding="utf-8")

    def test_no_hardcoded_cognitiveservices_endpoint(self):
        self.assertNotIn(
            "cognitiveservices.azure.com",
            self.src,
            "ocr.py must not hardcode a specific Azure resource endpoint -- "
            "require AZURE_OCR_ENDPOINT instead",
        )

    def test_no_private_product_key_path(self):
        self.assertNotIn(
            "config/resplit",
            self.src,
            "ocr.py must not reference a private product's secret-key path",
        )

    def test_endpoint_default_is_empty(self):
        self.assertEqual(
            self.ocr.DEFAULT_ENDPOINT,
            "",
            "DEFAULT_ENDPOINT must be empty so a consumer must configure their own",
        )

    def test_resolve_endpoint_requires_env(self):
        import os
        saved = os.environ.pop("AZURE_OCR_ENDPOINT", None)
        try:
            with self.assertRaises(self.ocr.OCRConfigError):
                self.ocr._resolve_endpoint()
        finally:
            if saved is not None:
                os.environ["AZURE_OCR_ENDPOINT"] = saved


if __name__ == "__main__":
    unittest.main()
