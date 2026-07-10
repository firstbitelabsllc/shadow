#!/usr/bin/env python3
"""Fail-closed preregistration and scoring helpers for Vidux benchmark v2.

The benchmark is deliberately transport-agnostic. This module freezes fairness,
measurement, pairing, oracle separation, and decision rules before any model run
starts. It does not invoke Claude, Codex, or Vidux itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "benchmarks" / "v2" / "manifest.json"

ARM_IDS = ("vidux_cockpit", "claude_native", "codex_native")
NATIVE_ARMS = ("claude_native", "codex_native")
SCENARIO_IDS = (
    "durable_state",
    "interruption_recovery",
    "cross_project_prioritization",
    "proof_inspection",
)
METRIC_IDS = (
    "success",
    "wall_seconds",
    "tokens",
    "dollars",
    "operator_touches",
    "resume_loss",
)
RECEIPT_IDS = (
    "provider_model",
    "runtime_version",
    "provider_receipt_id",
    "runner_receipt_id",
    "transcript_receipt_id",
)
FIXTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(ValueError):
    """Raised when a preregistration or raw result violates the contract."""


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("manifest root must be an object")
    return payload


def manifest_digest(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _scenario_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios = manifest.get("scenario_classes", [])
    if not isinstance(scenarios, list):
        return {}
    return {
        item.get("id"): item
        for item in scenarios
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Return every static preregistration defect without starting a benchmark."""
    errors: list[str] = []

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if manifest.get("protocol_id") != "vidux-cockpit-v2":
        errors.append("protocol_id must equal vidux-cockpit-v2")

    status = manifest.get("status")
    valid_statuses = {"protocol_frozen_pending_fixture_seal", "ready_for_transport"}
    if status not in valid_statuses:
        errors.append("status must be protocol_frozen_pending_fixture_seal or ready_for_transport")

    policy = manifest.get("amendment_policy")
    if not isinstance(policy, dict):
        errors.append("amendment_policy must be an object")
    else:
        if policy.get("rule_changes_require_new_protocol_id") is not True:
            errors.append("amendment_policy must require a new protocol id for rule changes")
        if policy.get("sealed_fixture_release_must_reference_protocol_digest") is not True:
            errors.append("amendment_policy must require a sealed fixture protocol digest")
        if policy.get("posthoc_threshold_changes_forbidden") is not True:
            errors.append("amendment_policy must forbid posthoc threshold changes")

    arms = manifest.get("arms")
    arm_map: dict[str, dict[str, Any]] = {}
    if not isinstance(arms, list):
        errors.append("arms must be a list")
    else:
        for arm in arms:
            if isinstance(arm, dict) and isinstance(arm.get("id"), str):
                arm_map[arm["id"]] = arm
        if set(arm_map) != set(ARM_IDS) or len(arms) != len(ARM_IDS):
            errors.append("arms must contain exactly vidux_cockpit, claude_native, and codex_native")

    for arm_id in ARM_IDS:
        arm = arm_map.get(arm_id)
        if arm is None:
            continue
        if arm.get("ordinary_filesystem") is not True:
            errors.append(f"{arm_id} must retain ordinary_filesystem access")
        if arm.get("fixture_workspace") != "identical":
            errors.append(f"{arm_id} must use an identical fixture_workspace")
        if arm.get("tool_permission_profile") != "identical":
            errors.append(f"{arm_id} must use an identical tool_permission_profile")

    if arm_map.get("vidux_cockpit", {}).get("additional_surface") != "read_only_cockpit_packet":
        errors.append("vidux_cockpit must add only a read_only_cockpit_packet")
    for arm_id in NATIVE_ARMS:
        if arm_map.get(arm_id, {}).get("additional_surface") != "none":
            errors.append(f"{arm_id} must not receive an additional Vidux surface")

    raw_scenarios = manifest.get("scenario_classes")
    scenarios = _scenario_map(manifest)
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) != len(SCENARIO_IDS) or set(scenarios) != set(SCENARIO_IDS):
        errors.append("scenario_classes must contain the four preregistered scenario ids")

    trial_design = manifest.get("trial_design")
    if not isinstance(trial_design, dict):
        errors.append("trial_design must be an object")
        minimum_pairs = None
    else:
        minimum_pairs = trial_design.get("minimum_complete_pairs_per_class")
        if trial_design.get("paired_by") != ["scenario_class", "fixture_id", "replica"]:
            errors.append("trial_design must pair rows by scenario_class, fixture_id, and replica")
        if trial_design.get("randomize_fixture_order") is not True:
            errors.append("trial_design must randomize fixture order")
        if trial_design.get("randomize_arm_order") is not True:
            errors.append("trial_design must randomize arm order")
        if trial_design.get("infra_exclusion") != (
            "Exclude a paired block only when every arm has the same documented infrastructure failure."
        ):
            errors.append("trial_design must exclude infrastructure only as a complete paired block")
    if not isinstance(minimum_pairs, int) or minimum_pairs < 12:
        errors.append("trial_design minimum_complete_pairs_per_class must be at least 12")

    for scenario_id in SCENARIO_IDS:
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            continue
        if not isinstance(scenario.get("fixture_count_target"), int) or scenario["fixture_count_target"] < 12:
            errors.append(f"{scenario_id} fixture_count_target must be at least 12")
        state = scenario.get("oracle_state")
        if state not in {"pending_seal", "sealed"}:
            errors.append(f"{scenario_id} oracle_state must be pending_seal or sealed")
            continue
        if scenario.get("seal_before_transport") is not True:
            errors.append(f"{scenario_id} must require sealing before transport")
        commitment = scenario.get("oracle_commitment_sha256")
        if state == "sealed" and (not isinstance(commitment, str) or not SHA256_RE.fullmatch(commitment)):
            errors.append(f"{scenario_id} sealed oracle requires a SHA-256 commitment")
        if state == "pending_seal" and commitment is not None:
            errors.append(f"{scenario_id} pending oracle must not expose a commitment before sealing")

    if status == "ready_for_transport" and any(
        scenario.get("oracle_state") != "sealed" for scenario in scenarios.values()
    ):
        errors.append("ready_for_transport requires every hidden oracle to be sealed")
    if status == "protocol_frozen_pending_fixture_seal" and scenarios and all(
        scenario.get("oracle_state") == "sealed" for scenario in scenarios.values()
    ):
        errors.append("sealed fixture set must advance status to ready_for_transport")

    metrics = manifest.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(METRIC_IDS):
        errors.append("metrics must contain exactly success, wall_seconds, tokens, dollars, operator_touches, and resume_loss")
    elif not all(isinstance(metrics[metric], dict) for metric in METRIC_IDS):
        errors.append("every metric definition must be an object")
    else:
        if metrics["success"].get("source") != "sealed_hidden_oracle":
            errors.append("success must be sourced from a sealed_hidden_oracle")
        if metrics["resume_loss"].get("source") != "sealed_hidden_oracle":
            errors.append("resume_loss must be sourced from a sealed_hidden_oracle")

    measurement_contract = manifest.get("measurement_contract")
    expected_measurement_contract = {
        "provider_cost_scope": "Include every provider token and dollar charge attributable to the arm, including cockpit packet generation and routing overhead.",
        "wall_clock_boundary": "Measure from standardized arm launch until a terminal runner receipt.",
        "operator_touch_definition": "Count each human-originated message, approval, click, command, or recovery action after standardized launch; exclude the standardized launch itself.",
        "resume_loss_definition": "The sealed oracle counts missed, repeated, or invented required state transitions; lower is better.",
        "required_receipts": list(RECEIPT_IDS),
    }
    if not isinstance(measurement_contract, dict):
        errors.append("measurement_contract must be an object")
    else:
        for key, value in expected_measurement_contract.items():
            if measurement_contract.get(key) != value:
                errors.append(f"measurement_contract.{key} must equal {value!r}")

    oracles = manifest.get("oracles")
    expected_oracles = {
        "storage": "sealed_external_to_arm_workspace",
        "arm_prompt_visibility": "forbidden",
        "score_after_run_only": True,
        "fixture_release_requires_sha256_commitment": True,
    }
    if not isinstance(oracles, dict):
        errors.append("oracles must be an object")
    else:
        for key, value in expected_oracles.items():
            if oracles.get(key) != value:
                errors.append(f"oracles.{key} must equal {value!r}")

    rules = manifest.get("decision_rules")
    expected_rules = {
        "confidence_level": 0.95,
        "bootstrap_replicates": 5000,
        "success_delta_lower_bound": 0.1,
        "tokens_per_resolved_ratio_upper_bound": 1.15,
        "cost_per_resolved_ratio_upper_bound": 1.15,
        "wall_seconds_ratio_upper_bound": 1.15,
        "operator_touches_delta_upper_bound": 0.0,
        "resume_loss_delta_upper_bound": 0.0,
        "class_win_requires": "win_against_both_native_controls",
        "minimum_verified_net_win_classes": 3,
    }
    if not isinstance(rules, dict):
        errors.append("decision_rules must be an object")
    else:
        for key, value in expected_rules.items():
            if rules.get(key) != value:
                errors.append(f"decision_rules.{key} must equal {value!r}")

    return errors


