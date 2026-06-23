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
    def _row(self, extractions, *, expected=None, ocr_text=None):
        annotations = {"extractions": extractions}
        if ocr_text is not None:
            annotations["azure_response"] = {"analyzeResult": {"content": ocr_text}}
        return {
            "id": "abc123",
            "name": "sample",
            "image_path": "images/sample.jpg",
            "expected": expected,
            "annotations": annotations,
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

    def test_reconciled_majority_total_can_override_one_provider_outlier(self):
        # Daesung c04031206c0f has subtotal/tax agreement, but Azure selected
        # an impossible $44.00 typed total while Claude and Qwen both read the
        # printed $138.21 total and reconcile it.
        tax = [{"kind": "tax", "label": "Tax", "amount": 11.27}]
        row = self._row({
            "azure": _result(total=44.0, subtotal=126.94, extras=tax),
            "claude": _result(total=138.21, subtotal=126.94, extras=tax),
            "qwen": _result(total=138.21, subtotal=126.94, extras=tax),
        })

        got = review.review_row(row)

        self.assertEqual(got["state"], "ready_candidate")
        self.assertEqual(got["reasons"], [])
        self.assertEqual(got["warnings"], ["provider_outlier_total"])
        self.assertEqual(got["consensus"]["total"], 138.21)
        self.assertEqual(got["consensus"]["totalSupportingProviders"], ["claude", "qwen"])
        self.assertEqual(got["consensus"]["totalOutlierProviders"], ["azure"])

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

    def test_grounded_expected_downgrades_provider_disagreement_to_warning(self):
        # Marathon 0bbded8cc434 is app-grounded at the corrected payment total.
        # Azure's old extraction remains useful evidence, but it should not keep
        # the already-fixed fixture at the top of the active bug queue.
        expected = _result(
            total=63.03,
            subtotal=49.45,
            extras=[
                {"kind": "tax", "label": "Tax", "amount": 4.39},
                {"kind": "tip", "label": "Tip", "amount": 7.42},
                {"kind": "fee", "label": "Processing Fee", "amount": 1.77},
            ],
        )["expected"]
        row = self._row({
            "azure": _result(
                total=53.84,
                subtotal=49.45,
                extras=[
                    {"kind": "tax", "label": "Tax", "amount": 4.39},
                    {"kind": "tip", "label": "Tip", "amount": 7.42},
                    {"kind": "fee", "label": "Processing Fee", "amount": 7.42},
                ],
            ),
            "claude": _result(
                total=63.03,
                subtotal=49.45,
                extras=[
                    {"kind": "tax", "label": "Tax", "amount": 4.39},
                    {"kind": "tip", "label": "Tip", "amount": 7.42},
                    {"kind": "fee", "label": "Processing Fee", "amount": 1.77},
                ],
            ),
        }, expected=expected)

        got = review.review_row(row)

        self.assertEqual(got["state"], "grounded_consistent")
        self.assertEqual(got["reasons"], [])
        self.assertIn("provider_total_disagreement", got["warnings"])
        self.assertIn("provider_extras_disagreement", got["warnings"])

    def test_repo_grounded_fixture_downgrades_provider_disagreement_to_warning(self):
        row = self._row({
            "azure": _result(total=10.0, currency="USD"),
            "claude": _result(total=12.0, currency="AED"),
        })

        got = review.review_row(
            row,
            repo_fixtures={
                "abc123": {
                    "inRepo": True,
                    "grounded": True,
                    "imagePath": "Tests/Fixtures/Receipts/images/abc123.jpg",
                },
            },
        )

        self.assertEqual(got["state"], "grounded_consistent")
        self.assertTrue(got["grounded"])
        self.assertTrue(got["repoFixture"]["grounded"])
        self.assertEqual(got["reasons"], [])
        self.assertIn("in_repo_grounded", got["warnings"])
        self.assertIn("provider_total_disagreement", got["warnings"])
        self.assertIn("provider_currency_disagreement", got["warnings"])

    def test_repo_stub_fixture_does_not_downgrade_provider_disagreement(self):
        row = self._row({
            "azure": _result(total=10.0, currency="USD"),
            "claude": _result(total=12.0, currency="AED"),
        })

        got = review.review_row(
            row,
            repo_fixtures={
                "abc123": {
                    "inRepo": True,
                    "grounded": False,
                    "imagePath": "Tests/Fixtures/Receipts/images/abc123.jpg",
                },
            },
        )

        self.assertEqual(got["state"], "needs_review")
        self.assertFalse(got["grounded"])
        self.assertIn("in_repo_stub", got["warnings"])
        self.assertIn("total_disagreement", got["reasons"])
        self.assertIn("currency_disagreement", got["reasons"])

    def test_grounded_expected_still_flags_true_total_mismatch(self):
        expected = _result(total=11.0, subtotal=9.0)["expected"]
        row = self._row({"azure": _result(), "claude": _result()}, expected=expected)

        got = review.review_row(row)

        self.assertEqual(got["state"], "needs_review")
        self.assertIn("grounded_total_disagreement", got["reasons"])

    def test_repo_grounded_fixture_downgrades_stale_local_expected_mismatch(self):
        expected = _result(total=11.0, subtotal=9.0)["expected"]
        row = self._row({"azure": _result(), "claude": _result()}, expected=expected)

        got = review.review_row(
            row,
            repo_fixtures={
                "abc123": {
                    "inRepo": True,
                    "grounded": True,
                    "imagePath": "Tests/Fixtures/Receipts/images/abc123.jpg",
                },
            },
        )

        self.assertEqual(got["state"], "grounded_consistent")
        self.assertEqual(got["reasons"], [])
        self.assertIn("repo_grounded_total_disagreement", got["warnings"])

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

    def test_review_row_classifies_domain_from_stored_ocr_text(self):
        row = self._row(
            {"azure": _result()},
            ocr_text="TAIER\nTable 8\nSubtotal $88.99\nTip $19.58\nCREDIT CARD SALE $116.47",
        )

        got = review.review_row(row)

        self.assertEqual(got["domain"]["verdict"], "dining")
        self.assertGreaterEqual(got["domain"]["strong"], 1)


class ReviewCorpusCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus.jsonl"
        self.image = Path(self.tmp.name) / "images" / "sample.jpg"
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(SAMPLE_BYTES)

    def tearDown(self):
        self.tmp.cleanup()

    def _append(self, name, extractions, *, expected=None, ocr_text=None):
        row = storage.make_row(
            image_bytes=SAMPLE_BYTES + name.encode(),
            name=name,
            image_path=f"images/{name}.jpg",
            source="test",
        )
        row["expected"] = expected
        row["annotations"]["extractions"] = extractions
        if ocr_text is not None:
            row["annotations"]["azure_response"] = {"analyzeResult": {"content": ocr_text}}
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
        self.assertEqual(report["domainCounts"], {"unsure": 2})
        self.assertEqual(report["providerErrors"], {"qwen": 1})

    def test_review_corpus_uses_ios_fixture_corpus(self):
        row = self._append("review", {
            "azure": _result(total=10.0, currency="USD"),
            "claude": _result(total=12.0, currency="AED"),
        })
        ios_corpus = Path(self.tmp.name) / "ios-corpus.jsonl"
        storage.append_row(ios_corpus, {
            "id": row["id"],
            "name": "review",
            "image_path": "Tests/Fixtures/Receipts/images/review.jpg",
            "expected": _result()["expected"],
        })

        report = review.review_corpus(self.corpus, repo_fixture_corpus_path=ios_corpus)

        self.assertEqual(report["repoFixtureCount"], 1)
        self.assertEqual(report["repoGroundedFixtureCount"], 1)
        self.assertEqual(report["counts"]["grounded_consistent"], 1)
        self.assertEqual(report["rows"][0]["state"], "grounded_consistent")
        self.assertIn("in_repo_grounded", report["rows"][0]["warnings"])

    def test_review_corpus_orders_dining_before_retail_within_state(self):
        self._append(
            "retail",
            {"azure": _result(error="timeout")},
            ocr_text="COSTCO WHOLESALE\nMember 123\nCashier 7\nSKU 001\nTOTAL $40.00",
        )
        self._append(
            "dining",
            {"azure": _result(error="timeout")},
            ocr_text="FUZI PASTA\nTable 6\nSubtotal $285.75\nTax $25.36\nTip $62.22\nTotal $373.33",
        )

        report = review.review_corpus(self.corpus)

        self.assertEqual([row["name"] for row in report["rows"]], ["dining", "retail"])
        self.assertEqual(report["domainCounts"], {"dining": 1, "retail": 1})

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

    def test_main_table_filters_domain(self):
        self._append(
            "dining",
            {"azure": _result(), "claude": _result()},
            ocr_text="RESTAURANT\nServer: A\nTable 2\nSubtotal $9.00\nTip $1.00\nTotal $10.00",
        )
        self._append(
            "retail",
            {"azure": _result(), "claude": _result()},
            ocr_text="STORE #1\nCashier 9\nSKU 12\nReturn policy\nTotal $10.00",
        )

        stdout = StringIO()
        with redirect_stdout(stdout):
            rc = review.main(["--corpus", str(self.corpus), "--domain", "dining"])

        self.assertEqual(rc, 0)
        out = stdout.getvalue()
        self.assertIn("dining", out)
        self.assertNotIn("ready_candidate      retail", out)


if __name__ == "__main__":
    unittest.main()
