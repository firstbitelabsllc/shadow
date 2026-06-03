#!/usr/bin/env python3
"""Build a read-only approval packet for the Snowcubes readiness lane.

The packet narrows the remaining local-CI gate without crossing it. It checks
the recommended tracker candidate, the canonical tracker path, and the clean
Snowcubes source ref, then emits the exact restore/execute commands that still
require explicit operator approval.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SCRIPT_NAME = "vidux-snowcubes-readiness-approval-packet.py"
DEFAULT_GOAL_AUDIT_JSON = Path(
    "projects/firstbite-local-ci-mega/evidence/2026-06-01-local-operator-goal-audit.json"
)
DEFAULT_MCP_DIR = Path("/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci")
SNOWCUBES_READINESS_LANE = "moussey_snowcubes_readiness"
REQUIRED_TRACKER_FILES = [
    "snowcubes-consignment-partners.csv",
    "snowcubes-consignment-live-ledger.csv",
]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    try:
        line_count = path.read_bytes().count(b"\n")
    except OSError:
        line_count = None
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "line_count": line_count,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _run_git(path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "head": None,
            "clean": False,
            "status_short": None,
            "error": "worktree missing",
        }
    head = _run_git(path, ["rev-parse", "HEAD"])
    status = _run_git(path, ["status", "--porcelain"])
    branch = _run_git(path, ["status", "--short", "--branch"])
    return {
        "path": str(path),
        "exists": True,
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "clean": status.returncode == 0 and status.stdout.strip() == "",
        "status_short": status.stdout.strip(),
        "status_short_branch": branch.stdout.strip().splitlines()[0]
        if branch.returncode == 0 and branch.stdout.strip()
        else None,
        "error": None if head.returncode == 0 and status.returncode == 0 else (head.stderr or status.stderr).strip(),
    }


def _dig(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _approval_commands(
    *,
    candidate_path: Path,
    canonical_path: Path,
    source_ref: str,
    run_id_prefix: str,
    mcp_dir: Path,
) -> dict[str, Any]:
    mkdir_command = ["mkdir", "-p", str(canonical_path)]
    copy_commands = [
        ["cp", "-p", str(candidate_path / filename), str(canonical_path / filename)]
        for filename in REQUIRED_TRACKER_FILES
    ]
    execute_json = {
        "mode": "execute",
        "lanes": [SNOWCUBES_READINESS_LANE],
        "source_ref": source_ref,
        "worktree": True,
        "keep_worktree": True,
        "run_id": "$run_id",
    }
    execute_json_text = json.dumps(execute_json, separators=(",", ":")).replace('"', '\\"')
    execute_command = (
        f"cd {shlex.quote(str(mcp_dir))} && "
        f"run_id={shlex.quote(run_id_prefix)}-$(date +%Y%m%d-%H%M%S) && "
        "npm run --silent call -- run_lanes "
        f"\"{execute_json_text}\""
    )
    return {
        "restore_commands": [_shell_join(mkdir_command), *[_shell_join(command) for command in copy_commands]],
        "execute_command": execute_command,
        "approval_required": True,
        "execute_approval_required": True,
    }


def build_packet(
    *,
    goal_audit_path: Path,
    mcp_dir: Path = DEFAULT_MCP_DIR,
    run_id_prefix: str = "moussey-snowcubes-readiness",
) -> dict[str, Any]:
    goal = _read_json(goal_audit_path)
    source_notes = _dig(goal, ["local_ci_launch_trust", "current_source_notes"])
    if not isinstance(source_notes, dict):
        raise ValueError("goal audit is missing local_ci_launch_trust.current_source_notes")
    tracker = source_notes.get("tracker_diagnosis") if isinstance(source_notes.get("tracker_diagnosis"), dict) else {}
    recommendation = (
        tracker.get("recommended_candidate") if isinstance(tracker.get("recommended_candidate"), dict) else {}
    )
    clean_source = (
        source_notes.get("clean_source_candidate")
        if isinstance(source_notes.get("clean_source_candidate"), dict)
        else {}
    )

    candidate_path_value = recommendation.get("path")
    canonical_path_value = tracker.get("canonical_tracker")
    source_ref_value = clean_source.get("source_ref")
    worktree_value = clean_source.get("worktree")
    if not candidate_path_value:
        raise ValueError("goal audit has no tracker_diagnosis.recommended_candidate.path")
    if not canonical_path_value:
        raise ValueError("goal audit has no tracker_diagnosis.canonical_tracker")
    if not source_ref_value:
        raise ValueError("goal audit has no clean_source_candidate.source_ref")
    if not worktree_value:
        raise ValueError("goal audit has no clean_source_candidate.worktree")

    candidate_path = Path(str(candidate_path_value)).expanduser()
    canonical_path = Path(str(canonical_path_value)).expanduser()
    source_ref = str(source_ref_value)
    source_worktree = Path(str(worktree_value)).expanduser()

    candidate_files = {
        filename: _file_metadata(candidate_path / filename) for filename in REQUIRED_TRACKER_FILES
    }
    canonical_files = {
        filename: _file_metadata(canonical_path / filename) for filename in REQUIRED_TRACKER_FILES
    }
    candidate_ready = candidate_path.exists() and all(item["exists"] for item in candidate_files.values())
    canonical_complete = canonical_path.exists() and all(item["exists"] for item in canonical_files.values())
    source_git = _git_state(source_worktree)
    source_ref_ready = (
        source_git["exists"]
        and source_git["clean"]
        and source_git["head"] == source_ref
    )
    status = "ready_for_approval" if candidate_ready and source_ref_ready else "not_ready"

    commands = _approval_commands(
        candidate_path=candidate_path,
        canonical_path=canonical_path,
        source_ref=source_ref,
        run_id_prefix=run_id_prefix,
        mcp_dir=mcp_dir,
    )
    next_action = (
        "With explicit operator approval, run the listed restore commands, then run the listed local-CI execute command."
        if status == "ready_for_approval"
        else "Inspect blocked checks before approving restore or local-CI execute."
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "snowcubes_readiness_approval_packet",
        "source": SCRIPT_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": (
            "Candidate tracker data and clean Snowcubes source ref are ready for an explicit operator-approved restore plus local-CI execute."
            if status == "ready_for_approval"
            else "Snowcubes readiness approval packet is not ready; inspect checks before approving restore or execute."
        ),
        "readonly": True,
        "local_ci_lanes_executed": False,
        "tracker_files_copied": False,
        "canonical_tracker_created": False,
        "approval_gate_status": "operator_gated",
        "restore_requires_explicit_approval": True,
        "execute_requires_explicit_approval": True,
        "approval_required": True,
        "next_action": next_action,
        "required_files": REQUIRED_TRACKER_FILES,
        "goal_audit_path": str(goal_audit_path),
        "candidate": {
            "path": str(candidate_path),
            "files": candidate_files,
            "ready": candidate_ready,
            "private_fields_redacted": True,
        },
        "canonical_tracker": {
            "path": str(canonical_path),
            "exists": canonical_path.exists(),
            "complete": canonical_complete,
            "files": canonical_files,
        },
        "source_ref": {
            "ref": source_ref,
            "worktree": str(source_worktree),
            "git": source_git,
            "ready": source_ref_ready,
        },
        "lane": {
            "id": SNOWCUBES_READINESS_LANE,
            "mcp_dir": str(mcp_dir),
            "execute_requires_explicit_approval": True,
            "restore_requires_explicit_approval": True,
            "commands": commands,
        },
        "checks": [
            {
                "id": "candidate_tracker",
                "status": "ready" if candidate_ready else "blocked",
                "summary": "Recommended tracker candidate contains both required CSV filenames."
                if candidate_ready
                else "Recommended tracker candidate is missing one or more required CSV filenames.",
            },
            {
                "id": "canonical_tracker",
                "status": "ready" if not canonical_complete else "warning",
                "summary": "Canonical tracker path is absent/incomplete; restore/provide would create the required inputs."
                if not canonical_complete
                else "Canonical tracker path already contains required files; inspect before overwriting.",
            },
            {
                "id": "source_ref",
                "status": "ready" if source_ref_ready else "blocked",
                "summary": f"Clean source worktree is at {source_ref}."
                if source_ref_ready
                else "Clean source worktree is missing, dirty, or not at the expected source ref.",
            },
            {
                "id": "approval_gate",
                "status": "operator_gated",
                "summary": "Restore/provide and run_lanes execute are not performed by this packet.",
            },
        ],
        "non_claims": [
            "This packet did not print CSV contents.",
            "This packet did not copy, restore, edit, or delete tracker CSVs.",
            "This packet did not create the canonical tracker directory.",
            "This packet did not execute local-CI lanes.",
            "This packet did not mutate Moussey, Snowcubes, Vidux, /ai, or /ai-leo source.",
            "This packet does not prove Candidate B is product-authoritative.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Snowcubes Readiness Approval Packet",
        "",
        f"- `generated_at`: `{payload['generated_at']}`",
        f"- `status`: `{payload['status']}`",
        f"- `summary`: {payload['summary']}",
        f"- `readonly`: `{payload['readonly']}`",
        f"- `local_ci_lanes_executed`: `{payload['local_ci_lanes_executed']}`",
        f"- `tracker_files_copied`: `{payload['tracker_files_copied']}`",
        f"- `approval_gate_status`: `{payload['approval_gate_status']}`",
        f"- `restore_requires_explicit_approval`: `{payload['restore_requires_explicit_approval']}`",
        f"- `execute_requires_explicit_approval`: `{payload['execute_requires_explicit_approval']}`",
        f"- `next_action`: {payload['next_action']}",
        f"- `required_files`: `{', '.join(payload['required_files'])}`",
        "",
        "## Candidate",
        "",
        f"- `path`: `{payload['candidate']['path']}`",
        f"- `ready`: `{payload['candidate']['ready']}`",
        f"- `private_fields_redacted`: `{payload['candidate']['private_fields_redacted']}`",
    ]
    for filename, metadata in payload["candidate"]["files"].items():
        lines.append(
            f"- `{filename}` exists=`{metadata.get('exists')}` size=`{metadata.get('size_bytes')}` "
            f"lines=`{metadata.get('line_count')}` mtime=`{metadata.get('mtime')}`"
        )
    canonical = payload["canonical_tracker"]
    lines.extend(
        [
            "",
            "## Canonical Tracker",
            "",
            f"- `path`: `{canonical['path']}`",
            f"- `exists`: `{canonical['exists']}`",
            f"- `complete`: `{canonical['complete']}`",
            "",
            "## Source Ref",
            "",
            f"- `source_ref`: `{payload['source_ref']['ref']}`",
            f"- `worktree`: `{payload['source_ref']['worktree']}`",
            f"- `ready`: `{payload['source_ref']['ready']}`",
            f"- `git_head`: `{payload['source_ref']['git']['head']}`",
            f"- `git_clean`: `{payload['source_ref']['git']['clean']}`",
            "",
            "## Approval-Required Commands",
            "",
        ]
    )
    commands = payload["lane"]["commands"]
    for command in commands["restore_commands"]:
        lines.append(f"- `{command}`")
    lines.append(f"- `{commands['execute_command']}`")
    lines.extend(["", "## Checks", ""])
    for check in payload["checks"]:
        lines.append(f"- `{check['id']}`: `{check['status']}` - {check['summary']}")
    lines.extend(["", "## Non-Claims", ""])
    for item in payload["non_claims"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal-audit-json", type=Path, default=DEFAULT_GOAL_AUDIT_JSON)
    parser.add_argument("--mcp-dir", type=Path, default=DEFAULT_MCP_DIR)
    parser.add_argument("--run-id-prefix", default="moussey-snowcubes-readiness")
    parser.add_argument("--write-json", type=Path)
    parser.add_argument("--write-markdown", type=Path)
    args = parser.parse_args()

    payload = build_packet(
        goal_audit_path=args.goal_audit_json,
        mcp_dir=args.mcp_dir,
        run_id_prefix=args.run_id_prefix,
    )
    if args.write_json:
        _write_json(args.write_json, payload)
    if args.write_markdown:
        args.write_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.write_markdown.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
