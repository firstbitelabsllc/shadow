"""Unit tests for receipts.contract.validate_expected — the Swift-decode-parity gate.

Pins the code-review P0/P1 fixes: fractional quantity, confidence/operationId types, and the
no-fractional-seconds scannedAt rule must all be rejected (they'd red the whole iOS corpus).
"""

import sys
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import contract  # noqa: E402


def base(**over):
    e = {
        "lineItems": [{"name": "Coffee", "amount": 3.5, "quantity": 1}],
        "extras": [{"label": "Tax", "amount": 0.3, "kind": "tax"}],
        "provenance": {
            "providerName": "a", "providerVersion": "4",
            "scannedAt": "2026-05-30T00:00:00Z", "latencyMs": 0, "retryCount": 0,
        },
        "total": 3.8,
    }
    e.update(over)
    return e


class ContractTests(unittest.TestCase):
    def test_valid_passes(self):
        self.assertEqual(contract.validate_expected(base()), [])

    def test_integral_float_quantity_ok(self):
        self.assertEqual(contract.validate_expected(base(lineItems=[{"name": "x", "amount": 1.0, "quantity": 2.0}])), [])

    def test_fractional_quantity_rejected(self):
        # P0: 0.452 kg produce — Swift Int? throws, reds the whole corpus.
        probs = contract.validate_expected(base(lineItems=[{"name": "Bananas", "amount": 1.2, "quantity": 0.452}]))
        self.assertTrue(any("quantity" in p for p in probs), probs)

    def test_string_quantity_rejected(self):
        probs = contract.validate_expected(base(lineItems=[{"name": "x", "amount": 1, "quantity": "2"}]))
        self.assertTrue(any("quantity" in p for p in probs))

    def test_nonnumeric_lineitem_confidence_rejected(self):
        probs = contract.validate_expected(base(lineItems=[{"name": "x", "amount": 1, "confidence": "high"}]))
        self.assertTrue(any("confidence" in p for p in probs))

    def test_nonnumeric_extra_confidence_rejected(self):
        probs = contract.validate_expected(base(extras=[{"label": "T", "amount": 1.0, "kind": "tax", "confidence": "x"}]))
        self.assertTrue(any("confidence" in p for p in probs))

    def test_nonstring_operationid_rejected(self):
        prov = dict(base()["provenance"], operationId=123)
        probs = contract.validate_expected(base(provenance=prov))
        self.assertTrue(any("operationId" in p for p in probs))

    def test_null_operationid_ok(self):
        prov = dict(base()["provenance"], operationId=None)
        self.assertEqual(contract.validate_expected(base(provenance=prov)), [])

    def test_fractional_seconds_scannedat_rejected(self):
        # Swift .iso8601 default has no fractional seconds.
        prov = dict(base()["provenance"], scannedAt="2026-05-30T00:00:00.5Z")
        probs = contract.validate_expected(base(provenance=prov))
        self.assertTrue(any("scannedAt" in p for p in probs))

    def test_numeric_scannedat_rejected(self):
        prov = dict(base()["provenance"], scannedAt=0)
        probs = contract.validate_expected(base(provenance=prov))
        self.assertTrue(any("scannedAt" in p for p in probs))

    def test_missing_timezone_scannedat_rejected(self):
        prov = dict(base()["provenance"], scannedAt="2026-05-30T00:00:00")
        probs = contract.validate_expected(base(provenance=prov))
        self.assertTrue(any("scannedAt" in p for p in probs))


if __name__ == "__main__":
    unittest.main()