def transport_readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    """Report whether the frozen protocol may issue a run packet yet."""
    errors = validate_manifest(manifest)
    gates = list(errors)
    scenarios = _scenario_map(manifest)
    for scenario_id in SCENARIO_IDS:
        scenario = scenarios.get(scenario_id)
        if scenario and scenario.get("oracle_state") != "sealed":
            gates.append(f"{scenario_id} hidden oracle is not sealed")
    if manifest.get("status") != "ready_for_transport":
        gates.append("manifest status is not ready_for_transport")
    return {
        "protocol_id": manifest.get("protocol_id"),
        "protocol_digest": manifest_digest(manifest),
        "status": manifest.get("status"),
        "ready": not gates,
        "gates": sorted(set(gates)),
    }


def build_run_packet(
    manifest: dict[str, Any],
    *,
    arm: str,
    scenario_class: str,
    fixture_id: str,
    replica: int,
) -> dict[str, Any]:
    """Emit an arm-safe packet after oracle sealing and static validation."""
    readiness = transport_readiness(manifest)
    if not readiness["ready"]:
        raise ValidationError("benchmark is not transport-ready: " + "; ".join(readiness["gates"]))
    if arm not in ARM_IDS:
        raise ValidationError(f"unknown arm: {arm}")
    if scenario_class not in SCENARIO_IDS:
        raise ValidationError(f"unknown scenario_class: {scenario_class}")
    if not FIXTURE_ID_RE.fullmatch(fixture_id):
        raise ValidationError("fixture_id must be lowercase alphanumeric with optional dashes")
    if not isinstance(replica, int) or replica < 1:
        raise ValidationError("replica must be a positive integer")
    arm_record = next(item for item in manifest["arms"] if item["id"] == arm)
    return {
        "protocol_id": manifest["protocol_id"],
        "protocol_digest": readiness["protocol_digest"],
        "arm": arm,
        "scenario_class": scenario_class,
        "fixture_id": fixture_id,
        "replica": replica,
        "ordinary_filesystem": arm_record["ordinary_filesystem"],
        "fixture_workspace": arm_record["fixture_workspace"],
        "tool_permission_profile": arm_record["tool_permission_profile"],
        "additional_surface": arm_record["additional_surface"],
        "prohibited_surface": "sealed_hidden_oracle",
        "required_metrics": list(METRIC_IDS),
    }


