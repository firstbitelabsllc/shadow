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
        # link either. The canonical file is byte-for-byte untouched, the
        # link survives, no temp file remains — and the backup, which commits
        # via link(2) before the rename is attempted, is RETAINED as the
        # explicit recovery, with the error saying where it is.
        with tempfile.TemporaryDirectory() as tmp:
            link, canonical = self._linked(Path(tmp))
            original = hd.os.replace
            hd.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
            try:
                with self.assertRaisesRegex(OSError, "preserved at"):
                    hd.apply(link, BLOCK)
            finally:
                hd.os.replace = original
            self.assertTrue(link.is_symlink())
            self.assertEqual(canonical.read_text(encoding="utf-8"), BEFORE)
            backup = canonical.with_suffix(canonical.suffix + ".bak-shadow")
            self.assertEqual(backup.read_text(encoding="utf-8"), BEFORE,
                             "the retained backup must hold the pre-write bytes")
            self.assertEqual(sorted(p.name for p in canonical.parent.iterdir()),
                             sorted([canonical.name, backup.name]),
                             "no temp file may survive the failure")
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


def _swap_with_distinct_inode(path: Path, content: str) -> None:
    """Replace `path` with a NEW inode holding `content`, deterministically.

    unlink-then-create can hand the freed inode straight back (APFS does),
    which turns an identity-guard test into a coin flip — the audit caught CI
    red on exactly that. Creating the sibling FIRST, while the original still
    holds its inode, forces a distinct one; os.replace then swaps atomically
    and the sibling keeps its inode.
    """
    sibling = path.with_name(path.name + ".swap")
    sibling.write_text(content, encoding="utf-8")
    os.replace(sibling, path)


