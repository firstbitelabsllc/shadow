"""Unit tests for receipts.storage — the JSONL corpus store.

Run from repo root: python3 -m unittest tests.test_receipts_storage
Isolation: every test writes to a TemporaryDirectory; the real corpus is never touched.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# The `receipts` package lives under browser/, not the repo root.
BROWSER_DIR = Path(__file__).resolve().parents[1] / "browser"
if str(BROWSER_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_DIR))

from receipts import storage  # noqa: E402


SAMPLE_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 2048 + b"\xff\xd9"


class ComputeIdTests(unittest.TestCase):
    def test_deterministic_12_hex(self):
        a = storage.compute_id(SAMPLE_BYTES)
        b = storage.compute_id(SAMPLE_BYTES)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in a))

    def test_matches_raw_sha256_prefix(self):
        import hashlib

        self.assertEqual(
            storage.compute_id(SAMPLE_BYTES),
            hashlib.sha256(SAMPLE_BYTES).hexdigest()[:12],
        )

    def test_different_bytes_different_id(self):
        self.assertNotEqual(
            storage.compute_id(SAMPLE_BYTES),
            storage.compute_id(SAMPLE_BYTES + b"x"),
        )


class IsoNowTests(unittest.TestCase):
    def test_utc_iso8601_z_suffix(self):
        now = storage.iso_now()
        self.assertTrue(now.endswith("Z"))
        self.assertRegex(now, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class MakeRowTests(unittest.TestCase):
    def test_schema_shape_matches_fixture_contract(self):
        row = storage.make_row(
            image_bytes=SAMPLE_BYTES,
            name="lunch",
            image_path="images/abc.jpg",
            source="test",
            tags=["a", "b"],
        )
        self.assertEqual(set(row.keys()), {"id", "name", "image_path", "expected", "annotations"})
        self.assertIsNone(row["expected"])
        self.assertEqual(row["id"], storage.compute_id(SAMPLE_BYTES))
        self.assertEqual(
            set(row["annotations"].keys()), {"source", "imported_at", "tags", "known_issues"}
        )
        self.assertEqual(row["annotations"]["tags"], ["a", "b"])
        self.assertEqual(row["annotations"]["known_issues"], [])

    def test_leo_note_lands_in_annotations(self):
        row = storage.make_row(
            image_bytes=SAMPLE_BYTES, name="x", image_path=None, source="t", leo_note="hi"
        )
        self.assertEqual(row["annotations"]["leo_note"], "hi")

    def test_private_sets_top_level_flag(self):
        row = storage.make_row(
            image_bytes=SAMPLE_BYTES, name="x", image_path=None, source="t", private=True
        )
        self.assertTrue(row["private"])

    def test_pii_guard_private_with_image_path_raises(self):
        with self.assertRaises(ValueError):
            storage.make_row(
                image_bytes=SAMPLE_BYTES,
                name="x",
                image_path="images/abc.jpg",
                source="t",
                private=True,
            )


class CorpusIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _row(self, name="x", extra_byte=b""):
        return storage.make_row(
            image_bytes=SAMPLE_BYTES + extra_byte, name=name, image_path=None, source="t"
        )

    def test_read_all_missing_file_is_empty(self):
        self.assertEqual(storage.read_all(self.corpus), [])

    def test_append_idempotent_by_id(self):
        row = self._row()
        self.assertTrue(storage.append_row(self.corpus, row))
        self.assertFalse(storage.append_row(self.corpus, row))
        self.assertEqual(len(storage.read_all(self.corpus)), 1)

    def test_append_missing_id_raises(self):
        with self.assertRaises(ValueError):
            storage.append_row(self.corpus, {"name": "no id"})

    def test_replace_row_updates_and_forces_id(self):
        row = self._row(name="before")
        storage.append_row(self.corpus, row)
        updated = dict(row)
        updated["name"] = "after"
        updated["id"] = "tampered"  # caller must not be able to change the id
        self.assertTrue(storage.replace_row(self.corpus, row["id"], updated))
        got = storage.find_by_id(self.corpus, row["id"])
        self.assertEqual(got["name"], "after")
        self.assertEqual(got["id"], row["id"])

    def test_replace_missing_id_returns_false(self):
        self.assertFalse(storage.replace_row(self.corpus, "nope", {"id": "nope"}))

    def test_find_by_id_hit_and_miss(self):
        row = self._row()
        storage.append_row(self.corpus, row)
        self.assertIsNotNone(storage.find_by_id(self.corpus, row["id"]))
        self.assertIsNone(storage.find_by_id(self.corpus, "missing"))

    def test_corrupt_line_raises_corpus_error_with_line_number(self):
        self.corpus.write_text('{"id":"a","name":"ok"}\nnot valid json\n', encoding="utf-8")
        with self.assertRaises(storage.CorpusError) as ctx:
            storage.read_all(self.corpus)
        self.assertIn("line 2", str(ctx.exception))
        self.assertIsInstance(ctx.exception, ValueError)  # back-compat

    def test_concurrent_replace_of_distinct_rows_all_survive(self):
        import threading

        rows = [self._row(name=f"r{i}", extra_byte=bytes([i])) for i in range(5)]
        for r in rows:
            storage.append_row(self.corpus, r)
        barrier = threading.Barrier(len(rows))

        def worker(row):
            barrier.wait()
            updated = dict(row)
            updated["name"] = row["name"] + "-updated"
            storage.replace_row(self.corpus, row["id"], updated)

        threads = [threading.Thread(target=worker, args=(r,)) for r in rows]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        names = {r["name"] for r in storage.read_all(self.corpus)}
        self.assertEqual(names, {f"r{i}-updated" for i in range(5)})


class SafeImageAbsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name)
        self.images = self.parent / "images"
        self.images.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_contained_path_resolves(self):
        (self.images / "abc.jpg").write_bytes(b"x")
        got = storage.safe_image_abs(self.parent, self.images, "images/abc.jpg")
        self.assertEqual(got, (self.images / "abc.jpg").resolve())

    def test_traversal_rejected(self):
        for evil in ("../../etc/passwd", "/etc/passwd", "../server.py", "images/../../secret"):
            self.assertIsNone(storage.safe_image_abs(self.parent, self.images, evil), evil)


if __name__ == "__main__":
    unittest.main()