def _require_row_metric(row: dict[str, Any], key: str, *, integer: bool = False) -> str | None:
    value = row.get(key)
    if integer:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return f"{key} must be a non-negative integer"
    elif not _is_number(value) or value < 0:
        return f"{key} must be a non-negative number"
    return None


def validate_result_rows(rows: Iterable[dict[str, Any]], manifest: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, dict[str, Any]]]:
    """Validate paired raw rows and return them grouped by paired-block key."""
    readiness = transport_readiness(manifest)
    if not readiness["ready"]:
        raise ValidationError("cannot validate rows before transport readiness")
    scenarios = _scenario_map(manifest)
    groups: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    errors: list[str] = []

    for index, row in enumerate(rows):
        label = f"row {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be an object")
            continue
        scenario_class = row.get("scenario_class")
        fixture_id = row.get("fixture_id")
        replica = row.get("replica")
        arm = row.get("arm")
        if scenario_class not in SCENARIO_IDS:
            errors.append(f"{label} has unknown scenario_class")
            continue
        if not isinstance(fixture_id, str) or not FIXTURE_ID_RE.fullmatch(fixture_id):
            errors.append(f"{label} has invalid fixture_id")
            continue
        if not isinstance(replica, int) or replica < 1:
            errors.append(f"{label} has invalid replica")
            continue
        if arm not in ARM_IDS:
            errors.append(f"{label} has unknown arm")
            continue
        if row.get("status") not in {"complete", "infra_excluded"}:
            errors.append(f"{label} status must be complete or infra_excluded")
        if row.get("success") not in {0, 1} or isinstance(row.get("success"), bool):
            errors.append(f"{label} success must be 0 or 1")
        for metric, integer in (
            ("wall_seconds", False),
            ("tokens", True),
            ("dollars", False),
            ("operator_touches", True),
            ("resume_loss", False),
        ):
            problem = _require_row_metric(row, metric, integer=integer)
            if problem:
                errors.append(f"{label} {problem}")
        expected_commitment = scenarios[scenario_class].get("oracle_commitment_sha256")
        if row.get("oracle_commitment_sha256") != expected_commitment:
            errors.append(f"{label} oracle commitment does not match sealed scenario commitment")
        if row.get("protocol_digest") != readiness["protocol_digest"]:
            errors.append(f"{label} protocol digest does not match the sealed manifest")
        for receipt_id in RECEIPT_IDS:
            if not isinstance(row.get(receipt_id), str) or not row[receipt_id].strip():
                errors.append(f"{label} {receipt_id} must be a non-empty string")
        key = (scenario_class, fixture_id, replica)
        if arm in groups[key]:
            errors.append(f"{label} duplicates arm {arm} in paired block {key}")
        else:
            groups[key][arm] = row

    for key, block in groups.items():
        missing = sorted(set(ARM_IDS) - set(block))
        if missing:
            errors.append(f"paired block {key} missing arm {', '.join(missing)}")
            continue
        statuses = {row.get("status") for row in block.values()}
        if len(statuses) != 1:
            errors.append(f"paired block {key} must be all complete or all infra_excluded")

    if errors:
        raise ValidationError("; ".join(errors))
    return dict(groups)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValidationError("cannot calculate a percentile of no values")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _bootstrap_interval(
    pairs: list[dict[str, dict[str, Any]]],
    *,
    seed: str,
    replicates: int,
    statistic: Callable[[list[dict[str, dict[str, Any]]]], float | None],
) -> list[float] | None:
    estimate = statistic(pairs)
    if estimate is None:
        return None
    generator = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    samples: list[float] = []
    for _ in range(replicates):
        sample = [pairs[generator.randrange(len(pairs))] for _ in range(len(pairs))]
        value = statistic(sample)
        if value is None:
            return None
        samples.append(value)
    return [_percentile(samples, 0.025), _percentile(samples, 0.975)]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _success_delta(pairs: list[dict[str, dict[str, Any]]], baseline: str) -> float:
    return _mean([pair["vidux_cockpit"]["success"] - pair[baseline]["success"] for pair in pairs])


