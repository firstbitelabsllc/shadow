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
RELEASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FIXTURE_RELEASE_KEYS = {
    "schema_version",
    "release_id",
    "protocol_id",
    "source_manifest_digest",
    "evaluator_receipt_id",
    "fixtures",
}
FIXTURE_RELEASE_ENTRY_KEYS = {
    "scenario_class",
    "fixture_id",
    "fixture_path",
    "fixture_sha256",
    "oracle_commitment_sha256",
}


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


def fixture_release_digest(release: dict[str, Any]) -> str:
    """Return the immutable digest that binds rows to one fixture release."""
    encoded = json.dumps(release, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_relative_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty relative path")
    if "\\" in value:
        raise ValidationError(f"{label} must use forward-slash relative paths")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(f"{label} must be a normalized relative path")
    return path


def _resolve_regular_file(root: Path, relative_path: Any, label: str) -> Path:
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"{label} root is unavailable: {error}") from error
    if not resolved_root.is_dir():
        raise ValidationError(f"{label} root must be a directory")

    relative = _safe_relative_path(relative_path, label)
    candidate = resolved_root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValidationError(f"{label} must not traverse a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"{label} is unavailable: {error}") from error
    if not _is_within(resolved, resolved_root):
        raise ValidationError(f"{label} escapes its declared root")
    if not resolved.is_file():
        raise ValidationError(f"{label} must name a regular file")
    return resolved


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    if manifest.get("status") != "protocol_frozen_pending_fixture_seal":
        errors.append("source manifest must remain protocol_frozen_pending_fixture_seal")

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
        if state != "pending_seal":
            errors.append(f"{scenario_id} source manifest oracle_state must remain pending_seal")
        if scenario.get("seal_before_transport") is not True:
            errors.append(f"{scenario_id} must require sealing before transport")
        commitment = scenario.get("oracle_commitment_sha256")
        if commitment is not None:
            errors.append(f"{scenario_id} source manifest must not expose an oracle commitment")

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


def _fixture_release_map(release: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    fixtures = release.get("fixtures")
    if not isinstance(fixtures, list):
        return {}
    return {
        (fixture.get("scenario_class"), fixture.get("fixture_id")): fixture
        for fixture in fixtures
        if isinstance(fixture, dict)
        and isinstance(fixture.get("scenario_class"), str)
        and isinstance(fixture.get("fixture_id"), str)
    }


def validate_fixture_release(release: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """Validate public release metadata without opening any hidden oracle."""
    errors: list[str] = []
    if not isinstance(release, dict):
        return ["fixture release root must be an object"]
    if set(release) != FIXTURE_RELEASE_KEYS:
        errors.append("fixture release must contain exactly the required public fields")
    if release.get("schema_version") != 1:
        errors.append("fixture release schema_version must equal 1")
    if not isinstance(release.get("release_id"), str) or not RELEASE_ID_RE.fullmatch(release["release_id"]):
        errors.append("fixture release_id must be lowercase alphanumeric with optional dashes")
    if release.get("protocol_id") != manifest.get("protocol_id"):
        errors.append("fixture release protocol_id must match the source manifest")
    if release.get("source_manifest_digest") != manifest_digest(manifest):
        errors.append("fixture release must bind to the exact source manifest digest")
    receipt_id = release.get("evaluator_receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 256:
        errors.append("fixture release evaluator_receipt_id must be a bounded non-empty string")

    fixtures = release.get("fixtures")
    if not isinstance(fixtures, list):
        return errors + ["fixture release fixtures must be a list"]
    targets = {
        scenario_id: scenario["fixture_count_target"]
        for scenario_id, scenario in _scenario_map(manifest).items()
        if isinstance(scenario.get("fixture_count_target"), int)
    }
    counts = {scenario_id: 0 for scenario_id in SCENARIO_IDS}
    seen_ids: set[tuple[str, str]] = set()
    seen_paths: set[str] = set()

    for index, fixture in enumerate(fixtures, start=1):
        label = f"fixture release entry {index}"
        if not isinstance(fixture, dict):
            errors.append(f"{label} must be an object")
            continue
        if set(fixture) != FIXTURE_RELEASE_ENTRY_KEYS:
            errors.append(f"{label} must contain exactly public fixture fields")
        scenario_id = fixture.get("scenario_class")
        fixture_id = fixture.get("fixture_id")
        if scenario_id not in SCENARIO_IDS:
            errors.append(f"{label} has unknown scenario_class")
            continue
        if not isinstance(fixture_id, str) or not FIXTURE_ID_RE.fullmatch(fixture_id):
            errors.append(f"{label} has invalid fixture_id")
            continue
        key = (scenario_id, fixture_id)
        if key in seen_ids:
            errors.append(f"{label} duplicates fixture {scenario_id}/{fixture_id}")
        seen_ids.add(key)
        try:
            fixture_path = _safe_relative_path(fixture.get("fixture_path"), f"{label} fixture_path")
        except ValidationError as error:
            errors.append(str(error))
        else:
            normalized_path = fixture_path.as_posix()
            if normalized_path in seen_paths:
                errors.append(f"{label} reuses fixture_path {normalized_path}")
            seen_paths.add(normalized_path)
        for key_name in ("fixture_sha256", "oracle_commitment_sha256"):
            value = fixture.get(key_name)
            if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                errors.append(f"{label} {key_name} must be a SHA-256 digest")
        counts[scenario_id] += 1

    for scenario_id in SCENARIO_IDS:
        target = targets.get(scenario_id)
        if target is None:
            errors.append(f"source manifest is missing a fixture target for {scenario_id}")
        elif counts[scenario_id] < target:
            errors.append(f"fixture release {scenario_id} needs at least {target} fixtures")
    return errors


def validate_fixture_release_files(release: dict[str, Any], fixture_root: Path) -> list[str]:
    """Verify every public fixture byte without reading external oracle bytes."""
    errors: list[str] = []
    fixtures = release.get("fixtures", [])
    if not isinstance(fixtures, list):
        return ["fixture release fixtures must be a list"]
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, dict):
            continue
        label = f"fixture release entry {index} fixture_path"
        try:
            fixture_file = _resolve_regular_file(fixture_root, fixture.get("fixture_path"), label)
        except ValidationError as error:
            errors.append(str(error))
            continue
        if _file_sha256(fixture_file) != fixture.get("fixture_sha256"):
            errors.append(f"fixture release entry {index} fixture SHA-256 does not match")
    return errors


def fixture_release_context(manifest: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    """Return release-bound identifiers after structural validation only."""
    source_errors = validate_manifest(manifest)
    if source_errors:
        raise ValidationError("source manifest is invalid: " + "; ".join(source_errors))
    release_errors = validate_fixture_release(release, manifest)
    if release_errors:
        raise ValidationError("fixture release is invalid: " + "; ".join(release_errors))
    return {
        "protocol_id": manifest["protocol_id"],
        "protocol_digest": manifest_digest(manifest),
        "fixture_release_digest": fixture_release_digest(release),
        "fixtures": _fixture_release_map(release),
    }


def build_fixture_release(
    manifest: dict[str, Any],
    index: dict[str, Any],
    *,
    fixture_root: Path,
    oracle_root: Path,
) -> dict[str, Any]:
    """Create public release metadata from evaluator-only index and oracle roots."""
    source_errors = validate_manifest(manifest)
    if source_errors:
        raise ValidationError("source manifest is invalid: " + "; ".join(source_errors))
    if not isinstance(index, dict) or set(index) != {"release_id", "evaluator_receipt_id", "fixtures"}:
        raise ValidationError("fixture index must contain release_id, evaluator_receipt_id, and fixtures only")
    if not isinstance(index.get("fixtures"), list):
        raise ValidationError("fixture index fixtures must be a list")
    if not isinstance(index.get("release_id"), str) or not RELEASE_ID_RE.fullmatch(index["release_id"]):
        raise ValidationError("fixture index release_id must be lowercase alphanumeric with optional dashes")
    receipt_id = index.get("evaluator_receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 256:
        raise ValidationError("fixture index evaluator_receipt_id must be a bounded non-empty string")

    try:
        resolved_fixture_root = fixture_root.resolve(strict=True)
        resolved_oracle_root = oracle_root.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"fixture or oracle root is unavailable: {error}") from error
    if not resolved_fixture_root.is_dir() or not resolved_oracle_root.is_dir():
        raise ValidationError("fixture and oracle roots must be directories")
    if _is_within(resolved_fixture_root, resolved_oracle_root) or _is_within(resolved_oracle_root, resolved_fixture_root):
        raise ValidationError("fixture and oracle roots must not overlap")

    public_fixtures: list[dict[str, Any]] = []
    for entry_number, entry in enumerate(index["fixtures"], start=1):
        label = f"fixture index entry {entry_number}"
        if not isinstance(entry, dict) or set(entry) != {
            "scenario_class",
            "fixture_id",
            "fixture_path",
            "oracle_path",
        }:
            raise ValidationError(f"{label} must contain scenario_class, fixture_id, fixture_path, and oracle_path only")
        if entry.get("scenario_class") not in SCENARIO_IDS:
            raise ValidationError(f"{label} has unknown scenario_class")
        if not isinstance(entry.get("fixture_id"), str) or not FIXTURE_ID_RE.fullmatch(entry["fixture_id"]):
            raise ValidationError(f"{label} has invalid fixture_id")
        fixture_file = _resolve_regular_file(resolved_fixture_root, entry.get("fixture_path"), f"{label} fixture_path")
        oracle_file = _resolve_regular_file(resolved_oracle_root, entry.get("oracle_path"), f"{label} oracle_path")
        public_fixtures.append(
            {
                "scenario_class": entry.get("scenario_class"),
                "fixture_id": entry.get("fixture_id"),
                "fixture_path": _safe_relative_path(entry.get("fixture_path"), f"{label} fixture_path").as_posix(),
                "fixture_sha256": _file_sha256(fixture_file),
                "oracle_commitment_sha256": _file_sha256(oracle_file),
            }
        )

    release = {
        "schema_version": 1,
        "release_id": index.get("release_id"),
        "protocol_id": manifest["protocol_id"],
        "source_manifest_digest": manifest_digest(manifest),
        "evaluator_receipt_id": index.get("evaluator_receipt_id"),
        "fixtures": sorted(public_fixtures, key=lambda item: (item["scenario_class"], item["fixture_id"])),
    }
    release_errors = validate_fixture_release(release, manifest)
    if release_errors:
        raise ValidationError("fixture release is invalid: " + "; ".join(release_errors))
    return release


def load_fixture_release(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("fixture release root must be an object")
    return payload


def load_fixture_index(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("fixture index root must be an object")
    return payload


def write_fixture_release(path: Path, release: dict[str, Any], *, fixture_root: Path, oracle_root: Path) -> None:
    if path.exists():
        raise ValidationError("fixture release output already exists; sealed releases are immutable")
    try:
        parent = path.parent.resolve(strict=True)
        output = parent / path.name
        resolved_fixture_root = fixture_root.resolve(strict=True)
        resolved_oracle_root = oracle_root.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"fixture release output parent is unavailable: {error}") from error
    if _is_within(output, resolved_fixture_root) or _is_within(output, resolved_oracle_root):
        raise ValidationError("fixture release output must stay outside fixture and oracle roots")
    output.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def transport_readiness(
    manifest: dict[str, Any],
    *,
    release: dict[str, Any] | None = None,
    fixture_root: Path | None = None,
) -> dict[str, Any]:
    """Report whether a verified external fixture release may issue a run packet."""
    gates = list(validate_manifest(manifest))
    release_digest = fixture_release_digest(release) if isinstance(release, dict) else None
    if release is None:
        gates.append("sealed external fixture release is required")
    else:
        gates.extend(validate_fixture_release(release, manifest))
        if fixture_root is None:
            gates.append("fixture root is required to verify the sealed release")
        elif not gates:
            gates.extend(validate_fixture_release_files(release, fixture_root))
    return {
        "protocol_id": manifest.get("protocol_id"),
        "protocol_digest": manifest_digest(manifest),
        "fixture_release_digest": release_digest,
        "status": manifest.get("status"),
        "ready": not gates,
        "gates": sorted(set(gates)),
    }


def build_run_packet(
    manifest: dict[str, Any],
    *,
    release: dict[str, Any],
    fixture_root: Path,
    arm: str,
    scenario_class: str,
    fixture_id: str,
    replica: int,
) -> dict[str, Any]:
    """Emit an arm-safe packet from a verified release without oracle payloads."""
    readiness = transport_readiness(manifest, release=release, fixture_root=fixture_root)
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
    context = fixture_release_context(manifest, release)
    fixture = context["fixtures"].get((scenario_class, fixture_id))
    if fixture is None:
        raise ValidationError("fixture_id is not present in the sealed fixture release")
    arm_record = next(item for item in manifest["arms"] if item["id"] == arm)
    return {
        "protocol_id": manifest["protocol_id"],
        "protocol_digest": context["protocol_digest"],
        "fixture_release_digest": context["fixture_release_digest"],
        "arm": arm,
        "scenario_class": scenario_class,
        "fixture_id": fixture_id,
        "fixture_path": fixture["fixture_path"],
        "fixture_sha256": fixture["fixture_sha256"],
        "oracle_commitment_sha256": fixture["oracle_commitment_sha256"],
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


def validate_result_rows(
    rows: Iterable[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    release: dict[str, Any],
) -> dict[tuple[str, str, int], dict[str, dict[str, Any]]]:
    """Validate paired raw rows and return them grouped by paired-block key."""
    context = fixture_release_context(manifest, release)
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
        fixture = context["fixtures"].get((scenario_class, fixture_id))
        if fixture is None:
            errors.append(f"{label} fixture is not present in the sealed fixture release")
            continue
        if row.get("oracle_commitment_sha256") != fixture["oracle_commitment_sha256"]:
            errors.append(f"{label} oracle commitment does not match sealed scenario commitment")
        if row.get("protocol_digest") != context["protocol_digest"]:
            errors.append(f"{label} protocol digest does not match the frozen source manifest")
        if row.get("fixture_release_digest") != context["fixture_release_digest"]:
            errors.append(f"{label} fixture release digest does not match the sealed fixture release")
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


def score_result_rows(
    rows: Iterable[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    release: dict[str, Any],
) -> dict[str, Any]:
    """Score raw rows without upgrading absent or incomplete evidence to a win."""
    context = fixture_release_context(manifest, release)
    grouped = validate_result_rows(list(rows), manifest, release=release)
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
        "protocol_digest": context["protocol_digest"],
        "fixture_release_digest": context["fixture_release_digest"],
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
    validate = subparsers.add_parser("validate")
    validate.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    readiness = subparsers.add_parser("readiness")
    readiness.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    readiness.add_argument("--release", type=Path)
    readiness.add_argument("--fixture-root", type=Path)
    seal_release = subparsers.add_parser("seal-release")
    seal_release.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    seal_release.add_argument("--index", type=Path, required=True)
    seal_release.add_argument("--fixture-root", type=Path, required=True)
    seal_release.add_argument("--oracle-root", type=Path, required=True)
    seal_release.add_argument("--output", type=Path, required=True)
    score = subparsers.add_parser("score")
    score.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    score.add_argument("--results", type=Path, required=True)
    score.add_argument("--release", type=Path, required=True)
    packet = subparsers.add_parser("packet")
    packet.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    packet.add_argument("--release", type=Path, required=True)
    packet.add_argument("--fixture-root", type=Path, required=True)
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
            release = load_fixture_release(args.release) if args.release else None
            result = transport_readiness(manifest, release=release, fixture_root=args.fixture_root)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["ready"] else 2
        if args.command == "seal-release":
            release = build_fixture_release(
                manifest,
                load_fixture_index(args.index),
                fixture_root=args.fixture_root,
                oracle_root=args.oracle_root,
            )
            write_fixture_release(
                args.output,
                release,
                fixture_root=args.fixture_root,
                oracle_root=args.oracle_root,
            )
            print(
                json.dumps(
                    {
                        "fixture_release_digest": fixture_release_digest(release),
                        "output": str(args.output),
                        "protocol_digest": manifest_digest(manifest),
                        "release_id": release["release_id"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "score":
            release = load_fixture_release(args.release)
            print(json.dumps(score_result_rows(_read_rows(args.results), manifest, release=release), sort_keys=True))
            return 0
        release = load_fixture_release(args.release)
        print(
            json.dumps(
                build_run_packet(
                    manifest,
                    release=release,
                    fixture_root=args.fixture_root,
                    arm=args.arm,
                    scenario_class=args.scenario_class,
                    fixture_id=args.fixture_id,
                    replica=args.replica,
                ),
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, ValidationError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
