#!/usr/bin/env python3
"""Poll a vidux GitHub PR until review-gate is satisfied, then squash-merge.

Replaces `gh pr merge --auto --squash` for vidux automation lanes. The
`--auto` flag merges the moment branch protection lets it through; on a
repo without REQUIRED checks the merge fires immediately, bypassing the
repo policy that required review bots + CI must pass on the *latest* commit
before any squash.

This helper polls `gh pr view --json headRefOid,statusCheckRollup,reviews`
on a fixed interval, checks readiness against the latest commit SHA, and
only invokes `gh pr merge --squash --delete-branch` when every gate is
green. If the cap is reached without going green, exits with the
`ACK-PENDING` token so the next 30-min cron cycle can pick up.

Exit codes: 0 merged/ready, 1 ACK-PENDING (not green within --max-wait,
retry next cycle), 2 BLOCKED (CHANGES_REQUESTED or a failed check, will not
resolve on retry), 3 GH-ERROR (the `gh` CLI call itself failed -- auth,
network, or PATH problem, not a readiness signal; distinct from 1 so a
caller doesn't mistake a broken tool for "not ready yet" and retry forever).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Sequence


DEFAULT_REQUIRED_BOTS = ("graphite-app",)
SUCCESS_CONCLUSIONS = frozenset({"SUCCESS", "SKIPPED", "NEUTRAL"})
PENDING_STATUSES = frozenset({"QUEUED", "IN_PROGRESS", "PENDING", "WAITING"})
GRAPHITE_CHECK_NAMES = ("Graphite / AI Reviews",)

# Some bots ack via a CheckRun rather than a review entry when they have no
# blocking concerns. Graphite, in particular, only submits a review when it
# wants to flag something — silent passes only show up as the AI Reviews
# CheckRun going SUCCESS. This mapping lets the helper accept that signal as
# a stand-in for a missing review entry.
CHECKRUN_FALLBACK_FOR_BOT = {"graphite-app": GRAPHITE_CHECK_NAMES}


@dataclass
class ReadinessReport:
    ready: bool
    reason: str
    pending_checks: list[str] = field(default_factory=list)
    pending_bots: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def _check_runs(view: dict) -> list[dict]:
    """Return CheckRun + StatusContext entries from statusCheckRollup."""
    return list(view.get("statusCheckRollup") or [])


def _reviews_on_commit(view: dict, sha: str) -> list[dict]:
    """Return reviews whose commit.oid matches the latest head SHA."""
    out = []
    for r in view.get("reviews") or []:
        commit = r.get("commit") or {}
        if commit.get("oid") == sha:
            out.append(r)
    return out


def assess(view: dict) -> ReadinessReport:
    """Pure function — given a `gh pr view` payload, return readiness."""
    sha = view.get("headRefOid")
    if not sha:
        return ReadinessReport(
            ready=False,
            reason="blocked: missing headRefOid in gh pr view payload",
            blockers=["headRefOid"],
        )

    pending_checks: list[str] = []
    failed_checks: list[str] = []
    # Track bot-fallback CheckRun states separately so they can stand in for
    # a missing review entry from the same bot (see CHECKRUN_FALLBACK_FOR_BOT).
    fallback_check_state: dict[str, str] = {}
    fallback_names = {n for names in CHECKRUN_FALLBACK_FOR_BOT.values() for n in names}

    for entry in _check_runs(view):
        name = entry.get("name") or entry.get("context") or "<unknown>"
        status = (entry.get("status") or "").upper()
        conclusion = (entry.get("conclusion") or "").upper()
        is_fallback = name in fallback_names
        if is_fallback:
            if status in PENDING_STATUSES or status != "COMPLETED":
                fallback_check_state[name] = "PENDING"
            elif conclusion in SUCCESS_CONCLUSIONS:
                fallback_check_state[name] = "SUCCESS"
            else:
                fallback_check_state[name] = f"FAILURE:{conclusion or 'UNKNOWN'}"
            # Bot-fallback CheckRuns do NOT contribute to the CI gate; they
            # feed bot-ack below.
            continue
        if status in PENDING_STATUSES or status == "":
            pending_checks.append(name)
            continue
        if status != "COMPLETED":
            pending_checks.append(name)
            continue
        if conclusion in SUCCESS_CONCLUSIONS:
            continue
        failed_checks.append(f"{name}={conclusion or 'UNKNOWN'}")

    required_bots = view.get("__required_bots") or list(DEFAULT_REQUIRED_BOTS)
    on_sha = _reviews_on_commit(view, sha)
    bot_seen: dict[str, str] = {}
    changes_requested: list[str] = []
    for review in on_sha:
        login = ((review.get("author") or {}).get("login") or "").lower()
        state = (review.get("state") or "").upper()
        if state == "CHANGES_REQUESTED":
            changes_requested.append(f"{login}:{review.get('id', '?')}")
        # Both COMMENTED and APPROVED count as "the bot weighed in on this SHA";
        # COMMENTED is what Graphite + Seer normally emit when they finish.
        if state in ("APPROVED", "COMMENTED"):
            bot_seen[login] = state

    # CheckRun fallback: a required bot may ack via its fallback CheckRun
    # going SUCCESS even when it never submits a review entry. A FAILURE on
    # that CheckRun is a hard blocker.
    fallback_blockers: list[str] = []
    pending_bots: list[str] = []
    for bot in required_bots:
        if bot.lower() in bot_seen:
            continue
        fallback = CHECKRUN_FALLBACK_FOR_BOT.get(bot.lower())
        ack_via_check = False
        if fallback:
            for check_name in fallback:
                state = fallback_check_state.get(check_name)
                if state == "SUCCESS":
                    bot_seen[bot.lower()] = "CHECKRUN-SUCCESS"
                    ack_via_check = True
                    break
                if state and state.startswith("FAILURE"):
                    fallback_blockers.append(f"{check_name}={state[len('FAILURE:'):]}")
                    ack_via_check = True
                    break
        if not ack_via_check:
            pending_bots.append(bot)

    blockers: list[str] = []
    if failed_checks:
        blockers.extend(f"check-failed:{c}" for c in failed_checks)
    if changes_requested:
        blockers.extend(f"changes-requested:{c}" for c in changes_requested)
    if fallback_blockers:
        blockers.extend(f"check-failed:{c}" for c in fallback_blockers)

    if blockers:
        return ReadinessReport(
            ready=False,
            reason=f"blocked: {'; '.join(blockers)}",
            pending_checks=pending_checks,
            pending_bots=pending_bots,
            blockers=blockers,
        )

    if pending_checks or pending_bots:
        bits = []
        if pending_checks:
            bits.append(f"checks={','.join(pending_checks)}")
        if pending_bots:
            bits.append(f"bots={','.join(pending_bots)}")
        return ReadinessReport(
            ready=False,
            reason=f"pending: {'; '.join(bits)}",
            pending_checks=pending_checks,
            pending_bots=pending_bots,
        )

    return ReadinessReport(ready=True, reason="all gates green")


def fetch_view(pr: int, repo: str | None) -> dict:
    cmd = ["gh", "pr", "view", str(pr), "--json", "headRefOid,statusCheckRollup,reviews"]
    if repo:
        cmd += ["--repo", repo]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def merge_now(pr: int, repo: str | None) -> None:
    cmd = ["gh", "pr", "merge", str(pr), "--squash", "--delete-branch"]
    if repo:
        cmd += ["--repo", repo]
    subprocess.run(cmd, check=True)


def poll_until_ready(
    pr: int,
    *,
    repo: str | None,
    max_wait_s: int,
    poll_interval_s: int,
    required_bots: Sequence[str],
    fetch=fetch_view,
    sleep=time.sleep,
    clock=time.monotonic,
) -> tuple[int, ReadinessReport]:
    """Poll until ready, blocked, cap reached, or the gh CLI call fails.

    Returns (exit_code, last_report). Exit code semantics:
      0  ready (caller should call merge_now)
      1  ack-pending (timed out)
      2  blocked (CHANGES_REQUESTED or FAILURE)
      3  gh-error (the `gh` CLI call itself failed -- not a readiness signal)

    `fetch` (== `gh pr view`) used to run with check=True and no surrounding
    try/except, so any transient gh failure (auth expiry, rate limit, network
    blip, gh not on PATH) raised uncaught out of this loop, out of main(), and
    crashed with a raw traceback instead of one of the three documented exit
    codes above -- a cron lane checking `rc == 1` for "not ready, retry next
    cycle" saw Python's traceback-triggered exit code 1 and treated a broken
    gh CLI as an ordinary pending state, which never resolves on retry (round-3
    readiness panel, code-quality-scripts lens). Exit code 3 is new and
    deliberately distinct from 1/2 so callers can tell "the tool is broken"
    from "not ready yet" / "reviewer said no" and stop retrying blindly.
    """
    deadline = clock() + max_wait_s
    last: ReadinessReport | None = None
    while True:
        try:
            view = fetch(pr, repo)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            return 3, ReadinessReport(ready=False, reason=f"gh-error: {exc}")
        view["__required_bots"] = list(required_bots)
        last = assess(view)
        if last.ready:
            return 0, last
        if last.blockers:
            return 2, last
        if clock() >= deadline:
            return 1, last
        sleep(poll_interval_s)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pr", type=int, help="PR number")
    p.add_argument("--repo", help="OWNER/NAME (default: gh's local detection)")
    p.add_argument("--max-wait", type=int, default=900, help="cap in seconds (default 900 = 15 min)")
    p.add_argument("--poll-interval", type=int, default=30, help="poll interval seconds (default 30)")
    p.add_argument(
        "--required-bot",
        action="append",
        default=None,
        help="bot login required to have reviewed the latest SHA (repeatable; default: graphite-app)",
    )
    p.add_argument("--no-merge", action="store_true", help="poll only; do not invoke gh pr merge")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    required_bots = args.required_bot or list(DEFAULT_REQUIRED_BOTS)
    code, report = poll_until_ready(
        args.pr,
        repo=args.repo,
        max_wait_s=args.max_wait,
        poll_interval_s=args.poll_interval,
        required_bots=required_bots,
    )
    print(report.reason, file=sys.stderr)
    if code == 0:
        if args.no_merge:
            print("READY: would merge (--no-merge set)", file=sys.stderr)
            return 0
        try:
            merge_now(args.pr, args.repo)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"GH-ERROR: merge command failed for PR #{args.pr}: {exc}", file=sys.stderr)
            return 3
        print(f"MERGED: PR #{args.pr}", file=sys.stderr)
        return 0
    if code == 1:
        print(f"ACK-PENDING: PR #{args.pr} not green within {args.max_wait}s", file=sys.stderr)
        return 1
    if code == 3:
        print(f"GH-ERROR: PR #{args.pr} — {report.reason}", file=sys.stderr)
        return 3
    print(f"BLOCKED: PR #{args.pr} — {report.reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
