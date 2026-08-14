#!/usr/bin/env python3
"""Acquire one immutable remote claim ref without touching the project trunk."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Any, Final

from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE


SCHEMA: Final = "shadow.remote-claim.v1"
FIELDS: Final = {
    "schema", "status", "ref", "entity", "row", "owner", "project",
    "plan", "claim", "state", "reason", "winner", "failure",
}
JOURNAL_FIELDS: Final = {
    "schema", "state", "reason", "entity", "row", "owner", "project", "plan", "claim"
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
MAX_RELATIVE_BYTES: Final = 240
MAX_DISCOVERY_ROWS: Final = 128
MAX_PLAN_BYTES: Final = 1_000_000
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


class RemoteClaimError(RuntimeError):
    """A remote claim projection could not be authenticated completely."""


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
    branch = _git(repo, "symbolic-ref", "--short", "HEAD")
    name = branch.stdout.decode("utf-8", errors="replace").strip()
    if branch.returncode or not name:
        return False
    remote = _git(repo, "config", "--get", f"branch.{name}.remote")
    merge = _git(repo, "config", "--get", f"branch.{name}.merge")
    return (
        not remote.returncode
        and remote.stdout.decode().strip() == "origin"
        and not merge.returncode
        and merge.stdout.decode().strip().startswith("refs/heads/")
    )


def _configured_origin_merge_refs(repo: Path) -> list[str]:
    configured = _git(repo, "config", "--get-regexp", r"^branch\..*\.remote$")
    if configured.returncode:
        return []
    refs: set[str] = set()
    for line in configured.stdout.decode("utf-8", errors="replace").splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or fields[1] != "origin":
            continue
        key = fields[0]
        if not key.startswith("branch.") or not key.endswith(".remote"):
            continue
        branch = key[len("branch.") : -len(".remote")]
        merge = _git(repo, "config", "--get", f"branch.{branch}.merge")
        value = merge.stdout.decode("utf-8", errors="replace").strip()
        if not merge.returncode and value.startswith("refs/heads/"):
            refs.add(value)
    return sorted(refs)


def _origin_default(repo: Path) -> tuple[str, str]:
    listed = _git(repo, "ls-remote", "--symref", "origin", "HEAD")
    if listed.returncode:
        raise RemoteClaimError("published completion could not be authenticated")
    default_ref: str | None = None
    default_tip: str | None = None
    for line in listed.stdout.decode("ascii", errors="ignore").splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] == "ref:" and fields[2] == "HEAD":
            if default_ref is not None or not fields[1].startswith("refs/heads/"):
                raise RemoteClaimError("published completion returned an invalid listing")
            default_ref = fields[1]
        elif len(fields) == 2 and fields[1] == "HEAD" and HEX_OBJECT.fullmatch(fields[0]):
            if default_tip is not None:
                raise RemoteClaimError("published completion returned an invalid listing")
            default_tip = fields[0]
        else:
            raise RemoteClaimError("published completion returned an invalid listing")
    if default_ref is None or default_tip is None:
        raise RemoteClaimError("published completion returned an incomplete listing")
    return default_ref, default_tip


def published_plan_bytes(repo: Path, plan_token: dict[str, str]) -> bytes | None:
    """Read the bounded current PLAN only when default authority contains its head."""
    if not public_safe_plan_token(plan_token):
        return None
    head = plan_token["head"]
    configured = set(_configured_origin_merge_refs(repo))
    if not configured:
        return None
    default_ref, default_tip = _origin_default(repo)
    if default_ref not in configured:
        return None
    fetched = _git(
        repo,
        "fetch",
        "--quiet",
        "--no-tags",
        "--no-write-fetch-head",
        "origin",
        default_ref,
    )
    if fetched.returncode:
        raise RemoteClaimError("published completion could not be authenticated")
    if _origin_default(repo) != (default_ref, default_tip):
        raise RemoteClaimError("published completion changed during authentication")
    if _git(repo, "merge-base", "--is-ancestor", head, default_tip).returncode:
        return None
    located = _git(repo, "rev-parse", f"{default_tip}:{plan_token['relative']}")
    object_id = located.stdout.decode("ascii", errors="ignore").strip()
    if located.returncode or HEX_OBJECT.fullmatch(object_id) is None:
        return None
    kind = _git(repo, "cat-file", "-t", object_id)
    if kind.returncode or kind.stdout.strip() != b"blob":
        raise RemoteClaimError("published completion PLAN is not a regular Git blob")
    measured = _git(repo, "cat-file", "-s", object_id)
    try:
        size = int(measured.stdout.decode("ascii").strip())
    except (UnicodeError, ValueError) as exc:
        raise RemoteClaimError("published completion PLAN size is invalid") from exc
    if measured.returncode or size < 0 or size > MAX_PLAN_BYTES:
        raise RemoteClaimError("published completion PLAN exceeds its bounded size")
    content = _git(repo, "cat-file", "blob", object_id)
    if content.returncode or len(content.stdout) != size:
        raise RemoteClaimError("published completion PLAN could not be authenticated")
    return content.stdout


def managed_repo_for_plan(plan: Path) -> Path | None:
    """Return the configured-origin repository for a plan, else local-only."""
    top = _git(plan.parent, "rev-parse", "--show-toplevel")
    if top.returncode or not top.stdout.strip():
        return None
    try:
        repo = Path(top.stdout.decode("utf-8").strip()).resolve(strict=True)
    except (OSError, UnicodeError):
        return None
    return repo if uses_origin_upstream(repo) else None


def claim_ref(entity: str, row: str) -> str:
    if ENTITY.fullmatch(entity) is None or ROW.fullmatch(row) is None:
        raise ValueError("remote claim identity is invalid")
    return f"refs/heads/shadow/claims/v1/{entity}/{row[1:]}"


def public_safe_plan_token(value: object) -> bool:
    """True only for a bounded public Git PLAN locator."""
    if not isinstance(value, dict) or not PLAN_FIELDS.issubset(value):
        return False
    head = value.get("head")
    blob = value.get("blob")
    relative = value.get("relative")
    try:
        relative_bytes = relative.encode("utf-8") if isinstance(relative, str) else b""
    except UnicodeEncodeError:
        return False
    if (
        not isinstance(head, str)
        or HEX_OBJECT.fullmatch(head) is None
        or not isinstance(blob, str)
        or HEX_OBJECT.fullmatch(blob) is None
        or not isinstance(relative, str)
        or not relative
        or len(relative_bytes) > MAX_RELATIVE_BYTES
        or not relative.isprintable()
        or relative.startswith("/")
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or PRIVATE_PATH_RE.search(relative)
        or SECRET_SHAPE_RE.search(relative)
    ):
        return False
    return True


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
    state: str,
    reason: str,
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
        "state": state,
        "reason": reason,
        "winner": winner,
        "failure": failure,
    }


def _journal(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt[key] for key in JOURNAL_FIELDS}


def _commit_receipt(
    repo: Path,
    receipt: dict[str, Any],
    claimed_at: str,
    previous: str | None = None,
) -> str | None:
    encoded = (
        json.dumps(_journal(receipt), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
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
    parents = [previous] if previous else []
    plan_head = receipt["plan"]["head"]
    if previous is None or _git(
        repo, "merge-base", "--is-ancestor", plan_head, previous
    ).returncode:
        parents.append(plan_head)
    parent_args = [item for parent in parents for item in ("-p", parent)]
    commit = _git(
        repo,
        "commit-tree",
        tree_id,
        *parent_args,
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
    if not isinstance(value, dict) or set(value) != JOURNAL_FIELDS:
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
        or not public_safe_plan_token(value.get("plan"))
        or value.get("entity") != entity
        or value.get("row") != row
        or value.get("project") != project
        or value.get("plan")
        != {key: plan_token[key] for key in ("head", "blob", "relative")}
        or not valid_claim
        or value.get("state") not in {"acquired", "released", "completed"}
        or value.get("reason") not in {
            "acquire", "adopt", "handback", "blocked", "completed"
        }
    ):
        return None
    return value if owner is not None else None


def _validated_tip_commit(
    repo: Path,
    *,
    commit_id: str,
    ref: str,
    entity: str,
    row: str,
    project: str,
    plan_token: dict[str, str] | None = None,
) -> dict[str, Any] | None:
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
    token = value.get("plan") if plan_token is None and isinstance(value, dict) else plan_token
    if not public_safe_plan_token(token):
        return None
    if not isinstance(token, dict):
        return None
    ancestor = _git(repo, "merge-base", "--is-ancestor", token["head"], commit_id)
    resolved_blob = _git(repo, "rev-parse", f"{token['head']}:{token['relative']}")
    resolved_oid = resolved_blob.stdout.decode("ascii", errors="ignore").strip()
    object_type = _git(repo, "cat-file", "-t", resolved_oid)
    if (
        ancestor.returncode
        or resolved_blob.returncode
        or resolved_oid != token["blob"]
        or object_type.returncode
        or object_type.stdout.decode("ascii", errors="ignore").strip() != "blob"
    ):
        return None
    return _valid_winner(
        value,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
        plan_token=token,
    )


def _remote_tip(
    repo: Path,
    *,
    ref: str,
    entity: str,
    row: str,
    project: str,
    plan_token: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any] | None] | None:
    listed = _git(repo, "ls-remote", "--refs", "origin", ref)
    if listed.returncode:
        return None
    listing = listed.stdout.decode("ascii", errors="ignore").strip()
    if not listing:
        return ("", None)
    fields = listing.split()
    if len(fields) != 2 or HEX_OBJECT.fullmatch(fields[0]) is None or fields[1] != ref:
        return None
    commit_id = fields[0]
    fetched = _git(repo, "fetch", "--quiet", "--no-tags", "origin", ref)
    if fetched.returncode:
        return None
    return (
        commit_id,
        _validated_tip_commit(
            repo,
            commit_id=commit_id,
            ref=ref,
            entity=entity,
            row=row,
            project=project,
            plan_token=plan_token,
        ),
    )


def discover_active(
    repo: Path,
    *,
    entity: str,
    project: str,
    rows: list[str],
    relative: str,
    recover_detached: bool = False,
) -> list[dict[str, Any]] | None:
    """Project active remote locks for known local PLAN rows without coaching.

    The local PLAN bounds the query to at most the Method's hot-row limit. The
    conventional refs make the lookup deterministic; arbitrary branches are
    never enumerated. Returned journals are observations only and must not be
    written into the local root board.
    """
    if not uses_origin_upstream(repo) and not (
        recover_detached and _configured_origin_merge_refs(repo)
    ):
        return None
    unique_rows = sorted(set(rows))
    if (
        ENTITY.fullmatch(entity) is None
        or PROJECT.fullmatch(project) is None
        or not isinstance(relative, str)
        or len(unique_rows) > MAX_DISCOVERY_ROWS
        or any(ROW.fullmatch(row) is None for row in unique_rows)
    ):
        raise RemoteClaimError("remote claim discovery input is invalid")
    if not unique_rows:
        return []
    expected = {claim_ref(entity, row): row for row in unique_rows}
    listed = _git(repo, "ls-remote", "--refs", "origin", *expected)
    if listed.returncode:
        raise RemoteClaimError("remote claim discovery is unavailable")
    lines = listed.stdout.decode("ascii", errors="ignore").splitlines()
    if len(lines) > len(expected):
        raise RemoteClaimError("remote claim discovery returned an invalid listing")
    tips: dict[str, str] = {}
    for line in lines:
        fields = line.split()
        if (
            len(fields) != 2
            or HEX_OBJECT.fullmatch(fields[0]) is None
            or fields[1] not in expected
            or fields[1] in tips
        ):
            raise RemoteClaimError("remote claim discovery returned an invalid listing")
        tips[fields[1]] = fields[0]
    if not tips:
        return []
    fetched = _git(
        repo, "fetch", "--quiet", "--no-tags", "--no-write-fetch-head",
        "origin", *tips,
    )
    if fetched.returncode:
        raise RemoteClaimError("remote claim discovery could not authenticate its receipts")
    active: list[dict[str, Any]] = []
    for ref, commit_id in sorted(tips.items()):
        receipt = _validated_tip_commit(
            repo,
            commit_id=commit_id,
            ref=ref,
            entity=entity,
            row=expected[ref],
            project=project,
        )
        if receipt is None or receipt["plan"]["relative"] != relative:
            raise RemoteClaimError("remote claim discovery found an unauthenticated receipt")
        if receipt["state"] == "acquired":
            active.append(receipt)
    return active


def _push(repo: Path, ref: str, commit_id: str, previous: str | None) -> bool:
    lease = f"--force-with-lease={ref}:{previous or ''}"
    return _git(repo, "push", "--porcelain", lease, "origin", f"{commit_id}:{ref}").returncode == 0


def _result(
    desired: dict[str, Any], status: str, *, winner: str | None, failure: str | None
) -> dict[str, Any]:
    return {**desired, "status": status, "winner": winner, "failure": failure}


def _unsafe_plan_result(
    *, entity: str, row: str, owner: str, project: str, state: str, reason: str
) -> dict[str, Any]:
    """One closed error outcome that cannot echo the rejected PLAN locator."""
    return {
        "schema": SCHEMA,
        "status": "error",
        "ref": claim_ref(entity, row),
        "entity": entity,
        "row": row,
        "owner": _public_owner(owner),
        "project": project if PROJECT.fullmatch(project) else None,
        "plan": None,
        "claim": None,
        "state": state,
        "reason": reason,
        "winner": None,
        "failure": "unsafe_plan_token",
    }


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
    adopt_expired: bool = False,
) -> dict[str, Any] | None:
    """Return None for local-only repos, else one closed public outcome."""
    if not uses_origin_upstream(repo):
        return None
    ref = claim_ref(entity, row)
    if not public_safe_plan_token(plan_token):
        return _unsafe_plan_result(
            entity=entity, row=row, owner=owner, project=project,
            state="acquired", reason="acquire",
        )
    if (
        _public_owner(owner) is None
        or PROJECT.fullmatch(project) is None
        or STAMP.fullmatch(claimed_at) is None
        or STAMP.fullmatch(return_by) is None
        or return_by <= claimed_at
        or recovery != RECOVERY
    ):
        return _receipt(
            status="error", ref=ref, entity=entity, row=row, owner=owner,
            project=project, plan_token=plan_token, claimed_at=claimed_at,
            return_by=return_by, recovery=recovery, state="acquired", reason="acquire", winner=None,
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
        state="acquired",
        reason="acquire",
        winner=owner,
        failure=None,
    )
    tip = _remote_tip(
        repo, ref=ref, entity=entity, row=row, project=project, plan_token=None
    )
    if tip is None:
        return _result(acquired, "error", winner=None, failure="ambiguous_remote")
    previous = tip[0] or None
    current = tip[1]
    if previous is not None and current is None:
        return _result(acquired, "error", winner=None, failure="ambiguous_remote")
    if current is not None and current["state"] == "acquired":
        if current == _journal(acquired):
            return acquired
        expired = current["claim"]["return_by"] <= datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if not (adopt_expired and expired):
            return _result(acquired, "lost", winner=current["owner"], failure="claim_exists")
        acquired["reason"] = "adopt"
    commit_id = _commit_receipt(repo, acquired, claimed_at, previous)
    if commit_id is not None:
        if _push(repo, ref, commit_id, previous):
            return acquired
    observed = _remote_tip(
        repo,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
        plan_token=None,
    )
    winner = observed[1] if observed is not None else None
    if winner is not None:
        if winner == _journal(acquired):
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
            state="acquired",
            reason=acquired["reason"],
            winner=winner["owner"],
            failure="claim_exists",
        )
    if previous is None and observed == ("", None):
        return _result(acquired, "lost", winner=None, failure="transport_failed")
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
        state="acquired",
        reason=acquired["reason"],
        winner=None,
        failure="transport_failed",
    )


def transition(
    repo: Path,
    *,
    entity: str,
    row: str,
    owner: str,
    project: str,
    plan_token: dict[str, str],
    claim: dict[str, str],
    state: str,
    reason: str,
    recover_detached: bool = False,
) -> dict[str, Any] | None:
    """CAS one acquired journal tip to released/completed."""
    if not uses_origin_upstream(repo) and not (
        recover_detached and _configured_origin_merge_refs(repo)
    ):
        return None
    if not public_safe_plan_token(plan_token):
        return _unsafe_plan_result(
            entity=entity, row=row, owner=owner, project=project,
            state=state, reason=reason,
        )
    ref = claim_ref(entity, row)
    desired = _receipt(
        status="acquired", ref=ref, entity=entity, row=row, owner=owner,
        project=project, plan_token=plan_token, claimed_at=claim["claimed_at"],
        return_by=claim["return_by"], recovery=claim["recovery"], state=state,
        reason=reason, winner=owner, failure=None,
    )
    tip = _remote_tip(repo, ref=ref, entity=entity, row=row, project=project)
    if tip is None:
        return _result(desired, "error", winner=None, failure="ambiguous_remote")
    previous, current = tip
    if not previous and current is None:
        commit_id = _commit_receipt(repo, desired, claim["claimed_at"])
        if commit_id is not None and _push(repo, ref, commit_id, None):
            return desired
        observed = _remote_tip(repo, ref=ref, entity=entity, row=row, project=project)
        if observed is not None and observed[1] == _journal(desired):
            return desired
        return _result(desired, "error", winner=None, failure="ambiguous_remote")
    if current is None:
        return _result(desired, "error", winner=None, failure="ambiguous_remote")
    if current == _journal(desired):
        return desired
    if (
        current["state"] == state
        and current["reason"] == reason
        and current["owner"] == owner
        and current["claim"] == desired["claim"]
    ):
        return desired
    if (
        current["state"] != "acquired"
        or current["owner"] != owner
        or current["claim"] != desired["claim"]
    ):
        return _result(desired, "lost", winner=current["owner"], failure="claim_changed")
    commit_id = _commit_receipt(repo, desired, claim["claimed_at"], previous)
    if commit_id is not None and _push(repo, ref, commit_id, previous):
        return desired
    observed = _remote_tip(repo, ref=ref, entity=entity, row=row, project=project)
    if observed is not None and observed[1] == _journal(desired):
        return desired
    return _result(desired, "error", winner=None, failure="ambiguous_remote")
