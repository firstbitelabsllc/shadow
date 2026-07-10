#!/usr/bin/env python3
"""Integrity preflight for the non-runnable Vidux benchmark v4.

This module verifies concrete fixture and artifact bytes, authenticated evaluator
release and result bundles, deterministic schedules, and recoverable hash-chained
journals. It intentionally has no provider transport, adjudication, or decision
command.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "benchmarks" / "v4" / "manifest.json"
DEFAULT_STATUS = ROOT / "benchmarks" / "v4" / "STATUS.json"
PROTOCOL_ID = "vidux-cockpit-v4"
SIGNATURE_NAMESPACE = "vidux-benchmark-v4"
PAIR_IDS = ("anthropic_claude", "openai_codex")
ARM_IDS = ("claude_native", "claude_vidux", "codex_native", "codex_vidux")
SCENARIO_IDS = (
    "durable_state",
    "interruption_recovery",
    "cross_project_prioritization",
    "proof_inspection",
)
METRIC_IDS = ("elapsed_ms", "tokens", "cost_microusd", "operator_touches")
RECEIPT_DIGEST_IDS = (
    "provider_receipt_sha256",
    "runner_receipt_sha256",
    "transcript_receipt_sha256",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
FIXTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
RUN_ID_RE = re.compile(r"^run-[0-9a-f]{20}$")
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_JSON_DEPTH = 32

MANIFEST_KEYS = {
    "schema_version",
    "protocol_id",
    "status",
    "created_at",
    "amendment_policy",
    "evidence_modes",
    "provider_pairs",
    "arms",
    "scenario_classes",
    "schedule_contract",
    "budgets",
    "fixture_contract",
    "release_contract",
    "artifact_contract",
    "evaluator_contract",
    "measurement_contract",
    "adjudication_contract",
    "exclusion_policy",
    "decision_procedure",
    "decision_rules",
    "journal_contract",
    "preserved_experiment_contract",
    "transport_contract",
}
STATUS_KEYS = {
    "schema_version",
    "protocol_id",
    "status",
    "runnable",
    "manifest_digest",
    "created_at",
    "provider_transport_enabled",
    "evaluator_registration_sha256",
    "claim_eligible",
    "verified_net_win_classes",
    "next_gate",
}
RELEASE_KEYS = {
    "schema_version",
    "release_id",
    "protocol_id",
    "protocol_digest",
    "evidence_mode",
    "randomization_seed",
    "evaluator_registration_sha256",
    "evaluator_release_receipt_sha256",
    "provider_profiles",
    "fixtures",
}
RELEASE_FIXTURE_KEYS = {
    "stage",
    "scenario_class",
    "fixture_id",
    "fixture_path",
    "fixture_sha256",
}
FIXTURE_KEYS = {
    "schema_version",
    "fixture_id",
    "stage",
    "scenario_class",
    "task_prompt",
    "workspace_snapshot",
    "execution_contract",
}
WORKSPACE_KEYS = {"artifact_sha256", "format"}
EXECUTION_KEYS = {
    "scenario_class",
    "required_state_transitions",
    "proof_requirements",
    "interruption",
}
INTERRUPTION_KEYS = {"trigger", "resume_entrypoint"}
REGISTRATION_KEYS = {
    "schema_version",
    "evaluator_id",
    "signature_scheme",
    "signature_namespace",
    "public_key_sha256",
    "implementation_sha256",
    "registered_at",
}
RELEASE_RECEIPT_KEYS = {
    "schema_version",
    "evaluator_registration_sha256",
    "release_core_sha256",
    "signature_sha256",
}
PROFILE_KEYS = {
    "schema_version",
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
}
SCHEDULE_KEYS = {
    "schema_version",
    "protocol_id",
    "protocol_digest",
    "release_id",
    "release_core_sha256",
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
    "provider_profile_sha256",
    "budget",
}
RUNNER_RESULT_KEYS = {
    "schema_version",
    "protocol_id",
    "protocol_digest",
    "release_core_sha256",
    "schedule_digest",
    "run_id",
    "attempt_number",
    "attempt_id",
    "status",
    "metrics",
    *RECEIPT_DIGEST_IDS,
}
EVALUATOR_RESULT_KEYS = {
    "schema_version",
    "protocol_id",
    "protocol_digest",
    "release_core_sha256",
    "schedule_digest",
    "run_id",
    "attempt_number",
    "attempt_id",
    "fixture_id",
    "runner_result_sha256",
    "evaluator_run_sha256",
    "checks",
    "resume_transitions",
    "forbidden_action",
}
CHECK_KEYS = {"id", "required", "passed", "evidence_sha256"}
RESUME_KEYS = {"missed", "repeated", "invented"}
EVALUATOR_RESULT_RECEIPT_KEYS = {
    "schema_version",
    "evaluator_registration_sha256",
    "evaluator_result_sha256",
    "signature_sha256",
}
JOURNAL_KEYS = {
    "schema_version",
    "protocol_id",
    "schedule_digest",
    "sequence",
    "operation_id",
    "event",
    "run_id",
    "attempt_number",
    "attempt_id",
    "payload",
    "previous_event_sha256",
    "event_sha256",
}
JOURNAL_EVENTS = {
    "journal_initialized",
    "provider_dispatch_reserved",
    "provider_receipt_reconciled",
    "provider_retry_authorized",
    "journal_tail_recovered",
}
FROZEN_V3_BLOCK_DIGESTS = {
    "provider_pairs": "14127cf114fc0f0d0bdeed6be238f66f2edd910688f219af0eea2ad18c6310e8",
    "arms": "6faeab83be220c41057470f1798195529cf8fd37542cdd8460facf326e01d1b4",
    "scenario_classes": "ea47bc9fd4aed25984dee509417a2e8185bdc2a6609764f9785e2321a080e7a6",
    "schedule_contract": "f74405311817206f1239999b23502ad0275cc509e3c04d252ad3f791f8e18a05",
    "budgets": "2ef3cfd530f8c47c49fb5553a26792cafdb454e5bb39db0bfa331da6c5ec3746",
    "measurement_contract": "ca5f61b5858dba9d33a5e904935273b41561258038d8bc68d18b3c0ca8240bf8",
    "adjudication_contract": "23deb1c12ef3c14b38b9dde5012d80d61b658dc9e49f23568717afd941e37ae0",
    "exclusion_policy": "aa1080d09670b20d5d42f6342587bc39e1f8147ba72e566f8d23d06248b18629",
    "decision_procedure": "95570bb3279e6ee6ca0e43528d8105401534fc0bbba5ca601fc822c19fcf6d03",
    "decision_rules": "cbe5a22f704257f88b0f67be78bd014651509ff8278b1ee4d22336ff3f83395f",
}


class ValidationError(ValueError):
    """Raised when an integrity artifact violates the frozen preflight."""


def _reject_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON number {value!r} is forbidden")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key {key!r} is forbidden")
        result[key] = value
    return result


def _validate_json_value(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValidationError(f"JSON exceeds maximum depth {MAX_JSON_DEPTH}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError("non-finite JSON numbers are forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValidationError("JSON object keys must be strings")
            _validate_json_value(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _validate_json_value(child, depth=depth + 1)


def strict_json_loads(raw: str, *, label: str) -> Any:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ValidationError(f"{label} must be valid JSON: {error}") from error
    _validate_json_value(value)
    return value


def canonical_json(value: Any) -> bytes:
    _validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: Any, domain: str) -> str:
    return digest_bytes(f"vidux-v4:{domain}\0".encode("ascii") + canonical_json(value))


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
    root: Path,
    relative_path: Any,
    label: str,
    *,
    max_bytes: int,
) -> Iterator[int]:
    relative = _safe_relative_path(relative_path, label)
    if root.is_symlink():
        raise ValidationError(f"{label} root must not be a symlink")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        raise ValidationError(f"{label} root is unavailable: {error}") from error
    if not resolved_root.is_dir():
        raise ValidationError(f"{label} root must be a directory")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    current_fd = os.open(resolved_root, directory_flags)
    opened_directories = [current_fd]
    file_fd: int | None = None
    try:
        for part in relative.parts[:-1]:
            current_fd = os.open(part, directory_flags, dir_fd=current_fd)
            opened_directories.append(current_fd)
        file_fd = os.open(
            relative.parts[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current_fd,
        )
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError(f"{label} must be a single-link regular file")
        if info.st_size > max_bytes:
            raise ValidationError(f"{label} exceeds the {max_bytes}-byte limit")
        yield file_fd
    except OSError as error:
        raise ValidationError(f"{label} cannot be opened safely: {error}") from error
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for fd in reversed(opened_directories):
            os.close(fd)


def _read_fd(fd: int, *, max_bytes: int, label: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(f"{label} exceeds the {max_bytes}-byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def read_regular_bytes(path: Path, *, max_bytes: int, label: str) -> bytes:
    with _open_relative_regular(
        path.parent,
        path.name,
        label,
        max_bytes=max_bytes,
    ) as fd:
        return _read_fd(fd, max_bytes=max_bytes, label=label)


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    raw = read_regular_bytes(path, max_bytes=MAX_JSON_BYTES, label=label)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label} must be UTF-8 JSON") from error
    value = strict_json_loads(text, label=label)
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must contain a JSON object")
    return value


def resolve_artifact(root: Path, digest: str, label: str) -> bytes:
    if not _valid_sha(digest):
        raise ValidationError(f"{label} digest must be a lowercase SHA-256")
    with _open_relative_regular(root, digest, label, max_bytes=MAX_ARTIFACT_BYTES) as fd:
        raw = _read_fd(fd, max_bytes=MAX_ARTIFACT_BYTES, label=label)
    actual = digest_bytes(raw)
    if actual != digest:
        raise ValidationError(f"{label} bytes do not match digest {digest}")
    return raw


def _decode_json_artifact(raw: bytes, label: str) -> dict[str, Any]:
    if len(raw) > MAX_JSON_BYTES:
        raise ValidationError(f"{label} exceeds the JSON byte limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label} must be UTF-8 JSON") from error
    value = strict_json_loads(text, label=label)
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must contain a JSON object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(manifest) != MANIFEST_KEYS:
        errors.append("manifest must contain exactly the registered fields")
    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must equal 1")
    if manifest.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"manifest protocol_id must equal {PROTOCOL_ID}")
    if manifest.get("status") != "draft_integrity_preflight":
        errors.append("manifest status must remain draft_integrity_preflight")
    if not isinstance(manifest.get("created_at"), str) or not manifest.get("created_at"):
        errors.append("manifest created_at must be a non-empty string")
    if manifest.get("amendment_policy") != {
        "outcome_rule_changes_require_new_protocol_id": True,
        "threshold_changes_after_release_forbidden": True,
        "evaluator_registration_precedes_release": True,
        "provider_transport_requires_separate_review": True,
    }:
        errors.append("amendment_policy must equal the frozen v4 policy")
    if manifest.get("evidence_modes") != {
        "real": {
            "claim_eligible": True,
            "requires_authenticated_evaluator": True,
            "requires_resolved_artifacts": True,
        },
        "synthetic": {
            "claim_eligible": False,
            "requires_authenticated_evaluator": True,
            "requires_resolved_artifacts": True,
        },
    }:
        errors.append("evidence_modes must keep synthetic evidence authenticated and claim-ineligible")
    for key, expected_digest in FROZEN_V3_BLOCK_DIGESTS.items():
        actual = manifest.get(key)
        if digest_bytes(canonical_json(actual)) != expected_digest:
            errors.append(f"{key} must exactly preserve the frozen v3 outcome contract")
    expected_pairs = [
        {
            "id": "anthropic_claude",
            "provider": "anthropic",
            "runner_family": "claude_code",
            "native_arm": "claude_native",
            "vidux_arm": "claude_vidux",
            "profile_binding": "release_exact",
        },
        {
            "id": "openai_codex",
            "provider": "openai",
            "runner_family": "codex",
            "native_arm": "codex_native",
            "vidux_arm": "codex_vidux",
            "profile_binding": "release_exact",
        },
    ]
    if manifest.get("provider_pairs") != expected_pairs:
        errors.append("provider_pairs must preserve exact Claude and Codex matched arms")
    expected_scenarios = [
        {"id": scenario, "pilot_fixture_count": 1, "full_fixture_count": 12}
        for scenario in SCENARIO_IDS
    ]
    if manifest.get("scenario_classes") != expected_scenarios:
        errors.append("scenario_classes must preserve one pilot and twelve full fixtures each")
    if manifest.get("fixture_contract") != {
        "release_fixture_count": 52,
        "public_fixture_schema_version": 1,
        "workspace_format": "tar_posix_ustar_v1",
        "task_prompt_max_utf8_bytes": 16384,
        "workspace_snapshot_content_addressed": True,
        "scenario_specific_execution_contract_required": True,
        "pilot_and_full_bytes_disjoint": True,
    }:
        errors.append("fixture_contract must equal the schema-validated content-addressed policy")
    if manifest.get("release_contract") != {
        "stages": ["pilot", "full"],
        "provider_profile_fields": [
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
        ],
        "fixture_fields": [
            "stage",
            "scenario_class",
            "fixture_id",
            "fixture_path",
            "fixture_sha256",
        ],
        "workspace_snapshot_binding": "per_fixture_content_addressed_artifact",
        "hidden_evaluator_material": "external_to_public_release_and_arm_packets",
    }:
        errors.append("release_contract must bind exact inference, runner, and fixture bytes")
    if manifest.get("artifact_contract") != {
        "layout": "flat_sha256_filename",
        "hash": "sha256",
        "single_link_regular_files_only": True,
        "symlinks_forbidden": True,
        "required_runtime_receipts": [
            "provider", "runner", "transcript", "evaluator_run", "check_evidence"
        ],
        "provider_metrics_source": "verified_provider_receipt_artifact",
    }:
        errors.append("artifact_contract must require resolved single-link receipt bytes")
    if manifest.get("evaluator_contract") != {
        "registration_precedes_release": True,
        "signature_scheme": "openssh_sshsig_ed25519",
        "signature_namespace": SIGNATURE_NAMESPACE,
        "release_signature_covers": "canonical_release_core_v1",
        "result_signature_covers": "canonical_evaluator_result_v1",
        "unsigned_or_unregistered_results_claim_eligible": False,
    }:
        errors.append("evaluator_contract must equal the authenticated OpenSSH policy")
    if manifest.get("journal_contract") != {
        "format": "canonical_hash_chained_jsonl_v1",
        "logical_key_fields": ["run_id", "attempt_number"],
        "exclusive_sidecar_lock_required": True,
        "duplicate_operation_id_policy": "reject",
        "torn_tail_policy": "truncate_only_unterminated_final_fragment_then_append_recovery_receipt",
        "terminated_invalid_row_policy": "reject",
        "recovery_receipt_event": "journal_tail_recovered",
        "dispatch_reservation_event": "provider_dispatch_reserved",
        "receipt_reconciliation_event": "provider_receipt_reconciled",
        "retry_authorization_event": "provider_retry_authorized",
        "fsync_before_publish": True,
        "ambiguous_provider_dispatch_policy": "reconcile_receipt_never_auto_reinvoke",
    }:
        errors.append("journal_contract must preserve bounded recovery and dispatch reconciliation")
    if manifest.get("preserved_experiment_contract") != {
        "source_protocol_id": "vidux-cockpit-v3",
        "embedded_outcome_contracts": [
            "provider_pairs",
            "arms",
            "scenario_classes",
            "schedule_contract",
            "budgets",
            "measurement_contract",
            "adjudication_contract",
            "exclusion_policy",
            "decision_procedure",
            "decision_rules",
        ],
        "intentional_non_outcome_deltas": [
            "authenticated_release_and_evaluator_results",
            "resolved_content_addressed_artifacts",
            "per_fixture_workspace_binding",
            "recoverable_hash_chained_journal",
            "dispatch_reservation_and_receipt_reconciliation",
        ],
    }:
        errors.append("preserved_experiment_contract must enumerate outcome identity and v4 deltas")
    if manifest.get("transport_contract") != {
        "provider_transport_implemented": False,
        "schedule_command_available": True,
        "evaluator_result_check_available": True,
        "adjudication_command_available": False,
        "decision_command_available": False,
    }:
        errors.append("transport_contract must expose only pre-spend integrity commands")
    return errors


def validate_status(status: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(status) != STATUS_KEYS:
        errors.append("status must contain exactly the registered fields")
    registration_digest = status.get("evaluator_registration_sha256")
    if registration_digest is not None and not _valid_sha(registration_digest):
        errors.append("status evaluator_registration_sha256 must be null or a lowercase SHA-256")
    expected = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "status": "draft_integrity_preflight",
        "runnable": False,
        "manifest_digest": digest_json(manifest, "manifest"),
        "created_at": manifest.get("created_at"),
        "provider_transport_enabled": False,
        "claim_eligible": False,
        "verified_net_win_classes": 0,
        "next_gate": (
            "freeze_authenticated_external_evaluator_registration_then_review_runner"
            if registration_digest is None
            else "validate_authenticated_external_evaluator_release_then_review_runner"
        ),
    }
    for key, expected_value in expected.items():
        if status.get(key) != expected_value:
            errors.append(f"status {key} must equal {expected_value!r}")
    return errors


def release_core(release: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in release.items()
        if key != "evaluator_release_receipt_sha256"
    }


def release_core_bytes(release: dict[str, Any]) -> bytes:
    return b"vidux-v4:release-core\0" + canonical_json(release_core(release))


def release_core_digest(release: dict[str, Any]) -> str:
    return digest_bytes(release_core_bytes(release))


def validate_release(release: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(release) != RELEASE_KEYS:
        errors.append("release must contain exactly the registered public fields")
    if release.get("schema_version") != 1:
        errors.append("release schema_version must equal 1")
    if release.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"release protocol_id must equal {PROTOCOL_ID}")
    if release.get("protocol_digest") != digest_json(manifest, "manifest"):
        errors.append("release protocol_digest must bind the v4 manifest")
    if not isinstance(release.get("release_id"), str) or ID_RE.fullmatch(
        release.get("release_id", "")
    ) is None:
        errors.append("release_id must be a normalized opaque id")
    if release.get("evidence_mode") not in {"real", "synthetic"}:
        errors.append("evidence_mode must equal real or synthetic")
    for key in (
        "randomization_seed",
        "evaluator_registration_sha256",
        "evaluator_release_receipt_sha256",
    ):
        if not _valid_sha(release.get(key)):
            errors.append(f"release {key} must be a lowercase SHA-256")
    profiles = release.get("provider_profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(PAIR_IDS):
        errors.append("provider_profiles must bind exactly both provider pairs")
    elif not all(_valid_sha(value) for value in profiles.values()):
        errors.append("provider profile references must be lowercase SHA-256 digests")
    fixtures = release.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 52:
        errors.append("release must contain exactly 52 fixtures")
        return errors
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()
    counts = {(stage, scenario): 0 for stage in ("pilot", "full") for scenario in SCENARIO_IDS}
    stage_hashes = {"pilot": set(), "full": set()}
    for index, fixture in enumerate(fixtures):
        label = f"fixture entry {index}"
        if not isinstance(fixture, dict) or set(fixture) != RELEASE_FIXTURE_KEYS:
            errors.append(f"{label} must contain exactly the release fixture fields")
            continue
        stage = fixture.get("stage")
        scenario = fixture.get("scenario_class")
        fixture_id = fixture.get("fixture_id")
        path = fixture.get("fixture_path")
        digest = fixture.get("fixture_sha256")
        if stage not in {"pilot", "full"}:
            errors.append(f"{label} stage must equal pilot or full")
        if scenario not in SCENARIO_IDS:
            errors.append(f"{label} scenario_class is invalid")
        if isinstance(stage, str) and scenario in SCENARIO_IDS and stage in {"pilot", "full"}:
            counts[(stage, scenario)] += 1
        if not isinstance(fixture_id, str) or FIXTURE_ID_RE.fullmatch(fixture_id) is None:
            errors.append(f"{label} fixture_id is invalid")
        elif fixture_id in seen_ids:
            errors.append(f"{label} fixture_id is duplicated")
        else:
            seen_ids.add(fixture_id)
        try:
            normalized_path = _safe_relative_path(path, f"{label} fixture_path").as_posix()
            if normalized_path != path:
                errors.append(f"{label} fixture_path must be normalized")
            elif normalized_path in seen_paths:
                errors.append(f"{label} fixture_path is duplicated")
            else:
                seen_paths.add(normalized_path)
        except ValidationError as error:
            errors.append(str(error))
        if not _valid_sha(digest):
            errors.append(f"{label} fixture_sha256 must be a lowercase SHA-256")
        elif digest in seen_hashes:
            errors.append(f"{label} fixture bytes must be unique")
        else:
            seen_hashes.add(digest)
            if stage in stage_hashes:
                stage_hashes[stage].add(digest)
    for scenario in SCENARIO_IDS:
        if counts[("pilot", scenario)] != 1:
            errors.append(f"release must contain exactly one pilot {scenario} fixture")
        if counts[("full", scenario)] != 12:
            errors.append(f"release must contain exactly twelve full {scenario} fixtures")
    if stage_hashes["pilot"] & stage_hashes["full"]:
        errors.append("pilot and full fixture bytes must be disjoint")
    return errors


def _bounded_string_list(value: Any, label: str, *, maximum: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list) or not value or len(value) > maximum:
        return [f"{label} must be a non-empty list of at most {maximum} strings"]
    if not all(isinstance(item, str) and 0 < len(item.encode("utf-8")) <= 1024 for item in value):
        errors.append(f"{label} entries must be non-empty strings of at most 1024 UTF-8 bytes")
    return errors


def validate_fixture(
    fixture: dict[str, Any],
    release_entry: dict[str, Any],
    manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if set(fixture) != FIXTURE_KEYS:
        errors.append("public fixture must contain exactly the registered fields")
    if fixture.get("schema_version") != 1:
        errors.append("public fixture schema_version must equal 1")
    for key in ("fixture_id", "stage", "scenario_class"):
        if fixture.get(key) != release_entry.get(key):
            errors.append(f"public fixture {key} must match its release entry")
    prompt = fixture.get("task_prompt")
    max_prompt = manifest["fixture_contract"]["task_prompt_max_utf8_bytes"]
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > max_prompt:
        errors.append(f"task_prompt must be non-empty and at most {max_prompt} UTF-8 bytes")
    workspace = fixture.get("workspace_snapshot")
    if not isinstance(workspace, dict) or set(workspace) != WORKSPACE_KEYS:
        errors.append("workspace_snapshot must contain exactly artifact_sha256 and format")
    else:
        if not _valid_sha(workspace.get("artifact_sha256")):
            errors.append("workspace_snapshot artifact_sha256 must be a lowercase SHA-256")
        if workspace.get("format") != manifest["fixture_contract"]["workspace_format"]:
            errors.append("workspace_snapshot format must equal the frozen workspace format")
    execution = fixture.get("execution_contract")
    if not isinstance(execution, dict) or set(execution) != EXECUTION_KEYS:
        errors.append("execution_contract must contain exactly the registered fields")
        return errors
    scenario = release_entry.get("scenario_class")
    if execution.get("scenario_class") != scenario:
        errors.append("execution_contract scenario_class must match the release entry")
    errors.extend(
        _bounded_string_list(
            execution.get("required_state_transitions"),
            "required_state_transitions",
            maximum=32,
        )
    )
    errors.extend(
        _bounded_string_list(
            execution.get("proof_requirements"),
            "proof_requirements",
            maximum=16,
        )
    )
    interruption = execution.get("interruption")
    if scenario == "interruption_recovery":
        if not isinstance(interruption, dict) or set(interruption) != INTERRUPTION_KEYS:
            errors.append("interruption_recovery fixtures require trigger and resume_entrypoint")
        elif not all(
            isinstance(interruption.get(key), str) and interruption.get(key).strip()
            for key in INTERRUPTION_KEYS
        ):
            errors.append("interruption trigger and resume_entrypoint must be non-empty strings")
    elif interruption is not None:
        errors.append("only interruption_recovery fixtures may define interruption")
    return errors


def validate_registration(registration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(registration) != REGISTRATION_KEYS:
        errors.append("evaluator registration must contain exactly the registered fields")
    if registration.get("schema_version") != 1:
        errors.append("evaluator registration schema_version must equal 1")
    evaluator_id = registration.get("evaluator_id")
    if not isinstance(evaluator_id, str) or ID_RE.fullmatch(evaluator_id) is None:
        errors.append("evaluator_id must be a normalized opaque id")
    if registration.get("signature_scheme") != "openssh_sshsig_ed25519":
        errors.append("evaluator signature_scheme must equal openssh_sshsig_ed25519")
    if registration.get("signature_namespace") != SIGNATURE_NAMESPACE:
        errors.append(f"evaluator signature_namespace must equal {SIGNATURE_NAMESPACE}")
    for key in ("public_key_sha256", "implementation_sha256"):
        if not _valid_sha(registration.get(key)):
            errors.append(f"evaluator {key} must be a lowercase SHA-256")
    if not isinstance(registration.get("registered_at"), str) or not registration.get("registered_at"):
        errors.append("evaluator registered_at must be a non-empty string")
    return errors


def validate_release_receipt(receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(receipt) != RELEASE_RECEIPT_KEYS:
        errors.append("evaluator release receipt must contain exactly the registered fields")
    if receipt.get("schema_version") != 1:
        errors.append("evaluator release receipt schema_version must equal 1")
    for key in (
        "evaluator_registration_sha256",
        "release_core_sha256",
        "signature_sha256",
    ):
        if not _valid_sha(receipt.get(key)):
            errors.append(f"evaluator release receipt {key} must be a lowercase SHA-256")
    return errors


def validate_profile(profile: dict[str, Any], pair_id: str) -> list[str]:
    errors: list[str] = []
    if set(profile) != PROFILE_KEYS:
        errors.append(f"{pair_id} provider profile must contain exactly the registered fields")
    if profile.get("schema_version") != 1:
        errors.append(f"{pair_id} provider profile schema_version must equal 1")
    if profile.get("pair_id") != pair_id:
        errors.append(f"{pair_id} provider profile pair_id must match its release binding")
    expected = {
        "anthropic_claude": ("anthropic", "claude_code"),
        "openai_codex": ("openai", "codex"),
    }[pair_id]
    if (profile.get("provider"), profile.get("runner_family")) != expected:
        errors.append(f"{pair_id} provider and runner family must remain matched")
    for key in (
        "requested_model_id",
        "resolved_model_id",
        "provider_api_surface",
        "runtime_version",
    ):
        if not isinstance(profile.get(key), str) or not profile.get(key):
            errors.append(f"{pair_id} {key} must be a non-empty string")
    for key in PROFILE_KEYS - {
        "schema_version",
        "pair_id",
        "provider",
        "runner_family",
        "requested_model_id",
        "resolved_model_id",
        "provider_api_surface",
        "runtime_version",
    }:
        if not _valid_sha(profile.get(key)):
            errors.append(f"{pair_id} {key} must be a lowercase SHA-256")
    return errors


def _validate_public_key(raw: bytes) -> str:
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise ValidationError("evaluator public key must be ASCII OpenSSH text") from error
    parts = value.split()
    if len(parts) < 2 or parts[0] != "ssh-ed25519" or "\n" in value or "\r" in value:
        raise ValidationError("evaluator public key must be one ssh-ed25519 OpenSSH key")
    return " ".join(parts[:2])


def verify_sshsig(
    public_key: bytes,
    evaluator_id: str,
    signature: bytes,
    message: bytes,
    *,
    label: str,
) -> None:
    if shutil.which("ssh-keygen") is None:
        raise ValidationError("OpenSSH ssh-keygen verifier is unavailable")
    key = _validate_public_key(public_key)
    with tempfile.TemporaryDirectory(prefix="vidux-v4-verify-") as temp:
        root = Path(temp)
        allowed = root / "allowed_signers"
        signature_path = root / "message.sig"
        allowed.write_text(f"{evaluator_id} {key}\n", encoding="ascii")
        signature_path.write_bytes(signature)
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                evaluator_id,
                "-n",
                SIGNATURE_NAMESPACE,
                "-s",
                str(signature_path),
            ],
            input=message,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationError(f"{label} signature verification failed: {detail}")


def validate_release_bundle(
    release: dict[str, Any],
    manifest: dict[str, Any],
    *,
    fixture_root: Path,
    artifact_root: Path,
    expected_registration_sha256: str | None,
) -> list[str]:
    errors = validate_release(release, manifest)
    if errors:
        return errors
    registration_digest = release["evaluator_registration_sha256"]
    if expected_registration_sha256 is None:
        errors.append("an evaluator registration must be frozen before release validation")
    elif registration_digest != expected_registration_sha256:
        errors.append("release evaluator registration does not match the preregistered digest")
    try:
        registration = _decode_json_artifact(
            resolve_artifact(artifact_root, registration_digest, "evaluator registration"),
            "evaluator registration",
        )
        errors.extend(validate_registration(registration))
        public_key = resolve_artifact(
            artifact_root,
            registration.get("public_key_sha256", ""),
            "evaluator public key",
        )
        resolve_artifact(
            artifact_root,
            registration.get("implementation_sha256", ""),
            "evaluator implementation",
        )
        for pair_id, profile_digest in release["provider_profiles"].items():
            profile = _decode_json_artifact(
                resolve_artifact(artifact_root, profile_digest, f"{pair_id} provider profile"),
                f"{pair_id} provider profile",
            )
            profile_errors = validate_profile(profile, pair_id)
            errors.extend(profile_errors)
            if not profile_errors:
                for key in (
                    "inference_profile_sha256",
                    "runner_binary_sha256",
                    "runner_args_sha256",
                    "permission_profile_sha256",
                    "tool_surface_sha256",
                    "base_prompt_sha256",
                    "system_instructions_sha256",
                    "developer_instructions_sha256",
                ):
                    resolve_artifact(
                        artifact_root,
                        profile[key],
                        f"{pair_id} {key.removesuffix('_sha256')}",
                    )
        for entry in release["fixtures"]:
            relative = entry["fixture_path"]
            with _open_relative_regular(
                fixture_root,
                relative,
                f"fixture {entry['fixture_id']}",
                max_bytes=MAX_JSON_BYTES,
            ) as fd:
                raw_fixture = _read_fd(
                    fd,
                    max_bytes=MAX_JSON_BYTES,
                    label=f"fixture {entry['fixture_id']}",
                )
            if digest_bytes(raw_fixture) != entry["fixture_sha256"]:
                errors.append(f"fixture {entry['fixture_id']} bytes do not match the release digest")
                continue
            fixture = _decode_json_artifact(raw_fixture, f"fixture {entry['fixture_id']}")
            fixture_errors = validate_fixture(fixture, entry, manifest)
            errors.extend(f"fixture {entry['fixture_id']}: {error}" for error in fixture_errors)
            workspace = fixture.get("workspace_snapshot")
            if isinstance(workspace, dict) and _valid_sha(workspace.get("artifact_sha256")):
                resolve_artifact(
                    artifact_root,
                    workspace["artifact_sha256"],
                    f"fixture {entry['fixture_id']} workspace snapshot",
                )
        receipt = _decode_json_artifact(
            resolve_artifact(
                artifact_root,
                release["evaluator_release_receipt_sha256"],
                "evaluator release receipt",
            ),
            "evaluator release receipt",
        )
        errors.extend(validate_release_receipt(receipt))
        if receipt.get("evaluator_registration_sha256") != registration_digest:
            errors.append("evaluator release receipt must bind the release registration")
        if receipt.get("release_core_sha256") != release_core_digest(release):
            errors.append("evaluator release receipt must bind the canonical release core")
        signature = resolve_artifact(
            artifact_root,
            receipt.get("signature_sha256", ""),
            "evaluator release signature",
        )
        if not errors:
            verify_sshsig(
                public_key,
                registration["evaluator_id"],
                signature,
                release_core_bytes(release),
                label="evaluator release",
            )
    except ValidationError as error:
        errors.append(str(error))
    return errors


def build_schedule(
    manifest: dict[str, Any],
    release: dict[str, Any],
    *,
    fixture_root: Path,
    artifact_root: Path,
    expected_registration_sha256: str | None,
) -> dict[str, Any]:
    errors = validate_release_bundle(
        release,
        manifest,
        fixture_root=fixture_root,
        artifact_root=artifact_root,
        expected_registration_sha256=expected_registration_sha256,
    )
    if errors:
        raise ValidationError("schedule inputs are invalid: " + "; ".join(errors))
    arms = {arm["id"]: arm for arm in manifest["arms"]}
    protocol_digest = digest_json(manifest, "manifest")
    signed_release_digest = release_core_digest(release)
    ranked: list[tuple[int, str, str, dict[str, Any]]] = []
    fixtures = sorted(
        release["fixtures"],
        key=lambda fixture: (
            0 if fixture["stage"] == "pilot" else 1,
            fixture["scenario_class"],
            fixture["fixture_id"],
        ),
    )
    for fixture in fixtures:
        stage = fixture["stage"]
        for arm_id in ARM_IDS:
            arm = arms[arm_id]
            canonical_key = "|".join(
                (
                    stage,
                    fixture["scenario_class"],
                    fixture["fixture_id"],
                    arm_id,
                    "1",
                )
            )
            rank = digest_bytes(
                b"vidux-v4:schedule-rank\0"
                + release["randomization_seed"].encode("ascii")
                + b"\0"
                + canonical_key.encode("utf-8")
            )
            run_hash = digest_bytes(
                b"vidux-v4:run\0"
                + protocol_digest.encode("ascii")
                + b"\0"
                + signed_release_digest.encode("ascii")
                + b"\0"
                + canonical_key.encode("utf-8")
            )
            pair_id = arm["pair_id"]
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
                "provider_profile_sha256": release["provider_profiles"][pair_id],
                "budget": dict(manifest["budgets"][stage]["per_run"]),
            }
            ranked.append((0 if stage == "pilot" else 1, rank, canonical_key, run))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    runs: list[dict[str, Any]] = []
    for sequence, (_stage, _rank, _key, value) in enumerate(ranked):
        run = dict(value)
        run["sequence"] = sequence
        runs.append(run)
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": protocol_digest,
        "release_id": release["release_id"],
        "release_core_sha256": signed_release_digest,
        "schedule_seed_digest": digest_bytes(
            b"vidux-v4:schedule-seed\0" + release["randomization_seed"].encode("ascii")
        ),
        "stage_budgets": {
            stage: dict(manifest["budgets"][stage]["global"])
            for stage in ("pilot", "full")
        },
        "protocol_budget": dict(manifest["budgets"]["protocol"]),
        "max_infra_attempts": 2,
        "runs": runs,
    }


def validate_schedule(
    schedule: dict[str, Any],
    manifest: dict[str, Any],
    release: dict[str, Any],
    *,
    fixture_root: Path,
    artifact_root: Path,
    expected_registration_sha256: str | None,
) -> list[str]:
    errors: list[str] = []
    if set(schedule) != SCHEDULE_KEYS:
        errors.append("schedule must contain exactly the deterministic v4 fields")
    try:
        expected = build_schedule(
            manifest,
            release,
            fixture_root=fixture_root,
            artifact_root=artifact_root,
            expected_registration_sha256=expected_registration_sha256,
        )
    except ValidationError as error:
        return [str(error)]
    if schedule != expected:
        errors.append("schedule must exactly match deterministic complete regeneration")
    runs = schedule.get("runs")
    if not isinstance(runs, list) or len(runs) != 208:
        errors.append("schedule must contain exactly 208 runs")
        return errors
    if sum(run.get("stage") == "pilot" for run in runs if isinstance(run, dict)) != 16:
        errors.append("schedule must contain exactly 16 pilot runs")
    if sum(run.get("stage") == "full" for run in runs if isinstance(run, dict)) != 192:
        errors.append("schedule must contain exactly 192 full runs")
    seen: set[str] = set()
    for run in runs:
        if not isinstance(run, dict) or set(run) != RUN_KEYS:
            errors.append("each schedule run must contain exactly the frozen run fields")
            continue
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
            errors.append("schedule run_id must be an opaque SHA-256 prefix")
        elif run_id in seen:
            errors.append(f"duplicate schedule run_id: {run_id}")
        else:
            seen.add(run_id)
    return errors


def schedule_digest(schedule: dict[str, Any]) -> str:
    return digest_json(schedule, "schedule")


def attempt_id_for(run_id: str, attempt_number: int) -> str:
    if RUN_ID_RE.fullmatch(run_id) is None or attempt_number < 1:
        raise ValidationError("attempt identity requires a valid run_id and positive number")
    digest = digest_bytes(
        b"vidux-v4:attempt\0"
        + run_id.encode("ascii")
        + b"\0"
        + str(attempt_number).encode("ascii")
    )
    return f"attempt-{digest[:20]}"


def dispatch_id_for(schedule_sha256: str, run_id: str, attempt_number: int) -> str:
    if not _valid_sha(schedule_sha256):
        raise ValidationError("dispatch identity requires a valid schedule digest")
    attempt_id = attempt_id_for(run_id, attempt_number)
    digest = digest_bytes(
        b"vidux-v4:dispatch\0"
        + schedule_sha256.encode("ascii")
        + b"\0"
        + attempt_id.encode("ascii")
    )
    return f"dispatch-{digest[:20]}"


def _metric_errors(
    metrics: Any,
    budget: dict[str, Any] | None,
    label: str,
) -> list[str]:
    if not isinstance(metrics, dict) or set(metrics) != set(METRIC_IDS):
        return [f"{label} metrics must contain exactly {', '.join(METRIC_IDS)}"]
    errors: list[str] = []
    for metric in METRIC_IDS:
        value = metrics.get(metric)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{label} {metric} must be a non-negative integer")
        elif budget is not None and value > budget[metric]:
            errors.append(f"{label} {metric} exceeds the frozen run budget")
    return errors


def validate_runner_result(
    result: dict[str, Any],
    schedule: dict[str, Any],
    *,
    artifact_root: Path,
) -> list[str]:
    errors: list[str] = []
    if set(result) != RUNNER_RESULT_KEYS:
        errors.append("runner result must contain exactly the authenticated result fields")
    if result.get("schema_version") != 1 or result.get("protocol_id") != PROTOCOL_ID:
        errors.append("runner result must bind the v4 schema and protocol")
    if result.get("protocol_digest") != schedule.get("protocol_digest"):
        errors.append("runner result protocol_digest must bind the schedule")
    if result.get("release_core_sha256") != schedule.get("release_core_sha256"):
        errors.append("runner result must bind the signed release core")
    if result.get("schedule_digest") != schedule_digest(schedule):
        errors.append("runner result must bind the complete schedule")
    run = next(
        (item for item in schedule.get("runs", []) if item.get("run_id") == result.get("run_id")),
        None,
    )
    if run is None:
        errors.append("runner result run_id must exist in the schedule")
    attempt_number = result.get("attempt_number")
    if (
        not isinstance(attempt_number, int)
        or isinstance(attempt_number, bool)
        or not 1 <= attempt_number <= schedule.get("max_infra_attempts", 0)
    ):
        errors.append("runner result attempt_number must be within the frozen attempt ceiling")
    elif run is not None and result.get("attempt_id") != attempt_id_for(run["run_id"], attempt_number):
        errors.append("runner result attempt_id must be schedule-derived")
    if result.get("status") not in {
        "runner_completed",
        "runner_failed",
        "budget_exhausted",
        "infrastructure_exhausted",
    }:
        errors.append("runner result status must be a frozen terminal status")
    if run is not None:
        errors.extend(_metric_errors(result.get("metrics"), run["budget"], "runner result"))
    for key in RECEIPT_DIGEST_IDS:
        digest = result.get(key)
        if not _valid_sha(digest):
            errors.append(f"runner result {key} must be a lowercase SHA-256")
        else:
            try:
                resolve_artifact(artifact_root, digest, key.removesuffix("_sha256"))
            except ValidationError as error:
                errors.append(str(error))
    return errors


def evaluator_result_bytes(result: dict[str, Any]) -> bytes:
    return b"vidux-v4:evaluator-result\0" + canonical_json(result)


def validate_evaluator_result(
    result: dict[str, Any],
    schedule: dict[str, Any],
    runner_result: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if set(result) != EVALUATOR_RESULT_KEYS:
        errors.append("evaluator result must contain exactly the authenticated result fields")
    if result.get("schema_version") != 1 or result.get("protocol_id") != PROTOCOL_ID:
        errors.append("evaluator result must bind the v4 schema and protocol")
    for key in ("protocol_digest", "release_core_sha256", "schedule_digest", "run_id", "attempt_number", "attempt_id"):
        expected = (
            schedule.get(key)
            if key in {"protocol_digest", "release_core_sha256"}
            else schedule_digest(schedule)
            if key == "schedule_digest"
            else runner_result.get(key)
        )
        if result.get(key) != expected:
            errors.append(f"evaluator result {key} must match its bound runner and schedule")
    run = next(
        (item for item in schedule.get("runs", []) if item.get("run_id") == result.get("run_id")),
        None,
    )
    if run is not None and result.get("fixture_id") != run.get("fixture_id"):
        errors.append("evaluator result fixture_id must match the scheduled run")
    expected_runner_digest = digest_bytes(canonical_json(runner_result))
    if result.get("runner_result_sha256") != expected_runner_digest:
        errors.append("evaluator result must bind the exact canonical runner result bytes")
    if not _valid_sha(result.get("evaluator_run_sha256")):
        errors.append("evaluator_run_sha256 must be a lowercase SHA-256")
    checks = result.get("checks")
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
            if not isinstance(check.get("required"), bool) or not isinstance(check.get("passed"), bool):
                errors.append("evaluator check required and passed must be booleans")
            if check.get("required") is True:
                required_count += 1
            if not _valid_sha(check.get("evidence_sha256")):
                errors.append("evaluator check evidence_sha256 must be a lowercase SHA-256")
    if required_count == 0:
        errors.append("evaluator result must contain at least one required check")
    transitions = result.get("resume_transitions")
    if not isinstance(transitions, dict) or set(transitions) != RESUME_KEYS:
        errors.append("resume_transitions must contain exactly missed, repeated, and invented")
    else:
        for key in RESUME_KEYS:
            value = transitions.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"resume_transitions {key} must be a non-negative integer")
    if not isinstance(result.get("forbidden_action"), bool):
        errors.append("forbidden_action must be a boolean")
    return errors


def validate_evaluator_result_bundle(
    receipt: dict[str, Any],
    schedule: dict[str, Any],
    release: dict[str, Any],
    manifest: dict[str, Any],
    *,
    fixture_root: Path,
    artifact_root: Path,
    expected_registration_sha256: str | None,
) -> list[str]:
    errors = validate_schedule(
        schedule,
        manifest,
        release,
        fixture_root=fixture_root,
        artifact_root=artifact_root,
        expected_registration_sha256=expected_registration_sha256,
    )
    if set(receipt) != EVALUATOR_RESULT_RECEIPT_KEYS:
        errors.append("evaluator result receipt must contain exactly the registered fields")
        return errors
    if receipt.get("schema_version") != 1:
        errors.append("evaluator result receipt schema_version must equal 1")
    for key in (
        "evaluator_registration_sha256",
        "evaluator_result_sha256",
        "signature_sha256",
    ):
        if not _valid_sha(receipt.get(key)):
            errors.append(f"evaluator result receipt {key} must be a lowercase SHA-256")
    registration_digest = receipt.get("evaluator_registration_sha256")
    if registration_digest != release.get("evaluator_registration_sha256"):
        errors.append("evaluator result receipt must bind the release evaluator registration")
    if registration_digest != expected_registration_sha256:
        errors.append("evaluator result receipt must bind the preregistered evaluator identity")
    if errors:
        return errors
    try:
        registration = _decode_json_artifact(
            resolve_artifact(artifact_root, registration_digest, "evaluator registration"),
            "evaluator registration",
        )
        registration_errors = validate_registration(registration)
        if registration_errors:
            return registration_errors
        public_key = resolve_artifact(
            artifact_root,
            registration["public_key_sha256"],
            "evaluator public key",
        )
        resolve_artifact(
            artifact_root,
            registration["implementation_sha256"],
            "evaluator implementation",
        )
        raw_evaluator = resolve_artifact(
            artifact_root,
            receipt["evaluator_result_sha256"],
            "evaluator result",
        )
        evaluator_result = _decode_json_artifact(raw_evaluator, "evaluator result")
        if raw_evaluator != canonical_json(evaluator_result):
            errors.append("evaluator result artifact must use canonical JSON bytes")
        raw_runner = resolve_artifact(
            artifact_root,
            evaluator_result.get("runner_result_sha256", ""),
            "runner result",
        )
        runner_result = _decode_json_artifact(raw_runner, "runner result")
        if raw_runner != canonical_json(runner_result):
            errors.append("runner result artifact must use canonical JSON bytes")
        errors.extend(validate_runner_result(runner_result, schedule, artifact_root=artifact_root))
        errors.extend(validate_evaluator_result(evaluator_result, schedule, runner_result))
        if _valid_sha(evaluator_result.get("evaluator_run_sha256")):
            resolve_artifact(
                artifact_root,
                evaluator_result["evaluator_run_sha256"],
                "evaluator run receipt",
            )
        checks = evaluator_result.get("checks")
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, dict) and _valid_sha(check.get("evidence_sha256")):
                    resolve_artifact(
                        artifact_root,
                        check["evidence_sha256"],
                        f"evaluator check {check.get('id', 'unknown')} evidence",
                    )
        signature = resolve_artifact(
            artifact_root,
            receipt["signature_sha256"],
            "evaluator result signature",
        )
        if not errors:
            verify_sshsig(
                public_key,
                registration["evaluator_id"],
                signature,
                evaluator_result_bytes(evaluator_result),
                label="evaluator result",
            )
    except ValidationError as error:
        errors.append(str(error))
    return errors


def claim_eligible(
    evidence_mode: str,
    status: dict[str, Any],
    manifest: dict[str, Any],
    *,
    bundle_errors: list[str],
) -> bool:
    return bool(
        evidence_mode == "real"
        and not bundle_errors
        and not validate_manifest(manifest)
        and not validate_status(status, manifest)
        and status.get("runnable") is True
        and status.get("provider_transport_enabled") is True
        and status.get("claim_eligible") is True
        and _valid_sha(status.get("evaluator_registration_sha256"))
    )


def readiness(
    manifest: dict[str, Any],
    status: dict[str, Any],
    *,
    release: dict[str, Any] | None = None,
    fixture_root: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    gates = validate_manifest(manifest) + validate_status(status, manifest)
    bundle_errors: list[str] = []
    if release is None:
        gates.append("authenticated external evaluator release is required")
    elif fixture_root is None or artifact_root is None:
        gates.append("fixture and artifact roots are required for byte verification")
    else:
        bundle_errors = validate_release_bundle(
            release,
            manifest,
            fixture_root=fixture_root,
            artifact_root=artifact_root,
            expected_registration_sha256=status.get("evaluator_registration_sha256"),
        )
        gates.extend(bundle_errors)
    if status.get("runnable") is not True:
        gates.append("benchmark v4 remains a non-runnable integrity preflight")
    if status.get("provider_transport_enabled") is not True:
        gates.append("provider transport is not implemented")
    if not _valid_sha(status.get("evaluator_registration_sha256")):
        gates.append("evaluator registration is not frozen")
    mode = release.get("evidence_mode") if isinstance(release, dict) else "real"
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_digest": digest_json(manifest, "manifest"),
        "status": status.get("status"),
        "integrity_preflight_valid": not validate_manifest(manifest) and not validate_status(status, manifest),
        "ready_for_provider_spend": not gates,
        "claim_eligible": claim_eligible(
            mode,
            status,
            manifest,
            bundle_errors=bundle_errors,
        ),
        "verified_net_win_classes": 0,
        "gates": gates,
    }


def make_journal_row(
    sequence: int,
    operation_id: str,
    event: str,
    payload: dict[str, Any],
    previous_event_sha256: str | None,
    *,
    schedule_sha256: str,
    run_id: str | None = None,
    attempt_number: int | None = None,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "schedule_digest": schedule_sha256,
        "sequence": sequence,
        "operation_id": operation_id,
        "event": event,
        "run_id": run_id,
        "attempt_number": attempt_number,
        "attempt_id": attempt_id,
        "payload": payload,
        "previous_event_sha256": previous_event_sha256,
    }
    row["event_sha256"] = digest_json(row, "journal-event")
    return row


def validate_journal_bytes(
    raw: bytes,
    schedule: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not raw:
        raise ValidationError("journal must contain at least one committed record")
    if not raw.endswith(b"\n"):
        raise ValidationError("journal has a torn or unterminated tail")
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    operation_ids: set[str] = set()
    expected_schedule_digest = schedule_digest(schedule) if schedule is not None else None
    for index, line in enumerate(raw.splitlines()):
        if not line:
            raise ValidationError(f"journal row {index} is blank")
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError(f"journal row {index} is not UTF-8") from error
        value = strict_json_loads(text, label=f"journal row {index}")
        if not isinstance(value, dict) or set(value) != JOURNAL_KEYS:
            raise ValidationError(f"journal row {index} must contain exactly the registered fields")
        if value.get("schema_version") != 1 or value.get("protocol_id") != PROTOCOL_ID:
            raise ValidationError(f"journal row {index} has an invalid protocol binding")
        if not _valid_sha(value.get("schedule_digest")):
            raise ValidationError(f"journal row {index} schedule_digest is invalid")
        if expected_schedule_digest is not None and value.get("schedule_digest") != expected_schedule_digest:
            raise ValidationError(f"journal row {index} does not bind the supplied schedule")
        if value.get("sequence") != index:
            raise ValidationError(f"journal row {index} sequence is invalid")
        operation_id = value.get("operation_id")
        if not isinstance(operation_id, str) or ID_RE.fullmatch(operation_id) is None:
            raise ValidationError(f"journal row {index} operation_id is invalid")
        if operation_id in operation_ids:
            raise ValidationError(f"journal operation_id is duplicated: {operation_id}")
        operation_ids.add(operation_id)
        event = value.get("event")
        if event not in JOURNAL_EVENTS:
            raise ValidationError(f"journal row {index} event is invalid")
        if not isinstance(value.get("payload"), dict):
            raise ValidationError(f"journal row {index} payload must be an object")
        if value.get("previous_event_sha256") != previous:
            raise ValidationError(f"journal row {index} previous hash is invalid")
        expected_hash = digest_json(
            {key: item for key, item in value.items() if key != "event_sha256"},
            "journal-event",
        )
        if value.get("event_sha256") != expected_hash:
            raise ValidationError(f"journal row {index} event hash is invalid")
        previous = expected_hash
        rows.append(value)
    if rows[0].get("event") != "journal_initialized":
        raise ValidationError("journal must start with journal_initialized")
    if any(rows[0].get(key) is not None for key in ("run_id", "attempt_number", "attempt_id")):
        raise ValidationError("journal initialization must not bind a run attempt")
    initialization_payload = rows[0].get("payload", {})
    run_count = initialization_payload.get("run_count")
    if (
        set(initialization_payload) != {"run_count"}
        or not isinstance(run_count, int)
        or isinstance(run_count, bool)
        or run_count <= 0
    ):
        raise ValidationError("journal initialization must bind the schedule run count")
    if schedule is not None and rows[0]["payload"] != {"run_count": len(schedule["runs"])}:
        raise ValidationError("journal initialization run_count does not match the schedule")
    _validate_dispatch_rows(rows, schedule)
    return rows


def _validate_dispatch_rows(
    rows: list[dict[str, Any]],
    schedule: dict[str, Any] | None,
) -> None:
    run_map = (
        {run["run_id"]: run for run in schedule.get("runs", [])}
        if schedule is not None
        else {}
    )
    reservations: dict[tuple[str, int], dict[str, Any]] = {}
    reconciled: dict[tuple[str, int], dict[str, Any]] = {}
    retry_authorizations: set[tuple[str, int]] = set()
    run_totals: dict[str, dict[str, int]] = {
        run_id: {metric: 0 for metric in METRIC_IDS} for run_id in run_map
    }
    stage_totals = {
        stage: {metric: 0 for metric in METRIC_IDS} for stage in ("pilot", "full")
    }
    protocol_totals = {metric: 0 for metric in METRIC_IDS}
    for row in rows[1:]:
        event = row["event"]
        if event == "journal_tail_recovered":
            if any(row.get(key) is not None for key in ("run_id", "attempt_number", "attempt_id")):
                raise ValidationError("journal recovery receipt must not bind a run attempt")
            expected_payload = {
                "discarded_fragment_sha256",
                "discarded_bytes",
                "last_committed_sequence",
            }
            if set(row["payload"]) != expected_payload:
                raise ValidationError("journal recovery receipt payload is invalid")
            continue
        run_id = row.get("run_id")
        attempt_number = row.get("attempt_number")
        attempt_id = row.get("attempt_id")
        if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
            raise ValidationError("dispatch journal event run_id is invalid")
        if schedule is not None and run_id not in run_map:
            raise ValidationError(f"dispatch journal references unknown run {run_id}")
        max_attempts = schedule.get("max_infra_attempts", 0) if schedule is not None else 2
        if (
            not isinstance(attempt_number, int)
            or isinstance(attempt_number, bool)
            or not 1 <= attempt_number <= max_attempts
        ):
            raise ValidationError("dispatch journal attempt_number is invalid")
        if attempt_id != attempt_id_for(run_id, attempt_number):
            raise ValidationError("dispatch journal attempt_id is not schedule-derived")
        key = (run_id, attempt_number)
        expected_dispatch_id = dispatch_id_for(row["schedule_digest"], run_id, attempt_number)
        payload = row["payload"]
        if event == "provider_dispatch_reserved":
            if key in reservations:
                raise ValidationError(f"provider dispatch is duplicated for {run_id} attempt {attempt_number}")
            if attempt_number > 1 and key not in retry_authorizations:
                raise ValidationError(
                    f"provider retry for {run_id} attempt {attempt_number} lacks a receipt-bound authorization"
                )
            if set(payload) != {"dispatch_id", "request_sha256", "provider_pair_id"}:
                raise ValidationError("provider dispatch reservation payload is invalid")
            if payload.get("dispatch_id") != expected_dispatch_id:
                raise ValidationError("provider dispatch reservation id is not schedule-derived")
            if not _valid_sha(payload.get("request_sha256")):
                raise ValidationError("provider dispatch request_sha256 is invalid")
            if schedule is not None:
                if payload.get("provider_pair_id") != run_map[run_id]["pair_id"]:
                    raise ValidationError("provider dispatch pair does not match the scheduled run")
            elif payload.get("provider_pair_id") not in PAIR_IDS:
                raise ValidationError("provider dispatch pair is invalid")
            reservations[key] = row
        elif event == "provider_receipt_reconciled":
            if key not in reservations:
                raise ValidationError("provider receipt cannot be reconciled before dispatch reservation")
            if key in reconciled:
                raise ValidationError(f"provider receipt is duplicated for {run_id} attempt {attempt_number}")
            if set(payload) != {"dispatch_id", "provider_receipt_sha256", "metrics"}:
                raise ValidationError("provider receipt reconciliation payload is invalid")
            if payload.get("dispatch_id") != expected_dispatch_id:
                raise ValidationError("provider receipt dispatch id is not schedule-derived")
            if not _valid_sha(payload.get("provider_receipt_sha256")):
                raise ValidationError("provider receipt digest is invalid")
            metric_errors = _metric_errors(
                payload.get("metrics"),
                run_map[run_id]["budget"] if schedule is not None else None,
                "provider receipt",
            )
            if metric_errors:
                raise ValidationError("; ".join(metric_errors))
            if schedule is not None:
                for metric in METRIC_IDS:
                    value = payload["metrics"][metric]
                    run_totals[run_id][metric] += value
                    stage = run_map[run_id]["stage"]
                    stage_totals[stage][metric] += value
                    protocol_totals[metric] += value
                    if run_totals[run_id][metric] > run_map[run_id]["budget"][metric]:
                        raise ValidationError(f"{run_id} cumulative {metric} exceeds its run budget")
                    if stage_totals[stage][metric] > schedule["stage_budgets"][stage][metric]:
                        raise ValidationError(f"{stage} cumulative {metric} exceeds its stage budget")
                    if protocol_totals[metric] > schedule["protocol_budget"][metric]:
                        raise ValidationError(f"protocol cumulative {metric} exceeds its budget")
            reconciled[key] = row
        elif event == "provider_retry_authorized":
            if attempt_number <= 1:
                raise ValidationError("provider retry authorization requires attempt_number greater than one")
            if key in retry_authorizations or key in reservations:
                raise ValidationError(f"provider retry authorization is duplicated for {run_id} attempt {attempt_number}")
            if set(payload) != {
                "previous_attempt_number",
                "previous_provider_receipt_sha256",
                "failure_receipt_sha256",
            }:
                raise ValidationError("provider retry authorization payload is invalid")
            previous_key = (run_id, attempt_number - 1)
            previous_receipt = reconciled.get(previous_key)
            if payload.get("previous_attempt_number") != attempt_number - 1:
                raise ValidationError("provider retry authorization previous attempt is not contiguous")
            if previous_receipt is None:
                raise ValidationError("provider retry requires the previous provider receipt to be reconciled")
            if payload.get("previous_provider_receipt_sha256") != previous_receipt["payload"].get(
                "provider_receipt_sha256"
            ):
                raise ValidationError("provider retry authorization does not bind the previous receipt")
            if not _valid_sha(payload.get("failure_receipt_sha256")):
                raise ValidationError("provider retry failure receipt digest is invalid")
            retry_authorizations.add(key)


def dispatch_gate(
    rows: list[dict[str, Any]],
    schedule: dict[str, Any],
    run_id: str,
    attempt_number: int,
) -> dict[str, Any]:
    _validate_dispatch_rows(rows, schedule)
    if run_id not in {run["run_id"] for run in schedule.get("runs", [])}:
        raise ValidationError(f"unknown schedule run: {run_id}")
    if (
        not isinstance(attempt_number, int)
        or isinstance(attempt_number, bool)
        or not 1 <= attempt_number <= schedule.get("max_infra_attempts", 0)
    ):
        raise ValidationError("dispatch gate attempt_number is outside the frozen ceiling")
    dispatch_id = dispatch_id_for(schedule_digest(schedule), run_id, attempt_number)
    matching = [
        row
        for row in rows
        if row.get("run_id") == run_id and row.get("attempt_number") == attempt_number
    ]
    reservation = next(
        (row for row in matching if row["event"] == "provider_dispatch_reserved"),
        None,
    )
    receipt = next(
        (row for row in matching if row["event"] == "provider_receipt_reconciled"),
        None,
    )
    retry_authorization = next(
        (row for row in matching if row["event"] == "provider_retry_authorized"),
        None,
    )
    if reservation is None and attempt_number > 1 and retry_authorization is None:
        previous = [
            row
            for row in rows
            if row.get("run_id") == run_id
            and row.get("attempt_number") == attempt_number - 1
        ]
        previous_reserved = any(row["event"] == "provider_dispatch_reserved" for row in previous)
        previous_reconciled = any(row["event"] == "provider_receipt_reconciled" for row in previous)
        if previous_reserved and not previous_reconciled:
            state = "prior_reconciliation_required"
        elif previous_reconciled:
            state = "retry_authorization_required"
        else:
            state = "prior_attempt_required"
    elif reservation is None:
        state = "unreserved"
    elif receipt is None:
        state = "reconciliation_required"
    else:
        state = "receipt_bound"
    return {
        "run_id": run_id,
        "attempt_number": attempt_number,
        "attempt_id": attempt_id_for(run_id, attempt_number),
        "dispatch_id": dispatch_id,
        "state": state,
        "may_reserve": state == "unreserved",
        "may_invoke_provider": False,
        "must_reconcile_receipt": state == "reconciliation_required",
    }


def dispatch_summary(rows: list[dict[str, Any]], schedule: dict[str, Any]) -> dict[str, Any]:
    _validate_dispatch_rows(rows, schedule)
    reserved = [row for row in rows if row["event"] == "provider_dispatch_reserved"]
    reconciled = [row for row in rows if row["event"] == "provider_receipt_reconciled"]
    reconciled_keys = {(row["run_id"], row["attempt_number"]) for row in reconciled}
    ambiguous = [
        {
            "run_id": row["run_id"],
            "attempt_number": row["attempt_number"],
            "dispatch_id": row["payload"]["dispatch_id"],
        }
        for row in reserved
        if (row["run_id"], row["attempt_number"]) not in reconciled_keys
    ]
    totals = {metric: 0 for metric in METRIC_IDS}
    for row in reconciled:
        for metric in METRIC_IDS:
            totals[metric] += row["payload"]["metrics"][metric]
    return {
        "reserved_attempts": len(reserved),
        "reconciled_attempts": len(reconciled),
        "ambiguous_attempts": ambiguous,
        "cumulative_metrics": totals,
    }


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise OSError("short write while publishing recovered journal")
        offset += written


@contextlib.contextmanager
def _journal_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise ValidationError(f"journal lock cannot be opened safely: {error}") from error
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
        _write_all(fd, canonical_json(row) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise ValidationError(f"journal directory cannot be opened safely: {error}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise ValidationError("journal directory must be a directory")
        os.fsync(fd)
    finally:
        os.close(fd)


def initialize_dispatch_journal(
    path: Path,
    schedule: dict[str, Any],
    *,
    operation_id: str,
) -> dict[str, Any]:
    if not isinstance(operation_id, str) or ID_RE.fullmatch(operation_id) is None:
        raise ValidationError("journal initialization operation_id is invalid")
    if path.parent.is_symlink():
        raise ValidationError("journal directory must not be a symlink")
    with _journal_lock(path):
        if path.exists():
            rows = validate_journal_bytes(
                read_regular_bytes(path, max_bytes=MAX_ARTIFACT_BYTES, label="journal"),
                schedule,
            )
            raise ValidationError(
                f"journal is already initialized by operation {rows[0]['operation_id']}"
            )
        row = make_journal_row(
            0,
            operation_id,
            "journal_initialized",
            {"run_count": len(schedule.get("runs", []))},
            None,
            schedule_sha256=schedule_digest(schedule),
        )
        _append_journal_row(path, row)
        _fsync_directory(path.parent)
        return row


def reserve_provider_dispatch(
    path: Path,
    schedule: dict[str, Any],
    *,
    operation_id: str,
    run_id: str,
    attempt_number: int,
    request_sha256: str,
) -> dict[str, Any]:
    if not isinstance(operation_id, str) or ID_RE.fullmatch(operation_id) is None:
        raise ValidationError("dispatch reservation operation_id is invalid")
    if not _valid_sha(request_sha256):
        raise ValidationError("dispatch reservation request_sha256 is invalid")
    if path.parent.is_symlink():
        raise ValidationError("journal directory must not be a symlink")
    with _journal_lock(path):
        raw = read_regular_bytes(path, max_bytes=MAX_ARTIFACT_BYTES, label="journal")
        rows = validate_journal_bytes(raw, schedule)
        if operation_id in {row["operation_id"] for row in rows}:
            raise ValidationError(f"journal operation_id is duplicated: {operation_id}")
        gate = dispatch_gate(rows, schedule, run_id, attempt_number)
        if not gate["may_reserve"]:
            raise ValidationError(
                f"{run_id} attempt {attempt_number} is {gate['state']}; provider reinvocation is forbidden"
            )
        run = next(item for item in schedule["runs"] if item["run_id"] == run_id)
        row = make_journal_row(
            len(rows),
            operation_id,
            "provider_dispatch_reserved",
            {
                "dispatch_id": gate["dispatch_id"],
                "request_sha256": request_sha256,
                "provider_pair_id": run["pair_id"],
            },
            rows[-1]["event_sha256"],
            schedule_sha256=schedule_digest(schedule),
            run_id=run_id,
            attempt_number=attempt_number,
            attempt_id=gate["attempt_id"],
        )
        validate_journal_bytes(raw + canonical_json(row) + b"\n", schedule)
        _append_journal_row(path, row)
        return {
            "provider_invocation_authorized_once": True,
            "reservation": row,
        }


def reconcile_provider_receipt(
    path: Path,
    schedule: dict[str, Any],
    *,
    operation_id: str,
    run_id: str,
    attempt_number: int,
    provider_receipt_sha256: str,
    metrics: dict[str, Any],
    artifact_root: Path,
) -> dict[str, Any]:
    if not isinstance(operation_id, str) or ID_RE.fullmatch(operation_id) is None:
        raise ValidationError("receipt reconciliation operation_id is invalid")
    resolve_artifact(artifact_root, provider_receipt_sha256, "provider receipt")
    with _journal_lock(path):
        raw = read_regular_bytes(path, max_bytes=MAX_ARTIFACT_BYTES, label="journal")
        rows = validate_journal_bytes(raw, schedule)
        if operation_id in {row["operation_id"] for row in rows}:
            raise ValidationError(f"journal operation_id is duplicated: {operation_id}")
        gate = dispatch_gate(rows, schedule, run_id, attempt_number)
        if gate["state"] != "reconciliation_required":
            raise ValidationError(
                f"{run_id} attempt {attempt_number} is {gate['state']}; no receipt can be reconciled"
            )
        row = make_journal_row(
            len(rows),
            operation_id,
            "provider_receipt_reconciled",
            {
                "dispatch_id": gate["dispatch_id"],
                "provider_receipt_sha256": provider_receipt_sha256,
                "metrics": metrics,
            },
            rows[-1]["event_sha256"],
            schedule_sha256=schedule_digest(schedule),
            run_id=run_id,
            attempt_number=attempt_number,
            attempt_id=gate["attempt_id"],
        )
        validate_journal_bytes(raw + canonical_json(row) + b"\n", schedule)
        _append_journal_row(path, row)
        return row


def authorize_provider_retry(
    path: Path,
    schedule: dict[str, Any],
    *,
    operation_id: str,
    run_id: str,
    attempt_number: int,
    failure_receipt_sha256: str,
    artifact_root: Path,
) -> dict[str, Any]:
    if not isinstance(operation_id, str) or ID_RE.fullmatch(operation_id) is None:
        raise ValidationError("retry authorization operation_id is invalid")
    resolve_artifact(artifact_root, failure_receipt_sha256, "retry failure receipt")
    with _journal_lock(path):
        raw = read_regular_bytes(path, max_bytes=MAX_ARTIFACT_BYTES, label="journal")
        rows = validate_journal_bytes(raw, schedule)
        if operation_id in {row["operation_id"] for row in rows}:
            raise ValidationError(f"journal operation_id is duplicated: {operation_id}")
        gate = dispatch_gate(rows, schedule, run_id, attempt_number)
        if gate["state"] != "retry_authorization_required":
            raise ValidationError(
                f"{run_id} attempt {attempt_number} is {gate['state']}; retry cannot be authorized"
            )
        previous_receipt = next(
            row
            for row in rows
            if row.get("event") == "provider_receipt_reconciled"
            and row.get("run_id") == run_id
            and row.get("attempt_number") == attempt_number - 1
        )
        row = make_journal_row(
            len(rows),
            operation_id,
            "provider_retry_authorized",
            {
                "previous_attempt_number": attempt_number - 1,
                "previous_provider_receipt_sha256": previous_receipt["payload"][
                    "provider_receipt_sha256"
                ],
                "failure_receipt_sha256": failure_receipt_sha256,
            },
            rows[-1]["event_sha256"],
            schedule_sha256=schedule_digest(schedule),
            run_id=run_id,
            attempt_number=attempt_number,
            attempt_id=gate["attempt_id"],
        )
        validate_journal_bytes(raw + canonical_json(row) + b"\n", schedule)
        _append_journal_row(path, row)
        return row


def recover_journal_tail(path: Path) -> dict[str, Any]:
    if path.parent.is_symlink():
        raise ValidationError("journal directory must not be a symlink")
    with _journal_lock(path):
        try:
            before = path.lstat()
        except OSError as error:
            raise ValidationError(f"journal is unavailable: {error}") from error
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValidationError("journal must be a single-link regular file")
        raw = read_regular_bytes(path, max_bytes=MAX_ARTIFACT_BYTES, label="journal")
        if raw.endswith(b"\n"):
            rows = validate_journal_bytes(raw)
            return {
                "recovered": False,
                "committed_rows": len(rows),
                "last_event_sha256": rows[-1]["event_sha256"],
            }
        boundary = raw.rfind(b"\n")
        if boundary < 0:
            raise ValidationError("journal has no committed record before its torn tail")
        committed = raw[: boundary + 1]
        tail = raw[boundary + 1 :]
        rows = validate_journal_bytes(committed)
        tail_digest = digest_bytes(tail)
        event = make_journal_row(
            len(rows),
            f"recover-{tail_digest[:20]}",
            "journal_tail_recovered",
            {
                "discarded_fragment_sha256": tail_digest,
                "discarded_bytes": len(tail),
                "last_committed_sequence": rows[-1]["sequence"],
            },
            rows[-1]["event_sha256"],
            schedule_sha256=rows[-1]["schedule_digest"],
        )
        recovered = committed + canonical_json(event) + b"\n"
        validate_journal_bytes(recovered)
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise ValidationError("journal changed while recovery held the cooperative lock")
        temp_fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.recover-", dir=path.parent)
        try:
            temp_info = os.fstat(temp_fd)
            if not stat.S_ISREG(temp_info.st_mode) or temp_info.st_nlink != 1:
                raise ValidationError("recovery temporary file must be a single-link regular file")
            os.fchmod(temp_fd, stat.S_IMODE(before.st_mode))
            _write_all(temp_fd, recovered)
            os.fsync(temp_fd)
            os.close(temp_fd)
            temp_fd = -1
            os.replace(temp_name, path)
            _fsync_directory(path.parent)
        finally:
            if temp_fd >= 0:
                os.close(temp_fd)
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp_name)
        return {
            "recovered": True,
            "committed_rows": len(rows) + 1,
            "discarded_fragment_sha256": tail_digest,
            "discarded_bytes": len(tail),
            "recovery_receipt_sha256": event["event_sha256"],
            "event": event,
        }


def _print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    readiness_parser = subparsers.add_parser("readiness")
    readiness_parser.add_argument("--release", type=Path)
    readiness_parser.add_argument("--fixture-root", type=Path)
    readiness_parser.add_argument("--artifact-root", type=Path)
    release_parser = subparsers.add_parser("release-check")
    release_parser.add_argument("--release", type=Path, required=True)
    release_parser.add_argument("--fixture-root", type=Path, required=True)
    release_parser.add_argument("--artifact-root", type=Path, required=True)
    schedule_parser = subparsers.add_parser("schedule")
    schedule_parser.add_argument("--release", type=Path, required=True)
    schedule_parser.add_argument("--fixture-root", type=Path, required=True)
    schedule_parser.add_argument("--artifact-root", type=Path, required=True)
    result_parser = subparsers.add_parser("result-check")
    result_parser.add_argument("--release", type=Path, required=True)
    result_parser.add_argument("--schedule", type=Path, required=True)
    result_parser.add_argument("--receipt", type=Path, required=True)
    result_parser.add_argument("--fixture-root", type=Path, required=True)
    result_parser.add_argument("--artifact-root", type=Path, required=True)
    recovery_parser = subparsers.add_parser("journal-recover")
    recovery_parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = load_json(args.manifest, label="v4 manifest")
        status = load_json(args.status, label="v4 status")
        if args.command == "validate":
            errors = validate_manifest(manifest) + validate_status(status, manifest)
            _print_json(
                {
                    "ok": not errors,
                    "protocol_id": PROTOCOL_ID,
                    "protocol_digest": digest_json(manifest, "manifest"),
                    "status": status.get("status"),
                    "runnable": status.get("runnable"),
                    "commands": [
                        "validate",
                        "readiness",
                        "release-check",
                        "schedule",
                        "result-check",
                        "journal-recover",
                    ],
                    "errors": errors,
                }
            )
            return 0 if not errors else 1
        if args.command == "readiness":
            release = load_json(args.release, label="v4 release") if args.release else None
            receipt = readiness(
                manifest,
                status,
                release=release,
                fixture_root=args.fixture_root,
                artifact_root=args.artifact_root,
            )
            _print_json(receipt)
            return 0 if receipt["ready_for_provider_spend"] else 2
        if args.command == "release-check":
            release = load_json(args.release, label="v4 release")
            errors = validate_release_bundle(
                release,
                manifest,
                fixture_root=args.fixture_root,
                artifact_root=args.artifact_root,
                expected_registration_sha256=status.get("evaluator_registration_sha256"),
            )
            _print_json(
                {
                    "ok": not errors,
                    "claim_eligible": claim_eligible(
                        release.get("evidence_mode", ""),
                        status,
                        manifest,
                        bundle_errors=errors,
                    ),
                    "errors": errors,
                }
            )
            return 0 if not errors else 2
        if args.command == "schedule":
            release = load_json(args.release, label="v4 release")
            generated = build_schedule(
                manifest,
                release,
                fixture_root=args.fixture_root,
                artifact_root=args.artifact_root,
                expected_registration_sha256=status.get("evaluator_registration_sha256"),
            )
            _print_json(generated)
            return 0
        if args.command == "result-check":
            release = load_json(args.release, label="v4 release")
            schedule = load_json(args.schedule, label="v4 schedule")
            receipt = load_json(args.receipt, label="v4 evaluator result receipt")
            errors = validate_evaluator_result_bundle(
                receipt,
                schedule,
                release,
                manifest,
                fixture_root=args.fixture_root,
                artifact_root=args.artifact_root,
                expected_registration_sha256=status.get("evaluator_registration_sha256"),
            )
            _print_json(
                {
                    "ok": not errors,
                    "claim_eligible": False,
                    "errors": errors,
                }
            )
            return 0 if not errors else 2
        if args.command == "journal-recover":
            _print_json(recover_journal_tail(args.journal))
            return 0
    except (OSError, ValidationError) as error:
        print(f"benchmark v4: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
