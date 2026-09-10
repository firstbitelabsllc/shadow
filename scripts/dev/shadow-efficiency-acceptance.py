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
import shadow_host_observation as observation

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


def observed_join(start, finish, value, repo):
    """The supplied-file comparator never calls this controller-only gate."""
    binding = value.get("execution_binding", {})
    claim = binding.get("admitted_claim", {}) if isinstance(binding, dict) else {}
    controller = value.get("controller_observation", {})
    policy = value.get("execution_policy", {})
    if not all(isinstance(x, dict) for x in (claim, controller, policy)):
        return False
    return (
        value.get("schema") == "shadow.host-attempt.v1"
        and controller.get("state") == "retained"
        and controller.get("run_id") == start["run_id"]
        and start["worktree_sha256"] == observation.sha(str(repo)) == binding.get("worktree_sha256")
        and start["entity"] == claim.get("entity")
        and start["row"] == claim.get("row")
        and start["claim_revision"] == claim.get("claim_revision")
        and isinstance(claim.get("owner"), str)
        and start["owner_sha256"] == observation.sha(claim["owner"])
        and start["task_sha256"] == binding.get("task_sha256") == value.get("task_sha256")
        and start["host"] == value.get("host")
        and start["work_class"] == policy.get("work_class")
        and finish["status"] == value.get("status")
        and type(value.get("duration_s")) in (int, float)
        and finish["duration_ms"] == round(value["duration_s"] * 1000)
    )


