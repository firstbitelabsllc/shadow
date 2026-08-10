"""Shadow owns a block in a host instruction file without owning the file.

A host instruction file is hand-written, long, and irreplaceable. Every test
here exists because some way of editing it would have destroyed work: appending
duplicates, rewriting the whole file loses text, a partial write truncates it,
and guessing where an unmarked block ends eats the paragraph after it.
"""

from __future__ import annotations

import importlib.util
import os
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


class ASymlinkedHostFileIsWrittenThrough(unittest.TestCase):
    """One canonical directive file, linked from each host that reads one.

    `os.replace` onto a symlink replaces THE LINK with a regular file and
    leaves what it pointed at untouched, so before this a symlinked host file
    survived exactly zero installs: the link became a copy, the canonical file
    never received the block, and the install printed success either way. The
    write resolves the link first, so the canonical file is what changes and
    the link is still a link afterwards.
    """

    def _linked(self, tmp: Path, *, contents: str = BEFORE) -> tuple[Path, Path]:
        """A canonical file in one directory and a host path pointing at it."""
        host = tmp / ".claude"
        host.mkdir(parents=True)
        canonical = tmp / "canonical" / "DIRECTIVES.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text(contents, encoding="utf-8")
        link = host / "CLAUDE.md"
        link.symlink_to(canonical)
        return link, canonical

    def test_the_link_survives_and_the_canonical_file_carries_the_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            self.assertEqual(hd.apply(link, BLOCK), "added")
            self.assertTrue(link.is_symlink(), "the link was replaced by a regular file")
            self.assertEqual(Path(os.readlink(link)), canonical)
            text = canonical.read_text(encoding="utf-8")
            self.assertIn(BLOCK, text)
            self.assertIn(BEFORE, text)

    def test_a_relative_link_resolves_against_the_directory_holding_it(self) -> None:
        # A link people write by hand is usually relative, and resolving one
        # against the process's directory instead of the link's writes into
        # whatever happens to be next to the current directory.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            link.unlink()
            link.symlink_to(Path("..") / "canonical" / "DIRECTIVES.md")
            self.assertEqual(hd.apply(link, BLOCK), "added")
            self.assertTrue(link.is_symlink())
            self.assertIn(BLOCK, canonical.read_text(encoding="utf-8"))

    def test_a_chain_of_links_lands_on_the_file_at_the_end(self) -> None:
        # Migrations leave chains: the host file points at yesterday's path,
        # which points at the canonical one. Every link in it stays a link.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            middle = Path(tmp) / "previous-home.md"
            middle.symlink_to(canonical)
            link.unlink()
            link.symlink_to(middle)
            self.assertEqual(hd.apply(link, BLOCK), "added")
            self.assertTrue(link.is_symlink())
            self.assertTrue(middle.is_symlink())
            self.assertIn(BLOCK, canonical.read_text(encoding="utf-8"))

    def test_a_link_that_leaves_the_home_directory_is_written_not_refused(self) -> None:
        # The reason anyone makes one of these links: the canonical file lives
        # in a private repository, so it is versioned and shared between
        # machines. Where the link goes is the person's business; refusing to
        # follow it out of the home directory would refuse the whole feature.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            (home / ".claude").mkdir(parents=True)
            canonical = Path(tmp) / "elsewhere" / "DIRECTIVES.md"
            canonical.parent.mkdir(parents=True)
            canonical.write_text(BEFORE, encoding="utf-8")
            link = home / ".claude" / "CLAUDE.md"
            link.symlink_to(canonical)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--host", "claude"],
                capture_output=True, text=True, check=False,
                env={**os.environ, "HOME": str(home)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("added:", result.stdout)
            self.assertTrue(link.is_symlink(), result.stdout)
            self.assertIn(BLOCK, canonical.read_text(encoding="utf-8"))

    def test_a_broken_link_is_refused_and_no_file_is_invented(self) -> None:
        # A path with nothing at it says "nothing here yet" and is created. A
        # link with nothing at the end says something else, and the two honest
        # readings — the repository is not cloned on this machine yet, or the
        # path is a typo — want opposite actions. Creating the target picks one
        # silently: it invents a file where shadow guessed, reports success,
        # and leaves the text the person meant to edit somewhere else.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            missing = canonical.parent / "not-cloned-yet.md"
            link.unlink()
            link.symlink_to(missing)
            with self.assertRaises(ValueError) as caught:
                hd.apply(link, BLOCK)
            self.assertIn("does not exist", str(caught.exception))
            self.assertTrue(link.is_symlink())
            self.assertFalse(missing.exists())

    def test_a_link_to_something_that_is_not_a_file_is_refused(self) -> None:
        # Following a link is not the same as following it anywhere. A
        # directory, a device, or a fifo at the end of one is not a directive
        # file that lost its way, and writing to it is not a recoverable
        # mistake.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            link.unlink()
            link.symlink_to(canonical.parent)
            with self.assertRaises(ValueError) as caught:
                hd.apply(link, BLOCK)
            self.assertIn("not a regular file", str(caught.exception))
            self.assertTrue(canonical.parent.is_dir())
            self.assertEqual(canonical.read_text(encoding="utf-8"), BEFORE)

    def test_a_chain_of_links_that_loops_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link, _ = self._linked(Path(tmp))
            other = Path(tmp) / "round-again.md"
            link.unlink()
            link.symlink_to(other)
            other.symlink_to(link)
            with self.assertRaises(ValueError) as caught:
                hd.apply(link, BLOCK)
            self.assertIn("loops", str(caught.exception))
            self.assertTrue(link.is_symlink())

    def test_the_backup_sits_beside_the_canonical_file_not_the_link(self) -> None:
        # The backup holds the bytes that are about to be overwritten, and
        # those bytes live in the canonical file. Left beside the link it reads
        # as a backup OF the link, so the obvious recovery — copy it back over
        # CLAUDE.md — replaces the link with a regular file, which is the
        # defect this whole class exists to prevent. Beside the target the same
        # recovery restores the file that actually changed, and several hosts
        # linking at one canonical file leave one backup of it rather than one
        # per link, each snapshotting a different moment.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            hd.apply(link, BLOCK)
            beside_target = canonical.with_suffix(canonical.suffix + ".bak-shadow")
            beside_link = link.with_suffix(link.suffix + ".bak-shadow")
            self.assertEqual(beside_target.read_text(encoding="utf-8"), BEFORE)
            self.assertFalse(beside_link.exists(), "restoring this would destroy the link")

    def test_the_canonical_file_and_its_backup_keep_the_mode_it_had(self) -> None:
        # Both directions are load-bearing. A fresh temp file is 0600, so a
        # 0644 file quietly becomes private — invisible in git, and this file
        # is shared between machines. A copy made with the default mask goes
        # the other way and publishes a 0600 file's contents at 0644.
        for mode in (0o600, 0o644):
            with self.subTest(oct(mode)), tempfile.TemporaryDirectory() as tmp:
                link, canonical = self._linked(Path(tmp))
                canonical.chmod(mode)
                hd.apply(link, BLOCK)
                backup = canonical.with_suffix(canonical.suffix + ".bak-shadow")
                self.assertEqual(canonical.stat().st_mode & 0o777, mode)
                self.assertEqual(backup.stat().st_mode & 0o777, mode)

    def test_writing_twice_through_the_link_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            hd.apply(link, BLOCK)
            first = canonical.read_text(encoding="utf-8")
            self.assertEqual(hd.apply(link, BLOCK), "current")
            self.assertEqual(canonical.read_text(encoding="utf-8"), first)
            self.assertTrue(link.is_symlink())

    def test_remove_takes_the_block_out_of_the_canonical_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp), contents=BEFORE + hd.managed(BLOCK) + AFTER)
            self.assertEqual(hd.apply(link, BLOCK, remove=True), "removed")
            text = canonical.read_text(encoding="utf-8")
            self.assertNotIn(hd.BEGIN, text)
            self.assertIn("Do not break these.", text)
            self.assertIn("Still mine.", text)
            self.assertTrue(link.is_symlink())

    def test_a_failed_write_leaves_the_link_and_the_canonical_file_as_they_were(self) -> None:
        # A crash mid-install must not be the thing that costs someone their
        # link either. Nothing is created anywhere: no temp file, and no
        # half-taken backup standing in for a write that never happened.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            original = hd.os.replace
            hd.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
            try:
                with self.assertRaises(OSError):
                    hd.apply(link, BLOCK)
            finally:
                hd.os.replace = original
            self.assertTrue(link.is_symlink())
            self.assertEqual(canonical.read_text(encoding="utf-8"), BEFORE)
            self.assertEqual([p.name for p in canonical.parent.iterdir()], [canonical.name])
            self.assertEqual([p.name for p in link.parent.iterdir()], [link.name])


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

    def test_an_unmarked_older_revision_is_refused_not_guessed_at(self) -> None:
        # Its last line has changed, so nothing in the file marks where it
        # ends. Shape is not evidence: a note glued under the final paragraph,
        # or one of their own paragraphs opening "Word: ", reads exactly like
        # block text. Stopping early leaves half a stale copy behind; reaching
        # further eats their writing. Say so and let the person draw the line.
        stale = BLOCK.replace("re-observe read/gate proofs yourself.", "re-check them yourself.")
        self.assertNotEqual(stale.splitlines()[-1], BLOCK.splitlines()[-1])
        for name, contents in {
            "plain": BEFORE + stale + AFTER,
            "their note glued under it": BEFORE + stale + "\nAnd my own note.\n" + AFTER,
            "their own labelled paragraph": BEFORE + stale + "\n\nNote: mine, not shadow's.\n" + AFTER,
        }.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "CLAUDE.md"
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError) as caught:
                    hd.apply(path, BLOCK)
                self.assertIn("delete that block by hand", str(caught.exception))
                self.assertEqual(path.read_text(encoding="utf-8"), contents)  # untouched

    def test_the_refusal_names_the_host_and_keeps_going(self) -> None:
        # One unadoptable host must not stop the other, and the person needs to
        # know which file to open.
        with tempfile.TemporaryDirectory() as tmp:
            claude = Path(tmp) / ".claude" / "CLAUDE.md"
            claude.parent.mkdir(parents=True)
            stale = BLOCK.replace("re-observe read/gate proofs yourself.", "re-check them yourself.")
            claude.write_text(BEFORE + stale, encoding="utf-8")
            (Path(tmp) / ".codex").mkdir()
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                capture_output=True, text=True, check=False,
                env={**hd.os.environ, "HOME": tmp},
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("failed:    claude:", result.stderr)
            self.assertIn("created:   codex", result.stdout)

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


