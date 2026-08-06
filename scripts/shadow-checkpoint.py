#!/usr/bin/env python3
"""Checkpoint one PLAN.md row and write one bounded project-local receipt."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any


MAX_PLAN_BYTES = 1_000_000
MAX_FIELD_CHARS = 1_000
TASK_RE = re.compile(r"^(?P<prefix>\s*-\s*\[)(?P<state>[^]]+)(?P<suffix>\]\s*)(?P<body>.+?)\s*$")
PRIVATE_PATH_RE = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)")
SECRET_RE = re.compile(
    r"(?:\b(?:sk|ghp|github_pat|xox[baprs])-[-A-Za-z0-9_]{8,}|"
    r"\bAKIA[0-9A-Z]{12,}|\bBearer\s+[A-Za-z0-9._~+/-]{8,}|"
    r"(?:token|password|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


class CheckpointError(ValueError):
    pass


def safe_field(value: str, label: str, *, required: bool = True) -> str:
    clean = " ".join(value.split())
    if required and not clean:
        raise CheckpointError(f"{label} is required")
    if len(clean) > MAX_FIELD_CHARS:
        raise CheckpointError(f"{label} exceeds {MAX_FIELD_CHARS} characters")
    if PRIVATE_PATH_RE.search(clean):
        raise CheckpointError(f"{label} contains an absolute private path")
    if SECRET_RE.search(clean):
        raise CheckpointError(f"{label} appears to contain a credential")
    return clean


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode:
        raise CheckpointError(result.stderr.strip() or "Git command failed")
    return result


def repository_root(plan: Path) -> Path:
    result = git(plan.parent, "rev-parse", "--show-toplevel")
    root = Path(result.stdout.strip()).resolve()
    try:
        plan.relative_to(root)
    except ValueError as exc:
        raise CheckpointError("PLAN.md is outside its Git worktree") from exc
    return root


def atomic_replace(path: Path, text: str, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IMODE(mode))
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_create(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".receipt.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            return False
        return True
    finally:
        temporary_path.unlink(missing_ok=True)


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (result or "checkpoint")[:64]


def receipt_core(args: argparse.Namespace, plan_relative: str) -> dict[str, Any]:
    return {
        "schema": "shadow.checkpoint.v1",
        "plan": plan_relative,
        "task": safe_field(args.task, "task"),
        "summary": safe_field(args.summary, "summary"),
        "proof": safe_field(args.proof, "proof"),
        "status": args.status,
        "outcome": args.outcome,
        "blocker": safe_field(args.blocker or "", "blocker", required=False) or None,
    }


def receipt_id(core: dict[str, Any]) -> str:
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def update_plan(text: str, task: str, status: str, progress: str, marker: str) -> str:
    if marker in text:
        return text
    lines = text.splitlines()
    target = " ".join(task.split())
    matches: list[int] = []
    for index, line in enumerate(lines):
        match = TASK_RE.match(line)
        if match and " ".join(match.group("body").split()) == target:
            matches.append(index)
    if len(matches) != 1:
        raise CheckpointError("task must match exactly one PLAN.md checkbox row")
    index = matches[0]
    match = TASK_RE.match(lines[index])
    assert match is not None
    next_state = "completed" if status in {"done", "done_with_concerns"} else "blocked"
    lines[index] = f"{match.group('prefix')}{next_state}{match.group('suffix')}{match.group('body')}"
    progress_index = next((i for i, line in enumerate(lines) if line.strip() == "## Progress"), None)
    if progress_index is None:
        lines.extend(["", "## Progress", ""])
    elif progress_index == len(lines) - 1:
        lines.append("")
    lines.append(progress)
    return "\n".join(lines).rstrip() + "\n"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="shadow checkpoint", description=__doc__)
    value.add_argument("plan_path")
    value.add_argument("task")
    value.add_argument("summary")
    value.add_argument("--proof", required=True)
    value.add_argument("--blocker")
    value.add_argument("--status", choices=("done", "done_with_concerns", "blocked"), default="done")
    value.add_argument("--outcome", choices=("useful", "busy", "blocked_clarified"))
    value.add_argument("--commit", action="store_true")
    value.add_argument("--json", action="store_true")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    plan_input = Path(args.plan_path).expanduser()
    if plan_input.is_symlink() or not plan_input.is_file() or plan_input.name != "PLAN.md":
        raise CheckpointError("plan path must be a regular non-symlink PLAN.md")
    if plan_input.stat().st_size > MAX_PLAN_BYTES:
        raise CheckpointError("PLAN.md exceeds the bounded size limit")
    plan = plan_input.resolve()
    repo = repository_root(plan)
    plan_relative = plan.relative_to(repo).as_posix()
    core = receipt_core(args, plan_relative)
    identifier = receipt_id(core)
    marker = f"[receipt:{identifier}]"
    evidence_relative = Path(".shadow") / "evidence" / f"{slug(core['task'])}-{identifier}.json"
    evidence = repo / evidence_relative
    state = repo / ".shadow"
    evidence_dir = state / "evidence"
    if state.is_symlink() or evidence_dir.is_symlink() or evidence.is_symlink():
        raise CheckpointError("receipt path must not contain symlinks")

    existing = evidence.read_text(encoding="utf-8") if evidence.is_file() else None
    if existing is not None:
        payload = json.loads(existing)
        if payload.get("receipt_id") != identifier:
            raise CheckpointError("existing receipt does not match this checkpoint")
        return payload

    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    progress = (
        f"- {recorded_at[:10]}: {core['summary']} Proof: {core['proof']} "
        f"{marker}"
    )
    if core["blocker"]:
        progress += f" Blocker: {core['blocker']}"
    original = plan.read_text(encoding="utf-8")
    updated = update_plan(original, core["task"], core["status"], progress, marker)
    if updated != original:
        atomic_replace(plan, updated, plan.stat().st_mode)

    payload = {
        **core,
        "receipt_id": identifier,
        "recorded_at": recorded_at,
        "evidence": evidence_relative.as_posix(),
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if not atomic_create(evidence, encoded):
        current = json.loads(evidence.read_text(encoding="utf-8"))
        if current.get("receipt_id") != identifier:
            raise CheckpointError("receipt collision")
        payload = current

    if args.commit:
        git(repo, "add", "--", plan_relative, evidence_relative.as_posix())
        staged = git(repo, "diff", "--cached", "--quiet", check=False)
        if staged.returncode == 1:
            git(repo, "commit", "-m", f"shadow: {core['summary']}")
        elif staged.returncode not in {0, 1}:
            raise CheckpointError("cannot inspect staged checkpoint")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = run(args)
    except (CheckpointError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"shadow checkpoint: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"shadow checkpoint: {payload['status']} ({payload['evidence']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
