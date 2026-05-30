"""Unit tests for receipts.telemetry — OCR observability event-building + local capture.

Pure logic + the LAN-local jsonl fallback only. No network, no PostHog key.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import telemetry  # noqa: E402


def _res(expected, latency=100, error=None, problems=None):
    return {"provider": "x", "latency_ms": latency, "expected": expected,
            "error": error, "problems": problems or []}


# Azure dropped a CC fee (40 + 3.55 tax + 6 tip = 49.55 ≠ 50 total); claude caught it.
AZURE = _res({"total": 50.0, "subtotal": 40.0, "currencyCode": "USD",
              "lineItems": [{"name": "a"}, {"name": "b"}],
              "extras": [{"kind": "tax", "amount": 3.55}, {"kind": "tip", "amount": 6.0}]})
CLAUDE = _res({"total": 50.0, "subtotal": 40.0, "currencyCode": "USD",
               "lineItems": [{"name": "a"}, {"name": "b"}],
               "extras": [{"kind": "tax", "amount": 3.55}, {"kind": "tip", "amount": 6.0},
                          {"kind": "fee", "amount": 0.45}]})


class BuildScanEventsTests(unittest.TestCase):
    def test_one_scan_completed_per_provider(self):
        events = telemetry.build_scan_events({"azure": AZURE, "claude": CLAUDE}, row_id="r1")
        scans = [e for e in events if e["event"] == "ocr.scan.completed"]
        self.assertEqual({e["properties"]["provider"] for e in scans}, {"azure", "claude"})

    def test_reconcile_flags_the_dropped_fee(self):
        events = telemetry.build_scan_events({"azure": AZURE, "claude": CLAUDE}, row_id="r1")
        props = {e["properties"]["provider"]: e["properties"]
                 for e in events if e["event"] == "ocr.scan.completed"}
        # Azure's subtotal+extras misses the total (dropped fee) -> does not reconcile.
        self.assertFalse(props["azure"]["totalReconciles"])
        self.assertFalse(props["azure"]["hasExtraBeyondTaxTip"])
        # Claude recovered the fee -> reconciles + carries an extra beyond tax/tip.
        self.assertTrue(props["claude"]["totalReconciles"])
        self.assertTrue(props["claude"]["hasExtraBeyondTaxTip"])

    def test_divergence_names_the_kind_azure_missed(self):
        events = telemetry.build_scan_events({"azure": AZURE, "claude": CLAUDE}, row_id="r1")
        extras_div = [e for e in events if e["event"] == "ocr.divergence"
                      and e["properties"]["field"] == "extras"]
        self.assertEqual(len(extras_div), 1)
        self.assertEqual(extras_div[0]["properties"]["azureMissedKinds"], ["fee"])
        self.assertEqual(extras_div[0]["properties"]["flagship"], "claude")

    def test_scalar_divergence_on_total(self):
        cheap = _res({"total": 47.0, "subtotal": 40.0, "currencyCode": "USD", "extras": []})
        events = telemetry.build_scan_events({"azure": AZURE, "claude": cheap}, row_id="r1")
        totals = [e for e in events if e["event"] == "ocr.divergence"
                  and e["properties"]["field"] == "total"]
        self.assertEqual(len(totals), 1)
        self.assertEqual(totals[0]["properties"]["azureValue"], 50.0)
        self.assertEqual(totals[0]["properties"]["flagshipValue"], 47.0)

    def test_no_divergence_when_azure_errored(self):
        events = telemetry.build_scan_events(
            {"azure": _res(None, error="boom"), "claude": CLAUDE}, row_id="r1")
        self.assertEqual([e for e in events if e["event"] == "ocr.divergence"], [])

    def test_reconcile_none_when_inputs_missing(self):
        events = telemetry.build_scan_events({"claude": _res({"total": 9.0})}, row_id="r1")
        self.assertIsNone(events[0]["properties"]["totalReconciles"])


class LocalCaptureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_path = telemetry.LOCAL_EVENTS_PATH
        self._orig_key = os.environ.pop("POSTHOG_API_KEY", None)
        telemetry.LOCAL_EVENTS_PATH = Path(self._tmp.name) / "events.jsonl"

    def tearDown(self):
        telemetry.LOCAL_EVENTS_PATH = self._orig_path
        if self._orig_key is not None:
            os.environ["POSTHOG_API_KEY"] = self._orig_key
        self._tmp.cleanup()

    def test_emit_scan_appends_jsonl_when_no_key(self):
        n = telemetry.emit_scan({"azure": AZURE, "claude": CLAUDE}, row_id="r9")
        self.assertGreater(n, 0)
        lines = telemetry.LOCAL_EVENTS_PATH.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), n)
        first = json.loads(lines[0])
        self.assertIn("ts", first)
        self.assertEqual(first["distinct_id"], "corpus")
        self.assertTrue(first["event"].startswith("ocr."))


if __name__ == "__main__":
    unittest.main()
