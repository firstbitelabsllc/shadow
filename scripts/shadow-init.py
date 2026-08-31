#!/usr/bin/env python3
"""Create one machine-local Shadow PLAN.md for the current project."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import shadow_root_board as board


UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


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


def repository_recovery_identity(repo: Path, origin: str | None) -> str:
    if origin is not None:
        source = f"origin\0{origin}"
    else:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode or not result.stdout.strip():
            raise board.BoardError("repository identity could not be read")
        common_dir = Path(result.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = repo / common_dir
        source = f"local\0{common_dir.resolve()}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


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


def stable_plain_plan_snapshot(path: Path) -> tuple[str, bytes]:
    state, content = board.plan_state_snapshot(path)
    if content is None:
        raise board.BoardError("generated PLAN.md changed before registration")
    snapshot = board.open_plan(path)
    if (
        snapshot.is_tree
        or snapshot.root_bytes != content
    ):
        raise board.BoardError("generated PLAN.md changed before registration")
    return state, content


def generated_plan_snapshot(
    path: Path,
    expected: bytes,
) -> tuple[str, bytes]:
    state, content = stable_plain_plan_snapshot(path)
    if content != expected:
        raise board.BoardError("generated PLAN.md changed before registration")
    return state, content


def registration_receipt(
    repository_identity: str,
    generated_at: str,
    content: bytes,
) -> bytes:
    size, digest = board.plan_content_token(content.decode("utf-8"))
    return (
        json.dumps(
            {
                "generated_at": generated_at,
                "plan_sha256": digest,
                "plan_size": size,
                "repository_identity": repository_identity,
                "schema": "shadow.init-registration.v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def parse_registration_receipt(content: bytes) -> dict:
    try:
        receipt = json.loads(content.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise board.BoardError("init registration receipt is malformed") from exc
    if not isinstance(receipt, dict) or set(receipt) != {
        "generated_at",
        "plan_sha256",
        "plan_size",
        "repository_identity",
        "schema",
    }:
        raise board.BoardError("init registration receipt has unknown fields")
    if (
        receipt["schema"] != "shadow.init-registration.v1"
        or not isinstance(receipt["generated_at"], str)
        or UTC_TIMESTAMP.fullmatch(receipt["generated_at"]) is None
        or isinstance(receipt["plan_size"], bool)
        or not isinstance(receipt["plan_size"], int)
        or receipt["plan_size"] < 0
        or receipt["plan_size"] > board.MAX_PLAN_BYTES
        or not isinstance(receipt["plan_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", receipt["plan_sha256"]) is None
        or not isinstance(receipt["repository_identity"], str)
        or re.fullmatch(r"[0-9a-f]{64}", receipt["repository_identity"]) is None
    ):
        raise board.BoardError("init registration receipt is invalid")
    return receipt


def receipt_plan(
    receipt: dict,
    repo: Path,
    origin: str | None,
) -> bytes:
    content = plan_text(repo, receipt["generated_at"], origin=origin).encode("utf-8")
    size, digest = board.plan_content_token(content.decode("utf-8"))
    if size != receipt["plan_size"] or digest != receipt["plan_sha256"]:
        raise board.BoardError("init registration receipt does not match this repository")
    return content


def registration_seed(
    path: Path,
    repo: Path,
    state: str,
    content: bytes,
) -> dict:
    size, digest = board.plan_content_token(content.decode("utf-8"))
    return {
        "plan": str(path),
        "project": public_identifier(repo.name),
        "priority": 3,
        "candidates": ["~a1b2"],
        "rows": ["~a1b2", "~b2c3"],
        "identity": board.entity_id(path),
        "expected_size": size,
        "expected_sha256": digest,
        "witnesses": [{"plan": str(path), "expected_state": state}],
    }


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
    origin = proof_source_origin(repo)
    try:
        repository_identity = repository_recovery_identity(repo, origin)
    except board.BoardError as exc:
        print(f"shadow init: {exc}", file=sys.stderr)
        return 1
    destination_exists = destination.exists() or destination.is_symlink()
    try:
        if destination_exists:
            pending = board.read_init_registration(
                destination,
                home=Path.home(),
            )
            if pending is None:
                print(
                    "shadow init: PLAN.md already exists; refusing to overwrite",
                    file=sys.stderr,
                )
                return 1
        else:
            proposed_content = plan_text(repo, now, origin=origin).encode("utf-8")
            pending = board.prepare_init_registration(
                destination,
                registration_receipt(
                    repository_identity,
                    now,
                    proposed_content,
                ),
                home=Path.home(),
            )
        receipt = parse_registration_receipt(pending)
        if receipt["repository_identity"] != repository_identity:
            raise board.BoardError(
                "init registration receipt belongs to another repository"
            )
        content = receipt_plan(receipt, repo, origin)
    except board.BoardError as exc:
        print(f"shadow init: {exc}", file=sys.stderr)
        return 1
    try:
        write_exclusive(destination, content.decode("utf-8"))
        created = True
    except FileExistsError:
        created = False
    except OSError as exc:
        print(f"shadow init: could not write {destination}: {exc}", file=sys.stderr)
        return 1
    action = "created" if created else "recognized"
    try:
        state, frozen = generated_plan_snapshot(destination, content)
    except board.BoardError as exc:
        if created:
            print(
                f"shadow init: created {destination}, but could not freeze it: {exc}",
                file=sys.stderr,
            )
        else:
            print(
                "shadow init: PLAN.md already exists; refusing to overwrite",
                file=sys.stderr,
            )
        return 1
    def repository_witness() -> bool:
        current_origin = proof_source_origin(repo)
        if current_origin != origin:
            return False
        try:
            current_identity = repository_recovery_identity(repo, current_origin)
        except board.BoardError:
            return False
        return current_identity == repository_identity

    try:
        board.complete_init_registration(
            registration_seed(destination, repo, state, frozen),
            pending,
            repository_witness,
            home=Path.home(),
        )
    except board.BoardError as exc:
        print(
            f"shadow init: {action} {destination}, but could not register it: {exc}",
            file=sys.stderr,
        )
        return 1
    print(f"{action} local PLAN.md: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
