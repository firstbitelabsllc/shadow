#!/usr/bin/env python3
"""Historical deterministic tools for the retired Vidux benchmark v3.

The frozen library functions remain inspectable for negative-artifact tests.
The CLI validates the administrative disposition and refuses every operation
that could issue artifacts, mutate a journal, adjudicate rows, or emit a claim.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from fractions import Fraction
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "benchmarks" / "v3" / "manifest.json"
DEFAULT_STATUS = ROOT / "benchmarks" / "v3" / "STATUS.json"

PROTOCOL_ID = "vidux-cockpit-v3"
PAIR_IDS = ("anthropic_claude", "openai_codex")
ARM_IDS = ("claude_native", "claude_vidux", "codex_native", "codex_vidux")
SCENARIO_IDS = (
    "durable_state",
    "interruption_recovery",
    "cross_project_prioritization",
    "proof_inspection",
)
METRIC_IDS = ("elapsed_ms", "tokens", "cost_microusd", "operator_touches")
DECISION_METRIC_IDS = (
    "success_delta_basis_points",
    "tokens_per_resolved_ratio_basis_points",
    "cost_per_resolved_ratio_basis_points",
    "elapsed_ratio_basis_points",
    "operator_touches_delta_basis_points",
    "resume_loss_delta_basis_points",
)
RECEIPT_DIGEST_IDS = (
    "provider_receipt_sha256",
    "runner_receipt_sha256",
    "transcript_receipt_sha256",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
FIXTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
RUN_ID_RE = re.compile(r"^run-[0-9a-f]{20}$")

MANIFEST_KEYS = {
    "schema_version",
    "protocol_id",
    "status",
    "frozen_at",
    "amendment_policy",
    "content_addressing",
    "provider_pairs",
    "arms",
    "scenario_classes",
    "release_contract",
    "schedule_contract",
    "attempt_journal",
    "budgets",
    "measurement_contract",
    "adjudication_contract",
    "exclusion_policy",
    "decision_procedure",
    "decision_rules",
}
STATUS_KEYS = {
    "schema_version",
    "protocol_id",
    "status",
    "runnable",
    "protocol_digest",
    "decided_at",
    "replacement_protocol_id",
    "decision_basis",
    "next_protocol_requirements",
}
NON_RUNNABLE_GATE = (
    "benchmark v3 is retired and non-runnable; integrity and recovery corrections require protocol v4"
)
RELEASE_KEYS = {
    "schema_version",
    "release_id",
    "protocol_id",
    "protocol_digest",
    "randomization_seed",
    "evaluator_receipt_sha256",
    "provider_profiles",
    "fixtures",
}
PROFILE_KEYS = {
    "pair_id",
    "provider",
    "requested_model_id",
    "resolved_model_id",
    "provider_api_surface",
    "inference_profile_sha256",
    "runner_family",
    "runtime_version",
    "runner_binary_sha256",
    "runner_args_sha256",
    "permission_profile_sha256",
    "tool_surface_sha256",
    "base_prompt_sha256",
    "system_instructions_sha256",
    "developer_instructions_sha256",
    "workspace_snapshot_sha256",
}
FIXTURE_KEYS = {"stage", "scenario_class", "fixture_id", "fixture_path", "fixture_sha256"}
SCHEDULE_KEYS = {
    "schema_version",
    "protocol_id",
    "protocol_digest",
    "release_id",
    "release_digest",
    "schedule_seed_digest",
    "stage_budgets",
    "protocol_budget",
    "max_infra_attempts",
    "runs",
}
RUN_KEYS = {
    "run_id",
    "sequence",
    "stage",
    "scenario_class",
    "fixture_id",
    "replica",
    "arm",
    "pair_id",
    "mode",
    "intervention",
    "provider_profile_digest",
    "budget",
}
RESULT_KEYS = {
    "schema_version",
    "schedule_digest",
    "run_id",
    "attempt_id",
    "status",
    "metrics",
    *RECEIPT_DIGEST_IDS,
}
EVALUATOR_RESULT_KEYS = {
    "schema_version",
    "protocol_id",
    "run_id",
    "fixture_id",
    "runner_result_sha256",
    "evaluator_run_sha256",
    "checks",
    "resume_transitions",
    "forbidden_action",
}
ADJUDICATION_KEYS = {
    "schema_version",
    "protocol_id",
    "protocol_digest",
    "schedule_digest",
    "run_id",
    "attempt_id",
    "stage",
    "scenario_class",
    "fixture_id",
    "arm",
    "pair_id",
    "runner_result_sha256",
    "evaluator_result_sha256",
    "success",
    "resume_loss",
    "terminal_outcome",
    "metrics",
}
ADJUDICATION_BUNDLE_KEYS = {
    "schema_version",
    "schedule_digest",
    "stage",
    "adjudications",
}
CHECK_KEYS = {"id", "required", "passed", "evidence_sha256"}
RESUME_KEYS = {"missed", "repeated", "invented"}
JOURNAL_REQUEST_KEYS = {"operation_id", "event", "run_id", "attempt_id", "payload"}
JOURNAL_EVENTS = {
    "attempt_claimed",
    "attempt_started",
    "runner_completed",
    "attempt_failed",
    "infra_retryable",
    "adjudicated",
}
PUBLIC_JOURNAL_EVENTS = JOURNAL_EVENTS - {"adjudicated"}
JOURNAL_HEADER_KEYS = {
    "schema_version",
    "sequence",
    "operation_id",
    "event",
    "schedule_digest",
    "payload",
    "previous_event_sha256",
    "event_sha256",
}
JOURNAL_EVENT_KEYS = {
    "schema_version",
    "sequence",
    "operation_id",
    "event",
    "run_id",
    "attempt_id",
    "payload",
    "previous_event_sha256",
    "event_sha256",
}
USAGE_EVENTS = {"runner_completed", "attempt_failed", "infra_retryable"}
ACTIVE_STATES = {"claimed", "started"}
RUNNER_TERMINAL_STATES = {
    "runner_completed",
    "runner_failed",
    "budget_exhausted",
    "infrastructure_exhausted",
}


class ValidationError(ValueError):
    """Raised when a benchmark artifact violates the frozen contract."""


MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_JOURNAL_BYTES = 64 * 1024 * 1024


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValidationError(f"value is not canonical JSON: {error}") from error


def digest_json(value: Any, domain: str = "json") -> str:
    prefix = f"vidux-v3:{domain}\0".encode("ascii")
    return hashlib.sha256(prefix + canonical_bytes(value)).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(text: str, *, label: str = "JSON") -> Any:
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ValidationError(f"{label} is invalid JSON: {error}") from error
    except RecursionError as error:
        raise ValidationError(f"{label} exceeds the maximum JSON nesting depth") from error
    if _json_depth(payload) > 64:
        raise ValidationError(f"{label} exceeds the maximum JSON nesting depth")
    return payload


def _json_depth(value: Any) -> int:
    maximum = 0
    pending: list[tuple[Any, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if isinstance(current, dict):
            depth += 1
            pending.extend((item, depth) for item in current.values())
        elif isinstance(current, list):
            depth += 1
            pending.extend((item, depth) for item in current)
        maximum = max(maximum, depth)
        if maximum > 64:
            return maximum
    return maximum


def load_json(path: Path) -> dict[str, Any]:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise ValidationError(f"{path} is unavailable: {error}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError(f"{path} must be a single-link regular file")
        if info.st_size > MAX_JSON_BYTES:
            raise ValidationError(f"{path} exceeds the {MAX_JSON_BYTES}-byte JSON limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_JSON_BYTES:
                raise ValidationError(f"{path} exceeds the {MAX_JSON_BYTES}-byte JSON limit")
            chunks.append(chunk)
    finally:
        os.close(fd)
    try:
        text = b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{path} must be UTF-8 JSON") from error
    payload = strict_json_loads(text, label=str(path))
    if not isinstance(payload, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    return payload


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _safe_relative_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValidationError(f"{label} must be a non-empty forward-slash relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(f"{label} must be a normalized relative path")
    return path


@contextlib.contextmanager
def _open_relative_regular(
    root: Path, relative_path: Any, label: str
) -> Iterator[int]:
    """Open a single-link file without following any path component."""
    relative = _safe_relative_path(relative_path, label)
    if root.is_symlink():
        raise ValidationError(f"{label} root must not be a symlink")
    try:
        root_path = root.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"{label} root is unavailable: {error}") from error
    if not root_path.is_dir():
        raise ValidationError(f"{label} root must be a directory")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        current_fd = os.open(root_path, directory_flags)
    except OSError as error:
        raise ValidationError(f"{label} root cannot be opened safely: {error}") from error
    opened_directories = [current_fd]
    file_fd: int | None = None
    try:
        for part in relative.parts[:-1]:
            try:
                current_fd = os.open(part, directory_flags, dir_fd=current_fd)
            except OSError as error:
                raise ValidationError(f"{label} traverses an unsafe directory: {error}") from error
            opened_directories.append(current_fd)
        try:
            file_fd = os.open(
                relative.parts[-1],
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current_fd,
            )
        except OSError as error:
            raise ValidationError(f"{label} cannot be opened safely: {error}") from error
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError(f"{label} must be a single-link regular file")
        yield file_fd
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for fd in reversed(opened_directories):
            os.close(fd)


def _sha256_open_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _map_by_id(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    return {
        row["id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(manifest) != MANIFEST_KEYS:
        errors.append("manifest must contain exactly the frozen top-level fields")
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if manifest.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"protocol_id must equal {PROTOCOL_ID}")
    if manifest.get("status") != "protocol_frozen_pending_evaluator_release":
        errors.append("manifest status must remain protocol_frozen_pending_evaluator_release")
    if not isinstance(manifest.get("frozen_at"), str) or not manifest.get("frozen_at"):
        errors.append("frozen_at must be a non-empty string")

    amendment = manifest.get("amendment_policy")
    expected_amendment = {
        "rule_changes_require_new_protocol_id": True,
        "posthoc_threshold_changes_forbidden": True,
        "released_fixture_bytes_are_immutable": True,
        "provider_transport_requires_separate_review": True,
    }
    if amendment != expected_amendment:
        errors.append("amendment_policy must equal the frozen fail-closed policy")

    if manifest.get("content_addressing") != {
        "canonicalization": "utf8_sorted_key_compact_json_v1",
        "hash": "sha256",
        "domain_prefix": "vidux-v3",
        "duplicate_key_policy": "reject",
        "non_finite_number_policy": "reject",
    }:
        errors.append("content_addressing must equal the frozen strict JSON policy")

    pairs = _map_by_id(manifest.get("provider_pairs"))
    raw_pairs = manifest.get("provider_pairs")
    if set(pairs) != set(PAIR_IDS) or not isinstance(raw_pairs, list) or len(raw_pairs) != 2:
        errors.append("provider_pairs must contain exactly anthropic_claude and openai_codex")
    expected_pairs = {
        "anthropic_claude": ("anthropic", "claude_code", "claude_native", "claude_vidux"),
        "openai_codex": ("openai", "codex", "codex_native", "codex_vidux"),
    }
    for pair_id, (provider, runner, native, vidux) in expected_pairs.items():
        pair = pairs.get(pair_id)
        if pair is None:
            continue
        if set(pair) != {
            "id", "provider", "runner_family", "native_arm", "vidux_arm", "profile_binding"
        }:
            errors.append(f"{pair_id} must contain exactly the provider-pair fields")
        if (
            pair.get("provider"),
            pair.get("runner_family"),
            pair.get("native_arm"),
            pair.get("vidux_arm"),
        ) != (provider, runner, native, vidux):
            errors.append(f"{pair_id} provider and arm binding must remain frozen")
        if pair.get("profile_binding") != "release_exact":
            errors.append(f"{pair_id} must use release_exact profile binding")

    arms = _map_by_id(manifest.get("arms"))
    raw_arms = manifest.get("arms")
    if set(arms) != set(ARM_IDS) or not isinstance(raw_arms, list) or len(raw_arms) != 4:
        errors.append("arms must contain exactly the four provider-matched controls")
    expected_arms = {
        "claude_native": ("anthropic_claude", "native", "none"),
        "claude_vidux": ("anthropic_claude", "vidux", "read_only_vidux_packet"),
        "codex_native": ("openai_codex", "native", "none"),
        "codex_vidux": ("openai_codex", "vidux", "read_only_vidux_packet"),
    }
    for arm_id, expected in expected_arms.items():
        arm = arms.get(arm_id)
        if arm is None:
            continue
        if set(arm) != {"id", "pair_id", "mode", "intervention"}:
            errors.append(f"{arm_id} must contain exactly the arm fields")
        if (arm.get("pair_id"), arm.get("mode"), arm.get("intervention")) != expected:
            errors.append(f"{arm_id} binding must remain provider-matched and frozen")

    scenarios = _map_by_id(manifest.get("scenario_classes"))
    raw_scenarios = manifest.get("scenario_classes")
    if (
        set(scenarios) != set(SCENARIO_IDS)
        or not isinstance(raw_scenarios, list)
        or len(raw_scenarios) != 4
    ):
        errors.append("scenario_classes must contain exactly the four frozen classes")
    for scenario_id in SCENARIO_IDS:
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            continue
        if set(scenario) != {"id", "pilot_fixture_count", "full_fixture_count"}:
            errors.append(f"{scenario_id} must contain exactly the scenario count fields")
        if scenario.get("pilot_fixture_count") != 1 or scenario.get("full_fixture_count") != 12:
            errors.append(f"{scenario_id} must freeze pilot=1 and full=12 fixtures")

    release_contract = manifest.get("release_contract")
    if not isinstance(release_contract, dict):
        errors.append("release_contract must be an object")
    else:
        if release_contract.get("stages") != ["pilot", "full"]:
            errors.append("release_contract stages must equal pilot and full")
        if set(release_contract.get("provider_profile_fields", [])) != PROFILE_KEYS:
            errors.append("release_contract provider_profile_fields must match the public schema")
        if set(release_contract.get("fixture_fields", [])) != FIXTURE_KEYS:
            errors.append("release_contract fixture_fields must match the public schema")
        if release_contract.get("hidden_evaluator_material") != (
            "external_to_public_release_and_arm_packets"
        ):
            errors.append("release_contract must keep hidden evaluator material external")

    if manifest.get("schedule_contract") != {
        "replicas_per_fixture": 1,
        "complete_cartesian_product": True,
        "ordering": "sha256_seeded_canonical_run_key",
        "run_ids": "opaque_sha256_prefix",
        "all_arms_required": True,
        "workspace_isolation": "fresh_copy_per_run",
    }:
        errors.append("schedule_contract must equal the deterministic complete schedule policy")

    if manifest.get("attempt_journal") != {
        "format": "canonical_jsonl_hash_chain_v1",
        "logical_key_fields": ["run_id", "attempt_number"],
        "durability": "fcntl_lock_o_append_fsync",
        "locking": "single_link_no_follow_sidecar_flock",
        "torn_tail_policy": "reject",
        "hash": "sha256",
        "operation_replay": "same_intent_idempotent_different_intent_rejected",
        "dispatch_policy": (
            "provider_transport_disabled_until_dispatch_reconciliation_is_implemented"
        ),
    }:
        errors.append("attempt_journal must equal the frozen durable replay policy")

    budgets = manifest.get("budgets")
    if not isinstance(budgets, dict) or set(budgets) != {"pilot", "full", "protocol"}:
        errors.append("budgets must contain exactly pilot, full, and protocol")
    else:
        expected_runs = {"pilot": 16, "full": 192}
        for scope in ("pilot", "full"):
            block = budgets.get(scope)
            if not isinstance(block, dict) or set(block) != {
                "per_run", "global", "max_infra_attempts"
            }:
                errors.append(f"{scope} budget must contain per_run, global, max_infra_attempts")
                continue
            if block.get("max_infra_attempts") != 2:
                errors.append(f"{scope} max_infra_attempts must equal 2")
            per_run = block.get("per_run")
            global_budget = block.get("global")
            if not isinstance(per_run, dict) or set(per_run) != set(METRIC_IDS):
                errors.append(f"{scope} per_run budget must contain exactly all metrics")
                continue
            if not isinstance(global_budget, dict) or set(global_budget) != set(METRIC_IDS):
                errors.append(f"{scope} global budget must contain exactly all metrics")
                continue
            for metric in METRIC_IDS:
                per_value = per_run.get(metric)
                global_value = global_budget.get(metric)
                if not isinstance(per_value, int) or isinstance(per_value, bool) or per_value < 0:
                    errors.append(f"{scope} per_run {metric} must be a non-negative integer")
                if (
                    not isinstance(global_value, int)
                    or isinstance(global_value, bool)
                    or global_value < 0
                ):
                    errors.append(f"{scope} global {metric} must be a non-negative integer")
                if isinstance(per_value, int) and isinstance(global_value, int):
                    if global_value != per_value * expected_runs[scope]:
                        errors.append(
                            f"{scope} global {metric} must equal the complete schedule ceiling"
                        )
        protocol_budget = budgets.get("protocol")
        if not isinstance(protocol_budget, dict) or set(protocol_budget) != set(METRIC_IDS):
            errors.append("protocol budget must contain exactly all metrics")
        else:
            for metric in METRIC_IDS:
                expected = sum(budgets[scope]["global"][metric] for scope in ("pilot", "full"))
                value = protocol_budget.get(metric)
                if value != expected:
                    errors.append(f"protocol {metric} must equal pilot plus full ceilings")

    expected_measurement = {
        "activation_overhead": (
            "Include every token, cost_microusd, and elapsed_ms used to produce or consume "
            "the Vidux packet."
        ),
        "wall_boundary": (
            "Start before Vidux packet generation or the matched native no-op; stop at the "
            "terminal runner receipt."
        ),
        "operator_touch_definition": (
            "Every human-originated message, approval, click, command, or recovery action "
            "after standardized launch."
        ),
        "token_counting": (
            "Provider-billed input, output, reasoning, and cache token units from the provider "
            "receipt."
        ),
        "cost_counting": (
            "Provider charge converted once to integer micro-USD from the provider receipt."
        ),
        "retry_counting": (
            "All attempt usage is cumulative within the logical run ceiling and stage/protocol "
            "totals."
        ),
        "required_receipt_digests": list(RECEIPT_DIGEST_IDS),
    }
    if manifest.get("measurement_contract") != expected_measurement:
        errors.append("measurement_contract must equal the frozen accounting policy")

    adjudication = manifest.get("adjudication_contract")
    if not isinstance(adjudication, dict):
        errors.append("adjudication_contract must be an object")
    else:
        expected = {
            "input": "post_run_evaluator_result_bound_to_runner_result",
            "required_check_policy": "all_required_checks_pass",
            "forbidden_action_forces_failure": True,
            "runner_failure_forces_failure": True,
            "resume_loss_formula": "missed_plus_repeated_plus_invented_state_transitions",
            "oracle_commitment_in_arm_packet": "forbidden",
        }
        if adjudication != expected:
            errors.append("adjudication_contract must equal the frozen deterministic policy")

    expected_exclusion_policy = {
        "post_release_run_or_block_exclusion": "forbidden",
        "fixture_replacement": "forbidden",
        "runner_failure": "scored_zero_success",
        "budget_exhaustion": "scored_zero_success",
        "infrastructure_attempts_exhausted": "scored_zero_success",
        "evaluator_defect": "protocol_inconclusive_requires_new_protocol_id",
        "arm_label_unblinding_gate": (
            "not_applicable_because_exclusions_are_forbidden"
        ),
    }
    if manifest.get("exclusion_policy") != expected_exclusion_policy:
        errors.append("exclusion_policy must forbid all post-release exclusions")

    expected_decision_procedure = {
        "input": "complete_stage_adjudication_receipts_bound_to_attempt_journal",
        "analysis_unit": "provider_pair_scenario_fixture_pair",
        "resampling": "paired_sha256_index_bootstrap_with_replacement",
        "bootstrap_seed_domain": (
            "protocol_release_stage_pair_scenario_replicate_draw"
        ),
        "bootstrap_replicates": 5000,
        "confidence_interval": (
            "two_sided_percentile_nearest_rank_250_9750_basis_points"
        ),
        "multiplicity_adjustment": "none_preregistered_joint_all_metrics_gate",
        "statistics": {
            "success_delta_basis_points": "10000_mean_vidux_minus_native",
            "tokens_per_resolved_ratio_basis_points": (
                "10000_ratio_of_total_tokens_per_success"
            ),
            "cost_per_resolved_ratio_basis_points": (
                "10000_ratio_of_total_cost_microusd_per_success"
            ),
            "elapsed_ratio_basis_points": "10000_ratio_of_total_elapsed_ms",
            "operator_touches_delta_basis_points": "10000_mean_vidux_minus_native",
            "resume_loss_delta_basis_points": "10000_mean_vidux_minus_native",
        },
        "undefined_ratio_policy": "provider_pair_non_win",
        "bootstrap_zero_denominator_sample": "positive_infinity",
        "terminal_failure_policy": "success_zero_metrics_and_resume_loss_retained",
        "provider_pair_win": "all_interval_thresholds_pass",
        "class_win": "all_provider_pairs_win",
        "pilot_policy": "directional_only_never_claim_eligible",
        "full_claim_requires": "complete_192_run_stage",
    }
    if manifest.get("decision_procedure") != expected_decision_procedure:
        errors.append("decision_procedure must equal the frozen deterministic procedure")

    rules = manifest.get("decision_rules")
    if not isinstance(rules, dict):
        errors.append("decision_rules must be an object")
    else:
        frozen_values = {
            "confidence_basis_points": 9500,
            "bootstrap_replicates": 5000,
            "pilot_is_directional_only": True,
            "minimum_complete_pairs_per_provider_class": 12,
            "success_delta_lower_bound_basis_points": 1000,
            "tokens_per_resolved_ratio_upper_bound_basis_points": 11500,
            "cost_per_resolved_ratio_upper_bound_basis_points": 11500,
            "elapsed_ratio_upper_bound_basis_points": 11500,
            "operator_touches_delta_upper_bound": 0,
            "resume_loss_delta_upper_bound": 0,
            "class_win_requires": "all_provider_pairs_win",
            "minimum_verified_net_win_classes": 3,
        }
        if rules != frozen_values:
            errors.append("decision_rules must equal the frozen threshold set")
        elif rules["bootstrap_replicates"] != expected_decision_procedure[
            "bootstrap_replicates"
        ]:
            errors.append("decision_rules bootstrap count must match decision_procedure")
    return errors


def validate_status(status: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(status) != STATUS_KEYS:
        errors.append("status must contain exactly the registered fields")
    if status.get("schema_version") != 1:
        errors.append("status schema_version must equal 1")
    if status.get("protocol_id") != manifest.get("protocol_id"):
        errors.append("status protocol_id must match the frozen manifest")
    if status.get("status") != "retired_non_runnable":
        errors.append("status must remain retired_non_runnable")
    if status.get("runnable") is not False:
        errors.append("status runnable must remain false")
    if status.get("protocol_digest") != digest_json(manifest, "protocol"):
        errors.append("status protocol_digest must bind the frozen manifest")
    if status.get("replacement_protocol_id") != "vidux-cockpit-v4":
        errors.append("replacement protocol id must equal vidux-cockpit-v4")
    if not isinstance(status.get("decided_at"), str) or not status.get("decided_at", "").strip():
        errors.append("status decided_at must be a non-empty string")
    for key in ("decision_basis", "next_protocol_requirements"):
        value = status.get(key)
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            errors.append(f"status {key} must be a non-empty string list")
    return errors


def require_protocol_runnable(status: dict[str, Any], manifest: dict[str, Any]) -> None:
    errors = validate_status(status, manifest)
    if errors:
        raise ValidationError("protocol status is invalid: " + "; ".join(errors))
    if status.get("runnable") is not True:
        raise ValidationError(NON_RUNNABLE_GATE)


def _contains_private_evaluator_key(value: Any) -> bool:
    forbidden_tokens = ("oracle", "hidden", "adjudicat")
    if isinstance(value, dict):
        return any(
            any(token in str(key).lower() for token in forbidden_tokens)
            or _contains_private_evaluator_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_private_evaluator_key(item) for item in value)
    return False


def validate_release(release: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(release) != RELEASE_KEYS:
        errors.append("release must contain exactly the public release fields")
    if _contains_private_evaluator_key(release):
        errors.append("public release must not contain hidden evaluator or adjudication fields")
    if release.get("schema_version") != 1:
        errors.append("release schema_version must equal 1")
    if release.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"release protocol_id must equal {PROTOCOL_ID}")
    if release.get("protocol_digest") != digest_json(manifest, "protocol"):
        errors.append("release protocol_digest must bind the frozen manifest")
    release_id = release.get("release_id")
    if not isinstance(release_id, str) or ID_RE.fullmatch(release_id) is None:
        errors.append("release_id must be a normalized opaque id")
    if not _valid_sha(release.get("randomization_seed")):
        errors.append("randomization_seed must be a lowercase SHA-256-sized value")
    if not _valid_sha(release.get("evaluator_receipt_sha256")):
        errors.append("evaluator_receipt_sha256 must be a lowercase SHA-256")

    pairs = _map_by_id(manifest.get("provider_pairs"))
    profiles = release.get("provider_profiles")
    profile_map: dict[str, dict[str, Any]] = {}
    if not isinstance(profiles, list):
        errors.append("provider_profiles must be a list")
    else:
        for profile in profiles:
            if not isinstance(profile, dict) or set(profile) != PROFILE_KEYS:
                errors.append("each provider profile must contain exactly the public profile fields")
                continue
            pair_id = profile.get("pair_id")
            if not isinstance(pair_id, str) or pair_id in profile_map:
                errors.append("provider profile pair_id values must be unique strings")
                continue
            profile_map[pair_id] = profile
            pair = pairs.get(pair_id, {})
            if profile.get("provider") != pair.get("provider"):
                errors.append(f"{pair_id} provider must match the frozen pair")
            if profile.get("runner_family") != pair.get("runner_family"):
                errors.append(f"{pair_id} runner_family must match the frozen pair")
            for key in (
                "requested_model_id",
                "resolved_model_id",
                "provider_api_surface",
                "runtime_version",
            ):
                if not isinstance(profile.get(key), str) or not profile.get(key, "").strip():
                    errors.append(f"{pair_id} {key} must be a non-empty string")
            for key in (
                "inference_profile_sha256",
                "runner_binary_sha256",
                "runner_args_sha256",
                "permission_profile_sha256",
                "tool_surface_sha256",
                "base_prompt_sha256",
                "system_instructions_sha256",
                "developer_instructions_sha256",
                "workspace_snapshot_sha256",
            ):
                if not _valid_sha(profile.get(key)):
                    errors.append(f"{pair_id} {key} must be a lowercase SHA-256")
    if set(profile_map) != set(PAIR_IDS) or len(profile_map) != 2:
        errors.append("provider_profiles must contain exactly one profile per matched pair")

    fixtures = release.get("fixtures")
    seen: set[tuple[str, str, str]] = set()
    seen_fixture_ids: set[str] = set()
    seen_fixture_digests: dict[str, str] = {}
    counts = {
        stage: {scenario_id: 0 for scenario_id in SCENARIO_IDS}
        for stage in ("pilot", "full")
    }
    if not isinstance(fixtures, list):
        errors.append("fixtures must be a list")
    else:
        for fixture in fixtures:
            if not isinstance(fixture, dict) or set(fixture) != FIXTURE_KEYS:
                errors.append("each fixture must contain exactly the public fixture fields")
                continue
            scenario = fixture.get("scenario_class")
            stage = fixture.get("stage")
            fixture_id = fixture.get("fixture_id")
            if stage not in counts:
                errors.append(f"unknown fixture stage: {stage!r}")
            elif scenario not in counts[stage]:
                errors.append(f"unknown fixture scenario_class: {scenario!r}")
            else:
                counts[stage][scenario] += 1
            if not isinstance(fixture_id, str) or FIXTURE_ID_RE.fullmatch(fixture_id) is None:
                errors.append("fixture_id must be a normalized kebab-case id")
            elif (str(stage), str(scenario), fixture_id) in seen:
                errors.append(f"duplicate fixture identity: {stage}/{scenario}/{fixture_id}")
            else:
                seen.add((str(stage), str(scenario), fixture_id))
                if fixture_id in seen_fixture_ids:
                    errors.append(f"fixture_id must be disjoint across stages: {fixture_id}")
                seen_fixture_ids.add(fixture_id)
            try:
                _safe_relative_path(fixture.get("fixture_path"), "fixture_path")
            except ValidationError as error:
                errors.append(str(error))
            if not _valid_sha(fixture.get("fixture_sha256")):
                errors.append(
                    f"{stage}/{scenario}/{fixture_id} fixture_sha256 must be lowercase SHA-256"
                )
            elif fixture["fixture_sha256"] in seen_fixture_digests:
                errors.append(
                    "fixture bytes must be disjoint across stages: "
                    f"{fixture_id} matches {seen_fixture_digests[fixture['fixture_sha256']]}"
                )
            else:
                seen_fixture_digests[fixture["fixture_sha256"]] = str(fixture_id)
    scenarios = _map_by_id(manifest.get("scenario_classes"))
    for stage in ("pilot", "full"):
        field = f"{stage}_fixture_count"
        for scenario_id in SCENARIO_IDS:
            expected = scenarios.get(scenario_id, {}).get(field)
            if counts[stage][scenario_id] != expected:
                errors.append(
                    f"release requires exactly {expected} {stage} {scenario_id} fixtures"
                )
    return errors


def validate_release_files(release: dict[str, Any], fixture_root: Path) -> list[str]:
    errors: list[str] = []
    fixtures = release.get("fixtures")
    if not isinstance(fixtures, list):
        return ["fixtures must be a list before file validation"]
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        label = f"fixture {fixture.get('scenario_class')}/{fixture.get('fixture_id')}"
        try:
            with _open_relative_regular(
                fixture_root, fixture.get("fixture_path"), label
            ) as file_fd:
                actual_digest = _sha256_open_fd(file_fd)
        except ValidationError as error:
            errors.append(str(error))
            continue
        if actual_digest != fixture.get("fixture_sha256"):
            errors.append(f"{label} SHA-256 does not match the release")
    return errors


def _profile_map(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles = release.get("provider_profiles", [])
    return {
        profile["pair_id"]: profile
        for profile in profiles
        if isinstance(profile, dict) and isinstance(profile.get("pair_id"), str)
    }


def _fixture_map(
    release: dict[str, Any]
) -> dict[tuple[str, str, str], dict[str, Any]]:
    fixtures = release.get("fixtures", [])
    return {
        (fixture["stage"], fixture["scenario_class"], fixture["fixture_id"]): fixture
        for fixture in fixtures
        if isinstance(fixture, dict)
        and isinstance(fixture.get("stage"), str)
        and isinstance(fixture.get("scenario_class"), str)
        and isinstance(fixture.get("fixture_id"), str)
    }


def normalized_release(release: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize evaluator list ordering before content addressing."""
    normalized = dict(release)
    normalized["provider_profiles"] = sorted(
        (dict(profile) for profile in release.get("provider_profiles", [])),
        key=lambda profile: str(profile.get("pair_id", "")),
    )
    normalized["fixtures"] = sorted(
        (dict(fixture) for fixture in release.get("fixtures", [])),
        key=lambda fixture: (
            0 if fixture.get("stage") == "pilot" else 1,
            str(fixture.get("scenario_class", "")),
            str(fixture.get("fixture_id", "")),
        ),
    )
    return normalized


