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
        # already fits -> returned unchanged
        self.assertEqual(extract._resize_for_vision(small.getvalue(), max_dim=1568), small.getvalue())


if __name__ == "__main__":
    unittest.main()