def _cost_per_resolved_ratio(pairs: list[dict[str, dict[str, Any]]], baseline: str) -> float | None:
    treatment_resolved = sum(pair["vidux_cockpit"]["success"] for pair in pairs)
    baseline_resolved = sum(pair[baseline]["success"] for pair in pairs)
    if treatment_resolved == 0 or baseline_resolved == 0:
        return None
    treatment_cost = sum(pair["vidux_cockpit"]["dollars"] for pair in pairs) / treatment_resolved
    baseline_cost = sum(pair[baseline]["dollars"] for pair in pairs) / baseline_resolved
    if baseline_cost == 0:
        return None
    return treatment_cost / baseline_cost


def _tokens_per_resolved_ratio(pairs: list[dict[str, dict[str, Any]]], baseline: str) -> float | None:
    treatment_resolved = sum(pair["vidux_cockpit"]["success"] for pair in pairs)
    baseline_resolved = sum(pair[baseline]["success"] for pair in pairs)
    if treatment_resolved == 0 or baseline_resolved == 0:
        return None
    treatment_tokens = sum(pair["vidux_cockpit"]["tokens"] for pair in pairs) / treatment_resolved
    baseline_tokens = sum(pair[baseline]["tokens"] for pair in pairs) / baseline_resolved
    if baseline_tokens == 0:
        return None
    return treatment_tokens / baseline_tokens