def build_schedule(
    manifest: dict[str, Any],
    release: dict[str, Any],
    *,
    fixture_root: Path,
) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    errors.extend(validate_release(release, manifest))
    errors.extend(validate_release_files(release, fixture_root))
    if errors:
        raise ValidationError("schedule inputs are invalid: " + "; ".join(errors))

    arms = _map_by_id(manifest["arms"])
    profiles = _profile_map(release)
    protocol_digest = digest_json(manifest, "protocol")
    canonical_release = normalized_release(release)
    release_digest = digest_json(canonical_release, "release")
    seed = release["randomization_seed"]
    ranked_runs: list[tuple[int, str, str, dict[str, Any]]] = []
    for fixture in canonical_release["fixtures"]:
        stage = fixture["stage"]
        budget_block = manifest["budgets"][stage]
        for arm_id in ARM_IDS:
            arm = arms[arm_id]
            pair_id = arm["pair_id"]
            canonical_key = "|".join(
                (
                    stage,
                    fixture["scenario_class"],
                    fixture["fixture_id"],
                    arm_id,
                    "1",
                )
            )
            rank = hashlib.sha256(f"{seed}|{canonical_key}".encode("utf-8")).hexdigest()
            run_hash = hashlib.sha256(
                f"{protocol_digest}|{release_digest}|{canonical_key}".encode("utf-8")
            ).hexdigest()
            run = {
                "run_id": f"run-{run_hash[:20]}",
                "sequence": -1,
                "stage": stage,
                "scenario_class": fixture["scenario_class"],
                "fixture_id": fixture["fixture_id"],
                "replica": 1,
                "arm": arm_id,
                "pair_id": pair_id,
                "mode": arm["mode"],
                "intervention": arm["intervention"],
                "provider_profile_digest": digest_json(
                    profiles[pair_id], "provider-profile"
                ),
                "budget": dict(budget_block["per_run"]),
            }
            stage_order = 0 if stage == "pilot" else 1
            ranked_runs.append((stage_order, rank, canonical_key, run))
    ranked_runs.sort(key=lambda item: (item[0], item[1], item[2]))
    ordered_runs: list[dict[str, Any]] = []
    for sequence, item in enumerate(ranked_runs):
        run = dict(item[3])
        run["sequence"] = sequence
        ordered_runs.append(run)
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": protocol_digest,
        "release_id": release["release_id"],
        "release_digest": release_digest,
        "schedule_seed_digest": hashlib.sha256(
            b"vidux-v3:schedule-seed\0" + seed.encode("ascii")
        ).hexdigest(),
        "stage_budgets": {
            stage: dict(manifest["budgets"][stage]["global"])
            for stage in ("pilot", "full")
        },
        "protocol_budget": dict(manifest["budgets"]["protocol"]),
        "max_infra_attempts": 2,
        "runs": ordered_runs,
    }


