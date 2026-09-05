#!/usr/bin/env python3
"""Bounded, pull-first command line surface for Shadow Huddles."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import shadow_root_board as board
import shadow_huddle_event as event
import shadow_remote_claim as remote


MAX_STDIN = 64 * 1024
HUDDLE_ID = re.compile(r"hdl_[0-9a-f]{8}\Z")
ROOT = Path(__file__).resolve().parent.parent


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"error": message}), file=sys.stderr)
    raise SystemExit(code)


def _positive_int(value: str) -> int:
    try:
        result = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def _nonnegative_int(value: str) -> int:
    try:
        result = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return result


def _huddle_id(value: str) -> str:
    if not isinstance(value, str) or HUDDLE_ID.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("must be a canonical Huddle id")
    return value


def _entity_id(value: str) -> str:
    if not isinstance(value, str) or board.ENTITY_ID.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("must be a canonical entity id")
    return value


def _row_id(value: str) -> str:
    if not isinstance(value, str) or board.ROW_ID.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("must be a canonical row id")
    return value


def stdin_object() -> dict:
    data = sys.stdin.buffer.read(MAX_STDIN + 1)
    if len(data) > MAX_STDIN:
        fail("stdin exceeds bound")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=board._strict_json_object)
    except (ValueError, UnicodeError):
        fail("stdin must be one closed JSON object")
    if not isinstance(value, dict):
        fail("stdin must be one JSON object")
    return value


def _read_stdin(limit: int = MAX_STDIN) -> bytes:
    data = sys.stdin.buffer.read(limit + 1)
    if len(data) > limit:
        fail("stdin exceeds bound")
    return data


def out(value: object) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _huddle(payload: dict, huddle_id: str) -> dict:
    for huddle in payload.get("huddles", []):
        if huddle.get("id") == huddle_id:
            return huddle
    fail("Huddle was not found", 1)
    raise AssertionError("unreachable")


def _mutation_receipt(mutation: board.BoardMutation) -> dict:
    payload = mutation.payload
    detail = mutation.event or {}
    huddle = next((item for item in payload.get("huddles", [])
                   if item.get("id") == detail.get("huddle_id")), None)
    return {"board_revision": payload["revision"], "changed": mutation.changed,
            "huddle_id": huddle["id"] if huddle else None,
            "generation": huddle["generation"] if huddle else None}


def _current_claims(payload: dict) -> dict[tuple, dict]:
    return {board._claim_key(claim): claim for claim in payload.get("claims", [])}


def _actor_claim(payload: dict, huddle: dict, seat: str) -> dict:
    """Resolve the seat to one exact current Huddle participant."""
    current = _current_claims(payload)
    matches = []
    for reference in huddle["claims"]:
        claim = current.get(board._claim_key(reference))
        if claim is not None and claim["owner"] == seat and board._claim_ref(claim) == reference:
            matches.append(claim)
    if len(matches) != 1:
        raise board.BoardError("seat does not resolve to exactly one current Huddle participant")
    return board._claim_ref(matches[0])


def _pair_from_snapshot(payload: dict, huddle: dict) -> tuple[dict, dict, dict]:
    """Return exact current source, successor candidate, and target refs."""
    current = _current_claims(payload)
    bids = [bid for bid in huddle["bids"] if bid["round"] == huddle["round"]]
    yields = [bid for bid in bids if bid["role"] == "yield"]
    if len(yields) != 1:
        raise board.BoardError("Huddle settlement requires exactly one handoff pair")
    offer = yields[0]
    source_ref = offer.get("claim")
    target_ref = offer.get("target")
    if (not isinstance(source_ref, dict) or not isinstance(target_ref, dict)
            or not board._valid_claim_ref(source_ref)
            or not board._valid_claim_ref(target_ref)):
        raise board.BoardError("Huddle settlement requires a matching owner handoff pair")
    source = current.get(board._claim_key(source_ref))
    target = current.get(board._claim_key(target_ref))
    own = [bid for bid in bids if bid["role"] == "own"
           and bid["reason"] == "owner_authorized_handoff"
           and bid["claim"] == target_ref]
    if (source is None or target is None or board._claim_ref(source) != source_ref
            or board._claim_ref(target) != target_ref or len(own) != 1):
        raise board.BoardError("Huddle settlement requires a matching owner handoff pair")
    source_ref = board._claim_ref(source)
    target_ref = board._claim_ref(target)
    return source_ref, dict(source_ref, owner=target["owner"]), target_ref


def _source_entity(payload: dict, source: dict) -> dict:
    entity = next((item for item in payload["entities"] if item["id"] == source["entity"]), None)
    if entity is None:
        raise board.BoardError("remote Huddle source entity is missing")
    return entity


def _remote_context(payload: dict, source: dict) -> tuple[Path, dict, str, str]:
    """Resolve and authenticate the stable predecessor tip for a new handoff."""
    entity = _source_entity(payload, source)
    plan = Path(entity["plan"])
    eligibility, repo = remote.managed_repo_for_plan(plan)
    if eligibility is remote.RemoteEligibility.UNKNOWN or repo is None:
        raise board.BoardError("remote Huddle repository is unavailable")
    token, _ = board.committed_plan_snapshot(plan, repo=repo)
    binding = remote.upstream_binding(repo)
    if binding.eligibility is not remote.RemoteEligibility.REMOTE or binding.endpoint is None:
        raise board.BoardError("remote Huddle repository has no authenticated upstream")
    ref = remote.claim_ref(source["entity"], source["row"])
    observed, _ = remote._stable_huddle_tip(
        repo, endpoint=binding.endpoint, ref=ref, entity=source["entity"], row=source["row"],
        project=entity["project"], plan_token=token, retries=2,
    )
    if observed is None or len(observed) != 2 or remote.HEX_OBJECT.fullmatch(observed[0]) is None:
        raise board.BoardError("remote Huddle predecessor tip is not stable")
    if not remote._huddle_receipt_matches(observed[1], source, token):
        raise board.BoardError("remote Huddle predecessor claim does not match current authority")
    return repo, token, ref, observed[0]


def _settle_remote(payload: dict, huddle: dict, actor: dict, *, now: datetime,
                   home: Path) -> board.BoardMutation:
    source, successor, target = _pair_from_snapshot(payload, huddle)
    source_full = _current_claims(payload).get(board._claim_key(source))
    if source_full is None:
        raise board.BoardError("remote Huddle source claim changed before begin")
    repo, token, ref, remote_version = _remote_context(payload, source_full)
    begun = board.begin_huddle_handoff(
        huddle_id=huddle["id"], generation=huddle["generation"], source_claim=source,
        successor_claim=successor, target_prior_claim=target, remote_ref=ref,
        expected_remote_version=remote_version, now=now, home=home,
        expected_board_revision=payload["revision"], actor_claim=actor,
    )
    event.post_commit_mutation(begun, repo_root=ROOT, home=home)
    pending = _huddle(begun.payload, huddle["id"])
    transition = pending["remote_transition"]
    current = _current_claims(begun.payload)
    source_full = current.get(board._claim_key(transition["source_claim"]))
    target_full = current.get(board._claim_key(transition["target_prior_claim"]))
    if source_full is None or target_full is None:
        raise board.BoardError("remote Huddle handoff claims changed after begin")
    successor_full = dict(source_full, owner=transition["successor_claim"]["owner"])
    readback = remote.handoff_huddle_claim(
        repo, expected_remote_version=transition["expected_remote_version"],
        source_claim=source_full, successor_claim=successor_full,
        project=_source_entity(begun.payload, source_full)["project"], plan_token=token,
    )
    finished = board.finalize_huddle_handoff(
        huddle_id=pending["id"], generation=pending["generation"], remote_receipt=readback,
        now=now, home=home, expected_board_revision=begun.payload["revision"],
    )
    event.post_commit_mutation(finished, repo_root=ROOT, home=home)
    return finished


def _recover_remote_pending(payload: dict, huddle: dict, *, now: datetime,
                            home: Path) -> board.BoardMutation:
    transition = huddle.get("remote_transition")
    if not isinstance(transition, dict):
        raise board.BoardError("remote Huddle transition is missing")
    current = _current_claims(payload)
    source = current.get(board._claim_key(transition["source_claim"]))
    if source is None or board._claim_ref(source) != transition["source_claim"]:
        raise board.BoardError("remote Huddle source claim changed before recovery")
    successor_ref = transition.get("successor_claim")
    if not isinstance(successor_ref, dict) or not board._valid_claim_ref(successor_ref):
        raise board.BoardError("remote Huddle successor claim is malformed")
    successor = dict(source, owner=successor_ref["owner"])
    entity = _source_entity(payload, source)
    eligibility, repo = remote.managed_repo_for_plan(Path(entity["plan"]))
    if eligibility is not remote.RemoteEligibility.REMOTE or repo is None:
        raise board.BoardError("remote Huddle repository is unavailable")
    token, _ = board.committed_plan_snapshot(Path(entity["plan"]), repo=repo)
    readback = remote.read_remote_claim_stably(
        repo, expected_remote_version=transition["expected_remote_version"],
        source_claim=source, successor_claim=successor,
        project=entity["project"], plan_token=token,
    )
    finished = board.finalize_huddle_handoff(
        huddle_id=huddle["id"], generation=huddle["generation"], remote_receipt=readback,
        now=now, home=home, expected_board_revision=payload["revision"],
    )
    event.post_commit_mutation(finished, repo_root=ROOT, home=home)
    return finished


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shadow huddle")
    sub = parser.add_subparsers(dest="route", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--entity", required=True, type=_entity_id)
    preflight.add_argument("--row", required=True, type=_row_id)
    preflight.add_argument("--claim-revision", required=True, type=_nonnegative_int)
    preflight.add_argument("--by", required=True)
    preflight.add_argument("--repo", required=True)
    preflight.add_argument("--access", required=True, choices=("unscoped", "read_only", "write"))
    preflight.add_argument("--path", action="append", default=[])
    preflight.add_argument("--expect-board", required=True, type=_nonnegative_int)
    opening = sub.add_parser("open")
    opening.add_argument("--by", required=True)
    bid = sub.add_parser("bid")
    bid.add_argument("--id", required=True, type=_huddle_id)
    bid.add_argument("--generation", required=True, type=_positive_int)
    bid.add_argument("--by", required=True)
    showing = sub.add_parser("show")
    showing.add_argument("--id", required=True, type=_huddle_id)
    settle = sub.add_parser("settle")
    settle.add_argument("--id", required=True, type=_huddle_id)
    settle.add_argument("--generation", required=True, type=_positive_int)
    settle.add_argument("--expect-board", required=True, type=_nonnegative_int)
    settle.add_argument("--by", required=True)
    contact = sub.add_parser("contact-register")
    contact.add_argument("--seat", required=True)
    return parser


def _require_settle_cas(payload: dict, huddle: dict, *, generation: int,
                        board_revision: int) -> None:
    if payload["revision"] != board_revision:
        raise board.BoardError("Huddle settlement board revision changed")
    if huddle["generation"] != generation:
        raise board.BoardError("Huddle settlement generation changed")


def main() -> None:
    args = _parser().parse_args()
    home = Path(os.environ.get("HOME", str(Path.home())))
    now = datetime.now(timezone.utc)
    if args.route == "show":
        out(board.huddle_show(args.id, home=home))
        return
    if args.route == "contact-register":
        out(event.run_confined_contact_register(
            seat=args.seat, stdin=_read_stdin(getattr(event, "_MAX_IO", 16 * 1024)),
            repo_root=ROOT, home=home))
        return
    if args.route == "preflight":
        mutation = board.preflight_access(
            entity=args.entity, row=args.row, owner=args.by, repo=Path(args.repo),
            access=args.access, write_scope=args.path,
            expected_claim_revision=args.claim_revision,
            expected_board_revision=args.expect_board, now=now, home=home)
        event.post_commit_mutation(mutation, repo_root=ROOT, home=home)
        out(_mutation_receipt(mutation))
        return
    payload = board.snapshot(home=home)
    if payload is None:
        raise board.BoardError("board is unavailable")
    if args.route == "open":
        value = stdin_object()
        if (set(value) != {"claim_keys", "reason"}
                or value["reason"] != "semantic_suspicion"
                or not isinstance(value["claim_keys"], list)):
            fail("open input is invalid")
        claims = []
        for key in value["claim_keys"]:
            if not board._valid_claim_ref(key):
                fail("open claim key is invalid")
            claim = next((candidate for candidate in payload["claims"]
                          if board._claim_ref(candidate) == key), None)
            if claim is None:
                fail("open claim is stale")
            claims.append(claim)
        actor = _actor_claim(payload, {"claims": value["claim_keys"]}, args.by)
        mutation = board.open_or_join_huddle(
            claim=next(claim for claim in claims if board._claim_ref(claim) == actor),
            overlap=[claim for claim in claims if board._claim_ref(claim) != actor],
            reason=value["reason"], now=now, home=home)
        event.post_commit_mutation(mutation, repo_root=ROOT, home=home)
        out(_mutation_receipt(mutation))
        return
    if args.route == "bid":
        value = stdin_object()
        if set(value) != board._BID_REQUEST_FIELDS or value.get("seat") != args.by:
            fail("bid input is invalid")
        if value.get("expected_huddle_generation") != args.generation:
            fail("bid generation differs from CLI generation")
        mutation = board.submit_huddle_bid(huddle_id=args.id, now=now, home=home, **value)
        event.post_commit_mutation(mutation, repo_root=ROOT, home=home)
        out(board.bid_receipt(args.id, value["claim"], value["round"], home=home))
        return
    huddle = _huddle(payload, args.id)
    _require_settle_cas(payload, huddle, generation=args.generation,
                        board_revision=args.expect_board)
    actor = _actor_claim(payload, huddle, args.by)
    if huddle["state"] == "remote_pending":
        mutation = _recover_remote_pending(payload, huddle, now=now, home=home)
    elif any(bid["round"] == huddle["round"] and bid["role"] == "yield"
             for bid in huddle["bids"]):
        source, _, _ = _pair_from_snapshot(payload, huddle)
        source_full = _current_claims(payload).get(board._claim_key(source))
        if source_full is None:
            raise board.BoardError("remote Huddle source claim changed before begin")
        entity = _source_entity(payload, source_full)
        eligibility, _ = remote.managed_repo_for_plan(Path(entity["plan"]))
        if eligibility is remote.RemoteEligibility.REMOTE:
            mutation = _settle_remote(payload, huddle, actor, now=now, home=home)
        else:
            mutation = board.settle_huddle(
                huddle_id=args.id, expected_generation=args.generation, actor_claim=actor,
                expected_board_revision=args.expect_board, now=now, home=home)
            event.post_commit_mutation(mutation, repo_root=ROOT, home=home)
    else:
        mutation = board.settle_huddle(
            huddle_id=args.id, expected_generation=args.generation, actor_claim=actor,
            expected_board_revision=args.expect_board, now=now, home=home)
        event.post_commit_mutation(mutation, repo_root=ROOT, home=home)
    out(_mutation_receipt(mutation))


if __name__ == "__main__":
    try:
        main()
    except board.BoardError as exc:
        fail(str(exc), 1)