class TheWindowBetweenResolveAndWriteIsGuarded(unittest.TestCase):
    """The world keeps moving after the symlink resolves.

    Between resolution and the rename, the target can be deleted or swapped.
    Renaming anyway would recreate a file someone deliberately removed, or —
    the sharp case — destroy a fresh symlink planted at the resolved path,
    which is this feature's own defect one level down. The races are
    real but their window is milliseconds, so these tests drive the module's
    explicit seam (`_test_between_resolve_and_write`) instead of racing
    threads: a probabilistic test would pass for years while the guard rotted.

    Identity is the file, not the content: a same-bytes file swapped in is
    still not the file that was resolved — and not the inode NUMBER either,
    which the filesystem is free to hand straight back to the replacement.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.target = root / "repo" / "DIRECTIVES.md"
        self.target.parent.mkdir()
        self.target.write_text("owner text\n", encoding="utf-8")
        self.link = root / "CLAUDE.md"
        self.link.symlink_to(self.target)

    def tearDown(self) -> None:
        hd._test_between_resolve_and_write = None
        self._tmp.cleanup()

    def _mutate(self, action) -> None:
        hd._test_between_resolve_and_write = action

    def test_a_target_deleted_inside_the_window_is_not_recreated(self) -> None:
        self._mutate(lambda: self.target.unlink())
        with self.assertRaisesRegex(ValueError, "vanished after it was resolved"):
            hd.apply(self.link, BLOCK)
        self.assertFalse(self.target.exists(),
                         "the write recreated a file that was deliberately removed")

    def test_a_symlink_planted_inside_the_window_is_not_destroyed(self) -> None:
        elsewhere = self.target.parent / "elsewhere.md"
        elsewhere.write_text("someone else's file\n", encoding="utf-8")

        def swap() -> None:
            self.target.unlink()
            self.target.symlink_to(elsewhere)

        self._mutate(swap)
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            hd.apply(self.link, BLOCK)
        self.assertTrue(self.target.is_symlink(), "the planted link was destroyed")
        self.assertEqual(elsewhere.read_text(encoding="utf-8"), "someone else's file\n")

    def test_a_same_content_file_swapped_inside_the_window_is_refused(self) -> None:
        original = self.target.read_text(encoding="utf-8")

        def swap() -> None:
            self.target.unlink()
            self.target.write_text(original, encoding="utf-8")  # same bytes, new file

        self._mutate(swap)
        with self.assertRaisesRegex(ValueError, "changed identity"):
            hd.apply(self.link, BLOCK)

    def test_a_swap_onto_a_recycled_inode_number_is_still_refused(self) -> None:
        # The test above only catches the swap on filesystems that hand the
        # replacement a fresh inode number. Numbers are recycled: ext4 gives
        # the new file the one it just freed, so the pair the guard compares
        # matches and the swap walks through — which is how this passed on a
        # developer's overlayfs and failed on CI. Here the recycling is forced
        # rather than hoped for: os.lstat is made to report the number the
        # resolved file had, and the guard must still refuse.
        original = self.target.read_text(encoding="utf-8")
        before = os.lstat(self.target)
        real_lstat = os.lstat

        class _Recycled:
            """A stat of the new file, wearing the old one's number."""

            def __init__(self, of: os.stat_result) -> None:
                self.st_mode = of.st_mode
                self.st_dev = before.st_dev
                self.st_ino = before.st_ino

        def swap() -> None:
            self.target.unlink()
            self.target.write_text(original, encoding="utf-8")
            os.lstat = lambda p, *a, **k: (
                _Recycled(real_lstat(p, *a, **k))
                if Path(p) == self.target else real_lstat(p, *a, **k)
            )

        self.addCleanup(setattr, os, "lstat", real_lstat)
        self._mutate(swap)
        with self.assertRaisesRegex(ValueError, "changed identity"):
            hd.apply(self.link, BLOCK)
        self.assertEqual(self.target.read_text(encoding="utf-8"), original,
                         "the write landed in a file that was not the one resolved")

    def test_a_file_appearing_during_a_fresh_create_is_not_clobbered(self) -> None:
        fresh = Path(self._tmp.name) / "codex" / "AGENTS.md"

        def plant() -> None:
            fresh.parent.mkdir(parents=True, exist_ok=True)
            fresh.write_text("someone got here first\n", encoding="utf-8")

        self._mutate(plant)
        with self.assertRaisesRegex(ValueError, "appeared while the install was writing"):
            hd.apply(fresh, BLOCK)
        self.assertEqual(fresh.read_text(encoding="utf-8"), "someone got here first\n")

    def test_the_undisturbed_path_still_writes_through(self) -> None:
        # A guard that fires on everything is as useless as one that never
        # fires. With no mutation, the write lands in the target and the link
        # survives.
        self.assertEqual(hd.apply(self.link, BLOCK), "added")
        self.assertTrue(self.link.is_symlink())
        self.assertIn(hd.BEGIN, self.target.read_text(encoding="utf-8"))


