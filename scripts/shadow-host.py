#!/usr/bin/env python3
"""Run a claimed Shadow task through a native coding host.

This is deliberately a thin transport seam. It does not choose a host or
provider, create a queue, accept a result, or write a durable plan. The caller
supplies the host, one semantic work class, a clean worktree, a task file, and
exact allowed paths — or a machine-local ``~/.shadow/host-defaults.json`` may
fill the sealed host/class/delegation triple. Shadow resolves only that
host/class pair to the native model selector. The host must return a ``shadow.host-receipt.v1`` JSON fence;
otherwise the attempt is blocked or failed closed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

import shadow_plan_grammar as _grammar
import shadow_git as _shadow_git
import shadow_root_board as _board
import shadow_host_observation as _observation
import shadow_telemetry as _telemetry
from shadow_durable_lib import durable_write
from shadow_json_lib import json_text
from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE
from shadow_task_lib import TaskError, frozen_task_sha256
from shadow_execution_policy import (
    DELEGATION_MODES,
    ExecutionPolicyError,
    HOSTS as POLICY_HOSTS,
    POLICY_VERSION,
    WORK_CLASSES,
    delegation_capability,
    native_model_argv,
    resolve_route,
)


PROBE_SCHEMA = "shadow.host-probe.v1"
ATTEMPT_SCHEMA = "shadow.host-attempt.v1"
HOST_RECEIPT_SCHEMA = "shadow.host-receipt.v1"
AUTHORITY_PROPOSAL_SCHEMA = "shadow.authority-proposal.v1"
HOSTS = set(POLICY_HOSTS)
# codex-zai is the same `codex exec` argv behind the `codexz` launcher, which
# points CODEX_HOME at the isolated Z.AI home. Authority proposals stay
# codex-only: that pass is trusted, and the volume host is not.
CODEX_HOSTS = frozenset({"codex", "codex-zai"})
GIT_ESCALATIONS = frozenset({"approve-for-me"})
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
MAX_CAPTURE_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_ATTEMPT_BYTES = 64 * 1024
MAX_SUMMARY_CHARS = 280
MAX_TEST_NAME_CHARS = 160
HEAD_REFLOG_LIMIT = 128
HEAD_REFLOG_ANCHOR_LIMIT = 64
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# Known-private markers match anywhere: a mid-string `/Users/...` behind a
# backtick or parenthesis is still a private path.
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\"'=])/(?!/)[A-Za-z0-9._-]+(?:/[^\s\"']*)?")

CLAUDE_EVIDENCE_AGENT = {
    "shadow-evidence": {
        "description": "Use for one bounded independent evidence lane when delegation is required.",
        "prompt": "Inspect only the delegated evidence. Do not edit files. Return concise, exact facts to the parent.",
        "tools": ["Read", "Glob", "Grep"],
        "model": "sonnet",
    }
}


ENVIRONMENTAL_KINDS = frozenset({"host_failed", "host_launch_failed", "host_timeout"})
HOST_DEFAULTS_ENV = "SHADOW_HOST_DEFAULTS"
HOST_DEFAULTS_NAME = "host-defaults.json"


class HostError(ValueError):
    """A fail-closed host adapter error."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail



def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise HostError("identifier_invalid", f"{label} must match the public identifier pattern")
    return value


def _scrub_detail(text: str) -> str:
    """Redact private paths, secret shapes, and control characters from
    adapter-written detail before it is persisted in a receipt."""

    clean = CONTROL_RE.sub(" ", text)
    clean = PRIVATE_PATH_RE.sub("<redacted-path>", clean)
    clean = SECRET_SHAPE_RE.sub("<redacted-secret>", clean)
    return clean


def _blocked_reason(exc: "HostError") -> dict[str, str]:
    """The one shape a refusal may take on stdout. Every detail — including a
    git subprocess timeout that stringifies the full argv — is scrubbed here,
    so no emission path can leak a raw machine path by forgetting to call it."""

    return {"kind": exc.kind, "detail": _scrub_detail(exc.detail)}


def _refusal_status(kind: str) -> str:
    """Classify one refusal kind. Environmental host failures are `failed`;
    every other kind — including a failure raised before the host ever ran —
    is an ordinary blocked kind."""

    return "failed" if kind in ENVIRONMENTAL_KINDS else "blocked"


