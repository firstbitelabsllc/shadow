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
   copy.
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
import importlib.util
import os
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


def apply(path: Path, block: str, *, remove: bool = False) -> str:
    """Write the block into `path`. Returns what happened, for the caller."""
    existed = path.exists()
    text = path.read_text(encoding="utf-8") if existed else ""
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

    if not existed:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.with_suffix(path.suffix + ".bak-shadow").exists():
        path.with_suffix(path.suffix + ".bak-shadow").write_text(text, encoding="utf-8")

    # Same directory so the rename is atomic: os.replace across filesystems is
    # a copy, which reintroduces the truncated-file window this avoids.
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".shadow-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(new)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
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
