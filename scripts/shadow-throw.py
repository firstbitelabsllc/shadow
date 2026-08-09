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
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("shadow_amp", ROOT / "scripts" / "shadow-amp.py")
_amp = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("shadow_amp", _amp)
_spec.loader.exec_module(_amp)

NOTE_MAX: Final = 200
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


def thrown_ids(text: str) -> set[str]:
    """Task ids already carrying a THROWN Progress line."""
    return set(re.findall(r"^- \S+ THROWN (~[0-9a-z]{4})\b", text, flags=re.M))


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
    note = f" | note: {args.note}" if args.note else ""
    thrown = f"- {stamp} THROWN {args.task} {match.group('text')}{note}\n"
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
        plan_path.write_text(text, encoding="utf-8")
        if index_entry:
            fields_ = index_entry.split()
            git(repo, "update-index", "--cacheinfo", f"{fields_[0]},{fields_[1]},PLAN.md", check=False)
        else:
            git(repo, "rm", "--cached", "--quiet", "--", "PLAN.md", check=False)

    plan_path.write_text(body, encoding="utf-8")

    try:
        git(repo, "commit", "--only", "--quiet",
            "-m", f"plan: THROWN {args.task} — dispatched, claimed before launch",
            "--", "PLAN.md")
    except RuntimeError as exc:
        restore_plan()
        print(f"shadow throw: commit failed; the plan was restored and nothing was dispatched: {exc}",
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
