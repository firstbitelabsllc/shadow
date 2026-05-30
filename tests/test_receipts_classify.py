"""Unit tests for receipts.classify.classify_text — the dining/retail/invoice keyword gate."""

import sys
import unittest
from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts.classify import classify_text  # noqa: E402

DINING = "SAIGON SHACK\nServer: Anna  Table 12\nPho Tai  14.00\nSpring Rolls 8.00\nSubtotal 22.00\nTax 1.95\nTip 4.00\nTotal $27.95\nThank you!"
GROCERY = "TRADER JOE'S\nStore #543  Cashier: 7\nBananas 0.59 SKU 001\nMilk 3.49 UPC 99\nYou saved 2.00\nTotal $14.20\nReturn policy: 14 days"
INVOICE = "ACME SUPPLY CO\nTAX INVOICE #4471\nBill To: Leo Kwan\nNet 30  Due Date 2026-06-30\nAmount Due $1,240.00\nP.O. 8832  Terms: net 30"


class ClassifyTests(unittest.TestCase):
    def test_restaurant_is_dining(self):
        c = classify_text(DINING)
        self.assertEqual(c["verdict"], "dining")
        self.assertGreaterEqual(c["dining"], 3)
        self.assertTrue(c["money"])

    def test_grocery_is_retail(self):
        c = classify_text(GROCERY)
        self.assertEqual(c["verdict"], "retail")

    def test_invoice_is_invoice(self):
        c = classify_text(INVOICE)
        self.assertEqual(c["verdict"], "invoice")

    def test_sparse_text_is_unsure(self):
        self.assertEqual(classify_text("blurry  $12.00")["verdict"], "unsure")

    def test_empty(self):
        self.assertEqual(classify_text("")["verdict"], "unsure")

    def test_dining_needs_money(self):
        # dining keywords but no money -> not confidently dining
        c = classify_text("server table guest menu dinner")
        self.assertNotEqual(c["verdict"], "dining")

    def test_substring_keywords_do_not_inflate_dining(self):
        # Regression: `bar` in BARCODE, `host` in GHOST, `tea`/`menu` inside other words must NOT
        # count. A pharmacy/grocery receipt full of such substrings must never verdict dining.
        pharmacy = (
            "CVS PHARMACY\nRX READY\nBARCODE 8827\nGHOST PEPPER CHIPS 4.99\n"
            "STEAK SEASONING 3.50\nMENUS PRINTED 0.00\nSUBTOTAL 8.49\nTOTAL $8.49"
        )
        c = classify_text(pharmacy)
        self.assertNotEqual(c["verdict"], "dining")

    def test_generic_beverage_words_alone_are_not_dining(self):
        # Regression: subtotal (signal-free, now dropped) + a few generic beverage nouns must not
        # reach the dining floor without a strong dining-only token.
        store = "GENERIC MART\nsubtotal\ncoffee 2.00\ntea 1.50\nsoda 1.00\nTOTAL $9.00"
        c = classify_text(store)
        self.assertNotEqual(c["verdict"], "dining")
        self.assertEqual(c["strong"], 0)

    def test_dining_requires_strong_keyword(self):
        # cafe/grill/menu are venue/generic nouns; with no server/table/tip/gratuity the verdict
        # stays unsure (-> LLM second pass), never a confident dining commit.
        weak = "CORNER CAFE\nGrill special 9.00\nMenu item 4.00\nDrink 3.00\nTOTAL $16.00"
        self.assertNotEqual(classify_text(weak)["verdict"], "dining")

    def test_real_restaurant_still_passes(self):
        # The strong-keyword + margin gate must not regress a genuine dining receipt.
        self.assertEqual(classify_text(DINING)["verdict"], "dining")


if __name__ == "__main__":
    unittest.main()
