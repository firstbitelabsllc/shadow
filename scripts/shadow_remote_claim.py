#!/usr/bin/env python3
"""Acquire one immutable remote claim ref without touching the project trunk."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Final

from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE


SCHEMA: Final = "shadow.remote-claim.v1"
FIELDS: Final = {
    "schema", "status", "ref", "entity", "row", "owner", "project",
    "plan", "claim", "winner", "failure",
}
PLAN_FIELDS: Final = {"head", "blob", "relative"}
CLAIM_FIELDS: Final = {"claimed_at", "return_by", "recovery"}
HEX_OBJECT: Final = re.compile(r"[0-9a-f]{40,64}\Z")
ENTITY: Final = re.compile(r"[0-9a-f]{64}\Z")
ROW: Final = re.compile(r"~[0-9a-z]{4}\Z")
PROJECT: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
STAMP: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
RECOVERY: Final = "probe-proof-then-adopt-park-or-close"
TIMEOUT_SECONDS: Final = 20
MAX_RECEIPT_BYTES: Final = 8 * 1024
GIT_INJECTION_VARS: Final = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_NAMESPACE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


def _is_git_injection(name: str) -> bool:
    return name in GIT_INJECTION_VARS or re.fullmatch(
        r"GIT_CONFIG_(?:KEY|VALUE)_\d+", name
    ) is not None


def sanitize_process_git_env() -> None:
    """Remove repository/config redirection without disabling normal auth."""
    for name in tuple(os.environ):
        if _is_git_injection(name):
            os.environ.pop(name)
    os.environ["GIT_TERMINAL_PROMPT"] = "0"


def _git(
    repo: Path,
    *args: str,
    input_bytes: bytes | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    for name in tuple(env):
        if _is_git_injection(name):
            env.pop(name)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/usr/bin/false"
    env.update(extra_env or {})
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return subprocess.CompletedProcess(args, 1, b"", b"")


def uses_origin_upstream(repo: Path) -> bool:
    """Only clones tracking origin opt into remote claim transport."""
    result = _git(repo, "rev-parse", "--symbolic-full-name", "@{upstream}")
    if result.returncode:
        return False
    return result.stdout.decode("utf-8", errors="replace").strip().startswith(
        "refs/remotes/origin/"
    )


def claim_ref(entity: str, row: str) -> str:
    if ENTITY.fullmatch(entity) is None or ROW.fullmatch(row) is None:
        raise ValueError("remote claim identity is invalid")
    return f"refs/heads/shadow/claims/v1/{entity}/{row[1:]}"


def _public_owner(owner: object) -> str | None:
    if (
        not isinstance(owner, str)
        or not owner
        or owner != owner.strip()
        or not owner.isprintable()
        or len(owner) > 40
        or PRIVATE_PATH_RE.search(owner)
        or SECRET_SHAPE_RE.search(owner)
    ):
        return None
    return owner


def _receipt(
    *,
    status: str,
    ref: str,
    entity: str,
    row: str,
    owner: str,
    project: str,
    plan_token: dict[str, str],
    claimed_at: str,
    return_by: str,
    recovery: str,
    winner: str | None,
    failure: str | None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "ref": ref,
        "entity": entity,
        "row": row,
        "owner": owner,
        "project": project,
        "plan": {key: plan_token[key] for key in ("head", "blob", "relative")},
        "claim": {
            "claimed_at": claimed_at,
            "return_by": return_by,
            "recovery": recovery,
        },
        "winner": winner,
        "failure": failure,
    }


def _commit_receipt(
    repo: Path, receipt: dict[str, Any], claimed_at: str
) -> str | None:
    encoded = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
    blob = _git(repo, "hash-object", "-w", "--stdin", input_bytes=encoded)
    if blob.returncode:
        return None
    blob_id = blob.stdout.decode("ascii", errors="ignore").strip()
    if HEX_OBJECT.fullmatch(blob_id) is None:
        return None
    tree_line = f"100644 blob {blob_id}\tclaim.json\n".encode()
    tree = _git(repo, "mktree", input_bytes=tree_line)
    if tree.returncode:
        return None
    tree_id = tree.stdout.decode("ascii", errors="ignore").strip()
    if HEX_OBJECT.fullmatch(tree_id) is None:
        return None
    identity_env = {
        "GIT_AUTHOR_NAME": "Shadow",
        "GIT_AUTHOR_EMAIL": "shadow@localhost",
        "GIT_COMMITTER_NAME": "Shadow",
        "GIT_COMMITTER_EMAIL": "shadow@localhost",
        "GIT_AUTHOR_DATE": claimed_at,
        "GIT_COMMITTER_DATE": claimed_at,
    }
    commit = _git(
        repo,
        "commit-tree",
        tree_id,
        "-p",
        receipt["plan"]["head"],
        input_bytes=b"shadow remote claim\n",
        extra_env=identity_env,
    )
    commit_id = commit.stdout.decode("ascii", errors="ignore").strip()
    return commit_id if not commit.returncode and HEX_OBJECT.fullmatch(commit_id) else None


def _valid_winner(
    value: object,
    *,
    ref: str,
    entity: str,
    row: str,
    project: str,
    plan_token: dict[str, str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != FIELDS:
        return None
    owner = _public_owner(value.get("owner"))
    claim = value.get("claim")
    valid_claim = (
        isinstance(claim, dict)
        and set(claim) == CLAIM_FIELDS
        and isinstance(claim.get("claimed_at"), str)
        and STAMP.fullmatch(claim["claimed_at"]) is not None
        and isinstance(claim.get("return_by"), str)
        and STAMP.fullmatch(claim["return_by"]) is not None
        and claim["return_by"] > claim["claimed_at"]
        and claim.get("recovery") == RECOVERY
    )
    if (
        value.get("schema") != SCHEMA
        or value.get("status") != "acquired"
        or value.get("ref") != ref
        or value.get("entity") != entity
        or value.get("row") != row
        or value.get("project") != project
        or value.get("plan")
        != {key: plan_token[key] for key in ("head", "blob", "relative")}
        or not valid_claim
        or value.get("winner") != owner
        or value.get("failure") is not None
    ):
        return None
    return value if owner is not None else None


def _remote_winner(
    repo: Path,
    *,
    ref: str,
    entity: str,
    row: str,
    project: str,
    plan_token: dict[str, str],
) -> dict[str, Any] | None:
    listed = _git(repo, "ls-remote", "--refs", "origin", ref)
    if listed.returncode:
        return None
    fields = listed.stdout.decode("ascii", errors="ignore").strip().split()
    if len(fields) != 2 or HEX_OBJECT.fullmatch(fields[0]) is None or fields[1] != ref:
        return None
    commit_id = fields[0]
    fetched = _git(repo, "fetch", "--quiet", "--no-tags", "origin", ref)
    if fetched.returncode:
        return None
    sized = _git(repo, "cat-file", "-s", f"{commit_id}:claim.json")
    raw_size = sized.stdout.decode("ascii", errors="ignore").strip()
    if (
        sized.returncode
        or not raw_size.isdigit()
        or int(raw_size) > MAX_RECEIPT_BYTES
    ):
        return None
    shown = _git(repo, "show", f"{commit_id}:claim.json")
    if shown.returncode:
        return None
    try:
        value = json.loads(shown.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    return _valid_winner(
        value,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
        plan_token=plan_token,
    )


def acquire(
    repo: Path,
    *,
    entity: str,
    row: str,
    owner: str,
    project: str,
    plan_token: dict[str, str],
    claimed_at: str,
    return_by: str,
    recovery: str,
) -> dict[str, Any] | None:
    """Return None for local-only repos, else one closed public outcome."""
    if not uses_origin_upstream(repo):
        return None
    ref = claim_ref(entity, row)
    if (
        _public_owner(owner) is None
        or PROJECT.fullmatch(project) is None
        or set(plan_token) < PLAN_FIELDS
        or HEX_OBJECT.fullmatch(plan_token["head"]) is None
        or HEX_OBJECT.fullmatch(plan_token["blob"]) is None
        or not isinstance(plan_token["relative"], str)
        or not plan_token["relative"]
        or plan_token["relative"].startswith("/")
        or "\\" in plan_token["relative"]
        or any(part in {"", ".", ".."} for part in plan_token["relative"].split("/"))
        or STAMP.fullmatch(claimed_at) is None
        or STAMP.fullmatch(return_by) is None
        or return_by <= claimed_at
        or recovery != RECOVERY
    ):
        return _receipt(
            status="error", ref=ref, entity=entity, row=row, owner=owner,
            project=project, plan_token=plan_token, claimed_at=claimed_at,
            return_by=return_by, recovery=recovery, winner=None,
            failure="transport_failed",
        )
    acquired = _receipt(
        status="acquired",
        ref=ref,
        entity=entity,
        row=row,
        owner=owner,
        project=project,
        plan_token=plan_token,
        claimed_at=claimed_at,
        return_by=return_by,
        recovery=recovery,
        winner=owner,
        failure=None,
    )
    commit_id = _commit_receipt(repo, acquired, claimed_at)
    if commit_id is not None:
        pushed = _git(
            repo,
            "push",
            "--porcelain",
            f"--force-with-lease={ref}:",
            "origin",
            f"{commit_id}:{ref}",
        )
        if pushed.returncode == 0:
            return acquired
    winner = _remote_winner(
        repo,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
        plan_token=plan_token,
    )
    if winner is not None:
        if winner == acquired:
            return acquired
        return _receipt(
            status="lost",
            ref=ref,
            entity=entity,
            row=row,
            owner=owner,
            project=project,
            plan_token=plan_token,
            claimed_at=claimed_at,
            return_by=return_by,
            recovery=recovery,
            winner=winner["owner"],
            failure="claim_exists",
        )
    return _receipt(
        status="error",
        ref=ref,
        entity=entity,
        row=row,
        owner=owner,
        project=project,
        plan_token=plan_token,
        claimed_at=claimed_at,
        return_by=return_by,
        recovery=recovery,
        winner=None,
        failure="transport_failed",
    )
