#!/usr/bin/env python3
"""Own one marker-delimited block inside a host's instruction file.

`shadow goal` prints the standing goal; this writes it. Until now doctor could
say "refresh with: shadow goal" while the verb only printed, so following that
advice appended a second copy — the instruction was not followable.

The contract, in order of how much it matters:

1. **Never lose the person's text.** A host instruction file is hand-written
   and often long. Every write goes to a temp file in the same directory and
   is renamed over the target, so a crash leaves either the old file or the new
   one, never a truncated one. The first write to a file that already existed
   also leaves a `.bak-shadow` copy of its pre-shadow bytes; a file created
   from nothing has nothing to back up and gets none. If the backup name is
   already taken, whatever bears it is KEPT and no new backup is made —
   usually that is a prior run's backup, the one copy that is genuinely
   pre-shadow; either way never-clobber wins over backup-freshness, and the
   write proceeds without a fresh copy. A host file that is a symlink is written THROUGH — the canonical file
   it points at is what changes, and the link is still a link afterwards.

### Concurrency and durability model — what this promises, and what it does not

This file writes correctly against a person editing by hand and against its own
reruns. It does NOT implement a lock, and it makes no claim of safety against an
arbitrary other process racing the same file. The precise boundary, because an
over-promise here would be a lie about someone's hand-written instructions:

- **Guaranteed.** *Atomic visibility*: a reader at any instant sees the complete
  old directive or the complete new one, never a partial or empty one — the new
  bytes are fully written and `fsync`-ed to a temp file before an atomic rename
  ever gives them the target's name. *Durability*: the temp file — its bytes and
  its mode, `fchmod`-ed before the sync — is `fsync`-ed, and on a filesystem that
  supports a directory `fsync` (APFS and ext4, the deployed cases) the target's
  own directory is too, so a completed write survives a process or OS crash; a
  filesystem that rejects a directory `fsync` degrades to atomic visibility, not
  crash-durability of the name change — never to a partial write. This covers a
  write into a directory that already exists, which every installed host's does
  (`~/.claude`, `~/.codex`); a fresh create that must also make new parent
  directories syncs the file and its immediate directory but not the chain of
  newly created ancestors, whose persistence across power loss is best-effort.
  *Create/backup exclusivity*: a fresh target or a
  `.bak-shadow` is made with `link(2)`, which the kernel refuses atomically if
  the name is already taken — nothing is ever clobbered into existence, and on
  any failure the pre-write state is preserved (the backup is kept and named in
  the error). Exclusivity holds AT the create instant; the instant after it, a
  swap of the freshly created file is the same last-writer-wins floor as the
  rename path (the post-create re-check catches a non-regular replacement, and
  a regular-file swap there is undetectable by construction). *Symlink
  survival*: a symlinked host file stays a symlink; its
  canonical target receives the bytes.
- **Best-effort.** *Identity re-verification*: from the moment the resolved file
  is pinned (an `O_RDONLY|O_NOFOLLOW` descriptor, whose link count reads zero the
  instant the file loses its last name — inode numbers recycle, a live descriptor
  does not) up to the rename instant, every guard re-checks that the pathname
  still names the pinned file, that no hard link appeared, and — for a link — that
  it still resolves to the same target. This catches human-scale races (a swap, a
  delete, a repoint between resolve and write) and refuses loudly.
- **Out of scope, by decision, not oversight.** The single instant *at* the
  rename cannot be made both atomic-replacing and never-clobber-a-concurrent-
  writer: POSIX rename offers no compare-and-swap, and Darwin exposes none
  either (`renameatx_np` gives EXCL only for an absent destination and SWAP
  without an expected identity; `RENAME_SECLUDE` is undocumented as a
  concurrency primitive). So if a *different* process renames its own file over
  the target in that instant, last writer wins and this cannot detect it — which
  is why crash-safety, not race-detection, is the property kept at the floor.
  Likewise a concurrent writer that edits the *same inode in place* (rather than
  renaming a replacement over it) is invisible to every identity check by
  construction. Cooperating processes that need mutual exclusion must take a
  shared advisory lock around resolve-read-write themselves; a process that
  ignores such a lock is, and is documented to be, outside this contract.
2. **Own only between the markers.** Text before and after is untouched, byte
   for byte.
3. **Idempotent.** Writing twice changes nothing the second time.
4. **Adopt only a known unmarked revision.** Anyone who pasted a shipped block
   by hand before markers existed has an unmarked copy; that exact region is
   wrapped rather than duplicated. The current block and explicitly recorded
   older revisions are the only admissible shapes. An unrecognized `## Shadow`
   heading is refused by name — never guessed at, overwritten, or followed by
   a duplicate block.
5. **Removable.** `--remove` takes the block and its markers out together
   with, at most, the blank-line separator adding it introduced — one newline
   after the block and one before it when the block was preceded by a blank
   line. Everything else is untouched, but a separator is indistinguishable
   from a blank line the person typed, so one such line can come out with the
   block; a file that never ended in a newline gains one on the round trip.

Cursor is deliberately absent from file writes: its user-level rules live in
application settings, not a documented file. Machine configuration may declare
the `user_rules` projection; Shadow then prints a hash receipt for the manual
application action and never claims it inspected or changed Cursor settings.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import os
import stat
from pathlib import Path
import re
import sys
import tempfile
from typing import Final

ROOT: Final = Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent)).resolve()
DOC: Final = ROOT / "docs" / "reference" / "host-integration.md"
NATIVE_HOSTS_DOC: Final = ROOT / "docs" / "reference" / "native-hosts.md"

ACTIVATION_TABLE_HEADER: Final = ("Host selector", "Activation file")

BEGIN: Final = "<!-- shadow:goal:begin — managed by `shadow goal --install`; edits here are overwritten -->"
END: Final = "<!-- shadow:goal:end -->"
# The prefix that identifies an unmarked candidate. A candidate is writable
# only when its complete text matches the current block or an explicitly known
# shipped predecessor below.
ANCHOR: Final = "## Shadow "

# This is the exact fifteen-line standing goal shipped in 4.0.3, before the
# dispatch law was added. Keep historical blocks here rather than deriving a
# boundary from a heading or tail line: a hand-edited host instruction file is
# the person's text, and shape alone is not authority to replace it.
KNOWN_EARLIER_STANDING_GOALS: Final = (
    "\n".join((
        "## " + "Shadow — standing goal (static; the pointer moves, this text does not)",
        "",
        "Outcome: the durable board moves; no plan goes stale silently.",
        "Authority: each repository's own PLAN.md at origin/main — never a chat log,",
        "never a dashboard. Enumerate with `shadow status` (empty directories fall",
        "back to the portfolio root, so this works from anywhere).",
        "Resume: take the highest-value reachable row; `shadow amp --repo <that repo>`",
        "emits the paste-ready goal block; execute it.",
        "Stance: proxy. Never ask \"which project?\" — open the board and name the row.",
        "Never wait to be asked to amplify, mint successor goals, challenge findings",
        "adversarially, codify lessons, or archive shipped milestones: those are your",
        "moves. Blocked → park with one exact wake predicate. Done → mint the",
        "successor in the owning PLAN.md before stopping.",
        "Proof: no completed without its proof line; `shadow accept` is the only flip",
        "path for cmd proofs; re-observe read/gate proofs yourself.",
    )),
)
TEMP_PREFIX: Final = ".shadow-host-directives-"
TEMP_SUFFIX: Final = ".tmp"
TEMP_RE: Final = re.compile(
    rf"^{re.escape(TEMP_PREFIX)}(?P<pid>[1-9][0-9]*)-[A-Za-z0-9_]+{re.escape(TEMP_SUFFIX)}$"
)

def _markdown_cells(line: str) -> list[str] | None:
    """Return the cells in one ordinary Markdown table row, if it is one."""
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|")):
        return None
    return [cell.strip() for cell in line[1:-1].split("|")]


def supported_activation_targets(
    doc: Path | None = None, *, home: Path | None = None
) -> dict[str, Path]:
    """Read supported cold-activation targets from the public host contract.

    The documentation is deliberately the only list. A second source here
    once left installation and doctor disagreeing about which cold hosts were
    supported. The narrow table grammar refuses a malformed edit before it can
    cause a write to an invented path.
    """
    source = doc or NATIVE_HOSTS_DOC
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read supported cold-activation list in {source}: {exc}") from exc

    header_at = next(
        (
            index
            for index, line in enumerate(lines)
            if _markdown_cells(line) == list(ACTIVATION_TABLE_HEADER)
        ),
        None,
    )
    if header_at is None:
        raise ValueError(
            f"{source} has no supported cold-activation table with "
            f"{ACTIVATION_TABLE_HEADER[0]!r} and {ACTIVATION_TABLE_HEADER[1]!r} columns"
        )
    if header_at + 1 >= len(lines) or _markdown_cells(lines[header_at + 1]) is None:
        raise ValueError(f"{source}:{header_at + 2} has no activation-table separator")

    base = home or Path.home()
    targets: dict[str, Path] = {}
    for line_number, line in enumerate(lines[header_at + 2 :], header_at + 3):
        cells = _markdown_cells(line)
        if cells is None:
            break
        if len(cells) != 2:
            raise ValueError(f"{source}:{line_number} has {len(cells)} activation-table columns, expected 2")
        selector, raw_path = (cell.strip("`").strip() for cell in cells)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", selector):
            raise ValueError(f"{source}:{line_number} has invalid host selector {selector!r}")
        if selector in targets:
            raise ValueError(f"{source}:{line_number} repeats host selector {selector!r}")
        if not raw_path.startswith("~/"):
            raise ValueError(f"{source}:{line_number} must name a home-relative activation file, not {raw_path!r}")
        relative = Path(raw_path[2:])
        if not relative.parts or ".." in relative.parts:
            raise ValueError(f"{source}:{line_number} has unsafe activation file {raw_path!r}")
        targets[selector] = base / relative
    if not targets:
        raise ValueError(f"{source} lists no supported cold-activation targets")
    return targets


# Compatibility for focused callers and the CLI argument choices. The value is
# derived from docs/reference/native-hosts.md, never hand-maintained here.
HOSTS: Final = supported_activation_targets()


def _machine_config() -> dict:
    """Read bootstrap configuration from the installed Shadow checkout only."""
    try:
        spec = importlib.util.spec_from_file_location(
            "shadow_config_for_host_directives", ROOT / "scripts" / "shadow_config.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("could not load scripts/shadow_config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.load_machine_config(ROOT)
    except (ImportError, OSError, TypeError, ValueError) as exc:
        raise ValueError(f"machine configuration is invalid: {exc}") from exc


def configured_directive_topology(*, home: Path | None = None) -> dict:
    """Return the installed checkout's directive topology.

    An absent source retains the shipped file-target convention.  Once a
    source is declared, its two targets are declarations to verify, never
    paths Shadow is authorized to create or replace with links.
    """
    config = _machine_config()
    declared = config.get("directives", {})
    if not isinstance(declared, dict):
        raise ValueError("machine directives configuration is not a mapping")
    source = declared.get("source")
    targets = declared.get("targets", {})
    projections = declared.get("projections", {})
    if source is None:
        return {
            "source": None,
            "targets": supported_activation_targets(home=home),
            "projections": {},
        }

    def expand(value: str) -> Path:
        if value.startswith("~/"):
            return (home or Path.home()).resolve() / value[2:]
        return Path(value)

    return {
        "source": expand(source),
        "targets": {name: expand(value) for name, value in targets.items()},
        "projections": dict(projections),
    }


def projection_sha256(block: str) -> str:
    """The reproducible receipt for a manual application-settings projection."""
    return hashlib.sha256(block.encode("utf-8")).hexdigest()


def verify_declared_topology(source: Path, targets: dict[str, Path]) -> None:
    """Require pre-existing Claude/Codex links to the declared source."""
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"directive source {source} must be an existing regular file")
    if set(targets) != {"claude", "codex"}:
        raise ValueError("configured directive topology requires exactly claude and codex targets")
    canonical = source.resolve()
    for name, target in sorted(targets.items()):
        if not os.path.lexists(target):
            raise ValueError(
                f"directive target {name} ({target}) is missing; create its link to "
                f"{source} yourself, then rerun"
            )
        if not target.is_symlink():
            raise ValueError(
                f"directive target {name} ({target}) is not a symlink; configured shared-source "
                "mode requires a pre-existing personal link and never accepts a regular-file alias"
            )
        try:
            actual = Path(os.path.realpath(target, strict=True))
        except OSError as exc:
            raise ValueError(f"directive target {name} ({target}) does not resolve: {exc}") from exc
        if actual != canonical:
            raise ValueError(
                f"directive target {name} ({target}) resolves to {actual}, expected {canonical}; "
                "Shadow does not create or replace personal links"
            )


class ApplyResult(str):
    """One successful directive operation, with the file it actually touched.

    `str` compatibility keeps the narrow `apply()` API used by focused callers:
    an added result still compares equal to ``"added"``. The CLI needs more
    than that action word, though. A host path can be a symlink into a private
    canonical source, so saying only ``added: claude`` conceals the file whose
    bytes changed and the recovery copy beside it.
    """

    target: Path
    backup: Path | None

    def __new__(cls, action: str, *, target: Path, backup: Path | None = None) -> "ApplyResult":
        result = super().__new__(cls, action)
        result.target = target
        result.backup = backup
        return result


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
    # An unmarked copy is adoptable only if its *complete* region is a known
    # shipped block. Looking for this release's heading plus its last line let
    # a person-customized middle be silently overwritten; looking for a loose
    # `## Shadow …` heading and appending let a renamed copy acquire a second
    # directive. Both paths alter ambiguous person-owned text, so fail closed.
    headings: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        heading = line.rstrip("\r\n")
        if heading.startswith(ANCHOR):
            headings.append((offset, heading))
        offset += len(line)
    if not headings:
        return None

    spans: dict[int, tuple[int, int]] = {}
    for known in (block, *KNOWN_EARLIER_STANDING_GOALS):
        start = text.find(known)
        while start != -1:
            spans[start] = (start, start + len(known))
            start = text.find(known, start + 1)

    for start, heading in headings:
        if start not in spans:
            raise ValueError(
                f"found unmarked Shadow heading {heading!r}, but it is not an exact shipped "
                "standing-goal revision; delete that block by hand, or wrap the intended block in the "
                f"markers ({BEGIN.split(' —')[0]} … {END}), then rerun"
            )
    if len(headings) != 1:
        names = ", ".join(repr(heading) for _, heading in headings)
        raise ValueError(
            f"found multiple unmarked standing-goal headings ({names}); leave them unchanged "
            f"or wrap the intended block in the markers ({BEGIN.split(' —')[0]} … {END}), then rerun"
        )
    return spans[headings[0][0]]


def _canonical(path: Path) -> Path:
    """The file a host path finally names, following any symlink through.

    `os.replace` onto a symlink replaces THE LINK with a regular file and
    leaves what it pointed at untouched. Anyone who keeps one canonical
    directive file and links each host at it would be un-migrated by their
    first install: the link becomes a copy, the canonical file never receives
    the block, and the install reports success either way. Resolving first
    sends the write to where their text actually lives.

    Hard links are invisible here — `is_symlink()` is False for them, so a
    hard-linked pair splits on the first write exactly as symlinks used to;
    use symlinks. The temp file lands beside the TARGET so the rename stays
    on one filesystem, which also means a canonical file inside a read-only
    directory now refuses where it once worked via the link's directory —
    the price of the rename being genuinely atomic on the file that matters.

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
        if exc.errno == errno.ENOTDIR:
            raise ValueError(
                f"{path} is a symlink through a component that is not a directory; "
                "repoint the link, then rerun"
            ) from exc
        raise
    if not target.is_file():
        raise ValueError(f"{path} is a symlink to {target}, which is not a regular file")
    # BOTH sides resolved — realpath already canonicalised the target, and an
    # unresolved ROOT never matches it on macOS, where /var is a symlink to
    # /private/var. The browser scan carries the identical comment for the
    # identical reason; this trap has now bitten this repository twice.
    root = ROOT.resolve()
    if root == target or root in target.parents:
        # A link into shadow's own tree would write the managed block into the
        # product's source — reviewed adversarially: pointed at
        # docs/reference/host-integration.md, the unmarked-adoption branch
        # wraps the SOURCE of the standing goal in markers inside its own
        # fence, the reader then swallows the end marker as content, and every
        # later install propagates the corruption while the one-source drift
        # test stays green because both readers share the rule that broke.
        raise ValueError(
            f"{path} is a symlink into shadow's own checkout ({target}); point it "
            "at your instruction file, not at the product's source"
        )
    return target