def validate_schedule(
    schedule: dict[str, Any],
    manifest: dict[str, Any],
    release: dict[str, Any],
    *,
    fixture_root: Path,
) -> list[str]:
    errors: list[str] = []
    if set(schedule) != SCHEDULE_KEYS:
        errors.append("schedule must contain exactly the deterministic schedule fields")
    try:
        expected = build_schedule(manifest, release, fixture_root=fixture_root)
    except ValidationError as error:
        return [str(error)]
    if schedule != expected:
        errors.append("schedule must exactly match deterministic complete regeneration")
    runs = schedule.get("runs")
    if isinstance(runs, list):
        run_ids: set[str] = set()
        for run in runs:
            if not isinstance(run, dict) or set(run) != RUN_KEYS:
                errors.append("each schedule run must contain exactly the frozen run fields")
                continue
            run_id = run.get("run_id")
            if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
                errors.append("schedule run_id must be an opaque SHA-256 prefix")
            elif run_id in run_ids:
                errors.append(f"duplicate schedule run_id: {run_id}")
            else:
                run_ids.add(run_id)
    return errors


def build_run_packet(
    manifest: dict[str, Any],
    release: dict[str, Any],
    schedule: dict[str, Any],
    *,
    fixture_root: Path,
    run_id: str,
) -> dict[str, Any]:
    errors = validate_schedule(schedule, manifest, release, fixture_root=fixture_root)
    if errors:
        raise ValidationError("schedule is invalid: " + "; ".join(errors))
    run = next((item for item in schedule["runs"] if item["run_id"] == run_id), None)
    if run is None:
        raise ValidationError(f"unknown run_id: {run_id}")
    fixture = _fixture_map(release)[
        (run["stage"], run["scenario_class"], run["fixture_id"])
    ]
    profile = _profile_map(release)[run["pair_id"]]
    packet = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": schedule["protocol_digest"],
        "release_digest": schedule["release_digest"],
        "schedule_digest": digest_json(schedule, "schedule"),
        "run_id": run["run_id"],
        "sequence": run["sequence"],
        "stage": run["stage"],
        "arm": run["arm"],
        "pair_id": run["pair_id"],
        "mode": run["mode"],
        "intervention": run["intervention"],
        "provider_profile": dict(profile),
        "fixture": dict(fixture),
        "budget": dict(run["budget"]),
        "measurement_receipts": list(RECEIPT_DIGEST_IDS),
    }
    if _contains_private_evaluator_key(packet):
        raise ValidationError("arm packet contains forbidden evaluator material")
    return packet


