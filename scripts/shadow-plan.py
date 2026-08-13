#!/usr/bin/env python3
"""Inspect and migrate one authoritative Shadow plan without another queue."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_store as store  # noqa: E402
import shadow_root_board as board_store  # noqa: E402


PlanStoreError = store.PlanStoreError


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PlanStoreError(f"{label} is unreadable") from exc


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )


def _git_context(plan: Path) -> tuple[Path, Path] | None:
    if board_store.is_local_plan(plan):
        return None
    probe = _git(plan.parent, "rev-parse", "--show-toplevel")
    if probe.returncode:
        return None
    try:
        repo = Path(probe.stdout.decode("utf-8").strip()).resolve()
        relative = plan.resolve().relative_to(repo)
    except (UnicodeError, ValueError):
        raise PlanStoreError("plan does not resolve inside its Git repository") from None
    tracked = _git(repo, "ls-files", "--error-unmatch", "--", relative.as_posix())
    if tracked.returncode:
        raise PlanStoreError("Git-backed migration requires a tracked PLAN.md")
    tree = relative.parent / "PLAN.d"
    dirty = _git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        relative.as_posix(),
        tree.as_posix(),
    )
    if dirty.returncode or dirty.stdout.strip():
        raise PlanStoreError("plan root or object tree is not clean at Git HEAD")
    return repo, relative


def _reset_index(repo: Path, relative: Path) -> None:
    tree = relative.parent / "PLAN.d"
    _git(repo, "reset", "--quiet", "HEAD", "--", relative.as_posix(), tree.as_posix())


def _commit_tree(repo: Path, relative: Path, message: str) -> str:
    tree = relative.parent / "PLAN.d"
    added = _git(repo, "add", "--", relative.as_posix(), tree.as_posix())
    if added.returncode:
        raise PlanStoreError("partitioned plan could not be staged")
    committed = _git(
        repo,
        "-c", "core.hooksPath=/dev/null",
        "-c", "commit.gpgsign=false",
        "-c", "user.name=Shadow Plan",
        "-c", "user.email=shadow-plan@localhost",
        "commit", "--quiet", "--no-verify", "--no-gpg-sign", "--only",
        "-m", message, "--", relative.as_posix(), tree.as_posix(),
    )
    if committed.returncode:
        raise PlanStoreError("partitioned plan could not be committed")
    head = _git(repo, "rev-parse", "HEAD")
    if head.returncode:
        raise PlanStoreError("migration commit could not be read back")
    return head.stdout.decode("ascii").strip()


def _apply(plan: Path, board: Path | None, expected: str) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    board_before = _read(board, "board") if board is not None else None
    report = store.dry_run_migration(plan, board=board)
    if report.source_sha256 != expected:
        raise PlanStoreError("migration source digest changed; rerun the dry run")
    git_context = _git_context(plan)
    snapshot = store.PlanSnapshot.open(plan)
    transaction = store.PlanTransaction.begin(plan, expected_root=snapshot.root_sha256)
    publication = transaction.replace_content(snapshot.materialize()).publish()
    commit: str | None = None
    try:
        if board is not None and _read(board, "board") != board_before:
            raise PlanStoreError("board changed during migration")
        if git_context is not None:
            commit = _commit_tree(
                git_context[0], git_context[1], "shadow: partition authoritative plan"
            )
    except (OSError, PlanStoreError):
        store.rollback(plan, expected_root=publication.root_sha256)
        if git_context is not None:
            _reset_index(*git_context)
        store.discard_unreachable(plan, publication.new_objects)
        raise
    result = report.as_dict()
    result.update(
        {
            "action": "migrated",
            "writes": publication.object_writes + 1,
            "previous_root_sha256": publication.previous_root_sha256,
            "root_sha256": publication.root_sha256,
            "generation": publication.generation,
            "commit": commit,
            "board_preserved": board is None or _read(board, "board") == board_before,
        }
    )
    return result


def _rollback(plan: Path, board: Path | None, expected: str) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    board_before = _read(board, "board") if board is not None else None
    git_context = _git_context(plan)
    original_root = store.PlanSnapshot.open(plan).root_bytes
    receipt = store.rollback(plan, expected_root=expected)
    commit: str | None = None
    try:
        if board is not None and _read(board, "board") != board_before:
            raise PlanStoreError("board changed during rollback")
        if git_context is not None:
            commit = _commit_tree(
                git_context[0], git_context[1], "shadow: roll back partitioned plan"
            )
    except (OSError, PlanStoreError):
        store.restore_exact_root(
            plan,
            expected_current_root=receipt.root_sha256,
            target_root_bytes=original_root,
        )
        if git_context is not None:
            _reset_index(*git_context)
        raise
    return {
        "schema": "shadow.plan-rollback.v1",
        "action": "rolled_back",
        "plan": "PLAN.md",
        "expected_root_sha256": expected,
        "root_sha256": receipt.root_sha256,
        "logical_sha256": receipt.logical_sha256,
        "generation": receipt.generation,
        "commit": commit,
        "board_preserved": board is None or _read(board, "board") == board_before,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="verify a lossless plan-tree migration")
    migrate.add_argument("plan", type=Path)
    mode = migrate.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    migrate.add_argument("--expect")
    migrate.add_argument("--board", type=Path)
    rollback = commands.add_parser("rollback", help="restore the exact previous plan root")
    rollback.add_argument("plan", type=Path)
    rollback.add_argument("--expect", required=True)
    rollback.add_argument("--board", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "rollback":
            payload = _rollback(args.plan, args.board, args.expect)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.apply:
            if not args.expect:
                parser().error("migrate --apply requires --expect SOURCE_SHA256")
            payload = _apply(args.plan, args.board, args.expect)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        report = store.dry_run_migration(args.plan, board=args.board)
    except PlanStoreError as exc:
        print(f"shadow plan migrate: {exc}", file=sys.stderr)
        return 3 if "changed during dry run" in str(exc) else 2
    if (
        not report.exact_materialization
        or not report.routes_rebuilt
        or report.query_mismatches
    ):
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return 2
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
