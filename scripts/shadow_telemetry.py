#!/usr/bin/env python3
"""Construct and append one closed, opt-in repository-local Shadow event."""

from __future__ import annotations

from collections.abc import Mapping
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Final
import hashlib

import shadow_git as _shadow_git


SCHEMA: Final = "shadow.telemetry.event.v1"
EVENT_FILE: Final = "shadow-events.jsonl"
LOCAL_MODE: Final = "local"
MAX_EVENT_BYTES: Final = 1024
MAX_DURATION_MS: Final = 86_400_000
ID_RE: Final = re.compile(r"^[0-9a-f]{64}$")
PROJECT_RE: Final = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
ROW_RE: Final = re.compile(r"^~[0-9a-z]{4}$")
UTC_RE: Final = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
VERBS: Final = frozenset({"throw"})
OUTCOMES: Final = frozenset({"claimed"})
EVENT_FIELDS: Final = (
    "schema",
    "recorded_at",
    "project",
    "entity",
    "row",
    "verb",
    "duration_ms",
    "outcome",
)

CLEANUP_SCHEMA: Final = "shadow.clean-observation.v1"
CLEANUP_PHASE: Final = "automatic_pass"
CLEANUP_TRIGGERS: Final = frozenset({"accept", "return", "lifecycle", "create", "sweep"})
CLEANUP_STATES: Final = (
    "disabled", "no_candidates", "trashed", "already_trashed", "refused",
    "recovery_required", "other",
)
CLEANUP_FIELDS: Final = (
    "schema", "recorded_at", "phase", "report_sha256", "trigger", "enabled",
    "source_sha256", "entity", "row", "candidate_count", "changed_count",
    "outcomes",
)
MAX_CLEANUP_CANDIDATES: Final = 4096
MAX_CLEANUP_BYTES: Final = 2048


class TelemetryError(RuntimeError):
    """The optional local event could not be recorded safely."""


def event_record(candidate: Mapping[str, object]) -> dict[str, object]:
    """Project candidate data into the closed vocabulary; values stay untrusted."""
    return {
        "schema": SCHEMA,
        "recorded_at": candidate.get("recorded_at"),
        "project": candidate.get("project"),
        "entity": candidate.get("entity"),
        "row": candidate.get("row"),
        "verb": candidate.get("verb"),
        "duration_ms": candidate.get("duration_ms"),
        "outcome": candidate.get("outcome"),
    }


def local_enabled(environment: Mapping[str, str] | None = None) -> bool:
    """Only one explicit local mode enables writing; every other value is off."""
    source = os.environ if environment is None else environment
    return source.get("SHADOW_TELEMETRY") == LOCAL_MODE


def _validated_record(candidate: Mapping[str, object]) -> dict[str, object]:
    record = event_record(candidate)
    if not isinstance(record["recorded_at"], str) or not UTC_RE.fullmatch(
        record["recorded_at"]
    ):
        raise TelemetryError("recorded_at is outside the local event vocabulary")
    if not isinstance(record["project"], str) or not PROJECT_RE.fullmatch(
        record["project"]
    ):
        raise TelemetryError("project is outside the local event vocabulary")
    if not isinstance(record["entity"], str) or not ID_RE.fullmatch(record["entity"]):
        raise TelemetryError("entity is outside the local event vocabulary")
    if not isinstance(record["row"], str) or not ROW_RE.fullmatch(record["row"]):
        raise TelemetryError("row is outside the local event vocabulary")
    if record["verb"] not in VERBS:
        raise TelemetryError("verb is outside the local event vocabulary")
    if record["outcome"] not in OUTCOMES:
        raise TelemetryError("outcome is outside the local event vocabulary")
    duration = record["duration_ms"]
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or duration < 0
        or duration > MAX_DURATION_MS
    ):
        raise TelemetryError("duration_ms is outside the local event vocabulary")
    return record


