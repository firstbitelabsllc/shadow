#!/usr/bin/env python3
"""Own one marker-delimited block inside a host's instruction file.

`shadow goal` prints the standing goal; this writes it. Until now doctor could
say "refresh with: shadow goal" while the verb only printed, so following that
advice appended a second copy — the instruction was not followable.

The contract, in order of how much it matters:

1. **Never lose the person's text.** A host instruction file is hand-written
   and often long. Every write goes to a temp file in the same directory and
   is renamed over the target, so a crash leaves either the old file or the new
   one, never a truncated one. The first write also leaves a `.bak-shadow`
   copy. A host file that is a symlink is written THROUGH — the canonical file
   it points at is what changes, and the link is still a link afterwards.
2. **Own only between the markers.** Text before and after is untouched, byte
   for byte.
3. **Idempotent.** Writing twice changes nothing the second time.
4. **Adopt an unmarked copy.** Anyone who pasted the block by hand before
   markers existed has an unmarked copy; that exact region is wrapped rather
   than duplicated. An older revision, whose last line no longer matches, has
   no discernible end — that is refused out loud, not guessed at.
5. **Removable.** `--remove` takes the block and its markers out and leaves the
   surrounding text as it was.

Cursor is deliberately absent: its user rules live in application settings, not
a file, so writing `~/.cursor/rules/shadow.md` would invent a convention. That
is a row in the plan, not a silent gap.
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import os
import stat
from pathlib import Path
import sys
import tempfile
from typing import Final

ROOT: Final = Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent)).resolve()
DOC: Final = ROOT / "docs" / "reference" / "host-integration.md"

BEGIN: Final = "<!-- shadow:goal:begin — managed by `shadow goal --install`; edits here are overwritten -->"
END: Final = "<!-- shadow:goal:end -->"
# The heading the block always starts with. Used to find an unmarked copy left
# by someone who pasted it before markers existed.
ANCHOR: Final = "## Shadow "

HOSTS: Final = {
    "claude": Path.home() / ".claude" / "CLAUDE.md",
    "codex": Path.home() / ".codex" / "AGENTS.md",
}


def standing_goal(doc: Path | None = None) -> str:
    """The block, read from the doc that ships it.

    One source: `bin/shadow goal` extracts the same region with awk, and a test
    asserts both readers return identical text. A second copy is a copy that
    drifts.
    """
    try:
        lines = (doc or DOC).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    out: list[str] = []
    for line in lines:
        if line.startswith(ANCHOR):
            out.append(line)
        elif out:
            if line == "```":
                break
            out.append(line)
    return "\n".join(out).strip()


def managed(block: str) -> str:
    return f"{BEGIN}\n{block}\n{END}"


def _span(text: str, block: str) -> tuple[int, int] | None:
    """Where the managed block lives, marked or not. None if absent."""
    start = text.find(BEGIN)
    if start != -1:
        end = text.find(END, start)
        if end != -1:
            return start, end + len(END)
        # A begin with no end means someone deleted the terminator. Refuse
        # rather than guess how far the block ran — a wrong guess eats their
        # text, and that is the one outcome this module exists to prevent.
        raise ValueError("found the begin marker with no end marker; fix the file by hand")
    # Unmarked legacy copy: adopt exactly the region matching the shipped block
    # or an earlier revision of it, identified by its heading and last line.
    head = block.splitlines()[0]
    start = text.find(head)
    if start == -1:
        return None
    tail_line = block.splitlines()[-1]
    end = text.find(tail_line, start)
    if end == -1:
        # The heading is present but the block's own last line is not: an older
        # revision, and nothing in the file says how far it ran. Shape is not
        # evidence — a note glued under the last paragraph, or one of their own
        # paragraphs opening `Word: `, reads exactly like block text, so any
        # rule that guesses eats it. Same answer as a begin with no end: say so
        # and let the person draw the line.
        raise ValueError(
            "found an unmarked copy of the standing goal whose last line has changed, "
            "so where it ends is a guess; delete that block by hand, or wrap it in the "
            f"markers ({BEGIN.split(' —')[0]} … {END}), then rerun"
        )
    return start, end + len(tail_line)


def _canonical(path: Path) -> Path:
    """The file a host path finally names, following any symlink through.

    `os.replace` onto a symlink replaces THE LINK with a regular file and
    leaves what it pointed at untouched. Anyone who keeps one canonical
    directive file and links each host at it would be un-migrated by their
    first install: the link becomes a copy, the canonical file never receives
    the block, and the install reports success either way. Resolving first
    sends the write to where their text actually lives.

    Where the link goes is not policed. Pointing a host file at a private
    repository — outside the home directory, versioned, shared between
    machines — is the reason to make one at all. What is checked is what sits
    at the end of it: a regular file that is already there. A directory, a
    device, or a fifo is not a directive file that lost its way. A link to
    nothing is refused rather than created, because a path with nothing at it
    says "nothing here yet" while a link with nothing at the end has two
    honest readings — the repository is not cloned on this machine yet, or the
    path is a typo — that want opposite actions. Creating the target picks one
    silently: it invents a file where shadow guessed and reports success while
    the text the person meant to change sits somewhere else.
    """
    if not path.is_symlink():
        return path
    try:
        target = Path(os.path.realpath(path, strict=True))
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(
                f"{path} is a symlink whose chain loops back on itself; point it at a file"
            ) from exc
        if exc.errno == errno.ENOENT:
            raise ValueError(
                f"{path} is a symlink to {os.path.realpath(path)}, which does not exist; "
                "restore that file or repoint the link, then rerun"
            ) from exc
        raise
    if not target.is_file():
        raise ValueError(f"{path} is a symlink to {target}, which is not a regular file")
    return target


# Test seam, called once in apply() between resolution and the final write.
# The delete-and-swap races below are real but their window is milliseconds;
# a probabilistic test would pass for years while the guard rotted. Setting
# this hook lets a test mutate the filesystem deterministically inside the
# window. Never set outside tests; costs one None-check in production.
_test_between_resolve_and_write = None


def _atomic_write(path: Path, text: str, *, mode: int | None,
                  expect: os.stat_result | None = None,
                  expect_absent: bool = False) -> None:
    """Replace `path` in one step, never leaving it partially written.

    Same directory so the rename is atomic: os.replace across filesystems is
    a copy, which reintroduces the truncated-file window this avoids.

    `mode` is the mode the finished file must have — the one the file being
    replaced already had. A fresh temp file is 0600, so without this a
    world-readable instruction file quietly turns private, which git does not
    show and the person did not ask for. It is set before the rename rather
    than after, so the bytes are never sitting in a file more readable than
    the one they replace.
    """
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".shadow-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        if mode is not None:
            os.chmod(temporary, mode)
        if expect is not None:
            # The path was resolved earlier and the world kept moving. If the
            # file vanished, renaming would silently recreate it where the
            # person may have deliberately removed it; if something else was
            # put there — above all a fresh symlink — renaming would replace
            # it, which for a link is this feature's own defect one level
            # down. Identity is the inode, not the content: a same-bytes file
            # swapped in is still not the file that was resolved.
            try:
                current = os.lstat(path)
            except FileNotFoundError:
                raise ValueError(
                    f"{path} vanished after it was resolved; nothing was written"
                ) from None
            if not stat.S_ISREG(current.st_mode):
                raise ValueError(
                    f"{path} was replaced by something that is not a regular file "
                    "after it was resolved; refusing to overwrite it"
                )
            if (current.st_dev, current.st_ino) != (expect.st_dev, expect.st_ino):
                raise ValueError(
                    f"{path} changed identity after it was resolved; rerun so the "
                    "write sees what is there now"
                )
        elif expect_absent and os.path.lexists(path):
            raise ValueError(
                f"{path} appeared while the install was writing it; rerun so the "
                "write sees what is there now"
            )
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def apply(path: Path, block: str, *, remove: bool = False) -> str:
    """Write the block into `path`. Returns what happened, for the caller."""
    target = _canonical(path)
    existed = target.exists()
    text = target.read_text(encoding="utf-8") if existed else ""
    span = _span(text, block) if text else None

    if remove:
        if span is None:
            return "absent"
        head, tail = text[: span[0]], text[span[1] :]
        new = (head.rstrip("\n") + "\n" + tail.lstrip("\n")) if head.strip() else tail.lstrip("\n")
        action = "removed"
    else:
        wanted = managed(block)
        if span is None:
            separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
            new = text + separator + wanted + "\n"
            action = "added" if existed else "created"
        else:
            current = text[span[0] : span[1]]
            if current == wanted:
                return "current"
            new = text[: span[0]] + wanted + text[span[1] :]
            action = "refreshed" if current.startswith(BEGIN) else "adopted"

    mode: int | None = None
    identity: os.stat_result | None = None
    if not existed:
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        identity = os.lstat(target)
        mode = identity.st_mode & 0o7777
        # Beside the canonical file, not beside the link. These are the
        # canonical file's bytes, and a copy left next to the link reads as a
        # backup OF the link — so the obvious recovery, `cp CLAUDE.md.bak-shadow
        # CLAUDE.md`, replaces the link with a regular file, which is the defect
        # writing through exists to prevent. Several hosts pointed at one file
        # also leave one backup of it rather than one per link, each snapshotting
        # a different moment and only the first of them pre-shadow.
        backup = target.with_suffix(target.suffix + ".bak-shadow")

    made_backup = False
    if existed and not backup.exists():
        _atomic_write(backup, text, mode=mode)
        made_backup = True

    if _test_between_resolve_and_write is not None:
        _test_between_resolve_and_write()

    try:
        _atomic_write(target, new, mode=mode, expect=identity,
                      expect_absent=not existed)
    except BaseException:
        # All-or-nothing includes the backup. One that this run created
        # alongside a write that never landed records a change that never
        # happened, and its existence makes the NEXT run skip backing up the
        # state that actually preceded it. A pre-existing backup is somebody's
        # earlier state and is never touched.
        if made_backup:
            backup.unlink(missing_ok=True)
        raise
    return action


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow goal --install",
        description="Write the standing goal into each host's instruction file.",
    )
    parser.add_argument("--remove", action="store_true", help="take the block out again")
    parser.add_argument("--host", action="append", choices=sorted(HOSTS),
                        help="limit to one host (repeatable); default is every known host")
    args = parser.parse_args(argv)

    block = standing_goal()
    if not block:
        print("shadow goal: no standing goal found in docs/reference/host-integration.md", file=sys.stderr)
        return 1

    status = 0
    for name in args.host or sorted(HOSTS):
        path = HOSTS[name]
        if not path.parent.is_dir():
            # The host is not installed on this machine. Not an error.
            print(f"skipped:   {name} (no host directory)")
            continue
        try:
            action = apply(path, block, remove=args.remove)
        except (OSError, ValueError) as exc:
            print(f"failed:    {name}: {exc}", file=sys.stderr)
            status = 1
            continue
        print(f"{action + ':':10} {name}")
    print("\nCursor is not written: its user rules live in application settings, not a file.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
