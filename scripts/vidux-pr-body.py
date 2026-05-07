#!/usr/bin/env python3
"""Build the canonical ready-PR body for vidux automation lanes."""

from __future__ import annotations

import argparse
import re
import sys


LINEAR_REF_RE = re.compile(r"^[A-Z]+-\d+$")


def _clean(value: str, *, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def build_pr_body(
    *,
    lane: str,
    task: str,
    resume: str,
    changes: list[str],
    linear: str | None = None,
) -> str:
    """Return the durable PR body every automation lane can resume from."""
    lane = _clean(lane, field="lane")
    task = _clean(task, field="task")
    resume = _clean(resume, field="resume")

    cleaned_changes = [_clean(change, field="change") for change in changes]
    if not cleaned_changes:
        raise ValueError("at least one --change entry is required")

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
    parser.add_argument(
        "--resume",
        required=True,
        help="What the next cycle should do if this PR stalls.",
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
