#!/usr/bin/env python3
"""Build the canonical ready-PR body for vidux automation lanes."""

from __future__ import annotations

import argparse
import re
import sys


LINEAR_REF_RE = re.compile(r"^[A-Z]+-\d+$")
HANDOFF_STATUSES = {"done", "in_progress", "blocked", "needs_review"}


def _clean(value: str, *, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def build_pr_body(
    *,
    lane: str,
    task: str,
    plan_path: str,
    proof: str,
    handoff_status: str,
    ledger: str,
    files_claimed: list[str],
    resume: str,
    changes: list[str],
    linear: str | None = None,
) -> str:
    """Return the durable PR body every automation lane can resume from."""
    lane = _clean(lane, field="lane")
    task = _clean(task, field="task")
    plan_path = _clean(plan_path, field="plan_path")
    proof = _clean(proof, field="proof")
    ledger = _clean(ledger, field="ledger")
    handoff_status = _clean(handoff_status, field="handoff_status")
    if handoff_status not in HANDOFF_STATUSES:
        allowed = ", ".join(sorted(HANDOFF_STATUSES))
        raise ValueError(f"handoff_status must be one of: {allowed}")
    resume = _clean(resume, field="resume")

    cleaned_changes = [_clean(change, field="change") for change in changes]
    if not cleaned_changes:
        raise ValueError("at least one --change entry is required")
    cleaned_files = [_clean(path, field="file_claimed") for path in files_claimed]
    if not cleaned_files:
        raise ValueError("at least one --file-claimed entry is required")

    body = [
        "## Automation",
        f"Lane: {lane}",
        f"Plan task: {task}",
    ]

    if linear is not None:
        linear = _clean(linear, field="linear").upper()
        if not LINEAR_REF_RE.match(linear):
            raise ValueError("linear must use the public issue id shape, e.g. EVE-123")
        body.append(f"Linear: {linear}")

    body.extend(
        [
            "",
            "## Publish Propagation",
            f"Plan path: {plan_path}",
            f"Proof: {proof}",
            f"Ledger: {ledger}",
            f"Handoff status: {handoff_status}",
            "Files claimed:",
        ]
    )

    for path in cleaned_files:
        body.append(path if path.startswith("- ") else f"- {path}")

    body.extend(
        [
            "",
            f"Resume point: {resume}",
            "",
            "## Changes",
        ]
    )

    for change in cleaned_changes:
        body.append(change if change.startswith("- ") else f"- {change}")

    return "\n".join(body) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a canonical vidux automation PR body."
    )
    parser.add_argument("--lane", required=True, help="Lane id, e.g. codex/resplit-web")
    parser.add_argument("--task", required=True, help="PLAN.md task id, e.g. BD-68")
    parser.add_argument("--plan-path", required=True, help="Owning PLAN.md path.")
    parser.add_argument("--proof", required=True, help="Command or artifact proving the PR state.")
    parser.add_argument(
        "--handoff-status",
        required=True,
        choices=sorted(HANDOFF_STATUSES),
        help="Current resume status for the PR handoff.",
    )
    parser.add_argument(
        "--ledger",
        required=True,
        help="Ledger eid, ledger command dry-run payload, or proof path for the publish row.",
    )
    parser.add_argument(
        "--resume",
        required=True,
        help="What the next cycle should do if this PR stalls.",
    )
    parser.add_argument(
        "--file-claimed",
        action="append",
        default=[],
        help="File/plan path claimed by this PR. Repeat for multiple files.",
    )
    parser.add_argument(
        "--change",
        action="append",
        default=[],
        help="One concise change summary. Repeat for 1-3 bullets.",
    )
    parser.add_argument(
        "--linear",
        help="Optional public Linear issue id, e.g. EVE-123, when already known.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        sys.stdout.write(
            build_pr_body(
                lane=args.lane,
                task=args.task,
                plan_path=args.plan_path,
                proof=args.proof,
                handoff_status=args.handoff_status,
                ledger=args.ledger,
                files_claimed=args.file_claimed,
                resume=args.resume,
                changes=args.change,
                linear=args.linear,
            )
        )
    except ValueError as exc:
        sys.stderr.write(f"vidux-pr-body: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
