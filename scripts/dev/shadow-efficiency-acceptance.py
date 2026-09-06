#!/usr/bin/env python3
"""Compare explicit attempt receipts with current canonical source acceptance.

Supplied receipt bytes are not an authenticated actor witness. This command
never grants worker credit, even when they name an accepted source exactly.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import shadow_root_board as board

_spec = importlib.util.spec_from_file_location("efficiency_accept_reader", SCRIPTS / "shadow-accept.py")
accept = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(accept)
MAX_BYTES = 64 * 1024


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate field")
        value[key] = item
    return value


def read_attempt(path):
    path = Path(path).expanduser().absolute()
    if not path.is_file() or any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("symlink input")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized receipt")
    value = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("receipt must be an object")
    return hashlib.sha256(raw).hexdigest(), value


def compare(value, plan_text):
    """Compare one supplied hint; canonical acceptance and actor credit differ."""
    result = {"referenced_root_state": "unknown", "exact_accepted_source_match": None,
              "accepted_worker_contribution": None, "usage_join": None,
              "reason": "receipt_invalid"}
    if value.get("schema") != "shadow.host-attempt.v1":
        return result
    binding = value.get("execution_binding")
    if not isinstance(binding, dict):
        result["reason"] = "execution_binding_missing"
        return result
    claim = binding.get("admitted_claim")
    if not isinstance(claim, dict) or not isinstance(claim.get("row"), str):
        return result
    row = claim["row"]
    if re.fullmatch(r"~[a-z0-9]+", row) is None:
        return result
    try:
        _, _, state, proof, _ = accept.find_row(plan_text, row)
        if state != "completed":
            result.update(referenced_root_state="not_completed", reason="root_not_completed")
            return result
        if not proof.startswith("cmd "):
            result["reason"] = "non_command_acceptance_requires_separate_witness"
            return result
        source, head = accept.local_source_receipt(plan_text, row, accept.proof_argv(proof[4:]))
        result["referenced_root_state"] = "source_accepted"
        repository = binding.get("repository")
        if not isinstance(repository, dict):
            return result
        claimed_source = repository.get("remote_identity")
        result["exact_accepted_source_match"] = (
            isinstance(claimed_source, str)
            and accept.canonical_source_identity(claimed_source) == source
            and binding.get("head_after") == head)
        # Even a byte-for-byte copy of a real receipt is not independent
        # evidence of who executed it. Never infer attribution from equality.
        result["reason"] = ("actor_provenance_unverified" if result["exact_accepted_source_match"]
                            else "source_mismatch")
    except (accept.AcceptError, ValueError, TypeError):
        result["reason"] = "canonical_acceptance_unavailable"
    return result


def audit(paths):
    if not 1 <= len(paths) <= 64:
        raise ValueError("supply 1 to 64 receipt paths")
    results, seen, plan_tokens = [], set(), {}
    state = board.snapshot()
    if state is None:
        raise ValueError("canonical board unavailable")
    revision = state["revision"]
    for path in paths:
        try:
            digest, value = read_attempt(path)
            if digest in seen:
                continue
            seen.add(digest)
            binding = value.get("execution_binding", {})
            claim = binding.get("admitted_claim", {}) if isinstance(binding, dict) else {}
            entity = claim.get("entity") if isinstance(claim, dict) else None
            if not isinstance(entity, str) or re.fullmatch(r"[0-9a-f]{64}", entity) is None:
                raise ValueError("entity hint unavailable")
            plan = board.canonical_plan_by_id_at_revision(entity, revision=revision)
            token = board.plan_state_token(plan)
            result = compare(value, board.read_plan_text(plan))
            if board.plan_state_token(plan) != token or (
                    plan in plan_tokens and plan_tokens[plan] != token):
                raise ValueError("canonical plan moved")
            plan_tokens[plan] = token
            result["receipt_sha256"] = digest
            results.append(result)
        except (ValueError, OSError, board.BoardError):
            # No path, actor, task text, native output or exception payload is
            # printed. One rejected input stays visible, never silently drops.
            results.append({"reason": "input_or_canonical_state_unavailable",
                            "accepted_worker_contribution": None, "usage_join": None})
    final = board.snapshot()
    if final is None or final["revision"] != revision:
        raise ValueError("canonical board moved; rerun the bounded read")
    if any(board.plan_state_token(plan) != token for plan, token in plan_tokens.items()):
        raise ValueError("canonical plan moved; rerun the bounded read")
    return {"schema": "shadow.efficiency-acceptance.v1", "board_revision": revision,
            "receipts": results, "accepted_worker_tasks": None,
            "cost_per_accepted_task": None, "attention_per_accepted_task": None,
            "coverage": "explicit receipt selection; source comparison only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", action="append", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.attempt), indent=2, sort_keys=True))
    except (ValueError, OSError, board.BoardError):
        print(json.dumps({"error": "bounded canonical read unavailable; no attribution made"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
