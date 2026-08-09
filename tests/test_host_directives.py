"""Shadow owns a block in a host instruction file without owning the file.

A host instruction file is hand-written, long, and irreplaceable. Every test
here exists because some way of editing it would have destroyed work: appending
duplicates, rewriting the whole file loses text, a partial write truncates it,
and guessing where an unmarked block ends eats the paragraph after it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-host-directives.py"
SHADOW = ROOT / "bin" / "shadow"

_SPEC = importlib.util.spec_from_file_location("shadow_host_directives", SCRIPT)
hd = importlib.util.module_from_spec(_SPEC)
sys.modules["shadow_host_directives"] = hd
_SPEC.loader.exec_module(hd)

_DSPEC = importlib.util.spec_from_file_location("shadow_doctor", ROOT / "scripts" / "shadow-doctor.py")
doctor = importlib.util.module_from_spec(_DSPEC)
sys.modules["shadow_doctor"] = doctor
_DSPEC.loader.exec_module(doctor)

BLOCK = hd.standing_goal()
BEFORE = "# My rules\n\nDo not break these.\n\n"
AFTER = "\n## My own section\n\nStill mine.\n"


class OneSource(unittest.TestCase):
    def test_every_reader_returns_the_same_block(self) -> None:
        # Three readers exist: the awk in bin/shadow, doctor's check, and this
        # writer. If any two disagree, doctor can pass while what got written
        # is different text.
        awk = subprocess.run([str(SHADOW), "goal"], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(hd.standing_goal(), awk)
        self.assertEqual(doctor.standing_goal(), awk)
        self.assertTrue(BLOCK.startswith("## Shadow "))


class WritesTheBlock(unittest.TestCase):
    def _file(self, tmp: Path, contents: str | None) -> Path:
        path = tmp / "CLAUDE.md"
        if contents is not None:
            path.write_text(contents, encoding="utf-8")
        return path

    def test_adds_to_an_existing_file_and_keeps_every_other_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), BEFORE + "tail\n")
            self.assertEqual(hd.apply(path, BLOCK), "added")
            text = path.read_text(encoding="utf-8")
            self.assertIn(BEFORE, text)
            self.assertIn("tail\n", text)
            self.assertEqual(text.count(hd.BEGIN), 1)
            self.assertIn(BLOCK, text)

    def test_creates_the_file_when_the_host_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "CLAUDE.md"
            self.assertEqual(hd.apply(path, BLOCK), "created")
            self.assertIn(BLOCK, path.read_text(encoding="utf-8"))

    def test_running_twice_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), BEFORE)
            hd.apply(path, BLOCK)
            first = path.read_text(encoding="utf-8")
            self.assertEqual(hd.apply(path, BLOCK), "current")
            self.assertEqual(path.read_text(encoding="utf-8"), first)

    def test_an_unmarked_hand_pasted_copy_is_adopted_not_duplicated(self) -> None:
        # The real migration: everyone who pasted the block before markers
        # existed has one. Appending would give them two copies, and doctor
        # would then report "current" while a stale copy sat above it.
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), BEFORE + BLOCK + AFTER)
            self.assertEqual(hd.apply(path, BLOCK), "adopted")
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("## Shadow "), 1)
            self.assertEqual(text.count(hd.BEGIN), 1)
            self.assertIn(BEFORE, text)
            self.assertIn("Still mine.", text)

    def test_a_stale_unmarked_copy_is_adopted_whole(self) -> None:
        # The common migration case: an unmarked paste of an earlier revision,
        # so neither the last line nor the wording matches. Wrapping only the
        # heading would leave the rest of the stale copy in the file — two
        # sets of directives, the older one now unreachable by any refresh.
        with tempfile.TemporaryDirectory() as tmp:
            stale = BLOCK.replace("Proof:", "Evidence:").replace("shadow accept", "shadow flip")
            path = self._file(Path(tmp), BEFORE + stale + AFTER)
            self.assertEqual(hd.apply(path, BLOCK), "adopted")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("shadow flip", text)
            self.assertNotIn("Evidence:", text)
            self.assertEqual(text.count("## Shadow "), 1)
            self.assertEqual(text.count(hd.BEGIN), 1)
            self.assertIn(BLOCK, text)
            self.assertTrue(text.startswith(BEFORE), repr(text[:80]))
            self.assertTrue(text.endswith(AFTER), repr(text[-80:]))

    def test_adoption_stops_at_the_persons_own_prose(self) -> None:
        # Their paragraph directly under the block is not part of it. Eating it
        # is the failure this module exists to prevent.
        with tempfile.TemporaryDirectory() as tmp:
            stale = BLOCK.replace("Proof:", "Evidence:")
            mine = "\nAnd my own note about the block above.\n"
            path = self._file(Path(tmp), BEFORE + stale + mine + AFTER)
            self.assertEqual(hd.apply(path, BLOCK), "adopted")
            text = path.read_text(encoding="utf-8")
            self.assertIn("And my own note about the block above.", text)
            self.assertNotIn("Evidence:", text)
            self.assertIn(BLOCK, text)

    def test_a_stale_marked_block_is_replaced_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stale = BLOCK.replace("shadow accept", "shadow flip")
            path = self._file(Path(tmp), BEFORE + hd.managed(stale) + AFTER)
            self.assertEqual(hd.apply(path, BLOCK), "refreshed")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("shadow flip", text)
            self.assertIn(BLOCK, text)
            self.assertIn("Still mine.", text)
            self.assertEqual(text.count(hd.BEGIN), 1)

    def test_text_outside_the_markers_is_never_touched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stale = BLOCK.replace("Outcome:", "Outcome CHANGED:")
            path = self._file(Path(tmp), BEFORE + hd.managed(stale) + AFTER)
            hd.apply(path, BLOCK)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith(BEFORE), repr(text[:80]))
            self.assertTrue(text.endswith(AFTER), repr(text[-80:]))

    def test_remove_takes_the_block_and_its_markers_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), BEFORE + hd.managed(BLOCK) + AFTER)
            self.assertEqual(hd.apply(path, BLOCK, remove=True), "removed")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("## Shadow ", text)
            self.assertNotIn(hd.BEGIN, text)
            self.assertIn("Do not break these.", text)
            self.assertIn("Still mine.", text)
            self.assertEqual(hd.apply(path, BLOCK, remove=True), "absent")

    def test_the_first_write_leaves_a_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), BEFORE)
            hd.apply(path, BLOCK)
            backup = path.with_suffix(path.suffix + ".bak-shadow")
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), BEFORE)


class RefusesRatherThanGuesses(unittest.TestCase):
    def test_a_begin_marker_with_no_end_is_refused(self) -> None:
        # Someone deleted the terminator. Any guess about how far the block ran
        # risks eating their text, which is the one outcome worth failing for.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CLAUDE.md"
            path.write_text(BEFORE + hd.BEGIN + "\n" + BLOCK + AFTER, encoding="utf-8")
            before = path.read_text(encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                hd.apply(path, BLOCK)
            self.assertIn("end marker", str(caught.exception))
            self.assertEqual(path.read_text(encoding="utf-8"), before)  # untouched

    def test_a_failed_write_leaves_the_original_intact(self) -> None:
        # The write is temp-file-plus-rename precisely so a crash mid-write
        # cannot truncate a person's instruction file.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CLAUDE.md"
            path.write_text(BEFORE, encoding="utf-8")
            original = hd.os.replace
            hd.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
            try:
                with self.assertRaises(OSError):
                    hd.apply(path, BLOCK)
            finally:
                hd.os.replace = original
            self.assertEqual(path.read_text(encoding="utf-8"), BEFORE)
            leftovers = [p.name for p in Path(tmp).iterdir() if p.name.startswith(".shadow-")]
            self.assertEqual(leftovers, [], "a failed write left a temp file behind")


class CursorIsNotInvented(unittest.TestCase):
    def test_cursor_is_not_a_written_host(self) -> None:
        # Its user rules live in application settings, not a file. Writing
        # ~/.cursor/rules/shadow.md would invent a convention and then report
        # success for wiring that does nothing.
        self.assertEqual(sorted(hd.HOSTS), ["claude", "codex"])
        self.assertNotIn("cursor", hd.HOSTS)

    def test_the_cli_says_so_out_loud(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--host", "claude"],
                capture_output=True, text=True, check=False,
                env={**hd.os.environ, "HOME": tmp},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Cursor is not written", result.stdout)


if __name__ == "__main__":
    unittest.main()
