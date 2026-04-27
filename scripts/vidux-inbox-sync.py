#!/usr/bin/env python3
"""vidux-inbox-sync.py — Round-trip sync between PLAN.md and external kanban boards.

Reads `vidux.config.json` (from CWD or `$VIDUX_CONFIG`), loads every enabled
adapter from the `adapters/` package, and reconciles PLAN.md tasks with items
on each external board.

Direction:
  --direction=pull    external → PLAN.md (INBOX promotion) + status reconcile
  --direction=push    PLAN.md  → external (create missing, sync status/fields)
  --direction=both    both (default)

Policy:
  * PLAN.md is the source of truth for [pending] / [in_progress] / [in_review]
    / [blocked] tasks. By default, novel external items land in INBOX.md as
    `- [live-feedback] <title> [Source: gh_projects:<id>]` entries for humans
    to promote. When an adapter explicitly sets `auto_promote_target`, novel
    external items are routed directly into that target PLAN.md as `BD-*`
    tasks instead.
  * When an external card moves to the `completed` column, the sync flips the
    corresponding PLAN.md task to `[completed]`. (Only that direction is auto —
    PLAN.md → external status is pushed explicitly every run.)
  * Mapping between vidux task ids and external_ids lives in a per-plan
    sidecar `<plan_dir>/.external-state.json` (gitignored since the whole
    projects/ tree is gitignored). Never touched by humans.

Usage:
  vidux-inbox-sync.py
  vidux-inbox-sync.py --dry-run
  vidux-inbox-sync.py --direction=pull
  vidux-inbox-sync.py --config /path/to/vidux.config.json
  vidux-inbox-sync.py --plan   /path/to/plan-dir

Exits 0 on success, 2 on configuration error, 3 on adapter error.

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- Path bootstrap: scripts/ lives alongside adapters/ -----------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adapters import (  # noqa: E402
    AdapterBase,
    ExternalItem,
    PlanTask,
    VidxStatus,
    get_adapter,
)


STATE_FILENAME = ".external-state.json"
INBOX_FILENAME = "INBOX.md"
PLAN_FILENAME = "PLAN.md"
INBOX_TAG = "live-feedback"
DEFAULT_AUTO_PROMOTE_MAX_NEW = 25


# --- Config loading ----------------------------------------------------------


def find_config(explicit: str | None) -> Path:
    """Resolve vidux.config.json path.

    Precedence: --config > $VIDUX_CONFIG > cwd/vidux.config.json >
    ~/Development/vidux/vidux.config.json.
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env = os.environ.get("VIDUX_CONFIG")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "vidux.config.json")
    candidates.append(Path("~/Development/vidux/vidux.config.json").expanduser())
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"vidux.config.json not found. Tried: {', '.join(str(c) for c in candidates)}"
    )


