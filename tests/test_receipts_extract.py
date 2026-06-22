"""Unit tests for receipts.extract pure logic — Azure mapping, JSON parsing, finalize/validate.

No network, no CLI spawn: only the deterministic mapping/parsing functions are exercised.
"""

import sys
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import contract, extract  # noqa: E402

AZURE_SAMPLE = {
    "analyzeResult": {
        "documents": [
            {
                "fields": {
                    "MerchantName": {"valueString": "CAFE DE BERLIN"},
                    "Subtotal": {"valueNumber": 10.0},
                    "TotalTax": {"valueNumber": 2.0},
                    "Total": {"valueCurrency": {"amount": 12.5, "currencyCode": "EUR"}},
                    "Items": {
                        "valueArray": [
                            {"valueObject": {"Description": {"valueString": "Kaffee"},
                                             "TotalPrice": {"valueNumber": 3.0},
                                             "Quantity": {"valueNumber": 1}}},
                            {"valueObject": {"Description": {"valueString": "Kuchen"},
                                             "TotalPrice": {"valueNumber": 4.5}}},
                        ]
                    },
                }
            }
        ]
    }
}

AZURE_KETTLE_QUERY_FIELDS = {
    "analyzeResult": {
        "documents": [
            {
                "fields": {
                    "MerchantName": {"valueString": "THE KETTLE CORNER RESTAURANT LLC"},
                    "MerchantAddress": {"valueString": "Shams Boutik, Al Reem Island, Abu Dhabi"},
                    "Subtotal": {"valueCurrency": {"amount": 100.0, "currencyCode": "USD"}},
                    "TotalBeforeVAT": {"valueCurrency": {"amount": 95.24, "currencyCode": "AED"}},
                    "VAT": {"valueCurrency": {"amount": 4.76, "currencyCode": "AED"}},
                    "Total": {"valueCurrency": {"amount": 100.0, "currencyCode": "USD"}},
                    "Items": {
                        "valueArray": [
                            {"valueObject": {"Description": {"valueString": "MASALA CHAI REGULAR"},
                                             "TotalPrice": {"valueNumber": 8.0},
                                             "Quantity": {"valueNumber": 1}}},
                            {"valueObject": {"Description": {"valueString": "NILGARI CHICKEN"},
                                             "TotalPrice": {"valueNumber": 48.0},
                                             "Quantity": {"valueNumber": 1}}},
                        ]
                    },
                }
            }
        ]
    }
}


class JsonFromTextTests(unittest.TestCase):
    def test_fenced(self):
        self.assertEqual(extract._json_from_text('```json\n{"total": 12.5}\n```'), {"total": 12.5})

    def test_bare_with_prose(self):
        self.assertEqual(extract._json_from_text('Here it is: {"a": 1} done'), {"a": 1})

    def test_nested_braces(self):
        got = extract._json_from_text('{"x": {"y": 2}, "z": 3}')
        self.assertEqual(got, {"x": {"y": 2}, "z": 3})

    def test_no_json(self):
        self.assertIsNone(extract._json_from_text("no json here"))


class AzureMappingTests(unittest.TestCase):
    def test_maps_to_valid_scanned_receipt(self):
        scanned = extract.azure_to_scanned(AZURE_SAMPLE, latency_ms=900)
        self.assertEqual(scanned["merchantName"], "CAFE DE BERLIN")
        self.assertEqual(scanned["total"], 12.5)
        self.assertEqual(scanned["subtotal"], 10.0)
        self.assertEqual(scanned["currencyCode"], "EUR")
        self.assertEqual(len(scanned["lineItems"]), 2)
        self.assertEqual(scanned["lineItems"][0]["name"], "Kaffee")
        self.assertEqual([e["kind"] for e in scanned["extras"]], ["tax"])

    def test_prefers_total_before_vat_and_uae_currency(self):
        scanned = extract.azure_to_scanned(AZURE_KETTLE_QUERY_FIELDS, latency_ms=900)
        self.assertEqual(scanned["currencyCode"], "AED")
        self.assertEqual(scanned["subtotal"], 95.24)
        self.assertEqual(scanned["total"], 100.0)
        self.assertEqual(scanned["extras"], [{"label": "VAT", "amount": 4.76, "kind": "tax"}])

    def test_maps_adjustment_query_fields_and_rejects_payment_false_positives(self):
        scanned = extract.azure_to_scanned({
            "analyzeResult": {"documents": [{"fields": {
                "Subtotal": {"valueCurrency": {"amount": 285.75}},
                "Total": {"valueCurrency": {"amount": 373.33, "currencyCode": "USD"}},
                "Tip": {"valueCurrency": {"amount": 62.22}},
                "Credit": {"content": "$373.33", "confidence": 0.605},
                "Discounts": {"content": "$1.60", "confidence": 0.578},
                "GiftCard": {"content": "xxxxxx4949", "confidence": 0.603},
                "Gratuity": {"content": "$62.22", "confidence": 0.395},
                "ProcessingFee": {"content": "$7.42", "confidence": 0.652},
                "TotalDiscount": {"content": "$373.33", "confidence": 0.304},
            }}]}
        }, latency_ms=100)

        self.assertEqual(scanned["extras"], [
            {"label": "Tip", "amount": 62.22, "kind": "tip"},
            {"label": "Discounts", "amount": 1.60, "kind": "discount"},
            {"label": "Processing Fee", "amount": 7.42, "kind": "fee"},
        ])

    def test_finalize_injects_provenance_and_validates(self):
        result = extract._finalize(
            "azure", "prebuilt", extract.azure_to_scanned(AZURE_SAMPLE, 900), 900, "{}", None
        )
        self.assertEqual(result["provider"], "azure")
        self.assertIsNotNone(result["expected"])
        self.assertIn("provenance", result["expected"])
        # Mapped object must satisfy the same contract LLM output is held to.
        self.assertEqual(contract.validate_expected(result["expected"]), [])
        self.assertEqual(result["problems"], [])