# Test seam, called once in apply() between resolution and the final write.
# The delete-and-swap races below are real but their window is milliseconds;
# a probabilistic test would pass for years while the guard rotted. Setting
# this hook lets a test mutate the filesystem deterministically inside the
# window. Never set outside tests; costs one None-check in production.
_test_between_resolve_and_write = None
_test_between_snapshot_and_read = None
_test_between_resolve_and_snapshot = None
_test_between_verify_and_commit = None
_test_between_final_verify_and_replace = None


def _fsync_dir(directory: Path) -> None:
    """Flush a rename/link into the directory so the name change is durable.

    `fsync` on the file makes its BYTES survive a crash; the directory ENTRY —
    the fact that those bytes now wear this name — survives only if the parent
    directory is synced too. Without this the write is atomically *visible* but
    not *durable*: a crash immediately after the rename could lose the name
    change. Kept best-effort — a few filesystems reject a directory fsync — but
    the common case (APFS, ext4) makes the completed write crash-durable, which
    is the only condition under which the module docstring claims durability.
    """
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _temp_name_for_pid(pid: int) -> str:
    """A recognizably Shadow-owned atomic-write temp name for one process.

    The random suffix still comes from `mkstemp`; the PID is deliberately in
    the stable part so a later apply can distinguish a crashed writer from a
    concurrent one without ever guessing about generic `.shadow-*.tmp` files.
    """
    return f"{TEMP_PREFIX}{pid}-residue{TEMP_SUFFIX}"