def load_config(path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    # Stash the config file's parent dir so resolve_plan_dirs can resolve
    # relative plan_store.path against the repo root.
    cfg["_config_dir"] = str(path.resolve().parent)
    return cfg


# --- Plan dir discovery ------------------------------------------------------


def resolve_plan_dirs(config: dict[str, Any], explicit: str | None) -> list[Path]:
    """Resolve one or more plan directories to sync.

    If --plan is given, use just that. Otherwise walk plan_store.path for
    every subdir that contains a PLAN.md.
    """
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not (p / PLAN_FILENAME).exists():
            raise FileNotFoundError(f"{p} has no {PLAN_FILENAME}")
        return [p]

    plan_store = config.get("plan_store", {})
    root_raw = plan_store.get("path")
    if not root_raw:
        raise ValueError("plan_store.path missing in vidux.config.json")
    root = Path(os.path.expanduser(root_raw))
    if not root.is_absolute():
        # Relative paths resolve against the config file's parent (repo root).
        config_dir = config.get("_config_dir")
        if config_dir:
            root = (Path(config_dir) / root).resolve()
    if not root.exists():
        return []
    # Recursive walk: any directory containing a PLAN.md is a plan dir, even
    # when nested under an outer plan dir (e.g. creative-engine/squad-integration).
    # Skip common noise dirs + dot dirs.
    skip_dirs = {"node_modules", ".next", "dist", "build", ".git", "evidence",
                 "investigations", "explorations", "spec"}
    out: list[Path] = []
    for plan_path in sorted(root.rglob(PLAN_FILENAME)):
        if any(part in skip_dirs or part.startswith(".") for part in plan_path.parent.relative_to(root).parts):
            continue
        out.append(plan_path.parent)
    return out


# --- PLAN.md parsing ---------------------------------------------------------

# Match task lines. Supports:
#   "- [pending] T7: description ..."              (vidux-kanban-ext style)
#   "- [pending] **GP-M6**: description ..."       (bolded task id)
#   "- [pending] I5: description ..."              (single-letter prefix)
# ID must start with an uppercase letter and may contain alphanumerics, `-`, `_`, `.`
# Optional `**...**` bold wrapping is tolerated and stripped by post-match cleanup.
_TASK_LINE = re.compile(
    r"^- \[(?P<status>pending|in_progress|in_review|completed|blocked)\] "
    r"(?:\*\*)?(?P<id>[A-Z][A-Za-z0-9_.+\-]*(?:\s+\d+(?:\.\d+)?)?)(?:\*\*)?"
    r"(?P<extras>(?:\s*(?:\([^)]*\)|\[[^\]]+\]))*)"
    r"\s*:\s*"
    r"(?P<body>.*)$"
)

_EVIDENCE_TAG = re.compile(r"\[Evidence:\s*(?P<v>[^\]]*)\]")
_INVESTIGATION_TAG = re.compile(r"\[Investigation:\s*(?P<v>[^\]]*)\]")
_ETA_TAG = re.compile(r"\[ETA:\s*(?P<v>[^\]]+)\]")
_ETA_HOURS = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*h", re.IGNORECASE)
_SOURCE_TAG = re.compile(r"\[Source:\s*(?P<v>[^\]]*)\]")


def parse_plan(plan_path: Path) -> list[PlanTask]:
    """Extract tasks from the `## Tasks` section of a PLAN.md."""
    text = plan_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Terminate the Tasks section only on canonical vidux sibling headers.
    # Non-canonical `## ` dividers (e.g., "## HUGE ESTIMATION" as a prose
    # break) are treated as part of the Tasks block — they commonly precede
    # additional task rows in long-running plans.
    _TERMINATOR_HEADERS = (
        "## Decision Log",
        "## Progress",
        "## Open Questions",
        "## ARCHIVE",
        "## Archive",
    )
    task_start = task_end = None
    for i, line in enumerate(lines):
        if re.match(r"^## Tasks\s*$", line):
            task_start = i + 1
            continue
        if task_start is not None:
            stripped = line.rstrip()
            if any(stripped == h or stripped.startswith(h + " ") for h in _TERMINATOR_HEADERS):
                task_end = i
                break
    if task_start is None:
        return []
    if task_end is None:
        task_end = len(lines)

    tasks: list[PlanTask] = []
    for line in lines[task_start:task_end]:
        m = _TASK_LINE.match(line)
        if not m:
            continue
        status = VidxStatus(m.group("status"))
        raw_id = m.group("id")
        body = m.group("body").strip()
        metadata_text = f"{m.group('extras') or ''} {body}"

        title = _strip_tags(body)

        evidence = _first(_EVIDENCE_TAG, metadata_text)
        investigation = _first(_INVESTIGATION_TAG, metadata_text)
        source = _first(_SOURCE_TAG, metadata_text)
        eta_hours = _parse_eta(metadata_text)

        tasks.append(
            PlanTask(
                id=raw_id,
                title=title,
                status=status,
                evidence=evidence,
                investigation=investigation,
                eta_hours=eta_hours,
                source=source,
            )
        )
    return tasks


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    val = m.group("v").strip()
    return val or None


def _parse_eta(body: str) -> float | None:
    tag = _first(_ETA_TAG, body)
    if not tag:
        return None
    m = _ETA_HOURS.search(tag)
    if not m:
        return None
    try:
        return float(m.group("n"))
    except ValueError:
        return None


def _strip_tags(body: str) -> str:
    """Drop bracketed meta tags to recover the bare task title."""
    # Remove bracketed tags (Evidence, ETA, Source, Shipped, Investigation, Fix, ...).
    cleaned = re.sub(r"\s*\[[^\]]+\]", "", body).strip()
    return cleaned


# --- External state sidecar --------------------------------------------------


def load_state(plan_dir: Path) -> dict[str, Any]:
    path = plan_dir / STATE_FILENAME
    if not path.exists():
        return {"adapters": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"adapters": {}}


def save_state(plan_dir: Path, state: dict[str, Any]) -> None:
    path = plan_dir / STATE_FILENAME
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def adapter_state(state: dict[str, Any], adapter_name: str) -> dict[str, str]:
    """Return the task-id → external_id map for one adapter, creating it lazily."""
    adapters = state.setdefault("adapters", {})
    entry = adapters.setdefault(adapter_name, {"task_to_external": {}})
    entry.setdefault("task_to_external", {})
    return entry["task_to_external"]


def source_external_id(task: PlanTask, adapter_name: str) -> str | None:
    """Return the adapter external id encoded in a task's Source marker."""
    if not task.source:
        return None
    prefix = f"{adapter_name}:"
    source = task.source.strip()
    if not source.startswith(prefix):
        return None
    external_id = source[len(prefix):].strip()
    return external_id or None


def source_marker_mappings(
    tasks: list[PlanTask],
    adapter_name: str,
) -> dict[str, str]:
    """Recover task-id → external_id mappings from `[Source: adapter:id]` tags."""
    mappings: dict[str, str] = {}
    for task in tasks:
        external_id = source_external_id(task, adapter_name)
        if external_id:
            mappings[task.id] = external_id
    return mappings


# --- INBOX.md append ---------------------------------------------------------


def append_inbox(plan_dir: Path, items: list[ExternalItem], adapter_name: str,
                 dry_run: bool) -> int:
    """Append novel external items to INBOX.md. Return count written."""
    if not items:
        return 0
    inbox = plan_dir / INBOX_FILENAME
    existing = inbox.read_text(encoding="utf-8") if inbox.exists() else ""

    new_lines: list[str] = []
    for item in items:
        marker = f"[Source: {adapter_name}:{item.external_id}]"
        if marker in existing:
            continue
        line = f"- [{INBOX_TAG}] {item.title} {marker}"
        new_lines.append(line)

    if not new_lines:
        return 0

    if not dry_run:
        header = "" if existing.endswith("\n") or not existing else "\n"
        addition = header + "\n".join(new_lines) + "\n"
        with inbox.open("a", encoding="utf-8") as fh:
            if not existing:
                fh.write("# Inbox\n\n")
            fh.write(addition)
    return len(new_lines)


# --- PLAN.md auto-promotion (board card → [pending] task) -------------------


_BD_TASK_ID = re.compile(
    r"^- \[(?:pending|in_progress|in_review|completed|blocked)\] (?:\*\*)?(BD-\d+)(?:\*\*)?",
    re.MULTILINE,
)


def _next_bd_seq(plan_text: str) -> int:
    """Highest existing BD-N in the plan + 1. Used to mint stable, unique
    task IDs for board-dropped cards. BD = Board-Dropped (per-plan namespace)."""
    seen = [
        int(m.group(1).split("-", 1)[1])
        for m in _BD_TASK_ID.finditer(plan_text)
    ]
    return (max(seen) + 1) if seen else 1


def _matchable_title(title: str) -> str:
    """Normalize task/card titles for conservative duplicate recovery."""
    stripped = _strip_tags(title)
    lowered = stripped.lower()
    lowered = lowered.replace("—", "-").replace("–", "-")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip(" *`\"'")


def recover_title_mappings(
    plan_dirs: list[Path],
    items: list[ExternalItem],
    adapter_name: str,
    dry_run: bool,
) -> set[str]:
    """Recover missing sidecar mappings for exact title matches.

    Sidecars are intentionally gitignored. In a fresh worktree, an
    auto-promote target can otherwise re-add existing Linear cards as new
    `BD-*` rows because there is no `.external-state.json` memory yet.

    This fallback only maps unique exact normalized titles. Ambiguous titles
    remain novel so the operator can see them instead of silently binding the
    wrong task.
    """
    if not items:
        return set()

    item_by_title: dict[str, ExternalItem] = {}
    duplicate_item_titles: set[str] = set()
    for item in items:
        key = _matchable_title(item.title)
        if not key:
            continue
        if key in item_by_title:
            duplicate_item_titles.add(key)
            continue
        item_by_title[key] = item

    task_by_title: dict[str, tuple[Path, str]] = {}
    duplicate_task_titles: set[str] = set()
    known_ext_ids: set[str] = set()
    for plan_dir in plan_dirs:
        plan_path = plan_dir / PLAN_FILENAME
        if not plan_path.exists():
            continue
        state = load_state(plan_dir)
        mapping = adapter_state(state, adapter_name)
        known_ext_ids.update(mapping.values())
        for task in parse_plan(plan_path):
            ext_id = source_external_id(task, adapter_name)
            if ext_id:
                known_ext_ids.add(ext_id)
            key = _matchable_title(task.title)
            if not key:
                continue
            if key in task_by_title:
                duplicate_task_titles.add(key)
                continue
            task_by_title[key] = (plan_dir, task.id)

    recovered: set[str] = set()
    for title_key, item in item_by_title.items():
        if title_key in duplicate_item_titles or title_key in duplicate_task_titles:
            continue
        task_ref = task_by_title.get(title_key)
        if not task_ref:
            continue
        if item.external_id in known_ext_ids:
            recovered.add(item.external_id)
            continue
        plan_dir, task_id = task_ref
        state = load_state(plan_dir)
        mapping = adapter_state(state, adapter_name)
        existing = mapping.get(task_id)
        if existing and existing != item.external_id:
            continue
        recovered.add(item.external_id)
        if not dry_run:
            mapping[task_id] = item.external_id
            save_state(plan_dir, state)
            known_ext_ids.add(item.external_id)
    return recovered


def _split_plan_for_task_insert(text: str) -> tuple[str, str, str]:
    """Split PLAN.md into (head, tasks_block, tail) so we can append new task
    lines just before the next sibling header (Decision Log / Progress / etc).

    head      — everything up to and including the line "## Tasks"
    tasks     — the body of the Tasks section (may end with blank lines)
    tail      — the next sibling header onward

    If no `## Tasks` section exists, the tasks block is empty and we splice
    one in at the end of the document.
    """
    lines = text.splitlines(keepends=True)
    _TERMINATOR_HEADERS = (
        "## Decision Log",
        "## Progress",
        "## Open Questions",
        "## ARCHIVE",
        "## Archive",
    )
    task_start = task_end = None
    for i, line in enumerate(lines):
        if re.match(r"^## Tasks\s*$", line):
            task_start = i + 1
            continue
        if task_start is not None:
            stripped = line.rstrip()
            if any(stripped == h or stripped.startswith(h + " ")
                   for h in _TERMINATOR_HEADERS):
                task_end = i
                break
    if task_start is None:
        # No ## Tasks section — append one at the end.
        head = text if text.endswith("\n") else text + "\n"
        head += "\n## Tasks\n\n"
        return head, "", ""
    if task_end is None:
        task_end = len(lines)
    head = "".join(lines[:task_start])
    tasks = "".join(lines[task_start:task_end])
    tail = "".join(lines[task_end:])
    return head, tasks, tail


def auto_promote_novel_items(
    target_plan_dir: Path,
    items: list[ExternalItem],
    adapter_name: str,
    fleet_known_ext_ids: set[str],
    dry_run: bool,
    max_new: int | None = DEFAULT_AUTO_PROMOTE_MAX_NEW,
) -> tuple[int, dict[str, str]]:
    """Promote novel external items directly to a target plan's `## Tasks`.

    Returns (count_appended, new_mappings). `new_mappings` is a dict of
    {task_id: external_id} the caller should merge into the target plan_dir's
    state file via adapter_state(...) + save_state(...).

    Idempotency is double-checked:
      1. `fleet_known_ext_ids` (state-file-derived) — primary signal
      2. `[Source: <adapter>:<id>]` markers scanned in PLAN.md text — bulletproof
         fallback when the state file got blown away (e.g. during a rebase
         that stashed it as untracked then dropped the stash).

    Same item across two cycles produces no change because either the
    state file or the in-text marker prevents re-promotion.
    """
    if not items:
        return 0, {}
    plan_path = target_plan_dir / PLAN_FILENAME
    text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    seq = _next_bd_seq(text)

    # Scan PLAN.md text for ext_ids already present as `[Source: <adapter>:<id>]`
    # markers. This is the bulletproof safety net against state-file loss.
    in_text_ext_ids: set[str] = set()
    for m in re.finditer(
        rf"\[Source:\s*{re.escape(adapter_name)}:([A-Za-z0-9_\-]+)\]", text
    ):
        in_text_ext_ids.add(m.group(1))
    skip_set = fleet_known_ext_ids | in_text_ext_ids

    new_lines: list[str] = []
    new_mappings: dict[str, str] = {}
    for item in items:
        if item.external_id in skip_set:
            continue
        # Build a sanitized, single-line title so it survives PLAN.md parsing.
        title = re.sub(r"\s+", " ", item.title).strip()
        if len(title) > 240:
            title = title[:239].rstrip() + "…"
        task_id = f"BD-{seq}"
        seq += 1
        marker = f"[Source: {adapter_name}:{item.external_id}]"
        new_lines.append(f"- [pending] {task_id}: {title} {marker}")
        new_mappings[task_id] = item.external_id

    if not new_lines:
        return 0, {}

    if max_new is not None and len(new_lines) > max_new:
        raise ValueError(
            "auto_promote would append "
            f"{len(new_lines)} tasks, above auto_promote_max_new={max_new}; "
            "refusing to mutate PLAN.md"
        )

    if not dry_run:
        head, tasks, tail = _split_plan_for_task_insert(text)
        # Ensure the tasks block ends with exactly one blank line before tail.
        tasks_body = tasks.rstrip("\n")
        if tasks_body:
            tasks_body += "\n"
        else:
            tasks_body = ""
        addition = "\n".join(new_lines) + "\n"
        if tasks_body:
            new_text = head + tasks_body + addition + ("\n" if tail else "") + tail
        else:
            new_text = head + addition + ("\n" if tail else "") + tail
        plan_path.write_text(new_text, encoding="utf-8")
    return len(new_lines), new_mappings


def auto_promote_max_new(source: dict[str, Any]) -> int | None:
    """Return the configured auto-promote batch cap for one source."""
    raw = (source.get("config") or {}).get(
        "auto_promote_max_new",
        DEFAULT_AUTO_PROMOTE_MAX_NEW,
    )
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("auto_promote_max_new must be an integer or null") from exc
    if value < 0:
        raise ValueError("auto_promote_max_new must be >= 0 or null")
    return value


# --- PLAN.md status flip -----------------------------------------------------


def flip_plan_statuses(plan_path: Path, flips: dict[str, VidxStatus],
                       dry_run: bool) -> int:
    """Rewrite PLAN.md flipping `[old]` to `[new]` for the given task ids.

    Only called for external → completed promotions. Returns count of tasks
    actually flipped.
    """
    if not flips:
        return 0
    text = plan_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = 0

    # Mirror parse_plan's terminator whitelist — non-canonical `## ` dividers
    # (e.g. "## HUGE ESTIMATION") sit inside the Tasks block in long-running
    # plans and must NOT end the flip scan.
    _TERMINATOR_HEADERS = (
        "## Decision Log",
        "## Progress",
        "## Open Questions",
        "## ARCHIVE",
        "## Archive",
    )
    task_start = None
    for i, line in enumerate(lines):
        if re.match(r"^## Tasks\s*$", line.rstrip("\n")):
            task_start = i + 1
            break
    if task_start is None:
        return 0

    for i in range(task_start, len(lines)):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip()
        if any(stripped == h or stripped.startswith(h + " ") for h in _TERMINATOR_HEADERS):
            break
        m = _TASK_LINE.match(line.rstrip("\n"))
        if not m:
            continue
        tid = m.group("id")
        if tid not in flips:
            continue
        new_status = flips[tid].value
        old_status = m.group("status")
        if old_status == new_status:
            continue
        lines[i] = line.replace(f"[{old_status}]", f"[{new_status}]", 1)
        changed += 1

    if changed and not dry_run:
        plan_path.write_text("".join(lines), encoding="utf-8")
    return changed


# --- Adapter instantiation ---------------------------------------------------


def instantiate_adapter(source: dict[str, Any]) -> AdapterBase | None:
    if not source.get("enabled", False):
        return None
    name = source.get("adapter")
    if not name:
        return None
    cls = get_adapter(name)
    return cls(source.get("config", {}))


# --- Sync per plan × adapter -------------------------------------------------


def sync_plan_with_adapter(
    plan_dir: Path,
    adapter: AdapterBase,
    direction: str,
    dry_run: bool,
    push_statuses: set[VidxStatus] | None = None,
    do_pull: bool = True,
    do_push: bool = True,
    fleet_known_ext_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Reconcile one plan-dir against one adapter. Return a summary dict.

    When multiple plan_dirs share a single adapter, only the FIRST plan in the
    iteration should receive the pull half's inbox append (otherwise 22 plans
    × 70 board items = 1,540 duplicate INBOX entries per run). Callers pass
    `do_pull=False` on subsequent plans; `fleet_known_ext_ids` carries the
    union of ext_ids mapped in every plan's `.external-state.json` so genuinely
    novel items are still detected correctly.
    """
    plan_path = plan_dir / PLAN_FILENAME
    state = load_state(plan_dir)
    mapping = adapter_state(state, adapter.name)

    tasks = parse_plan(plan_path)
    tasks_by_id = {t.id: t for t in tasks}
    source_mappings = source_marker_mappings(tasks, adapter.name)
    source_mapped = 0
    for task_id, external_id in source_mappings.items():
        if task_id not in mapping:
            mapping[task_id] = external_id
            source_mapped += 1

    summary: dict[str, Any] = {
        "plan": str(plan_dir),
        "adapter": adapter.name,
        "tasks": len(tasks),
        "external_items": 0,
        "pushed": 0,
        "pushed_ids": [],
        "inbox_appended": 0,
        "plan_flipped": 0,
        "flipped_ids": [],
        "source_mapped": source_mapped,
        "push_skipped_idempotent": 0,
        "push_suppressed_auto_promote": 0,
        "errors": [],
    }

    # fetch_inbox always — both halves benefit. The pull half needs it for
    # novel-item detection + status flip; the push half needs it for
    # idempotency (skip push_status / push_fields when remote already
    # matches local). Adapter caches the result for the instance's lifetime.
    external_items: list[ExternalItem] = []
    try:
        external_items = adapter.fetch_inbox()
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"fetch_inbox: {exc}")
        return summary
    summary["external_items"] = len(external_items)
    ext_by_id = {item.external_id: item for item in external_items}

    if direction in ("pull", "both"):
        # Novel = external items not mapped to ANY plan in the fleet (so the
        # same item doesn't get appended to 22 different INBOX.md files).
        # Fall back to per-plan mapping when fleet set wasn't supplied.
        known_ext_ids = set(mapping.values())
        if fleet_known_ext_ids is not None:
            known_ext_ids |= fleet_known_ext_ids
        novel = [item for item in external_items if item.external_id not in known_ext_ids]
        # Only the first plan in the fleet-iteration actually writes novel
        # items to its INBOX.md. Everyone else skips the append but still
        # performs the flip reconcile below (that's per-plan data).
        if do_pull:
            summary["inbox_appended"] = append_inbox(
                plan_dir, novel, adapter.name, dry_run
            )

        # Flip PLAN.md tasks that have moved to completed on the external board.
        flips: dict[str, VidxStatus] = {}
        for task_id, ext_id in mapping.items():
            item = ext_by_id.get(ext_id)
            if not item:
                continue
            plan_task = tasks_by_id.get(task_id)
            if not plan_task:
                continue
            if item.status == VidxStatus.COMPLETED and plan_task.status != VidxStatus.COMPLETED:
                flips[task_id] = VidxStatus.COMPLETED
        summary["plan_flipped"] = flip_plan_statuses(plan_path, flips, dry_run)
        summary["flipped_ids"] = sorted(flips.keys())

    if direction in ("push", "both") and not do_push:
        effective_push = push_statuses or {
            VidxStatus.PENDING, VidxStatus.IN_PROGRESS, VidxStatus.IN_REVIEW
        }
        summary["push_suppressed_auto_promote"] = len([
            t for t in tasks if t.status in effective_push
        ])

    if direction in ("push", "both") and do_push:
        # Push any PLAN.md task whose status is in push_statuses and has no
        # external_id recorded. Default excludes BLOCKED (historical summaries
        # stay in PLAN.md) — pass --push-statuses to override.
        effective_push = push_statuses or {
            VidxStatus.PENDING, VidxStatus.IN_PROGRESS, VidxStatus.IN_REVIEW
        }
        pushable = [
            t for t in tasks
            if t.status in effective_push
            and t.id not in mapping
        ]
        for task in pushable:
            try:
                if dry_run:
                    external_id = f"<dry-run:{task.id}>"
                else:
                    external_id = adapter.push_task(task)
                mapping[task.id] = external_id
                summary["pushed"] += 1
                summary["pushed_ids"].append(task.id)
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(f"push_task({task.id}): {exc}")

        # Reconcile status + blocked for tasks we already know about.
        # Idempotency: skip the GraphQL mutation when remote already
        # matches local. This was the rate-limit-flood root cause —
        # the loop fired ~138 push_status calls per cycle on
        # a busy repo even when nothing changed, exhausting Linear's
        # hourly bucket in one hour. INBOX P1 2026-04-25.
        skipped = 0
        for task in tasks:
            ext_id = mapping.get(task.id)
            if not ext_id:
                continue
            if task.status == VidxStatus.COMPLETED:
                # We only push active tasks; completed is a terminal record.
                continue
            if dry_run:
                continue
            remote = ext_by_id.get(ext_id)
            local_blocked = task.blocked or task.status == VidxStatus.BLOCKED
            try:
                # push_status: only when status diverges. BLOCKED is
                # orthogonal — never pushed via push_status (adapters
                # reject it); the blocked flag handles it below.
                if task.status != VidxStatus.BLOCKED:
                    if remote is None or remote.status != task.status:
                        adapter.push_status(ext_id, task.status)
                    else:
                        skipped += 1
                # push_fields(_blocked): only when the flag diverges.
                if remote is None or remote.blocked != local_blocked:
                    adapter.push_fields(ext_id, {"_blocked": local_blocked})
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(f"push_status({task.id}): {exc}")
        summary["push_skipped_idempotent"] = skipped

    if not dry_run:
        save_state(plan_dir, state)

    return summary


def sync_prs_to_project(adapter: AdapterBase,
                        repo_dir: Path,
                        dry_run: bool) -> dict[str, Any]:
    """Add open + recently-closed PRs from a repo onto the bound GH Project.

    Idempotent: walks all open and recently-merged PRs, looks each up in the
    adapter's PR-url cache, and only calls add_pr_to_project for PRs not yet
    represented as a project item. Status is set to:
        OPEN draft         → IN_PROGRESS  (Dev column)
        OPEN ready         → IN_REVIEW    (QA/Testing/Review column)
        MERGED             → COMPLETED    (Prod/Shipped column)
        CLOSED (not merged)→ skipped (no card; closed-without-merge is noise)

    Only supports gh_projects adapters today; other adapters raise here. The
    sync is best-effort — a single PR's failure doesn't abort the sweep.
    """
    summary: dict[str, Any] = {
        "repo": str(repo_dir),
        "open_prs": 0,
        "merged_prs": 0,
        "added": 0,
        "moved": 0,
        "errors": [],
    }
    if adapter.name != "gh_projects":
        return summary  # only gh_projects supports PR linking

    # Discover the repo's owner/name via `gh repo view`.
    try:
        proc = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner"],
            cwd=str(repo_dir), capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            summary["errors"].append(f"gh repo view: {proc.stderr.strip()}")
            return summary
        repo_full = json.loads(proc.stdout)["nameWithOwner"]
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"gh repo view: {exc}")
        return summary

    # List open + recently-merged PRs (last 50 of each — covers anything from
    # the last few days at typical fleet velocity).
    pr_states = [("open", "open"), ("merged", "merged")]
    pr_index: dict[str, dict[str, Any]] = {}
    for state_name, state_arg in pr_states:
        try:
            proc = subprocess.run(
                ["gh", "pr", "list", "--repo", repo_full, "--state", state_arg,
                 "--limit", "50",
                 "--json", "number,url,title,id,isDraft,state,mergedAt"],
                capture_output=True, text=True, check=False,
            )
            if proc.returncode != 0:
                summary["errors"].append(
                    f"gh pr list {state_arg}: {proc.stderr.strip()[:160]}"
                )
                continue
            for pr in json.loads(proc.stdout):
                pr_index[pr["url"]] = pr
                if state_name == "open":
                    summary["open_prs"] += 1
                else:
                    summary["merged_prs"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"gh pr list {state_arg}: {exc}")

    if not pr_index:
        return summary

    # Idempotency map: PR URL → project_item_id (already on board).
    try:
        url_to_item = adapter._pr_url_to_item_id_cache()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"fetch project items: {exc}")
        return summary

    for url, pr in pr_index.items():
        # Compute target status from PR state.
        if pr["state"] == "MERGED":
            target_status = VidxStatus.COMPLETED
        elif pr.get("isDraft"):
            target_status = VidxStatus.IN_PROGRESS
        else:
            target_status = VidxStatus.IN_REVIEW

        item_id = url_to_item.get(url)
        try:
            if item_id is None:
                # Only auto-ADD open PRs to the board. Merged PRs that were
                # never tracked stay off — backfilling 50 historical merges
                # would flood the Backlog with already-shipped work.
                if pr["state"] == "MERGED":
                    continue
                if dry_run:
                    summary["added"] += 1
                    continue
                item_id = adapter.add_pr_to_project(pr["id"], target_status)
                url_to_item[url] = item_id
                summary["added"] += 1
            else:
                # Already on board — reconcile status if it drifted.
                if dry_run:
                    summary["moved"] += 1
                    continue
                adapter.push_status(item_id, target_status)
                summary["moved"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(
                f"pr#{pr['number']} ({target_status.value}): {str(exc)[:160]}"
            )
    return summary


# --- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Round-trip sync between PLAN.md and external kanban boards."
    )
    parser.add_argument("--config", help="Path to vidux.config.json")
    parser.add_argument("--plan", help="Path to a single plan dir (skips plan_store walk)")
    parser.add_argument(
        "--direction",
        choices=("pull", "push", "both"),
        default="both",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable summary")
    parser.add_argument(
        "--push-statuses",
        default="pending,in_progress,in_review",
        help=("Comma-separated vidux statuses eligible for push as new items. "
              "Default excludes 'blocked' (historical summaries stay in PLAN.md). "
              "Valid values: pending,in_progress,in_review,blocked,completed."),
    )
    parser.add_argument(
        "--include-prs",
        action="store_true",
        help=("Also sweep open + recently-merged PRs from the repo containing "
              "the config and add them as items on the bound GH Project. "
              "Status follows PR state: open-draft→Dev, open-ready→QA-Review, "
              "merged→Prod-Shipped. Idempotent — skips PRs already on board."),
    )
    parser.add_argument(
        "--repo-dir",
        help=("Repo directory to source PR list from (defaults to the parent "
              "of the resolved config). Only used with --include-prs."),
    )
    parser.add_argument(
        "--only-adapter",
        help=("Run sync only for sources whose adapter name matches. "
              "Lets per-adapter crons run at independent cadences (e.g. "
              "Linear at 10-min, GH Projects at 30-min)."),
    )
    args = parser.parse_args(argv)

    try:
        push_statuses = {
            VidxStatus(s.strip())
            for s in args.push_statuses.split(",")
            if s.strip()
        }
    except ValueError as exc:
        print(f"error: --push-statuses: {exc}", file=sys.stderr)
        return 2

    try:
        config_path = find_config(args.config)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    config = load_config(config_path)

    sources = config.get("inbox_sources", []) or []
    if args.only_adapter:
        sources = [s for s in sources if s.get("adapter") == args.only_adapter]
    if not sources:
        reason = (
            f"no inbox_sources for adapter={args.only_adapter}"
            if args.only_adapter
            else "no inbox_sources"
        )
        if args.json:
            print(json.dumps({"status": "noop", "reason": reason}))
        else:
            print(f"{reason}; nothing to sync.")
        return 0

    try:
        plan_dirs = resolve_plan_dirs(config, args.plan)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not plan_dirs:
        print("no plan dirs found under plan_store.path", file=sys.stderr)
        return 0

    results: list[dict[str, Any]] = []
    exit_code = 0
    for source in sources:
        try:
            adapter = instantiate_adapter(source)
        except (KeyError, ValueError) as exc:
            print(f"error: adapter '{source.get('adapter')}': {exc}", file=sys.stderr)
            exit_code = 3
            continue
        if adapter is None:
            continue
        # Build fleet-wide set of ext_ids already mapped under this adapter
        # across ALL plan_dirs — prevents the same external item being tagged
        # "novel" by every plan in the fleet and appended 22× to INBOX.md.
        fleet_known: set[str] = set()
        for plan_dir in plan_dirs:
            state = load_state(plan_dir)
            mapping = adapter_state(state, adapter.name)
            fleet_known.update(mapping.values())
            plan_path = plan_dir / PLAN_FILENAME
            if plan_path.exists():
                fleet_known.update(
                    source_marker_mappings(
                        parse_plan(plan_path),
                        adapter.name,
                    ).values()
                )

        # Resolve auto_promote_target if set in adapter source config.
        # When set, novel cards skip the INBOX.md path and land directly in
        # the named plan_dir's PLAN.md as `[pending] BD-<n>: ...` tasks.
        promote_target_dir: Path | None = None
        promote_max_new: int | None = DEFAULT_AUTO_PROMOTE_MAX_NEW
        promote_raw = (source.get("config") or {}).get("auto_promote_target")
        if promote_raw:
            try:
                promote_max_new = auto_promote_max_new(source)
            except ValueError as exc:
                results.append({
                    "_kind": "auto_promote",
                    "adapter": adapter.name,
                    "target": str(promote_raw),
                    "promoted": 0,
                    "errors": [str(exc)],
                })
                if exit_code == 0:
                    exit_code = 2
                continue
            base = Path(config["_config_dir"])
            cand = Path(promote_raw).expanduser()
            promote_target_dir = (
                cand if cand.is_absolute() else (base / cand)
            ).resolve()
            if not (promote_target_dir / PLAN_FILENAME).exists():
                # Treat misconfiguration as fatal for this source. Falling
                # back to INBOX would route the external task to the first
                # plan in the store, and would also re-enable PLAN->board
                # pushes for a source the operator configured as import-only.
                msg = (f"auto_promote_target {promote_target_dir} has no "
                       "PLAN.md; refusing to fall back to INBOX")
                results.append({
                    "_kind": "auto_promote",
                    "adapter": adapter.name,
                    "target": str(promote_target_dir),
                    "promoted": 0,
                    "errors": [msg],
                })
                if exit_code == 0:
                    exit_code = 2
                continue

        title_recovered_ext_ids: set[str] = set()
        if promote_target_dir is not None and args.direction in ("pull", "both"):
            try:
                ext_items_for_recovery = adapter.fetch_inbox()
            except Exception:
                # The plan loop below records the fetch error in the normal
                # per-plan summaries. Avoid adding a duplicate synthetic error.
                ext_items_for_recovery = []
            title_recovered_ext_ids = recover_title_mappings(
                plan_dirs,
                ext_items_for_recovery,
                adapter.name,
                args.dry_run,
            )
            fleet_known.update(title_recovered_ext_ids)

        # When auto-promote is on, suppress the per-plan INBOX append
        # entirely (do_pull=False everywhere). The promotion sweep below
        # handles routing to a single PLAN.md instead.
        suppress_inbox = promote_target_dir is not None
        for idx, plan_dir in enumerate(plan_dirs):
            summary = sync_plan_with_adapter(
                plan_dir, adapter, args.direction, args.dry_run,
                push_statuses=push_statuses,
                do_pull=(False if suppress_inbox else (idx == 0)),
                do_push=(False if suppress_inbox else True),
                fleet_known_ext_ids=fleet_known,
            )
            results.append(summary)
            if summary["errors"]:
                exit_code = 3

        # Auto-promotion sweep — runs once per source after the plan loop.
        if promote_target_dir is not None and args.direction in ("pull", "both"):
            auto_errors: list[str] = []
            auto_exit_code = 0
            auto_promoted = 0
            auto_mappings: dict[str, str] = {}
            try:
                ext_items = adapter.fetch_inbox()  # cached
            except Exception as exc:  # noqa: BLE001
                auto_errors = [f"fetch_inbox: {str(exc)[:200]}"]
                auto_exit_code = 3
            else:
                try:
                    count, new_mappings = auto_promote_novel_items(
                        promote_target_dir, ext_items, adapter.name,
                        fleet_known, args.dry_run,
                        max_new=promote_max_new,
                    )
                except ValueError as exc:
                    auto_errors = [str(exc)]
                    auto_exit_code = 2
                    auto_promoted = 0
                    auto_mappings = {}
                else:
                    auto_promoted = count
                    auto_mappings = new_mappings
                # Persist the new task_id ↔ external_id mapping in the target's
                # state file so subsequent cycles don't re-promote.
                if auto_mappings and not args.dry_run:
                    target_state = load_state(promote_target_dir)
                    target_mapping = adapter_state(target_state, adapter.name)
                    target_mapping.update(auto_mappings)
                    save_state(promote_target_dir, target_state)
            if auto_exit_code and exit_code == 0:
                exit_code = auto_exit_code
            results.append({
                "_kind": "auto_promote",
                "adapter": adapter.name,
                "target": str(promote_target_dir),
                "promoted": auto_promoted,
                "title_matched": len(title_recovered_ext_ids),
                "errors": auto_errors,
            })

        # PR sweep — only when --include-prs is set. One sweep per source.
        if args.include_prs:
            repo_dir = Path(
                args.repo_dir or config.get("_config_dir", str(Path.cwd()))
            ).expanduser().resolve()
            pr_summary = sync_prs_to_project(adapter, repo_dir, args.dry_run)
            pr_summary["adapter"] = adapter.name
            results.append({"_kind": "pr_sweep", **pr_summary})
            if pr_summary["errors"]:
                exit_code = 3

    if args.json:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": args.direction,
            "dry_run": args.dry_run,
            "results": results,
        }, indent=2))
    else:
        for r in results:
            tag = "[dry-run] " if args.dry_run else ""
            kind = r.get("_kind")
            if kind == "pr_sweep":
                print(f"{tag}{r['adapter']} × pr_sweep")
                print(f"  added={r.get('added', 0)} skipped={r.get('skipped', 0)}")
                for err in r.get("errors", []):
                    print(f"  ! {err}")
                continue
            if kind == "auto_promote":
                print(f"{tag}{r['adapter']} × auto_promote → {r.get('target','?')}")
                print(f"  promoted={r.get('promoted', 0)}")
                for err in r.get("errors", []):
                    print(f"  ! {err}")
                continue
            print(f"{tag}{r['adapter']} × {r.get('plan', '?')}")
            print(f"  tasks={r.get('tasks',0)} external_items={r.get('external_items',0)} "
                  f"pushed={r.get('pushed',0)} inbox+={r.get('inbox_appended',0)} "
                  f"flipped={r.get('plan_flipped',0)}")
            if r.get("pushed_ids"):
                print(f"  pushed: {', '.join(r['pushed_ids'])}")
            if r.get("flipped_ids"):
                print(f"  flipped→completed: {', '.join(r['flipped_ids'])}")
            if r.get("source_mapped"):
                print(f"  source-mapped={r['source_mapped']}")
            if r.get("push_suppressed_auto_promote"):
                print(
                    "  push suppressed by auto_promote="
                    f"{r['push_suppressed_auto_promote']}"
                )
            for err in r.get("errors", []):
                print(f"  ! {err}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
