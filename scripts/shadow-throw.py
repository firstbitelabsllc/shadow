#!/usr/bin/env python3
"""shadow throw — record that a conversation is being dispatched, before it starts.

One chat throws dozens of conversations. The failure mode is not running them;
it is that the chat is the only place they exist. When the chat dies, its
in-flight work is unrecoverable — nothing on disk says a job was launched, what
it was meant to reach, or how anyone would know it finished.

So: no conversation leaves the chat until its row is claimed and pushed.
`throw` refuses unless a ready `[pending]` row exists, flips it to
`[in_progress]`, appends a THROWN Progress line, commits PLAN.md alone, pushes,
and prints the amp goal block. Launch and flush are one atom.

THROWN is also the discriminator a cold successor needs: an `in_progress` row
WITH a THROWN line was dispatched (probe its proof — the job may have finished
after the chat died); an `in_progress` row WITHOUT one is a hand-claimed
resume target. `shadow amp` skips thrown rows when auto-resuming so a fresh
seat never re-runs work already in flight.

No daemon, no queue, no session registry: liveness stays unprovable by design.
The row and its proof are the entire in-flight record.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("shadow_amp", ROOT / "scripts" / "shadow-amp.py")
_amp = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("shadow_amp", _amp)
_spec.loader.exec_module(_amp)

NOTE_MAX: Final = 200
# A lead is a name, not a sentence. Bounded because it lands in a Progress line
# other seats parse, and in the `--in-flight` view a person reads to decide who
# to talk to. Deliberately free text: v4 deleted the roster, and a registry of
# legal lead names would rebuild it.
BY_MAX: Final = 40
# A Progress entry is one line. Anything that can end a line can forge rows,
# sections, and THROWN entries in a file the whole board trusts, so the two
# operator-supplied values are constrained before they are serialized.
CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")

STAMP_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
# A remote URL can carry a token in its userinfo; git echoes the URL back on a
# rejected push, and that stderr lands in terminals and CI logs.
CREDENTIAL_RE: Final = re.compile(r"(?<=://)[^/\s@]+@")
# Advisory only. Shadow cannot see other chats (a session registry would be a
# banned second store), but it CAN count claimed rows, which is the honest
# proxy for "how much is this seat juggling".
BUSY_THRESHOLD: Final = 8


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def _atomic_write(path: Path, text: str) -> None:
    """Replace a file in one step, never leaving it partially written.

    `Path.write_text` truncates and then fills. A second process reading the
    file in that window sees whatever has been written so far — and the second
    process that matters here is `git commit`, which hashes the working tree
    copy. Two `shadow throw` runs in one checkout, which is exactly the
    documented two-leads-one-plan case, could hash a zero-length PLAN.md and
    push the empty blob as the board every other seat reads. Measured at 3
    occurrences in 45 same-checkout trials before this changed.

    A temp file in the same directory keeps the rename on one filesystem, so
    `os.replace` is atomic: readers see the old bytes or the new ones.
    """
    directory = path.parent
    handle, temporary = tempfile.mkstemp(dir=directory, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            # A fresh temp file is 0600; the plan is world-readable and stays so.
            os.chmod(temporary, path.stat().st_mode & 0o7777)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise



def thrown_ids(text: str) -> set[str]:
    """Task ids already carrying a THROWN Progress line."""
    return set(re.findall(r"^- \S+ THROWN (~[0-9a-z]{4})\b", text, flags=re.M))


def claimed_by(text: str, task_id: str) -> str | None:
    """Which lead holds `task_id`, read from its THROWN line.

    None when the row is not thrown at all. A name when `--by` was given, and
    "another seat" when it was thrown anonymously — the row is still claimed,
    and answering "nobody" because the claimant did not sign it would invite a
    second lead onto work already in flight.

    Progress is append-only, so a row handed back to [pending] and re-thrown
    carries several THROWN lines. The LAST one is the live claim; naming the
    historical claimant would send a losing lead to argue with someone who
    already let the row go.
    """
    lines = re.findall(rf"^- \S+ THROWN {re.escape(task_id)}\b(.*)$", text, flags=re.M)
    if not lines:
        return None
    named = re.search(r"\| by: ([^|]+)", lines[-1])
    return named.group(1).strip() if named else "another seat"


def _row_line(text: str, task_id: str) -> tuple[int, str] | None:
    for index, line in enumerate(text.splitlines()):
        match = _amp.ROW_RE.match(line)
        if match and match.group("id") == task_id:
            return index, line
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow throw",
        description="Claim a task row and print its goal block, before the work leaves the chat.",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    parser.add_argument("--task", required=True, help="the row to claim, e.g. ~ab12")
    parser.add_argument("--by", default="", help=f"which lead is claiming it (<={BY_MAX} chars, "
                                                 "free text: codex, claude, a person's name)")
    parser.add_argument("--note", default="", help=f"why it is being thrown (<={NOTE_MAX} chars)")
    parser.add_argument("--timestamp", default=None, help="ISO8601 Z (default: now)")
    parser.add_argument("--no-push", action="store_true",
                        help="commit without pushing (an unpushed dispatch is invisible to other seats)")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    plan_path = repo / "PLAN.md"
    if not plan_path.is_file():
        print(f"shadow throw: no plan at {plan_path}", file=sys.stderr)
        return 2
    if not re.fullmatch(r"~[0-9a-z]{4}", args.task):
        print(f"shadow throw: --task wants a four-char id like ~ab12, got {args.task}", file=sys.stderr)
        return 2
    if len(args.note) > NOTE_MAX:
        print(f"shadow throw: --note exceeds {NOTE_MAX} chars", file=sys.stderr)
        return 2
    if CONTROL_RE.search(args.note):
        print("shadow throw: --note must be a single line of text — a newline in a Progress "
              "entry would write rows and sections nobody authored", file=sys.stderr)
        return 2
    if len(args.by) > BY_MAX:
        print(f"shadow throw: --by exceeds {BY_MAX} chars — it names a lead, not a sentence",
              file=sys.stderr)
        return 2
    # `|` would open a second tail field, so a lead name could forge `note:` or
    # any future key on a line other seats parse. Same class as the newline.
    if CONTROL_RE.search(args.by) or "|" in args.by:
        print("shadow throw: --by must be a single line with no '|' — it lands in a Progress "
              "entry that other seats parse into fields", file=sys.stderr)
        return 2
    if args.timestamp is not None and not STAMP_RE.fullmatch(args.timestamp):
        print("shadow throw: --timestamp wants ISO8601 Z like 2026-08-09T03:00:00Z, "
              f"got {args.timestamp!r}", file=sys.stderr)
        return 2

    # Refuse on an unresolved merge — never claim a row mid-conflict.
    if git(repo, "ls-files", "-u", check=False).stdout.strip():
        print("shadow throw: repository has unmerged paths; resolve them first", file=sys.stderr)
        return 1

    # `git commit --only -- PLAN.md` commits the file as it stands on disk, so
    # unrelated edits would ride along inside the dispatch commit — and get
    # pushed. The claim travels alone or not at all.
    status = git(repo, "status", "--porcelain", "--", "PLAN.md", check=False).stdout.strip()
    if status.startswith("??"):
        print("shadow throw: PLAN.md is untracked; commit it before dispatching from it",
              file=sys.stderr)
        return 1
    if status:
        print("shadow throw: PLAN.md has uncommitted changes; commit or stash them first — "
              "the dispatch commit carries the claim alone", file=sys.stderr)
        return 1

    # Fresh re-read immediately before the write: another seat may have claimed
    # this row since the chat last looked.
    text = plan_path.read_text(encoding="utf-8")
    plan = _amp._parse(text)
    located = _row_line(text, args.task)
    if located is None:
        print(f"shadow throw: no task carries {args.task} in {plan_path}", file=sys.stderr)
        return 1
    index, line = located
    match = _amp.ROW_RE.match(line)
    state = match.group("state")
    if state != "pending":
        already = " (already thrown)" if args.task in thrown_ids(text) else ""
        print(f"shadow throw: {args.task} is [{state}], not [pending]{already} — "
              "refusing to re-claim another seat's work", file=sys.stderr)
        return 1

    done = _amp._completed_ids(plan["milestones"])
    fields = {m.group("key"): m.group("value").strip()
              for m in _amp.FIELD_RE.finditer(match.group("tail") or "")}
    unmet = [ref for ref in _amp.HASH_RE.findall(fields.get("needs", "")) if ref not in done]
    if unmet:
        print(f"shadow throw: {args.task} still needs {', '.join(unmet)}", file=sys.stderr)
        return 1
    if not fields.get("proof"):
        print(f"shadow throw: {args.task} has no proof — a thrown row's proof is its "
              "completion predicate, and without one nobody can tell if the job finished",
              file=sys.stderr)
        return 1

    in_flight_before = sum(
        1 for m in plan["milestones"] for r in m["rows"] if r["state"] == "in_progress"
    )

    stamp = args.timestamp or subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True, check=True
    ).stdout.strip()

    lines = text.splitlines()
    lines[index] = line.replace("- [pending] ", "- [in_progress] ", 1)
    body = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    # Tail only, never before the id: `_thrown_ids` in shadow-amp.py anchors on
    # `^- \S+ THROWN (~hash)\b`, so a lead name inserted ahead of the id would
    # make every thrown row invisible to auto-resume-skip, fleet-wide.
    by = f" | by: {args.by}" if args.by else ""
    note = f" | note: {args.note}" if args.note else ""
    thrown = f"- {stamp} THROWN {args.task} {match.group('text')}{by}{note}\n"
    # Progress is append-only, newest at the bottom (the grammar, and what
    # `shadow accept` does with its PROOF lines) — so the entry goes at the end
    # of the section, not under its heading.
    heading = re.search(r"^## Progress[^\n]*\n", body, flags=re.M)
    if heading is None:
        body = body.rstrip("\n") + "\n\n## Progress\n\n" + thrown
    else:
        boundary = body.find("\n## ", heading.end())
        if boundary == -1:
            body = body.rstrip("\n") + "\n" + thrown
        else:
            # A section after Progress would otherwise swallow the entry.
            body = body[:boundary].rstrip("\n") + "\n" + thrown + "\n" + body[boundary + 1:]
    # The exact index entry, not a "was it staged" flag: a staged snapshot that
    # differs from the working tree must come back byte-for-byte if the claim
    # cannot be made durable.
    index_entry = git(repo, "ls-files", "--stage", "--", "PLAN.md", check=False).stdout.strip()
    head_before = git(repo, "rev-parse", "--verify", "HEAD", check=False).stdout.strip()

    def restore_plan() -> None:
        """Put the plan and its index entry back exactly as they were: a row
        flipped to in_progress with no commit behind it reads as somebody's
        claim and refuses every retry."""
        _atomic_write(plan_path, text)
        if index_entry:
            fields_ = index_entry.split()
            git(repo, "update-index", "--cacheinfo", f"{fields_[0]},{fields_[1]},PLAN.md", check=False)
        else:
            git(repo, "rm", "--cached", "--quiet", "--", "PLAN.md", check=False)

    _atomic_write(plan_path, body)

    try:
        git(repo, "commit", "--only", "--quiet",
            "-m", f"plan: THROWN {args.task} — dispatched, claimed before launch",
            "--", "PLAN.md")
    except RuntimeError as exc:
        restore_plan()
        print(f"shadow throw: commit failed; the plan was restored and nothing was dispatched: {exc}",
              file=sys.stderr)
        return 1

    # Read the plan back OUT of the commit before anything is pushed.
    #
    # A zero-exit commit says git ran, not that it recorded the right bytes. If
    # anything truncated or reverted the file between the write and the hash,
    # the push would publish that to every other seat, and lint reads an empty
    # plan as clean. The claim is what makes dispatch durable, so it is checked
    # against the object git actually stored — the only copy that will travel.
    recorded = git(repo, "show", "HEAD:PLAN.md", check=False)
    committed = recorded.stdout if recorded.returncode == 0 else ""
    if len(committed) < len(text) // 2 or f"THROWN {args.task}" not in committed:
        rolled_back = bool(head_before) and git(
            repo, "reset", "--quiet", "--soft", head_before, check=False).returncode == 0
        if rolled_back:
            restore_plan()
        print("shadow throw: the commit does not contain the claim — refusing to push a plan "
              f"other seats would read as authority. Recorded {len(committed)} chars against "
              f"{len(text)} on disk. "
              + ("The commit was rolled back and the plan restored; nothing was dispatched."
                 if rolled_back
                 else "The commit could NOT be rolled back — inspect HEAD before throwing again."),
              file=sys.stderr)
        return 1

    # Build the block before pushing. While the claim has not left this machine
    # it can still be undone, so a block that cannot be built dispatches
    # nothing — which is what a nonzero exit is read to mean.
    try:
        block, _ = _amp.build_block(_amp._parse(body), repo, plan_path, args.task, _amp.DEFAULT_MAX_CHARS)
    except (LookupError, ValueError) as exc:
        rolled_back = bool(head_before) and git(
            repo, "reset", "--quiet", "--soft", head_before, check=False
        ).returncode == 0
        if rolled_back:
            restore_plan()
            print(f"shadow throw: the goal block could not be built; the claim was rolled back "
                  f"and nothing was dispatched: {exc}", file=sys.stderr)
        else:
            print(f"shadow throw: {args.task} is claimed and committed, but the goal block could "
                  f"not be built and the claim could not be rolled back: {exc}\n"
                  f"  the dispatch stands — recover the block with `shadow amp --task {args.task}`, "
                  "or hand the row back with a [pending] flip", file=sys.stderr)
        return 1

    push_failed = False
    pushed = False
    if not args.no_push:
        # Push to the branch's CONFIGURED upstream, not to a remote branch that
        # merely shares its local name. A local `master` tracking `origin/main`
        # used to create a brand-new `origin/master` and still report "pushed":
        # the claim row was invisible on the branch every other seat reads,
        # which is the one failure "launch and flush are one atom" must not have.
        upstream = git(
            repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False
        )
        if upstream.returncode == 0 and "/" in upstream.stdout.strip():
            remote, _, remote_branch = upstream.stdout.strip().partition("/")
        else:
            remote = "origin"
            remote_branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        push = git(repo, "push", remote, f"HEAD:{remote_branch}", check=False)
        pushed = push.returncode == 0
        push_failed = not pushed
        if push_failed and head_before:
            # THE RACE. Two leads throw against one plan and both push; one
            # lands, the other bounces. That bounce IS the mutex — no lock, no
            # daemon, no coordinator, and no session registry. The loser can
            # recover itself, and only one question matters: did the winner
            # claim THIS row, or a different one?
            #
            # Recovery is attempted only when it is provably safe. `head_before`
            # being an ancestor of the fetched remote tip means this claim
            # commit is the only local commit — a plain race. Anything else
            # (other local work, a diverged branch) is somebody's judgment call,
            # so the claim is left exactly where it is and the operator is told.
            #
            # The tip must also have MOVED. A hook or a branch policy rejects a
            # push without anyone else landing anything, and there `head_before`
            # is still an ancestor — of itself. Recovering there would throw
            # away a perfectly good local claim and blame a race that never
            # happened, when the honest answer is the push-rejected path.
            fetched = git(repo, "fetch", "--quiet", remote, remote_branch, check=False)
            remote_tip = git(
                repo, "rev-parse", "--verify", f"{remote}/{remote_branch}", check=False
            ) if fetched.returncode == 0 else None
            advanced = (
                remote_tip is not None
                and remote_tip.returncode == 0
                and remote_tip.stdout.strip() not in ("", head_before)
            )
            # Ancestry proves there are no unpushed COMMITS. It says nothing
            # about the index or the working tree, and the cleanliness check up
            # front only covered PLAN.md — so edits to any other tracked file
            # are still unsaved work that `reset --hard` would delete. Untracked
            # files survive a reset, so they do not block recovery.
            dirty = git(
                repo, "status", "--porcelain", "--untracked-files=no", check=False
            ).stdout.strip()
            recoverable = advanced and not dirty and git(
                repo, "merge-base", "--is-ancestor", head_before, f"{remote}/{remote_branch}",
                check=False,
            ).returncode == 0
            if recoverable:
                git(repo, "reset", "--quiet", "--hard", f"{remote}/{remote_branch}", check=False)
                claimant = claimed_by(plan_path.read_text(encoding="utf-8"), args.task)
                if claimant is not None:
                    print(f"shadow throw: {args.task} was claimed by {claimant} while this claim "
                          "was in flight, so the row is theirs and nothing was dispatched. This "
                          "checkout is now on the winning revision. Take another row, or say so "
                          "in the plan before contesting it.", file=sys.stderr)
                else:
                    print(f"shadow throw: another seat pushed first, but it claimed a different "
                          f"row. This checkout is now on {remote}/{remote_branch} and {args.task} "
                          "is still open — re-run to claim it.", file=sys.stderr)
                return 1
            if advanced and dirty:
                # A real race, but recovery was declined. Say why, or the
                # push-rejected text below reads as advice to rebase into a row
                # somebody else already owns.
                print("shadow throw: another seat pushed first, but this checkout has "
                      "uncommitted changes to tracked files, so nothing was reset — recovering "
                      "the claim would have destroyed them. Commit or stash them, then fetch "
                      "and re-run throw.", file=sys.stderr)
        if push_failed:
            detail = CREDENTIAL_RE.sub("***@", push.stderr.strip())[:300]
            # Withhold the goal block. Exiting nonzero is not enough on its own:
            # printing a pasteable dispatch while saying "do not use it" is the
            # mixed signal that gets ignored, and the claim is not on the remote,
            # so every other seat still sees the row as [pending].
            print("shadow throw: PUSH REJECTED — the claim is committed locally but NOT on the "
                  "remote, so this dispatch is invisible to every other seat and machine. "
                  "DO NOT LAUNCH THE WORK. Fetch, rebase, re-push, then re-run throw "
                  f"(or pass --no-push deliberately):\n  {detail}", file=sys.stderr)
            return 1

    sys.stdout.write(block)
    status = "claimed + pushed" if pushed else "claimed (NOT pushed)"
    print(f"[throw] {args.task} {status}; {in_flight_before + 1} row(s) now in flight in this plan",
          file=sys.stderr)
    if in_flight_before + 1 >= BUSY_THRESHOLD:
        print(f"[throw] {in_flight_before + 1} in flight — at this depth a chief is splitting "
              "attention thin. Land or park something before throwing more; "
              "`shadow status --in-flight` shows every claimed row.", file=sys.stderr)
    # A failed push leaves the claim local-only: exit nonzero so a caller never
    # reads zero as "durably dispatched".
    return 1 if push_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
