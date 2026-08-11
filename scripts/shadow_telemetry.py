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
from typing import Final


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
    root = Path(repo)
    try:
        canonical = root.resolve(strict=True)
    except OSError as exc:
        raise TelemetryError("repository root is unavailable") from exc
    if not root.is_absolute() or root != canonical or not root.is_dir():
        raise TelemetryError("repository root is not canonical")
    record = _validated_record(candidate)
    encoded = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_EVENT_BYTES:
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