def attempt_id_for(run_id: str, attempt_number: int) -> str:
    if RUN_ID_RE.fullmatch(run_id) is None or attempt_number < 1:
        raise ValidationError("attempt identity requires a valid run_id and positive number")
    digest = hashlib.sha256(
        f"vidux-v3:attempt\0{run_id}\0{attempt_number}".encode("ascii")
    ).hexdigest()
    return f"attempt-{digest[:20]}"


def readiness(
    manifest: dict[str, Any],
    status: dict[str, Any],
    *,
    release: dict[str, Any] | None = None,
    fixture_root: Path | None = None,
    schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gates = validate_manifest(manifest)
    gates.extend(validate_status(status, manifest))
    if not gates and status.get("runnable") is not True:
        gates.append(NON_RUNNABLE_GATE)
        return {
            "protocol_id": PROTOCOL_ID,
            "protocol_digest": digest_json(manifest, "protocol"),
            "status": status.get("status"),
            "preflight_ready": False,
            "ready_for_provider_spend": False,
            "provider_transport_enabled": False,
            "pilot_executed": False,
            "verified_net_win_classes": 0,
            "gates": gates,
        }
    if release is None:
        gates.append("external public evaluator release is required")
    elif fixture_root is None:
        gates.append("public fixture root is required")
    else:
        gates.extend(validate_release(release, manifest))
        gates.extend(validate_release_files(release, fixture_root))
        if schedule is None:
            gates.append("deterministic complete schedule is required")
        else:
            gates.extend(
                validate_schedule(schedule, manifest, release, fixture_root=fixture_root)
            )
    artifact_gates = list(gates)
    if status.get("provider_transport_enabled") is not True:
        gates.append("provider transport is intentionally disabled pending a reviewed runner slice")
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": digest_json(manifest, "protocol"),
        "status": status.get("status"),
        "preflight_ready": not artifact_gates,
        "ready_for_provider_spend": not gates,
        "provider_transport_enabled": status.get("provider_transport_enabled") is True,
        "pilot_executed": status.get("pilot_executed") is True,
        "verified_net_win_classes": status.get("verified_net_win_classes"),
        "gates": gates,
    }


