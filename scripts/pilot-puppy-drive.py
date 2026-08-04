#!/usr/bin/env python3
"""Prepare foreground, PLAN-owned Pilot Puppy Drive sessions.

Preparation reads one clean Git project's existing PLAN.md and writes bounded
local evidence for up to three ready, path-disjoint native-host handoffs.  It
never starts a host, creates a worktree, changes source, or contacts a remote
service.  A later explicit launch must re-check the frozen plan and routes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any

from pilot_puppy_drive_lib import (
    DrivePacketError,
    extract_document,
    plan_sha256,
    select_disjoint_ready_lanes,
)
from pilot_puppy_roster_lib import RosterError, default_roster_path, load_roster
from pilot_puppy_route_lib import RoutePacketError, load_route_packet, route_sha256
import pilot_puppy_telemetry as telemetry


SESSION_SCHEMA = "pilot-puppy.drive-session.v1"
MAX_PLAN_BYTES = 1_000_000
MAX_SESSION_BYTES = 64 * 1024
SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ACCEPTED_SESSION_STATE = "accepted"


class DriveError(ValueError):
    """Preparation cannot safely continue from the current local project."""


def load_script_module(name: str, filename: str):
    source = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise DriveError("local route helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROUTE = load_script_module("pilot_puppy_drive_route", "pilot-puppy-route.py")
HOST = load_script_module("pilot_puppy_drive_host", "pilot-puppy-host.py")


def git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DriveError("project Git state cannot be read") from exc
    if result.returncode:
        raise DriveError("project Git state cannot be read")
    return result.stdout.strip()


def exact_git_root(value: Path) -> Path:
    candidate = value.expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise DriveError("project must be a regular Git worktree root")
    root = Path(git(candidate, "rev-parse", "--show-toplevel")).resolve()
    if root != candidate.resolve():
        raise DriveError("project must be an exact Git worktree root")
    return root


def clean_head(repo: Path) -> str:
    if git(repo, "status", "--porcelain=v1", "--untracked-files=normal"):
        raise DriveError("save or commit the current project changes before preparing ready work")
    return git(repo, "rev-parse", "--verify", "HEAD")


def plan_path(repo: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts or candidate.name != "PLAN.md":
        raise DriveError("plan must be a relative PLAN.md path inside the project")
    path = (repo / candidate).resolve(strict=False)
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise DriveError("plan must stay inside the project") from exc
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PLAN_BYTES:
        raise DriveError("plan must be a bounded regular PLAN.md file")
    return path


def read_plan(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DriveError("plan cannot be read safely") from exc


def evidence_directory(repo: Path) -> Path:
    state = repo / ".pilot-puppy"
    evidence = state / "evidence"
    if state.is_symlink() or evidence.is_symlink():
        raise DriveError("project evidence path must not contain a symlink")
    if state.exists() and not state.is_dir():
        raise DriveError("project evidence state is not a directory")
    if state.exists() and any(path.name != "evidence" for path in state.iterdir()):
        raise DriveError("project evidence state contains unexpected files")
    if evidence.exists() and not evidence.is_dir():
        raise DriveError("project evidence is not a directory")
    state.mkdir(mode=0o700, exist_ok=True)
    evidence.mkdir(mode=0o700, exist_ok=True)
    return evidence


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise DriveError("Drive preparation output already exists")
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".drive.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise DriveError("Drive preparation output already exists") from None
    finally:
        temporary.unlink(missing_ok=True)


def prepare(
    *,
    repo: Path,
    plan: Path,
    roster_path: Path,
    availability: str,
    session_id: str,
    base_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    """Write route packets and one session record; never launch a host."""

    source = read_plan(plan)
    document = extract_document(source)
    if document is None:
        raise DriveError("this plan has no Pilot Puppy Drive Packet yet")
    try:
        roster = load_roster(roster_path.expanduser())
    except RosterError as exc:
        raise DriveError("local work-role setup is unavailable") from exc
    route_candidates: list[dict[str, Any]] = []
    notices: list[dict[str, str]] = []
    for lane in document["lanes"]:
        if lane["state"] != "ready":
            continue
        task_sha256 = hashlib.sha256(lane["task"].encode("utf-8")).hexdigest()
        try:
            route = ROUTE.route_document(
                task_id=lane["id"],
                task_hash=task_sha256,
                roster=roster,
                task_kind=lane["task_kind"],
                role=lane["task_kind"],
                host=None,
                availability=availability,
            )
        except (RoutePacketError, ValueError):
            notices.append({"id": lane["id"], "reason": "needs_a_ready_coding_tool"})
            continue
        candidate = dict(lane)
        if route["status"] != "ready" or route["selection"] is None:
            notices.append({"id": lane["id"], "reason": "needs_a_ready_coding_tool"})
            continue
        candidate["selection"] = {
            "role": route["selection"]["role"],
            "host": route["selection"]["host"],
            "route": route,
        }
        route_candidates.append(candidate)
    selected, selection_notices = select_disjoint_ready_lanes({**document, "lanes": route_candidates})
    notices.extend(selection_notices)
    if not selected:
        raise DriveError("there is no ready work that can start safely from this project")
    evidence = evidence_directory(repo)
    prepared: list[dict[str, Any]] = []
    for lane in selected:
        route_document = lane["selection"]["route"]
        route_file = evidence / f"drive-{session_id}-{lane['id']}.route.json"
        ROUTE.write_exclusive(route_file, route_document)
        telemetry.record_route(route_document)
        prepared.append(
            {
                "id": lane["id"],
                "observation_id": hashlib.sha256(f"{session_id}:{lane['id']}".encode("utf-8")).hexdigest()[:32],
                "role": lane["selection"]["role"],
                "host": lane["selection"]["host"],
                "route_sha256": route_sha256(route_document),
                "status": "prepared",
                "scope_ok": None,
                "proof_ok": None,
                "merge_ok": None,
            }
        )
    session = {
        "schema": SESSION_SCHEMA,
        "revision": 1,
        "session_id": session_id,
        "state": "prepared",
        "plan_sha256": plan_sha256(source),
        "base_sha256": base_sha256,
        "lanes": prepared,
    }
    write_exclusive(evidence / f"drive-{session_id}.json", session)
    return session, selected, notices


def session_file(repo: Path, session_id: str) -> Path:
    if SESSION_ID_RE.fullmatch(session_id) is None:
        raise DriveError("Drive session ID is invalid")
    path = evidence_directory(repo) / f"drive-{session_id}.json"
    try:
        valid = not path.is_symlink() and path.is_file() and path.stat().st_size <= MAX_SESSION_BYTES
    except OSError:
        valid = False
    if not valid:
        raise DriveError("prepared Drive session is unavailable")
    return path


def validate_session(value: object, session_id: str) -> dict[str, Any]:
    fields = {"schema", "revision", "session_id", "state", "plan_sha256", "base_sha256", "lanes"}
    if not isinstance(value, dict) or set(value) != fields:
        raise DriveError("prepared Drive session is invalid")
    if (
        value["schema"] != SESSION_SCHEMA
        or value["revision"] != 1
        or value["session_id"] != session_id
        or not isinstance(value["state"], str)
        or value["state"] not in {"prepared", "running", "finished", ACCEPTED_SESSION_STATE}
        or not isinstance(value["plan_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["plan_sha256"])
        or not isinstance(value["base_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{40,64}", value["base_sha256"])
        or not isinstance(value["lanes"], list)
        or not 1 <= len(value["lanes"]) <= 3
    ):
        raise DriveError("prepared Drive session is invalid")
    lanes: list[dict[str, Any]] = []
    expected_lane_fields = {
        "id",
        "observation_id",
        "role",
        "host",
        "route_sha256",
        "status",
        "scope_ok",
        "proof_ok",
        "merge_ok",
    }
    seen: set[str] = set()
    for item in value["lanes"]:
        if not isinstance(item, dict) or set(item) != expected_lane_fields:
            raise DriveError("prepared Drive session is invalid")
        if (
            not isinstance(item["id"], str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", item["id"])
            or item["id"] in seen
            or not isinstance(item["observation_id"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", item["observation_id"])
            or not isinstance(item["role"], str)
            or item["role"] not in {"dev", "debug", "hard-dev"}
            or not isinstance(item["host"], str)
            or item["host"] not in {"codex", "claude-code", "cursor"}
            or not isinstance(item["route_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", item["route_sha256"])
            or not isinstance(item["status"], str)
            or item["status"] not in {"prepared", "passed", "needs_attention"}
            or any(value is not None and type(value) is not bool for value in (item["scope_ok"], item["proof_ok"], item["merge_ok"]))
        ):
            raise DriveError("prepared Drive session is invalid")
        seen.add(item["id"])
        lanes.append(dict(item))
    return {
        "schema": SESSION_SCHEMA,
        "revision": 1,
        "session_id": session_id,
        "state": value["state"],
        "plan_sha256": value["plan_sha256"],
        "base_sha256": value["base_sha256"],
        "lanes": lanes,
    }


def read_session(repo: Path, session_id: str) -> tuple[Path, dict[str, Any]]:
    path = session_file(repo, session_id)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DriveError("prepared Drive session is invalid") from exc
    return path, validate_session(raw, session_id)


def replace_session(path: Path, session: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        raise DriveError("prepared Drive session is unavailable")
    encoded = (json.dumps(session, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".drive-update.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def launch_head(repo: Path) -> str:
    try:
        state = HOST.local_state_snapshot(repo)
        changed = HOST.status_paths(repo)
    except HOST.HostError as exc:
        raise DriveError("project is not sealed for a Drive launch") from exc
    if any(path not in state for path in changed):
        raise DriveError("save or commit project changes before launching ready work")
    return git(repo, "rev-parse", "--verify", "HEAD")


def route_for_lane(repo: Path, session_id: str, lane: dict[str, Any]) -> dict[str, Any]:
    path = evidence_directory(repo) / f"drive-{session_id}-{lane['id']}.route.json"
    if path.is_symlink() or not path.is_file():
        raise DriveError("a prepared handoff is unavailable")
    try:
        route = load_route_packet(path)
    except RoutePacketError as exc:
        raise DriveError("a prepared handoff is invalid") from exc
    if route_sha256(route) != lane["route_sha256"]:
        raise DriveError("a prepared handoff changed after preparation")
    return route


def worktree_path(repo: Path, session_id: str, lane_id: str) -> Path:
    parent = repo.parent / f"{repo.name}-pilot-puppy-drive"
    session_root = parent / session_id
    destination = session_root / lane_id
    for path in (parent, session_root, destination):
        if path.is_symlink():
            raise DriveError("Drive worktree location is unsafe")
    if destination.exists():
        raise DriveError("the prepared worktree already exists and is kept for review")
    parent.mkdir(mode=0o700, exist_ok=True)
    session_root.mkdir(mode=0o700, exist_ok=True)
    return destination


def create_worktree(repo: Path, session_id: str, lane_id: str, base_sha256: str) -> Path:
    destination = worktree_path(repo, session_id, lane_id)
    branch = f"pilot-puppy/drive-{session_id[:12]}-{lane_id}"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(destination), base_sha256],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DriveError("a clean worktree could not be created for this piece of work") from exc
    if result.returncode:
        raise DriveError("a clean worktree could not be created for this piece of work")
    return destination


def new_review_attempt(repo: Path, session_id: str) -> Path:
    """Reserve a fresh kept review attempt without deleting a failed attempt."""

    parent = repo.parent / f"{repo.name}-pilot-puppy-lead-review"
    session_root = parent / session_id
    for path in (parent, session_root):
        if path.is_symlink():
            raise DriveError("lead review location is unsafe")
    parent.mkdir(mode=0o700, exist_ok=True)
    session_root.mkdir(mode=0o700, exist_ok=True)
    for number in range(1, 100):
        attempt = session_root / f"attempt-{number:02d}"
        if attempt.is_symlink():
            raise DriveError("lead review location is unsafe")
        if attempt.exists():
            continue
        attempt.mkdir(mode=0o700)
        return attempt
    raise DriveError("too many kept lead review attempts exist for this Drive session")


def drive_branch_name(session_id: str, lane_id: str) -> str:
    return f"pilot-puppy/drive-{session_id[:12]}-{lane_id}"


def git_completed(repo: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DriveError("project Git state cannot be read") from exc


def branch_commit(repo: Path, session_id: str, lane_id: str) -> tuple[str, str]:
    branch = drive_branch_name(session_id, lane_id)
    result = git_completed(repo, "rev-parse", "--verify", f"{branch}^{{commit}}")
    if result.returncode:
        raise DriveError("the kept review branch is unavailable")
    return branch, result.stdout.strip()


def branch_contains_base(repo: Path, base_sha256: str, commit: str) -> bool:
    result = git_completed(repo, "merge-base", "--is-ancestor", base_sha256, commit)
    if result.returncode not in {0, 1}:
        raise DriveError("the kept review branch cannot be verified")
    return result.returncode == 0


def changed_paths_between(repo: Path, base_sha256: str, commit: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only", "-z", base_sha256, commit],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DriveError("the kept review branch cannot be verified") from exc
    if result.returncode:
        raise DriveError("the kept review branch cannot be verified")
    try:
        return [item.decode("utf-8", errors="strict") for item in result.stdout.split(b"\0") if item]
    except UnicodeDecodeError as exc:
        raise DriveError("the kept review branch cannot be verified") from exc


def commit_diff_is_clean(repo: Path, base_sha256: str, commit: str) -> bool:
    result = git_completed(repo, "diff", "--check", base_sha256, commit)
    return result.returncode == 0


def cached_diff_is_clean(repo: Path) -> bool:
    result = git_completed(repo, "diff", "--cached", "--check")
    return result.returncode == 0


def create_lead_review_worktree(repo: Path, attempt: Path, lane_id: str, commit: str) -> Path:
    destination = attempt / lane_id
    if destination.is_symlink() or destination.exists():
        raise DriveError("lead review location is unsafe")
    result = git_completed(repo, "worktree", "add", "--detach", str(destination), commit, timeout=30)
    if result.returncode:
        raise DriveError("a clean lead review checkout could not be created")
    return destination


def lead_review_passes(worktree: Path, proof: list[str], timeout_seconds: int) -> bool:
    if not proof_passes(worktree, proof, timeout_seconds):
        return False
    try:
        return not HOST.status_paths(worktree)
    except HOST.HostError:
        return False


def commit_identity_is_ready(repo: Path) -> bool:
    return git_completed(repo, "var", "GIT_COMMITTER_IDENT").returncode == 0


def merge_in_progress(repo: Path) -> bool:
    return git_completed(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0


def abort_our_merge(repo: Path) -> None:
    if not merge_in_progress(repo):
        return
    result = git_completed(repo, "merge", "--abort")
    if result.returncode:
        raise DriveError("the local merge needs manual recovery")


def merge_review_branches(
    *,
    repo: Path,
    branches: list[str],
    allowed_paths: list[str],
    proofs: list[list[str]],
    timeout_seconds: int,
    session_id: str,
) -> None:
    """Merge only already-reviewed local branches as one explicit action."""

    result = git_completed(repo, "merge", "--no-ff", "--no-commit", *branches, timeout=60)
    if result.returncode:
        abort_our_merge(repo)
        raise DriveError("the checked work could not be brought together safely")
    try:
        changed = HOST.status_paths(repo)
        if not changed or not all(HOST.path_allowed(path, allowed_paths) for path in changed):
            raise DriveError("the checked work changed outside its declared files")
        if not cached_diff_is_clean(repo):
            raise DriveError("the checked work has a whitespace error")
        if not all(proof_passes(repo, proof, timeout_seconds) for proof in proofs):
            raise DriveError("the checked work did not pass its named check after review")
        changed = HOST.status_paths(repo)
        if not changed or not all(HOST.path_allowed(path, allowed_paths) for path in changed):
            raise DriveError("the checked work changed outside its declared files")
        committed = git_completed(repo, "commit", "-m", f"pilot-puppy accept: {session_id}", timeout=30)
        if committed.returncode:
            raise DriveError("the local acceptance commit could not be created")
    except DriveError:
        abort_our_merge(repo)
        raise


def task_file(text: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix="pilot-puppy-drive-", suffix=".md")
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def proof_passes(worktree: Path, argv: list[str], timeout_seconds: int) -> bool:
    try:
        result = subprocess.run(
            argv,
            cwd=worktree,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def diff_is_clean(worktree: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--check"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def all_changes_are_allowed(worktree: Path, allowed_paths: list[str]) -> bool:
    try:
        changed = HOST.status_paths(worktree, include_ignored=True)
    except HOST.HostError:
        return False
    return all(
        HOST.path_allowed(path, allowed_paths) or path.startswith(".pilot-puppy/evidence/")
        for path in changed
    )


def commit_lane(worktree: Path, lane_id: str, allowed_paths: list[str]) -> bool:
    try:
        staged = subprocess.run(
            ["git", "-C", str(worktree), "add", "--", *allowed_paths],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        if staged.returncode:
            return False
        has_diff = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--cached", "--quiet"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        if has_diff.returncode != 1:
            return False
        committed = subprocess.run(
            ["git", "-C", str(worktree), "commit", "-m", f"pilot-puppy drive: {lane_id}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return committed.returncode == 0


def lane_result(
    *,
    repo: Path,
    session_id: str,
    session_lane: dict[str, Any],
    packet_lane: dict[str, Any],
    roster_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run exactly one prepared lane. Errors stay as a bounded local status."""

    result = dict(session_lane)
    started = time.monotonic()
    try:
        route = route_for_lane(repo, session_id, session_lane)
        expected_hash = hashlib.sha256(packet_lane["task"].encode("utf-8")).hexdigest()
        if route["binding"]["task_id"] != packet_lane["id"] or route["binding"]["task_sha256"] != expected_hash:
            raise DriveError("prepared work no longer matches the plan")
        worktree = create_worktree(repo, session_id, packet_lane["id"], session_lane["base_sha256"])
        destination = worktree / ".pilot-puppy" / "evidence" / f"drive-{session_id}-{packet_lane['id']}.route.json"
        ROUTE.write_exclusive(destination, route)
        temporary_task = task_file(packet_lane["task"])
        try:
            args = argparse.Namespace(
                host=session_lane["host"],
                binary=None,
                repo=str(worktree),
                task_file=str(temporary_task),
                task_id=packet_lane["id"],
                allowed_path=packet_lane["allowed_paths"],
                route_file=f".pilot-puppy/evidence/{destination.name}",
                roster_file=str(roster_path.expanduser()),
                use_seat=False,
                seat_file=None,
                out=str(worktree / ".pilot-puppy" / "evidence" / f"drive-{session_id}-{packet_lane['id']}.attempt.json"),
                force=False,
                timeout_seconds=timeout_seconds,
                json=False,
            )
            attempt, code = HOST.run_attempt(args)
        finally:
            temporary_task.unlink(missing_ok=True)
        if code != 0 or attempt.get("status") != "ok":
            result.update({"status": "needs_attention", "scope_ok": None, "proof_ok": None, "merge_ok": None})
            return result
        if not all_changes_are_allowed(worktree, packet_lane["allowed_paths"]):
            result.update({"status": "needs_attention", "scope_ok": False, "proof_ok": None, "merge_ok": None})
            return result
        if not diff_is_clean(worktree) or not proof_passes(worktree, packet_lane["proof"], timeout_seconds):
            result.update({"status": "needs_attention", "scope_ok": True, "proof_ok": False, "merge_ok": None})
            return result
        if not commit_lane(worktree, packet_lane["id"], packet_lane["allowed_paths"]):
            result.update({"status": "needs_attention", "scope_ok": True, "proof_ok": True, "merge_ok": None})
            return result
        result.update({"status": "passed", "scope_ok": True, "proof_ok": True, "merge_ok": None})
        return result
    except (DriveError, HOST.HostError, OSError, UnicodeError):
        result.update({"status": "needs_attention", "scope_ok": None, "proof_ok": None, "merge_ok": None})
        return result
    finally:
        result["duration_s"] = round(time.monotonic() - started, 3)