def host_defaults_path() -> Path:
    override = os.environ.get(HOST_DEFAULTS_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".shadow" / HOST_DEFAULTS_NAME


def load_host_defaults(path: Path | None = None) -> dict[str, str]:
    """Read optional machine-local host/class/delegation defaults.

    A missing or invalid file is an empty default set: flags stay required.
    This never invents a host. Only an exact sealed triple is accepted.
    """

    source = path or host_defaults_path()
    try:
        if source.is_symlink() or not source.is_file():
            return {}
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    host = raw.get("host")
    work_class = raw.get("work_class")
    delegation = raw.get("delegation")
    if host not in HOSTS or work_class not in WORK_CLASSES or delegation not in DELEGATION_MODES:
        return {}
    defaults = {"host": host, "work_class": work_class, "delegation": delegation}
    seat = raw.get("seat")
    if isinstance(seat, str) and ID_RE.fullmatch(seat):
        defaults["seat"] = seat
    return defaults


def resolve_binary(host: str, explicit: str | None) -> str:
    candidate = explicit or os.environ.get(f"SHADOW_{host.upper().replace('-', '_')}_BIN")
    if candidate:
        path = Path(candidate).expanduser()
        if "/" in candidate:
            if not path.is_file() or not os.access(path, os.X_OK):
                raise HostError("host_unavailable", f"{host} executable is unavailable")
            return str(path.resolve())
        resolved = shutil.which(candidate)
    else:
        resolved = shutil.which(
            {"claude-code": "claude", "cursor": "cursor-agent", "zai": "opencode", "codex-zai": "codexz"}.get(host, host)
        )
    if not resolved:
        raise HostError("host_unavailable", f"{host} executable is unavailable")
    return str(Path(resolved).resolve())


def run_probe(binary: str) -> tuple[int | None, str, bool]:
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "", False
    output = (result.stdout or result.stderr or "").strip()
    # Versions are diagnostic only. Keep them short and strip control bytes;
    # never include command paths, prompts, or provider output in the receipt.
    clean = " ".join(output.split())[:120]
    return result.returncode, clean, result.returncode == 0


def git_value(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot inspect worktree: {exc}") from exc
    if result.returncode != 0:
        raise HostError("git_unavailable", "worktree is not a readable Git checkout")
    return result.stdout.strip()


def exact_git_root(repo: Path) -> Path:
    root = Path(git_value(repo, "rev-parse", "--show-toplevel")).resolve()
    if root != repo.resolve():
        raise HostError("worktree_invalid", "--repo must be an exact Git worktree root")
    return root


def git_branch(repo: Path) -> str | None:
    """Return the attached branch name, or None for a detached HEAD."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "symbolic-ref", "--quiet", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot inspect worktree branch: {exc}") from exc
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise HostError("git_unavailable", "cannot inspect worktree branch")
    branch = result.stdout.strip()
    if not branch or CONTROL_RE.search(branch) or PRIVATE_PATH_RE.search(branch) or SECRET_SHAPE_RE.search(branch):
        raise HostError("git_unavailable", "worktree branch identity is unsafe")
    return branch


def head_reflog_snapshot(repo: Path, *, limit: int = HEAD_REFLOG_LIMIT) -> tuple[tuple[str, str], ...]:
    """Read one bounded, redacted-in-memory HEAD transition witness."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "reflog", "show", "--format=%H%x09%gs", "-z", "-n", str(limit), "HEAD"],
            capture_output=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot inspect worktree reflog: {exc}") from exc
    if result.returncode:
        raise HostError("git_unavailable", "cannot inspect worktree reflog")
    records = [record for record in result.stdout.split(b"\0") if record]
    if not records:
        return ()
    entries: list[tuple[str, str]] = []
    for record in records:
        if b"\t" not in record:
            raise HostError("git_unavailable", "worktree reflog is malformed")
        raw_head, raw_message = record.split(b"\t", 1)
        try:
            head = raw_head.decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise HostError("git_unavailable", "worktree reflog head is malformed") from exc
        if GIT_SHA1_RE.fullmatch(head) is None:
            raise HostError("git_unavailable", "worktree reflog head is malformed")
        action = {
            b"commit": "commit",
            b"checkout": "checkout",
            b"reset": "reset",
        }.get(raw_message.partition(b":")[0], "other")
        entries.append((head, action))
    return tuple(entries)


def reflog_continuity(
    repo: Path,
    before: tuple[tuple[str, str], ...],
    after: tuple[tuple[str, str], ...],
    allowed: list[str],
    head_after: str,
) -> bool:
    """Accept only one unambiguous run of scoped forward commit transitions."""
    if not before or not after or after[0][0] != head_after or len(after) < len(before):
        return False
    starts = [index for index in range(len(after) - len(before) + 1) if after[index:index + len(before)] == before]
    if len(starts) != 1:
        return False
    transitions = tuple(reversed(after[:starts[0]]))
    previous = before[0][0]
    for head, action in transitions:
        if action != "commit" or head == previous:
            return False
        ancestry, has_merge, paths = git_commit_paths(repo, previous, head)
        if not ancestry or has_merge or not all(path_allowed(path, allowed) for path in paths):
            return False
        previous = head
    return bool(transitions)


def index_has_suppressed_entries(repo: Path) -> bool:
    """Fail closed when Git flags can hide tracked worktree source changes."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-v", "-t", "-z"],
            capture_output=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot inspect worktree index flags: {exc}") from exc
    if result.returncode:
        raise HostError("git_unavailable", "cannot inspect worktree index flags")
    for record in (item for item in result.stdout.split(b"\0") if item):
        if len(record) < 3 or record[1:2] != b" ":
            raise HostError("git_unavailable", "worktree index flags are malformed")
        tag = chr(record[0])
        if tag == "S" or tag.islower():
            return True
    return False


def git_commit_paths(repo: Path, before: str, after: str) -> tuple[bool, bool, set[str]]:
    """Return ancestry, merge presence, and every path touched in a commit range.

    Git's NUL-delimited name-status output keeps spaces and rename endpoints
    unambiguous. This is source observation, never host-reported metadata.
    """
    try:
        ancestor = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", before, after],
            capture_output=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
        if ancestor.returncode not in {0, 1}:
            raise HostError("git_unavailable", "cannot compare source revisions")
        if ancestor.returncode:
            return False, False, set()
        commits = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--parents", f"{before}..{after}"],
            capture_output=True,
            text=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
        if commits.returncode:
            raise HostError("git_unavailable", "cannot inspect source commit range")
        commit_ids: list[str] = []
        has_merge = False
        for line in commits.stdout.splitlines():
            fields = line.split()
            if not fields or GIT_SHA1_RE.fullmatch(fields[0]) is None:
                raise HostError("git_unavailable", "source commit range is malformed")
            if len(fields) != 2:
                has_merge = True
            commit_ids.append(fields[0])
        paths: set[str] = set()
        for commit in commit_ids:
            diff = subprocess.run(
                ["git", "-C", str(repo), "diff-tree", "--no-commit-id", "--name-status", "-r", "-z", commit],
                capture_output=True,
                timeout=5,
                env=_shadow_git.sanitized_git_env(),
                check=False,
            )
            if diff.returncode:
                raise HostError("git_unavailable", "cannot inspect source commit paths")
            records = [item for item in diff.stdout.split(b"\0") if item]
            index = 0
            while index < len(records):
                status = records[index].decode("ascii", errors="strict")
                index += 1
                if not status or status[0] not in {"A", "C", "D", "M", "R", "T", "U", "X", "B"}:
                    raise HostError("git_unavailable", "source commit path status is malformed")
                names = 2 if status[0] in {"R", "C"} else 1
                if index + names > len(records):
                    raise HostError("git_unavailable", "source commit path record is malformed")
                for raw_path in records[index:index + names]:
                    path = raw_path.decode("utf-8", errors="strict")
                    if not path or CONTROL_RE.search(path):
                        raise HostError("git_unavailable", "source commit path is malformed")
                    paths.add(path)
                index += names
        return True, has_merge, paths
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise HostError("git_unavailable", f"cannot inspect source commit range: {exc}") from exc


def execution_binding(
    *,
    admitted_claim: dict[str, Any],
    authorized_revision: int,
    authorized_at: datetime,
    repository: dict[str, Any],
    repo: Path,
    branch_before: str | None,
    head_before: str,
    branch_after: str | None,
    head_after: str,
    task_sha256: str,
    allowed_scope: list[str],
    status: str,
    final_clean: bool,
    reflog_continuous: bool,
    index_suppressed: bool,
    observation: tuple[bool, bool, set[str]] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    """Build a runner-owned candidate receipt after one native execution."""
    ancestry, has_merge, committed_paths = observation or git_commit_paths(repo, head_before, head_after)
    candidate = (
        status == "ok"
        and branch_before is not None
        and branch_after == branch_before
        and head_after != head_before
        and ancestry
        and not has_merge
        and all(path_allowed(path, allowed_scope) for path in committed_paths)
        and final_clean
        and reflog_continuous
        and not index_suppressed
    )
    claim = {
        key: admitted_claim[key]
        for key in ("entity", "row", "owner", "claim_revision", "claimed_at")
    }
    return {
        "admitted_claim": claim,
        "authorized_board_revision": authorized_revision,
        "authorized_at": authorized_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repository": repository,
        "worktree_sha256": hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest(),
        "branch_before": branch_before,
        "branch_after": branch_after,
        "head_before": head_before,
        "head_after": head_after,
        "task_sha256": task_sha256,
        "allowed_scope": allowed_scope,
        "execution_candidate": candidate,
    }, committed_paths


def status_paths(repo: Path, *, include_ignored: bool = False) -> list[str]:
    command = ["git", "-C", str(repo), "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    if include_ignored:
        command.append("--ignored")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=5,
            env=_shadow_git.sanitized_git_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot read worktree status: {exc}") from exc
    if result.returncode != 0:
        raise HostError("git_unavailable", "cannot read worktree status")
    raw = result.stdout
    entries = [item for item in raw.split(b"\0") if item]
    paths: list[str] = []
    for entry in entries:
        if len(entry) < 4:
            raise HostError("git_status_invalid", "Git returned an invalid status record")
        if chr(entry[0]) in {"R", "C"} or chr(entry[1]) in {"R", "C"}:
            raise HostError("scope_violation", "renames are not accepted by the host packet")
        path = entry[3:].decode("utf-8", errors="strict")
        paths.append(path)
    return paths


def local_state_snapshot(repo: Path) -> dict[str, str]:
    # Every flow that snapshots product state also exempts pre-rename evidence
    # from its sealing checks, so validate that directory's shape here.
    state = repo / ".shadow"
    evidence = state / "evidence"
    if state.is_symlink() or evidence.is_symlink():
        raise HostError("worktree_unsealed", "project evidence path must not be a symlink")
    if not state.exists():
        return {}
    if not state.is_dir():
        raise HostError("worktree_unsealed", "project evidence state must be a directory")
    unexpected = [path for path in state.iterdir() if path.name != "evidence"]
    if unexpected:
        raise HostError("worktree_unsealed", "project state contains material outside evidence")
    if not evidence.exists():
        return {}
    if not evidence.is_dir():
        raise HostError("worktree_unsealed", "project evidence must be a directory")
    snapshot: dict[str, str] = {}
    for path in sorted(evidence.rglob("*")):
        relative = path.relative_to(repo).as_posix()
        if path.is_symlink():
            raise HostError("worktree_unsealed", "project evidence must not contain symlinks")
        if path.is_dir():
            continue
        if not path.is_file():
            raise HostError("worktree_unsealed", "project evidence must contain regular files only")
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _control_path_snapshot(
    path: Path,
    label: str,
    *,
    recursive: bool = False,
) -> dict[str, str]:
    if path.is_symlink():
        raise HostError("worktree_unsealed", "Git control state contains a symlink")
    if not path.exists():
        return {label: "absent"}
    mode = path.stat().st_mode & 0o777
    if path.is_file():
        return {
            label: (
                f"file:{mode:o}:"
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
            )
        }
    if not path.is_dir():
        raise HostError("worktree_unsealed", "Git control state is not regular")
    snapshot = {label: f"directory:{mode:o}"}
    if not recursive:
        return snapshot
    for child in sorted(path.rglob("*")):
        relative = child.relative_to(path).as_posix()
        key = f"{label}/{relative}"
        if child.is_symlink():
            raise HostError("worktree_unsealed", "Git control state contains a symlink")
        child_mode = child.stat().st_mode & 0o777
        if child.is_dir():
            snapshot[key] = f"directory:{child_mode:o}"
        elif child.is_file():
            snapshot[key] = (
                f"file:{child_mode:o}:"
                f"{hashlib.sha256(child.read_bytes()).hexdigest()}"
            )
        else:
            raise HostError("worktree_unsealed", "Git control state is not regular")
    return snapshot


def git_control_snapshot(repo: Path) -> dict[str, str]:
    git_dir = Path(
        git_value(repo, "rev-parse", "--path-format=absolute", "--git-dir")
    )
    common_dir = Path(
        git_value(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    git_dir = git_dir.resolve()
    common_dir = common_dir.resolve()

    snapshot: dict[str, str] = {}
    for label, path, recursive in (
        ("git-marker", repo / ".git", False),
        ("git-head", git_dir / "HEAD", False),
        ("git-index", git_dir / "index", False),
        ("git-commondir", git_dir / "commondir", False),
        ("git-worktree-pointer", git_dir / "gitdir", False),
        ("git-worktree-config", git_dir / "config.worktree", False),
        ("git-config", common_dir / "config", False),
        ("git-packed-refs", common_dir / "packed-refs", False),
        ("git-refs", common_dir / "refs", True),
        ("git-hooks", common_dir / "hooks", True),
        ("git-exclude", common_dir / "info" / "exclude", False),
    ):
        snapshot.update(
            _control_path_snapshot(
                path,
                label,
                recursive=recursive,
            )
        )
    return snapshot


def normalize_allowed(repo: Path, values: list[str]) -> list[str]:
    if not values:
        raise HostError("allowed_paths_missing", "at least one exact allowed path is required")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip() or "*" in raw or "?" in raw:
            raise HostError("allowed_path_invalid", "allowed paths must be nonempty exact paths")
        candidate = (repo / raw).resolve(strict=False)
        try:
            relative = candidate.relative_to(repo).as_posix()
        except ValueError as exc:
            raise HostError("allowed_path_escape", "allowed path escapes the worktree") from exc
        if relative in {"", "."} or relative.startswith("../"):
            raise HostError("allowed_path_invalid", "the worktree root is not an allowed path")
        if relative not in normalized:
            normalized.append(relative)
    return normalized


def path_allowed(path: str, allowed: list[str]) -> bool:
    return any(path == item or path.startswith(item.rstrip("/") + "/") for item in allowed)


def validate_git_escalation(host: str, value: str | None) -> str | None:
    if value is None:
        return None
    if value not in GIT_ESCALATIONS or host not in CODEX_HOSTS:
        raise HostError(
            "escalation_unsupported",
            "--git-escalation approve-for-me supports only codex and codex-zai",
        )
    return value


def public_command_shape(
    host: str,
    *,
    delegation: str,
    git_escalation: str | None = None,
) -> list[str]:
    """Return the static, non-secret shape that may enter an attempt receipt.

    The actual native argv is built separately below. The public shape records
    that a native model selector was supplied, while the execution-policy field
    records its non-secret requested value. It never records account or auth.
    """

    if host in CODEX_HOSTS:
        validate_git_escalation(host, git_escalation)
        sandbox_shape = (
            ["--approve-for-me"]
            if git_escalation is not None
            else ["--sandbox", "workspace-write"]
        )
        shape = [
            "exec",
            "--model",
            "--json",
            "--ephemeral",
            *sandbox_shape,
            "-C",
            "--output-last-message",
        ]
        shape[1:1] = ["--enable" if delegation == "required" else "--disable", "multi_agent"]
        return shape
    if host == "claude-code":
        shape = [
            "--model",
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "acceptEdits",
            "--add-dir",
        ]
        shape[0:0] = ["--agents"] if delegation == "required" else ["--disallowedTools", "Agent"]
        return shape
    if host == "cursor":
        return [
            "--model",
            "--print",
            "--output-format",
            "json",
            "--workspace",
            "--trust",
            "--force",
            "agent",
        ]
    if host == "grok":
        shape = [
            "--model",
            "--cwd",
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
            "--prompt-file",
        ]
        shape[0:0] = ["--max-turns", "20"] if delegation == "required" else ["--no-subagents"]
        return shape
    if host == "zai":
        return [
            "run",
            "--model",
            "--format",
            "json",
            "--dir",
            "--auto",
            "--variant",
            "max",
        ]
    raise HostError("host_unknown", f"unsupported host: {host}")



def launch_command(
    host: str,
    binary: str,
    repo: Path,
    final_message: Path,
    prompt_file: Path | None = None,
    *,
    work_class: str,
    delegation: str,
    git_escalation: str | None = None,
) -> list[str]:
    """Build the private native argv for one frozen task.

    Codex (both homes), Claude Code, and Cursor receive the frozen task on
    stdin, which the runner closes after the write. Grok's
    documented headless entry is ``--prompt-file`` (not stdin). Cursor's
    current non-interactive CLI requires ``agent``. This argv never becomes
    an attempt field. The native model selector is resolved from the public
    semantic work class; no account or credential selector is accepted.
    """

    try:
        model_argv = native_model_argv(host, work_class)
        delegation_capability(host, delegation)
        validate_git_escalation(host, git_escalation)
    except ExecutionPolicyError as exc:
        raise HostError("execution_policy_invalid", str(exc)) from None

    if delegation == "direct":
        delegation_argv = {
            "claude-code": ["--disallowedTools", "Agent"],
            "codex": ["--disable", "multi_agent"],
            "codex-zai": ["--disable", "multi_agent"],
            "cursor": [],
            "grok": ["--no-subagents"],
            "zai": [],
        }[host]
    else:
        delegation_argv = {
            "claude-code": [
                "--agents",
                json.dumps(CLAUDE_EVIDENCE_AGENT, separators=(",", ":")),
            ],
            "codex": ["--enable", "multi_agent"],
            "codex-zai": ["--enable", "multi_agent"],
            "cursor": [],  # Rejected by delegation_capability above.
            "grok": ["--max-turns", "20"],
            "zai": [],  # Rejected by delegation_capability above.
        }[host]

    if host in CODEX_HOSTS:
        sandbox_argv = (
            ["--approve-for-me"]
            if git_escalation is not None
            else ["--sandbox", "workspace-write"]
        )
        command = [binary, "exec"]
        command.extend(delegation_argv)
        command.extend(model_argv)
        command.extend(
            [
                "--json",
                "--ephemeral",
                *sandbox_argv,
                "-C",
                str(repo),
                "--output-last-message",
                str(final_message),
            ]
        )
        return command
    if host == "claude-code":
        command = [binary]
        command.extend(delegation_argv)
        command.extend(model_argv)
        command.extend(
            [
                "--print",
                "--output-format",
                "json",
                "--no-session-persistence",
                "--permission-mode",
                "acceptEdits",
                "--add-dir",
                str(repo),
            ]
        )
        return command
    if host == "cursor":
        command = [
            binary,
            *delegation_argv,
            *model_argv,
            "--print",
            "--output-format",
            "json",
            "--workspace",
            str(repo),
            "--trust",
            "--force",
        ]
        command.append("agent")
        return command
    if host == "grok":
        if prompt_file is None:
            raise HostError("host_unknown", "grok requires a prompt file")
        return [
            binary,
            *delegation_argv,
            *model_argv,
            "--cwd",
            str(repo),
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
            "--prompt-file",
            str(prompt_file),
        ]
    if host == "zai":
        if prompt_file is None:
            raise HostError("host_unknown", "zai requires a prompt file")
        return [
            binary,
            "run",
            *model_argv,
            "--format",
            "json",
            "--dir",
            str(repo),
            "--auto",
            "--variant",
            "max",
            prompt_file.read_text(encoding="utf-8"),
        ]
    raise HostError("host_unknown", f"unsupported host: {host}")


def command_shape(
    host: str,
    binary: str,
    repo: Path,
    final_message: Path,
    prompt_file: Path | None = None,
    *,
    work_class: str,
    delegation: str,
    git_escalation: str | None = None,
) -> list[str]:
    """Compatibility helper for tests of the native argv."""

    return launch_command(
        host,
        binary,
        repo,
        final_message,
        prompt_file,
        work_class=work_class,
        delegation=delegation,
        git_escalation=git_escalation,
    )


def host_prompt(
    task: str,
    task_id: str,
    allowed: list[str],
    task_sha256: str,
    delegation: str,
    *,
    authority_proposal: bool = False,
) -> str:
    paths = "\n".join(f"- {path}" for path in allowed)
    if authority_proposal:
        paths = "- none; this proposal pass must not change source files"
    delegation_contract = (
        "Do the bounded work directly. Do not invoke a child agent."
        if delegation == "direct"
        else (
            "Invoke one native child agent for an independent evidence lane before "
            "reconciling the result. Do not merely claim that delegation occurred."
        )
    )
    proposal_contract = ""
    if authority_proposal:
        proposal_contract = f"""
This is the explicit authority-proposal pass. Add exactly one top-level
`authority_proposal` field whose value has this closed shape:
{{"schema":"{AUTHORITY_PROPOSAL_SCHEMA}","entity_id":"64-lowercase-hex","row_id":"~ab12","owner":"public-seat","base":{{"plan_root_sha256":"64-lowercase-hex","source_head":"40-lowercase-hex"}},"request":{{"transition":"complete"}}}}
Never add proof text, a marker, a floor, paths, timestamps, or authority edits
to the proposal. This is the second, no-change pass after source edits were
reviewed and committed. Report an empty `changed_paths` list and do not change
source files or Git control state.
"""
    changed_paths_example = "[]" if authority_proposal else '["one-allowed-relative-path"]'
    return f"""Execute this bounded coding task in the current worktree.

Task ID: {task_id}
Frozen task SHA-256: {task_sha256}
Allowed paths:
{paths}

Delegation contract: {delegation_contract}

Do not change any other path. Run the relevant tests. Finish by emitting exactly
one JSON object with this shape and no additional JSON objects:
{{"schema":"{HOST_RECEIPT_SCHEMA}","task_id":"example-task-id","status":"ok","summary":"short result summary","proof_ref":"bounded-proof","changed_paths":{changed_paths_example},"tests":[{{"name":"relevant-test","status":"pass"}}]}}
{proposal_contract}

For a successful result, use the exact Task ID above and a lowercase proof_ref
identifier such as `bounded-proof`. Do not use spaces or prose for proof_ref.
If the task is blocked or fails, emit the same one object with status `blocked`
or `failed`, `proof_ref`: null, and no passing-test claim.

Frozen task:
{task}
"""


def _drain(stream: Any, state: dict[str, Any]) -> None:
    usage = state.get('usage_stream')
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        if usage is not None:
            usage.feed(chunk)
        state["bytes"] += len(chunk)
        state["tail"].extend(chunk)
        if len(state["tail"]) > MAX_CAPTURE_BYTES:
            del state["tail"][:-MAX_CAPTURE_BYTES]
    if usage is not None:
        usage.finish()


def _stop(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return
    try:
        process.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    process.wait()


def _close_pipes(process: subprocess.Popen[bytes]) -> None:
    """Close parent-owned pipes after the drain threads have finished."""

    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            pass


def run_bounded(command: list[str], task: str, repo: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return {"returncode": None, "timed_out": False, "launch_error": str(exc), "duration_s": 0.0, "stdout": b"", "stderr": b""}
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    stdout_state: dict[str, Any] = {"tail": bytearray(), "bytes": 0, "usage_stream": _observation.UsageStream()}
    stderr_state: dict[str, Any] = {"tail": bytearray(), "bytes": 0}
    threads = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_state), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr_state), daemon=True),
    ]
    for thread in threads:
        thread.start()
    # The task can exceed the OS pipe buffer while a wedged host never reads
    # stdin; a main-thread write would then block with no timeout at all. The
    # writer runs as a daemon thread so process.wait() always governs, and a
    # kill on timeout breaks the pipe and releases the writer.
    stdin_state: dict[str, Any] = {"error": False}

    def _feed_stdin() -> None:
        try:
            process.stdin.write(task.encode("utf-8"))
            process.stdin.close()
        except OSError:
            stdin_state["error"] = True

    writer = threading.Thread(target=_feed_stdin, daemon=True)
    writer.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop(process)
    for thread in threads:
        thread.join(timeout=2)
    writer.join(timeout=2)
    _close_pipes(process)
    usage_transport, usage_complete = stdout_state['usage_stream'].snapshot()
    if stdin_state["error"] and not timed_out:
        return {
            "returncode": process.returncode,
            "timed_out": False,
            "launch_error": "host stdin failed",
            "duration_s": round(time.monotonic() - started, 3),
            "stdout": bytes(stdout_state["tail"]),
            "stderr": bytes(stderr_state["tail"]),
        }
    return {
        "returncode": process.returncode,
        "timed_out": timed_out,
        "launch_error": None,
        "duration_s": round(time.monotonic() - started, 3),
        "stdout": bytes(stdout_state["tail"]),
        "stderr": bytes(stderr_state["tail"]),
        "stdout_bytes": stdout_state["bytes"],
        "stderr_bytes": stderr_state["bytes"],
        "usage_transport": usage_transport,
        "usage_transport_complete": usage_complete,
    }


def json_objects(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(value: Any) -> None:
        if not isinstance(value, dict):
            return
        candidates.append(value)
        for key in ("result", "text"):
            nested = value.get(key)
            if isinstance(nested, str) and nested != text:
                candidates.extend(json_objects(nested))

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise HostError(
                    "host_receipt_invalid",
                    f"host output repeats JSON field {key}",
                )
            value[key] = item
        return value

    def decode(raw: str) -> Any:
        return json.loads(raw, object_pairs_hook=unique_object)

    for raw in JSON_FENCE_RE.findall(text):
        try:
            value = decode(raw)
        except json.JSONDecodeError:
            continue
        add(value)
    for line in text.splitlines():
        try:
            value = decode(line)
        except json.JSONDecodeError:
            continue
        add(value)
    try:
        value = decode(text.strip())
    except json.JSONDecodeError:
        value = None

    add(value)

    # Cursor's JSON envelope currently places the model's final response in a
    # string that may contain prose immediately before the receipt object. A
    # normal line/full-document parse cannot see that object; scan only for
    # syntactically valid JSON objects and keep the schema filter below as the
    # trust boundary. This does not accept arbitrary text as a receipt.
    decoder = json.JSONDecoder(object_pairs_hook=unique_object)
    offset = 0
    while True:
        start = text.find("{", offset)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            offset = start + 1
            continue
        add(value)
        offset = start + max(end, 1)

    unique = {
        json.dumps(item, sort_keys=True, separators=(",", ":")): item
        for item in candidates
        if item.get("schema") == HOST_RECEIPT_SCHEMA
    }
    return list(unique.values())


def extract_host_receipt(texts: list[str]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for text in texts:
        candidates.extend(json_objects(text))
    # Native JSON/stream output can repeat the same final object; identical
    # repeats are not ambiguous, but two different claims are fail-closed.
    unique = {json.dumps(item, sort_keys=True, separators=(",", ":")): item for item in candidates}
    if len(unique) != 1:
        raise HostError("host_receipt_missing", "host must emit exactly one shadow.host-receipt.v1 object")
    return next(iter(unique.values()))


def _receipt_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise HostError("host_receipt_invalid", f"host receipt {label} is invalid")
    clean = value.strip()
    if not clean or len(clean) > maximum or any(ord(character) < 32 or ord(character) == 127 for character in clean):
        raise HostError("host_receipt_invalid", f"host receipt {label} is invalid")
    if PRIVATE_PATH_RE.search(clean) or ABSOLUTE_PATH_RE.search(clean):
        raise HostError("host_receipt_invalid", f"host receipt {label} contains a private path")
    if SECRET_SHAPE_RE.search(clean):
        raise HostError("host_receipt_invalid", f"host receipt {label} contains a secret-shaped value")
    return clean


def validate_authority_proposal(raw: object) -> dict[str, Any]:
    expected_fields = {"schema", "entity_id", "row_id", "owner", "base", "request"}
    if not isinstance(raw, dict) or set(raw) != expected_fields:
        raise HostError("host_receipt_invalid", "authority proposal fields are invalid")
    if raw.get("schema") != AUTHORITY_PROPOSAL_SCHEMA:
        raise HostError("host_receipt_invalid", "authority proposal schema is invalid")

    entity_id = raw.get("entity_id")
    row_id = raw.get("row_id")
    owner = raw.get("owner")
    if not isinstance(entity_id, str) or SHA256_RE.fullmatch(entity_id) is None:
        raise HostError("host_receipt_invalid", "authority proposal entity id is invalid")
    if not isinstance(row_id, str) or _grammar.ROW_ID_RE.fullmatch(row_id) is None:
        raise HostError("host_receipt_invalid", "authority proposal row id is invalid")
    safe_owner = _receipt_text(owner, "authority proposal owner", 40)
    if safe_owner != owner:
        raise HostError("host_receipt_invalid", "authority proposal owner is invalid")

    base = raw.get("base")
    if not isinstance(base, dict) or set(base) != {"plan_root_sha256", "source_head"}:
        raise HostError("host_receipt_invalid", "authority proposal base fields are invalid")
    plan_root = base.get("plan_root_sha256")
    source_head = base.get("source_head")
    if not isinstance(plan_root, str) or SHA256_RE.fullmatch(plan_root) is None:
        raise HostError("host_receipt_invalid", "authority proposal plan root is invalid")
    if not isinstance(source_head, str) or GIT_SHA1_RE.fullmatch(source_head) is None:
        raise HostError("host_receipt_invalid", "authority proposal source head is invalid")

    request = raw.get("request")
    if not isinstance(request, dict) or set(request) != {"transition"}:
        raise HostError("host_receipt_invalid", "authority proposal request fields are invalid")
    if request.get("transition") != "complete":
        raise HostError("host_receipt_invalid", "authority proposal transition is invalid")

    return {
        "schema": AUTHORITY_PROPOSAL_SCHEMA,
        "entity_id": entity_id,
        "row_id": row_id,
        "owner": safe_owner,
        "base": {
            "plan_root_sha256": plan_root,
            "source_head": source_head,
        },
        "request": {"transition": "complete"},
    }


def validate_host_receipt(
    raw: dict[str, Any],
    task_id: str,
    allowed: list[str],
    host: str,
    *,
    authority_proposal: bool = False,
) -> dict[str, Any]:
    expected_fields = {"schema", "task_id", "status", "summary", "proof_ref", "changed_paths", "tests"}
    actual_fields = set(raw)
    if actual_fields != expected_fields and actual_fields != expected_fields | {"authority_proposal"}:
        raise HostError("host_receipt_invalid", "host receipt fields are invalid")
    if raw.get("schema") != HOST_RECEIPT_SCHEMA:
        raise HostError("host_receipt_invalid", "host receipt schema is invalid")
    if raw.get("task_id") != task_id:
        raise HostError("host_receipt_invalid", "host receipt task id does not match the packet")
    status = raw.get("status")
    if status not in {"ok", "blocked", "failed"}:
        raise HostError("host_receipt_invalid", "host receipt status is invalid")
    summary = _receipt_text(raw.get("summary"), "summary", MAX_SUMMARY_CHARS)
    reported_paths = raw.get("changed_paths")
    if not isinstance(reported_paths, list) or any(not isinstance(item, str) for item in reported_paths):
        raise HostError("host_receipt_invalid", "host receipt changed_paths must be a string list")
    if authority_proposal and reported_paths:
        raise HostError(
            "scope_violation",
            "authority proposal attempts must report no changed paths",
        )
    safe_paths: list[str] = []
    for path in reported_paths:
        if not path or any(ord(character) < 32 or ord(character) == 127 for character in path):
            raise HostError("host_receipt_invalid", "host receipt changed path is invalid")
        if SECRET_SHAPE_RE.search(path):
            raise HostError("host_receipt_invalid", "host receipt changed path contains a secret-shaped value")
        candidate = Path(path)
        if (
            not path
            or CONTROL_RE.search(path)
            or re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", path)
            or candidate.is_absolute()
            or ".." in candidate.parts
            or not path_allowed(path, allowed)
        ):
            raise HostError("scope_violation", "host receipt reports a path outside the packet")
        safe_paths.append(path)
    tests = raw.get("tests")
    if not isinstance(tests, list) or any(not isinstance(item, dict) for item in tests):
        raise HostError("host_receipt_invalid", "host receipt tests must be an object list")
    safe_tests: list[dict[str, str]] = []
    for item in tests:
        if set(item) != {"name", "status"} or item.get("status") not in {"pass", "fail"}:
            raise HostError("host_receipt_invalid", "host receipt test is invalid")
        safe_tests.append(
            {
                "name": _receipt_text(item.get("name"), "test name", MAX_TEST_NAME_CHARS),
                "status": item["status"],
            }
        )
    proof_ref = raw.get("proof_ref")
    if status == "ok":
        identifier(proof_ref, "host proof_ref")
        if not safe_tests or any(item["status"] != "pass" for item in safe_tests):
            raise HostError("proof_missing", "successful host receipt requires passing tests")
    elif proof_ref is not None:
        identifier(proof_ref, "host proof_ref")
    validated = {
        "status": status,
        "summary": summary,
        "proof_ref": proof_ref,
        "changed_paths": sorted(set(safe_paths)),
        "tests": safe_tests,
    }
    if "authority_proposal" in raw:
        if host != "codex" or not authority_proposal:
            raise HostError(
                "host_receipt_invalid",
                "authority proposals require the explicit Codex proposal mode",
            )
        validated["authority_proposal"] = validate_authority_proposal(raw["authority_proposal"])
    elif authority_proposal and status == "ok":
        raise HostError(
            "host_receipt_invalid",
            "successful authority proposal attempt omitted its proposal",
        )
    return validated


def _json_text(payload: dict[str, Any]) -> str:
    return json_text(payload)


def bound_successful_proposal_attempt(payload: dict[str, Any]) -> dict[str, Any]:
    if (
        payload.get("status") != "ok"
        or "authority_proposal" not in payload
        or len(_json_text(payload).encode("utf-8")) <= MAX_ATTEMPT_BYTES
    ):
        return payload
    bounded = dict(payload)
    bounded.pop("authority_proposal", None)
    bounded.update(
        {
            "status": "failed",
            "summary": None,
            "proof_ref": None,
            "tests": [],
            "blocked": {
                "kind": "attempt_too_large",
                "detail": (
                    "successful authority proposal exceeded the "
                    f"{MAX_ATTEMPT_BYTES}-byte attempt limit"
                ),
            },
        }
    )
    if len(_json_text(bounded).encode("utf-8")) > MAX_ATTEMPT_BYTES:
        bounded["changed_paths"] = []
        bounded["ignored_artifact_paths"] = []
    return bounded


def write_json(path: str, payload: dict[str, Any], *, force: bool = False) -> None:
    encoded = _json_text(payload)
    if path == "-":
        sys.stdout.write(encoded)
        return
    destination_input = Path(path).expanduser()
    if destination_input.is_symlink():
        raise HostError("output_unsafe", "output symlinks are not allowed")
    destination = destination_input.resolve(strict=False)
    if destination.exists() and not force:
        raise HostError("output_exists", "output exists; use --force to replace it")
    try:
        durable_write(destination, encoded.encode("utf-8"), exclusive=not force, make_parents=True)
    except FileExistsError:
        raise HostError("output_exists", "output exists; use --force to replace it") from None


def validate_output_path(repo: Path, value: str) -> Path | None:
    if value == "-":
        return None
    state = repo / ".shadow"
    evidence = state / "evidence"
    if state.is_symlink() or evidence.is_symlink():
        raise HostError("output_unsafe", "project evidence path must not be a symlink")
    supplied = Path(value).expanduser()
    destination = (supplied if supplied.is_absolute() else repo / supplied).resolve(strict=False)
    try:
        destination.relative_to(evidence.resolve(strict=False))
    except ValueError as exc:
        raise HostError("output_unsafe", "host output must stay in .shadow/evidence") from exc
    return destination




def probe(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        binary = resolve_binary(args.host, args.binary)
        returncode, version, available = run_probe(binary)
        payload = {
            "schema": PROBE_SCHEMA,
            "host": args.host,
            "available": available,
            "binary_name": Path(binary).name,
            "version": version or None,
            "probe_exit_code": returncode,
            "execution": {"performed": False, "projection_only": True},
        }
        return payload, 0 if available else 1
    except HostError as exc:
        return {
            "schema": PROBE_SCHEMA,
            "host": args.host,
            "available": False,
            "blocked": _blocked_reason(exc),
            "execution": {"performed": False, "projection_only": True},
        }, 1


def run_attempt(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    started = time.monotonic()
    task_id = identifier(args.task_id, "task id")
    try:
        route = resolve_route(args.host, args.work_class)
        requested_capability = delegation_capability(args.host, args.delegation)
    except ExecutionPolicyError as exc:
        raise HostError("execution_policy_invalid", str(exc)) from None
    git_escalation = validate_git_escalation(
        args.host, getattr(args, "git_escalation", None)
    )
    authority_proposal = bool(args.authority_proposal)
    if git_escalation is not None and authority_proposal:
        raise HostError(
            "escalation_unsupported",
            "authority proposal mode seals Git control state and refuses escalation",
        )
    if authority_proposal:
        if args.host != "codex":
            raise HostError(
                "proposal_host_invalid",
                "authority proposal mode requires Codex",
            )
        if args.allowed_path:
            raise HostError(
                "proposal_scope_invalid",
                "authority proposal mode accepts no source write paths",
            )
        if args.binary is not None or os.environ.get("SHADOW_CODEX_BIN"):
            raise HostError(
                "proposal_binary_override",
                "authority proposal mode requires the default Codex executable",
            )
    repo = Path(args.repo).expanduser().resolve()
    exact_git_root(repo)
    context = None
    if args.claim_context is not None:
        def unique_fields(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate claim context field")
                result[key] = value
            return result
        try:
            if len(args.claim_context.encode("utf-8")) > 4096:
                raise ValueError("claim context exceeds 4096 bytes")
            context = json.loads(args.claim_context, object_pairs_hook=unique_fields)
            if not isinstance(context, dict):
                raise ValueError("claim context must be an object")
        except (ValueError, UnicodeError) as exc:
            raise HostError("claim_context_invalid", str(exc)) from None
    try:
        observed_board = _board.snapshot()
        staged_v2 = observed_board is not None and observed_board["schema"] == _board.V2_SCHEMA
        if staged_v2 and context is None:
            raise HostError("claim_context_missing", "v2 host run requires exact claim context")
        allowed = ([] if authority_proposal else
                   _board.normalize_write_scope(repo, args.allowed_path) if staged_v2 else
                   normalize_allowed(repo, args.allowed_path))
    except _board.BoardError as exc:
        raise HostError("claim_access_refused", str(exc)) from None
    destination = validate_output_path(repo, args.out)
    if authority_proposal and destination is None:
        raise HostError(
            "proposal_output_invalid",
            "authority proposal mode requires one sealed evidence output file",
        )
    observe = _telemetry.local_enabled() and not authority_proposal
    # Refuse a would-be-clobbered receipt BEFORE the host runs: discovering it
    # only at write time throws away a completed, worktree-mutating attempt.
    if destination is not None and destination.exists() and not args.force:
        raise HostError("output_exists", "attempt output already exists; pass --force to replace it")
    if observe and (destination is None or destination.relative_to(repo).as_posix() == _observation.LOG_PATH):
        raise HostError("observation_output_required", "local observation needs a separate evidence output file")
    try:
        task, task_sha256 = frozen_task_sha256(Path(args.task_file).expanduser())
    except TaskError as exc:
        kind = "task_too_large" if "exceeds" in str(exc) else "task_unreadable"
        raise HostError(kind, str(exc)) from None
    prompt = host_prompt(
        task,
        task_id,
        allowed,
        task_sha256,
        args.delegation,
        authority_proposal=authority_proposal,
    )
    state_before = local_state_snapshot(repo)
    before = status_paths(repo)
    source_changes = [
        path for path in before if path not in state_before
    ]
    if source_changes:
        raise HostError("worktree_dirty", "host packet requires a clean assigned worktree")
    before_all = status_paths(repo, include_ignored=True)
    before_ignored = set(before_all) - set(before)
    unsafe_ignored = [
        path
        for path in before_ignored
        if not path_allowed(path, allowed)
        and path.rstrip("/") != ".shadow"
        and not path.startswith(".shadow/evidence/")
    ]
    if unsafe_ignored:
        raise HostError("worktree_unsealed", "ignored files outside the packet are not allowed")
    source_head_before = (
        git_value(repo, "rev-parse", "--verify", "HEAD^{commit}")
        if authority_proposal
        else None
    )
    git_control_before = (
        git_control_snapshot(repo)
        if authority_proposal
        else None
    )
    binary = resolve_binary(args.host, args.binary)
    with tempfile.TemporaryDirectory(prefix="shadow-host-") as temp_dir:
        final_message = Path(temp_dir) / "final-message.txt"
        prompt_file = Path(temp_dir) / "prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        command = launch_command(
            args.host,
            binary,
            repo,
            final_message,
            prompt_file,
            work_class=args.work_class,
            delegation=args.delegation,
            git_escalation=git_escalation,
        )
        try:
            authorized_at = datetime.now(timezone.utc)
            authorization = _board.authorize_host_attempt(
                context=context, repo=repo, write_scope=args.allowed_path,
                authority_proposal=authority_proposal, now=authorized_at)
        except _board.BoardError as exc:
            raise HostError("claim_access_refused", str(exc)) from None
        binding_context: tuple[
            dict[str, Any], int, datetime, dict[str, Any], str | None, str,
            tuple[tuple[str, str], ...], bool,
        ] | None = None
        if not authority_proposal and authorization is not None:
            admitted_claim = next(
                (
                    claim for claim in authorization.payload["claims"]
                    if all(claim[key] == context[key] for key in ("entity", "row", "owner", "claim_revision"))
                ),
                None,
            )
            if admitted_claim is None:
                raise HostError("claim_access_refused", "authorized claim disappeared before launch")
            head_before = git_value(repo, "rev-parse", "--verify", "HEAD^{commit}")
            reflog_before = head_reflog_snapshot(repo, limit=HEAD_REFLOG_ANCHOR_LIMIT)
            binding_context = (
                admitted_claim,
                authorization.payload["revision"],
                authorized_at,
                admitted_claim["repository_binding"],
                git_branch(repo),
                head_before,
                reflog_before,
                index_has_suppressed_entries(repo),
            )
        launch_event = None
        launch_log_digest = None
        if observe:
            if binding_context is None:
                raise HostError("observation_claim_required", "local observation requires v2 claim admission")
            try:
                launch_event = _observation.start(repo, binding_context[0], task_sha256, args.host, args.work_class)
                launch_log_digest = local_state_snapshot(repo)[_observation.LOG_PATH]
            except _telemetry.TelemetryError:
                raise HostError("observation_incomplete", "controller launch observation could not be retained") from None
        result = run_bounded(command, prompt, repo, args.timeout_seconds)
        output_texts = [result.get("stdout", b"").decode("utf-8", errors="replace")]
        output_texts.append(result.get("stderr", b"").decode("utf-8", errors="replace"))
        if final_message.is_file() and not final_message.is_symlink() and final_message.stat().st_size <= MAX_RECEIPT_BYTES:
            output_texts.append(final_message.read_text(encoding="utf-8", errors="replace"))
        after = status_paths(repo)
        after_all = status_paths(repo, include_ignored=True)
        state_after = local_state_snapshot(repo)
        source_head_after = (
            git_value(repo, "rev-parse", "--verify", "HEAD^{commit}")
            if authority_proposal or binding_context is not None
            else None
        )
        git_control_after = (
            git_control_snapshot(repo)
            if authority_proposal
            else None
        )
        branch_after = git_branch(repo) if binding_context is not None else None
        reflog_after = head_reflog_snapshot(repo, limit=HEAD_REFLOG_LIMIT) if binding_context is not None else None
        index_suppressed_after = index_has_suppressed_entries(repo) if binding_context is not None else False
        changed = sorted(
            set(before).symmetric_difference(after)
            | {path for path in set(state_before) | set(state_after) if state_before.get(path) != state_after.get(path)}
        )
        log_unchanged = launch_event is None or state_after.get(_observation.LOG_PATH) == launch_log_digest
        if launch_event is not None and log_unchanged:
            # The only new state excluded from scope is the exact controller
            # append retained before execution. A worker append is not exempt.
            changed = [path for path in changed if path != _observation.LOG_PATH]
        # Ignored files created during the run (interpreter caches, dependency
        # installs from the bounded proof) are recorded for review but cannot
        # reach a commit, a merge, or the clean lead re-proof checkout.
        ignored_artifacts = sorted((set(after_all) - set(after)) - before_ignored)
        status = "failed"
        blocked_reason: dict[str, str] | None = None
        host_receipt: dict[str, Any] | None = None
        committed_paths: set[str] = set()
        range_observation: tuple[bool, bool, set[str]] | None = None
        binding: dict[str, Any] | None = None
        try:
            if not log_unchanged:
                raise HostError("observation_incomplete", "worker changed the controller observation stream")
            if result.get("timed_out"):
                raise HostError("host_timeout", "host exceeded the bounded execution timeout")
            if result.get("launch_error"):
                raise HostError("host_launch_failed", str(result["launch_error"]))
            if result.get("returncode") != 0:
                raise HostError("host_failed", "host exited non-zero")
            if binding_context is not None:
                range_observation = git_commit_paths(
                    repo, binding_context[5], source_head_after or binding_context[5]
                )
                committed_paths = range_observation[2]
            if authority_proposal and source_head_after != source_head_before:
                raise HostError(
                    "source_head_changed",
                    "authority proposal attempt changed source HEAD",
                )
            if authority_proposal and git_control_after != git_control_before:
                raise HostError(
                    "git_control_changed",
                    "authority proposal attempt changed Git control state",
                )
            if authority_proposal and changed:
                raise HostError(
                    "scope_violation",
                    "authority proposal attempt changed source state",
                )
            host_receipt = validate_host_receipt(
                extract_host_receipt(output_texts),
                task_id,
                allowed,
                args.host,
                authority_proposal=authority_proposal,
            )
            outside = [path for path in changed if not path_allowed(path, allowed)]
            if outside:
                raise HostError("scope_violation", "host changed a path outside the packet")
            reported_missing = [
                path
                for path in host_receipt["changed_paths"]
                if path not in changed and path not in committed_paths and path not in before_ignored
            ]
            if reported_missing:
                raise HostError("host_receipt_invalid", "host receipt reports a path Git did not change")
            status = host_receipt["status"]
            changed = sorted(set(changed) | set(host_receipt["changed_paths"]))
            if status == "ok" and not host_receipt["proof_ref"]:
                raise HostError("proof_missing", "host returned success without proof")
        except HostError as exc:
            blocked_reason = _blocked_reason(exc)
            status = _refusal_status(exc.kind)
        if binding_context is not None:
            (
                admitted_claim, authorized_revision, binding_authorized_at, repository,
                branch_before, head_before, reflog_before, index_suppressed_before,
            ) = binding_context
            binding, _ = execution_binding(
                admitted_claim=admitted_claim,
                authorized_revision=authorized_revision,
                authorized_at=binding_authorized_at,
                repository=repository,
                repo=repo,
                branch_before=branch_before,
                head_before=head_before,
                branch_after=branch_after,
                head_after=source_head_after or git_value(repo, "rev-parse", "--verify", "HEAD^{commit}"),
                task_sha256=task_sha256,
                allowed_scope=allowed,
                status=status,
                final_clean=(
                    not [path for path in after if path not in state_after]
                    and all(
                        path.rstrip("/") == ".shadow" or path.startswith(".shadow/evidence/")
                        for path in after_all
                    )
                    and all(
                        state_before.get(path) == digest
                        or destination is not None and path == destination.relative_to(repo).as_posix()
                        or launch_event is not None and path == _observation.LOG_PATH and log_unchanged
                        for path, digest in state_after.items()
                    )
                ),
                reflog_continuous=reflog_continuity(
                    repo, reflog_before, reflog_after or (), allowed,
                    source_head_after or head_before,
                ),
                index_suppressed=index_suppressed_before or index_suppressed_after,
                observation=range_observation,
            )
        payload = {
            "schema": ATTEMPT_SCHEMA,
            "revision": 1,
            "host": args.host,
            "execution_policy": {
                "schema": POLICY_VERSION,
                "work_class": args.work_class,
                "requested_model": route.model,
                "observed_model": None,
                "delegation": args.delegation,
                "requested_child_capability": requested_capability,
                "observed_child_spans": None,
                "observation": "owner-local-gauntlet-required",
            },
            "task_id": task_id,
            "task_sha256": task_sha256,
            "native_usage": _observation.native_usage(args.host, result),
            "controller_observation": {"state": "retained" if launch_event and log_unchanged else "disabled" if not observe else "incomplete",
                                       "run_id": launch_event["run_id"] if launch_event else None},
            "status": status,
            "summary": (host_receipt or {}).get("summary"),
            "proof_ref": (host_receipt or {}).get("proof_ref"),
            "changed_paths": [_scrub_detail(path) for path in changed],
            "ignored_artifact_paths": [_scrub_detail(path) for path in ignored_artifacts],
            "tests": (host_receipt or {}).get("tests", []),
            "host_exit_code": result.get("returncode"),
            "timed_out": bool(result.get("timed_out")),
            "duration_s": round(time.monotonic() - started, 3),
            "stdout_bytes": result.get("stdout_bytes", 0),
            "stderr_bytes": result.get("stderr_bytes", 0),
            "command_shape": public_command_shape(
                args.host,
                delegation=args.delegation,
                git_escalation=git_escalation,
            ),
            "blocked": blocked_reason,
            "unreviewed_claim": True,
            "accepted_by_lead": False,
            "projection_is_usage": False,
            "authority_proposal_mode": authority_proposal,
            "git_escalation": git_escalation,
        }
        if binding is not None:
            payload["execution_binding"] = binding
        if (
            status == "ok"
            and host_receipt is not None
            and "authority_proposal" in host_receipt
        ):
            payload["authority_proposal"] = host_receipt["authority_proposal"]
        payload = bound_successful_proposal_attempt(payload)
        status = payload["status"]
    write_json("-" if destination is None else str(destination), payload, force=args.force)
    if launch_event is not None and log_unchanged:
        try:
            _observation.finish(repo, launch_event, destination, payload)
        except (OSError, _telemetry.TelemetryError):
            payload["status"] = status = "blocked"
            payload["blocked"] = {"kind": "observation_incomplete", "detail": "controller terminal observation could not be retained"}
            payload["controller_observation"]["state"] = "incomplete"
            if "execution_binding" in payload:
                payload["execution_binding"]["execution_candidate"] = False
            write_json(str(destination), payload, force=True)
    return payload, 0 if status == "ok" else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="shadow host", description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    probe_parser = sub.add_parser("probe", help="probe one native host without invoking it")
    probe_parser.add_argument("--host", choices=sorted(HOSTS), required=True)
    probe_parser.add_argument("--binary")
    probe_parser.add_argument("--json", action="store_true")
    probe_parser.set_defaults(handler=probe)
    run_parser = sub.add_parser("run", help="run a claimed packet through a native host")
    defaults = load_host_defaults()
    run_parser.add_argument(
        "--host",
        choices=sorted(HOSTS),
        required="host" not in defaults,
        default=defaults.get("host"),
    )
    run_parser.add_argument(
        "--work-class",
        choices=WORK_CLASSES,
        required="work_class" not in defaults,
        default=defaults.get("work_class"),
    )
    run_parser.add_argument(
        "--delegation",
        choices=DELEGATION_MODES,
        required="delegation" not in defaults,
        default=defaults.get("delegation"),
    )
    run_parser.add_argument("--binary")
    run_parser.add_argument(
        "--git-escalation",
        choices=sorted(GIT_ESCALATIONS),
        default=None,
    )
    run_parser.add_argument("--authority-proposal", action="store_true")
    run_parser.add_argument("--repo", default=os.getcwd())
    run_parser.add_argument("--task-file", required=True)
    run_parser.add_argument("--task-id", required=True)
    run_parser.add_argument("--claim-context", help="closed JSON entity, row, owner, claim_revision and board_revision")
    run_parser.add_argument("--allowed-path", action="append", default=[])
    run_parser.add_argument("--out", default="-")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--timeout-seconds", type=int, default=900)
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(handler=run_attempt)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload, code = args.handler(args)
    except HostError as exc:
        payload = {
            "schema": PROBE_SCHEMA if args.command == "probe" else ATTEMPT_SCHEMA,
            "host": getattr(args, "host", None),
            "status": _refusal_status(exc.kind),
            "blocked": _blocked_reason(exc),
            "execution": {"performed": False, "projection_only": True},
        }
        code = 1
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif code:
        print(f"shadow host: {payload.get('blocked') or payload.get('status')}", file=sys.stderr)
    else:
        print(f"shadow host: {payload.get('host')} {payload.get('status') or 'available'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