class TheWindowBetweenResolveAndWriteIsGuarded(unittest.TestCase):
    """The world keeps moving after the resolve, and every later act checks.

    The snapshot is the first act on the resolved target; the read opens the
    snapshotted inode or refuses; the final write revalidates both the HOST
    LINK (what the host reads) and the target identity immediately before the
    rename. The races are real but their window is milliseconds, so these
    tests drive the module's explicit seams instead of racing threads — a
    probabilistic test would pass for years while the guard rotted.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.target = root / "repo" / "DIRECTIVES.md"
        self.target.parent.mkdir()
        self.target.write_text("owner text\n", encoding="utf-8")
        self.link = root / "CLAUDE.md"
        self.link.symlink_to(self.target)
        self.plain = root / "AGENTS.md"
        self.plain.write_text("plain host file\n", encoding="utf-8")

    def tearDown(self) -> None:
        hd._test_between_resolve_and_write = None
        hd._test_between_snapshot_and_read = None
        self._tmp.cleanup()

    # --- the link itself is revalidated ---

    def test_a_repointed_link_is_refused_and_neither_file_is_touched(self) -> None:
        other = self.target.parent / "OTHER.md"
        other.write_text("the file the host now reads\n", encoding="utf-8")

        def repoint() -> None:
            self.link.unlink()
            self.link.symlink_to(other)

        hd._test_between_resolve_and_write = repoint
        with self.assertRaisesRegex(ValueError, "repointed"):
            hd.apply(self.link, BLOCK)
        # The write went to the file the link named when it was pinned — that
        # is the pin-time contract — and the refusal exists because success
        # would describe a file the host no longer reads. The file it reads
        # NOW is untouched.
        self.assertEqual(other.read_text(encoding="utf-8"), "the file the host now reads\n")
        self.assertIn(hd.BEGIN, self.target.read_text(encoding="utf-8"),
                      "the pin-time target should carry the block the error describes")

    def test_a_target_deleted_inside_the_window_is_not_recreated(self) -> None:
        hd._test_between_resolve_and_write = lambda: self.target.unlink()
        with self.assertRaisesRegex(ValueError, "vanished after it was resolved"):
            hd.apply(self.link, BLOCK)
        self.assertFalse(self.target.exists(),
                         "the write recreated a file that was deliberately removed")

    def test_a_symlink_planted_at_the_target_is_not_destroyed(self) -> None:
        elsewhere = self.target.parent / "elsewhere.md"
        elsewhere.write_text("someone else's file\n", encoding="utf-8")

        def swap() -> None:
            self.target.unlink()
            self.target.symlink_to(elsewhere)

        hd._test_between_resolve_and_write = swap
        with self.assertRaisesRegex(ValueError, "repointed|not a regular file"):
            hd.apply(self.link, BLOCK)
        self.assertTrue(self.target.is_symlink(), "the planted link was destroyed")
        self.assertEqual(elsewhere.read_text(encoding="utf-8"), "someone else's file\n")

    # --- a plain host file gets the same guards, minus the link check ---

    def test_a_plain_file_swapped_in_the_window_is_refused_by_inode(self) -> None:
        original = self.plain.read_text(encoding="utf-8")
        hd._test_between_resolve_and_write = (
            lambda: _swap_with_distinct_inode(self.plain, original))
        with self.assertRaisesRegex(ValueError, "changed identity"):
            hd.apply(self.plain, BLOCK)
        self.assertEqual(self.plain.read_text(encoding="utf-8"), original)

    def test_a_plain_file_deleted_in_the_window_is_not_recreated(self) -> None:
        hd._test_between_resolve_and_write = lambda: self.plain.unlink()
        with self.assertRaisesRegex(ValueError, "vanished after it was resolved"):
            hd.apply(self.plain, BLOCK)
        self.assertFalse(self.plain.exists())

    # --- the read is pinned to the snapshotted inode ---

    def test_a_swap_after_the_pin_cannot_clobber_the_new_file(self) -> None:
        # The read comes off the pinned descriptor, so the swap does not even
        # perturb what is read — and the commit guards then refuse because the
        # pinned file has lost its name. The bystander survives untouched.
        hd._test_between_snapshot_and_read = (
            lambda: _swap_with_distinct_inode(self.plain, "somebody's fresh file\n"))
        with self.assertRaisesRegex(ValueError, "changed identity"):
            hd.apply(self.plain, BLOCK)
        self.assertEqual(self.plain.read_text(encoding="utf-8"), "somebody's fresh file\n",
                         "the new file was overwritten with text derived from the old one")

    def test_a_delete_after_the_pin_refuses_instead_of_creating(self) -> None:
        hd._test_between_snapshot_and_read = lambda: self.plain.unlink()
        with self.assertRaisesRegex(ValueError, "vanished after it was resolved"):
            hd.apply(self.plain, BLOCK)
        self.assertFalse(self.plain.exists())

    def test_a_swap_onto_a_recycled_inode_number_is_still_refused(self) -> None:
        # The worker's finding, ported to the pin architecture. Inode numbers
        # are recycled — ext4 hands back the one it just freed — so a swap
        # can produce a new file wearing the resolved file's (dev, ino) and
        # the pair-compare walks straight through. The recycling is forced
        # here rather than hoped for: fstat is patched so any stat of the
        # replacement reports the original's numbers. The pinned descriptor's
        # link count is the truth the spoof cannot touch: the kernel zeroed
        # it when the swap took the file's last name.
        original = self.plain.read_text(encoding="utf-8")
        before = os.stat(self.plain)
        real_lstat = os.lstat

        def swap() -> None:
            _swap_with_distinct_inode(self.plain, original)  # same bytes, new inode

            def spoofed(path, *a, **k):
                result = real_lstat(path, *a, **k)
                if Path(path) == self.plain:
                    class _Recycled:
                        st_dev = before.st_dev
                        st_ino = before.st_ino
                        st_mode = result.st_mode
                        st_nlink = result.st_nlink
                    return _Recycled()
                return result

            os.lstat = spoofed

        self.addCleanup(setattr, os, "lstat", real_lstat)
        hd._test_between_resolve_and_write = swap
        with self.assertRaisesRegex(ValueError, "changed identity"):
            hd.apply(self.plain, BLOCK)
        self.assertEqual(self.plain.read_text(encoding="utf-8"), original,
                         "the write landed in a file that was not the one resolved")

    def test_a_file_appearing_during_a_fresh_create_is_not_clobbered(self) -> None:
        fresh = Path(self._tmp.name) / "codex" / "NEW.md"

        def plant() -> None:
            fresh.parent.mkdir(parents=True, exist_ok=True)
            fresh.write_text("someone got here first\n", encoding="utf-8")

        hd._test_between_resolve_and_write = plant
        with self.assertRaisesRegex(ValueError, "appeared while the install was writing"):
            hd.apply(fresh, BLOCK)
        self.assertEqual(fresh.read_text(encoding="utf-8"), "someone got here first\n")

    def test_a_link_into_shadows_own_checkout_is_refused(self) -> None:
        # Reviewed adversarially: pointed at docs/reference/host-integration.md,
        # the unmarked-adoption branch wraps the standing goal's SOURCE in
        # markers inside its own fence, the reader then swallows the end marker
        # as content, and every later install propagates the corruption while
        # the one-source drift test stays green — both readers share the rule
        # that broke. The write must refuse the product's own tree.
        #
        # ROOT is patched to a sandbox for this test. The first version linked
        # at the REAL doc — and when a mutation run disabled the guard under
        # test, the test itself performed the corruption on the live file. A
        # test whose failure mode is the defect it guards must never point at
        # product state.
        sandbox_root = Path(self._tmp.name) / "fake-checkout"
        doc = sandbox_root / "docs" / "reference" / "host-integration.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("## Shadow — standing goal\ntext\n", encoding="utf-8")
        inward = Path(self._tmp.name) / "inward.md"
        inward.symlink_to(doc)
        real_root = hd.ROOT
        hd.ROOT = sandbox_root
        try:
            with self.assertRaisesRegex(ValueError, "shadow's own checkout"):
                hd.apply(inward, BLOCK)
        finally:
            hd.ROOT = real_root
        self.assertEqual(doc.read_text(encoding="utf-8"),
                         "## Shadow — standing goal\ntext\n",
                         "the sandboxed source of truth was modified")

    def test_the_final_window_cannot_clobber_a_swapped_in_file(self) -> None:
        # THE closure test for lstat-to-commit. The swap happens after the
        # verify, at the last possible instant. With rename semantics the
        # swapped-in file would be silently destroyed; with the pinned
        # descriptor our bytes land on the detached previous inode, the
        # bystander is untouched, and the lost race is a loud refusal instead
        # of a false success.
        # The seam fires once for the backup's commit and once for the final
        # write; the window under test is the SECOND. Firing on the first
        # would swap during the backup and be caught by the earlier identity
        # verify — a different guard than the one this test exists to pin.
        calls = {"n": 0}

        def swap() -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                hd._test_between_verify_and_commit = None
                _swap_with_distinct_inode(self.plain, "the other writer's file\n")

        hd._test_between_verify_and_commit = swap
        try:
            with self.assertRaisesRegex(ValueError, "changed identity"):
                hd.apply(self.plain, BLOCK)
        finally:
            hd._test_between_verify_and_commit = None
        self.assertEqual(self.plain.read_text(encoding="utf-8"),
                         "the other writer's file\n",
                         "the other writer's file was clobbered")

    def test_a_symlink_swapped_in_before_the_open_is_not_followed(self) -> None:
        elsewhere = Path(self._tmp.name) / "elsewhere.md"
        elsewhere.write_text("do not write here\n", encoding="utf-8")

        def plant() -> None:
            self.plain.unlink()
            self.plain.symlink_to(elsewhere)

        hd._test_between_resolve_and_write = plant
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            hd.apply(self.plain, BLOCK)
        self.assertEqual(elsewhere.read_text(encoding="utf-8"), "do not write here\n")

    def test_a_link_whose_target_dies_before_the_pin_is_refused(self) -> None:
        hd._test_between_resolve_and_snapshot = lambda: self.target.unlink()
        try:
            with self.assertRaisesRegex(ValueError, "vanished as it was being resolved"):
                hd.apply(self.link, BLOCK)
        finally:
            hd._test_between_resolve_and_snapshot = None
        self.assertFalse(self.target.exists(),
                         "the write recreated a deliberately removed target")

    def test_a_plain_file_swapped_before_the_pin_is_adopted_whole(self) -> None:
        # Pin-time semantics, stated as a test: whatever exists when the
        # snapshot is taken IS the file being edited. A swap before the pin
        # means the new file is read, edited, and written coherently — no
        # stale text, no refusal, nothing of the old file surviving.
        hd._test_between_resolve_and_snapshot = (
            lambda: _swap_with_distinct_inode(self.plain, "the new owner's text\n"))
        try:
            self.assertEqual(hd.apply(self.plain, BLOCK), "added")
        finally:
            hd._test_between_resolve_and_snapshot = None
        result = self.plain.read_text(encoding="utf-8")
        self.assertIn("the new owner's text", result)
        self.assertIn(hd.BEGIN, result)
        self.assertNotIn("plain host file", result)

    def test_a_target_with_a_second_hard_link_is_refused(self) -> None:
        # A second hard link is a second NAME for the same file, and every
        # write strategy breaks the contract somewhere: rename splits the
        # names — the other one keeps the old bytes forever, the split-brain
        # this feature exists to prevent — and writing the inode mutates a
        # file the person knows by a name this install never saw. The audit
        # reproduced exactly that against the descriptor strategy. There is
        # no honest write, so there is a refusal that says why.
        twin = self.target.parent / "TWIN.md"
        os.link(self.target, twin)
        with self.assertRaisesRegex(ValueError, "hard links"):
            hd.apply(self.link, BLOCK)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "owner text\n")
        self.assertEqual(twin.read_text(encoding="utf-8"), "owner text\n")
        self.assertNotIn(hd.BEGIN, self.target.read_text(encoding="utf-8"))

    def test_the_undisturbed_path_still_writes_through(self) -> None:
        self.assertEqual(hd.apply(self.link, BLOCK), "added")
        self.assertTrue(self.link.is_symlink())
        self.assertIn(hd.BEGIN, self.target.read_text(encoding="utf-8"))


class AFailedWriteLeavesNoNewBackup(unittest.TestCase):
    """All-or-nothing includes the backup, and removal is by identity.

    A backup created by this run is removed when the final write fails — it
    records a change that never happened, and its existence makes the NEXT
    run skip backing up the state that actually preceded it. Removal checks
    the inode: whatever else now answers to the pathname is a bystander, and
    deleting it would turn a refused write into a destroyed file.
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
        hd._test_between_snapshot_and_read = None
        self._tmp.cleanup()

    def test_a_backup_made_this_run_is_RETAINED_when_the_write_fails(self) -> None:
        # Deliberately inverted from an earlier revision. Deleting the backup
        # on failure was audited into the ground: removal is a pathname
        # operation, so it can race a concurrent writer and destroy a file
        # this run did not create — and after a failed write the backup may
        # be the only surviving copy. A kept backup is never wrong, only
        # redundant, and the error must say where it is.
        hd._test_between_resolve_and_write = lambda: self.target.unlink()
        with self.assertRaisesRegex(ValueError, "preserved at") as caught:
            hd.apply(self.link, BLOCK)
        self.assertTrue(self.backup.exists(), "the recovery copy was destroyed")
        self.assertIn(str(self.backup), str(caught.exception))
        self.assertEqual(self.backup.read_text(encoding="utf-8"), "owner text\n")

    def test_a_pre_existing_backup_is_never_touched(self) -> None:
        self.backup.write_text("an earlier state\n", encoding="utf-8")
        hd._test_between_resolve_and_write = lambda: self.target.unlink()
        with self.assertRaises(ValueError):
            hd.apply(self.link, BLOCK)
        self.assertEqual(self.backup.read_text(encoding="utf-8"), "an earlier state\n")

    def test_a_backup_swapped_during_the_window_is_not_deleted(self) -> None:
        def sabotage() -> None:
            self.target.unlink()  # forces the final write to refuse
            _swap_with_distinct_inode(self.backup, "somebody's replacement\n")

        hd._test_between_resolve_and_write = sabotage
        with self.assertRaises(ValueError):
            hd.apply(self.link, BLOCK)
        self.assertEqual(self.backup.read_text(encoding="utf-8"),
                         "somebody's replacement\n",
                         "the unwind deleted a file this run did not create")

    def test_a_dangling_link_at_the_backup_path_is_left_standing(self) -> None:
        nowhere = self.target.parent / "not-cloned-yet.md"
        self.backup.symlink_to(nowhere)
        self.assertEqual(hd.apply(self.link, BLOCK), "added")
        self.assertTrue(self.backup.is_symlink(),
                        "the backup write destroyed a link someone placed there")
        self.assertIn(hd.BEGIN, self.target.read_text(encoding="utf-8"))

    def test_a_backup_appearing_at_the_last_instant_is_kept_not_buried(self) -> None:
        # The backup commits with link(2), so the name is claimed atomically
        # in the kernel: whatever bears it first wins, and a concurrent
        # backup landing inside the window is KEPT — the install treats it
        # exactly like a pre-existing backup and carries on.
        planted = "somebody's simultaneous backup\n"

        def plant() -> None:
            hd._test_between_verify_and_commit = None  # one-shot: backup fires first
            self.backup.write_text(planted, encoding="utf-8")

        hd._test_between_verify_and_commit = plant
        try:
            self.assertEqual(hd.apply(self.link, BLOCK), "added")
        finally:
            hd._test_between_verify_and_commit = None
        self.assertEqual(self.backup.read_text(encoding="utf-8"), planted,
                         "the concurrent backup was buried")
        self.assertIn(hd.BEGIN, self.target.read_text(encoding="utf-8"))

    def test_no_temp_file_survives_the_failure(self) -> None:
        hd._test_between_resolve_and_write = lambda: self.target.unlink()
        with self.assertRaises(ValueError):
            hd.apply(self.link, BLOCK)
        leftovers = [q.name for q in self.target.parent.iterdir()
                     if q.name.startswith(".shadow-")]
        self.assertEqual(leftovers, [])
