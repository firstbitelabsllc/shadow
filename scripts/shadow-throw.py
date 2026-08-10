#!/usr/bin/env python3
"""Claim one project-plan row on this computer, then print its goal pointer.

The root board owns claims and owners.  The project plan remains byte-for-byte
the authority for task text and proof; claiming never copies or rewrites it.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
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
from shadow_config import (  # noqa: E402
    ConfigError,
    LOCAL_CONFIG,
    assert_expected_board_root,
    load_config,
)


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


def _config_preferences(
    repo: Path,
    owner: str,
    board_root: Path | None = None,
) -> tuple[int, str | None, list[str]]:
    selected_root = board_root or _board.configured_root()
    assert_expected_board_root(repo, selected_root)
    config = load_config(repo)
    durability = config.get("durability", {})
    if not isinstance(durability, dict):
        raise ConfigError(repo / LOCAL_CONFIG, 1, "durability must be a mapping")
    minutes = durability.get("claim_return_minutes", _board.DEFAULT_CLAIM_RETURN_MINUTES)
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise ConfigError(repo / LOCAL_CONFIG, 1, "durability.claim_return_minutes must be an integer")
    leads = config.get("leads", {})
    if not isinstance(leads, dict):
        raise ConfigError(repo / LOCAL_CONFIG, 1, "leads must be a mapping")
    lead = leads.get(owner, {})
    if not isinstance(lead, dict):
        raise ConfigError(repo / LOCAL_CONFIG, 1, f"leads.{owner} must be a mapping")
    display = lead.get("display_name")
    if display is not None and not isinstance(display, str):
        raise ConfigError(repo / LOCAL_CONFIG, 1, f"leads.{owner}.display_name must be a string")
    method = config.get("method", {})
    if not isinstance(method, dict):
        raise ConfigError(repo / LOCAL_CONFIG, 1, "method must be a mapping")
    lenses = lead.get("default_lenses", method.get("adversarial_lenses", []))
    if not isinstance(lenses, list) or not all(isinstance(item, str) for item in lenses):
        raise ConfigError(repo / LOCAL_CONFIG, 1, f"leads.{owner}.default_lenses must be a string list")
    return minutes, display, lenses


def _validated_target(
    plan_path: Path, task: str
) -> tuple[Path, dict, dict[str, str], str]:
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
    try:
        canonical_task = _amp.resolve_row_selector(plan, task)
    except _amp.SelectorError as exc:
        if "duplicated in the plan" in str(exc):
            unclean = _amp.unclean_note(plan)
            if unclean:
                raise _board.BoardError(
                    f"project plan cannot be claimed: {unclean}"
                ) from exc
        raise _board.BoardError(str(exc)) from exc
    located = _row_line(text, canonical_task)
    if located is None:
        raise _board.BoardError(
            f"no task carries {canonical_task} in the stored canonical project plan"
        )
    _, match = located
    if match.group("state") not in {"pending", "in_progress"}:
        raise _board.BoardError(
            f"{canonical_task} is [{match.group('state')}], not claimable"
        )
    done = _amp._completed_ids(plan["milestones"])
    fields = {
        field.group("key"): field.group("value").strip()
        for field in _amp.FIELD_RE.finditer(match.group("tail") or "")
    }
    unmet = [ref for ref in _amp.HASH_RE.findall(fields.get("needs", "")) if ref not in done]
    if unmet:
        raise _board.BoardError(f"{canonical_task} still needs {', '.join(unmet)}")
    if not fields.get("proof"):
        raise _board.BoardError(
            f"{canonical_task} has no proof, so nobody could tell whether it finished"
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
    return repo, plan, token, canonical_task


def main(argv: list[str] | None = None) -> int:
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
    try:
        board_root = _board.configured_root()
    except _board.BoardError as exc:
        print(f"shadow throw: claim refused: {exc}", file=sys.stderr)
        return 1

    if args.entity and args.repo:
        print("shadow throw: use either --entity or --repo, not both", file=sys.stderr)
        return 2
    state = None
    if args.entity:
        if _board.ENTITY_ID.fullmatch(args.entity) is None:
            print("shadow throw: --entity wants a 64-character board id", file=sys.stderr)
            return 2
        try:
            resolved = _board.resolve_entity(args.entity, root=board_root)
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
            _board.assert_entity_board(repo, root=board_root)
            existing = _board.entity_state(plan_path, root=board_root)
            if existing is not None and existing["entity"] is not None:
                plan_path = _board.canonical_plan(
                    plan_path, repair_missing=True, root=board_root
                )
                repo = _repo_for(plan_path)
                state = _board.entity_state(plan_path, root=board_root)
        except _board.BoardError as exc:
            print(f"shadow throw: claim refused: {exc}", file=sys.stderr)
            return 1
    if not _board.regular_plan(plan_path):
        print(f"shadow throw: no regular, non-symlink plan at {plan_path}", file=sys.stderr)
        return 2
    if not _amp.valid_selector(args.task):
        print(
            "shadow throw: --task wants a four-char id like ~ab12 or an exact "
            f"leading legacy label like P9a~formats, got {args.task}",
            file=sys.stderr,
        )
        return 2
    try:
        _board.validate_owner(args.by)
    except _board.BoardError as exc:
        print(f"shadow throw: --by is unsafe: {exc}", file=sys.stderr)
        return 2
    try:
        with _board.project_lock(plan_path):
            repo, plan, plan_token, canonical_task = _validated_target(plan_path, args.task)
            _board.assert_entity_board(repo, root=board_root)
            claim_return_minutes, seat_display_name, seat_lenses = _config_preferences(
                repo, args.by, board_root
            )
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
                    root=board_root,
                )
                state = _board.entity_state(plan_path, root=board_root)
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
            plan["seat_display_name"] = seat_display_name
            plan["seat_lenses"] = seat_lenses
            # Prove the final block fits before taking a claim. A concurrent board
            # write may advance this preview; the claimed block is rebuilt below
            # from the transaction's actual revision.
            block, _ = _amp.build_block(
                plan, repo, plan_path, canonical_task, _amp.DEFAULT_MAX_CHARS
            )
            receipt = _board.claim(
                plan_path,
                canonical_task,
                args.by,
                project=plan["brief"]["Project"],
                priority=_priority(plan),
                adopt_expired=args.adopt_expired,
                expected_plan=plan_token,
                claim_return_minutes=claim_return_minutes,
                root=board_root,
            )
            payload = receipt["payload"]
            claimed = receipt["claim"]
            entity = receipt["entity"]
            project = next(item for item in payload["projects"] if item["id"] == entity["project"])
            plan["board_revision"] = payload["revision"]
            plan["root_priority"] = project["priority"]
            plan["entity_id"] = entity["id"]
            plan["seat_owner"] = claimed["owner"]
            plan["seat_display_name"] = seat_display_name
            plan["seat_lenses"] = seat_lenses
            block, _ = _amp.build_block(
                plan, repo, plan_path, canonical_task, _amp.DEFAULT_MAX_CHARS
            )
    except _board.AlreadyClaimed as exc:
        print(
            f"shadow throw: {args.task} was claimed by {exc.owner}; take another reachable row",
            file=sys.stderr,
        )
        return 1
    except (_board.BoardError, ConfigError, LookupError, ValueError) as exc:
        print(f"shadow throw: claim refused: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(block)
    count = len(payload["claims"])
    display_task = (
        args.task if args.task == canonical_task else f"{args.task} -> {canonical_task}"
    )
    print(
        f"[throw] {display_task} claimed by {args.by} on this computer; "
        f"{count} claim(s) visible to every local seat",
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
