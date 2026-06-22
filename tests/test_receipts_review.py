"""Unit tests for receipts.review corpus triage."""

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import review, storage  # noqa: E402


SAMPLE_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 2048 + b"\xff\xd9"


def _result(total=10.0, subtotal=9.0, currency="USD", extras=None, error=None, problems=None):
    expected = None if error else {
        "merchantName": "Receipt",
        "currencyCode": currency,
        "subtotal": subtotal,
        "total": total,
        "lineItems": [{"name": "Item", "amount": subtotal, "quantity": 1}],
        "extras": extras if extras is not None else [{"kind": "tax", "label": "Tax", "amount": 1.0}],
    }
    return {
        "expected": expected,
        "latency_ms": 12,
        "error": error,
        "problems": problems or [],
    }


class ReviewRowTests(unittest.TestCase):
    def _row(self, extractions, *, expected=None):
        return {
            "id": "abc123",
            "name": "sample",
            "image_path": "images/sample.jpg",
            "expected": expected,
            "annotations": {"extractions": extractions},
        }

    def test_marks_unpromoted_consensus_as_ready_candidate(self):
        row = self._row({
            "azure": _result(),
            "claude": _result(),
            "qwen": _result(),
        })

        got = review.review_row(row)

        self.assertEqual(got["state"], "ready_candidate")
        self.assertEqual(got["reasons"], [])
        self.assertEqual(got["consensus"]["total"], 10.0)
        self.assertTrue(got["consensus"]["anyReconciles"])

    def test_single_provider_total_is_not_ready_candidate(self):
        # Molly Tea 7bc456d6f7c7 looked ready because Qwen read order "#8"
        # as an $8 total while Azure and Claude had no amount evidence.
        row = self._row({
            "azure": _result(total=None, subtotal=None, currency=None, extras=[]),
            "claude": _result(total=None, subtotal=None, currency="USD", extras=[]),
            "qwen": _result(total=8.0, subtotal=8.0, currency="USD", extras=[]),
        })

        got = review.review_row(row)

        self.assertEqual(got["state"], "needs_review")
        self.assertIn("insufficient_total_agreement", got["reasons"])
        self.assertEqual(got["consensus"]["total"], 8.0)

    def test_flags_qwen_extra_amount_disagreement_even_when_total_matches(self):
        row = self._row({
            "azure": _result(),
            "claude": _result(),
            "qwen": _result(extras=[
                {"kind": "tax", "label": "VAT", "amount": 1.0},
                {"kind": "tax", "label": "GST", "amount": 2.0},
            ]),
        })

        got = review.review_row(row)

        self.assertEqual(got["state"], "needs_review")
        self.assertIn("extras_disagreement", got["reasons"])

    def test_flags_provider_errors(self):
        row = self._row({
            "azure": _result(),
            "claude": _result(),
            "qwen": _result(error="timed out"),
        })

        got = review.review_row(row)

        self.assertEqual(got["state"], "needs_review")
        self.assertIn("provider_error", got["reasons"])

    def test_flags_total_currency_and_reconcile_disagreement(self):
        row = self._row({
            "azure": _result(total=10.0, currency="USD"),
            "claude": _result(total=12.0, currency="AED"),
        })

        got = review.review_row(row)

        self.assertEqual(got["state"], "needs_review")
        self.assertIn("total_disagreement", got["reasons"])
        self.assertIn("currency_disagreement", got["reasons"])

    def test_grounded_consistent_when_expected_matches_consensus(self):
        expected = _result()["expected"]
        row = self._row({"azure": _result(), "claude": _result()}, expected=expected)

        got = review.review_row(row)

        self.assertEqual(got["state"], "grounded_consistent")
        self.assertTrue(got["grounded"])

    def test_included_tax_reconciles_when_subtotal_already_equals_total(self):
        included_tax = _result(total=56.0, subtotal=56.0, currency="AUD", extras=[
            {"kind": "tax", "label": "GST(10%)", "amount": 5.10},
        ])
        row = self._row({
            "azure": included_tax,
            "claude": included_tax,
            "qwen": included_tax,
        }, expected=included_tax["expected"])

        got = review.review_row(row)

        self.assertEqual(got["state"], "grounded_consistent")
        self.assertEqual(got["reasons"], [])
        self.assertTrue(got["consensus"]["anyReconciles"])

    def test_included_tax_reconciles_with_non_tax_extras_only_once(self):
        included_tax_with_service = _result(total=102.0, subtotal=100.0, currency="AUD", extras=[
            {"kind": "serviceCharge", "label": "Service charge", "amount": 2.0},
            {"kind": "tax", "label": "GST Included In Total", "amount": 9.27},
        ])
        row = self._row({
            "azure": included_tax_with_service,
            "claude": included_tax_with_service,
        }, expected=included_tax_with_service["expected"])

        got = review.review_row(row)

        self.assertEqual(got["state"], "grounded_consistent")
        self.assertEqual(got["reasons"], [])

    def test_fee_only_non_reconcile_still_needs_review(self):
        fee_only = _result(total=56.0, subtotal=56.0, currency="USD", extras=[
            {"kind": "fee", "label": "Service fee", "amount": 2.0},
        ])
        row = self._row({"azure": fee_only, "claude": fee_only})

        got = review.review_row(row)

        self.assertEqual(got["state"], "needs_review")
        self.assertIn("no_reconciled_provider", got["reasons"])


class ReviewCorpusCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus.jsonl"
        self.image = Path(self.tmp.name) / "images" / "sample.jpg"
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(SAMPLE_BYTES)

    def tearDown(self):
        self.tmp.cleanup()

    def _append(self, name, extractions, *, expected=None):
        row = storage.make_row(
            image_bytes=SAMPLE_BYTES + name.encode(),
            name=name,
            image_path=f"images/{name}.jpg",
            source="test",
        )
        row["expected"] = expected
        row["annotations"]["extractions"] = extractions
        storage.append_row(self.corpus, row)
        return row

    def test_review_corpus_counts_states(self):
        self._append("ready", {"azure": _result(), "claude": _result()})
        self._append("review", {"azure": _result(), "qwen": _result(error="timed out")})

        report = review.review_corpus(self.corpus)

        self.assertEqual(report["rowCount"], 2)
        self.assertEqual(report["withExtractions"], 2)
        self.assertEqual(report["counts"]["ready_candidate"], 1)
        self.assertEqual(report["counts"]["needs_review"], 1)
        self.assertEqual(report["providerErrors"], {"qwen": 1})

    def test_main_json_is_read_only(self):
        self._append("ready", {"azure": _result(), "claude": _result()})
        before = self.corpus.read_text(encoding="utf-8")

        stdout = StringIO()
        with redirect_stdout(stdout):
            rc = review.main(["--corpus", str(self.corpus), "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["rowCount"], 1)
        self.assertEqual(self.corpus.read_text(encoding="utf-8"), before)

    def test_main_table_filters_state(self):
        self._append("ready", {"azure": _result(), "claude": _result()})
        self._append("review", {"azure": _result(), "qwen": _result(error="timed out")})

        stdout = StringIO()
        with redirect_stdout(stdout):
            rc = review.main(["--corpus", str(self.corpus), "--state", "needs_review"])

        self.assertEqual(rc, 0)
        out = stdout.getvalue()
        self.assertIn("needs_review", out)
        self.assertIn("provider_error", out)
        self.assertNotIn("ready_candidate  ", out)


if __name__ == "__main__":
    unittest.main()
