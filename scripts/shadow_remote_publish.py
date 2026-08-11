#!/usr/bin/env python3
"""Publish one local board claim as a discoverable GitHub draft PR.

The computer board remains the live claim authority.  This module is only the
cross-computer transport: one deterministic branch, one PLAN receipt, and one
read-back draft PR.  It never changes the caller's checkout, index, or HEAD.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Final
from urllib.parse import urlsplit


class RemoteClaimError(ValueError):
    pass


class RemoteClaimConflict(RemoteClaimError):
    pass


CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")
CREDENTIAL: Final = re.compile(r"(?<=://)[^/\s@]+@")


def _run(
    repo: Path,
    *args: str,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    command = os.environ.get("SHADOW_GIT", "git")
    return subprocess.run(
        [command, "-C", str(repo), *args],
        input=input_bytes,
        capture_output=True,
        check=False,
        env=env,
    )


def _text(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stdout.decode("utf-8", errors="replace").strip()


def _fail(result: subprocess.CompletedProcess[bytes], action: str) -> None:
    detail = CREDENTIAL.sub("***@", result.stderr.decode("utf-8", errors="replace").strip())[:300]
    raise RemoteClaimError(f"{action} failed: {detail or 'no detail returned'}")


def _remote(repo: Path) -> str:
    result = _run(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    value = _text(result)
    if result.returncode or "/" not in value:
        raise RemoteClaimError(
            "cross-computer claim needs the current branch to track a remote trunk"
        )
    return value.split("/", 1)[0]


def _default_branch(repo: Path, remote: str) -> str:
    result = _run(repo, "ls-remote", "--symref", remote, "HEAD")
    if result.returncode:
        _fail(result, "reading the remote default branch")
    match = re.search(r"^ref: refs/heads/([^\s]+)\s+HEAD$", _text(result), flags=re.M)
    if match is None:
        raise RemoteClaimError("the remote does not advertise one default branch")
    return match.group(1)


def _branch(entity: str, row: str) -> str:
    return f"shadow/claim/{entity}/{row.removeprefix('~')}"


def _append_receipt(
    text: str,
    *,
    row: str,
    row_text: str,
    owner: str,
    entity: str,
    claimed_at: str,
    return_by: str,
    base_blob: str,
) -> str:
    for value in (row_text, owner, entity, claimed_at, return_by, base_blob):
        if CONTROL.search(value) or "|" in value:
            raise RemoteClaimError("remote claim receipt contains unsafe control text")
    receipt = (
        f"- {claimed_at} THROWN {row} {row_text} | by: {owner} | entity: {entity} "
        f"| return-by: {return_by} | base-plan: {base_blob} "
        "| transport: shadow-draft-pr-v1\n"
    )
    heading = re.search(r"^## Progress[^\n]*\n", text, flags=re.M)
    if heading is None:
        return text.rstrip("\n") + "\n\n## Progress\n\n" + receipt
    boundary = text.find("\n## ", heading.end())
    if boundary == -1:
        return text.rstrip("\n") + "\n" + receipt
    return text[:boundary].rstrip("\n") + "\n" + receipt + "\n" + text[boundary + 1 :]


def _commit_without_checkout(
    repo: Path,
    *,
    base: str,
    relative: str,
    content: bytes,
    row: str,
    owner: str,
    claimed_at: str,
) -> str:
    blob = _run(repo, "hash-object", "-w", "--stdin", input_bytes=content)
    if blob.returncode:
        _fail(blob, "recording the remote claim PLAN blob")
    with tempfile.TemporaryDirectory(prefix="shadow-claim-index-") as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        read = _run(repo, "read-tree", base, env=env)
        if read.returncode:
            _fail(read, "reading the remote trunk tree")
        update = _run(
            repo,
            "update-index",
            "--add",
            "--cacheinfo",
            "100644",
            _text(blob),
            relative,
            env=env,
        )
        if update.returncode:
            _fail(update, "placing the remote claim receipt")
        tree = _run(repo, "write-tree", env=env)
        if tree.returncode:
            _fail(tree, "writing the remote claim tree")
    commit_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Shadow",
        "GIT_AUTHOR_EMAIL": "shadow@localhost",
        "GIT_COMMITTER_NAME": "Shadow",
        "GIT_COMMITTER_EMAIL": "shadow@localhost",
        "GIT_AUTHOR_DATE": claimed_at,
        "GIT_COMMITTER_DATE": claimed_at,
    }
    commit = _run(
        repo,
        "commit-tree",
        _text(tree),
        "-p",
        base,
        input_bytes=f"shadow claim: {row} by {owner}\n".encode(),
        env=commit_env,
    )
    if commit.returncode:
        _fail(commit, "committing the remote claim receipt")
    return _text(commit)


def _target_row(text: str, row: str) -> str | None:
    matches = [
        line
        for line in text.splitlines()
        if line.startswith("- [") and re.search(rf" {re.escape(row)}(?: \(DoD\))?(?: \||$)", line)
    ]
    return matches[0] if len(matches) == 1 else None


def _ref_has_owned_receipt(
    repo: Path,
    *,
    remote: str,
    ref: str,
    commit: str,
    relative: str,
    current_plan: str,
    row: str,
    row_text: str,
    owner: str,
    entity: str,
    claimed_at: str,
    return_by: str,
) -> bool:
    fetched = _run(repo, "fetch", "--quiet", remote, ref)
    if fetched.returncode:
        return False
    observed = _run(repo, "show", f"{commit}:{relative}")
    if observed.returncode:
        return False
    try:
        text = observed.stdout.decode("utf-8")
    except UnicodeError:
        return False
    identity = (
        f"- {claimed_at} THROWN {row} {row_text} | by: {owner} | entity: {entity} "
        f"| return-by: {return_by} |"
    )
    receipts = [
        line
        for line in text.splitlines()
        if line.startswith(identity) and line.endswith("| transport: shadow-draft-pr-v1")
    ]
    return (
        len(receipts) == 1
        and _target_row(text, row) is not None
        and _target_row(text, row) == _target_row(current_plan, row)
    )


def _github_repo(repo: Path, remote: str) -> str:
    result = _run(repo, "remote", "get-url", remote)
    if result.returncode:
        _fail(result, "reading the claim remote")
    origin = _text(result)
    if origin.startswith("git@github.com:"):
        path = origin.split(":", 1)[1]
    elif origin.startswith("ssh://git@github.com/"):
        path = urlsplit(origin).path.lstrip("/")
    elif origin.startswith("https://github.com/"):
        path = urlsplit(origin).path.lstrip("/")
    else:
        override = os.environ.get("SHADOW_GITHUB_REPO", "").strip()
        if not override:
            raise RemoteClaimError(
                "cross-computer claim currently needs a GitHub origin or SHADOW_GITHUB_REPO"
            )
        return override
    return path.removesuffix(".git")


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    command = os.environ.get("SHADOW_GH", "gh")
    try:
        return subprocess.run(
            [command, *args], capture_output=True, text=True, check=False, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess([command, *args], 124, "", str(exc))


def _ensure_pr(
    repo: Path,
    *,
    remote: str,
    trunk: str,
    branch: str,
    commit: str,
    row: str,
    entity: str,
) -> dict:
    slug = _github_repo(repo, remote)

    def listed() -> list[dict]:
        result = _gh(
            "pr",
            "list",
            "--repo",
            slug,
            "--state",
            "open",
            "--search",
            f"{row} in:title",
            "--json",
            "number,headRefName,headRefOid,baseRefName,isDraft,url",
        )
        if result.returncode:
            detail = CREDENTIAL.sub("***@", result.stderr.strip())[:300]
            raise RemoteClaimError(f"GitHub claim readback failed: {detail}")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RemoteClaimError("GitHub claim readback returned malformed JSON") from exc
        return value if isinstance(value, list) else []

    matches = listed()
    if not matches:
        created = _gh(
            "pr",
            "create",
            "--repo",
            slug,
            "--draft",
            "--base",
            trunk,
            "--head",
            branch,
            "--title",
            f"Shadow claim {row} — {entity[:12]}",
            "--body",
            "Cross-computer Shadow claim transport. The project PLAN remains the task and proof authority.",
        )
        if created.returncode:
            detail = CREDENTIAL.sub("***@", created.stderr.strip())[:300]
            raise RemoteClaimError(f"GitHub draft PR creation failed: {detail}")
        matches = listed()
    exact = [
        item
        for item in matches
        if item.get("headRefName") == branch
        and item.get("headRefOid") == commit
        and item.get("baseRefName") == trunk
        and item.get("isDraft") is True
        and isinstance(item.get("url"), str)
    ]
    if len(exact) != 1:
        raise RemoteClaimError(
            "the remote claim branch is not backed by one matching open draft PR"
        )
    return exact[0]


def publish(
    repo: Path,
    *,
    plan_token: dict[str, str],
    plan_text: str,
    row: str,
    row_text: str,
    owner: str,
    entity: str,
    claimed_at: str,
    return_by: str,
) -> dict:
    remote = _remote(repo)
    trunk = _default_branch(repo, remote)
    fetched = _run(repo, "fetch", "--quiet", remote, trunk)
    if fetched.returncode:
        _fail(fetched, "refreshing the remote trunk")
    base_ref = f"{remote}/{trunk}"
    base = _run(repo, "rev-parse", "--verify", base_ref)
    remote_blob = _run(repo, "rev-parse", f"{base_ref}:{plan_token['relative']}")
    if base.returncode or remote_blob.returncode:
        raise RemoteClaimError("the remote trunk does not contain the claimed project plan")
    if _text(remote_blob) != plan_token["blob"]:
        raise RemoteClaimError(
            "the remote trunk PLAN changed; refresh the project before publishing this claim"
        )
    body = _append_receipt(
        plan_text,
        row=row,
        row_text=row_text,
        owner=owner,
        entity=entity,
        claimed_at=claimed_at,
        return_by=return_by,
        base_blob=plan_token["blob"],
    ).encode()

    def make_commit(parent: str) -> str:
        return _commit_without_checkout(
            repo,
            base=parent,
            relative=plan_token["relative"],
            content=body,
            row=row,
            owner=owner,
            claimed_at=claimed_at,
        )

    base_commit = _text(base)
    commit = make_commit(base_commit)
    branch = _branch(entity, row)
    ref = f"refs/heads/{branch}"
    observed = _run(repo, "ls-remote", "--refs", remote, ref)
    if observed.returncode:
        _fail(observed, "checking the deterministic claim branch")
    lines = _text(observed).splitlines()
    if not lines:
        pushed = _run(
            repo,
            "push",
            f"--force-with-lease={ref}:",
            remote,
            f"{commit}:{ref}",
        )
        if pushed.returncode:
            observed = _run(repo, "ls-remote", "--refs", remote, ref)
            lines = _text(observed).splitlines() if observed.returncode == 0 else []
            if not lines or lines[0].split()[0] != commit:
                raise RemoteClaimConflict(
                    "another computer won the deterministic remote claim"
                )
    elif lines[0].split()[0] != commit:
        existing = lines[0].split()[0]
        if not _ref_has_owned_receipt(
            repo,
            remote=remote,
            ref=ref,
            commit=existing,
            relative=plan_token["relative"],
            current_plan=plan_text,
            row=row,
            row_text=row_text,
            owner=owner,
            entity=entity,
            claimed_at=claimed_at,
            return_by=return_by,
        ):
            raise RemoteClaimConflict(
                "the deterministic remote claim is owned by another receipt"
            )
        resumed = _run(
            repo,
            "push",
            f"--force-with-lease={ref}:{existing}",
            remote,
            f"{commit}:{ref}",
        )
        if resumed.returncode:
            raise RemoteClaimConflict(
                "the self-owned remote claim changed while it was being resumed"
            )
    readback = _run(repo, "ls-remote", "--refs", remote, "refs/heads/shadow/claim/*")
    if readback.returncode:
        _fail(readback, "discovering remote claims")
    if f"{commit}\t{ref}" not in _text(readback).splitlines():
        raise RemoteClaimError("the claim branch is not discoverable from the public namespace")
    pr = _ensure_pr(
        repo,
        remote=remote,
        trunk=trunk,
        branch=branch,
        commit=commit,
        row=row,
        entity=entity,
    )
    refreshed = _run(repo, "fetch", "--quiet", remote, trunk)
    if refreshed.returncode:
        _fail(refreshed, "rechecking the remote trunk after draft PR readback")
    latest = _run(repo, "rev-parse", "--verify", base_ref)
    if latest.returncode:
        _fail(latest, "re-reading the remote trunk after draft PR readback")
    latest_base = _text(latest)
    if latest_base != base_commit:
        latest_blob = _run(repo, "rev-parse", f"{base_ref}:{plan_token['relative']}")
        if latest_blob.returncode or _text(latest_blob) != plan_token["blob"]:
            raise RemoteClaimError(
                "the remote PLAN changed while the draft claim was published; no goal emitted"
            )
        rebased = make_commit(latest_base)
        moved = _run(
            repo,
            "push",
            f"--force-with-lease={ref}:{commit}",
            remote,
            f"{rebased}:{ref}",
        )
        if moved.returncode:
            raise RemoteClaimConflict(
                "the remote claim changed while rebasing onto the refreshed trunk"
            )
        commit = rebased
        pr = _ensure_pr(
            repo,
            remote=remote,
            trunk=trunk,
            branch=branch,
            commit=commit,
            row=row,
            entity=entity,
        )
        final_fetch = _run(repo, "fetch", "--quiet", remote, trunk)
        final_base = _run(repo, "rev-parse", "--verify", base_ref)
        if (
            final_fetch.returncode
            or final_base.returncode
            or _text(final_base) != latest_base
        ):
            raise RemoteClaimError(
                "the remote trunk kept moving during claim readback; no goal emitted"
            )
    return {"branch": branch, "commit": commit, "pr": pr}
