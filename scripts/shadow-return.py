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

SPEC = importlib.util.spec_from_file_location("shadow_return_amp", ROOT / "scripts" / "shadow-amp.py")
amp = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault("shadow_return_amp", amp)
SPEC.loader.exec_module(amp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shadow return", description=__doc__)
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--repo", type=Path)
    location.add_argument("--entity", help="computer-board entity id")
    parser.add_argument("--row", required=True)
    parser.add_argument("--by", required=True, help="the current claim owner")
    args = parser.parse_args(argv)
    if not amp.valid_selector(args.row):
        print(
            "shadow return: --row wants a four-char id like ~ab12 or an exact "
            "leading legacy label like P9a~formats",
            file=sys.stderr,
        )
        return 2
    try:
        board.validate_owner(args.by)
    except board.BoardError as exc:
        print(f"shadow return: --by is unsafe: {exc}", file=sys.stderr)
        return 2
    try:
        board_root = board.configured_root()
        if not args.entity:
            board.assert_entity_board((args.repo or Path(".")).resolve(), root=board_root)
        if args.entity:
            resolved = board.resolve_entity(args.entity, root=board_root)
            if resolved is None or resolved["plan"] is None:
                raise board.BoardError("this entity is not registered on the computer board")
            state = resolved["state"]
            plan_path = resolved["plan"]
        else:
            plan_path = (args.repo or Path(".")).resolve() / "PLAN.md"
            if not board.regular_plan(plan_path):
                print(f"shadow return: no regular, non-symlink plan at {plan_path}", file=sys.stderr)
                return 2
            state = board.entity_state(
                plan_path, exact_on_conflict=True, root=board_root
            )
            if state is None or state["entity"] is None:
                raise board.BoardError("this entity is not registered on the computer board")
            plan_path = board.canonical_plan(
                plan_path,
                repair_missing=True,
                exact_on_conflict=True,
                root=board_root,
            )
        board.assert_entity_board(plan_path.parent, root=board_root)
        with board.project_lock(plan_path):
            plan_token, plan_bytes = board.committed_plan_snapshot(plan_path)
            plan_text = plan_bytes.decode("utf-8")
            parsed = amp._parse(plan_text)
            try:
                row_id = amp.resolve_row_selector(parsed, args.row)
            except amp.SelectorError as exc:
                raise board.BoardError(str(exc)) from exc
            rows = [
                row
                for milestone in parsed["milestones"]
                for row in milestone["rows"]
                if row["id"] == row_id
            ]
            if not rows:
                print(f"shadow return: no task carries {row_id}", file=sys.stderr)
                return 1
            if len(rows) != 1:
                raise board.BoardError(f"task id {row_id} is duplicated in the project plan")
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
            result = board.release(
                plan_path,
                row_id,
                resumes=amp._candidate_ids(parsed),
                owner=args.by,
                reason=reason,
                expected_plan=plan_token,
                expected_text=plan_text,
                root=board_root,
            )
    except (OSError, UnicodeError, board.BoardError) as exc:
        print(f"shadow return: {exc}", file=sys.stderr)
        return 1
    if result is None:
        print("shadow return: this project was not registered on the computer board", file=sys.stderr)
        return 1
    payload, changed = result
    display_row = args.row if args.row == row_id else f"{args.row} -> {row_id}"
    if not changed:
        print(
            f"{display_row} already absent; root board unchanged at "
            f"revision {payload['revision']}"
        )
        return 0
    print(
        f"returned {display_row} ({reason}); "
        f"root board revision {payload['revision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