def _median_ratio(pairs: list[dict[str, dict[str, Any]]], baseline: str, metric: str) -> float | None:
    baseline_value = statistics.median(pair[baseline][metric] for pair in pairs)
    if baseline_value == 0:
        return None
    return statistics.median(pair["vidux_cockpit"][metric] for pair in pairs) / baseline_value


def _mean_delta(pairs: list[dict[str, dict[str, Any]]], baseline: str, metric: str) -> float:
    return _mean([pair["vidux_cockpit"][metric] - pair[baseline][metric] for pair in pairs])


def _metric_with_ci(
    pairs: list[dict[str, dict[str, Any]]],
    *,
    seed: str,
    replicates: int,
    statistic: Callable[[list[dict[str, dict[str, Any]]]], float | None],
) -> dict[str, Any]:
    estimate = statistic(pairs)
    interval = _bootstrap_interval(pairs, seed=seed, replicates=replicates, statistic=statistic)
    return {"estimate": estimate, "ci95": interval}


def _comparison(pairs: list[dict[str, dict[str, Any]]], baseline: str, rules: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    replicates = rules["bootstrap_replicates"]
    metrics = {
        "success_delta": _metric_with_ci(
            pairs,
            seed=f"{scenario_id}:{baseline}:success",
            replicates=replicates,
            statistic=lambda sample: _success_delta(sample, baseline),
        ),
        "tokens_per_resolved_ratio": _metric_with_ci(
            pairs,
            seed=f"{scenario_id}:{baseline}:tokens",
            replicates=replicates,
            statistic=lambda sample: _tokens_per_resolved_ratio(sample, baseline),
        ),
        "cost_per_resolved_ratio": _metric_with_ci(
            pairs,
            seed=f"{scenario_id}:{baseline}:cost",
            replicates=replicates,
            statistic=lambda sample: _cost_per_resolved_ratio(sample, baseline),
        ),
        "wall_seconds_ratio": _metric_with_ci(
            pairs,
            seed=f"{scenario_id}:{baseline}:wall",
            replicates=replicates,
            statistic=lambda sample: _median_ratio(sample, baseline, "wall_seconds"),
        ),
        "operator_touches_delta": _metric_with_ci(
            pairs,
            seed=f"{scenario_id}:{baseline}:touches",
            replicates=replicates,
            statistic=lambda sample: _mean_delta(sample, baseline, "operator_touches"),
        ),
        "resume_loss_delta": _metric_with_ci(
            pairs,
            seed=f"{scenario_id}:{baseline}:resume",
            replicates=replicates,
            statistic=lambda sample: _mean_delta(sample, baseline, "resume_loss"),
        ),
    }
    if any(metric["ci95"] is None for metric in metrics.values()):
        return {"status": "inconclusive", "metrics": metrics}

    win = (
        metrics["success_delta"]["ci95"][0] >= rules["success_delta_lower_bound"]
        and metrics["tokens_per_resolved_ratio"]["ci95"][1] <= rules["tokens_per_resolved_ratio_upper_bound"]
        and metrics["cost_per_resolved_ratio"]["ci95"][1] <= rules["cost_per_resolved_ratio_upper_bound"]
        and metrics["wall_seconds_ratio"]["ci95"][1] <= rules["wall_seconds_ratio_upper_bound"]
        and metrics["operator_touches_delta"]["ci95"][1] <= rules["operator_touches_delta_upper_bound"]
        and metrics["resume_loss_delta"]["ci95"][1] <= rules["resume_loss_delta_upper_bound"]
    )
    if win:
        status = "win"
    elif metrics["success_delta"]["ci95"][1] < 0:
        status = "loss"
    else:
        status = "inconclusive"
    return {"status": status, "metrics": metrics}


def score_result_rows(rows: Iterable[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    """Score raw rows without upgrading absent or incomplete evidence to a win."""
    grouped = validate_result_rows(list(rows), manifest)
    rules = manifest["decision_rules"]
    minimum_pairs = manifest["trial_design"]["minimum_complete_pairs_per_class"]
    scenario_results: dict[str, dict[str, Any]] = {}

    for scenario_id in SCENARIO_IDS:
        pairs = [
            block
            for (block_scenario, _fixture_id, _replica), block in sorted(grouped.items())
            if block_scenario == scenario_id and next(iter(block.values()))["status"] == "complete"
        ]
        if len(pairs) < minimum_pairs:
            scenario_results[scenario_id] = {
                "status": "unproven",
                "complete_pairs": len(pairs),
                "minimum_complete_pairs": minimum_pairs,
                "comparisons": {},
            }
            continue
        comparisons = {
            baseline: _comparison(pairs, baseline, rules, scenario_id)
            for baseline in NATIVE_ARMS
        }
        statuses = {comparison["status"] for comparison in comparisons.values()}
        if statuses == {"win"}:
            status = "win"
        elif "loss" in statuses:
            status = "loss"
        else:
            status = "inconclusive"
        scenario_results[scenario_id] = {
            "status": status,
            "complete_pairs": len(pairs),
            "minimum_complete_pairs": minimum_pairs,
            "comparisons": comparisons,
        }

    verified = [
        scenario_id
        for scenario_id, result in scenario_results.items()
        if result["status"] == "win"
    ]
    target = rules["minimum_verified_net_win_classes"]
    if len(verified) >= target:
        status = "net_value_established"
    elif not grouped:
        status = "unproven"
    else:
        status = "unproven"
    return {
        "protocol_id": manifest["protocol_id"],
        "protocol_digest": manifest_digest(manifest),
        "status": status,
        "verified_net_win_scenario_classes": verified,
        "minimum_verified_net_win_classes": target,
        "scenario_classes": scenario_results,
    }


def _read_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValidationError("results file must be a list or an object with a rows list")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "readiness"):
        command = subparsers.add_parser(name)
        command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    score = subparsers.add_parser("score")
    score.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    score.add_argument("--results", type=Path, required=True)
    packet = subparsers.add_parser("packet")
    packet.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    packet.add_argument("--arm", required=True)
    packet.add_argument("--scenario-class", required=True)
    packet.add_argument("--fixture-id", required=True)
    packet.add_argument("--replica", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        if args.command == "validate":
            errors = validate_manifest(manifest)
            readiness = transport_readiness(manifest)
            print(json.dumps({"valid": not errors, "errors": errors, "transport_ready": readiness["ready"], "gates": readiness["gates"]}, sort_keys=True))
            return 0 if not errors else 1
        if args.command == "readiness":
            readiness = transport_readiness(manifest)
            print(json.dumps(readiness, sort_keys=True))
            return 0 if readiness["ready"] else 2
        if args.command == "score":
            print(json.dumps(score_result_rows(_read_rows(args.results), manifest), sort_keys=True))
            return 0
        print(json.dumps(build_run_packet(manifest, arm=args.arm, scenario_class=args.scenario_class, fixture_id=args.fixture_id, replica=args.replica), sort_keys=True))
        return 0
    except (OSError, ValueError, ValidationError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
