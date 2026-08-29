#!/usr/bin/env python3
"""Acquire one immutable remote claim ref without touching the project trunk."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Final, Iterator

import shadow_git as _shadow_git
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
DISCOVERY_FIELDS: Final = {"entity", "project", "rows", "relative"}
HEX_OBJECT: Final = re.compile(r"[0-9a-f]{40,64}\Z")
ENTITY: Final = re.compile(r"[0-9a-f]{64}\Z")
ROW: Final = re.compile(r"~[0-9a-z]{4}\Z")
PROJECT: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
STAMP: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
RECOVERY: Final = "probe-proof-then-adopt-park-or-close"
TIMEOUT_SECONDS: Final = 20
GIT_EXECUTION_FAILURE: Final = 255
MAX_RECEIPT_BYTES: Final = 8 * 1024
MAX_RELATIVE_BYTES: Final = 240
MAX_DISCOVERY_ROWS: Final = 128
MAX_PLAN_BYTES: Final = 1_000_000


class RemoteClaimError(RuntimeError):
    """A remote claim projection could not be authenticated completely."""


class RemoteEligibility(str, Enum):
    """Whether remote claim transport is required for the current checkout."""

    REMOTE = "REMOTE"
    VERIFIED_LOCAL_ONLY = "VERIFIED_LOCAL_ONLY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class UpstreamBinding:
    """One verified decision about eligibility, transport, and publication refs."""

    eligibility: RemoteEligibility
    endpoint: str | None = None
    public_identity: str | None = None
    merge_refs: frozenset[str] = frozenset()


LOCAL_ONLY = UpstreamBinding(RemoteEligibility.VERIFIED_LOCAL_ONLY)
UNKNOWN = UpstreamBinding(RemoteEligibility.UNKNOWN)


def _git(
    repo: Path,
    *args: str,
    input_bytes: bytes | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = _shadow_git.sanitized_git_env(extra_env)
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
        return subprocess.CompletedProcess(args, GIT_EXECUTION_FAILURE, b"", b"")


def _missing_git_value(result: subprocess.CompletedProcess[bytes]) -> bool:
    return result.returncode == 1 and not result.stdout and not result.stderr


def _one_git_value(result: subprocess.CompletedProcess[bytes]) -> str | None:
    try:
        values = result.stdout.decode("utf-8").splitlines()
    except UnicodeError:
        return None
    if len(values) != 1 or not values[0].strip():
        return None
    return values[0].strip()


def remote_endpoint(
    repo: Path,
    remote_name: str,
    *,
    missing_ok: bool = False,
) -> tuple[str, str, tuple[str, ...]] | None:
    """Resolve one fetch/push-consistent endpoint and normalized identity."""
    if remote_name == ".":
        common = _git(
            repo,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        )
        common_dir = _one_git_value(common) if not common.returncode else None
        if common_dir is None:
            raise RemoteClaimError("remote endpoint configuration is unavailable")
        identity = _shadow_git.local_git_identity(repo, common_dir)
        return ".", identity, ("local-git", identity)
    configured = _git(repo, "config", "--get-all", f"remote.{remote_name}.url")
    if _missing_git_value(configured) and missing_ok:
        return None
    if configured.returncode or _one_git_value(configured) is None:
        raise RemoteClaimError("remote endpoint configuration is unavailable")
    fetch = _git(repo, "remote", "get-url", "--all", "--", remote_name)
    push = _git(repo, "remote", "get-url", "--push", "--all", "--", remote_name)
    fetch_url = _one_git_value(fetch) if not fetch.returncode else None
    push_url = _one_git_value(push) if not push.returncode else None
    if fetch_url is None or push_url is None:
        raise RemoteClaimError("remote endpoint configuration is unavailable")
    fetch_identity = _shadow_git.normalized_repo_origin(repo, fetch_url)
    push_identity = _shadow_git.normalized_repo_origin(repo, push_url)
    fetch_transport = _shadow_git.transport_fingerprint(repo, fetch_url)
    push_transport = _shadow_git.transport_fingerprint(repo, push_url)
    if (
        not fetch_identity
        or fetch_identity != push_identity
        or fetch_transport != push_transport
    ):
        raise RemoteClaimError("remote fetch and push endpoints do not match")
    return push_url, push_identity, push_transport


def _configured_branch_heads(repo: Path) -> list[tuple[str, str, str]]:
    """Return configured tracked branch heads after one strict Git parse."""
    configured = _git(
        repo,
        "config",
        "--null",
        "--get-regexp",
        r"^branch\..*\.(remote|merge)$",
    )
    if _missing_git_value(configured):
        return []
    if configured.returncode:
        raise RemoteClaimError("configured upstream branches are unavailable")
    try:
        records = configured.stdout.split(b"\0")
        if records.pop() != b"":
            raise ValueError
        entries: list[tuple[str, str]] = []
        for record in records:
            key, separator, value = record.partition(b"\n")
            if not separator:
                raise ValueError
            entries.append((key.decode("utf-8"), value.decode("utf-8")))
    except UnicodeError as exc:
        raise RemoteClaimError("configured upstream branches are unavailable") from exc
    except ValueError as exc:
        raise RemoteClaimError("configured upstream branches are malformed") from exc
    remotes: dict[str, list[str]] = {}
    merges: dict[str, list[str]] = {}
    for key, value in entries:
        matched = re.fullmatch(r"branch\.(.+)\.(remote|merge)", key)
        if (
            matched is None
            or not value
            or not value.isprintable()
            or any(char.isspace() for char in value)
        ):
            raise RemoteClaimError("configured upstream branches are malformed")
        branch, kind = matched.groups()
        target = remotes if kind == "remote" else merges
        target.setdefault(branch, []).append(value)
    heads: list[tuple[str, str, str]] = []
    for branch in sorted(set(remotes) | set(merges)):
        remote_names = remotes.get(branch, [])
        merge_refs = merges.get(branch, [])
        if len(remote_names) > 1 or (merge_refs and len(remote_names) != 1):
            raise RemoteClaimError("configured upstream branches are malformed")
        if remote_names:
            heads.extend(
                (branch, remote_names[0], merge_ref)
                for merge_ref in merge_refs
                if merge_ref.startswith("refs/heads/")
            )
    return heads


def _binding_for_heads(
    repo: Path,
    heads: list[tuple[str, str, str]],
    *,
    selected_remote: str | None = None,
) -> UpstreamBinding:
    if not heads:
        return LOCAL_ONLY
    endpoints: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    for remote_name in sorted({remote for _, remote, _ in heads}):
        resolved = remote_endpoint(repo, remote_name)
        assert resolved is not None
        endpoints[remote_name] = resolved
    if selected_remote is None:
        fingerprints = {resolved[2] for resolved in endpoints.values()}
        if len(fingerprints) != 1:
            return UNKNOWN
        selected_remote = min(endpoints)
    selected = endpoints.get(selected_remote)
    if selected is None:
        return UNKNOWN
    endpoint, public_identity, fingerprint = selected
    refs = frozenset(
        merge_ref
        for _, remote_name, merge_ref in heads
        if endpoints[remote_name][2] == fingerprint
    )
    if not refs:
        return LOCAL_ONLY
    return UpstreamBinding(
        RemoteEligibility.REMOTE,
        endpoint,
        public_identity,
        refs,
    )


def _configured_upstream_binding(
    repo: Path,
    heads: list[tuple[str, str, str]] | None = None,
) -> UpstreamBinding:
    try:
        configured_heads = heads if heads is not None else _configured_branch_heads(repo)
        return _binding_for_heads(repo, configured_heads)
    except RemoteClaimError:
        return UNKNOWN


_BINDING_MEMO: ContextVar[dict[tuple[str, bool], UpstreamBinding] | None] = (
    ContextVar("shadow_remote_claim_binding_memo", default=None)
)


@contextmanager
def upstream_binding_cache() -> Iterator[None]:
    """Memoize verified bindings within one bounded, explicit pass.

    No claim mutation path enters this scope: acquire/transition always binds
    fresh at call time, so a mid-flight config edit can never be masked by a
    memoized endpoint. Status and reconcile passes opt in per invocation, so
    N entities in one repository pay one resolution instead of N."""
    token = _BINDING_MEMO.set({})
    try:
        yield
    finally:
        _BINDING_MEMO.reset(token)


def upstream_binding(
    repo: Path,
    *,
    recover_detached: bool = False,
) -> UpstreamBinding:
    """Bind eligibility and transport to one verified repository endpoint."""
    memo = _BINDING_MEMO.get()
    if memo is None:
        return _upstream_binding_uncached(repo, recover_detached=recover_detached)
    key = (str(Path(os.path.abspath(repo)).resolve()), recover_detached)
    if key not in memo:
        result = _upstream_binding_uncached(repo, recover_detached=recover_detached)
        # UNKNOWN means "could not read; retry" — never memoize a transient
        # probe failure where its peer's fresh probe would have succeeded.
        if result.eligibility is not RemoteEligibility.UNKNOWN:
            memo[key] = result
        return result
    return memo[key]


def _upstream_binding_uncached(
    repo: Path,
    *,
    recover_detached: bool = False,
) -> UpstreamBinding:
    branch = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if _missing_git_value(branch):
        return _configured_upstream_binding(repo) if recover_detached else LOCAL_ONLY
    if branch.returncode:
        return UNKNOWN
    name = _one_git_value(branch)
    if name is None:
        return UNKNOWN
    try:
        heads = _configured_branch_heads(repo)
        current = [head for head in heads if head[0] == name]
        if not current:
            return (
                _configured_upstream_binding(repo, heads)
                if recover_detached
                else LOCAL_ONLY
            )
        return _binding_for_heads(repo, heads, selected_remote=current[0][1])
    except RemoteClaimError:
        return UNKNOWN


def upstream_eligibility(repo: Path) -> RemoteEligibility:
    """Classify branch tracking without treating an unreadable probe as local-only."""
    return upstream_binding(repo).eligibility


def uses_remote_upstream(repo: Path) -> bool:
    """Compatibility predicate for callers that do not own bound transport state."""
    return upstream_eligibility(repo) is RemoteEligibility.REMOTE


def managed_for_release(
    repo: Path,
    *,
    authenticated_receipt: bool,
) -> bool:
    """Require a definite local-only verdict before release skips remote state."""
    if authenticated_receipt:
        return True
    eligibility = upstream_eligibility(repo)
    if eligibility is RemoteEligibility.UNKNOWN:
        raise RemoteClaimError("remote claim eligibility is unavailable")
    return eligibility is RemoteEligibility.REMOTE


def _remote_default(repo: Path, endpoint: str) -> tuple[str, str]:
    listed = _git(repo, "ls-remote", "--symref", endpoint, "HEAD")
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


def published_file_bytes(repo: Path, default_tip: str, relative: str) -> bytes | None:
    """Read one bounded public file from an already-authenticated default tip."""
    try:
        relative_bytes = relative.encode("utf-8")
    except (AttributeError, UnicodeEncodeError):
        return None
    if (
        HEX_OBJECT.fullmatch(default_tip) is None
        or not relative
        or len(relative_bytes) > MAX_RELATIVE_BYTES
        or not relative.isprintable()
        or relative.startswith("/")
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or PRIVATE_PATH_RE.search(relative)
        or SECRET_SHAPE_RE.search(relative)
    ):
        return None
    located = _git(repo, "rev-parse", f"{default_tip}:{relative}")
    object_id = located.stdout.decode("ascii", errors="ignore").strip()
    if located.returncode or HEX_OBJECT.fullmatch(object_id) is None:
        return None
    kind = _git(repo, "cat-file", "-t", object_id)
    if kind.returncode or kind.stdout.strip() != b"blob":
        raise RemoteClaimError("published completion file is not a regular Git blob")
    measured = _git(repo, "cat-file", "-s", object_id)
    try:
        size = int(measured.stdout.decode("ascii").strip())
    except (UnicodeError, ValueError) as exc:
        raise RemoteClaimError("published completion file size is invalid") from exc
    if measured.returncode or size < 0 or size > MAX_PLAN_BYTES:
        raise RemoteClaimError("published completion file exceeds its bounded size")
    content = _git(repo, "cat-file", "blob", object_id)
    if content.returncode or len(content.stdout) != size:
        raise RemoteClaimError("published completion file could not be authenticated")
    return content.stdout


def published_plan_snapshot(
    repo: Path,
    plan_token: dict[str, str],
) -> tuple[bytes, str] | None:
    """Read the bounded current PLAN and retain its authenticated default tip."""
    if not public_safe_plan_token(plan_token):
        return None
    binding = upstream_binding(
        repo,
        recover_detached=True,
    )
    if binding.eligibility is RemoteEligibility.UNKNOWN:
        raise RemoteClaimError("published completion remote is unavailable")
    if binding.endpoint is None:
        return None
    head = plan_token["head"]
    if not binding.merge_refs:
        return None
    default_ref, default_tip = _remote_default(repo, binding.endpoint)
    if default_ref not in binding.merge_refs:
        return None
    fetched = _git(
        repo,
        "fetch",
        "--quiet",
        "--no-tags",
        "--no-write-fetch-head",
        binding.endpoint,
        default_ref,
    )
    if fetched.returncode:
        raise RemoteClaimError("published completion could not be authenticated")
    if _remote_default(repo, binding.endpoint) != (default_ref, default_tip):
        raise RemoteClaimError("published completion changed during authentication")
    if _git(repo, "merge-base", "--is-ancestor", head, default_tip).returncode:
        return None
    content = published_file_bytes(repo, default_tip, plan_token["relative"])
    return (content, default_tip) if content is not None else None


def published_plan_bytes(repo: Path, plan_token: dict[str, str]) -> bytes | None:
    """Read the bounded current PLAN only when default authority contains its head."""
    snapshot = published_plan_snapshot(repo, plan_token)
    return snapshot[0] if snapshot is not None else None


def _has_git_marker(path: Path) -> bool | None:
    try:
        current = path.resolve(strict=True)
    except OSError:
        return None
    for directory in (current, *current.parents):
        marker = directory / ".git"
        try:
            marker.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return None
        return True
    return False


def managed_repo_for_plan(
    plan: Path,
) -> tuple[RemoteEligibility, Path | None]:
    """Return explicit remote eligibility and its repository when managed."""
    marker = _has_git_marker(plan.parent)
    if marker is False:
        return RemoteEligibility.VERIFIED_LOCAL_ONLY, None
    if marker is None:
        return RemoteEligibility.UNKNOWN, None
    top = _git(plan.parent, "rev-parse", "--show-toplevel")
    if top.returncode or not top.stdout.strip():
        return RemoteEligibility.UNKNOWN, None
    try:
        top_value = _one_git_value(top)
        if top_value is None:
            return RemoteEligibility.UNKNOWN, None
        repo = Path(top_value).resolve(strict=True)
    except (OSError, UnicodeError):
        return RemoteEligibility.UNKNOWN, None
    eligibility = upstream_eligibility(repo)
    return (
        eligibility,
        repo if eligibility is RemoteEligibility.REMOTE else None,
    )


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
    endpoint: str,
    ref: str,
    entity: str,
    row: str,
    project: str,
    plan_token: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any] | None] | None:
    listed = _git(repo, "ls-remote", "--refs", endpoint, ref)
    if listed.returncode:
        return None
    listing = listed.stdout.decode("ascii", errors="ignore").strip()
    if not listing:
        return ("", None)
    fields = listing.split()
    if len(fields) != 2 or HEX_OBJECT.fullmatch(fields[0]) is None or fields[1] != ref:
        return None
    commit_id = fields[0]
    fetched = _git(repo, "fetch", "--quiet", "--no-tags", endpoint, ref)
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


def discover_active_batch(
    repo: Path,
    *,
    requests: list[dict[str, Any]],
    recover_detached: bool = False,
    verified_eligibility: RemoteEligibility | None = None,
) -> dict[str, list[dict[str, Any]] | None] | None:
    """Project active remote locks for known PLAN rows in one repository.

    Each local PLAN bounds its refs to the Method's hot-row limit. The
    conventional refs make one repository query deterministic; arbitrary
    branches are never enumerated.
    """
    binding = upstream_binding(
        repo,
        recover_detached=recover_detached,
    )
    if (
        verified_eligibility is not None
        and binding.eligibility is not verified_eligibility
    ):
        raise RemoteClaimError("remote claim eligibility changed during discovery")
    if binding.eligibility is RemoteEligibility.UNKNOWN:
        raise RemoteClaimError("remote claim eligibility is unavailable")
    if binding.eligibility is RemoteEligibility.VERIFIED_LOCAL_ONLY:
        return None
    assert binding.endpoint is not None
    if not isinstance(requests, list):
        raise RemoteClaimError("remote claim discovery input is invalid")
    active: dict[str, list[dict[str, Any]] | None] = {}
    expected: dict[str, tuple[str, str, str, str]] = {}
    for request in requests:
        if not isinstance(request, dict) or set(request) != DISCOVERY_FIELDS:
            raise RemoteClaimError("remote claim discovery input is invalid")
        entity = request["entity"]
        project = request["project"]
        rows = request["rows"]
        relative = request["relative"]
        if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
            raise RemoteClaimError("remote claim discovery input is invalid")
        unique_rows = sorted(set(rows))
        if (
            not isinstance(entity, str)
            or ENTITY.fullmatch(entity) is None
            or entity in active
            or not isinstance(project, str)
            or PROJECT.fullmatch(project) is None
            or not isinstance(relative, str)
            or len(unique_rows) > MAX_DISCOVERY_ROWS
            or any(ROW.fullmatch(row) is None for row in unique_rows)
        ):
            raise RemoteClaimError("remote claim discovery input is invalid")
        active[entity] = []
        for row in unique_rows:
            ref = claim_ref(entity, row)
            expected[ref] = (entity, row, project, relative)
    if not expected:
        return active
    listed = _git(repo, "ls-remote", "--refs", binding.endpoint, *expected)
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
        return active
    fetched = _git(
        repo, "fetch", "--quiet", "--no-tags", "--no-write-fetch-head",
        binding.endpoint, *tips,
    )
    if fetched.returncode:
        raise RemoteClaimError("remote claim discovery could not authenticate its receipts")
    for ref, commit_id in sorted(tips.items()):
        entity, row, project, relative = expected[ref]
        receipt = _validated_tip_commit(
            repo,
            commit_id=commit_id,
            ref=ref,
            entity=entity,
            row=row,
            project=project,
        )
        if receipt is None or receipt["plan"]["relative"] != relative:
            active[entity] = None
            continue
        if active[entity] is not None and receipt["state"] == "acquired":
            active[entity].append(receipt)
    return active


def discover_active(
    repo: Path,
    *,
    entity: str,
    project: str,
    rows: list[str],
    relative: str,
    recover_detached: bool = False,
) -> list[dict[str, Any]] | None:
    """Project active remote locks for one known local PLAN."""
    active = discover_active_batch(
        repo,
        requests=[
            {
                "entity": entity,
                "project": project,
                "rows": rows,
                "relative": relative,
            }
        ],
        recover_detached=recover_detached,
    )
    if active is None:
        return None
    observed = active[entity]
    if observed is None:
        raise RemoteClaimError("remote claim discovery found an unauthenticated receipt")
    return observed


def _push(
    repo: Path,
    endpoint: str,
    ref: str,
    commit_id: str,
    previous: str | None,
) -> bool:
    lease = f"--force-with-lease={ref}:{previous or ''}"
    return _git(
        repo,
        "push",
        "--porcelain",
        lease,
        endpoint,
        f"{commit_id}:{ref}",
    ).returncode == 0


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
    binding = upstream_binding(repo)
    if binding.eligibility is RemoteEligibility.VERIFIED_LOCAL_ONLY:
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
    if binding.eligibility is RemoteEligibility.UNKNOWN:
        return _result(acquired, "error", winner=None, failure="ambiguous_remote")
    assert binding.endpoint is not None
    tip = _remote_tip(
        repo,
        endpoint=binding.endpoint,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
        plan_token=None,
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
        if _push(repo, binding.endpoint, ref, commit_id, previous):
            return acquired
    observed = _remote_tip(
        repo,
        endpoint=binding.endpoint,
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
    binding = upstream_binding(
        repo,
        recover_detached=recover_detached,
    )
    if binding.eligibility is RemoteEligibility.VERIFIED_LOCAL_ONLY:
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
    if binding.eligibility is RemoteEligibility.UNKNOWN:
        return _result(desired, "error", winner=None, failure="ambiguous_remote")
    assert binding.endpoint is not None
    tip = _remote_tip(
        repo,
        endpoint=binding.endpoint,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
    )
    if tip is None:
        return _result(desired, "error", winner=None, failure="ambiguous_remote")
    previous, current = tip
    if not previous and current is None:
        commit_id = _commit_receipt(repo, desired, claim["claimed_at"])
        if commit_id is not None and _push(
            repo, binding.endpoint, ref, commit_id, None
        ):
            return desired
        observed = _remote_tip(
            repo,
            endpoint=binding.endpoint,
            ref=ref,
            entity=entity,
            row=row,
            project=project,
        )
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
    if current["state"] != "acquired":
        return _result(desired, "lost", winner=current["owner"], failure="claim_terminal")
    if current["owner"] != owner or current["claim"] != desired["claim"]:
        return _result(desired, "lost", winner=current["owner"], failure="claim_changed")
    commit_id = _commit_receipt(repo, desired, claim["claimed_at"], previous)
    if commit_id is not None and _push(
        repo, binding.endpoint, ref, commit_id, previous
    ):
        return desired
    observed = _remote_tip(
        repo,
        endpoint=binding.endpoint,
        ref=ref,
        entity=entity,
        row=row,
        project=project,
    )
    if observed is not None and observed[1] == _journal(desired):
        return desired
    return _result(desired, "error", winner=None, failure="ambiguous_remote")