def _validate_metric_map(metrics: Any, budget: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(metrics, dict) or set(metrics) != set(METRIC_IDS):
        return [f"{label} metrics must contain exactly {', '.join(METRIC_IDS)}"]
    for metric in METRIC_IDS:
        value = metrics.get(metric)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{label} {metric} must be a non-negative integer")
        elif value > budget[metric]:
            errors.append(f"{label} {metric} exceeds the frozen run budget")
    return errors


def validate_result(result: dict[str, Any], schedule: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(result) != RESULT_KEYS:
        errors.append("runner result must contain exactly the content-addressed result fields")
    if result.get("schema_version") != 1:
        errors.append("runner result schema_version must equal 1")
    if result.get("schedule_digest") != digest_json(schedule, "schedule"):
        errors.append("runner result schedule_digest must bind the complete schedule")
    run = next(
        (item for item in schedule.get("runs", []) if item.get("run_id") == result.get("run_id")),
        None,
    )
    if run is None:
        errors.append("runner result run_id must exist in the schedule")
    attempt_id = result.get("attempt_id")
    if not isinstance(attempt_id, str) or ID_RE.fullmatch(attempt_id) is None:
        errors.append("runner result attempt_id must be a normalized opaque id")
    elif run is not None and attempt_id not in {
        attempt_id_for(run["run_id"], number)
        for number in range(1, int(schedule.get("max_infra_attempts", 0)) + 1)
    }:
        errors.append("runner result attempt_id must be schedule-derived")
    if result.get("status") not in RUNNER_TERMINAL_STATES:
        errors.append("runner result status must be a frozen terminal runner status")
    if run is not None:
        errors.extend(_validate_metric_map(result.get("metrics"), run["budget"], "runner result"))
    for key in RECEIPT_DIGEST_IDS:
        if not _valid_sha(result.get(key)):
            errors.append(f"runner result {key} must be a lowercase SHA-256")
    return errors


def validate_evaluator_result(
    evaluator_result: dict[str, Any],
    schedule: dict[str, Any],
    result: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if set(evaluator_result) != EVALUATOR_RESULT_KEYS:
        errors.append("evaluator result must contain exactly the deterministic evaluator fields")
    if evaluator_result.get("schema_version") != 1:
        errors.append("evaluator result schema_version must equal 1")
    if evaluator_result.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"evaluator result protocol_id must equal {PROTOCOL_ID}")
    if evaluator_result.get("run_id") != result.get("run_id"):
        errors.append("evaluator result run_id must match the runner result")
    run = next(
        (item for item in schedule.get("runs", []) if item.get("run_id") == result.get("run_id")),
        None,
    )
    if run is not None and evaluator_result.get("fixture_id") != run.get("fixture_id"):
        errors.append("evaluator result fixture_id must match the scheduled run")
    if evaluator_result.get("runner_result_sha256") != digest_json(
        result, "runner-result"
    ):
        errors.append("evaluator result must bind the exact runner result")
    if not _valid_sha(evaluator_result.get("evaluator_run_sha256")):
        errors.append("evaluator_run_sha256 must be a lowercase SHA-256")
    checks = evaluator_result.get("checks")
    seen: set[str] = set()
    required_count = 0
    if not isinstance(checks, list) or not checks:
        errors.append("evaluator checks must be a non-empty list")
    else:
        for check in checks:
            if not isinstance(check, dict) or set(check) != CHECK_KEYS:
                errors.append("each evaluator check must contain exactly the check fields")
                continue
            check_id = check.get("id")
            if not isinstance(check_id, str) or ID_RE.fullmatch(check_id) is None:
                errors.append("evaluator check id must be a normalized opaque id")
            elif check_id in seen:
                errors.append(f"duplicate evaluator check id: {check_id}")
            else:
                seen.add(check_id)
            if not isinstance(check.get("required"), bool) or not isinstance(
                check.get("passed"), bool
            ):
                errors.append("evaluator check required and passed must be booleans")
            if check.get("required") is True:
                required_count += 1
            if not _valid_sha(check.get("evidence_sha256")):
                errors.append("evaluator check evidence_sha256 must be lowercase SHA-256")
    if required_count == 0:
        errors.append("evaluator result must contain at least one required check")
    transitions = evaluator_result.get("resume_transitions")
    if not isinstance(transitions, dict) or set(transitions) != RESUME_KEYS:
        errors.append("resume_transitions must contain exactly missed, repeated, and invented")
    else:
        for key in RESUME_KEYS:
            value = transitions.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"resume_transitions {key} must be a non-negative integer")
    if not isinstance(evaluator_result.get("forbidden_action"), bool):
        errors.append("forbidden_action must be a boolean")
    return errors


def adjudicate(
    schedule: dict[str, Any],
    result: dict[str, Any],
    evaluator_result: dict[str, Any],
    journal_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    errors = validate_result(result, schedule)
    errors.extend(validate_evaluator_result(evaluator_result, schedule, result))
    errors.extend(validate_result_against_journal(result, schedule, journal_rows))
    if errors:
        raise ValidationError("adjudication inputs are invalid: " + "; ".join(errors))
    run = next(
        item for item in schedule["runs"] if item["run_id"] == result["run_id"]
    )
    required_pass = all(
        check["passed"]
        for check in evaluator_result["checks"]
        if check["required"]
    )
    runner_completed = result["status"] == "runner_completed"
    forbidden_action = evaluator_result["forbidden_action"]
    success = int(runner_completed and required_pass and not forbidden_action)
    resume_loss = sum(evaluator_result["resume_transitions"].values())
    if forbidden_action:
        terminal_outcome = "disqualified_for_forbidden_action"
    elif result["status"] == "budget_exhausted":
        terminal_outcome = "budget_exhausted"
    elif result["status"] == "runner_failed":
        terminal_outcome = "runner_failed"
    elif result["status"] == "infrastructure_exhausted":
        terminal_outcome = "infrastructure_exhausted"
    elif not required_pass:
        terminal_outcome = "oracle_failed"
    else:
        terminal_outcome = "pass"
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": schedule["protocol_digest"],
        "schedule_digest": digest_json(schedule, "schedule"),
        "run_id": result["run_id"],
        "attempt_id": result["attempt_id"],
        "stage": run["stage"],
        "scenario_class": run["scenario_class"],
        "fixture_id": run["fixture_id"],
        "arm": run["arm"],
        "pair_id": run["pair_id"],
        "runner_result_sha256": digest_json(result, "runner-result"),
        "evaluator_result_sha256": digest_json(evaluator_result, "evaluator-result"),
        "success": success,
        "resume_loss": resume_loss,
        "terminal_outcome": terminal_outcome,
        "metrics": dict(result["metrics"]),
    }


def validate_result_against_journal(
    result: dict[str, Any],
    schedule: dict[str, Any],
    journal_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    try:
        states = _replay_journal(schedule, journal_rows)
    except ValidationError as error:
        return [str(error)]
    state = states.get(result.get("run_id"))
    if state is None:
        return ["runner result run_id is absent from the journal schedule"]
    runner_status = state.get("runner_status")
    if runner_status not in RUNNER_TERMINAL_STATES:
        errors.append("runner result requires a journaled terminal runner event")
        return errors
    if result.get("status") != runner_status:
        errors.append("runner result status does not match the journaled terminal event")
    if result.get("attempt_id") != state.get("attempt_id"):
        errors.append("runner result attempt_id does not match the journaled attempt")
    payload = state.get("runner_payload")
    if not isinstance(payload, dict):
        errors.append("journaled terminal event has no runner payload")
        return errors
    if result.get("metrics") != payload.get("metrics"):
        errors.append("runner result metrics do not match the journaled payload")
    for key in RECEIPT_DIGEST_IDS:
        if result.get(key) != payload.get(key):
            errors.append(f"runner result {key} does not match the journaled payload")
    return errors


def _journal_row_hash(row: dict[str, Any]) -> str:
    unhashed = {key: value for key, value in row.items() if key != "event_sha256"}
    return digest_json(unhashed, "journal-event")


def _secure_open_read(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError("journal must be a single-link regular file")
        if info.st_size > MAX_JOURNAL_BYTES:
            raise ValidationError("journal exceeds the 64 MiB safety limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_JOURNAL_BYTES:
                raise ValidationError("journal exceeds the 64 MiB safety limit")
            chunks.append(chunk)
        try:
            return b"".join(chunks).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError("journal must be UTF-8 JSONL") from error
    finally:
        os.close(fd)


def load_journal(path: Path, schedule: dict[str, Any]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = _secure_open_read(path)
    except OSError as error:
        raise ValidationError(f"journal is unavailable: {error}") from error
    if text and not text.endswith("\n"):
        raise ValidationError("journal has a torn or unterminated tail")
    rows: list[dict[str, Any]] = []
    previous = "0" * 64
    operation_ids: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line:
            raise ValidationError(f"journal line {line_number} is blank")
        row = strict_json_loads(raw_line, label=f"journal line {line_number}")
        if not isinstance(row, dict):
            raise ValidationError(f"journal line {line_number} must be an object")
        expected_keys = JOURNAL_HEADER_KEYS if line_number == 1 else JOURNAL_EVENT_KEYS
        if set(row) != expected_keys:
            raise ValidationError(f"journal line {line_number} contains unknown or missing fields")
        if row.get("schema_version") != 1:
            raise ValidationError(f"journal line {line_number} schema_version must equal 1")
        if row.get("sequence") != len(rows):
            raise ValidationError(f"journal line {line_number} sequence is not contiguous")
        if row.get("previous_event_sha256") != previous:
            raise ValidationError(f"journal line {line_number} breaks the hash chain")
        if row.get("event_sha256") != _journal_row_hash(row):
            raise ValidationError(f"journal line {line_number} event hash is invalid")
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str) or ID_RE.fullmatch(operation_id) is None:
            raise ValidationError(f"journal line {line_number} operation_id is invalid")
        if operation_id in operation_ids:
            raise ValidationError(f"journal operation_id is duplicated: {operation_id}")
        operation_ids.add(operation_id)
        rows.append(row)
        previous = row["event_sha256"]
    if rows:
        header = rows[0]
        if header.get("event") != "journal_initialized":
            raise ValidationError("journal must start with journal_initialized")
        if header.get("schedule_digest") != digest_json(schedule, "schedule"):
            raise ValidationError("journal header does not bind the supplied schedule")
        if header.get("payload") != {
            "protocol_id": schedule.get("protocol_id"),
            "run_count": len(schedule.get("runs", [])),
        }:
            raise ValidationError("journal header payload does not bind protocol and run count")
    _replay_journal(schedule, rows)
    return rows


def _usage_payload_errors(payload: Any, budget: dict[str, Any], label: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{label} payload must be an object"]
    required = {"metrics", *RECEIPT_DIGEST_IDS}
    if not required.issubset(payload):
        return [f"{label} payload must include metrics and all receipt digests"]
    errors = _validate_metric_map(payload.get("metrics"), budget, label)
    for key in RECEIPT_DIGEST_IDS:
        if not _valid_sha(payload.get(key)):
            errors.append(f"{label} {key} must be a lowercase SHA-256")
    return errors


def _replay_journal(
    schedule: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    run_map = {run["run_id"]: run for run in schedule.get("runs", [])}
    states = {
        run_id: {"state": "pending", "attempt_id": None, "attempts": 0}
        for run_id in run_map
    }
    if not rows:
        return states
    for row in rows[1:]:
        event = row.get("event")
        run_id = row.get("run_id")
        attempt_id = row.get("attempt_id")
        payload = row.get("payload")
        if event not in JOURNAL_EVENTS:
            raise ValidationError(f"journal contains an unknown event: {event!r}")
        if run_id not in states:
            raise ValidationError(f"journal event references an unknown run: {run_id!r}")
        state = states[run_id]
        current = state["state"]
        if event == "attempt_claimed":
            if current not in {"pending", "retryable"}:
                raise ValidationError(f"{run_id} cannot be claimed from {current}")
            if not isinstance(payload, dict) or set(payload) != {"worker_id", "attempt_number"}:
                raise ValidationError("attempt_claimed payload must contain worker_id and attempt_number")
            if not isinstance(payload.get("worker_id"), str) or ID_RE.fullmatch(
                payload.get("worker_id", "")
            ) is None:
                raise ValidationError("attempt_claimed worker_id is invalid")
            expected_attempt = state["attempts"] + 1
            if payload.get("attempt_number") != expected_attempt:
                raise ValidationError("attempt_claimed attempt_number is not contiguous")
            if attempt_id != attempt_id_for(run_id, expected_attempt):
                raise ValidationError("attempt_claimed attempt_id is not schedule-derived")
            if expected_attempt > schedule.get("max_infra_attempts", 0):
                raise ValidationError("attempt_claimed exceeds max_infra_attempts")
            state.update(state="claimed", attempt_id=attempt_id, attempts=expected_attempt)
        elif attempt_id != state["attempt_id"]:
            raise ValidationError(f"{run_id} event attempt_id does not match the active attempt")
        elif event == "attempt_started":
            if current != "claimed" or payload != {}:
                raise ValidationError(f"{run_id} can start only from claimed with an empty payload")
            state["state"] = "started"
        elif event == "runner_completed":
            if current != "started":
                raise ValidationError(f"{run_id} can complete only from started")
            errors = _usage_payload_errors(payload, run_map[run_id]["budget"], "runner_completed")
            if (
                errors
                or not isinstance(payload, dict)
                or set(payload) != {"metrics", *RECEIPT_DIGEST_IDS}
            ):
                raise ValidationError("; ".join(errors or ["runner_completed payload has extra fields"]))
            state.update(
                state="runner_completed",
                runner_status="runner_completed",
                runner_payload=dict(payload),
                metrics=payload["metrics"],
            )
        elif event == "attempt_failed":
            if current not in ACTIVE_STATES:
                raise ValidationError(f"{run_id} can fail only from claimed or started")
            errors = _usage_payload_errors(payload, run_map[run_id]["budget"], "attempt_failed")
            expected = {"metrics", *RECEIPT_DIGEST_IDS, "failure_kind", "failure_receipt_sha256"}
            if not isinstance(payload, dict) or set(payload) != expected:
                errors.append("attempt_failed payload must contain exactly failure evidence and usage")
            if not isinstance(payload, dict):
                raise ValidationError("; ".join(errors))
            if payload.get("failure_kind") not in {
                "runner_failure",
                "budget_exhausted",
                "infrastructure_exhausted",
            }:
                errors.append("attempt_failed failure_kind is invalid")
            if not _valid_sha(payload.get("failure_receipt_sha256")):
                errors.append("attempt_failed failure_receipt_sha256 must be lowercase SHA-256")
            if errors:
                raise ValidationError("; ".join(errors))
            terminal = {
                "runner_failure": "runner_failed",
                "budget_exhausted": "budget_exhausted",
                "infrastructure_exhausted": "infrastructure_exhausted",
            }[payload["failure_kind"]]
            state.update(
                state=terminal,
                runner_status=terminal,
                runner_payload=dict(payload),
                metrics=payload["metrics"],
            )
        elif event == "infra_retryable":
            if current not in ACTIVE_STATES:
                raise ValidationError(f"{run_id} can retry only from claimed or started")
            errors = _usage_payload_errors(payload, run_map[run_id]["budget"], "infra_retryable")
            expected = {"metrics", *RECEIPT_DIGEST_IDS, "reason_receipt_sha256"}
            if not isinstance(payload, dict) or set(payload) != expected:
                errors.append("infra_retryable payload must contain exactly reason evidence and usage")
            if not isinstance(payload, dict):
                raise ValidationError("; ".join(errors))
            if not _valid_sha(payload.get("reason_receipt_sha256")):
                errors.append("infra_retryable reason_receipt_sha256 must be lowercase SHA-256")
            if state["attempts"] >= schedule.get("max_infra_attempts", 0):
                errors.append("infra_retryable cannot exceed max_infra_attempts")
            if errors:
                raise ValidationError("; ".join(errors))
            state.update(state="retryable", metrics=payload["metrics"])
        elif event == "adjudicated":
            if current not in RUNNER_TERMINAL_STATES:
                raise ValidationError(f"{run_id} can adjudicate only from a runner terminal")
            if not isinstance(payload, dict) or set(payload) != {"adjudication_receipt_sha256"}:
                raise ValidationError("adjudicated payload must contain exactly its receipt digest")
            if not _valid_sha(payload.get("adjudication_receipt_sha256")):
                raise ValidationError("adjudication_receipt_sha256 must be lowercase SHA-256")
            state.update(
                state="adjudicated",
                adjudication_receipt_sha256=payload["adjudication_receipt_sha256"],
            )
    return states


def _spent_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    totals = {metric: 0 for metric in METRIC_IDS}
    for row in rows:
        if row.get("event") not in USAGE_EVENTS:
            continue
        metrics = row.get("payload", {}).get("metrics", {})
        for metric in METRIC_IDS:
            totals[metric] += int(metrics.get(metric, 0))
    return totals


def _check_global_budget(
    schedule: dict[str, Any],
    rows: list[dict[str, Any]],
    states: dict[str, dict[str, Any]],
    run_id: str,
    reported_metrics: dict[str, Any] | None,
) -> None:
    run_map = {run["run_id"]: run for run in schedule["runs"]}
    observed_by_run = {
        scheduled_run_id: {metric: 0 for metric in METRIC_IDS}
        for scheduled_run_id in run_map
    }
    protocol_totals = {metric: 0 for metric in METRIC_IDS}
    stage_totals = {
        stage: {metric: 0 for metric in METRIC_IDS}
        for stage in ("pilot", "full")
    }
    for row in rows:
        if row.get("event") not in USAGE_EVENTS:
            continue
        row_run = run_map[row["run_id"]]
        metrics = row["payload"]["metrics"]
        for metric in METRIC_IDS:
            observed_by_run[row["run_id"]][metric] += metrics[metric]
            protocol_totals[metric] += metrics[metric]
            stage_totals[row_run["stage"]][metric] += metrics[metric]
    for active_run_id, state in states.items():
        if state["state"] in ACTIVE_STATES and not (
            reported_metrics is not None and active_run_id == run_id
        ):
            active_run = run_map[active_run_id]
            for metric in METRIC_IDS:
                reservation = max(
                    0,
                    active_run["budget"][metric]
                    - observed_by_run[active_run_id][metric],
                )
                protocol_totals[metric] += reservation
                stage_totals[active_run["stage"]][metric] += reservation
    target_stage = run_map[run_id]["stage"]
    if reported_metrics is None:
        additional = {
            metric: max(
                0,
                run_map[run_id]["budget"][metric] - observed_by_run[run_id][metric],
            )
            for metric in METRIC_IDS
        }
    else:
        additional = reported_metrics
    for metric in METRIC_IDS:
        if observed_by_run[run_id][metric] + additional[metric] > run_map[run_id]["budget"][metric]:
            raise ValidationError(f"{run_id} cumulative {metric} budget would be exceeded")
        protocol_totals[metric] += additional[metric]
        stage_totals[target_stage][metric] += additional[metric]
        if stage_totals[target_stage][metric] > schedule["stage_budgets"][target_stage][metric]:
            raise ValidationError(f"{target_stage} {metric} budget would be exceeded")
        if protocol_totals[metric] > schedule["protocol_budget"][metric]:
            raise ValidationError(f"protocol {metric} budget would be exceeded")


def _intent_from_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row.get("payload", {}))
    if row.get("event") == "attempt_claimed":
        payload.pop("attempt_number", None)
    return {
        "operation_id": row.get("operation_id"),
        "event": row.get("event"),
        "run_id": row.get("run_id"),
        "attempt_id": row.get("attempt_id"),
        "payload": payload,
    }


def _validate_request(
    request: dict[str, Any], *, allow_adjudication: bool = False
) -> None:
    if set(request) != JOURNAL_REQUEST_KEYS:
        raise ValidationError("journal request must contain exactly the request fields")
    if not isinstance(request.get("operation_id"), str) or ID_RE.fullmatch(
        request.get("operation_id", "")
    ) is None:
        raise ValidationError("journal request operation_id is invalid")
    allowed_events = JOURNAL_EVENTS if allow_adjudication else PUBLIC_JOURNAL_EVENTS
    if request.get("event") not in allowed_events:
        if request.get("event") == "adjudicated":
            raise ValidationError("adjudicated events must be emitted by the adjudicator")
        raise ValidationError("journal request event is invalid")
    if not isinstance(request.get("run_id"), str) or RUN_ID_RE.fullmatch(
        request.get("run_id", "")
    ) is None:
        raise ValidationError("journal request run_id is invalid")
    if not isinstance(request.get("attempt_id"), str) or ID_RE.fullmatch(
        request.get("attempt_id", "")
    ) is None:
        raise ValidationError("journal request attempt_id is invalid")
    if not isinstance(request.get("payload"), dict):
        raise ValidationError("journal request payload must be an object")


def _assert_secure_parent(path: Path) -> None:
    parent = path.parent
    try:
        resolved = parent.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"journal parent is unavailable: {error}") from error
    if not resolved.is_dir() or parent.is_symlink():
        raise ValidationError("journal parent must be a real directory")


@contextlib.contextmanager
def _journal_lock(path: Path) -> Iterator[None]:
    _assert_secure_parent(path)
    lock_path = path.with_name(path.name + ".lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise ValidationError(f"journal lock is unavailable: {error}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError("journal lock must be a single-link regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _append_journal_row(path: Path, row: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as error:
        raise ValidationError(f"journal is unavailable: {error}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError("journal must be a single-link regular file")
        payload = canonical_bytes(row) + b"\n"
        offset = 0
        while offset < len(payload):
            offset += os.write(fd, payload[offset:])
        os.fsync(fd)
    finally:
        os.close(fd)


def initialize_journal(
    path: Path, schedule: dict[str, Any], *, operation_id: str
) -> tuple[dict[str, Any], bool]:
    if ID_RE.fullmatch(operation_id) is None:
        raise ValidationError("journal initialization operation_id is invalid")
    with _journal_lock(path):
        rows = load_journal(path, schedule)
        if rows:
            header = rows[0]
            if header.get("operation_id") == operation_id:
                return header, False
            raise ValidationError("journal is already initialized with a different operation_id")
        row = {
            "schema_version": 1,
            "sequence": 0,
            "operation_id": operation_id,
            "event": "journal_initialized",
            "schedule_digest": digest_json(schedule, "schedule"),
            "payload": {
                "protocol_id": schedule.get("protocol_id"),
                "run_count": len(schedule.get("runs", [])),
            },
            "previous_event_sha256": "0" * 64,
        }
        row["event_sha256"] = _journal_row_hash(row)
        _append_journal_row(path, row)
        return row, True


def record_journal_event(
    path: Path,
    schedule: dict[str, Any],
    request: dict[str, Any],
    *,
    allow_adjudication: bool = False,
) -> tuple[dict[str, Any], bool]:
    _validate_request(request, allow_adjudication=allow_adjudication)
    with _journal_lock(path):
        rows = load_journal(path, schedule)
        if not rows:
            raise ValidationError("journal must be initialized before recording events")
        for row in rows:
            if row.get("operation_id") == request["operation_id"]:
                if _intent_from_row(row) != request:
                    raise ValidationError("operation_id replay changed the original event intent")
                return row, False
        states = _replay_journal(schedule, rows)
        run_map = {run["run_id"]: run for run in schedule["runs"]}
        run_id = request["run_id"]
        if run_id not in run_map:
            raise ValidationError(f"journal request references an unknown run: {run_id}")
        state = states[run_id]
        event = request["event"]
        payload = dict(request["payload"])
        if event == "attempt_claimed":
            if state["state"] not in {"pending", "retryable"}:
                raise ValidationError(f"{run_id} cannot be claimed from {state['state']}")
            if set(payload) != {"worker_id"}:
                raise ValidationError("attempt_claimed request payload must contain only worker_id")
            next_attempt = state["attempts"] + 1
            if next_attempt > schedule["max_infra_attempts"]:
                raise ValidationError("attempt claim exceeds max_infra_attempts")
            if request["attempt_id"] != attempt_id_for(run_id, next_attempt):
                raise ValidationError("attempt claim must use the schedule-derived attempt_id")
            _check_global_budget(
                schedule,
                rows,
                states,
                run_id,
                None,
            )
            payload["attempt_number"] = next_attempt
        elif event in USAGE_EVENTS:
            metrics = payload.get("metrics") if isinstance(payload, dict) else None
            if not isinstance(metrics, dict):
                raise ValidationError(f"{event} request must include metrics")
            metric_errors = _validate_metric_map(metrics, run_map[run_id]["budget"], event)
            if metric_errors:
                raise ValidationError("; ".join(metric_errors))
            _check_global_budget(
                schedule,
                rows,
                states,
                run_id,
                metrics,
            )
        candidate = {
            "schema_version": 1,
            "sequence": len(rows),
            "operation_id": request["operation_id"],
            "event": event,
            "run_id": run_id,
            "attempt_id": request["attempt_id"],
            "payload": payload,
            "previous_event_sha256": rows[-1]["event_sha256"],
        }
        candidate["event_sha256"] = _journal_row_hash(candidate)
        _replay_journal(schedule, rows + [candidate])
        _append_journal_row(path, candidate)
        return candidate, True


def record_adjudication(
    path: Path,
    schedule: dict[str, Any],
    result: dict[str, Any],
    evaluator_result: dict[str, Any],
    *,
    operation_id: str,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    rows = load_journal(path, schedule)
    receipt = adjudicate(schedule, result, evaluator_result, rows)
    receipt_digest = digest_json(receipt, "adjudication")
    event, appended = record_journal_event(
        path,
        schedule,
        {
            "operation_id": operation_id,
            "event": "adjudicated",
            "run_id": result["run_id"],
            "attempt_id": result["attempt_id"],
            "payload": {"adjudication_receipt_sha256": receipt_digest},
        },
        allow_adjudication=True,
    )
    return receipt, event, appended


def validate_adjudication_receipt(
    receipt: dict[str, Any],
    schedule: dict[str, Any],
    states: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if set(receipt) != ADJUDICATION_KEYS:
        errors.append("adjudication receipt must contain exactly the frozen fields")
    if receipt.get("schema_version") != 1:
        errors.append("adjudication receipt schema_version must equal 1")
    if receipt.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"adjudication receipt protocol_id must equal {PROTOCOL_ID}")
    if receipt.get("protocol_digest") != schedule.get("protocol_digest"):
        errors.append("adjudication receipt protocol_digest must match the schedule")
    if receipt.get("schedule_digest") != digest_json(schedule, "schedule"):
        errors.append("adjudication receipt schedule_digest must match the schedule")
    run = next(
        (
            item
            for item in schedule.get("runs", [])
            if item.get("run_id") == receipt.get("run_id")
        ),
        None,
    )
    if run is None:
        errors.append("adjudication receipt run_id must exist in the schedule")
        return errors
    for key in ("stage", "scenario_class", "fixture_id", "arm", "pair_id"):
        if receipt.get(key) != run.get(key):
            errors.append(f"adjudication receipt {key} must match the scheduled run")
    state = states.get(run["run_id"])
    if state is None or state.get("state") != "adjudicated":
        errors.append("adjudication receipt requires a journaled adjudicated event")
        return errors
    if receipt.get("attempt_id") != state.get("attempt_id"):
        errors.append("adjudication receipt attempt_id must match the journaled attempt")
    if digest_json(receipt, "adjudication") != state.get(
        "adjudication_receipt_sha256"
    ):
        errors.append("adjudication receipt digest must match the journaled event")
    for key in ("runner_result_sha256", "evaluator_result_sha256"):
        if not _valid_sha(receipt.get(key)):
            errors.append(f"adjudication receipt {key} must be lowercase SHA-256")
    success = receipt.get("success")
    if not isinstance(success, int) or isinstance(success, bool) or success not in {0, 1}:
        errors.append("adjudication receipt success must equal integer 0 or 1")
    resume_loss = receipt.get("resume_loss")
    if not isinstance(resume_loss, int) or isinstance(resume_loss, bool) or resume_loss < 0:
        errors.append("adjudication receipt resume_loss must be a non-negative integer")
    errors.extend(
        _validate_metric_map(receipt.get("metrics"), run["budget"], "adjudication receipt")
    )
    if receipt.get("metrics") != state.get("runner_payload", {}).get("metrics"):
        errors.append("adjudication receipt metrics must match journaled usage")
    runner_status = state.get("runner_status")
    expected_terminal = {
        "runner_failed": "runner_failed",
        "budget_exhausted": "budget_exhausted",
        "infrastructure_exhausted": "infrastructure_exhausted",
    }.get(runner_status)
    terminal_outcome = receipt.get("terminal_outcome")
    if runner_status == "runner_completed":
        if terminal_outcome not in {
            "pass",
            "oracle_failed",
            "disqualified_for_forbidden_action",
        }:
            errors.append("completed runner adjudication has an invalid terminal_outcome")
        if success == 1 and terminal_outcome != "pass":
            errors.append("only a pass terminal_outcome may have success 1")
        if terminal_outcome == "pass" and success != 1:
            errors.append("a pass terminal_outcome must have success 1")
    elif terminal_outcome != expected_terminal or success != 0:
        errors.append("terminal runner failures must retain their zero-success outcome")
    return errors


def _statistic(
    pairs: list[dict[str, dict[str, Any]]], metric_id: str
) -> Fraction | None:
    if not pairs:
        return None
    native = [pair["native"] for pair in pairs]
    vidux = [pair["vidux"] for pair in pairs]
    if metric_id == "success_delta_basis_points":
        return Fraction(
            10000 * sum(v["success"] - n["success"] for n, v in zip(native, vidux)),
            len(pairs),
        )
    if metric_id in {
        "tokens_per_resolved_ratio_basis_points",
        "cost_per_resolved_ratio_basis_points",
    }:
        metric = (
            "tokens"
            if metric_id == "tokens_per_resolved_ratio_basis_points"
            else "cost_microusd"
        )
        native_success = sum(item["success"] for item in native)
        vidux_success = sum(item["success"] for item in vidux)
        native_total = sum(item["metrics"][metric] for item in native)
        vidux_total = sum(item["metrics"][metric] for item in vidux)
        if native_success == 0 or vidux_success == 0 or native_total == 0:
            return None
        return Fraction(
            10000 * vidux_total * native_success,
            vidux_success * native_total,
        )
    if metric_id == "elapsed_ratio_basis_points":
        native_total = sum(item["metrics"]["elapsed_ms"] for item in native)
        if native_total == 0:
            return None
        return Fraction(
            10000 * sum(item["metrics"]["elapsed_ms"] for item in vidux),
            native_total,
        )
    if metric_id == "operator_touches_delta_basis_points":
        return Fraction(
            10000
            * sum(
                v["metrics"]["operator_touches"] - n["metrics"]["operator_touches"]
                for n, v in zip(native, vidux)
            ),
            len(pairs),
        )
    if metric_id == "resume_loss_delta_basis_points":
        return Fraction(
            10000 * sum(v["resume_loss"] - n["resume_loss"] for n, v in zip(native, vidux)),
            len(pairs),
        )
    raise ValidationError(f"unknown decision metric: {metric_id}")


def _bootstrap_index(seed: str, replicate: int, draw: int, count: int) -> int:
    payload = f"{seed}\0{replicate}\0{draw}".encode("utf-8")
    digest = hashlib.sha256(b"vidux-v3:bootstrap-index\0" + payload).digest()
    return int.from_bytes(digest[:8], "big") % count


def _nearest_rank(
    values: list[Fraction | None], quantile_basis_points: int
) -> Fraction | None:
    if not values:
        raise ValidationError("cannot calculate a decision interval without samples")
    ordered = sorted(
        values,
        key=lambda value: (value is None, value if value is not None else Fraction(0)),
    )
    rank = (len(ordered) * quantile_basis_points + 9999) // 10000
    index = max(0, min(len(ordered) - 1, rank - 1))
    return ordered[index]


def _round_fraction(value: Fraction) -> int:
    numerator = value.numerator
    denominator = value.denominator
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((2 * -numerator + denominator) // (2 * denominator))


def _metric_receipt(
    estimate: Fraction | None,
    lower: Fraction | None,
    upper: Fraction | None,
) -> dict[str, Any]:
    if estimate is None or lower is None or upper is None:
        return {
            "defined": False,
            "estimate_basis_points": None,
            "ci_lower_basis_points": None,
            "ci_upper_basis_points": None,
        }
    return {
        "defined": True,
        "estimate_basis_points": _round_fraction(estimate),
        "ci_lower_basis_points": lower.numerator // lower.denominator,
        "ci_upper_basis_points": -((-upper.numerator) // upper.denominator),
    }


def _comparison(
    pairs: list[dict[str, dict[str, Any]]],
    *,
    schedule: dict[str, Any],
    stage: str,
    pair_id: str,
    scenario_id: str,
    rules: dict[str, Any],
) -> dict[str, Any]:
    replicates = rules["bootstrap_replicates"]
    seed = "|".join(
        (
            schedule["protocol_digest"],
            schedule["release_digest"],
            stage,
            pair_id,
            scenario_id,
        )
    )
    estimates = {
        metric_id: _statistic(pairs, metric_id)
        for metric_id in DECISION_METRIC_IDS
    }
    samples: dict[str, list[Fraction | None]] = {
        metric_id: [] for metric_id in DECISION_METRIC_IDS
    }
    undefined = {
        metric_id for metric_id, value in estimates.items() if value is None
    }
    for replicate in range(replicates):
        sample = [
            pairs[_bootstrap_index(seed, replicate, draw, len(pairs))]
            for draw in range(len(pairs))
        ]
        for metric_id in DECISION_METRIC_IDS:
            if metric_id in undefined:
                continue
            value = _statistic(sample, metric_id)
            if value is None:
                samples[metric_id].append(None)
            else:
                samples[metric_id].append(value)
    exact_intervals: dict[str, tuple[Fraction, Fraction] | None] = {}
    metrics: dict[str, dict[str, Any]] = {}
    for metric_id in DECISION_METRIC_IDS:
        if metric_id in undefined:
            exact_intervals[metric_id] = None
            metrics[metric_id] = _metric_receipt(None, None, None)
            continue
        lower = _nearest_rank(samples[metric_id], 250)
        upper = _nearest_rank(samples[metric_id], 9750)
        if lower is None or upper is None:
            exact_intervals[metric_id] = None
            metrics[metric_id] = _metric_receipt(None, None, None)
            continue
        exact_intervals[metric_id] = (lower, upper)
        metrics[metric_id] = _metric_receipt(estimates[metric_id], lower, upper)
    win = all(interval is not None for interval in exact_intervals.values())
    if win:
        win = (
            exact_intervals["success_delta_basis_points"][0]
            >= rules["success_delta_lower_bound_basis_points"]
            and exact_intervals["tokens_per_resolved_ratio_basis_points"][1]
            <= rules["tokens_per_resolved_ratio_upper_bound_basis_points"]
            and exact_intervals["cost_per_resolved_ratio_basis_points"][1]
            <= rules["cost_per_resolved_ratio_upper_bound_basis_points"]
            and exact_intervals["elapsed_ratio_basis_points"][1]
            <= rules["elapsed_ratio_upper_bound_basis_points"]
            and exact_intervals["operator_touches_delta_basis_points"][1]
            <= 10000 * rules["operator_touches_delta_upper_bound"]
            and exact_intervals["resume_loss_delta_basis_points"][1]
            <= 10000 * rules["resume_loss_delta_upper_bound"]
        )
    return {
        "pair_id": pair_id,
        "scenario_class": scenario_id,
        "fixture_pairs": len(pairs),
        "status": "win" if win else "no_win",
        "metrics": metrics,
    }


def decide(
    manifest: dict[str, Any],
    release: dict[str, Any],
    schedule: dict[str, Any],
    *,
    fixture_root: Path,
    journal_rows: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_schedule(schedule, manifest, release, fixture_root=fixture_root)
    if set(bundle) != ADJUDICATION_BUNDLE_KEYS:
        errors.append("adjudication bundle must contain exactly the frozen fields")
    if bundle.get("schema_version") != 1:
        errors.append("adjudication bundle schema_version must equal 1")
    if bundle.get("schedule_digest") != digest_json(schedule, "schedule"):
        errors.append("adjudication bundle schedule_digest must match the schedule")
    stage = bundle.get("stage")
    if stage not in {"pilot", "full"}:
        errors.append("adjudication bundle stage must equal pilot or full")
    receipts = bundle.get("adjudications")
    if not isinstance(receipts, list):
        errors.append("adjudication bundle adjudications must be a list")
        receipts = []
    states = _replay_journal(schedule, journal_rows)
    receipt_map: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if not isinstance(receipt, dict):
            errors.append("each adjudication receipt must be an object")
            continue
        run_id = receipt.get("run_id")
        if not isinstance(run_id, str) or run_id in receipt_map:
            errors.append("adjudication receipt run_id values must be unique strings")
            continue
        receipt_map[run_id] = receipt
        errors.extend(validate_adjudication_receipt(receipt, schedule, states))
    expected_runs = [run for run in schedule.get("runs", []) if run.get("stage") == stage]
    expected_ids = {run["run_id"] for run in expected_runs}
    if set(receipt_map) != expected_ids:
        missing = len(expected_ids - set(receipt_map))
        unexpected = len(set(receipt_map) - expected_ids)
        errors.append(
            f"adjudication bundle must contain the complete {stage} stage: "
            f"missing={missing}, unexpected={unexpected}"
        )
    expected_count = 16 if stage == "pilot" else 192
    if len(expected_runs) != expected_count:
        errors.append(f"schedule must contain exactly {expected_count} {stage} runs")
    if errors:
        raise ValidationError("decision inputs are invalid: " + "; ".join(errors))

    ordered_receipts = [receipt_map[run["run_id"]] for run in expected_runs]
    arms = _map_by_id(manifest["arms"])
    pairs_by_block: dict[
        tuple[str, str, str], dict[str, dict[str, Any]]
    ] = {}
    for receipt in ordered_receipts:
        key = (
            receipt["pair_id"],
            receipt["scenario_class"],
            receipt["fixture_id"],
        )
        role = "vidux" if arms[receipt["arm"]]["mode"] == "vidux" else "native"
        block = pairs_by_block.setdefault(key, {})
        if role in block:
            raise ValidationError(f"decision block has duplicate {role} arm: {key}")
        block[role] = receipt
    for key, block in pairs_by_block.items():
        if set(block) != {"native", "vidux"}:
            raise ValidationError(f"decision block is not provider-matched: {key}")

    comparisons: list[dict[str, Any]] = []
    rules = manifest["decision_rules"]
    for pair_id in PAIR_IDS:
        for scenario_id in SCENARIO_IDS:
            paired = [
                block
                for (block_pair, block_scenario, _fixture_id), block in sorted(
                    pairs_by_block.items()
                )
                if block_pair == pair_id and block_scenario == scenario_id
            ]
            minimum = 1 if stage == "pilot" else rules[
                "minimum_complete_pairs_per_provider_class"
            ]
            if len(paired) != minimum:
                raise ValidationError(
                    f"{stage} {pair_id}/{scenario_id} requires exactly {minimum} pairs"
                )
            comparisons.append(
                _comparison(
                    paired,
                    schedule=schedule,
                    stage=stage,
                    pair_id=pair_id,
                    scenario_id=scenario_id,
                    rules=rules,
                )
            )
    scenario_results: list[dict[str, Any]] = []
    for scenario_id in SCENARIO_IDS:
        pair_statuses = {
            comparison["pair_id"]: comparison["status"]
            for comparison in comparisons
            if comparison["scenario_class"] == scenario_id
        }
        scenario_results.append(
            {
                "scenario_class": scenario_id,
                "status": (
                    "win"
                    if stage == "full" and all(value == "win" for value in pair_statuses.values())
                    else "no_win"
                ),
                "provider_pair_statuses": pair_statuses,
            }
        )
    verified_classes = (
        sum(result["status"] == "win" for result in scenario_results)
        if stage == "full"
        else 0
    )
    normalized_bundle = {
        "schema_version": 1,
        "schedule_digest": bundle["schedule_digest"],
        "stage": stage,
        "adjudications": sorted(ordered_receipts, key=lambda item: item["run_id"]),
    }
    if stage == "pilot":
        verdict = "pilot_directional"
    elif verified_classes >= rules["minimum_verified_net_win_classes"]:
        verdict = "verified_net_win"
    else:
        verdict = "no_verified_net_win"
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": schedule["protocol_digest"],
        "release_digest": schedule["release_digest"],
        "schedule_digest": digest_json(schedule, "schedule"),
        "journal_last_event_sha256": journal_rows[-1]["event_sha256"],
        "adjudication_bundle_sha256": digest_json(
            normalized_bundle, "adjudication-bundle"
        ),
        "stage": stage,
        "claim_eligible": stage == "full",
        "run_count": len(ordered_receipts),
        "comparisons": comparisons,
        "scenario_results": scenario_results,
        "verified_net_win_classes": verified_classes,
        "verdict": verdict,
    }


def journal_summary(path: Path, schedule: dict[str, Any]) -> dict[str, Any]:
    rows = load_journal(path, schedule)
    states = _replay_journal(schedule, rows)
    counts: dict[str, int] = {}
    for state in states.values():
        counts[state["state"]] = counts.get(state["state"], 0) + 1
    return {
        "valid": bool(rows),
        "schedule_digest": digest_json(schedule, "schedule"),
        "events": len(rows),
        "run_states": dict(sorted(counts.items())),
        "spent": _spent_metrics(rows),
        "last_event_sha256": rows[-1]["event_sha256"] if rows else None,
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _load_optional(path: Path | None) -> dict[str, Any] | None:
    return load_json(path) if path is not None else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate")

    readiness_parser = subparsers.add_parser("readiness")
    readiness_parser.add_argument("--release", type=Path)
    readiness_parser.add_argument("--fixture-root", type=Path)
    readiness_parser.add_argument("--schedule", type=Path)

    schedule_parser = subparsers.add_parser("schedule")
    schedule_parser.add_argument("--release", type=Path, required=True)
    schedule_parser.add_argument("--fixture-root", type=Path, required=True)

    packet_parser = subparsers.add_parser("packet")
    packet_parser.add_argument("--release", type=Path, required=True)
    packet_parser.add_argument("--fixture-root", type=Path, required=True)
    packet_parser.add_argument("--schedule", type=Path, required=True)
    packet_parser.add_argument("--run-id", required=True)

    journal_init_parser = subparsers.add_parser("journal-init")
    journal_init_parser.add_argument("--schedule", type=Path, required=True)
    journal_init_parser.add_argument("--journal", type=Path, required=True)
    journal_init_parser.add_argument("--operation-id", required=True)

    journal_event_parser = subparsers.add_parser("journal-event")
    journal_event_parser.add_argument("--schedule", type=Path, required=True)
    journal_event_parser.add_argument("--journal", type=Path, required=True)
    journal_event_parser.add_argument("--request", type=Path, required=True)

    journal_verify_parser = subparsers.add_parser("journal-verify")
    journal_verify_parser.add_argument("--schedule", type=Path, required=True)
    journal_verify_parser.add_argument("--journal", type=Path, required=True)

    adjudicate_parser = subparsers.add_parser("adjudicate")
    adjudicate_parser.add_argument("--schedule", type=Path, required=True)
    adjudicate_parser.add_argument("--journal", type=Path, required=True)
    adjudicate_parser.add_argument("--result", type=Path, required=True)
    adjudicate_parser.add_argument("--evaluator-result", type=Path, required=True)
    adjudicate_parser.add_argument("--operation-id", required=True)

    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--release", type=Path, required=True)
    decide_parser.add_argument("--fixture-root", type=Path, required=True)
    decide_parser.add_argument("--schedule", type=Path, required=True)
    decide_parser.add_argument("--journal", type=Path, required=True)
    decide_parser.add_argument("--adjudications", type=Path, required=True)

    args = parser.parse_args()
    try:
        manifest = load_json(args.manifest)
        status = load_json(args.status)
        if args.command == "validate":
            errors = validate_manifest(manifest) + validate_status(status, manifest)
            receipt = {
                "ok": not errors,
                "protocol_id": PROTOCOL_ID,
                "protocol_digest": digest_json(manifest, "protocol"),
                "status": status.get("status"),
                "runnable": status.get("runnable"),
                "errors": errors,
            }
            _print_json(receipt)
            return 0 if receipt["ok"] else 1
        if args.command == "readiness":
            release = _load_optional(args.release)
            schedule = _load_optional(args.schedule)
            receipt = readiness(
                manifest,
                status,
                release=release,
                fixture_root=args.fixture_root,
                schedule=schedule,
            )
            _print_json(receipt)
            return 0 if receipt["ready_for_provider_spend"] else 2
        require_protocol_runnable(status, manifest)
        if args.command == "schedule":
            release = load_json(args.release)
            _print_json(build_schedule(manifest, release, fixture_root=args.fixture_root))
            return 0
        if args.command == "packet":
            release = load_json(args.release)
            schedule = load_json(args.schedule)
            _print_json(
                build_run_packet(
                    manifest,
                    release,
                    schedule,
                    fixture_root=args.fixture_root,
                    run_id=args.run_id,
                )
            )
            return 0
        if args.command == "journal-init":
            schedule = load_json(args.schedule)
            row, appended = initialize_journal(
                args.journal, schedule, operation_id=args.operation_id
            )
            _print_json({"appended": appended, "event": row})
            return 0
        if args.command == "journal-event":
            schedule = load_json(args.schedule)
            request = load_json(args.request)
            row, appended = record_journal_event(args.journal, schedule, request)
            _print_json({"appended": appended, "event": row})
            return 0
        if args.command == "journal-verify":
            _print_json(journal_summary(args.journal, load_json(args.schedule)))
            return 0
        if args.command == "adjudicate":
            schedule = load_json(args.schedule)
            receipt, event, appended = record_adjudication(
                args.journal,
                schedule,
                load_json(args.result),
                load_json(args.evaluator_result),
                operation_id=args.operation_id,
            )
            _print_json(
                {
                    "appended": appended,
                    "adjudication": receipt,
                    "adjudication_receipt_sha256": digest_json(
                        receipt, "adjudication"
                    ),
                    "journal_event": event,
                }
            )
            return 0
        if args.command == "decide":
            schedule = load_json(args.schedule)
            journal_rows = load_journal(args.journal, schedule)
            receipt = decide(
                manifest,
                load_json(args.release),
                schedule,
                fixture_root=args.fixture_root,
                journal_rows=journal_rows,
                bundle=load_json(args.adjudications),
            )
            _print_json(
                {
                    "decision": receipt,
                    "decision_receipt_sha256": digest_json(
                        receipt, "decision-receipt"
                    ),
                }
            )
            return 0
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"benchmark v3: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
