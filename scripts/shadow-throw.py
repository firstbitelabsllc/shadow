#!/usr/bin/env python3
"""Claim one project-plan row on this computer, then print its goal pointer.

The root board owns claims and owners.  The project plan remains byte-for-byte
the authority for task text and proof; claiming never copies or rewrites it.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Final


ROOT: Final = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
_amp_spec = importlib.util.spec_from_file_location("shadow_amp", ROOT / "scripts" / "shadow-amp.py")
_amp = importlib.util.module_from_spec(_amp_spec)
sys.modules.setdefault("shadow_amp", _amp)
_amp_spec.loader.exec_module(_amp)

import shadow_root_board as _board  # noqa: E402
import shadow_telemetry as _telemetry  # noqa: E402


BY_MAX: Final = 40
BUSY_THRESHOLD: Final = 8


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def _row_line(text: str, task_id: str) -> tuple[str, re.Match[str]] | None:
    for line in text.splitlines():
        match = _amp.ROW_RE.match(line)
        if match and match.group("id") == task_id:
            return line, match
    return None


def _priority(plan: dict) -> int:
    raw = plan["brief"].get("Priority", "3")
    try:
        value = int(raw)
    except ValueError as exc:
        raise _board.BoardError("project Priority must be 1-5 before it can enter the root board") from exc
    if value not in range(1, 6):
        raise _board.BoardError("project Priority must be 1-5 before it can enter the root board")
    return value


def _repo_for(plan_path: Path) -> Path:
    top = git(plan_path.parent, "rev-parse", "--show-toplevel")
    return Path(top.stdout.strip()).resolve() if top.returncode == 0 else plan_path.parent


def _validated_target(plan_path: Path, task: str) -> tuple[Path, dict, dict[str, str]]:
    """Read one exact project authority and reject an unsafe/untakeable row."""
    repo = _repo_for(plan_path)
    relative = str(plan_path.relative_to(repo)) if plan_path.is_relative_to(repo) else plan_path.name
    if git(repo, "ls-files", "-u", "--", relative).stdout.strip():
        raise _board.BoardError("PLAN.md has unresolved merge conflicts; resolve them first")
    if git(repo, "status", "--porcelain", "--", relative).stdout.strip():
        raise _board.BoardError(
            "PLAN.md has uncommitted changes; commit them before pointing another seat at it"
        )
    try:
        token, content = _board.committed_plan_snapshot(plan_path)
        text = content.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise _board.BoardError("project plan is missing or unreadable") from exc
    plan = _amp._parse(text)
    located = _row_line(text, task)
    if located is None:
        raise _board.BoardError(f"no task carries {task} in the stored canonical project plan")
    _, match = located
    if match.group("state") not in {"pending", "in_progress"}:
        raise _board.BoardError(f"{task} is [{match.group('state')}], not claimable")
    done = _amp._completed_ids(plan["milestones"])
    fields = {
        field.group("key"): field.group("value").strip()
        for field in _amp.FIELD_RE.finditer(match.group("tail") or "")
    }
    unmet = [ref for ref in _amp.HASH_RE.findall(fields.get("needs", "")) if ref not in done]
    if unmet:
        raise _board.BoardError(f"{task} still needs {', '.join(unmet)}")
    if not fields.get("proof"):
        raise _board.BoardError(
            f"{task} has no proof, so nobody could tell whether it finished"
        )
    unclean = _amp.unclean_note(plan)
    if unclean:
        raise _board.BoardError(f"project plan cannot be claimed: {unclean}")
    where = _board.public_plan_locator(plan_path)
    suffix = f"/{token['relative']}"
    public_repo = where[: -len(suffix)] if where.endswith(suffix) else where
    plan["authority_pointer"] = (
        f"{token['relative']} @ {token['head']} in {public_repo}"
    )
    return repo, plan, token


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    parser = argparse.ArgumentParser(
        prog="shadow throw",
        description="Claim a project-plan row on this computer before work leaves the chat.",
    )
    parser.add_argument("--repo", default=None, help="repository root (default: cwd)")
    parser.add_argument("--entity", default=None, help="computer-board entity id")
    parser.add_argument("--task", required=True, help="the row to claim, e.g. ~ab12")
    parser.add_argument(
        "--by",
        required=True,
        help=f"which seat owns the claim (1-{BY_MAX} visible characters)",
    )
    parser.add_argument(
        "--adopt-expired",
        action="store_true",
        help="after probing proof, atomically replace an overdue owner claim",
    )
    args = parser.parse_args(argv)

    if args.entity and args.repo:
        print("shadow throw: use either --entity or --repo, not both", file=sys.stderr)
        return 2
    state = None
    if args.entity:
        if _board.ENTITY_ID.fullmatch(args.entity) is None:
            print("shadow throw: --entity wants a 64-character board id", file=sys.stderr)
            return 2
        try:
            resolved = _board.resolve_entity(args.entity)
        except _board.BoardError as exc:
            print(f"shadow throw: claim refused: {exc}", file=sys.stderr)
            return 1
        if resolved is None or resolved["plan"] is None:
            print("shadow throw: claim refused: entity is not registered on this computer", file=sys.stderr)
            return 1
        state = resolved["state"]
        plan_path = resolved["plan"]
        repo = _repo_for(plan_path)
    else:
        unresolved_repo = Path(args.repo or ".")
        unresolved_plan = unresolved_repo / "PLAN.md"
        if not _board.regular_plan(unresolved_plan):
            print(
                f"shadow throw: no regular, non-symlink plan at {unresolved_plan}",
                file=sys.stderr,
            )
            return 2
        repo = unresolved_repo.resolve()
        plan_path = repo / "PLAN.md"
        try:
            existing = _board.entity_state(plan_path)
            if existing is not None and existing["entity"] is not None:
                plan_path = _board.canonical_plan(plan_path, repair_missing=True)
                repo = _repo_for(plan_path)
                state = _board.entity_state(plan_path)
        except _board.BoardError as exc:
            print(f"shadow throw: claim refused: {exc}", file=sys.stderr)
            return 1
    if not _board.regular_plan(plan_path):
        print(f"shadow throw: no regular, non-symlink plan at {plan_path}", file=sys.stderr)
        return 2
    if not re.fullmatch(r"~[0-9a-z]{4}", args.task):
        print(f"shadow throw: --task wants a four-char id like ~ab12, got {args.task}", file=sys.stderr)
        return 2
    try:
        _board.validate_owner(args.by)
    except _board.BoardError as exc:
        print(f"shadow throw: --by is unsafe: {exc}", file=sys.stderr)
        return 2
    try:
        with _board.project_lock(plan_path):
            repo, plan, plan_token = _validated_target(plan_path, args.task)
            if not args.entity:
                # Normalize/register this exact bounded entity before claiming.
                # This also rekeys a stored entity after its Git origin changes, so
                # the id printed in the packet is immediately addressable.
                _board.reconcile(
                    [
                        {
                            "plan": str(plan_path),
                            "project": plan["brief"]["Project"],
                            "priority": _priority(plan),
                            "candidates": _amp._candidate_ids(plan),
                        }
                    ],
                    [],
                )
                state = _board.entity_state(plan_path)
            if state is None or state["entity"] is None:
                if args.entity:
                    raise _board.BoardError("entity is not registered on this computer")
                raise _board.BoardError("entity did not enter the bounded computer board")
            plan["board_revision"] = 9_999_999_999_999_999_999
            plan["root_priority"] = (
                state["project"]["priority"]
                if state is not None and state["project"] is not None
                else _priority(plan)
            )
            plan["entity_id"] = state["entity"]["id"]
            plan["seat_owner"] = args.by
            # Prove the final block fits before taking a claim. A concurrent board
            # write may advance this preview; the claimed block is rebuilt below
            # from the transaction's actual revision.
            block, _ = _amp.build_block(plan, repo, plan_path, args.task, _amp.DEFAULT_MAX_CHARS)
            receipt = _board.claim(
                plan_path,
                args.task,
                args.by,
                project=plan["brief"]["Project"],
                priority=_priority(plan),
                adopt_expired=args.adopt_expired,
                expected_plan=plan_token,
            )
            payload = receipt["payload"]
            claimed = receipt["claim"]
            entity = receipt["entity"]
            project = next(item for item in payload["projects"] if item["id"] == entity["project"])
            plan["board_revision"] = payload["revision"]
            plan["root_priority"] = project["priority"]
            plan["entity_id"] = entity["id"]
            plan["seat_owner"] = claimed["owner"]
            block, _ = _amp.build_block(plan, repo, plan_path, args.task, _amp.DEFAULT_MAX_CHARS)
    except _board.AlreadyClaimed as exc:
        print(
            f"shadow throw: {args.task} was claimed by {exc.owner}; take another reachable row",
            file=sys.stderr,
        )
        return 1
    except (_board.BoardError, LookupError, ValueError) as exc:
        print(f"shadow throw: claim refused: {exc}", file=sys.stderr)
        return 1

    if _telemetry.local_enabled():
        try:
            _telemetry.emit_local(
                repo,
                {
                    "recorded_at": datetime.now(timezone.utc)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                    "project": project["id"],
                    "entity": entity["id"],
                    "row": args.task,
                    "verb": "throw",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "outcome": "claimed",
                },
            )
        except _telemetry.TelemetryError:
            print(
                "[throw] the claim succeeded but its optional local event was not recorded",
                file=sys.stderr,
            )

    sys.stdout.write(block)
    count = len(payload["claims"])
    print(
        f"[throw] {args.task} claimed by {args.by} on this computer; {count} claim(s) visible to every local seat",
        file=sys.stderr,
    )
    if count >= BUSY_THRESHOLD:
        print(
            f"[throw] {count} claims are open; land or park work before taking more",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