def _temp_prefix() -> str:
    return f"{TEMP_PREFIX}{os.getpid()}-"


def _pid_is_dead(pid: int) -> bool:
    """True only when the kernel says this PID no longer exists.

    Permission failures and every other uncertainty are treated as live. That
    leaves harmless residue rather than deleting a concurrent writer's bytes.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False


def _sweep_stale_temps(directory: Path) -> None:
    """Remove only regular, same-user temps from a conclusively dead Shadow run.

    A generic `.shadow-*.tmp` has no owner identity and is therefore never
    touched. The exact current writer's PID is live throughout its apply, so a
    second concurrent apply retains its temp. If a PID cannot be checked, the
    safe outcome is to retain the file for a later run.
    """
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    uid = os.getuid()
    for entry in entries:
        matched = TEMP_RE.fullmatch(entry.name)
        if matched is None:
            continue
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != uid
            or metadata.st_nlink != 1
            or not _pid_is_dead(int(matched.group("pid")))
        ):
            continue
        try:
            os.unlink(entry.path)
        except OSError:
            # A concurrent rename, unlink, or permission change means the
            # proof observed above is no longer enough. Leave it alone.
            continue


def _host_reads(host: Path) -> Path:
    """The file the host pathname leads to RIGHT NOW.

    realpath resolves whatever `host` currently IS — a symlink chain, or a
    regular file under symlinked parent directories — so the answer never
    depends on what its type was when this run started. That distinction is the
    whole point: a regular host file can become a symlink (and a symlink a
    regular file) between resolution and commit, and a boolean captured up
    front would then validate the wrong thing in either direction.
    """
    return Path(os.path.realpath(host, strict=True))


def _refuse_unless_host_still_leads_to_pin(host: Path, target: Path,
                                           pinned: int | None,
                                           identity: os.stat_result | None,
                                           claim: str) -> None:
    """Guard the NO-OP successes, which are claims about what the host reads.

    "current" says the host already reads this block; "absent" says it reads
    none. Both are read off the PINNED file — the one resolved when this run
    started. If the canonical target was atomically replaced at the same
    pathname since then, the host now reads a different file that may carry
    the opposite, and the symlink itself is untouched so re-resolving it alone
    proves nothing. Three things must hold to report a no-op honestly: the
    pinned file still has a name, the target pathname still names IT, and the
    host pathname still leads there.

    With NO pin — the target never existed, so "absent" rests on that absence —
    the claim is honest only while nothing has appeared at either pathname.
    """
    if pinned is None or identity is None:
        if os.path.lexists(target) or os.path.lexists(host):
            raise ValueError(
                f"{host} was absent when this run started but something exists "
                f"there now; {claim!r} was decided before it appeared — rerun"
            )
        return
    now = os.fstat(pinned)
    if now.st_nlink == 0:
        raise ValueError(
            f"the file behind {host} was replaced while it was being read, so "
            f"{claim!r} describes a file that no longer has a name — rerun"
        )
    if now.st_nlink > 1:
        # Every pin starts at one name (a multi-link file refuses before the
        # read), so more than one now means a hard link APPEARED in the
        # window. The no-op claim was decided about a one-name file.
        raise ValueError(
            f"{host} gained a hard link while it was being read; {claim!r} was "
            "decided about a file with one name — break the extra link or "
            "rerun"
        )
    try:
        there = os.lstat(target)
    except OSError as exc:
        raise ValueError(
            f"{target} is gone ({exc.strerror or exc}), so {claim!r} describes a "
            "file the host no longer reads — rerun"
        ) from None
    if (there.st_dev, there.st_ino) != (identity.st_dev, identity.st_ino):
        raise ValueError(
            f"{target} was replaced by a different file while it was being read; "
            f"{claim!r} was decided from the old one — rerun to see what the host "
            "reads now"
        )
    try:
        lands = _host_reads(host)
        settled = _host_reads(target)   # both sides resolved; see _atomic_write
    except OSError as exc:
        raise ValueError(
            f"{host} no longer resolves ({exc.strerror or exc}); {claim!r} describes "
            "the file it used to lead to — rerun to act on what it leads to now"
        ) from None
    if lands != settled:
        raise ValueError(
            f"{host} now leads to {lands}, not {target}; {claim!r} was decided in a "
            "file the host no longer reads — rerun"
        )


def _place_exclusive(path: Path, text: str, *, mode: int | None) -> bool:
    """Create `path` with these bytes atomically, or report that it exists.

    link(2) is the one POSIX primitive that is both crash-safe and race-free
    for creation: the temp file is complete and fsynced before it gains the
    real name, and giving it that name FAILS — atomically, in the kernel —
    if anything now bears it. No lexists-then-rename window, nothing
    overwritten, ever. Returns False when the name was already taken, which
    for a backup means "someone's backup exists; keep it".
    """
    handle, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=_temp_prefix(), suffix=TEMP_SUFFIX
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            # chmod BEFORE the fsync, and via the descriptor, so the mode is
            # part of what fsync makes durable — a chmod after the sync could be
            # lost in a crash, leaving the file readable at the mkstemp default.
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        if _test_between_verify_and_commit is not None:
            _test_between_verify_and_commit()
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        _fsync_dir(path.parent)
        return True
    finally:
        Path(temporary).unlink(missing_ok=True)


def _atomic_write(path: Path, text: str, *, mode: int | None,
                  expect: os.stat_result | None = None,
                  expect_absent: bool = False,
                  via: Path | None = None,
                  pinned: int | None = None) -> None:
    """Commit `text` to `path` without ever leaving it half-written.

    EXISTING file: temp-and-rename. The rename is atomic and crash-safe — a
    crash at any instant leaves the complete old file or the complete new
    one, never a truncation. Immediately before it, identity is re-verified
    two ways: the pathname still carries the pinned (dev, ino), and the
    pinned descriptor still has a name (`st_nlink > 0` — inode numbers are
    recycled, the pin's link count cannot be spoofed). The single instant AT
    the rename is the POSIX floor and is NOT detectable: a different process
    that renames its own file over the target in that instant wins, and after
    our own rename the pathname carries OUR inode — indistinguishable from
    having won cleanly — so the post-rename readback confirms only that our
    rename produced the file we placed, never that no racer's write was
    buried. Atomic replacement and never-replace-a-concurrent-writer cannot
    both be had from rename (there is no compare-and-swap); crash-safety is the
    property kept at the floor, because a truncated directive with its backup
    in doubt is strictly worse than a transient racer's write lost to a rename
    nothing could have made conditional. The module docstring states the whole
    concurrency contract.

    FRESH path: link(2), which refuses atomically if anything appeared.
    """
    _sweep_stale_temps(path.parent)
    if expect is not None:
        handle, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=_temp_prefix(), suffix=TEMP_SUFFIX
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
                stream.write(text)
                # chmod before the fsync (see _place_exclusive) so the mode is
                # durable, not just the bytes.
                if mode is not None:
                    os.fchmod(stream.fileno(), mode)
                stream.flush()
                os.fsync(stream.fileno())
            placed = os.stat(temporary)
            if _test_between_verify_and_commit is not None:
                _test_between_verify_and_commit()
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
            if (current.st_dev, current.st_ino) != (expect.st_dev, expect.st_ino) or (
                    pinned is not None and os.fstat(pinned).st_nlink == 0):
                raise ValueError(
                    f"{path} changed identity after it was resolved; rerun so the "
                    "write sees what is there now"
                )
            if pinned is not None and os.fstat(pinned).st_nlink > 1:
                # A hard link ADDED inside the window. Renaming would split
                # the names — the new alias keeps the old bytes forever — so
                # this refuses for exactly the reason the pin-time check does.
                raise ValueError(
                    f"{path} gained a hard link while the write was in flight; "
                    "a directive file must have one name — rerun after removing it"
                )
            if via is not None:
                # Re-resolve the HOST PATHNAME before clobbering, by whatever it
                # is NOW — not by the type it had when this run started. A
                # repoint, and equally a regular host file that has since become
                # a symlink pointing elsewhere, is caught here, before the old
                # target is touched at all: the temp is discarded and nothing
                # the host stopped reading is modified. The post-rename check
                # below still stands for the one instant this cannot cover.
                try:
                    ahead = _host_reads(via)
                    # BOTH sides resolved: _canonical hands back a plain file's
                    # path untouched, so a raw compare would read every
                    # symlinked parent directory (/var -> /private/var) as a
                    # repoint and refuse every ordinary write.
                    here = _host_reads(path)
                except OSError as exc:
                    raise ValueError(
                        f"{via} no longer resolves ({exc.strerror or exc}) before "
                        f"the write; nothing was written to {path} — repoint or "
                        "restore the link, then rerun"
                    ) from None
                if ahead != here:
                    raise ValueError(
                        f"{via} now leads to {ahead}, not {path}; nothing was "
                        "written — rerun to write the file the host reads now"
                    )
            if _test_between_final_verify_and_replace is not None:
                _test_between_final_verify_and_replace()
            os.replace(temporary, path)
            _fsync_dir(path.parent)
            final = os.lstat(path)
            if (final.st_dev, final.st_ino) != (placed.st_dev, placed.st_ino):
                raise ValueError(
                    f"{path} was replaced again as this write landed; another "
                    "writer won — rerun to see what is there now"
                )
            # No post-rename "was a concurrent write buried" check exists,
            # and none can: after a SUCCESSFUL os.replace the pinned inode
            # legitimately reads st_nlink == 0 because this write replaced it,
            # indistinguishable from a swap. POSIX rename offers no
            # compare-and-swap, so atomic replacement and
            # never-clobber-a-concurrent-writer cannot both be had. This file
            # keeps atomic replacement and crash safety; the concurrency it
            # does and does not promise is stated in the module docstring.
            if via is not None:
                # The link is what the host reads, and only NOW is there a
                # success to report. Re-resolve it; if it was repointed at any
                # moment during the write, the block landed in the file the
                # link used to name, and saying "added" would be a lie about
                # what the host sees.
                try:
                    lands = _host_reads(via)
                    settled = _host_reads(path)
                except OSError as exc:
                    raise ValueError(
                        f"{via} no longer resolves ({exc.strerror or exc}); the "
                        f"block was written to {path}, which the host no longer "
                        "reads — repoint or restore the link, then rerun"
                    ) from None
                if lands != settled:
                    raise ValueError(
                        f"{via} was repointed to {lands} while the block was being "
                        f"written to {path}; the host no longer reads that file — "
                        "rerun to write the one it points at now"
                    )
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return

    if not _place_exclusive(path, text, mode=mode):
        raise ValueError(
            f"{path} appeared while the install was writing it; rerun so the "
            "write sees what is there now"
        )
    # Post-create check, mirroring the existing-file postcheck: "created" is a
    # claim about what the host pathname reads NOW. link(2) proved the name was
    # ours at the create instant; if the pathname was swapped or became a link
    # elsewhere right after, say so instead of reporting a success about a file
    # the host no longer reads.
    made = os.lstat(path)
    if not stat.S_ISREG(made.st_mode):
        raise ValueError(
            f"{path} was replaced by something that is not a regular file as it "
            "was being created; the created text was displaced — rerun"
        )
    if via is not None:
        try:
            lands = _host_reads(via)
            settled = _host_reads(path)
        except OSError as exc:
            raise ValueError(
                f"{via} no longer resolves ({exc.strerror or exc}); the file was "
                f"created at {path}, which the host no longer reads — rerun"
            ) from None
        if lands != settled:
            raise ValueError(
                f"{via} now leads to {lands}, not {path}; the file was created "
                "where the host no longer reads — rerun"
            )

def _private_full_file(path: Path, block: str) -> str:
    """Replace one owner file with the generated block; never a public mode.

    This reuses the public installer's canonical-target, exclusive-backup,
    pinned-identity, atomic-write, fsync, and symlink-survival boundaries. The
    first pre-takeover bytes remain beside the canonical target forever; later
    generated-block upgrades converge without rewriting that backup.
    """
    target = _canonical(path)
    _sweep_stale_temps(target.parent)
    pinned: int | None = None
    backup_pinned: int | None = None
    try:
        try:
            pinned = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            identity = os.fstat(pinned)
        except FileNotFoundError:
            identity = None
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.EMLINK):
                raise ValueError(
                    f"{target} became a symlink while it was being pinned; rerun"
                ) from None
            raise
        if identity is not None and not stat.S_ISREG(identity.st_mode):
            raise ValueError(f"{target} is not a regular file")
        if identity is not None and identity.st_nlink > 1:
            raise ValueError(
                f"{target} has {identity.st_nlink} hard links; private takeover "
                "requires one canonical name"
            )
        if identity is None and path.is_symlink():
            raise ValueError(
                f"{path} resolves to {target}, which vanished; restore or repoint it"
            )

        existed = identity is not None
        if existed:
            with os.fdopen(os.dup(pinned), "r", encoding="utf-8", newline="") as stream:
                before = stream.read()
        else:
            before = ""
        wanted = managed(block) + "\n"
        if before == wanted:
            _refuse_unless_host_still_leads_to_pin(
                path, target, pinned, identity, "current"
            )
            return "current"

        target.parent.mkdir(parents=True, exist_ok=True)
        mode = identity.st_mode & 0o7777 if identity is not None else None
        backup = target.with_suffix(target.suffix + ".bak-shadow-full")
        made_backup = (
            _place_exclusive(backup, before, mode=mode) if existed else False
        )
        if existed and not made_backup:
            whole_managed = (
                before.count(BEGIN) == 1
                and before.count(END) == 1
                and before.startswith(BEGIN + "\n")
                and before.rstrip("\n").endswith("\n" + END)
            )
            if not whole_managed:
                raise ValueError(
                    f"{backup} already exists, so this run could not preserve "
                    "the owner file byte-for-byte; inspect or move that backup "
                    "before private takeover"
                )
            try:
                backup_pinned = os.open(backup, os.O_RDONLY | os.O_NOFOLLOW)
                backup_identity = os.fstat(backup_pinned)
                if not stat.S_ISREG(backup_identity.st_mode):
                    raise ValueError(f"{backup} is not a regular retained backup")
                if backup_identity.st_nlink != 1:
                    raise ValueError(
                        f"{backup} has {backup_identity.st_nlink} names; retained "
                        "backup identity is ambiguous"
                    )
                with os.fdopen(os.dup(backup_pinned), "r", encoding="utf-8", newline="") as stream:
                    stream.read()
            except (OSError, UnicodeError) as exc:
                raise ValueError(
                    f"{backup} is not one pinned, readable regular backup; "
                    "private takeover refused"
                ) from exc
        if _test_between_resolve_and_write is not None:
            _test_between_resolve_and_write()
        if backup_pinned is not None:
            now = os.fstat(backup_pinned)
            there = os.lstat(backup)
            if (
                now.st_nlink != 1
                or (there.st_dev, there.st_ino) !=
                (backup_identity.st_dev, backup_identity.st_ino)
            ):
                raise ValueError(
                    f"{backup} changed before private takeover; owner recovery "
                    "is no longer pinned"
                )
        try:
            _atomic_write(
                target,
                wanted,
                mode=mode,
                expect=identity,
                expect_absent=not existed,
                via=path,
                pinned=pinned,
            )
        except BaseException as exc:
            if made_backup:
                raise type(exc)(
                    f"{exc}; the pre-takeover state is preserved at {backup}"
                ) from exc
            raise
        return "replaced" if existed else "created"
    finally:
        if backup_pinned is not None:
            os.close(backup_pinned)
        if pinned is not None:
            os.close(pinned)

def apply(path: Path, block: str, *, remove: bool = False) -> ApplyResult:
    """Write the block into `path`, returning the action and actual target."""
    # No is_symlink() snapshot is taken here, deliberately. A host pathname is
    # mutable: a regular file can become a symlink, and a symlink a regular
    # file, between this line and the commit. Every success path therefore
    # re-resolves the pathname by what it IS at that moment (_host_reads), and
    # a boolean captured up front would only make one of those two transitions
    # invisible.
    target = _canonical(path)
    _sweep_stale_temps(target.parent)
    if _test_between_resolve_and_snapshot is not None:
        _test_between_resolve_and_snapshot()
    # The snapshot is the FIRST act on the resolved target, and it is a
    # DESCRIPTOR, not a stat. Inode numbers are recycled — delete a file and
    # the filesystem hands the number straight back — so a (dev, ino) pair
    # alone cannot tell "still the same file" from "a different file wearing
    # its number". The pinned descriptor is the kernel's own answer: the
    # moment the resolved file loses its last name, its link count reads
    # zero on THIS descriptor, whoever inherits the number afterwards. Every
    # later act — the read, the guards, the final write — is keyed to it.
    pinned: int | None = None
    try:
        try:
            pinned = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            identity = os.fstat(pinned)
        except FileNotFoundError:
            identity = None
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.EMLINK):
                raise ValueError(
                    f"{target} became a symlink as it was being pinned; rerun so "
                    "the write sees what is there now"
                ) from None
            raise
        if identity is not None and not stat.S_ISREG(identity.st_mode):
            raise ValueError(f"{target} is not a regular file")
        if identity is not None and identity.st_nlink > 1:
            # A second hard link is a second NAME for this same file. Every write
            # strategy breaks the contract somewhere: rename splits the names
            # (the other one keeps the old bytes forever), and writing the inode
            # mutates a file the person knows by a name this install never saw.
            # There is no honest write, so there is a refusal that says why.
            raise ValueError(
                f"{target} has {identity.st_nlink} hard links; a directive file "
                "must have one name — break the extra link or point the hosts at "
                "one path through symlinks, then rerun"
            )
        if identity is None and path.is_symlink():
            # The chain resolved an instant ago and its end is already gone. For a
            # LINK that is never a fresh create: inventing the target would
            # recreate a file someone just removed, at a path shadow followed
            # rather than was given.
            raise ValueError(
                f"{path} resolves to {target}, which vanished as it was being "
                "resolved; restore that file or repoint the link, then rerun"
            )
        existed = identity is not None
        if _test_between_snapshot_and_read is not None:
            _test_between_snapshot_and_read()
        if existed:
            # Read the pinned descriptor itself — not the pathname. Whatever
            # happens to the directory entry after the pin, this reads the exact
            # file that was resolved, and the commit guards below refuse if that
            # file has since lost its name.
            with os.fdopen(os.dup(pinned), "r", encoding="utf-8",
                           newline="") as stream:
                # newline="" — a CRLF file must come back CRLF. The
                # default universal-newline read once rewrote every
                # line ending in the person's file (and its backup).
                text = stream.read()
        else:
            text = ""
        span = _span(text, block) if text else None

        if remove:
            if span is None:
                _refuse_unless_host_still_leads_to_pin(
                    path, target, pinned, identity, "absent")
                return ApplyResult("absent", target=target)
            head, tail = text[: span[0]], text[span[1] :]
            # Take out at most what adding introduced: the one newline appended
            # after the block, and one newline of the separator before it. An
            # unbounded strip here once ate the person's own blank lines
            # (A\n\n<block>\n\nB\n came back as A\nB\n) — the exact loss
            # this module exists to prevent.
            if tail.startswith("\n"):
                tail = tail[1:]
            if head.endswith("\n\n"):
                head = head[:-1]
            new = head + tail
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
                    _refuse_unless_host_still_leads_to_pin(
                        path, target, pinned, identity, "current")
                    return ApplyResult("current", target=target)
                new = text[: span[0]] + wanted + text[span[1] :]
                action = "refreshed" if current.startswith(BEGIN) else "adopted"

        mode: int | None = None
        backup: Path | None = None
        if not existed:
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
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
        if existed:
            # link(2) is the claim: creation succeeds atomically or the name was
            # taken — a concurrent backup, a pre-existing one, even a dangling
            # symlink someone parked there — and whatever bears the name is
            # KEPT, never overwritten. No lexists window exists to race.
            made_backup = _place_exclusive(backup, text, mode=mode)

        if _test_between_resolve_and_write is not None:
            _test_between_resolve_and_write()

        try:
            _atomic_write(target, new, mode=mode, expect=identity,
                          pinned=pinned,
                          expect_absent=not existed,
                          via=path)
        except BaseException as exc:
            # The backup is RETAINED on failure, deliberately. Deleting it was
            # tried and audited into the ground: removal is a pathname operation,
            # so any deletion can race a concurrent writer and destroy a file
            # this run did not create — and after a failed write, the backup may
            # be the only surviving copy of the pre-write state. A kept backup is
            # never wrong, only redundant; the error says where it is.
            if made_backup:
                raise type(exc)(
                    f"{exc}; the pre-write state is preserved at {backup}"
                ) from exc
            raise
        # `_place_exclusive` keeps an existing backup as deliberately as a new
        # one. Say where it is while the successful write is still observable;
        # a link's target is the only honest recovery surface, never the host
        # pathname the user originally supplied.
        retained_backup = backup if backup is not None and os.path.lexists(backup) else None
        return ApplyResult(action, target=target, backup=retained_backup)
    finally:
        if pinned is not None:
            os.close(pinned)


def main(argv: list[str] | None = None) -> int:
    # Re-read at invocation time. A user can update the product docs between a
    # long-lived import and `main()`, and the current documented support list
    # must be the list this invocation writes.
    try:
        topology = configured_directive_topology()
        targets = topology["targets"]
    except ValueError as exc:
        print(f"shadow goal: {exc}", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(
        prog="shadow goal --install",
        description="Write the standing goal into each host's instruction file.",
    )
    parser.add_argument("--remove", action="store_true", help="take the block out again")
    parser.add_argument("--host", action="append", choices=sorted(targets),
                        help="limit to one host (repeatable); default is every known host")
    args = parser.parse_args(argv)

    block = standing_goal()
    if not block:
        print("shadow goal: no standing goal found in docs/reference/host-integration.md", file=sys.stderr)
        return 1

    status = 0
    source = topology["source"]
    if source is not None and args.host:
        print(
            "failed:    configured directive topology: --host is unavailable with a shared "
            "directive source; install or remove Claude and Codex together",
            file=sys.stderr,
        )
        return 1
    selected = {name: targets[name] for name in (args.host or sorted(targets))}
    if source is not None:
        try:
            verify_declared_topology(source, selected)
            result = apply(source, block, remove=args.remove)
        except (OSError, ValueError) as exc:
            print(f"failed:    configured directive topology: {exc}", file=sys.stderr)
            return 1
        for name, path in selected.items():
            detail = f"{str(result) + ':':10} {name} -> {path} -> {result.target}"
            if result.backup is not None:
                detail += f" (backup retained: {result.backup})"
            print(detail)
    else:
        for name, path in selected.items():
            if not path.parent.is_dir():
                # The host is not installed on this machine. Not an error.
                print(f"skipped:   {name} (no host directory)")
                continue
            try:
                result = apply(path, block, remove=args.remove)
            except (OSError, ValueError) as exc:
                print(f"failed:    {name}: {exc}", file=sys.stderr)
                status = 1
                continue
            detail = f"{str(result) + ':':10} {name} -> {result.target}"
            if result.backup is not None:
                detail += f" (backup retained: {result.backup})"
            print(detail)
    if topology["projections"].get("cursor") == "user_rules":
        print(
            "\nCursor user_rules projection is manual and read-only to Shadow; "
            f"expected standing-goal sha256: {projection_sha256(block)}"
        )
    else:
        print("\nCursor is not written: declare directives.projections.cursor: user_rules for a manual projection receipt.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