def audit_observed(repos):
    """Read selected controller streams and fresh canonical source acceptance."""
    if not 1 <= len(repos) <= 16:
        raise ValueError("supply 1 to 16 observed repositories")
    state = board.snapshot()
    if state is None:
        raise ValueError("canonical board unavailable")
    revision = state["revision"]
    plans, tokens, streams, rows, attempts = {}, {}, [], {}, []
    selected = set()
    global_runs = set()
    malformed = 0
    for candidate in repos:
        repo = Path(candidate).expanduser().absolute()
        if repo != repo.resolve() or not repo.is_dir():
            raise ValueError("repository is not canonical")
        if repo in selected:
            continue
        selected.add(repo)
        events, errors, log_digest = observation.read_log(repo)
        malformed += errors
        streams.append((repo, log_digest))
        grouped = {}
        for event in events:
            group = grouped.setdefault(event["run_id"], [])
            if event not in group:
                group.append(event)
        files = {}
        for index, path in enumerate((repo / ".shadow/evidence").rglob("*.json")):
            if index >= 256:
                raise ValueError("receipt selection exceeds bound")
            files[observation.sha(path.relative_to(repo).as_posix())] = path
        for run_id, group in grouped.items():
            starts = [x for x in group if x["event"] == "host_start"]
            ends = [x for x in group if x["event"] == "host_finish"]
            item = dict(run_id=run_id, state="unknown", reason="observation_incomplete",
                        accepted_worker_contribution=None, usage_join=None, duration_ms=None)
            attempts.append(item)
            if run_id in global_runs:
                item["reason"] = "replayed_across_streams"
                malformed += 1
                continue
            global_runs.add(run_id)
            if len(starts) != 1:
                item["reason"] = "launch_missing_or_conflicting"
                continue
            start = starts[0]
            key = (start["entity"], start["row"])
            root = rows.setdefault(key, dict(entity=key[0], row=key[1], attempts=0,
                current_state="unknown", observed_contribution=False))
            root["attempts"] += 1
            item.update(entity=key[0], row=key[1], host=start["host"], work_class=start["work_class"])
            if key[0] not in plans:
                plan = board.canonical_plan_by_id_at_revision(key[0], revision=revision)
                token = board.plan_state_token(plan)
                text = board.read_plan_text(plan)
                if board.plan_state_token(plan) != token:
                    raise ValueError("canonical plan moved")
                plans[key[0]], tokens[plan] = text, token
            text = plans[key[0]]
            try:
                root["current_state"] = accept.find_row(text, key[1])[2]
            except accept.AcceptError:
                pass
            if not ends:
                item["state"] = "unfinished"
                continue
            if len(ends) != 1:
                item["reason"] = "terminal_conflicting"
                continue
            finish = ends[0]
            identity = set(observation.COMMON) - {"event", "recorded_at"}
            if any(start[k] != finish[k] for k in identity) or group.index(finish) < group.index(start):
                item["reason"] = "terminal_identity_mismatch"
                continue
            try:
                digest, value = read_attempt(files[finish["receipt_path_sha256"]])
                if digest != finish["receipt_sha256"] or not observed_join(start, finish, value, repo):
                    raise ValueError("receipt mismatch")
            except (KeyError, ValueError, OSError, TypeError, OverflowError):
                item["reason"] = "terminal_receipt_mismatch"
                continue
            item.update(state=finish["status"], duration_ms=finish["duration_ms"], reason="observed_attempt")
            comparison = compare(value, text)
            item["exact_accepted_source_match"] = comparison["exact_accepted_source_match"]
            candidate_credit = (finish["status"] == "ok"
                and value["execution_binding"].get("execution_candidate") is True
                and comparison["exact_accepted_source_match"] is True)
            item["accepted_worker_contribution"] = candidate_credit
            root["observed_contribution"] |= candidate_credit
            usage = value.get("native_usage")
            if isinstance(usage, dict) and usage.get("state") == "known":
                # It is digest-bound to the runner; report only its closed
                # allowlist, never arbitrary receipt or model output fields.
                item["usage_join"] = {k: usage.get(k) for k in observation.unknown_usage()}
    final = board.snapshot()
    if final is None or final["revision"] != revision:
        raise ValueError("canonical board moved")
    if any(board.plan_state_token(p) != token for p, token in tokens.items()):
        raise ValueError("canonical plan moved")
    if any(observation.read_log(repo)[2] != digest for repo, digest in streams):
        raise ValueError("controller stream moved")
    if malformed:
        for item in attempts:
            item.update(accepted_worker_contribution=None, usage_join=None)
        for root in rows.values():
            root["observed_contribution"] = None
    token_fields = ("input_tokens", "cached_input_tokens", "cache_creation_input_tokens",
                    "output_tokens", "reasoning_output_tokens")
    aggregates = {}
    for item in attempts:
        usage = item["usage_join"]
        key = (item.get("work_class", "unknown"), usage["scope"] if usage else "unknown")
        group = aggregates.setdefault(key, dict(work_class=key[0], usage_scope=key[1], attempts=0,
             known_usage_attempts=0, observed_duration_ms=0, known_duration_attempts=0,
             input_tokens=0, cached_input_tokens=0, cache_creation_input_tokens=0,
             output_tokens=0, reasoning_output_tokens=0,
             token_field_coverage={name: 0 for name in token_fields},
             native_cost_usd=0, known_cost_attempts=0))
        group["attempts"] += 1
        if item["duration_ms"] is not None:
            group["observed_duration_ms"] += item["duration_ms"]
            group["known_duration_attempts"] += 1
        if usage:
            group["known_usage_attempts"] += 1
            for name in token_fields:
                value = usage[name]
                if value is not None:
                    group[name] += value
                    group["token_field_coverage"][name] += 1
            if usage["native_cost_usd"] is not None:
                group["native_cost_usd"] += usage["native_cost_usd"]
                group["known_cost_attempts"] += 1
    for group in aggregates.values():
        for name in token_fields:
            if not group["token_field_coverage"][name]:
                group[name] = None
        if not group["known_cost_attempts"]:
            group["native_cost_usd"] = None
        if not group["known_duration_attempts"]:
            group["observed_duration_ms"] = None
    return dict(schema="shadow.delegation-observation.v1", board_revision=revision,
        coverage="selected controller streams; pre-admission refusals, lead work and unobserved work excluded",
        trust_boundary="cooperative local controller and storage; no cryptographic provider identity",
        malformed_records=malformed, observed_attempts=len(attempts), known_roots=len(rows),
        accepted_worker_tasks=None if malformed else sum(r["observed_contribution"] for r in rows.values()),
        failed_attempts=sum(x["state"] in {"failed", "blocked"} for x in attempts),
        unfinished_attempts=sum(x["state"] == "unfinished" for x in attempts),
        unknown_attempts=sum(x["state"] == "unknown" for x in attempts),
        roots=list(rows.values()), attempts=attempts, resource_totals=list(aggregates.values()),
        worker_execution_share=None, cost_per_accepted_task=None, attention_per_accepted_task=None,
        comparative_benefit="NOT COMPARABLE; lead/review coverage and controlled comparison required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--attempt", action="append", type=Path)
    selection.add_argument("--observed-repo", action="append", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit_observed(args.observed_repo) if args.observed_repo else audit(args.attempt), indent=2, sort_keys=True))
    except (ValueError, OSError, board.BoardError):
        print(json.dumps({"error": "bounded canonical read unavailable; no attribution made"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