def _utc_now() -> str:
    """Return the one portable, bounded timestamp spelling used by local events."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _cleanup_outcomes(report: Mapping[str, object]) -> dict[str, int]:
    """Reduce an untrusted cleanup report to fixed aggregate counters only."""
    counts = {state: 0 for state in CLEANUP_STATES}
    enabled = report.get("enabled")
    candidates = report.get("candidates")
    if not isinstance(enabled, bool):
        raise TelemetryError("cleanup report is malformed")
    if not isinstance(candidates, list) or len(candidates) > MAX_CLEANUP_CANDIDATES:
        raise TelemetryError("cleanup report candidates are malformed")
    if not enabled:
        counts["disabled"] = 1
        return counts
    if not candidates:
        counts["no_candidates"] = 1
        return counts
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            counts["other"] += 1
            continue
        state = candidate.get("state")
        if state == "recovery_required":
            bucket = "recovery_required"
        elif state in {"trashed", "already_trashed", "refused"}:
            bucket = state
        else:
            bucket = "other"
        counts[bucket] += 1
    return counts


def cleanup_observation_sha256(report: Mapping[str, object], trigger: str) -> str:
    """Bind a path-free public cleanup report to its local observation.

    The digest is a correlation receipt, not candidate authority.  It allows a
    CLI report, local event, and owner-only exported span to prove the same
    bounded pass without exposing the report's opaque candidate identities.
    """
    if not isinstance(trigger, str) or trigger not in CLEANUP_TRIGGERS:
        raise TelemetryError("cleanup trigger is outside the local event vocabulary")
    outcomes = _cleanup_outcomes(report)
    candidates = report.get("candidates")
    assert isinstance(candidates, list)
    projection = {
        "trigger": trigger,
        "enabled": report["enabled"],
        "changed": report.get("changed") is True,
        "candidates": [
            {
                key: candidate.get(key)
                for key in ("id", "entity", "checkpoint", "state", "reason", "changed")
            }
            if isinstance(candidate, Mapping) else {"invalid": True}
            for candidate in candidates
        ],
        "outcomes": outcomes,
    }
    try:
        encoded = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    except (TypeError, ValueError) as exc:
        raise TelemetryError("cleanup report is malformed") from exc
    return hashlib.sha256(encoded).hexdigest()


def cleanup_record(repo: Path, report: Mapping[str, object], trigger: str) -> dict[str, object]:
    """Construct one closed aggregate automatic-cleanup observation.

    This deliberately receives the public report rather than private transaction
    records.  Its result contains no source path, worktree path, Git reference,
    exception, process, or candidate identity.
    """
    outcomes = _cleanup_outcomes(report)
    candidates = report.get("candidates")
    assert isinstance(candidates, list)
    # A committed automatic move is represented only by `trashed`; count that
    # closed outcome, rather than trusting arbitrary candidate `changed` data.
    changed_count = outcomes["trashed"]
    entity = report.get("entity")
    row = report.get("checkpoint")
    # The optional report scope is not guaranteed to be projected by every
    # caller.  It is recorded only when the shape is already public and safe.
    if entity is not None and (not isinstance(entity, str) or not ID_RE.fullmatch(entity)):
        entity = None
    if row is not None and (not isinstance(row, str) or not ROW_RE.fullmatch(row)):
        row = None
    return {
        "schema": CLEANUP_SCHEMA,
        "recorded_at": _utc_now(),
        "phase": CLEANUP_PHASE,
        "report_sha256": cleanup_observation_sha256(report, trigger),
        "trigger": trigger,
        "enabled": report["enabled"],
        "source_sha256": hashlib.sha256(str(Path(repo).resolve()).encode("utf-8")).hexdigest(),
        "entity": entity,
        "row": row,
        "candidate_count": len(candidates),
        "changed_count": changed_count,
        "outcomes": outcomes,
    }


def validate_cleanup_record(candidate: Mapping[str, object]) -> dict[str, object]:
    """Reject anything outside the exact cleanup observation contract."""
    if set(candidate) != set(CLEANUP_FIELDS) or candidate.get("schema") != CLEANUP_SCHEMA:
        raise TelemetryError("invalid cleanup observation shape")
    record = dict(candidate)
    if (not isinstance(record["recorded_at"], str) or not UTC_RE.fullmatch(record["recorded_at"])
            or record["phase"] != CLEANUP_PHASE
            or not isinstance(record["report_sha256"], str) or not ID_RE.fullmatch(record["report_sha256"])
            or not isinstance(record["trigger"], str) or record["trigger"] not in CLEANUP_TRIGGERS
            or not isinstance(record["enabled"], bool)
            or not isinstance(record["source_sha256"], str) or not ID_RE.fullmatch(record["source_sha256"])
            or record["entity"] is not None and (not isinstance(record["entity"], str) or not ID_RE.fullmatch(record["entity"]))
            or record["row"] is not None and (not isinstance(record["row"], str) or not ROW_RE.fullmatch(record["row"]))):
        raise TelemetryError("cleanup observation is outside the local event vocabulary")
    for key in ("candidate_count", "changed_count"):
        value = record[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_CLEANUP_CANDIDATES:
            raise TelemetryError("cleanup observation counts are outside the local event vocabulary")
    outcomes = record["outcomes"]
    if not isinstance(outcomes, dict) or set(outcomes) != set(CLEANUP_STATES):
        raise TelemetryError("cleanup observation outcomes are outside the local event vocabulary")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_CLEANUP_CANDIDATES
           for value in outcomes.values()):
        raise TelemetryError("cleanup observation outcomes are outside the local event vocabulary")
    total = sum(outcomes.values())
    sentinels = outcomes["disabled"] + outcomes["no_candidates"]
    if not record["enabled"]:
        if record["candidate_count"] != 0 or record["changed_count"] != 0 or outcomes["disabled"] != 1 or total != 1:
            raise TelemetryError("disabled cleanup observation is inconsistent")
    elif record["candidate_count"] == 0:
        if record["changed_count"] != 0 or outcomes["no_candidates"] != 1 or total != 1:
            raise TelemetryError("zero-candidate cleanup observation is inconsistent")
    elif sentinels or total != record["candidate_count"]:
        raise TelemetryError("cleanup observation outcome total is inconsistent")
    if record["changed_count"] != outcomes["trashed"]:
        raise TelemetryError("cleanup observation changed count is inconsistent")
    return record


def cleanup_observation_owner(repo: Path) -> Path:
    """Find the primary linked checkout, never an expendable child checkout."""
    try:
        source = Path(repo).resolve(strict=True)
        result = subprocess.run(
            ["git", "-C", str(source), "worktree", "list", "--porcelain", "-z"],
            capture_output=True, check=False, timeout=15,
            env=_shadow_git.sanitized_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TelemetryError("cleanup observation owner is unavailable") from exc
    if result.returncode:
        raise TelemetryError("cleanup observation owner is unavailable")
    # `-z` is essential: porcelain quotes paths with newlines and other odd
    # spelling under the line protocol. The first record is Git's primary
    # worktree, which is stable while linked children may be retired.
    owners = [
        Path(os.fsdecode(field[9:]))
        for field in result.stdout.split(b"\0")
        if field.startswith(b"worktree ")
    ]
    if not owners:
        raise TelemetryError("cleanup observation owner is unavailable")
    owner = owners[0].resolve(strict=True)
    if owner.is_symlink() or not owner.is_dir():
        raise TelemetryError("cleanup observation owner is unsafe")
    return owner


def emit_cleanup_observation(
    repo: Path,
    report: Mapping[str, object],
    trigger: str,
    *,
    owner_repo: Path | None = None,
) -> bool:
    """Best-effort, non-throwing automatic cleanup observability.

    Telemetry must never select a candidate, mutate a cleanup result, or turn a
    successful lifecycle boundary red.  Callers receive only whether the local
    append completed.
    """
    if not local_enabled():
        return False
    try:
        record = validate_cleanup_record(cleanup_record(repo, report, trigger))
        # Never create ignored state in a linked child that the same pass may
        # retire.  The primary checkout is excluded by the cleanup transaction
        # and is the durable owner for the shared local Git database.
        owner = cleanup_observation_owner(repo) if owner_repo is None else Path(owner_repo).resolve(strict=True)
        append_record(owner, record, max_bytes=MAX_CLEANUP_BYTES)
    except (TelemetryError, OSError, TypeError, ValueError, KeyError):
        return False
    return True


def validate_export_record(candidate: Mapping[str, object]) -> dict[str, object]:
    """Validate the two closed telemetry records this module owns for export."""
    if candidate.get("schema") == SCHEMA:
        return _validated_record(candidate)
    if candidate.get("schema") == CLEANUP_SCHEMA:
        return validate_cleanup_record(candidate)
    raise TelemetryError("unsupported local telemetry schema")


def _open_directory(parent: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
    except FileExistsError:
        pass
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent)
    except OSError as exc:
        raise TelemetryError("project evidence directory is unsafe") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise TelemetryError("project evidence directory is unsafe")
    return descriptor


def emit_local(repo: Path, candidate: Mapping[str, object]) -> Path:
    """Append one bounded event beneath the exact canonical repository root."""
    return append_record(repo, _validated_record(candidate), max_bytes=MAX_EVENT_BYTES)


def append_record(repo: Path, record: Mapping[str, object], *, max_bytes: int) -> Path:
    """Shared safe append for already validated closed local event schemas."""
    root = Path(repo)
    try:
        canonical = root.resolve(strict=True)
    except OSError as exc:
        raise TelemetryError("repository root is unavailable") from exc
    if not root.is_absolute() or root != canonical or not root.is_dir():
        raise TelemetryError("repository root is not canonical")
    encoded = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > max_bytes:
        raise TelemetryError("local event exceeds its byte budget")

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    repo_fd = state_fd = evidence_fd = event_fd = None
    try:
        repo_fd = os.open(root, directory_flags)
        state_fd = _open_directory(repo_fd, ".shadow")
        evidence_fd = _open_directory(state_fd, "evidence")
        event_flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK
        event_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        event_fd = os.open(EVENT_FILE, event_flags, 0o600, dir_fd=evidence_fd)
        metadata = os.fstat(event_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise TelemetryError("local event destination is not a regular file")
        os.fchmod(event_fd, 0o600)
        fcntl.flock(event_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        remaining = memoryview(encoded)
        while remaining:
            written = os.write(event_fd, remaining)
            if written <= 0:
                raise TelemetryError("local event write did not advance")
            remaining = remaining[written:]
        os.fsync(event_fd)
        fcntl.flock(event_fd, fcntl.LOCK_UN)
        os.fsync(evidence_fd)
    except TelemetryError:
        raise
    except OSError as exc:
        raise TelemetryError("local event could not be written safely") from exc
    finally:
        for descriptor in (event_fd, evidence_fd, state_fd, repo_fd):
            if descriptor is not None:
                os.close(descriptor)
    return root / ".shadow" / "evidence" / EVENT_FILE
