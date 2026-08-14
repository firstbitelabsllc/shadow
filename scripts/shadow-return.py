#!/usr/bin/env python3
"""Return one local claim after completion, parking, or an explicit handback."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as board  # noqa: E402
import shadow_remote_claim as remote_claim  # noqa: E402

SPEC = importlib.util.spec_from_file_location("shadow_return_amp", ROOT / "scripts" / "shadow-amp.py")
amp = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault("shadow_return_amp", amp)
SPEC.loader.exec_module(amp)


def main(argv: list[str] | None = None) -> int:
    remote_claim.sanitize_process_git_env()
    parser = argparse.ArgumentParser(prog="shadow return", description=__doc__)
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--repo", type=Path)
    location.add_argument("--entity", help="computer-board entity id")
    parser.add_argument("--row", required=True)
    parser.add_argument("--by", required=True, help="the current claim owner")
    args = parser.parse_args(argv)
    if board.ROW_ID.fullmatch(args.row) is None:
        print("shadow return: --row wants a four-char id like ~ab12", file=sys.stderr)
        return 2
    try:
        board.validate_owner(args.by)
    except board.BoardError as exc:
        print(f"shadow return: --by is unsafe: {exc}", file=sys.stderr)
        return 2
    try:
        if args.entity:
            resolved = board.resolve_entity(args.entity)
            if resolved is None or resolved["plan"] is None:
                raise board.BoardError("this entity is not registered on the computer board")
            state = resolved["state"]
            plan_path = resolved["plan"]
        else:
            plan_path = (args.repo or Path(".")).resolve() / "PLAN.md"
            if not board.regular_plan(plan_path):
                print(f"shadow return: no regular, non-symlink plan at {plan_path}", file=sys.stderr)
                return 2
            state = board.entity_state(plan_path, exact_on_conflict=True)
            if state is None or state["entity"] is None:
                raise board.BoardError("this entity is not registered on the computer board")
            plan_path = board.canonical_plan(
                plan_path,
                repair_missing=True,
                exact_on_conflict=True,
            )
        with board.project_lock(plan_path):
            plan_token, plan_bytes = board.frozen_plan_snapshot(plan_path)
            plan_text = plan_bytes.decode("utf-8")
            parsed = amp._parse(plan_text)
            rows = [
                row
                for milestone in parsed["milestones"]
                for row in milestone["rows"]
                if row["id"] == args.row
            ]
            if not rows:
                print(f"shadow return: no task carries {args.row}", file=sys.stderr)
                return 1
            if len(rows) != 1:
                raise board.BoardError(f"task id {args.row} is duplicated in the project plan")
            unclean = amp.unclean_note(parsed)
            if unclean:
                raise board.BoardError(f"project plan cannot return a claim: {unclean}")
            row = rows[0]
            reason = (
                "completed"
                if row["state"] == "completed"
                else "blocked"
                if row["state"] == "blocked"
                else "handback"
            )
            # Resume arbitration needs the full reachable order, including rows
            # currently claimed by other seats. The board removes this row itself.
            parsed["claimed"] = set()
            current = board.entity_state(plan_path, exact_on_conflict=True)
            claim = next(
                (
                    item for item in (current["claims"] if current else [])
                    if item["row"] == args.row and item["owner"] == args.by
                ),
                None,
            )
            if claim is not None and not board.is_local_plan(plan_path):
                repo = Path(plan_token["repo"])
                remote = remote_claim.transition(
                    repo,
                    entity=claim["entity"],
                    row=args.row,
                    owner=args.by,
                    project=current["project"]["id"],
                    plan_token=plan_token,
                    claim=claim,
                    state="completed" if reason == "completed" else "released",
                    reason=reason,
                )
                if remote is not None and remote["status"] != "acquired":
                    raise board.BoardError(
                        "remote claim transition was not confirmed; exact local claim retained"
                    )
            result = board.release(
                plan_path,
                args.row,
                resumes=amp._candidate_ids(parsed),
                owner=args.by,
                reason=reason,
                expected_plan=plan_token,
                expected_text=plan_text,
                expected_claim=claim,
            )
    except (OSError, UnicodeError, board.BoardError) as exc:
        print(f"shadow return: {exc}", file=sys.stderr)
        return 1
    if result is None:
        print("shadow return: this project was not registered on the computer board", file=sys.stderr)
        return 1
    payload, changed = result
    if not changed:
        print(f"{args.row} already absent; root board unchanged at revision {payload['revision']}")
        return 0
    print(f"returned {args.row} ({reason}); root board revision {payload['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
