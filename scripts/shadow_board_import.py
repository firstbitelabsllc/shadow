#!/usr/bin/env python3
"""Bounded migration from project plans into this computer's pointer board."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shadow_root_board as board


THROWN = re.compile(
    r"^- (?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
    r"THROWN (?P<row>~[0-9a-z]{4})\b(?P<tail>.*)$",
    flags=re.M,
)
OWNER = re.compile(r"\| by: (?P<owner>[^|]+)")


def portfolio_root(fallback: Path) -> Path:
    configured = os.environ.get("SHADOW_PORTFOLIO_ROOT") or os.environ.get("SHADOW_DEV_ROOT")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_dir():
            raise board.BoardError("SHADOW_PORTFOLIO_ROOT is not a directory")
        return candidate
    default = Path.home() / "Development"
    return default.resolve() if default.is_dir() else fallback.resolve()


def _priority(plan: dict) -> int:
    raw = plan["brief"].get("Priority", "3")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise board.BoardError("project Priority must be 1-5 for board import") from exc
    if value not in range(1, 6):
        raise board.BoardError("project Priority must be 1-5 for board import")
    return value


def reconcile_portfolio(
    root: Path,
    amp: ModuleType,
    *,
    home: Path | None = None,
) -> dict:
    """Import exactly the plans returned by shipped bounded discovery."""
    from browser.server import BrowserError, discover_plans, is_live

    seeds: list[dict] = []
    historical: list[dict] = []
    retired: list[str] = []
    try:
        records = discover_plans(root, fail_on_skipped=True)
    except BrowserError as exc:
        raise board.BoardError(f"portfolio import refused: {exc}") from exc
    for record in records:
        relative = record.get("path")
        if not relative:
            continue
        plan_path = (root / relative).resolve()
        if not is_live(record):
            retired.append(board.entity_id(plan_path))
            continue
        try:
            text = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise board.BoardError(f"{relative} cannot be read during board import") from exc
        plan = amp._parse(text)
        # Legacy outcome plans remain visible during migration but do not have
        # project rows for the root board to point at. Status renders them from
        # the same bounded discovery result until they adopt the current Brief.
        if not plan["brief"].get("Project") or not plan["brief"].get("Mode"):
            continue
        unclean = amp.unclean_note(plan)
        if unclean:
            raise board.BoardError(f"{relative} cannot enter the computer board: {unclean}")
        try:
            priority = _priority(plan)
        except board.BoardError as exc:
            raise board.BoardError(f"{relative}: {exc}") from exc
        seeds.append(
            {
                "plan": str(plan_path),
                "project": plan["brief"]["Project"],
                "priority": priority,
                "candidates": amp._candidate_ids(plan),
            }
        )

        latest: dict[str, tuple[str, str]] = {}
        for match in THROWN.finditer(text):
            owner = OWNER.search(match.group("tail"))
            latest[match.group("row")] = (
                match.group("stamp"),
                owner.group("owner").strip() if owner else "another seat",
            )
        live = {
            row["id"]
            for milestone in plan["milestones"]
            for row in milestone["rows"]
            if row["state"] == "in_progress"
        }
        historical.extend(
            {
                "plan": str(plan_path),
                "row": row,
                "owner": owner,
                "claimed_at": stamp,
            }
            for row, (stamp, owner) in latest.items()
            if row in live
        )
    return board.reconcile(
        seeds,
        historical,
        retired_entities=retired,
        home=home,
    )


def suppression_receipts(root: Path) -> list[dict[str, str | None]]:
    """Bounded, public reasons discovery withheld a plan from authority."""
    from browser.server import BrowserError, discover_plans

    try:
        records = discover_plans(root, include_shadowed=True, fail_on_skipped=True)
    except BrowserError as exc:
        raise board.BoardError(f"portfolio inspection refused: {exc}") from exc
    receipts: list[dict[str, str | None]] = []
    for record in records:
        if record.get("shadowed_by"):
            receipts.append(
                {
                    "path": record["path"],
                    "shadowed_by": record["shadowed_by"],
                    "reason": record["shadow_reason"],
                }
            )
        elif record.get("archived"):
            receipts.append(
                {
                    "path": record["path"],
                    "shadowed_by": None,
                    "reason": (
                        "demoted by its own banner: "
                        f'"{record.get("archive_veto", "self-demotion")}"'
                    ),
                }
            )
    return receipts
