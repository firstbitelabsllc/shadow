#!/usr/bin/env python3
"""Create one repository-owned Shadow PLAN.md."""

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

## Operator Brief

- Outcome ID: ship-{project_id}
- Outcome Revision: 1
- Outcome Updated At: {now}
- Outcome State: needs_input
- Outcome: Ship one useful, evidence-backed result for {name}.
- Next: Choose the first bounded move.
- Decision ID: choose-first-move
- Decision: What should Shadow do first?
- Option A ID: inspect-current-state
- Option A: Inspect current state
- Option A Consequence: Read the repository and report the smallest useful next move.
- Option B ID: implement-smallest-result
- Option B: Build the smallest result
- Option B Consequence: Make one bounded change and prove it locally.
- Option C ID: stop-with-brief
- Option C: Brief only
- Option C Consequence: Explain current truth without changing the repository.

## Work

- [pending] Choose and complete the first bounded move

## Progress

- {now}: Shadow initialized one repository-owned plan.
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
