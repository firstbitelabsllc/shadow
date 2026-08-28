#!/usr/bin/env python3
"""Create one machine-local Shadow PLAN.md for the current project."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import shadow_root_board as board


def repository_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("current directory is not inside a Git worktree")
    return Path(result.stdout.strip()).resolve()


def public_identifier(value: str) -> str:
    return board.local_plan_slug(value)[:32]


def display_name(value: str) -> str:
    words = [word for word in re.split(r"[-_\s]+", value) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words) or "Project"


def proof_source_origin(repo: Path) -> str | None:
    """Return this checkout's normalized public origin, or omit a private path."""
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not result.stdout.strip():
        return None
    identity = board.normalized_origin(result.stdout.strip())
    try:
        return board.well_formed_proof_origin(identity)
    except ValueError:
        return None


def plan_text(repo: Path, now: str, *, origin: str | None = None) -> str:
    project_id = public_identifier(repo.name)
    name = display_name(repo.name)
    origin_line = f"- Origin: {origin}\n" if origin else ""
    return f"""# {name}

## Brief

- Project: {project_id}
- Mode: explore
{origin_line}- Outcome ID: ship-{project_id}
- Outcome Revision: 1
- Outcome Updated At: {now}
- Outcome State: needs_input
- Outcome: Complete the full declared outcome for {name}; move every reachable lane to proof or an exact hard-rail wake.
- Next: Derive the complete acceptance matrix from repository evidence, then claim and execute every safe reachable lane.
- Decision ID: define-full-outcome
- Decision: What complete product outcome and acceptance matrix govern this project?
- Option A ID: derive-and-execute
- Option A: Derive and execute
- Option A Consequence: Read current source, plans, reports, and real surfaces; record the full matrix and start every safe disjoint lane.
- Option B ID: execute-declared-outcome
- Option B: Execute declared requirements
- Option B Consequence: Preserve the existing product intent, fill missing acceptance behavior, and drain all reachable work.
- Option C ID: isolate-product-forks
- Option C: Isolate true product forks
- Option C Consequence: Park only irrecoverable intent questions with exact wakes and continue all unambiguous work.

## Tasks

### M1 — complete outcome
- [pending] the full product outcome, scenario matrix, hard rails, and proof tiers are recorded from current evidence ~a1b2 | proof: read PLAN.md -> the Brief and task rows name every required surface and acceptance behavior
- [pending] every reachable row is proven and integrated or parked solely on an exact hard-rail wake ~b2c3 (DoD) | proof: read PLAN.md -> no agent-reachable acceptance work remains

## Progress

- {now}: Shadow initialized the machine-local plan; full-outcome definition is the only unresolved product decision.
"""


def write_exclusive(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    fd, temporary = tempfile.mkstemp(prefix=".PLAN.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            raise FileExistsError(path) from None
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary_path.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="shadow init",
        description="Create a local PLAN.md under ~/.shadow/plans without overwriting.",
    )
    result.add_argument("--here", action="store_true", help="initialize the current Git project")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.here:
        parser().error("--here is required")
    current = Path.cwd().resolve()
    try:
        repo = repository_root(current)
    except ValueError as exc:
        print(f"shadow init: {exc}", file=sys.stderr)
        return 2
    if current != repo:
        print("shadow init: run --here from the Git project root", file=sys.stderr)
        return 2
    destination = (
        Path.home()
        / ".shadow"
        / "plans"
        / board.local_plan_slug(repo.name)
        / "PLAN.md"
    )
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text = plan_text(repo, now, origin=proof_source_origin(repo))
    try:
        write_exclusive(destination, text)
    except FileExistsError:
        print("shadow init: PLAN.md already exists; refusing to overwrite", file=sys.stderr)
        return 1
    size, digest = board.plan_content_token(text)
    try:
        board.reconcile(
            [{
                "plan": str(destination),
                "project": public_identifier(repo.name),
                "priority": 3,
                "candidates": ["~a1b2"],
                "rows": ["~a1b2", "~b2c3"],
                "expected_identity": board.entity_id(destination),
                "expected_size": size,
                "expected_sha256": digest,
            }],
            [],
            home=Path.home(),
        )
    except board.BoardError as exc:
        print(
            f"shadow init: created {destination}, but could not register it: {exc}",
            file=sys.stderr,
        )
        return 1
    print(f"created local PLAN.md: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
