"""The durable write contract: complete or nothing, exclusive never clobbers."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shadow_durable_lib import durable_write  # noqa: E402


class DurableWriteTests(unittest.TestCase):
    def test_replace_writes_complete_content_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.bin"
            durable_write(target, b"new-content", mode=0o640)
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
            self.assertEqual([p for p in Path(tmp).iterdir()], [target])

    def test_replace_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.bin"
            target.write_bytes(b"old")
            durable_write(target, b"new")
            self.assertEqual(target.read_bytes(), b"new")

    def test_exclusive_never_clobbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.bin"
            target.write_bytes(b"old")
            with self.assertRaises(FileExistsError):
                durable_write(target, b"new", exclusive=True)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual([p for p in Path(tmp).iterdir()], [target])

    def test_make_parents_creates_missing_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b" / "out.bin"
            durable_write(target, b"nested", make_parents=True)
            self.assertEqual(target.read_bytes(), b"nested")

    def test_exclusive_link_refuses_a_symlink_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.bin"
            real.write_bytes(b"real")
            link = Path(tmp) / "link.bin"
            link.symlink_to(real)
            with self.assertRaises(FileExistsError):
                durable_write(link, b"new", exclusive=True, follow_symlinks=False)
            self.assertEqual(real.read_bytes(), b"real")


if __name__ == "__main__":
    unittest.main()
