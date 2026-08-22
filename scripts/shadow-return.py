#!/usr/bin/env python3
"""Return one owned claim, including a published remote-only manual completion."""

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


def _claim_from_remote_receipt(receipt: dict) -> dict:
    return {
        "entity": receipt["entity"],
        "row": receipt["row"],
        "owner": receipt["owner"],
        **receipt["claim"],
    }


def _remote_only_manual_completion(
    plan_path: Path,
    plan_token: dict[str, str],
    row: dict,
    row_id: str,
    owner: str,
    current: dict,
) -> dict | None:
    """Authenticate one published read/gate completion with no local claim."""
    repo = Path(plan_token["repo"])
    if board.is_local_plan(plan_path):
        return None
    entity = current.get("entity") if current else None
    project = current.get("project") if current else None
    if entity is None or project is None:
        raise board.BoardError("remote claim recovery cannot resolve its board identity")
    try:
        active = remote_claim.discover_active(
            repo,
            entity=entity["id"],
            project=project["id"],
            rows=[row_id],
            relative=plan_token["relative"],
            recover_detached=True,
        )
    except remote_claim.RemoteClaimError as exc:
        raise board.BoardError(
            "the completed row's remote claim could not be authenticated; "
            "remote claim retained"
        ) from exc
    if not active:
        return None
    if len(active) != 1:
        raise board.BoardError("the completed row has conflicting remote claims")
    receipt = active[0]
    if receipt["owner"] != owner:
        raise board.BoardError(
            f"{row_id} has a remote claim owned by {receipt['owner']}, not {owner}"
        )
    local_proof = row["fields"].get("proof", "")
    if not local_proof.startswith(("read ", "gate ")):
        raise board.BoardError(
            "remote-only return requires a completed read or gate proof; "
            "use shadow accept for a cmd proof"
        )
    try:
        published_bytes = remote_claim.published_plan_bytes(repo, plan_token)
    except remote_claim.RemoteClaimError as exc:
        raise board.BoardError(
            "completion publication could not be authenticated; remote claim retained"
        ) from exc
    if published_bytes is None:
        raise board.BoardError(
            "completed manual proof is not published on the configured origin; "
            "remote claim retained"
        )
    try:
        published_text = published_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise board.BoardError(
            "the current published project plan is not UTF-8; remote claim retained"
        ) from exc
    published = amp._parse(published_text)
    unclean = amp.unclean_note(published)
    if unclean:
        raise board.BoardError(
            f"the current published project plan cannot close a remote claim: {unclean}"
        )
    matches = [
        candidate
        for milestone in published["milestones"]
        for candidate in milestone["rows"]
        if candidate["id"] == row_id
    ]
    if len(matches) != 1:
        raise board.BoardError(
            "current origin default PLAN no longer carries exactly one completed row; "
            "remote claim retained"
        )
    published_row = matches[0]
    published_proof = published_row["fields"].get("proof", "")
    if (
        published_row["state"] != "completed"
        or published_proof != local_proof
        or not published_proof.startswith(("read ", "gate "))
        or not board.progress_proof_receipts(published_text, row_id)
    ):
        raise board.BoardError(
            "current origin default PLAN no longer carries the completed manual proof "
            "and its receipt; remote claim retained"
        )
    return _claim_from_remote_receipt(receipt)


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
            current = board.entity_state(plan_path, exact_on_conflict=True)
            claim = next(
                (
                    item for item in (current["claims"] if current else [])
                    if item["row"] == args.row
                ),
                None,
            )
            if claim is not None and claim["owner"] != args.by:
                raise board.BoardError(f"claim is owned by {claim['owner']}")
            rows = [
                row
                for milestone in parsed["milestones"]
                for row in milestone["rows"]
                if row["id"] == args.row
            ]
            if not rows:
                if claim is None:
                    print(f"shadow return: no task carries {args.row}", file=sys.stderr)
                    return 1
                reason = "orphan"
            elif len(rows) != 1:
                raise board.BoardError(f"task id {args.row} is duplicated in the project plan")
            else:
                row = rows[0]
                reason = (
                    "completed"
                    if row["state"] == "completed"
                    else "blocked"
                    if row["state"] == "blocked"
                    else "handback"
                )
            unclean = amp.unclean_note(parsed)
            if unclean:
                raise board.BoardError(f"project plan cannot return a claim: {unclean}")
            # Resume arbitration needs the full reachable order, including rows
            # currently claimed by other seats. The board removes this row itself.
            parsed["claimed"] = set()
            remote_only_claim = None
            if claim is None and reason == "completed":
                remote_only_claim = _remote_only_manual_completion(
                    plan_path,
                    plan_token,
                    row,
                    args.row,
                    args.by,
                    current,
                )
            transition_claim = claim or remote_only_claim
            if transition_claim is not None and not board.is_local_plan(plan_path):
                repo = Path(plan_token["repo"])
                remote = remote_claim.transition(
                    repo,
                    entity=transition_claim["entity"],
                    row=args.row,
                    owner=args.by,
                    project=current["project"]["id"],
                    plan_token=plan_token,
                    claim=transition_claim,
                    state="completed" if reason == "completed" else "released",
                    reason=reason,
                    recover_detached=remote_only_claim is not None,
                )
                if remote is not None and remote["status"] != "acquired":
                    raise board.BoardError(
                        "remote claim transition was not confirmed; exact claim retained"
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
        if remote_only_claim is not None:
            print(
                f"returned {args.row} (completed); remote claim completed; "
                f"local claim already absent at revision {payload['revision']}"
            )
            return 0
        print(f"{args.row} already absent; root board unchanged at revision {payload['revision']}")
        return 0
    print(f"returned {args.row} ({reason}); root board revision {payload['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