def launch(
    *,
    repo: Path,
    plan: Path,
    roster_path: Path,
    session_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run one explicit foreground session without pushing or merging anything."""

    session_path, session = read_session(repo, session_id)
    if session["state"] != "prepared":
        raise DriveError("this Drive session has already started or finished")
    source = read_plan(plan)
    if plan_sha256(source) != session["plan_sha256"]:
        raise DriveError("the plan changed after preparation; prepare ready work again")
    if launch_head(repo) != session["base_sha256"]:
        raise DriveError("the project changed after preparation; prepare ready work again")
    document = extract_document(source)
    if document is None:
        raise DriveError("this plan no longer has a Drive Packet")
    packet_lanes = {lane["id"]: lane for lane in document["lanes"]}
    if any(lane["id"] not in packet_lanes for lane in session["lanes"]):
        raise DriveError("the prepared work no longer exists in the plan")
    session["state"] = "running"
    replace_session(session_path, session)
    telemetry.record_drive(
        event="drive_started",
        session_id=session_id,
        lane_id=None,
        role=None,
        host=None,
        state="running",
        duration=0,
        lane_count=len(session["lanes"]),
        path_count=None,
        scope_ok=None,
        proof_ok=None,
        merge_ok=None,
    )
    finished: list[dict[str, Any]] = []
    for session_lane in session["lanes"]:
        packet_lane = packet_lanes[session_lane["id"]]
        session_lane["base_sha256"] = session["base_sha256"]
        outcome = lane_result(
            repo=repo,
            session_id=session_id,
            session_lane=session_lane,
            packet_lane=packet_lane,
            roster_path=roster_path,
            timeout_seconds=timeout_seconds,
        )
        outcome.pop("base_sha256", None)
        duration = outcome.pop("duration_s", 0)
        finished.append(outcome)
        session["lanes"] = finished + session["lanes"][len(finished) :]
        replace_session(session_path, session)
        telemetry.record_drive(
            event="drive_finished",
            session_id=session_id,
            lane_id=outcome["observation_id"],
            role=outcome["role"],
            host=outcome["host"],
            state="ok" if outcome["status"] == "passed" else "blocked",
            duration=duration,
            lane_count=len(session["lanes"]),
            path_count=len(packet_lane["allowed_paths"]),
            scope_ok=outcome["scope_ok"],
            proof_ok=outcome["proof_ok"],
            merge_ok=None,
        )
    session["lanes"] = finished
    session["state"] = "finished"
    replace_session(session_path, session)
    telemetry.record_drive(
        event="drive_finished",
        session_id=session_id,
        lane_id=None,
        role=None,
        host=None,
        state="finished",
        duration=None,
        lane_count=len(finished),
        path_count=None,
        scope_ok=None,
        proof_ok=None,
        merge_ok=None,
    )
    return session


def accept(
    *,
    repo: Path,
    plan: Path,
    session_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Reproduce finished work, then explicitly merge it only into this local repo."""

    session_path, session = read_session(repo, session_id)
    if session["state"] == ACCEPTED_SESSION_STATE:
        raise DriveError("this Drive session was already brought into the project")
    if session["state"] != "finished" or any(
        lane["status"] != "passed" or lane["scope_ok"] is not True or lane["proof_ok"] is not True
        for lane in session["lanes"]
    ):
        raise DriveError("only fully checked Drive work can be brought into the project")
    source = read_plan(plan)
    if plan_sha256(source) != session["plan_sha256"]:
        raise DriveError("the plan changed after preparation; prepare ready work again")
    if launch_head(repo) != session["base_sha256"]:
        raise DriveError("the project changed after preparation; prepare ready work again")
    document = extract_document(source)
    if document is None:
        raise DriveError("this plan no longer has a Drive Packet")
    packet_lanes = {lane["id"]: lane for lane in document["lanes"]}
    if any(lane["id"] not in packet_lanes for lane in session["lanes"]):
        raise DriveError("the checked work no longer exists in the plan")
    if not commit_identity_is_ready(repo):
        raise DriveError("this project needs a local Git commit identity before accepting work")

    candidates: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []
    allowed_paths: list[str] = []
    proofs: list[list[str]] = []
    for session_lane in session["lanes"]:
        packet_lane = packet_lanes[session_lane["id"]]
        route = route_for_lane(repo, session_id, session_lane)
        expected_hash = hashlib.sha256(packet_lane["task"].encode("utf-8")).hexdigest()
        if route["binding"]["task_id"] != packet_lane["id"] or route["binding"]["task_sha256"] != expected_hash:
            raise DriveError("the checked work no longer matches the plan")
        branch, commit = branch_commit(repo, session_id, packet_lane["id"])
        if not branch_contains_base(repo, session["base_sha256"], commit):
            raise DriveError("the kept review branch does not start from the prepared project")
        changed = changed_paths_between(repo, session["base_sha256"], commit)
        if not changed or not all(HOST.path_allowed(path, packet_lane["allowed_paths"]) for path in changed):
            raise DriveError("the kept review branch changed outside its declared files")
        if not commit_diff_is_clean(repo, session["base_sha256"], commit):
            raise DriveError("the kept review branch has a whitespace error")
        candidates.append((session_lane, packet_lane, branch, commit))
        allowed_paths.extend(packet_lane["allowed_paths"])
        proofs.append(packet_lane["proof"])

    attempt = new_review_attempt(repo, session_id)
    for _session_lane, packet_lane, _branch, commit in candidates:
        review = create_lead_review_worktree(repo, attempt, packet_lane["id"], commit)
        if not lead_review_passes(review, packet_lane["proof"], timeout_seconds):
            raise DriveError("the checked work did not reproduce in its lead review checkout")

    merge_review_branches(
        repo=repo,
        branches=[branch for _session_lane, _packet_lane, branch, _commit in candidates],
        allowed_paths=allowed_paths,
        proofs=proofs,
        timeout_seconds=timeout_seconds,
        session_id=session_id,
    )
    session["state"] = ACCEPTED_SESSION_STATE
    for lane in session["lanes"]:
        lane["merge_ok"] = True
    replace_session(session_path, session)
    telemetry.record_drive(
        event="drive_accepted",
        session_id=session_id,
        lane_id=None,
        role=None,
        host=None,
        state="ok",
        duration=None,
        lane_count=len(session["lanes"]),
        path_count=None,
        scope_ok=True,
        proof_ok=True,
        merge_ok=True,
    )
    return session


def render(session: dict[str, Any], lanes: list[dict[str, Any]], notices: list[dict[str, str]]) -> str:
    lines = ["Ready work", ""]
    for lane in lanes:
        lines.append(f"- {lane['summary']}")
        lines.append(f"  Good fit: {lane['selection']['role'].replace('-', ' ')} work")
        lines.append("  What we will check: the plan's named check")
    if notices:
        lines.extend(["", "Needs attention"])
        lines.extend(f"- {item['id'].replace('-', ' ')}" for item in notices)
    lines.extend(
        [
            "",
            "Nothing has started. This is a prepared local session only.",
            f"Session: {session['session_id']}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_launch(session: dict[str, Any]) -> str:
    passed = [lane for lane in session["lanes"] if lane["status"] == "passed"]
    attention = [lane for lane in session["lanes"] if lane["status"] != "passed"]
    lines = ["Work update", ""]
    if passed:
        lines.append(f"Finished and checked: {len(passed)}")
    if attention:
        lines.append(f"Needs attention: {len(attention)}")
    lines.extend(
        [
            "",
            "Each worktree and branch was kept for review.",
            "Nothing was pushed, merged, deployed, published, or sent outside this computer.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_accept(session: dict[str, Any]) -> str:
    return (
        "Work brought into this project\n\n"
        f"Finished and checked: {len(session['lanes'])}\n"
        "No remote branch, pull request, deployment, publication, or message was created.\n"
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pilot-puppy drive", description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare", help="prepare ready work without starting a coding host")
    prepare_parser.add_argument("--repo", required=True, type=Path, help="exact Git worktree root")
    prepare_parser.add_argument("--plan", default="PLAN.md", help="relative canonical PLAN.md path")
    prepare_parser.add_argument("--roster-file", type=Path, default=default_roster_path())
    prepare_parser.add_argument("--availability", choices=("probe", "assume"), default="probe")
    prepare_parser.add_argument("--json", action="store_true")
    launch_parser = sub.add_parser("launch", help="start one prepared foreground session")
    launch_parser.add_argument("--repo", required=True, type=Path, help="exact Git worktree root")
    launch_parser.add_argument("--plan", default="PLAN.md", help="relative canonical PLAN.md path")
    launch_parser.add_argument("--session", required=True, help="prepared local Drive session ID")
    launch_parser.add_argument("--roster-file", type=Path, default=default_roster_path())
    launch_parser.add_argument("--timeout-seconds", type=int, default=900)
    launch_parser.add_argument("--json", action="store_true")
    accept_parser = sub.add_parser("accept", help="reproduce and bring checked local work into this project")
    accept_parser.add_argument("--repo", required=True, type=Path, help="exact Git worktree root")
    accept_parser.add_argument("--plan", default="PLAN.md", help="relative canonical PLAN.md path")
    accept_parser.add_argument("--session", required=True, help="finished local Drive session ID")
    accept_parser.add_argument("--timeout-seconds", type=int, default=900)
    accept_parser.add_argument("--json", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repo = exact_git_root(args.repo)
        plan = plan_path(repo, args.plan)
        if args.command == "prepare":
            base_sha256 = clean_head(repo)
            session, lanes, notices = prepare(
                repo=repo,
                plan=plan,
                roster_path=args.roster_file,
                availability=args.availability,
                session_id=secrets.token_hex(16),
                base_sha256=base_sha256,
            )
            if args.json:
                print(json.dumps(session, indent=2, sort_keys=True))
            else:
                print(render(session, lanes, notices), end="")
            return 0
        if args.timeout_seconds < 1 or args.timeout_seconds > 3_600:
            raise DriveError("timeout must be between 1 and 3600 seconds")
        if args.command == "launch":
            session = launch(
                repo=repo,
                plan=plan,
                roster_path=args.roster_file,
                session_id=args.session,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            session = accept(
                repo=repo,
                plan=plan,
                session_id=args.session,
                timeout_seconds=args.timeout_seconds,
            )
    except (DriveError, DrivePacketError, OSError, UnicodeError) as exc:
        print(f"pilot-puppy drive: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(session, indent=2, sort_keys=True))
    else:
        print(render_launch(session) if args.command == "launch" else render_accept(session), end="")
    return 0 if all(lane["status"] == "passed" for lane in session["lanes"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