class AFailedWriteLeavesNoNewBackup(unittest.TestCase):
    """All-or-nothing includes the backup.

    The prior failure test only failed BACKUP creation. If the backup lands
    and the final replace then fails, a fresh `.bak-shadow` records a change
    that never happened — and its existence makes the NEXT run skip backing
    up the state that actually preceded it. A backup made by this run is
    removed on failure; a pre-existing backup is somebody's earlier state and
    is never touched.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.target = root / "repo" / "DIRECTIVES.md"
        self.target.parent.mkdir()
        self.target.write_text("owner text\n", encoding="utf-8")
        self.link = root / "CLAUDE.md"
        self.link.symlink_to(self.target)
        self.backup = self.target.with_suffix(self.target.suffix + ".bak-shadow")

    def tearDown(self) -> None:
        hd._test_between_resolve_and_write = None
        self._tmp.cleanup()

    def _fail_the_final_write(self) -> None:
        # Deleting the target inside the window makes the final write refuse
        # AFTER the backup was created — exactly the ordering under test.
        hd._test_between_resolve_and_write = lambda: self.target.unlink()

    def test_a_backup_made_this_run_is_removed_when_the_write_fails(self) -> None:
        self._fail_the_final_write()
        with self.assertRaises(ValueError):
            hd.apply(self.link, BLOCK)
        self.assertFalse(self.backup.exists(),
                         "a backup survived a write that never landed")

    def test_a_pre_existing_backup_is_never_touched(self) -> None:
        self.backup.write_text("an earlier state\n", encoding="utf-8")
        self._fail_the_final_write()
        with self.assertRaises(ValueError):
            hd.apply(self.link, BLOCK)
        self.assertEqual(self.backup.read_text(encoding="utf-8"), "an earlier state\n")

    def test_no_temp_file_survives_the_failure(self) -> None:
        self._fail_the_final_write()
        with self.assertRaises(ValueError):
            hd.apply(self.link, BLOCK)
        leftovers = [p.name for p in self.target.parent.iterdir()
                     if p.name.startswith(".shadow-")]
        self.assertEqual(leftovers, [])
