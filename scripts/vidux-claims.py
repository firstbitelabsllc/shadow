#!/usr/bin/env python3
"""Append-only claims bus for vidux automation lanes."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Callable


UTC = dt.timezone.utc
DEFAULT_TTL_HOURS = 2.0


def _now() -> dt.datetime:
    return dt.datetime.now(UTC).replace(microsecond=0)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _default_claims_file() -> Path:
    override = os.environ.get("VIDUX_CLAIMS_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".agent-ledger" / "claims.jsonl"


def _default_owner() -> str:
    for key in ("CLAUDE_AUTOMATION_NAME", "CODEX_AGENT_ID", "USER"):
        value = os.environ.get(key)
        if value:
            return value
    return f"pid-{os.getpid()}"


def _load_rows(handle: Any) -> list[dict[str, Any]]:
    handle.seek(0)
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(handle, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in claims file at line {line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"claims file line {line_no} is not an object")
        rows.append(row)
    return rows


def _with_claims_file(
    path: Path,
    lock_kind: int,
    callback: Callable[[list[dict[str, Any]], Any], tuple[int, dict[str, Any] | None]],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), lock_kind)
        rows = _load_rows(handle)
        rc, append_row = callback(rows, handle)
        if append_row is not None:
            handle.seek(0, os.SEEK_END)
            handle.write(json.dumps(append_row, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return rc


def _released_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("claim_id"))
        for row in rows
        if row.get("event") == "release" and row.get("claim_id")
    }


def _active_claims(rows: list[dict[str, Any]], *, now: dt.datetime) -> list[dict[str, Any]]:
    released = _released_ids(rows)
    active: list[dict[str, Any]] = []
    for row in rows:
        if row.get("event") != "claim":
            continue
        claim_id = str(row.get("claim_id", ""))
        if not claim_id or claim_id in released:
            continue
        try:
            expires_at = _parse_iso(str(row["expires_at"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"claim row {claim_id or '<missing>'} has invalid expires_at") from exc
        if expires_at > now:
            active.append(row)
    return active


def _claim_id(*, repo: str, claim: str, owner: str, at: dt.datetime) -> str:
    seed = f"{repo}\0{claim}\0{owner}\0{_iso(at)}\0{os.getpid()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"clm_{digest}"


def _print(payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _claim(args: argparse.Namespace) -> int:
    now = _now()
    claims_file = Path(args.claims_file).expanduser()
    repo = args.repo.strip()
    claim = args.claim.strip()
    owner = args.owner.strip()
    lane = args.lane.strip()
    plan_path = args.plan_path.strip()
    task_id = args.task_id.strip()
    expires_at = now + dt.timedelta(hours=args.ttl_hours)

    def locked(rows: list[dict[str, Any]], _handle: Any) -> tuple[int, dict[str, Any] | None]:
        active = _active_claims(rows, now=now)
        conflicts = [
            row
            for row in active
            if row.get("repo") == repo
            and row.get("claim") == claim
            and row.get("owner") != owner
        ]
        if conflicts:
            _print({"ok": False, "status": "conflict", "active": conflicts[0]})
            return 3, None

        existing = [
            row
            for row in active
            if row.get("repo") == repo
            and row.get("claim") == claim
            and row.get("owner") == owner
        ]
        if existing:
            _print({"ok": True, "status": "already_claimed", "claim": existing[0]})
            return 0, None

        row = {
            "event": "claim",
            "claim_id": _claim_id(repo=repo, claim=claim, owner=owner, at=now),
            "ts": _iso(now),
            "repo": repo,
            "claim": claim,
            "files_claimed": [claim],
            "owner": owner,
            "lane": lane,
            "plan_path": plan_path,
            "task_id": task_id,
            "ttl_hours": args.ttl_hours,
            "expires_at": _iso(expires_at),
            "host": socket.gethostname(),
            "pid": os.getpid(),
        }
        _print({"ok": True, "status": "claimed", "claim": row})
        return 0, row

    return _with_claims_file(claims_file, fcntl.LOCK_EX, locked)


def _release(args: argparse.Namespace) -> int:
    now = _now()
    claims_file = Path(args.claims_file).expanduser()
    claim_id = (args.claim_id or "").strip()
    repo = (args.repo or "").strip()
    claim = (args.claim or "").strip()
    owner = args.owner.strip()
    status = (args.status or "").strip()

    def locked(rows: list[dict[str, Any]], _handle: Any) -> tuple[int, dict[str, Any] | None]:
        active = _active_claims(rows, now=now)
        matches = [
            row
            for row in active
            if (claim_id and row.get("claim_id") == claim_id)
            or (
                not claim_id
                and row.get("repo") == repo
                and row.get("claim") == claim
                and row.get("owner") == owner
            )
        ]
        if not matches:
            _print({"ok": True, "status": "no_active_claim"})
            return 0, None

        claimed = matches[0]
        row = {
            "event": "release",
            "claim_id": claimed["claim_id"],
            "ts": _iso(now),
            "repo": claimed.get("repo", repo),
            "claim": claimed.get("claim", claim),
            "files_claimed": claimed.get("files_claimed", []),
            "owner": owner,
            "lane": claimed.get("lane", ""),
            "plan_path": claimed.get("plan_path", ""),
            "task_id": claimed.get("task_id", ""),
            "host": socket.gethostname(),
            "pid": os.getpid(),
        }
        if status:
            row["status"] = status
        _print({"ok": True, "status": "released", "release": row})
        return 0, row

    if not claim_id and not (repo and claim):
        raise ValueError("release requires --claim-id or both --repo and --claim")
    return _with_claims_file(claims_file, fcntl.LOCK_EX, locked)


def _active(args: argparse.Namespace) -> int:
    now = _now()
    claims_file = Path(args.claims_file).expanduser()
    repo = (args.repo or "").strip()
    claim = (args.claim or "").strip()

    def locked(rows: list[dict[str, Any]], _handle: Any) -> tuple[int, dict[str, Any] | None]:
        active = _active_claims(rows, now=now)
        if repo:
            active = [row for row in active if row.get("repo") == repo]
        if claim:
            active = [row for row in active if row.get("claim") == claim]
        _print({"ok": True, "claims": active})
        return 0, None

    return _with_claims_file(claims_file, fcntl.LOCK_SH, locked)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append-only vidux claims bus.")
    parser.add_argument(
        "--claims-file",
        default=str(_default_claims_file()),
        help="Claims JSONL path. Defaults to VIDUX_CLAIMS_FILE or ~/.agent-ledger/claims.jsonl.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim", help="Claim a repo surface if no active conflicting claim exists.")
    claim.add_argument("--repo", required=True)
    claim.add_argument("--claim", required=True, help="Claim key, usually a file path or plan row.")
    claim.add_argument("--owner", default=_default_owner())
    claim.add_argument("--lane", required=True)
    claim.add_argument("--plan-path", required=True)
    claim.add_argument("--task-id", required=True)
    claim.add_argument("--ttl-hours", type=_positive_float, default=DEFAULT_TTL_HOURS)
    claim.set_defaults(func=_claim)

    release = sub.add_parser("release", help="Release an active claim by id or repo+claim.")
    release.add_argument("--claim-id")
    release.add_argument("--repo")
    release.add_argument("--claim")
    release.add_argument("--owner", default=_default_owner())
    release.add_argument("--status", default="", help="Optional release status, e.g. done or blocked.")
    release.set_defaults(func=_release)

    active = sub.add_parser("active", help="List active, unexpired, unreleased claims.")
    active.add_argument("--repo")
    active.add_argument("--claim")
    active.set_defaults(func=_active)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        return int(args.func(args))
    except ValueError as exc:
        sys.stderr.write(f"vidux-claims: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
