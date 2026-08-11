#!/usr/bin/env python3
"""Create the repository-owned Shadow PLAN.md."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


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
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if len(value) < 3:
        value = f"project-{value or 'work'}"
    return value[:48]


def display_name(value: str) -> str:
    words = [word for word in re.split(r"[-_\s]+", value) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words) or "Project"


def plan_text(repo: Path, now: str) -> str:
    project_id = public_identifier(repo.name)
    name = display_name(repo.name)
    return f"""# {name}

## Brief

- Project: {project_id}
- Mode: explore
- Outcome ID: ship-{project_id}
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

- {now}: Shadow initialized the repository-owned plan; full-outcome definition is the only unresolved product decision.
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
        description="Create PLAN.md in the current Git project without overwriting.",
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
    destination = repo / "PLAN.md"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        write_exclusive(destination, plan_text(repo, now))
    except FileExistsError:
        print("shadow init: PLAN.md already exists; refusing to overwrite", file=sys.stderr)
        return 1
    print("created PLAN.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