AZURE_TAXDETAILS = {
    "analyzeResult": {"documents": [{"fields": {
        "MerchantName": {"valueString": "Shabu House"},
        "Total": {"valueCurrency": {"amount": 50.0, "currencyCode": "USD"}},
        "Subtotal": {"valueNumber": 40.0},
        "TaxDetails": {"valueArray": [
            {"valueObject": {"Description": {"valueString": "Sales Tax"}, "Amount": {"valueNumber": 3.55}}},
            {"valueObject": {"Description": {"valueString": "Service Tax"}, "Amount": {"valueNumber": 2.40}}},
        ]},
        "Tip": {"valueNumber": 6.0},
    }}]}
}


class TaxDetailsTests(unittest.TestCase):
    def test_per_tax_breakdown_emits_multiple_tax_extras(self):
        # P8.4: real receipts carry sales tax + service tax as distinct lines; V1 collapsed them.
        scanned = extract.azure_to_scanned(AZURE_TAXDETAILS, 100)
        tax = [e for e in scanned["extras"] if e["kind"] == "tax"]
        self.assertEqual(len(tax), 2)
        self.assertEqual({e["label"] for e in tax}, {"Sales Tax", "Service Tax"})
        self.assertTrue(any(e["kind"] == "tip" for e in scanned["extras"]))
        self.assertEqual(contract.validate_expected({**scanned, "provenance": {
            "providerName": "a", "providerVersion": "4", "scannedAt": "2026-05-30T00:00:00Z",
            "latencyMs": 0, "retryCount": 0}}), [])

    def test_falls_back_to_totaltax_when_no_taxdetails(self):
        scanned = extract.azure_to_scanned(AZURE_SAMPLE, 100)  # AZURE_SAMPLE has TotalTax only
        self.assertEqual(len([e for e in scanned["extras"] if e["kind"] == "tax"]), 1)


class ClaudeResultParseTests(unittest.TestCase):
    def test_extracts_result_from_event_array(self):
        events = [
            {"type": "system", "subtype": "init"},
            {"type": "result", "subtype": "success", "result": '```json\n{"total": 9.9}\n```'},
        ]
        import json
        text = extract._claude_result_text(json.dumps(events))
        self.assertEqual(extract._json_from_text(text), {"total": 9.9})

    def test_finalize_drops_extra_keys_and_defaults_arrays(self):
        # An LLM that returns only a couple fields still finalizes into a contract-shaped object.
        result = extract._finalize(
            "claude", "opus",
            {"merchantName": "X", "total": 5.0, "subtotal": 5.0, "junkKey": "ignored"},
            1200, "raw", None,
        )
        self.assertNotIn("junkKey", result["expected"])
        self.assertEqual(result["expected"]["lineItems"], [])
        self.assertEqual(result["expected"]["extras"], [])
        self.assertIn("provenance", result["expected"])


class ExtractAzureTests(unittest.TestCase):
    def test_extract_azure_requests_default_query_fields(self):
        saved_ready = extract.ocr.config_ready
        saved_analyze = extract.ocr.analyze_receipt
        seen = {}
        extract.ocr.config_ready = lambda: (True, "ok")

        def fake_analyze(image_bytes, **kwargs):
            seen["query_fields"] = kwargs.get("query_fields")
            return AZURE_SAMPLE

        extract.ocr.analyze_receipt = fake_analyze
        try:
            result = extract.extract_azure(b"\xff\xd8\xff\xe0" + b"x" * 2048)
            self.assertIsNone(result["error"])
            self.assertEqual(seen["query_fields"], extract.ocr.DEFAULT_QUERY_FIELDS)
        finally:
            extract.ocr.config_ready = saved_ready
            extract.ocr.analyze_receipt = saved_analyze


class DispatchTests(unittest.TestCase):
    def test_known_providers(self):
        self.assertEqual(sorted(extract.PROVIDERS), ["azure", "claude", "codex", "gemma3", "qwen"])

    def test_unknown_provider_raises(self):
        from pathlib import Path
        with self.assertRaises(ValueError):
            extract.extract("nope", Path("/tmp/x.jpg"))


class ResizeTests(unittest.TestCase):
    def test_downscales_large_image_keeps_small(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        import io

        big = io.BytesIO()
        Image.new("RGB", (4000, 3000), "white").save(big, "JPEG")
        out = extract._resize_for_vision(big.getvalue(), max_dim=1568)
        w, h = Image.open(io.BytesIO(out)).size
        self.assertEqual(max(w, h), 1568)

        small = io.BytesIO()
        Image.new("RGB", (800, 600), "white").save(small, "JPEG")
        # already fits + upright -> returned unchanged
        self.assertEqual(extract._resize_for_vision(small.getvalue(), max_dim=1568), small.getvalue())

    def test_bakes_in_exif_orientation_even_when_small(self):
        # P1 regression: a small phone photo with a rotation tag must be uprighted before it
        # reaches the vision LLMs (Azure honors EXIF server-side; claude/qwen do not).
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        import io

        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation 6 -> rotate, swapping W/H on transpose
        buf = io.BytesIO()
        Image.new("RGB", (100, 50), "white").save(buf, "JPEG", exif=exif)
        out = extract._resize_for_vision(buf.getvalue(), max_dim=1568)
        # bytes were re-encoded (not the short-circuit original) and dimensions are now uprighted
        self.assertNotEqual(out, buf.getvalue())
        w, h = Image.open(io.BytesIO(out)).size
        self.assertEqual((w, h), (50, 100))


if __name__ == "__main__":
    unittest.main()
