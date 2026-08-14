#!/usr/bin/env python3
"""Shadow bi-daily brief — collect, render, deliver, schedule.

Authority: this computer's ~/.shadow board + entity PLAN.md files.
Paint: local Development git repos, GitHub CLI, optional Vercel/Supabase.
Delivery: HTML evidence + macOS notification + a guarded Superhuman self-mail.
All receipts stay under the computer's private Shadow store; this source tree
never carries operational plans, mailbox receipts, or a second task queue.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import os
import plistlib
import re
import secrets
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import shadow_root_board as _shadow_board

LABEL = "com.leokwan.shadow-bidaily-brief"
SLOT_HOURS = (8, 20)
REPORT_TIMEZONE_NAME = "America/New_York"
REPORT_TIMEZONE = ZoneInfo(REPORT_TIMEZONE_NAME)
REPORT_LOOKBACK_HOURS = 14
GITHUB_PR_LIMIT = 20
BOARD_PATH = Path.home() / ".shadow" / "board.json"
DEFAULT_PORTFOLIO = Path.home() / "Development"
PRIVATE_BRIEF_ROOT = Path.home() / ".shadow" / "briefs"
EVIDENCE_DIR = PRIVATE_BRIEF_ROOT / "evidence"
LOG_DIR = PRIVATE_BRIEF_ROOT / "ledger"
WINDOW_LOG = LOG_DIR / "scheduled-windows.jsonl"
SEND_ATTEMPT_LOG = LOG_DIR / "send-attempts.jsonl"
MAILBOX_READBACK_LOG = LOG_DIR / "mailbox-readbacks.jsonl"
SELF_MAIL = "leojkwan@gmail.com"
SNOWCUBES_BUSINESS_MAIL = "trysnowcubes@gmail.com"
EXPECTED_SUPERHUMAN_IDENTITIES = (
    SELF_MAIL,
    SNOWCUBES_BUSINESS_MAIL,
    "firstbitelabs@gmail.com",
)
SUPERHUMAN_CONTEXT_SCHEMA = "shadow.superhuman-context.v2"
PRODUCER_PROVENANCE_SCHEMA = "shadow.brief-producer.v1"
SCHEDULED_ATTEMPT_SCHEMA = "shadow.bidaily-attempt.v1"
SEND_ATTEMPT_SCHEMA = "shadow.superhuman-send-attempt.v1"
SUPERHUMAN_LOOKBACK_DAYS = 90
SUPERHUMAN_PAGE_LIMIT = 50
SUPERHUMAN_MAX_PAGES = 40
SUPERHUMAN_MAX_ACTION_THREADS = 40
SUPERHUMAN_GLOBAL_ACTION_LIMIT = 40
SUPERHUMAN_READ_BUDGET_SECONDS = 420
SUPERHUMAN_SIGNAL_LIMIT = 50
# Each reader-first action category is classified from the full collision-safe
# set and bounded separately. Classifying from the retention sample instead
# drops a real obligation before anything ever reads it as one.
SUPERHUMAN_CATEGORY_LIMIT = 200
SUPERHUMAN_LIST_LANES = (
    ("active_inbox", ("INBOX",)),
    ("sent_follow_up", ("SENT",)),
)
SNOWCUBES_SHOPIFY_STORE = "939cf1-24"
SNOWCUBES_NATIVE_LINKS = {
    "commerce": f"https://admin.shopify.com/store/{SNOWCUBES_SHOPIFY_STORE}/orders",
    "funnel": "https://app.posthog.com/",
    "search": "https://search.google.com/search-console",
    "local": "https://business.google.com/",
    "lifecycle": "https://resend.com/overview",
    "seo": "https://app.ahrefs.com/",
    "shadow": "https://github.com/firstbitelabsllc/shadow",
    "deploy": "https://vercel.com/dashboard",
    "m12": "https://github.com/firstbitelabsllc/trysnowcubes-web/blob/main/scripts/cafe-doctor.py",
}
# v4 starts a fresh proof series for one reader-first umbrella brief at both
# natural windows. Older Snowcubes-first and generic notes remain private
# history, not evidence for this outcome.
WINDOW_RECEIPT_SCHEMA = "shadow.bidaily-window.v4"
MAILBOX_READBACK_SCHEMA = "shadow.superhuman-mailbox-readback.v1"
SUPERHUMAN_MCP_RESOURCE = "https://mcp.mail.superhuman.com/mcp"


class PrivateJSONLError(OSError):
    """An existing private JSONL ledger cannot be trusted as authority."""


SUPERHUMAN_TOKEN_ENDPOINT = "https://mcp.auth.mail.superhuman.com/oauth2/token"
SUPERHUMAN_MCP_CACHE_KEY = hashlib.md5(
    SUPERHUMAN_MCP_RESOURCE.encode("utf-8"), usedforsecurity=False
).hexdigest()

TASK_RE = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<title>.+?) ~(?P<id>[a-z0-9]{4})"
    r"(?: \(DoD\))?"
    r"(?: \| proof: (?P<proof>.+?))?"
    r"(?: \| needs: (?P<needs>.+?))?"
    r"\s*$"
)
MILESTONE_RE = re.compile(r"^### (?P<title>.+)\s*$")
BRIEF_RE = re.compile(r"^- (?P<key>Project|Mode|Priority): (?P<val>.+)$")


def brief_subject(slot: Any, generated_at: Any) -> str:
    """Keep one umbrella report identity at both natural delivery windows."""
    normalized_slot = str(slot or "brief").strip().lower()
    when = str(generated_at or "")
    return f"Shadow {normalized_slot} brief — {when}"


@dataclass
class Checkpoint:
    id: str
    title: str
    state: str
    proof: str = ""
    milestone: str = ""


@dataclass
class EntityBrief:
    project: str
    plan: str
    mode: str = ""
    priority: int | None = None
    resume: str | None = None
    entity_id: str = ""
    availability: str = "available"
    error: str = ""
    wake: str = ""
    open_checkpoints: list[Checkpoint] = field(default_factory=list)
    blocked: list[Checkpoint] = field(default_factory=list)
    forgotten: list[Checkpoint] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    recent_progress: list[str] = field(default_factory=list)


@dataclass
class RepoPaint:
    name: str
    path: str
    branch: str = ""
    dirty: bool = False
    ahead: int = 0
    behind: int = 0
    last_commit_age_h: float | None = None
    last_subject: str = ""
    recent_commits: list[str] = field(default_factory=list)
    stale: bool = False


@dataclass
class Recommendation:
    kind: str  # unify | streamline | challenge | focus | kill
    text: str
    source: str


def _row_id(value: Any) -> str:
    """Normalize a checkpoint/claim row ID without losing entity scope."""
    return str(value or "").lstrip("~")


def _entity_id(entity: dict[str, Any]) -> str:
    """Return the board entity identity used to scope claims."""
    return str(entity.get("entity_id") or entity.get("id") or "")


def _claim_key(entity_id: Any, row_id: Any) -> tuple[str, str]:
    return (str(entity_id or ""), _row_id(row_id))


def _claim_key_for(entity: dict[str, Any], checkpoint: dict[str, Any]) -> tuple[str, str]:
    return _claim_key(_entity_id(entity), checkpoint.get("id"))


def _claim_index(claims: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Index claims by (entity, row); row IDs are not globally unique."""
    return {
        _claim_key(claim.get("entity"), claim.get("row")): claim
        for claim in claims
        if claim.get("entity") and claim.get("row")
    }


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def producer_provenance() -> dict[str, Any]:
    """Bind a packet to the exact checked-in producer bytes that created it."""
    script = Path(__file__).resolve()
    try:
        script_sha256 = hashlib.sha256(script.read_bytes()).hexdigest()
    except OSError:
        script_sha256 = ""
    source_commit: str | None = None
    source_matches_commit = False
    try:
        root_result = _run(
            ["git", "-C", str(script.parent), "rev-parse", "--show-toplevel"]
        )
        if root_result.returncode == 0:
            root = Path((root_result.stdout or "").strip()).expanduser()
            try:
                relative = script.relative_to(root.resolve(strict=True))
            except (OSError, ValueError):
                relative = None
            if relative is not None:
                commit_result = _run(["git", "-C", str(root), "rev-parse", "HEAD"])
                candidate = (commit_result.stdout or "").strip().lower()
                if commit_result.returncode == 0 and _is_full_git_object_id(candidate):
                    source_commit = candidate
                    status_result = _run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "status",
                            "--porcelain",
                            "--untracked-files=all",
                            "--",
                            str(relative),
                        ]
                    )
                    working_blob = _run(
                        ["git", "-C", str(root), "hash-object", str(relative)]
                    )
                    committed_blob = _run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "rev-parse",
                            f"HEAD:{relative.as_posix()}",
                        ]
                    )
                    working_identity = (working_blob.stdout or "").strip().lower()
                    committed_identity = (committed_blob.stdout or "").strip().lower()
                    source_matches_commit = (
                        status_result.returncode == 0
                        and not (status_result.stdout or "").strip()
                        and working_blob.returncode == 0
                        and committed_blob.returncode == 0
                        and _is_full_git_object_id(working_identity)
                        and working_identity == committed_identity
                        and len(script_sha256) == 64
                    )
    except (OSError, subprocess.TimeoutExpired):
        source_matches_commit = False
    return {
        "schema": PRODUCER_PROVENANCE_SCHEMA,
        "source_commit": source_commit,
        "script_sha256": script_sha256,
        "source_matches_commit": source_matches_commit,
    }


def collect_shadow_status_excerpt() -> str:
    """Keep the optional seat summary from taking down the authoritative packet."""
    try:
        status = _run(["shadow", "status", "--by", "leo"], timeout=8)
    except (OSError, subprocess.TimeoutExpired) as exc:
        reason = "timed out" if isinstance(exc, subprocess.TimeoutExpired) else "was unavailable"
        return (
            f"Optional seat-status summary {reason}; the report continued from the "
            "separately read, revision-checked Shadow board."
        )
    return (status.stdout or status.stderr or "")[:4000]


def portfolio_root() -> Path:
    raw = os.environ.get("SHADOW_PORTFOLIO_ROOT") or os.environ.get("SHADOW_DEV_ROOT")
    return Path(raw).expanduser() if raw else DEFAULT_PORTFOLIO


def parse_plan(path: Path) -> EntityBrief:
    # Plans may be legacy Markdown or a content-addressed plan tree. The report
    # must read the same logical bytes as Shadow itself; parsing the tiny tree
    # pointer destroys the context needed for a real portfolio read.
    text = _shadow_board.read_plan_text(path)
    project = path.parent.name
    mode = ""
    priority: int | None = None
    for line in text.splitlines():
        m = BRIEF_RE.match(line.strip())
        if not m:
            continue
        key, val = m.group("key"), m.group("val").strip()
        if key == "Project":
            project = val
        elif key == "Mode":
            mode = val
        elif key == "Priority":
            try:
                priority = int(val)
            except ValueError:
                priority = None

    milestone = ""
    open_cps: list[Checkpoint] = []
    blocked: list[Checkpoint] = []
    for line in text.splitlines():
        ms = MILESTONE_RE.match(line)
        if ms:
            milestone = ms.group("title").strip()
            continue
        tm = TASK_RE.match(line.strip())
        if not tm:
            continue
        cp = Checkpoint(
            id=tm.group("id"),
            title=tm.group("title").strip(),
            state=tm.group("state"),
            proof=(tm.group("proof") or "").strip(),
            milestone=milestone,
        )
        if cp.state in {"pending", "in_progress"}:
            open_cps.append(cp)
        elif cp.state == "blocked":
            blocked.append(cp)

    # Forgotten heuristic: pending rows whose milestone is not the last open milestone
    # and title contains stall signals, or blocked without recent progress mention.
    forgotten = [
        cp
        for cp in open_cps + blocked
        if any(
            token in cp.title.lower()
            for token in ("forgotten", "stale", "cruft", "slop", "open-ended", "park", "orphan")
        )
    ]
    decisions: list[str] = []
    recent_progress: list[str] = []
    section_name = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section_name = line[3:].strip().lower()
            continue
        clean = line.strip()
        if section_name == "contradictions" and clean.startswith("- ") and (
            "| winner:" in clean or "| provisional winner:" in clean
        ):
            decisions.append(clean[2:].replace("| provisional winner:", "| winner:"))
        elif section_name == "progress" and clean.startswith("- "):
            recent_progress.append(clean[2:])

    return EntityBrief(
        project=project,
        plan=str(path),
        mode=mode,
        priority=priority,
        open_checkpoints=open_cps,
        blocked=blocked,
        forgotten=forgotten,
        decisions=decisions[-3:],
        recent_progress=recent_progress[-4:],
    )


def unavailable_plan_brief(
    *,
    entity: dict[str, Any],
    project_id: str,
    plan_path: Path,
    priority: int | None,
    error: str,
) -> EntityBrief:
    """Keep one unreadable plan explicit without aborting the whole brief."""
    return EntityBrief(
        project=project_id or "unknown",
        plan=str(plan_path),
        priority=priority,
        resume=entity.get("resume"),
        entity_id=str(entity.get("id") or ""),
        availability="unavailable",
        error=error,
        wake=(
            f"Make {plan_path} locally readable, then run shadow status --by leo; "
            "the next natural brief window retries it."
        ),
    )


def build_shadow_board_health(board: dict[str, Any]) -> dict[str, Any]:
    """Summarize board and plan-read availability for the private receipt."""
    if board.get("error"):
        return {
            "available": False,
            "error": str(board.get("error")),
            "wake": str(
                board.get("wake")
                or "Restore the local Shadow board read, then run shadow status --by leo."
            ),
        }
    unavailable = [
        entity
        for entity in (board.get("entities") or [])
        if isinstance(entity, dict) and entity.get("availability") == "unavailable"
    ]
    if unavailable:
        labels = [
            f"{entity.get('project') or 'unknown'}: {entity.get('error') or 'plan unreadable'}"
            for entity in unavailable
        ]
        wakes = [str(entity.get("wake")) for entity in unavailable if entity.get("wake")]
        return {
            "available": False,
            "error": f"{len(unavailable)} board-owned plan read(s) unavailable: " + "; ".join(labels),
            "wake": "; ".join(dict.fromkeys(wakes)),
        }
    return {"available": True, "revision": board.get("revision")}


def collect_board() -> dict[str, Any]:
    if not BOARD_PATH.is_file():
        return {
            "revision": None,
            "entities": [],
            "projects": [],
            "claims": [],
            "error": "board missing",
            "wake": "Restore the local Shadow board, then run shadow status --by leo.",
        }
    try:
        board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        return {
            "revision": None,
            "entities": [],
            "projects": [],
            "claims": [],
            "error": f"board unreadable: {exc}",
            "wake": "Restore a readable local Shadow board, then run shadow status --by leo.",
        }
    if not isinstance(board, dict):
        return {
            "revision": None,
            "entities": [],
            "projects": [],
            "claims": [],
            "error": "board unreadable: board root must be a JSON object",
            "wake": "Restore a readable local Shadow board, then run shadow status --by leo.",
        }
    projects = board.get("projects", [])
    entity_rows = board.get("entities", [])
    claims = board.get("claims", [])
    nested_error = None
    for name, value in (
        ("projects", projects),
        ("entities", entity_rows),
        ("claims", claims),
    ):
        if not isinstance(value, list):
            nested_error = f"{name} must be a list"
            break
        if any(not isinstance(row, dict) for row in value):
            nested_error = f"{name} rows must be objects"
            break
    if nested_error is None and any(
        not isinstance(entity.get("plan"), str) or not entity.get("plan", "").strip()
        for entity in entity_rows
    ):
        nested_error = "entity plan paths must be nonempty strings"
    if nested_error is not None:
        return {
            "revision": None,
            "entities": [],
            "projects": [],
            "claims": [],
            "error": f"board unreadable: {nested_error}",
            "wake": "Restore a readable local Shadow board, then run shadow status --by leo.",
        }
    # The root board owns project priority; a plan's own Priority line is stale
    # as soon as `shadow priority --value` moves the board-owned value.
    board_priority = {
        str(project.get("id") or ""): project.get("priority")
        for project in projects
        if isinstance(project, dict) and isinstance(project.get("priority"), int)
    }
    entities: list[EntityBrief] = []
    for ent in entity_rows:
        project_id = str(ent.get("project") or "")
        plan_path = Path(ent.get("plan") or "")
        if not plan_path.is_file():
            entities.append(
                unavailable_plan_brief(
                    entity=ent,
                    project_id=project_id,
                    plan_path=plan_path,
                    priority=board_priority.get(project_id),
                    error="plan file is missing or not a regular file",
                )
            )
            continue
        try:
            brief = parse_plan(plan_path)
        except (OSError, _shadow_board.BoardError) as exc:
            entities.append(
                unavailable_plan_brief(
                    entity=ent,
                    project_id=project_id,
                    plan_path=plan_path,
                    priority=board_priority.get(project_id),
                    error=f"plan read failed: {exc}",
                )
            )
            continue
        brief.resume = ent.get("resume")
        brief.entity_id = str(ent.get("id") or "")
        if not brief.project:
            brief.project = project_id or brief.project
        if project_id in board_priority:
            brief.priority = board_priority[project_id]
        entities.append(brief)
    return {
        "revision": board.get("revision"),
        "schema": board.get("schema"),
        "projects": projects,
        "claims": claims,
        "entities": [asdict(e) for e in entities],
    }


def _read_board_revision() -> int | None:
    try:
        board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(board, dict):
        return None
    revision = board.get("revision")
    return (
        revision
        if isinstance(revision, int) and not isinstance(revision, bool)
        else None
    )


def collect_repos(root: Path, *, max_age_h: float = 168.0) -> list[RepoPaint]:
    paints: list[RepoPaint] = []
    if not root.is_dir():
        return paints
    now = time.time()
    candidates = list(root.iterdir())
    installed_shadow = Path.home() / ".local" / "share" / "shadow"
    if installed_shadow.is_dir():
        candidates.append(installed_shadow)
    seen_paths: set[str] = set()
    for child in sorted(candidates, key=lambda path: str(path)):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            canonical_path = str(child.resolve())
        except OSError:
            canonical_path = str(child)
        if canonical_path in seen_paths:
            continue
        seen_paths.add(canonical_path)
        if not (child / ".git").exists():
            continue
        # Skip worktree pools and archives — paint product roots only
        if any(
            tok in child.name
            for tok in ("-worktrees", "-archives", "-worktree-", "scratch", "tmp")
        ):
            continue
        try:
            branch = _run(["git", "-C", str(child), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
            dirty = bool(_run(["git", "-C", str(child), "status", "--porcelain"]).stdout.strip())
            log = _run(
                ["git", "-C", str(child), "log", "-1", "--format=%ct\t%s"]
            ).stdout.strip()
            age_h = None
            subject = ""
            if log:
                ts_s, _, subject = log.partition("\t")
                age_h = (now - int(ts_s)) / 3600.0
            ahead = behind = 0
            ab = _run(
                ["git", "-C", str(child), "rev-list", "--left-right", "--count", "@{upstream}...HEAD"]
            )
            if ab.returncode == 0 and ab.stdout.strip():
                parts = ab.stdout.strip().split()
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])
            stale = bool(age_h is not None and age_h > max_age_h and dirty)
            recent_log = _run(
                [
                    "git",
                    "-C",
                    str(child),
                    "log",
                    f"--since={REPORT_LOOKBACK_HOURS} hours ago",
                    "--max-count=6",
                    "--format=%s",
                ]
            )
            recent_commits = [
                line.strip()
                for line in recent_log.stdout.splitlines()
                if line.strip()
            ] if recent_log.returncode == 0 else []
            paints.append(
                RepoPaint(
                    name=child.name,
                    path=str(child),
                    branch=branch,
                    dirty=dirty,
                    ahead=ahead,
                    behind=behind,
                    last_commit_age_h=round(age_h, 1) if age_h is not None else None,
                    last_subject=subject[:120],
                    recent_commits=recent_commits,
                    stale=stale,
                )
            )
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return paints


def collect_github(limit: int = GITHUB_PR_LIMIT) -> list[dict[str, Any]]:
    if not shutil.which("gh"):
        return []
    proc = _run(
        [
            "gh",
            "search",
            "prs",
            "--author",
            "@me",
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "title,url,repository,updatedAt,isDraft",
        ],
        timeout=45,
    )
    if proc.returncode != 0:
        return [{"error": (proc.stderr or proc.stdout or "gh failed")[:300]}]
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return [{"error": "gh json decode failed"}]


def collect_vercel() -> dict[str, Any]:
    if not shutil.which("vercel"):
        return {"available": False}
    # Vercel CLI 50+ uses --format json (not --json).
    proc = _run(["vercel", "ls", "--format", "json", "-y"], timeout=40)
    if proc.returncode != 0:
        return {"available": True, "error": (proc.stderr or proc.stdout or "")[:300]}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": True, "error": "vercel json decode failed"}
    # Keep tiny paint only — one row per project, prefer READY over noise.
    deployments = data if isinstance(data, list) else data.get("deployments") or []
    rank = {"READY": 0, "ERROR": 1, "BUILDING": 2, "QUEUED": 3, "CANCELED": 9}
    best: dict[str, dict[str, Any]] = {}
    for row in deployments:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("project") or "").strip()
        if not name:
            continue
        state = str(row.get("state") or row.get("readyState") or "")
        cand = {
            "name": name,
            "url": row.get("url"),
            "state": state,
            "created": row.get("created") or row.get("createdAt"),
        }
        prev = best.get(name)
        if prev is None or rank.get(state, 5) < rank.get(str(prev.get("state") or ""), 5):
            best[name] = cand
    slim = list(best.values())[:6]
    return {
        "available": True,
        "deployments": slim,
        "total_projects": len(best),
    }


def collect_supabase() -> dict[str, Any]:
    """Read project health only; never query tables or copy application data."""
    if not shutil.which("supabase"):
        return {"available": False, "error": "Supabase CLI is not installed"}
    proc = _run(["supabase", "projects", "list", "--output", "json"], timeout=45)
    if proc.returncode != 0:
        return {
            "available": False,
            "error": (proc.stderr or proc.stdout or "supabase project read failed")[:300],
        }
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return {"available": False, "error": "supabase json decode failed"}
    projects = [
        {
            "name": str(row.get("name") or "unknown"),
            "status": str(row.get("status") or "unknown"),
            "region": str(row.get("region") or ""),
        }
        for row in rows
        if isinstance(row, dict)
    ]
    return {"available": True, "projects": projects, "total_projects": len(projects)}


def collect_growth_source_status() -> dict[str, dict[str, Any]]:
    astro_available = False
    try:
        with socket.create_connection(("127.0.0.1", 8089), timeout=0.25):
            astro_available = True
    except OSError:
        pass
    return {
        "astro_aso": (
            {"available": True}
            if astro_available
            else {
                "available": False,
                "error": "Astro ASO MCP is not listening on localhost:8089",
                "wake": "open Astro, enable Settings > MCP, then run: lsof -nP -iTCP:8089 -sTCP:LISTEN",
            }
        ),
        "ahrefs_seo": {
            "available": False,
            "error": "Ahrefs MCP is not callable from the unattended report runtime",
            "wake": "claude mcp list | rg -i ahrefs",
        },
        "app_store_connect": {
            "available": False,
            "error": "No read-only App Store Connect adapter is installed for the report runtime",
            "wake": "open Astro, enable Settings > MCP, then confirm tracked apps and ASC metadata are readable",
        },
    }


def build_superhuman_context(
    call_tool: Any,
    *,
    observed_at: datetime | None = None,
    monotonic: Any | None = None,
) -> dict[str, Any]:
    """Build one privacy-bounded mail/calendar read from a live MCP session."""
    read_clock = monotonic or time.monotonic
    read_started = float(read_clock())
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    end_date = now.isoformat(timespec="seconds")
    start_date = (now - timedelta(days=SUPERHUMAN_LOOKBACK_DAYS)).isoformat(
        timespec="seconds"
    )
    query_range = {
        "start_date": start_date,
        "end_date": end_date,
        "lookback_days": SUPERHUMAN_LOOKBACK_DAYS,
    }
    context_problems: list[str] = []
    context_wakes: list[str] = []

    def read_budget_exhausted() -> bool:
        return float(read_clock()) - read_started >= SUPERHUMAN_READ_BUDGET_SECONDS

    def preserve_assertion(exc: Exception) -> None:
        # Tests and callers use AssertionError to prove the read-tool allowlist.
        # Provider parse/type failures are source failures; an unexpected tool
        # name remains a programming error and must stay loud.
        if isinstance(exc, AssertionError):
            raise exc

    def identity(value: Any) -> str:
        candidate = str(value or "").strip().lower()
        return candidate if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate) else ""

    def message_identity(value: Any) -> str:
        if isinstance(value, dict):
            value = value.get("email") or value.get("address")
        raw = str(value or "").strip().lower()
        exact = identity(raw)
        if exact:
            return exact
        match = re.search(r"[^<\s]+@[^>\s]+\.[^>\s]+", raw)
        return identity(match.group(0)) if match else ""

    def message_recipients(message: dict[str, Any]) -> set[str]:
        recipients: set[str] = set()
        for key in ("to", "cc", "bcc", "recipients"):
            values = message.get(key)
            if values is None:
                continue
            if not isinstance(values, list):
                values = [values]
            for value in values:
                recipient = message_identity(value)
                if recipient:
                    recipients.add(recipient)
        return recipients

    def unknown_coverage(
        acting_email: str,
        *,
        wake: str,
        problem: str,
        expected: bool,
    ) -> dict[str, Any]:
        return {
            "acting_email": acting_email,
            "expected": expected,
            "linked": False,
            "status": "UNKNOWN",
            "query_range": dict(query_range),
            "source_observed_at": None,
            "source_age_hours": None,
            "newest_message_at": None,
            "newest_message_age_hours": None,
            "threads_returned": 0,
            "total_estimate": None,
            "pagination": {
                "pages": 0,
                "exhausted": False,
                "truncated": True,
            },
            "calendar": {"status": "UNKNOWN", "proposal_only": True},
            "problems": [problem],
            "wake": wake,
            "metrics": {
                "unread_threads": 0,
                "github_notification_threads": 0,
                "human_or_other_threads": 0,
                "cursor_limit_threads": 0,
            },
        }

    try:
        account_payload = call_tool("list_accounts", {})
        if not isinstance(account_payload, dict):
            raise RuntimeError("list_accounts returned no structured payload")
        if account_payload.get("error"):
            raise RuntimeError(str(account_payload.get("error")))
        if "accounts" not in account_payload:
            raise RuntimeError("list_accounts omitted the account list")
        account_rows = account_payload.get("accounts")
        if not isinstance(account_rows, list):
            raise RuntimeError("list_accounts returned a malformed account list")
    except Exception as exc:
        preserve_assertion(exc)
        problem = f"Superhuman account discovery failed: {exc}"
        coverage = [
            unknown_coverage(
                email,
                expected=True,
                problem=problem,
                wake=(
                    "Restore the Superhuman read-only connection and rerun list_accounts; "
                    f"{email} remains UNKNOWN until live discovery succeeds."
                ),
            )
            for email in EXPECTED_SUPERHUMAN_IDENTITIES
        ]
        return {
            "schema": SUPERHUMAN_CONTEXT_SCHEMA,
            "available": False,
            "complete": False,
            "status": "UNKNOWN",
            "all_clear_allowed": False,
            "error": problem,
            "observed_at": end_date,
            "query_range": query_range,
            "expected_identities": list(EXPECTED_SUPERHUMAN_IDENTITIES),
            "linked_accounts": [],
            "coverage": coverage,
            "threads_returned_raw": 0,
            "threads_unique": 0,
            "signals": [],
            "forgotten_obligations": [],
            "urgent_replies": [],
            "waiting_replies": [],
            "proactive_candidates": [],
            "order_return_follow_up": [],
            "calendar_proposals": [],
            "account_discovery": {
                "status": "UNKNOWN",
                "malformed_rows": 0,
                "wake": "Restore list_accounts before inferring linked identity coverage.",
            },
            "window_hours": SUPERHUMAN_LOOKBACK_DAYS * 24,
            "unread_threads": 0,
            "github_notification_threads": 0,
            "human_or_other_threads": 0,
            "cursor_limit_threads": 0,
        }

    linked_accounts: list[dict[str, Any]] = []
    linked_by_email: dict[str, dict[str, Any]] = {}
    malformed_account_rows = 0
    sender_alias_keys = (
        "aliases",
        "sendAs",
        "send_as",
        "sendAsAddresses",
        "send_as_addresses",
    )
    for row in account_rows:
        if not isinstance(row, dict):
            malformed_account_rows += 1
            continue
        email = identity(row.get("accountEmail") or row.get("account_email") or row.get("email"))
        if not email:
            malformed_account_rows += 1
            continue
        if email in linked_by_email:
            continue
        sender_identities = [email]
        sender_identity_complete = any(key in row for key in sender_alias_keys)
        for key in sender_alias_keys:
            values = row.get(key)
            if values is None:
                continue
            if not isinstance(values, list):
                sender_identity_complete = False
                continue
            for value in values:
                if isinstance(value, dict):
                    value = value.get("email") or value.get("address")
                alias = identity(value)
                if alias:
                    sender_identities.append(alias)
                else:
                    sender_identity_complete = False
        account = {
            "acting_email": email,
            "is_primary": bool(row.get("isPrimary") or row.get("is_primary")),
            "added_at": str(row.get("addedAt") or row.get("added_at") or ""),
            "sender_identities": sorted(dict.fromkeys(sender_identities)),
            "sender_identity_complete": sender_identity_complete,
        }
        linked_accounts.append(account)
        linked_by_email[email] = account
    account_discovery = {
        "status": "UNKNOWN" if malformed_account_rows else "COMPLETE",
        "malformed_rows": malformed_account_rows,
        "wake": (
            f"Inspect and repair {malformed_account_rows} unusable account row from list_accounts before relying on identity coverage."
            if malformed_account_rows == 1
            else (
                f"Inspect and repair {malformed_account_rows} unusable account rows from list_accounts before relying on identity coverage."
                if malformed_account_rows
                else None
            )
        ),
    }
    if malformed_account_rows:
        context_problems.append(
            f"list_accounts returned {malformed_account_rows} unusable account row"
            + ("s" if malformed_account_rows != 1 else "")
        )
        context_wakes.append(str(account_discovery["wake"]))

    def parsed_time(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)

    def source_age(value: Any) -> float | None:
        parsed = parsed_time(value)
        if parsed is None:
            return None
        return round(max(0.0, (now - parsed).total_seconds() / 3600.0), 1)

    def normalized_subject(value: Any) -> str:
        return " ".join(str(value or "").split()).casefold()

    def normalized_message_time(value: Any) -> str:
        parsed = parsed_time(value)
        if parsed is not None:
            return parsed.isoformat(timespec="seconds")
        return " ".join(str(value or "").split()).casefold()

    def identity_sort_key(value: str) -> tuple[int, str]:
        return (
            EXPECTED_SUPERHUMAN_IDENTITIES.index(value)
            if value in EXPECTED_SUPERHUMAN_IDENTITIES
            else len(EXPECTED_SUPERHUMAN_IDENTITIES),
            value,
        )

    def action_tags(row: dict[str, Any], acting_email: str) -> tuple[str, list[str]]:
        subject = str(row.get("subject") or "")
        snippet = str(row.get("snippet") or "")
        participants = " ".join(str(value) for value in (row.get("participants") or []))
        message_text = " ".join(
            f"{message.get('subject', '')} {message.get('snippet', '')}"
            for message in (row.get("messages") or [])
            if isinstance(message, dict)
        )
        combined = f"{subject} {snippet} {participants} {message_text}".lower()
        automated = any(
            marker in combined
            for marker in (
                "noreply",
                "no-reply",
                "do-not-reply",
                "mailer-daemon",
                "notifications@",
                "@t.shopifyemail.com",
                "shopifyemail.com",
            )
        )
        kind = "github" if "github" in combined else ("automated" if automated else "human_or_other")
        labels_value = row.get("labels")
        labels = (
            {str(label).lower() for label in labels_value}
            if isinstance(labels_value, list)
            else set()
        )
        source_lane = str(row.get("_shadow_source_lane") or "active_inbox")
        tags: list[str] = []
        if labels.intersection({"archived", "archive", "done", "trash", "spam", "draft"}):
            # Subject keywords survive after work is handled. An explicit
            # inactive lifecycle label outranks those keywords.
            return kind, tags
        if source_lane == "sent_follow_up":
            if kind == "human_or_other" and "sent" in labels:
                tags.append("waiting_reply")
            return kind, tags
        if "inbox" not in labels:
            # Gmail represents archive as absence of INBOX. Even though the
            # lane requested INBOX, a contradictory/missing lifecycle row is
            # not elevated.
            return kind, tags
        if any(
            token in combined
            for token in (
                "order",
                "return",
                "refund",
                "shipment",
                "shipping",
                "tracking",
                "delivery",
                "rma",
            )
        ):
            tags.append("order_return")
        if any(
            token in combined
            for token in (
                "deadline",
                "due",
                "renewal",
                "registration",
                "license",
                "invoice",
                "bill",
                "payment",
                "action required",
                "overdue",
                "expires",
            )
        ):
            tags.append("obligation")
        if any(
            token in combined
            for token in (
                "calendar",
                "appointment",
                "meeting",
                "lesson",
                "schedule",
                "booking",
                "reservation",
            )
        ):
            tags.append("calendar")
        if kind == "human_or_other" and "inbox" in labels:
            tags.append("reply")
        # "Waiting on your response" in an incoming unread message asks Leo to
        # reply; it does not prove that Leo sent the last message. Only a sent
        # thread is admitted to the waiting-on-someone category, then the exact
        # thread read below verifies direction.
        if kind == "human_or_other" and "sent" in labels:
            tags.append("waiting_reply")
        if any(token in combined for token in ("urgent", "today", "immediately", "asap")):
            tags.append("urgent")
        if acting_email == SNOWCUBES_BUSINESS_MAIL and kind == "human_or_other" and "inbox" in labels:
            tags.append("proactive")
        return kind, list(dict.fromkeys(tags))

    def proposal_for_tags(tags: Any) -> str:
        tag_set = {str(tag) for tag in (tags or [])}
        if "order_return" in tag_set:
            return "Proposal only: verify the order, return, refund, and deadline facts before any merchant action."
        if tag_set.intersection({"reply", "waiting_reply"}):
            return "Proposal only: read the exact thread and prepare a reply for Leo to approve; no draft or send was created."
        if "calendar" in tag_set:
            return "Proposal only: reconcile the exact interval and conflicts before any calendar write or invitation."
        return "Proposal only: read the exact source before deciding whether follow-through is needed."

    def stable_signal(row: dict[str, Any], acting_email: str) -> dict[str, Any]:
        thread_id = str(row.get("thread_id") or row.get("id") or "").strip()
        message_id = str(row.get("last_message_id") or "").strip()
        if message_id:
            stable_source = f"message:{message_id}"
        elif thread_id:
            # Thread IDs are only known to be stable within the acting
            # account. Cross-account dedupe requires last_message_id.
            stable_source = f"thread:{acting_email}:{thread_id}"
        else:
            stable_source = "fallback:" + "|".join(
                (
                    acting_email,
                    normalized_subject(row.get("subject")),
                    normalized_message_time(row.get("last_message_at")),
                )
            )
        signal_id = hashlib.sha256(stable_source.encode("utf-8")).hexdigest()[:24]
        kind, tags = action_tags(row, acting_email)
        stable_provider_identity = bool(message_id or thread_id)
        result = {
            "signal_id": signal_id,
            "subject": str(row.get("subject") or "")[:160],
            "last_message_at": str(row.get("last_message_at") or ""),
            "kind": kind,
            "action_tags": tags,
            "thread_id": thread_id or None,
            "last_message_id": message_id or None,
            "stable_provider_identity": stable_provider_identity,
            "source_labels": sorted(
                {str(label).lower() for label in row.get("labels")}
                if isinstance(row.get("labels"), list)
                else set()
            ),
            "source_lanes": [str(row.get("_shadow_source_lane") or "unknown")],
            "_identity_fingerprint": (
                normalized_subject(row.get("subject")),
                normalized_message_time(row.get("last_message_at")),
            ),
            "unread": "unread" in {str(label).lower() for label in (row.get("labels") or [])},
            "source_identities": [acting_email],
            "source_threads": [
                {
                    "acting_email": acting_email,
                    "thread_id": thread_id or None,
                    "last_message_id": message_id or None,
                }
            ],
            "semantic_status": "OBSERVED" if not tags else "UNKNOWN",
            "fail_closed_reasons": [],
            "confidence": "LOW" if tags else "MEDIUM",
            "source_observed_at": end_date,
            "source_age_hours": 0.0,
            "message_age_hours": source_age(row.get("last_message_at")),
            "proposal": proposal_for_tags(tags),
            "proposal_only": True,
        }
        if not stable_provider_identity:
            result["semantic_status"] = "UNKNOWN"
            result["confidence"] = "LOW"
            result["wake"] = (
                f"Open Superhuman as {acting_email} and recover a stable provider identity for this candidate; "
                "the account-scoped fallback was not merged and no action was performed."
            )
            result["fail_closed_reasons"].append("stable provider identity unavailable")
        return result

    def merge_signal(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
        existing_status = str(existing.get("semantic_status") or "UNKNOWN")
        incoming_status = str(incoming.get("semantic_status") or "UNKNOWN")
        existing["source_identities"] = sorted(
            dict.fromkeys(
                (existing.get("source_identities") or [])
                + (incoming.get("source_identities") or [])
            ),
            key=identity_sort_key,
        )
        seen_refs = {
            (
                ref.get("acting_email"),
                ref.get("thread_id"),
                ref.get("last_message_id"),
            )
            for ref in (existing.get("source_threads") or [])
            if isinstance(ref, dict)
        }
        for ref in incoming.get("source_threads") or []:
            if not isinstance(ref, dict):
                continue
            key = (ref.get("acting_email"), ref.get("thread_id"), ref.get("last_message_id"))
            if key not in seen_refs:
                existing.setdefault("source_threads", []).append(ref)
                seen_refs.add(key)
        existing["action_tags"] = sorted(
            dict.fromkeys(
                (existing.get("action_tags") or [])
                + (incoming.get("action_tags") or [])
            )
        )
        existing["source_labels"] = sorted(
            dict.fromkeys(
                (existing.get("source_labels") or [])
                + (incoming.get("source_labels") or [])
            )
        )
        existing["source_lanes"] = sorted(
            dict.fromkeys(
                (existing.get("source_lanes") or [])
                + (incoming.get("source_lanes") or [])
            )
        )
        existing["unread"] = bool(existing.get("unread") or incoming.get("unread"))
        snapshots = [
            snapshot
            for snapshot in (
                (existing.get("account_snapshots") or [])
                + (incoming.get("account_snapshots") or [])
            )
            if isinstance(snapshot, dict) and snapshot.get("acting_email")
        ]
        if snapshots:
            snapshots_by_identity = {
                str(snapshot["acting_email"]): snapshot for snapshot in snapshots
            }
            existing["account_snapshots"] = sorted(
                snapshots_by_identity.values(),
                key=lambda snapshot: identity_sort_key(
                    str(snapshot.get("acting_email") or "")
                ),
            )
            existing["thread_body_read"] = all(
                snapshot.get("thread_body_read") is True
                for snapshot in existing["account_snapshots"]
            )
            snapshot_identities = {
                str(snapshot.get("acting_email") or "")
                for snapshot in existing["account_snapshots"]
            }
            missing_snapshot_identities = sorted(
                set(existing.get("source_identities") or []) - snapshot_identities,
                key=identity_sort_key,
            )
            snapshot_statuses = {
                str(snapshot.get("semantic_status") or "UNKNOWN")
                for snapshot in existing["account_snapshots"]
            }
            known_statuses = snapshot_statuses.intersection(
                {"OBSERVED", "PROPOSAL"}
            )
            classification_conflict = known_statuses == {
                "OBSERVED",
                "PROPOSAL",
            }
            has_unknown = (
                bool(missing_snapshot_identities)
                or "UNKNOWN" in snapshot_statuses
                or bool(
                    snapshot_statuses
                    - {"UNKNOWN", "OBSERVED", "PROPOSAL"}
                )
            )
            if has_unknown or classification_conflict or not snapshot_statuses:
                existing["semantic_status"] = "UNKNOWN"
            elif len(known_statuses) == 1:
                existing["semantic_status"] = next(iter(known_statuses))
            else:
                existing["semantic_status"] = "UNKNOWN"
            snapshot_confidences = {
                str(snapshot.get("confidence") or "LOW")
                for snapshot in existing["account_snapshots"]
            }
            if existing["semantic_status"] == "UNKNOWN" or "LOW" in snapshot_confidences:
                existing["confidence"] = "LOW"
            elif "MEDIUM" in snapshot_confidences:
                existing["confidence"] = "MEDIUM"
            else:
                existing["confidence"] = "HIGH"
            existing["action_tags"] = sorted(
                {
                    str(tag)
                    for snapshot in existing["account_snapshots"]
                    for tag in (snapshot.get("action_tags") or [])
                }
            )
            existing["source_labels"] = sorted(
                {
                    str(label)
                    for snapshot in existing["account_snapshots"]
                    for label in (snapshot.get("source_labels") or [])
                }
            )
            existing["source_lanes"] = sorted(
                {
                    str(lane)
                    for snapshot in existing["account_snapshots"]
                    for lane in (snapshot.get("source_lanes") or [])
                }
            )
            existing["unread"] = any(
                snapshot.get("unread") is True
                for snapshot in existing["account_snapshots"]
            )
            reasons = {
                str(reason)
                for snapshot in existing["account_snapshots"]
                for reason in (snapshot.get("fail_closed_reasons") or [])
            }
            if missing_snapshot_identities:
                reasons.add("per-account classification snapshot unavailable")
            if classification_conflict:
                reasons.add("cross-account classification/lifecycle conflict")
            existing["fail_closed_reasons"] = sorted(reasons)
            wakes = {
                str(snapshot.get("wake"))
                for snapshot in existing["account_snapshots"]
                if snapshot.get("wake")
            }
            if missing_snapshot_identities:
                wakes.add(
                    "Re-read the exact mail item as "
                    + ", ".join(missing_snapshot_identities)
                    + "; its per-account classification snapshot is unavailable."
                )
            if classification_conflict:
                subject = str(existing.get("subject") or "this mail item")
                identities = ", ".join(existing.get("source_identities") or [])
                wakes.add(
                    f"Open Superhuman separately as {identities} and verify {subject}; "
                    "cross-account classification/lifecycle facts disagree, so no relationship action is inferred."
                )
            if wakes:
                existing["wake"] = "; ".join(sorted(wakes))
            else:
                existing.pop("wake", None)
        else:
            classification_conflict = {
                existing_status,
                incoming_status,
            } == {"OBSERVED", "PROPOSAL"}
            if "UNKNOWN" in {existing_status, incoming_status} or classification_conflict:
                existing["semantic_status"] = "UNKNOWN"
            elif existing_status == incoming_status:
                existing["semantic_status"] = existing_status
            else:
                existing["semantic_status"] = "UNKNOWN"
                classification_conflict = True
            if (
                existing.get("semantic_status") == "UNKNOWN"
                or incoming.get("confidence") == "LOW"
                or existing.get("confidence") == "LOW"
            ):
                existing["confidence"] = "LOW"
            existing["fail_closed_reasons"] = sorted(
                dict.fromkeys(
                    (existing.get("fail_closed_reasons") or [])
                    + (incoming.get("fail_closed_reasons") or [])
                    + (
                        ["cross-account classification/lifecycle conflict"]
                        if classification_conflict
                        else []
                    )
                )
            )
            wakes = {
                str(value)
                for value in (existing.get("wake"), incoming.get("wake"))
                if value
            }
            if wakes:
                existing["wake"] = "; ".join(sorted(wakes))
        existing["proposal"] = proposal_for_tags(existing.get("action_tags") or [])
        existing["source_threads"] = sorted(
            (existing.get("source_threads") or []),
            key=lambda ref: (
                identity_sort_key(str(ref.get("acting_email") or "")),
                str(ref.get("thread_id") or ""),
                str(ref.get("last_message_id") or ""),
            ),
        )
        if existing["source_threads"]:
            canonical_ref = existing["source_threads"][0]
            existing["thread_id"] = canonical_ref.get("thread_id")
            existing["last_message_id"] = canonical_ref.get("last_message_id")

    def dedupe_signal_rows(
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Dedupe only when provider identity and normalized facts agree."""
        buckets: dict[str, list[dict[str, Any]]] = {}
        for signal in rows:
            buckets.setdefault(str(signal.get("signal_id") or ""), []).append(signal)
        result: list[dict[str, Any]] = []
        collision_problems: list[str] = []
        for base_id, bucket in buckets.items():
            variants: dict[tuple[str, str], dict[str, Any]] = {}
            for signal in bucket:
                fingerprint = tuple(signal.get("_identity_fingerprint") or ("", ""))
                prior = variants.get(fingerprint)
                if prior is None:
                    variants[fingerprint] = signal
                else:
                    merge_signal(prior, signal)
            if len(variants) > 1:
                collision_problems.append(
                    f"provider-ID collision for {base_id}: normalized subject/time disagree"
                )
                for fingerprint, signal in variants.items():
                    refs = sorted(
                        (
                            str(ref.get("acting_email") or ""),
                            str(ref.get("thread_id") or ""),
                            str(ref.get("last_message_id") or ""),
                        )
                        for ref in (signal.get("source_threads") or [])
                        if isinstance(ref, dict)
                    )
                    collision_key = json.dumps(
                        [base_id, list(fingerprint), refs],
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    signal["signal_id"] = hashlib.sha256(
                        f"collision:{collision_key}".encode("utf-8")
                    ).hexdigest()[:24]
                    signal["semantic_status"] = "UNKNOWN"
                    signal["confidence"] = "LOW"
                    signal.setdefault("fail_closed_reasons", []).append(
                        "provider-ID collision"
                    )
                    identities = ", ".join(signal.get("source_identities") or [])
                    thread_ids = ", ".join(
                        str(ref.get("thread_id") or "unknown thread")
                        for ref in (signal.get("source_threads") or [])
                    )
                    signal["wake"] = (
                        f"Open Superhuman as {identities} and verify exact thread {thread_ids}; "
                        "a provider-ID collision has conflicting normalized subject/time facts, so no rows were merged or acted on."
                    )
            result.extend(variants.values())
        return result, collision_problems

    def action_candidate_sort_key(signal: dict[str, Any]) -> tuple[int, float, str]:
        """Read and retain explicit/old obligations before generic inbox mail."""
        tags = set(signal.get("action_tags") or [])
        if tags.intersection({"obligation", "order_return", "calendar"}):
            priority = 0
        elif "urgent" in tags:
            priority = 1
        elif "waiting_reply" in tags:
            priority = 2
        elif "proactive" in tags:
            priority = 3
        else:
            priority = 4
        parsed = parsed_time(signal.get("last_message_at"))
        return (
            priority,
            parsed.timestamp() if parsed is not None else float("-inf"),
            str(signal.get("signal_id") or ""),
        )

    def append_signal_wake(signal: dict[str, Any], wake: str) -> None:
        wakes = [str(value) for value in (signal.get("wake"), wake) if value]
        signal["wake"] = "; ".join(dict.fromkeys(wakes))

    account_snapshot_fields = (
        "thread_id",
        "last_message_id",
        "action_tags",
        "source_labels",
        "source_lanes",
        "semantic_status",
        "confidence",
        "fail_closed_reasons",
        "wake",
        "thread_body_read",
        "waiting_direction",
        "message_age_hours",
        "verified_message_at",
        "unread",
        "proposal",
    )

    def account_snapshot(signal: dict[str, Any], acting_email: str) -> dict[str, Any]:
        snapshot: dict[str, Any] = {"acting_email": acting_email}
        for key in account_snapshot_fields:
            value = signal.get(key)
            snapshot[key] = list(value) if isinstance(value, list) else value
        return snapshot

    coverage: list[dict[str, Any]] = []
    all_signals: list[dict[str, Any]] = []
    calendar_proposals: list[dict[str, Any]] = []
    owned_sender_identities = {
        sender_identity
        for linked_account in linked_accounts
        for sender_identity in (linked_account.get("sender_identities") or [])
    }
    owned_sender_identity_complete = bool(linked_accounts) and all(
        bool(linked_account.get("sender_identity_complete"))
        for linked_account in linked_accounts
    )
    global_action_reads = 0
    global_action_limit_hit = False
    read_budget_hit = False
    linked_order = [account["acting_email"] for account in linked_accounts]
    for account in linked_accounts:
        acting_email = account["acting_email"]
        pages = 0
        raw_threads: list[dict[str, Any]] = []
        total_estimate: int | None = None
        exhausted = True
        pagination_truncated = False
        problems: list[str] = []
        lane_receipts: list[dict[str, Any]] = []
        duplicate_thread_ids: set[str] = set()
        duplicate_message_ids: set[str] = set()
        for lane_name, lane_labels in SUPERHUMAN_LIST_LANES:
            lane_pages = 0
            cursor: str | None = None
            seen_cursors: set[str] = set()
            seen_provider_rows: set[str] = set()
            seen_thread_ids: set[str] = set()
            seen_message_ids: set[str] = set()
            lane_estimate: int | None = None
            lane_exhausted = False
            lane_truncated = False
            while lane_pages < SUPERHUMAN_MAX_PAGES:
                if read_budget_exhausted():
                    read_budget_hit = True
                    lane_truncated = True
                    problems.append(
                        f"{lane_name}: global read budget exceeded the {SUPERHUMAN_READ_BUDGET_SECONDS}-second safety window"
                    )
                    break
                arguments: dict[str, Any] = {
                    "acting_email": acting_email,
                    "start_date": start_date,
                    "end_date": end_date,
                    "labels": list(lane_labels),
                    "limit": SUPERHUMAN_PAGE_LIMIT,
                    "sort": "newest",
                }
                if cursor:
                    arguments["cursor"] = cursor
                try:
                    page = call_tool("list_threads", arguments)
                    if not isinstance(page, dict):
                        raise RuntimeError("list_threads returned no structured payload")
                    if page.get("error"):
                        raise RuntimeError(str(page.get("error")))
                    if "threads" not in page:
                        raise RuntimeError("list_threads omitted the thread list")
                    rows = page.get("threads")
                    if not isinstance(rows, list):
                        raise RuntimeError("list_threads returned a malformed thread list")
                except Exception as exc:
                    preserve_assertion(exc)
                    problems.append(f"{lane_name} mail read failed: {exc}")
                    lane_truncated = True
                    break
                lane_pages += 1
                malformed_thread_rows = sum(
                    1 for row in rows if not isinstance(row, dict)
                )
                if malformed_thread_rows:
                    lane_truncated = True
                    problems.append(
                        f"{lane_name}: {malformed_thread_rows} unusable thread row"
                        + ("s" if malformed_thread_rows != 1 else "")
                        + " returned by list_threads"
                    )
                for provider_row in rows:
                    if not isinstance(provider_row, dict):
                        continue
                    row = dict(provider_row)
                    row["_shadow_source_lane"] = lane_name
                    message_id = str(row.get("last_message_id") or "").strip()
                    thread_id = str(row.get("thread_id") or row.get("id") or "").strip()
                    if thread_id:
                        provider_key = f"thread:{acting_email}:{thread_id}"
                    elif message_id:
                        provider_key = f"message:{message_id}"
                    else:
                        provider_key = "fallback:" + "|".join(
                            (
                                acting_email,
                                normalized_subject(row.get("subject")),
                                normalized_message_time(row.get("last_message_at")),
                            )
                        )
                    duplicate_reasons: list[str] = []
                    if thread_id and thread_id in seen_thread_ids:
                        duplicate_reasons.append(f"thread {thread_id}")
                    if message_id and message_id in seen_message_ids:
                        duplicate_reasons.append(f"message {message_id}")
                    if provider_key in seen_provider_rows and not duplicate_reasons:
                        duplicate_reasons.append(provider_key)
                    if duplicate_reasons:
                        lane_truncated = True
                        if thread_id and thread_id in seen_thread_ids:
                            duplicate_thread_ids.add(thread_id)
                        if message_id and message_id in seen_message_ids:
                            duplicate_message_ids.add(message_id)
                        problems.append(
                            f"{lane_name}: duplicate provider row "
                            + ", ".join(duplicate_reasons)
                            + " repeated across the paginated result"
                        )
                    else:
                        seen_provider_rows.add(provider_key)
                    if thread_id:
                        seen_thread_ids.add(thread_id)
                    if message_id:
                        seen_message_ids.add(message_id)
                    raw_threads.append(row)
                estimate = page.get("total_estimate")
                if isinstance(estimate, int) and estimate >= 0:
                    lane_estimate = max(lane_estimate or 0, estimate)
                if any(
                    bool(row.get("truncated"))
                    for row in rows
                    if isinstance(row, dict)
                ):
                    lane_truncated = True
                    problems.append(f"{lane_name}: thread result truncated")
                if bool(page.get("truncated")):
                    lane_truncated = True
                    problems.append(f"{lane_name}: page result truncated")
                maximum_rows = SUPERHUMAN_PAGE_LIMIT * SUPERHUMAN_MAX_PAGES
                if lane_estimate is not None and lane_estimate > maximum_rows:
                    lane_truncated = True
                    problems.append(
                        f"{lane_name}: declared total estimate {lane_estimate} exceeds the {maximum_rows}-row pagination safety bound"
                    )
                    break
                next_cursor = str(page.get("next_cursor") or "").strip()
                if not next_cursor:
                    lane_exhausted = True
                    break
                if next_cursor in seen_cursors:
                    lane_truncated = True
                    problems.append(
                        f"{lane_name}: pagination cursor cycle at {next_cursor}"
                    )
                    break
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            if not lane_exhausted and lane_pages >= SUPERHUMAN_MAX_PAGES:
                lane_truncated = True
                problems.append(
                    f"{lane_name}: pagination stopped at the {SUPERHUMAN_MAX_PAGES}-page safety cap"
                )
            if (
                lane_exhausted
                and lane_estimate is not None
                and lane_estimate > len(seen_provider_rows)
            ):
                lane_truncated = True
                problems.append(
                    f"{lane_name}: total estimate {lane_estimate} exceeds {len(seen_provider_rows)} unique exhausted thread rows"
                )
            pages += lane_pages
            if lane_estimate is not None:
                total_estimate = (total_estimate or 0) + lane_estimate
            exhausted = exhausted and lane_exhausted
            pagination_truncated = pagination_truncated or lane_truncated
            lane_receipts.append(
                {
                    "name": lane_name,
                    "labels": list(lane_labels),
                    "pages": lane_pages,
                    "exhausted": lane_exhausted,
                    "truncated": lane_truncated or not lane_exhausted,
                    "total_estimate": lane_estimate,
                    "unique_threads": len(seen_provider_rows),
                }
            )

        newest_source = max(
            (
                (parsed_time(row.get("last_message_at")), str(row.get("last_message_at") or ""))
                for row in raw_threads
                if parsed_time(row.get("last_message_at")) is not None
            ),
            default=(None, None),
            key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc),
        )[1]
        metrics = {
            "unread_threads": 0,
            "github_notification_threads": 0,
            "human_or_other_threads": 0,
            "cursor_limit_threads": 0,
        }
        account_signal_rows: list[dict[str, Any]] = []
        for row in raw_threads:
            signal = stable_signal(row, acting_email)
            if not isinstance(row.get("labels"), list):
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                signal["wake"] = (
                    f"Open Superhuman as {acting_email} and verify lifecycle labels for exact thread "
                    f"{signal.get('thread_id') or 'UNKNOWN'}; archived/done state is not inferred."
                )
                signal.setdefault("fail_closed_reasons", []).append(
                    "mail lifecycle labels are missing or malformed"
                )
                problems.append(
                    f"{signal.get('thread_id') or signal.get('signal_id')}: mail lifecycle labels are missing or malformed"
                )
            if (
                str(signal.get("thread_id") or "") in duplicate_thread_ids
                or str(signal.get("last_message_id") or "") in duplicate_message_ids
            ):
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                signal["wake"] = (
                    f"Open Superhuman as {acting_email} and verify duplicate exact thread "
                    f"{signal.get('thread_id') or 'UNKNOWN'}; a stable paginated snapshot was not observed."
                )
                signal.setdefault("fail_closed_reasons", []).append(
                    "duplicate provider row prevents a stable snapshot"
                )
            if parsed_time(row.get("last_message_at")) is None:
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                signal["wake"] = (
                    f"Open Superhuman as {acting_email} and verify the source timestamp for exact thread "
                    f"{signal.get('thread_id') or 'UNKNOWN'}; ordering, range membership, and forgotten age are not inferred."
                )
                problems.append(
                    f"{signal.get('thread_id') or signal.get('signal_id')}: unusable source timestamp"
                )
                signal.setdefault("fail_closed_reasons", []).append(
                    "unusable source timestamp"
                )
            labels = {str(label).lower() for label in (row.get("labels") or [])}
            if "unread" in labels:
                metrics["unread_threads"] += 1
            if signal["kind"] == "github":
                metrics["github_notification_threads"] += 1
            elif signal["kind"] == "human_or_other":
                metrics["human_or_other_threads"] += 1
            combined = f"{row.get('subject', '')} {row.get('snippet', '')}".lower()
            if "usage limit" in combined or "usage/spend limit" in combined:
                metrics["cursor_limit_threads"] += 1
            account_signal_rows.append(signal)

        account_signals, account_collision_problems = dedupe_signal_rows(account_signal_rows)
        problems.extend(account_collision_problems)
        for signal in account_signals:
            if not signal.get("stable_provider_identity"):
                problems.append("source row has no stable provider identity")

        action_candidates = sorted(
            (
                signal
                for signal in account_signals
                if signal.get("action_tags")
            ),
            key=action_candidate_sort_key,
        )
        for signal in action_candidates:
            if global_action_reads >= SUPERHUMAN_GLOBAL_ACTION_LIMIT:
                global_action_limit_hit = True
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                append_signal_wake(signal, (
                    f"Open Superhuman as {acting_email} and read exact thread {signal.get('thread_id') or 'UNKNOWN'}; "
                    f"the global {SUPERHUMAN_GLOBAL_ACTION_LIMIT}-thread exact thread read cap was reached and no action was performed."
                ))
                problems.append(
                    f"global exact thread read cap of {SUPERHUMAN_GLOBAL_ACTION_LIMIT} left action candidates unverified"
                )
                continue
            if read_budget_exhausted():
                read_budget_hit = True
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                append_signal_wake(signal, (
                    f"Open Superhuman as {acting_email} and read exact thread {signal.get('thread_id') or 'UNKNOWN'}; "
                    f"the {SUPERHUMAN_READ_BUDGET_SECONDS}-second read budget expired and no action was performed."
                ))
                problems.append(
                    f"global read budget exceeded the {SUPERHUMAN_READ_BUDGET_SECONDS}-second safety window"
                )
                continue
            thread_id = str(signal.get("thread_id") or "")
            if not thread_id:
                wake = (
                    f"Open Superhuman as {acting_email} and resolve the candidate without a stable thread ID; "
                    "no draft, send, calendar write, order, or return was performed."
                )
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                append_signal_wake(signal, wake)
                problems.append("action candidate has no stable thread ID")
                continue
            detail_problems: list[str] = []
            attachment_names: list[str] = []
            try:
                global_action_reads += 1
                detail = call_tool(
                    "get_thread",
                    {
                        "acting_email": acting_email,
                        "thread_id": thread_id,
                        "include_comments": False,
                        "include_drafts": False,
                        "message_limit": 100,
                    },
                )
                if not isinstance(detail, dict):
                    raise RuntimeError("get_thread returned no structured payload")
                if detail.get("error"):
                    raise RuntimeError(str(detail.get("error")))
                if str(detail.get("thread_id") or "") != thread_id:
                    detail_problems.append("exact thread identity mismatch")
                if detail.get("user_is_participant") is not True:
                    detail_problems.append(
                        "exact thread does not prove the acting user is a participant"
                    )
                messages = detail.get("messages") or []
                if not isinstance(messages, list):
                    messages = []
                    detail_problems.append("thread messages malformed")
                message_count = detail.get("message_count")
                if bool(detail.get("truncated")) or (
                    isinstance(message_count, int) and message_count > len(messages)
                ):
                    detail_problems.append("thread body truncated")
                if isinstance(message_count, int) and message_count > 0 and not messages:
                    detail_problems.append("thread body unavailable")
                visible_messages: list[dict[str, Any]] = []
                for message in messages:
                    if not isinstance(message, dict):
                        detail_problems.append("thread contains an unusable message row")
                        continue
                    message_labels = message.get("labels")
                    if not isinstance(message_labels, list):
                        detail_problems.append(
                            "thread message lifecycle labels are missing or malformed"
                        )
                        continue
                    if str(message.get("thread_id") or "") != thread_id:
                        detail_problems.append(
                            "thread contains a message from a different thread"
                        )
                        continue
                    if message.get("is_draft") is True or "draft" in {
                        str(label).casefold() for label in message_labels
                    }:
                        continue
                    visible_messages.append(message)
                    attachments = [
                        str(value)
                        for value in (message.get("attachments") or [])
                        if str(value or "").strip()
                    ]
                    attachment_names.extend(attachments)
                    if not str(message.get("body") or message.get("raw_html") or "").strip():
                        detail_problems.append("thread body unavailable")
                if not visible_messages:
                    detail_problems.append("no non-draft visible message")
                if attachment_names:
                    detail_problems.append("action-bearing attachment content unread")
                last_message: dict[str, Any] = {}
                listed_message_id = str(signal.get("last_message_id") or "")
                if visible_messages and listed_message_id:
                    matching = [
                        message
                        for message in visible_messages
                        if str(message.get("message_id") or "") == listed_message_id
                    ]
                    if len(matching) != 1:
                        detail_problems.append(
                            "listed latest message is unavailable in the exact thread read"
                        )
                    else:
                        last_message = matching[0]
                        listed_time = parsed_time(
                            last_message.get("sent_at") or last_message.get("timestamp")
                        )
                        if listed_time is not None and any(
                            (
                                parsed_time(message.get("sent_at") or message.get("timestamp"))
                                or datetime.min.replace(tzinfo=timezone.utc)
                            )
                            > listed_time
                            for message in visible_messages
                            if message is not last_message
                        ):
                            detail_problems.append(
                                "listed latest message conflicts with exact thread ordering"
                            )
                elif visible_messages:
                    timestamped = [
                        (
                            parsed_time(message.get("sent_at") or message.get("timestamp")),
                            index,
                            message,
                        )
                        for index, message in enumerate(visible_messages)
                    ]
                    if any(item[0] is None for item in timestamped):
                        detail_problems.append(
                            "latest message ordering is ambiguous without a summary message ID"
                        )
                    else:
                        latest_time = max(item[0] for item in timestamped)
                        latest_rows = [
                            item for item in timestamped if item[0] == latest_time
                        ]
                        if len(latest_rows) != 1:
                            detail_problems.append(
                                "latest message ordering is ambiguous because timestamps tie"
                            )
                        else:
                            last_message = latest_rows[0][2]
                if not last_message:
                    signal["action_tags"] = [
                        tag
                        for tag in (signal.get("action_tags") or [])
                        if tag not in {"reply", "waiting_reply", "proactive"}
                    ]
                else:
                    exact_message_time = parsed_time(
                        last_message.get("sent_at") or last_message.get("timestamp")
                    )
                    summary_message_time = parsed_time(signal.get("last_message_at"))
                    if exact_message_time is None:
                        detail_problems.append(
                            "latest exact message timestamp is unavailable or ambiguous"
                        )
                        signal["message_age_hours"] = None
                    elif summary_message_time is None:
                        signal["message_age_hours"] = None
                    elif exact_message_time != summary_message_time:
                        detail_problems.append(
                            "latest exact message timestamp disagrees with the thread summary"
                        )
                        signal["message_age_hours"] = None
                    else:
                        signal["message_age_hours"] = source_age(
                            exact_message_time.isoformat(timespec="seconds")
                        )
                        signal["verified_message_at"] = exact_message_time.isoformat(
                            timespec="seconds"
                        )
                    sender_email = message_identity(
                        last_message.get("from") or last_message.get("sender")
                    )
                    if not sender_email:
                        detail_problems.append("latest message sender identity is unavailable")
                    elif signal.get("kind") == "human_or_other":
                        tags = list(signal.get("action_tags") or [])
                        active_labels = set(signal.get("source_labels") or [])
                        recipients = message_recipients(last_message)
                        if sender_email in owned_sender_identities:
                            tags = [
                                tag
                                for tag in tags
                                if tag not in {"reply", "proactive"}
                            ]
                            outbound_text = " ".join(
                                str(last_message.get(key) or "")
                                for key in ("subject", "snippet", "body")
                            ).casefold()
                            expects_response = "?" in outbound_text or any(
                                token in outbound_text
                                for token in (
                                    "could you",
                                    "can you",
                                    "please",
                                    "let me know",
                                    "awaiting",
                                    "waiting for",
                                    "following up",
                                    "checking in",
                                    "your response",
                                    "what is the status",
                                )
                            )
                            internal_delivery = bool(recipients) and recipients.issubset(
                                owned_sender_identities
                            )
                            if not recipients:
                                tags = [tag for tag in tags if tag != "waiting_reply"]
                                detail_problems.append(
                                    "latest owned-sender message has no proven recipients"
                                )
                                signal["waiting_direction"] = (
                                    "latest visible message is owned, but its recipients are unavailable"
                                )
                            elif internal_delivery:
                                tags = [tag for tag in tags if tag != "waiting_reply"]
                            elif expects_response and "waiting_reply" not in tags:
                                tags.append("waiting_reply")
                            elif not expects_response:
                                tags = [tag for tag in tags if tag != "waiting_reply"]
                            if not recipients:
                                pass
                            elif internal_delivery:
                                signal["waiting_direction"] = (
                                    "latest visible message stayed within Leo-owned linked identities"
                                )
                            else:
                                signal["waiting_direction"] = (
                                    "last visible message sent by Leo with an explicit response expectation"
                                    if expects_response
                                    else "last visible message sent by Leo without a response expectation"
                                )
                        else:
                            if not owned_sender_identity_complete:
                                detail_problems.append(
                                    "send-as alias coverage is unavailable, so inbound/outbound direction is ambiguous"
                                )
                            tags = [tag for tag in tags if tag != "waiting_reply"]
                            if "inbox" in active_labels and "reply" not in tags:
                                tags.append("reply")
                            signal["waiting_direction"] = (
                                "latest visible message is inbound; Leo is not waiting on them"
                            )
                        signal["action_tags"] = list(dict.fromkeys(tags))
            except Exception as exc:
                preserve_assertion(exc)
                detail_problems.append(f"exact thread read failed: {exc}")
            signal["proposal"] = proposal_for_tags(signal.get("action_tags") or [])
            if detail_problems:
                attachment_note = (
                    " including " + ", ".join(sorted(dict.fromkeys(attachment_names)))
                    if attachment_names
                    else ""
                )
                signal["semantic_status"] = "UNKNOWN"
                signal["confidence"] = "LOW"
                append_signal_wake(signal, (
                    f"Open Superhuman as {acting_email}, read exact thread {thread_id}{attachment_note} and every "
                    "action-bearing attachment, then return a proposal; no draft, send, calendar write, order, or return was performed."
                ))
                signal.setdefault("fail_closed_reasons", []).extend(
                    str(problem) for problem in dict.fromkeys(detail_problems)
                )
                problems.extend(f"{thread_id}: {problem}" for problem in dict.fromkeys(detail_problems))
            else:
                signal["thread_body_read"] = True
                if signal.get("fail_closed_reasons"):
                    signal["semantic_status"] = "UNKNOWN"
                    signal["confidence"] = "LOW"
                elif not signal.get("action_tags"):
                    signal["semantic_status"] = "OBSERVED"
                    signal["confidence"] = "MEDIUM"
                else:
                    signal["semantic_status"] = "PROPOSAL"
                    signal["confidence"] = "MEDIUM"

        calendar: dict[str, Any]
        try:
            if read_budget_exhausted():
                read_budget_hit = True
                raise RuntimeError(
                    f"global read budget exceeded the {SUPERHUMAN_READ_BUDGET_SECONDS}-second safety window"
                )
            calendar_payload = call_tool(
                "query_email_and_calendar",
                {
                    "acting_email": acting_email,
                    "question": (
                        "Read only: for the next 14 days, summarize concrete calendar conflicts, deadlines, and "
                        "follow-through suggested by mail. Also search older accessible mail for unresolved "
                        "registration, driver license, payment, order, or return obligations predating the declared "
                        f"{SUPERHUMAN_LOOKBACK_DAYS}-day thread list; older hits are proposals, not exhaustive proof. "
                        "Return proposals only. Do not create, update, invite, "
                        "book, send, purchase, cancel, or change any account state."
                    ),
                },
            )
            if not isinstance(calendar_payload, dict):
                raise RuntimeError("calendar query returned no structured payload")
            if calendar_payload.get("error"):
                raise RuntimeError(str(calendar_payload.get("error")))
            if not str(calendar_payload.get("answer") or "").strip():
                raise RuntimeError("calendar query returned no answer")
            calendar_answer = str(calendar_payload.get("answer") or "")
            clarification = str(calendar_payload.get("clarification_needed") or "").strip()
            raw_sources = calendar_payload.get("sources")
            if not isinstance(raw_sources, list):
                raw_sources = []
            source_ids = [
                str(source.get("id"))
                for source in raw_sources
                if isinstance(source, dict) and source.get("id")
            ]
            calendar_problem = ""
            if clarification:
                calendar_problem = f"calendar query needs clarification: {clarification}"
            elif not source_ids:
                calendar_problem = "calendar query returned no source-labelled evidence"
            elif len(source_ids) != len(raw_sources):
                calendar_problem = "calendar query returned malformed source evidence"
            elif len(calendar_answer) > 1200:
                calendar_problem = (
                    "calendar answer exceeds the 1200-character reader evidence cap"
                )
            elif len(source_ids) > 20:
                calendar_problem = (
                    "calendar evidence exceeds the 20-source reader evidence cap"
                )
            calendar = {
                "status": "UNKNOWN" if calendar_problem else "PROPOSAL",
                "summary": calendar_answer[:1200],
                "source_ids": source_ids[:20],
                "clarification_needed": clarification or None,
                "proposal_only": True,
            }
            if calendar_problem:
                calendar["wake"] = (
                    f"Open read-only calendar evidence as {acting_email} and resolve: {calendar_problem}; "
                    "no event, invitation, booking, or notification was created."
                )
                problems.append(calendar_problem)
        except Exception as exc:
            preserve_assertion(exc)
            calendar = {
                "status": "UNKNOWN",
                "summary": "Calendar follow-through is unavailable; no event state or conflict is inferred.",
                "proposal_only": True,
                "wake": (
                    f"Restore read-only Superhuman calendar access for {acting_email}; no event write or invitation was attempted."
                ),
            }
            problems.append(f"calendar read failed: {exc}")
        calendar_proposals.append(
            {
                "acting_email": acting_email,
                "summary": calendar.get("summary"),
                "status": calendar.get("status"),
                "source_ids": calendar.get("source_ids") or [],
                "source_identities": [acting_email],
                "confidence": "MEDIUM" if calendar.get("status") == "PROPOSAL" else "LOW",
                "source_observed_at": end_date,
                "source_age_hours": 0.0,
                "wake": calendar.get("wake"),
                "proposal_only": True,
            }
        )

        status = "COMPLETE" if exhausted and not pagination_truncated and not problems else "UNKNOWN"
        coverage_row = {
            **account,
            "expected": acting_email in EXPECTED_SUPERHUMAN_IDENTITIES,
            "linked": True,
            "status": status,
            "query_range": dict(query_range),
            "source_observed_at": end_date,
            "source_age_hours": 0.0,
            "newest_message_at": newest_source,
            "newest_message_age_hours": source_age(newest_source),
            "threads_returned_raw": len(raw_threads),
            "threads_returned": len(account_signals),
            "total_estimate": total_estimate,
            "pagination": {
                "pages": pages,
                "exhausted": exhausted,
                "truncated": pagination_truncated or not exhausted,
                "lanes": lane_receipts,
            },
            "calendar": calendar,
            "problems": list(dict.fromkeys(problems)),
            "metrics": metrics,
        }
        if status == "UNKNOWN":
            if any("read budget" in problem for problem in problems):
                coverage_row["wake"] = (
                    f"Rerun read-only Superhuman coverage for {acting_email}; the "
                    f"{SUPERHUMAN_READ_BUDGET_SECONDS}-second read budget expired before this source was complete."
                )
            else:
                coverage_row["wake"] = (
                    f"Re-read {acting_email} through Superhuman from {start_date} to {end_date}, exhaust every cursor, "
                    "and open each named UNKNOWN thread before any all-clear."
                )
        for signal in account_signals:
            signal["account_snapshots"] = [account_snapshot(signal, acting_email)]
        coverage.append(coverage_row)
        all_signals.extend(account_signals)

    for expected_email in EXPECTED_SUPERHUMAN_IDENTITIES:
        if expected_email in linked_by_email:
            continue
        coverage.append(
            unknown_coverage(
                expected_email,
                expected=True,
                problem="expected identity is not linked in the live Superhuman account list",
                wake=(
                    f"Link {expected_email} in Superhuman, then rerun read-only list_accounts; "
                    "never reauthenticate or substitute another identity automatically."
                ),
            )
        )

    coverage.sort(
        key=lambda row: (
            EXPECTED_SUPERHUMAN_IDENTITIES.index(row["acting_email"])
            if row["acting_email"] in EXPECTED_SUPERHUMAN_IDENTITIES
            else len(EXPECTED_SUPERHUMAN_IDENTITIES),
            linked_order.index(row["acting_email"])
            if row["acting_email"] in linked_order
            else len(linked_order),
            row["acting_email"],
        )
    )
    deduped_rows, collision_problems = dedupe_signal_rows(all_signals)
    context_problems.extend(collision_problems)

    def signal_sort_key(signal: dict[str, Any]) -> tuple[float, str]:
        parsed = parsed_time(signal.get("last_message_at"))
        return (
            parsed.timestamp() if parsed is not None else float("-inf"),
            str(signal.get("signal_id") or ""),
        )

    unique_signals = sorted(deduped_rows, key=signal_sort_key, reverse=True)
    action_signals = sorted(
        (signal for signal in unique_signals if signal.get("action_tags")),
        key=action_candidate_sort_key,
    )
    neutral_signals = [signal for signal in unique_signals if not signal.get("action_tags")]
    # Preserve old obligations ahead of newer neutral mail. The packet stays
    # bounded, while each reader-first action category below is derived from
    # the full collision-safe set and carries its own cap/wake.
    retained_signals = (action_signals + neutral_signals)[:SUPERHUMAN_SIGNAL_LIMIT]
    for signal in unique_signals:
        if "provider-ID collision" not in str(signal.get("wake") or ""):
            continue
        for acting_email in signal.get("source_identities") or []:
            coverage_row = next(
                (row for row in coverage if row.get("acting_email") == acting_email),
                None,
            )
            if coverage_row is None:
                continue
            coverage_row["status"] = "UNKNOWN"
            coverage_row.setdefault("problems", []).append(
                "provider-ID collision requires exact thread verification"
            )
            coverage_row["wake"] = signal.get("wake")

    calendar_by_key: dict[tuple[str, tuple[str, ...], str, str], dict[str, Any]] = {}
    for proposal in calendar_proposals:
        key = (
            normalized_subject(proposal.get("summary")),
            tuple(sorted(str(value) for value in (proposal.get("source_ids") or []))),
            str(proposal.get("status") or "UNKNOWN"),
            str(proposal.get("wake") or ""),
        )
        prior = calendar_by_key.get(key)
        if prior is None:
            calendar_by_key[key] = proposal
            continue
        prior["source_identities"] = sorted(
            dict.fromkeys(
                (prior.get("source_identities") or [])
                + (proposal.get("source_identities") or [])
            ),
            key=identity_sort_key,
        )
    calendar_proposals = sorted(
        calendar_by_key.values(),
        key=lambda row: tuple(
            identity_sort_key(value) for value in row.get("source_identities") or []
        ),
    )
    category_omissions: dict[str, int] = {}

    def categorize(name: str, predicate: Any) -> list[dict[str, Any]]:
        # Classify from the FULL collision-safe set, never from the retention
        # sample: the sample is ordered action-first, so once action-tagged
        # signals exceed SUPERHUMAN_SIGNAL_LIMIT the tail is real obligations.
        # Order by action-candidate priority (obligation class first, then
        # ascending timestamp) before capping: unique_signals is
        # reverse-chronological, so a raw slice would drop the
        # longest-neglected rows this section exists to surface.
        matched = sorted(
            (signal for signal in unique_signals if predicate(signal)),
            key=action_candidate_sort_key,
        )
        if len(matched) > SUPERHUMAN_CATEGORY_LIMIT:
            category_omissions[name] = len(matched) - SUPERHUMAN_CATEGORY_LIMIT
        return matched[:SUPERHUMAN_CATEGORY_LIMIT]

    def tagged(signal: dict[str, Any], *tags: str) -> bool:
        return any(tag in (signal.get("action_tags") or []) for tag in tags)

    forgotten = categorize(
        "forgotten_obligations",
        lambda signal: (source_age(signal.get("last_message_at")) or 0) > 24
        and tagged(signal, "obligation", "order_return", "waiting_reply", "reply", "calendar"),
    )
    order_returns = categorize(
        "order_return_follow_up", lambda signal: tagged(signal, "order_return")
    )
    waiting_replies = categorize(
        "waiting_replies", lambda signal: tagged(signal, "waiting_reply")
    )
    urgent_replies = categorize(
        "urgent_replies",
        lambda signal: tagged(signal, "urgent") and tagged(signal, "reply", "waiting_reply"),
    )
    proactive = categorize("proactive_candidates", lambda signal: tagged(signal, "proactive"))
    metrics = {
        key: sum(int((row.get("metrics") or {}).get(key) or 0) for row in coverage)
        for key in (
            "unread_threads",
            "github_notification_threads",
            "human_or_other_threads",
            "cursor_limit_threads",
        )
    }
    declared_query_complete = bool(coverage) and all(
        row.get("status") == "COMPLETE" for row in coverage
    )
    if global_action_limit_hit:
        context_problems.append(
            f"global exact thread read cap of {SUPERHUMAN_GLOBAL_ACTION_LIMIT} left candidates unverified"
        )
        context_wakes.append(
            "Open each signal named as skipped by the global exact thread read cap before relying on the brief."
        )
    if read_budget_hit:
        context_problems.append(
            f"global read budget exceeded the {SUPERHUMAN_READ_BUDGET_SECONDS}-second safety window"
        )
        context_wakes.append(
            f"Rerun the read-only collector with enough time to finish before the next verifier; the {SUPERHUMAN_READ_BUDGET_SECONDS}-second read budget stopped this pass."
        )
    signals_omitted = max(0, len(unique_signals) - len(retained_signals))
    if signals_omitted:
        context_problems.append(
            f"{signals_omitted} signal omitted by the {SUPERHUMAN_SIGNAL_LIMIT}-signal retention cap"
        )
        context_wakes.append(
            f"Re-open the private packet and narrow the source read below the {SUPERHUMAN_SIGNAL_LIMIT}-signal retention cap before relying on an all-clear."
        )
    for category, omitted in sorted(category_omissions.items()):
        context_problems.append(
            f"{omitted} {category.replace('_', ' ')} row omitted by the "
            f"{SUPERHUMAN_CATEGORY_LIMIT}-row category cap"
        )
        context_wakes.append(
            f"Read the remaining {omitted} {category.replace('_', ' ')} row directly in "
            f"Superhuman; the {SUPERHUMAN_CATEGORY_LIMIT}-row category cap truncated this section."
        )
    forgotten_horizon = {
        "status": "UNKNOWN",
        "declared_thread_start": start_date,
        "proposal_only": True,
        "wake": (
            f"Search read-only Superhuman mail before {start_date[:10]} for unresolved registration, driver license, "
            "payment, order, and return obligations; the 90-day paginated query is exhausted only for its declared range."
        ),
    }
    context_problems.append(
        f"forgotten-obligation history before {start_date[:10]} is not proven exhaustive"
    )
    context_wakes.append(forgotten_horizon["wake"])
    semantic_unknown = any(
        signal.get("semantic_status") == "UNKNOWN" for signal in unique_signals
    )
    complete = declared_query_complete and not context_problems and not semantic_unknown
    all_clear_allowed = complete
    for signal in unique_signals:
        signal.pop("_identity_fingerprint", None)
    return {
        "schema": SUPERHUMAN_CONTEXT_SCHEMA,
        "available": bool(linked_accounts),
        "complete": complete,
        "status": "COMPLETE" if complete else "UNKNOWN",
        "all_clear_allowed": all_clear_allowed,
        "declared_query_complete": declared_query_complete,
        "problems": list(dict.fromkeys(context_problems)),
        "wake": "; ".join(dict.fromkeys(context_wakes)),
        "observed_at": end_date,
        "query_range": query_range,
        "expected_identities": list(EXPECTED_SUPERHUMAN_IDENTITIES),
        "account_discovery": account_discovery,
        "linked_accounts": linked_accounts,
        "coverage": coverage,
        "threads_returned_raw": sum(int(row.get("threads_returned_raw") or 0) for row in coverage),
        "threads_returned": sum(int(row.get("threads_returned") or 0) for row in coverage),
        "threads_unique": len(unique_signals),
        "signals_retained": len(retained_signals),
        "signals_omitted": signals_omitted,
        "signals": retained_signals,
        "forgotten_obligations": forgotten,
        "urgent_replies": urgent_replies,
        "waiting_replies": waiting_replies,
        "proactive_candidates": proactive,
        "order_return_follow_up": order_returns,
        "calendar_proposals": calendar_proposals,
        "forgotten_horizon": forgotten_horizon,
        "window_hours": SUPERHUMAN_LOOKBACK_DAYS * 24,
        **metrics,
    }


def superhuman_account_context(context: dict[str, Any], acting_email: str) -> dict[str, Any]:
    """Project one account from the all-account read without another provider call."""
    normalized = str(acting_email or "").strip().lower()
    if context.get("acting_email") == normalized and "coverage" not in context:
        return context
    coverage = next(
        (
            row
            for row in (context.get("coverage") or [])
            if isinstance(row, dict) and row.get("acting_email") == normalized
        ),
        None,
    )
    if coverage is None:
        return {
            "available": False,
            "complete": False,
            "status": "UNKNOWN",
            "acting_email": normalized,
            "error": "identity is absent from Superhuman coverage",
            "wake": f"Link {normalized} in Superhuman and rerun read-only list_accounts.",
            "signals": [],
        }
    signals: list[dict[str, Any]] = []
    for signal in context.get("signals") or []:
        if not isinstance(signal, dict) or normalized not in (signal.get("source_identities") or []):
            continue
        account_signal = dict(signal)
        source_ref = next(
            (
                ref
                for ref in (signal.get("source_threads") or [])
                if isinstance(ref, dict) and ref.get("acting_email") == normalized
            ),
            {},
        )
        snapshot = next(
            (
                item
                for item in (signal.get("account_snapshots") or [])
                if isinstance(item, dict) and item.get("acting_email") == normalized
            ),
            None,
        )
        if snapshot is None:
            account_signal["action_tags"] = []
            account_signal["semantic_status"] = "UNKNOWN"
            account_signal["confidence"] = "LOW"
            account_signal["fail_closed_reasons"] = [
                "per-account classification snapshot unavailable"
            ]
            account_signal["wake"] = (
                f"Re-read the exact mail item as {normalized}; its per-account classification snapshot is unavailable."
            )
            account_signal["thread_body_read"] = False
        else:
            for key in (
                "thread_id",
                "last_message_id",
                "action_tags",
                "source_labels",
                "source_lanes",
                "semantic_status",
                "confidence",
                "fail_closed_reasons",
                "wake",
                "thread_body_read",
                "waiting_direction",
                "message_age_hours",
                "verified_message_at",
                "unread",
                "proposal",
            ):
                value = snapshot.get(key)
                account_signal[key] = list(value) if isinstance(value, list) else value
        account_signal["thread_id"] = source_ref.get("thread_id") or account_signal.get("thread_id")
        account_signal["last_message_id"] = source_ref.get("last_message_id") or account_signal.get("last_message_id")
        account_signal["source_identities"] = [normalized]
        account_signal["source_threads"] = [source_ref] if source_ref else []
        account_signal.pop("native_link", None)
        signals.append(account_signal)
    metrics = coverage.get("metrics") or {}
    available = bool(coverage.get("linked"))
    result = {
        "available": available,
        "complete": coverage.get("status") == "COMPLETE",
        "status": coverage.get("status"),
        "acting_email": normalized,
        "window_hours": SUPERHUMAN_LOOKBACK_DAYS * 24,
        "query_range": coverage.get("query_range"),
        "source_age_hours": coverage.get("source_age_hours"),
        "threads_returned": coverage.get("threads_returned", 0),
        "total_estimate": coverage.get("total_estimate"),
        "unread_threads": metrics.get("unread_threads", 0),
        "github_notification_threads": metrics.get("github_notification_threads", 0),
        "human_or_other_threads": metrics.get("human_or_other_threads", 0),
        "cursor_limit_threads": metrics.get("cursor_limit_threads", 0),
        "signals": signals,
    }
    if not available or coverage.get("status") != "COMPLETE":
        result["error"] = "; ".join(str(value) for value in (coverage.get("problems") or [])) or "coverage unknown"
        result["wake"] = coverage.get("wake")
    return result


def collect_superhuman_context(*, acting_email: str | None = None) -> dict[str, Any]:
    """Collect every linked account once, returning only metadata and proposals."""
    import urllib.error
    import urllib.request

    token = _mcp_remote_token()
    if not token:
        def unavailable(_name: str, _arguments: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("Superhuman OAuth is unavailable")

        context = build_superhuman_context(unavailable)
        return superhuman_account_context(context, acting_email) if acting_email else context
    url = SUPERHUMAN_MCP_RESOURCE

    def post(payload: dict[str, Any], sid: str | None = None) -> tuple[str | None, dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if sid:
            headers["mcp-session-id"] = sid
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            next_sid = response.headers.get("mcp-session-id") or sid
            return next_sid, _parse_mcp_sse(response.read().decode("utf-8", errors="replace"))

    try:
        sid, _ = post({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "shadow-brief-context", "version": "1.0"},
            },
        })
        post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        def failed(_name: str, _arguments: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError(f"Superhuman session initialization failed: {exc}")

        context = build_superhuman_context(failed)
        return superhuman_account_context(context, acting_email) if acting_email else context

    request_id = 2

    def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id, sid
        current_id = request_id
        request_id += 1
        sid, result = post(
            {
                "jsonrpc": "2.0",
                "id": current_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            sid,
        )
        if result.get("error"):
            error = result.get("error")
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"{name} failed: {message}")
        payload = _mcp_text_payload(result)
        if not isinstance(payload, dict):
            raise RuntimeError(f"{name} returned no structured payload")
        return payload

    context = build_superhuman_context(call_tool)
    return superhuman_account_context(context, acting_email) if acting_email else context


def _snowcubes_surface(
    *,
    name: str,
    state: str,
    now: str,
    next_action: str,
    source: str,
    observed_at: str,
    wake: str | None = None,
    native_link: str | None = None,
    proposal: str | None = None,
) -> dict[str, Any]:
    """Create one source-labelled card without creating a task or business record."""
    card: dict[str, Any] = {
        "name": name,
        "state": state,
        "now": now,
        "next": next_action,
        "source": source,
        "observed_at": observed_at,
    }
    if wake:
        card["wake"] = wake
    if native_link:
        card["native_link"] = native_link
    if proposal:
        card["proposal"] = proposal
    return card


def _snowcubes_vercel_surface(vercel: dict[str, Any], observed_at: str) -> dict[str, Any]:
    rows = [
        row
        for row in (vercel.get("deployments") or [])
        if isinstance(row, dict)
        and "snowcube" in str(row.get("name") or "").lower()
    ]
    if not vercel.get("available"):
        return _snowcubes_surface(
            name="Deploy",
            state="unavailable",
            now="No current deployment fact is claimed.",
            next_action="Reconcile the Snowcubes deployment from the provider before calling the storefront live.",
            source="Vercel",
            observed_at=observed_at,
            wake="Authenticate the Vercel CLI, then run the next natural morning window; no deploy is started by this brief.",
            native_link=SNOWCUBES_NATIVE_LINKS["deploy"],
        )
    if not rows:
        return _snowcubes_surface(
            name="Deploy",
            state="unavailable",
            now="Vercel was read, but no Snowcubes project was identified in the bounded result.",
            next_action="Confirm the exact Snowcubes Vercel project identity before treating a deployment as live.",
            source="Vercel",
            observed_at=observed_at,
            wake="Name or authorize the Snowcubes Vercel project for the read-only producer; the next natural window will retry.",
            native_link=SNOWCUBES_NATIVE_LINKS["deploy"],
        )
    states = ", ".join(
        f"{row.get('name')}: {row.get('state') or 'unknown'}"
        for row in rows[:3]
    )
    link = next(
        (
            str(row.get("url"))
            for row in rows
            if str(row.get("url") or "").startswith(("https://", "http://"))
        ),
        SNOWCUBES_NATIVE_LINKS["deploy"],
    )
    return _snowcubes_surface(
        name="Deploy",
        state="available",
        now=f"Vercel read completed for the identified Snowcubes project: {states}.",
        next_action="Open the native deployment receipt before claiming the public storefront is shipped.",
        source="Vercel",
        observed_at=observed_at,
        native_link=link,
    )


def _snowcubes_m12_surface(observed_at: str) -> dict[str, Any]:
    repo = portfolio_root() / "trysnowcubes-web"
    script = repo / "scripts" / "cafe-doctor.py"
    fixture = repo / "tests" / "fixtures" / "cafe-native-three-partner.json"
    if not script.is_file() or not fixture.is_file():
        return _snowcubes_surface(
            name="M12 cafe-doctor",
            state="unavailable",
            now="The cafe freshness packet is unavailable; no balance or collection fact is inferred.",
            next_action="Restore the canonical doctor and its bounded fresh-native fixture before any money action.",
            source="Snowcubes M12 cafe-doctor",
            observed_at=observed_at,
            wake="Restore the canonical cafe doctor and fresh-native fixture; the next natural window will retry.",
            native_link=SNOWCUBES_NATIVE_LINKS["m12"],
        )
    try:
        proc = _run([sys.executable, str(script), "--json", "--fresh-native", str(fixture)], cwd=repo, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _snowcubes_surface(
            name="M12 cafe-doctor",
            state="unavailable",
            now="The fresh-native verifier could not complete; no balance or collection fact is inferred.",
            next_action="Keep money actions suppressed until the bounded source verifier can be read again.",
            source="Snowcubes M12 cafe-doctor",
            observed_at=observed_at,
            wake=f"Run the bounded fresh-native verifier successfully ({exc}); no provider mutation is performed here.",
            native_link=SNOWCUBES_NATIVE_LINKS["m12"],
        )
    try:
        result = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        result = {}
    checks = result.get("checks") if isinstance(result, dict) else []
    fresh = next(
        (check for check in checks if isinstance(check, dict) and check.get("name") == "fresh-native"),
        None,
    )
    if not isinstance(result, dict) or fresh is None:
        detail = proc.stderr or "doctor did not return a fresh-native result"
        return _snowcubes_surface(
            name="M12 cafe-doctor",
            state="unavailable",
            now=f"The fresh-native packet is unavailable: {detail[:220]}. No balance or collection fact is inferred.",
            next_action="Keep money actions suppressed until the bounded source packet is available.",
            source="Snowcubes M12 cafe-doctor",
            observed_at=observed_at,
            wake="Restore the fresh-native packet and re-read it; no provider mutation is performed here.",
            native_link=SNOWCUBES_NATIVE_LINKS["m12"],
        )
    source_observed_at = fresh.get("observed_at")
    if not isinstance(source_observed_at, str) or not source_observed_at.endswith("Z"):
        return _snowcubes_surface(
            name="M12 cafe-doctor",
            state="unavailable",
            now="The fresh-native packet has no canonical source timestamp; no current money state is inferred.",
            next_action="Keep money actions suppressed until the source packet carries its observation time.",
            source="Snowcubes M12 cafe-doctor",
            observed_at=observed_at,
            wake="Regenerate the bounded fresh-native packet with its canonical source timestamp.",
            native_link=SNOWCUBES_NATIVE_LINKS["m12"],
        )
    wake = fresh.get("wake") if isinstance(fresh.get("wake"), str) else "Collect fresh read-only source observations before any money action."
    if not fresh.get("ok"):
        return _snowcubes_surface(
            name="M12 cafe-doctor",
            state="attention",
            now=f"The fresh-native verifier found a discrepancy: {str(fresh.get('detail') or 'unknown')[:220]}. Money actions remain suppressed.",
            next_action="Reconcile the named source disagreement before treating any cafe amount as current.",
            source="Snowcubes M12 cafe-doctor",
            observed_at=source_observed_at,
            wake=wake,
            native_link=SNOWCUBES_NATIVE_LINKS["m12"],
        )
    return _snowcubes_surface(
        name="M12 cafe-doctor",
        state="unavailable",
        now="The fresh-native verifier passed, but it is a safety fixture rather than a current provider read; no cafe balance is inferred.",
        next_action="Keep money actions suppressed until a current native Calendar, Superhuman, and Shopify packet exists.",
        source="Snowcubes M12 cafe-doctor",
        observed_at=source_observed_at,
        wake=wake,
        native_link=SNOWCUBES_NATIVE_LINKS["m12"],
    )


def collect_snowcubes_context(
    *,
    vercel: dict[str, Any] | None = None,
    board: dict[str, Any] | None = None,
    mail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read the bounded business-mail signal and name every missing authority.

    This is deliberately a companion inside the one Shadow producer: it is not
    a storefront mirror, customer database, or separate task queue.
    """
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mail = (
        mail
        if isinstance(mail, dict)
        else collect_superhuman_context(acting_email=SNOWCUBES_BUSINESS_MAIL)
    )
    newest: dict[str, Any] | None = None
    if mail.get("available"):
        human = [
            row
            for row in mail.get("signals") or []
            if row.get("kind") == "human_or_other"
        ]
        verified = [
            row
            for row in human
            if any(
                tag in (row.get("action_tags") or [])
                for tag in ("reply", "proactive")
            )
            and row.get("semantic_status") == "PROPOSAL"
            and row.get("thread_body_read") is True
            and mail.get("complete") is True
        ]
        newest = next(iter(verified), None)
        if newest:
            subject = str(newest.get("subject") or "the named Snowcubes mail item")
            reply = (
                f"Review first: {subject} is a verified active Snowcubes reply candidate in "
                f"{mail.get('acting_email') or SNOWCUBES_BUSINESS_MAIL}."
            )
            relationship = "Keep the next verified active relationship visible after this proposal."
            mail_state = "available"
            mail_wake = None
            proposal = (
                f"Proposal only: open Superhuman as {mail.get('acting_email') or SNOWCUBES_BUSINESS_MAIL}, "
                f"find {subject}, and prepare a reply for Leo to approve; no draft or send was created."
            )
        elif human and all(
            row.get("semantic_status") == "OBSERVED"
            and not row.get("action_tags")
            for row in human
        ) and mail.get("complete") is True:
            reply = "No active Snowcubes reply candidate was proven in the declared read."
            relationship = "No relationship follow-up is proposed from these neutral observations."
            mail_state = "available"
            mail_wake = None
            proposal = None
        elif human:
            candidate = next(
                (row for row in human if row.get("wake")),
                None,
            )
            reply = (
                "A possible human thread was read, but it is not ranked as a reply because "
                "active status, exact body coverage, or account coverage remains UNKNOWN."
            )
            relationship = "No relationship follow-up is inferred until the named mail evidence is verified."
            mail_state = "unknown"
            mail_wake = (
                reader_safe_mail_wake(candidate.get("wake"), row=candidate)
                if candidate
                else (
                    f"Open Superhuman as {mail.get('acting_email') or SNOWCUBES_BUSINESS_MAIL} and verify the named "
                    "candidate's lifecycle and exact body; do not infer an action from a provider ID."
                )
            )
            proposal = None
        else:
            reply = "No human correspondence was surfaced in the declared 90-day read."
            relationship = "No relationship follow-up is inferred from the bounded read."
            mail_state = "available" if mail.get("complete") is True else "unknown"
            mail_wake = (
                None
                if mail_state == "available"
                else "Complete the declared Snowcubes business-mail read before inferring correspondence state."
            )
            proposal = None
    else:
        reply = "Reply priority is unavailable; no inbox state is inferred."
        relationship = "Relationship follow-up is unavailable; no customer action is invented."
        mail_state = "unavailable"
        mail_wake = "Link trysnowcubes@gmail.com in Superhuman, then run the declared read-only 90-day thread query."
        proposal = None

    unavailable = {
        "Commerce": (
            "Shopify read-only order and fulfillment adapter is not configured for this producer.",
            "Authorize a read-only Shopify adapter for store 939cf1-24; the next natural window will read it.",
            "Shopify",
            "Link the Shopify Admin read-only adapter for store 939cf1-24; no Admin mutation is performed here.",
            "commerce",
        ),
        "Funnel": (
            "PostHog read-only Snowcubes project adapter is not configured for this producer.",
            "Authenticate the named PostHog project and read behavior in the next natural window.",
            "PostHog",
            "Authenticate the Snowcubes PostHog project for a read-only query; no event or property write is performed.",
            "funnel",
        ),
        "Search": (
            "Search Console read-only property adapter is not configured for this producer.",
            "Authenticate the canonical Search Console property and read current query coverage next window.",
            "Google Search Console",
            "Authorize the canonical Search Console property for read-only access; the brief never changes it.",
            "search",
        ),
        "Local profile": (
            "Google Business Profile read-only location adapter is not configured for this producer.",
            "Authenticate the Snowcubes location and read profile health next window.",
            "Google Business Profile",
            "Authorize the Snowcubes location in GBP for a read-only read; no profile edit or review reply is sent.",
            "local",
        ),
        "Lifecycle email": (
            "Resend/Supabase read-only lifecycle adapter is not configured for this producer.",
            "Read aggregate event and delivery health from Supabase/Resend next window.",
            "Supabase + Resend",
            "Authorize read-only Supabase/Resend project access; no campaign, draft, or send is created.",
            "lifecycle",
        ),
        "SEO": (
            "SEO acquisition read is not configured for this producer.",
            "Read the named SEO provider next window and keep acquisition separate from storefront truth.",
            "Ahrefs",
            "Authorize the Ahrefs read-only workspace; no keyword, backlink, or campaign mutation is performed.",
            "seo",
        ),
    }
    surfaces = [
        _snowcubes_surface(
            name="Reply and relationships",
            state=mail_state,
            now=reply,
            next_action=relationship,
            source="Superhuman business inbox (trysnowcubes@gmail.com)",
            observed_at=observed_at,
            wake=mail_wake,
            proposal=proposal,
        ),
        _snowcubes_surface(
            name="Relationships to nurture",
            state=mail_state,
            now=relationship,
            next_action=(
                "Keep the relationship visible after Leo reviews the reply-now item."
                if newest
                else "No relationship action is inferred until the business read proves an active candidate."
            ),
            source="Superhuman business inbox (trysnowcubes@gmail.com)",
            observed_at=observed_at,
            wake=mail_wake,
            proposal=(
                "Proposal only: after Leo approves the reply, keep a short personal follow-up in view; no draft or send was created."
                if mail_state == "available" and newest
                else None
            ),
        ),
        *[
            _snowcubes_surface(
                name=name,
                state="unavailable",
                now="No current business fact is claimed.",
                next_action=next_action,
                source=source,
                observed_at=observed_at,
                wake=wake,
                native_link=SNOWCUBES_NATIVE_LINKS[link_key],
            )
            for name, (reason, next_action, source, wake, link_key) in unavailable.items()
        ],
    ]
    # Shadow is the implementation authority for this companion; exposing its
    # revision is useful evidence, not a new Snowcubes queue.
    board = board if isinstance(board, dict) else collect_board()
    unavailable_plans = [
        entity
        for entity in (board.get("entities") or [])
        if isinstance(entity, dict) and entity.get("availability") == "unavailable"
    ]
    if board.get("revision") is not None and not unavailable_plans:
        surfaces.append(
            _snowcubes_surface(
                name="Shadow work",
                state="available",
                now=f"Shadow board revision {board.get('revision')} is the only execution authority; no duplicate Snowcubes queue is created.",
                next_action="Keep implementation claims on Shadow and the canonical Snowcubes PLAN; show receipts separately.",
                source="Shadow computer board",
                observed_at=observed_at,
                native_link=SNOWCUBES_NATIVE_LINKS["shadow"],
            )
        )
    elif board.get("revision") is not None:
        plan_names = ", ".join(
            str(entity.get("project") or "unknown") for entity in unavailable_plans[:3]
        )
        wakes = [str(entity.get("wake")) for entity in unavailable_plans if entity.get("wake")]
        surfaces.append(
            _snowcubes_surface(
                name="Shadow work",
                state="unavailable",
                now=(
                    f"Shadow board revision {board.get('revision')} was read, but "
                    f"{len(unavailable_plans)} plan source(s) are unavailable ({plan_names}); "
                    "no execution state is inferred for them."
                ),
                next_action="Restore the named local plan read; do not create a second queue.",
                source="Shadow computer board",
                observed_at=observed_at,
                wake="; ".join(dict.fromkeys(wakes)),
                native_link=SNOWCUBES_NATIVE_LINKS["shadow"],
            )
        )
    else:
        surfaces.append(
            _snowcubes_surface(
                name="Shadow work",
                state="unavailable",
                now="The Shadow board could not be read; no execution state is inferred.",
                next_action="Restore the local Shadow board read before ranking work.",
                source="Shadow computer board",
                observed_at=observed_at,
                wake="Run shadow status --by leo and repair the local board read; do not create a second queue.",
                native_link=SNOWCUBES_NATIVE_LINKS["shadow"],
            )
        )
    surfaces.append(_snowcubes_vercel_surface(vercel or {}, observed_at))
    surfaces.append(_snowcubes_m12_surface(observed_at))
    return {"observed_at": observed_at, "surfaces": surfaces}


def build_paint_health(
    github: list[dict[str, Any]],
    vercel: dict[str, Any],
    *,
    gh_installed: bool | None = None,
    vercel_installed: bool | None = None,
) -> dict[str, dict[str, Any]]:
    if gh_installed is None:
        gh_installed = shutil.which("gh") is not None
    if vercel_installed is None:
        vercel_installed = shutil.which("vercel") is not None

    github_error = next(
        (str(row.get("error")) for row in github if isinstance(row, dict) and row.get("error")),
        None,
    )
    if not gh_installed:
        github_health = {
            "available": False,
            "error": "GitHub CLI is not installed",
            "wake": "brew install gh && gh auth login",
        }
    elif github_error:
        github_health = {
            "available": False,
            "error": github_error,
            "wake": "gh auth status || gh auth login",
        }
    else:
        github_health = {"available": True}

    if not vercel_installed or not vercel.get("available"):
        vercel_health = {
            "available": False,
            "error": "Vercel CLI is not installed",
            "wake": "brew install vercel-cli && vercel login",
        }
    elif vercel.get("error"):
        vercel_health = {
            "available": False,
            "error": str(vercel["error"]),
            "wake": "vercel whoami || vercel login",
        }
    else:
        vercel_health = {"available": True}
    return {"github": github_health, "vercel": vercel_health}


def build_local_git_health(root: Path, repos: list[RepoPaint]) -> dict[str, Any]:
    if root.is_dir():
        return {"available": True, "scanned_roots": len(repos)}
    quoted_root = shlex.quote(str(root))
    return {
        "available": False,
        "scanned_roots": 0,
        "error": f"local Git portfolio root is unavailable: {root}",
        "wake": f"test -d {quoted_root} && python3 {shlex.quote(str(Path(__file__).resolve()))} collect",
    }


def build_recommendations(board: dict[str, Any], repos: list[RepoPaint]) -> list[Recommendation]:
    recs: list[Recommendation] = []
    all_entities = [row for row in (board.get("entities") or []) if isinstance(row, dict)]
    unavailable_entities = [
        row for row in all_entities if row.get("availability") == "unavailable"
    ]
    entities = [row for row in all_entities if row.get("availability") != "unavailable"]
    claims = board.get("claims") or []

    if unavailable_entities:
        count = len(unavailable_entities)
        recs.append(
            Recommendation(
                kind="challenge",
                text=(
                    f"{count} Shadow plan source{'s are' if count != 1 else ' is'} unavailable. "
                    "Portfolio priority and work totals are UNKNOWN until the named read wakes; "
                    "do not promote another project from this partial view."
                ),
                source="shadow-board",
            )
        )

    # Focus: live claim first (what this computer is already doing), else priority resume.
    claim_keys = _claim_index([c for c in claims if isinstance(c, dict)])
    ranked = sorted(
        entities,
        key=lambda e: (e.get("priority") is None, e.get("priority") or 99, e.get("project") or ""),
    )
    focus_ent = None
    focus_cp = None
    for ent in ranked:
        opens = ent.get("open_checkpoints") or []
        for cp in opens:
            if _claim_key_for(ent, cp) in claim_keys:
                focus_ent, focus_cp = ent, cp
                break
        if focus_ent:
            break
    if focus_ent is None and not unavailable_entities:
        for ent in ranked:
            opens = ent.get("open_checkpoints") or []
            if opens and ent.get("resume"):
                resume = str(ent.get("resume") or "").lstrip("~")
                focus_cp = next((c for c in opens if str(c.get("id")) == resume), opens[0])
                focus_ent = ent
                break
    if focus_ent and focus_cp:
        rid = str(focus_cp.get("id") or str(focus_ent.get("resume") or "").lstrip("~"))
        title = str(focus_cp.get("title") or "")
        if len(title) > 110:
            title = title[:107] + "…"
        recs.append(
            Recommendation(
                kind="focus",
                text=(
                    f"Keep visible owned work moving without calling it portfolio priority: "
                    f"{focus_ent.get('project')} — {title}"
                    if unavailable_entities
                    else f"Keep {focus_ent.get('project')} first: {title}"
                ),
                source="shadow-board",
            )
        )

    blocked_n = sum(len(e.get("blocked") or []) for e in entities)
    if blocked_n:
        recs.append(
            Recommendation(
                kind="challenge",
                text=(
                    f"{blocked_n} item{'s' if blocked_n != 1 else ''} cannot move yet. "
                    "Give each one a clear restart condition or drop it."
                ),
                source="shadow-board",
            )
        )

    dirty = [r for r in repos if r.dirty]
    if len(dirty) >= 5:
        recs.append(
            Recommendation(
                kind="streamline",
                text=(
                    f"{len(dirty)} projects have unfinished local changes. "
                    "Finish or park them before starting more work."
                ),
                source="local-git",
            )
        )

    stale = [r for r in repos if r.stale]
    if stale:
        names = ", ".join(r.name for r in stale[:3])
        extra = f" (+{len(stale) - 3} more)" if len(stale) > 3 else ""
        recs.append(
            Recommendation(
                kind="kill",
                text=(
                    f"{len(stale)} older workspaces still have changes. Decide what is worth keeping: "
                    f"{names}{extra}."
                ),
                source="local-git",
            )
        )

    forgotten = []
    for ent in entities:
        forgotten.extend(ent.get("forgotten") or [])
    if forgotten:
        recs.append(
            Recommendation(
                kind="unify",
                text=(
                    f"{len(forgotten)} older task{'s' if len(forgotten) != 1 else ''} "
                    "have lost a clear next move. Fold them into current work or leave them parked."
                ),
                source="shadow-board",
            )
        )

    if not claims and ranked and not unavailable_entities:
        recs.append(
            Recommendation(
                kind="focus",
                text=(
                    "Nothing is actively owned yet. Start the highest-value ready item "
                    "before opening more work."
                ),
                source="shadow-board",
            )
        )

    # Deduplicate by text; keep the first screen scannable.
    seen: set[str] = set()
    out: list[Recommendation] = []
    for rec in recs:
        if rec.text in seen:
            continue
        seen.add(rec.text)
        out.append(rec)
    return out[:6]


def human_project_label(value: Any) -> str:
    """Translate internal entity keys into stable reader-facing product names."""
    text = str(value or "This work").replace("_", " ").strip()
    lowered = text.lower()
    friendly = {
        "ai-leo": "Twice-daily report",
        "resplit-ios": "Resplit",
        "resplit-runner": "Resplit build service",
        "local workspaces": "Local work",
        "portfolio": "All products",
    }
    if lowered in friendly:
        return friendly[lowered]
    families = (
        (("snowcubes",), "Snowcubes"),
        (("resplit",), "Resplit"),
        (("strongyes",), "StrongYes"),
        (("shadow",), "Shadow"),
        (("takeoff",), "Takeoff"),
        (("vidux",), "Vidux"),
        (("moussey",), "Moussey"),
        (("pilot-puppy", "pilot puppy"), "Pilot Puppy"),
        (("ai-leo",), "Twice-daily report"),
        (("skill-education", "ai-skill-source", "skill source"), "Skill system"),
    )
    for needles, label in families:
        if any(needle in lowered for needle in needles):
            return label
    words = text.replace("-", " ").split()
    return " ".join("iOS" if word.lower() == "ios" else word.capitalize() for word in words)


def clean_change_subject(value: Any) -> str:
    """Turn a source-history subject into evidence prose without branch/row plumbing."""
    text = " ".join(str(value or "").replace("`", "").split())
    text = re.sub(r"^\d{4}-\d{2}-\d{2}T\S+\s+", "", text)
    text = re.sub(r"^(?:feat|fix|docs|test|refactor|perf|chore|build|ci)(?:\([^)]*\))?[!:]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:STRUCT|PROOF|DECISION|SUCCESSOR|CHECKPOINT)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"~[a-z0-9]{4}\b", "", text)
    text = re.sub(r"\s*\(#\d+\)\s*$", "", text)
    text = re.sub(r"\b(?:origin/main|plan-scale-live|HEAD)\b", "the current source", text, flags=re.IGNORECASE)
    replacements = {
        "root cas": "version guard",
        "root CAS": "version guard",
        "cmd proof": "automated proof",
        "plan tree": "large plan",
        "plan trees": "large plans",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    text = re.sub(r"\s+", " ", text).strip(" .:-")
    if not text:
        return "A source change was recorded"
    return text[0].upper() + text[1:]


def repo_project_label(value: Any) -> str:
    """Name a source repository as a product, not as an operating-plan entity."""
    lowered = str(value or "").lower()
    if "ai-leo" in lowered or "skill-source" in lowered:
        return "AI toolchain"
    if "expenses-web" in lowered:
        return "Expenses Web"
    return human_project_label(value)


def _change_theme(project: str, subjects: list[str]) -> tuple[str, str]:
    """Explain the product consequence of a bounded set of recent source facts."""
    raw = " ".join(subjects).lower()
    if "brief" in raw or "report" in raw or "digest" in raw:
        return (
            "The twice-daily brief is being rebuilt around judgment, not activity",
            "This is a trust repair. The useful outcome is not a prettier engineering inventory; it is a note that can explain what changed, what remains unproven, and where Leo’s attention changes the result.",
        )
    if project == "Expenses Web" and any(token in raw for token in ("switchboard", "weekly", "forecast", "backup")):
        return (
            "Expenses Web repaired the operating surface behind weekly planning",
            "The product consequence is a planning view that is less likely to omit money, lose older history, or collapse on a narrow screen. A fresh production read is still needed before that reliability can be called live.",
        )
    if project == "Resplit" and any(token in raw for token in ("defer", "wake", "admission", "cross-platform proof")):
        return (
            "Resplit’s Group Link work is waiting on real-device proof",
            "This is an honest stall at verification, not a new traveler-facing improvement. The lane needs a usable device and browser environment before the cross-platform promise can be closed.",
        )
    if project == "Takeoff" and "adoption" in raw:
        return (
            "Takeoff verified the Resplit web train at scale",
            "The run is strong evidence that the shared source train is internally coherent. It is not evidence that a traveler received or successfully used the resulting experience.",
        )
    if project == "AI toolchain" and any(token in raw for token in ("python 3.9", "xcb", "import")):
        return (
            "The local AI toolchain fixed a Python compatibility break",
            "This removes one failure mode from unattended local work. It matters operationally, but it should stay below customer-facing product changes unless it was blocking a named outcome.",
        )
    if project == "Shadow" and any(token in raw for token in ("configured upstream", "shared trunk", "local-only claim")):
        return (
            "Shadow is making multi-computer ownership safer",
            "The proposal gives a second computer a discoverable claim without pretending a local-only receipt is globally durable. Review and a real protected-trunk exercise still separate the design from proven coordination.",
        )
    if any(token in raw for token in ("plan tree", "partition", "shard", "large plan")):
        return (
            "Shadow made large operating plans readable again",
            "The change removes a scaling failure that could blank an entire project from status and reporting. It improves the coordination substrate; it does not by itself prove any product shipped.",
        )
    if "allergen" in raw:
        return (
            "Snowcubes closed a product-truth gap on food pages",
            "The meaningful improvement is customer safety and clarity: missing per-product data can no longer make a food page imply that no allergen risk exists.",
        )
    if "switchboard" in raw or "operator" in raw:
        return (
            "Snowcubes is making its operating view more trustworthy",
            "The point is faster, safer operating judgment—not another dashboard. The remaining proof is whether the live surface reflects the same facts the business actually uses.",
        )
    if "gift" in raw or "gifting" in raw:
        return (
            "Snowcubes is organizing discovery around how people actually shop",
            "This is a merchandising decision, not just navigation cleanup: gifting becomes the primary customer intent and narrower occasions sit beneath it.",
        )
    if any(token in raw for token in ("group link", "trip link", "shared trip")):
        return (
            "Resplit is hardening how people enter a shared trip",
            "The work matters only if access stays private and the join path remains understandable across real devices; source proof and released-device proof stay separate.",
        )
    if any(token in raw for token in ("lifecycle", "retention", "account deletion")):
        return (
            "Resplit is moving sensitive lifecycle rules to the server",
            "That reduces the chance that different clients silently disagree about deletion, expiry, or retention. It is risk reduction first; production behavior still needs its own readback.",
        )
    if any(token in raw for token in ("testflight", "app store", "release", "screenshot")):
        return (
            f"{project} tightened the path from source change to release evidence",
            "The improvement is a clearer proof boundary: source, review, deployment, and customer availability are reported separately instead of collapsing into ‘shipped.’",
        )
    if "backfill" in raw:
        return (
            f"{project} is closing visibility gaps across the portfolio",
            "This makes missing operating history explicit so future decisions do not mistake an empty view for no activity.",
        )
    if any(token in raw for token in ("security", "auth", "token", "permission")):
        return (
            f"{project} reduced an access-control risk",
            "The consequence is safer failure behavior. It should be treated as verified source work until the affected live path is exercised.",
        )
    if any(token in raw for token in ("cache", "stale")):
        return (
            f"{project} corrected stale customer-facing state",
            "The value is consistency between what was changed and what a person can actually see; deployment and live readback remain the deciding evidence.",
        )
    if any(token in raw for token in ("proof", "receipt", "test", "guard")):
        return (
            f"{project} strengthened what it can honestly call finished",
            "This is verification work. It lowers the chance of reporting a green check as customer-visible completion, but it is not itself a new customer feature.",
        )
    return (
        f"{project} moved in source, but the product consequence is still unclear",
        "The evidence shows related implementation or review activity, but not yet one coherent change a customer or operator can feel. This remains supporting evidence until that consequence is named and proved.",
    )


def _material_change_fact(project: str, subjects: list[str], reviews: list[str]) -> str:
    """Summarize the bounded source facts without publishing commit plumbing."""
    raw = " ".join(subjects + reviews).lower()
    if ("brief" in raw or "report" in raw or "digest" in raw) and any(
        token in raw for token in ("plan", "reader", "prose", "chief", "html")
    ):
        return (
            "The brief now keeps the full picture intact when a project is complex, and both editions "
            "follow the same clear, decision-focused standard."
        )
    if project == "Expenses Web" and any(token in raw for token in ("switchboard", "weekly", "forecast", "backup")):
        return (
            "The weekly planning view was restored and protected against a narrow-screen regression. "
            "Scheduled backups now include the older transaction store and continue through long result sets instead of silently stopping at the first page."
        )
    if project == "Resplit" and any(token in raw for token in ("defer", "wake", "admission", "cross-platform proof")):
        return (
            "No new traveler-facing behavior was established in this window. The team recorded that cross-platform Group Link proof "
            "and Android admission checks still cannot run on the current host."
        )
    if project == "Snowcubes" and "switchboard" in raw:
        return (
            "The Snowcubes operating Switchboard was rechecked in production and its boundaries were clarified. "
            "The next kit workflow remains deliberately paused at Leo’s physical-batch decision."
        )
    if project == "Shadow" and any(token in raw for token in ("configured upstream", "shared trunk", "local-only claim")):
        return (
            "Two related proposals define how ownership should remain discoverable when work begins from a second computer, "
            "including an explicit degraded mode when the shared trunk cannot safely hold the receipt."
        )
    if project == "Takeoff" and "adoption" in raw:
        match = re.search(r"unit=(\d+)\s+parity=(\d+)\s+smoke=(\d+)", raw)
        if match:
            return (
                f"A broad Resplit web verification run passed {int(match.group(1)):,} unit checks, "
                f"{int(match.group(2))} parity checks, and {int(match.group(3))} smoke checks."
            )
        return "Takeoff recorded a broad Resplit web verification run across unit, parity, and smoke coverage."
    if project == "AI toolchain" and any(token in raw for token in ("python 3.9", "xcb", "import")):
        return "The local display-lock helper can now load under the system Python 3.9 runtime instead of failing at import time."
    if subjects and reviews:
        return (
            "Related source work and a review are visible, but their titles do not yet establish "
            "one product-level outcome."
        )
    if subjects:
        return (
            "Related source work is visible, but its titles do not yet establish one product-level outcome."
        )
    return (
        "A related proposal is under review, but its title does not yet establish one product-level outcome."
    )


def _material_change_weight(subjects: list[str], reviews: list[str]) -> int:
    """Prefer substantive implementation over receipts while keeping both visible."""
    weight = len(reviews)
    for subject in subjects:
        lowered = subject.lower()
        if any(token in lowered for token in ("brief", "report", "digest")):
            weight += 8
        if re.match(r"^(?:feat|fix|perf|refactor|backup|gate|test)(?:\([^)]*\))?[!:]", lowered):
            weight += 4
        elif any(token in lowered for token in ("allergen", "cache", "account deletion", "retention")):
            weight += 3
        elif re.match(r"^(?:docs|shadow|adoption|proof|record|defer|checkpoint)(?:\([^)]*\))?[!:]", lowered):
            weight += 0
        else:
            weight += 1
    return weight


def build_material_changes(
    *,
    board: dict[str, Any],
    repos: list[RepoPaint],
    github: list[dict[str, Any]],
    vercel: dict[str, Any],
) -> list[dict[str, Any]]:
    """Pool recent source facts by product, then add a separate bounded judgment."""
    groups: dict[str, dict[str, Any]] = {}

    def group(label: str) -> dict[str, Any]:
        return groups.setdefault(
            label,
            {"subjects": [], "reviews": [], "links": [], "ahead": False, "plan": False},
        )

    for repo in repos:
        if not repo.recent_commits:
            continue
        label = repo_project_label(repo.name)
        bucket = group(label)
        bucket["subjects"].extend(repo.recent_commits[:6])
        bucket["ahead"] = bucket["ahead"] or repo.ahead > 0 or repo.dirty

    for row in github:
        if not isinstance(row, dict) or row.get("error") or not row.get("title"):
            continue
        repository = row.get("repository") or {}
        repo_name = repository.get("nameWithOwner") if isinstance(repository, dict) else repository
        label = repo_project_label(repo_name or "Code review")
        bucket = group(label)
        bucket["reviews"].append(str(row.get("title")))
        if row.get("url"):
            bucket["links"].append({"label": "Open review", "url": str(row.get("url"))})

    project_priorities = {
        human_project_label(project.get("id")): int(project.get("priority"))
        for project in (board.get("projects") or [])
        if isinstance(project, dict) and isinstance(project.get("priority"), int)
    }
    claimed_projects: set[str] = set()
    entity_projects = {
        str(entity.get("id") or ""): human_project_label(entity.get("project"))
        for entity in (board.get("entities") or [])
        if isinstance(entity, dict)
    }
    for claim in (board.get("claims") or []):
        if isinstance(claim, dict) and claim.get("entity") in entity_projects:
            claimed_projects.add(entity_projects[str(claim.get("entity"))])
    for entity in (board.get("entities") or []):
        if not isinstance(entity, dict):
            continue
        label = human_project_label(entity.get("project"))
        if label in groups and entity.get("recent_progress"):
            groups[label]["plan"] = True

    ready_products = {
        human_project_label(row.get("name"))
        for row in (vercel.get("deployments") or [])
        if isinstance(row, dict) and str(row.get("state") or "").upper() == "READY"
    }
    ranked = sorted(
        groups.items(),
        key=lambda item: (
            -_material_change_weight(item[1]["subjects"], item[1]["reviews"]),
            item[0] not in claimed_projects,
            project_priorities.get(item[0], 99),
            -len(item[1]["subjects"]),
            -len(item[1]["reviews"]),
            item[0],
        ),
    )
    changes: list[dict[str, Any]] = []
    for project, facts in ranked[:5]:
        subjects = list(dict.fromkeys(facts["subjects"]))[:4]
        reviews = list(dict.fromkeys(facts["reviews"]))[:2]
        evidence_subjects = subjects or reviews
        if not evidence_subjects:
            continue
        headline, meaning = _change_theme(project, evidence_subjects)
        fact = _material_change_fact(project, subjects, reviews)
        if subjects:
            status = "local work in progress" if facts["ahead"] else "verified in source"
        else:
            status = "awaiting review"
        if project in ready_products:
            status = "live web receipt"
        evidence = ["Source confirmed" if subjects else "Review in progress"]
        if facts["plan"]:
            evidence.append("Current plan")
        if reviews and subjects:
            evidence.append("Review in progress")
        changes.append({
            "project": project,
            "status": status,
            "headline": headline,
            "fact": fact,
            "meaning": meaning,
            "evidence": evidence,
            "links": facts["links"][:2],
        })
    return changes


def build_chief_of_staff_analysis(
    *,
    board: dict[str, Any],
    repos: list[RepoPaint],
    github: list[dict[str, Any]],
    vercel: dict[str, Any],
    supabase: dict[str, Any],
    mail: dict[str, Any],
    source_health: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Turn source facts into bounded judgments without inventing dates or authority."""
    def readable_outcome(value: Any) -> str:
        text = " ".join(str(value or "the next proof").split())
        text = re.sub(r"~[a-z0-9]{4}\b", "", text)
        lowered = text.lower()
        if "customer/support loop" in lowered:
            return "prove the customer and support loop works end to end"
        if "two consecutive natural" in lowered and "08:00/20:00" in lowered:
            return "prove the morning and evening report arrives correctly"
        if "physical m1" in lowered:
            return "bring the dedicated build computer safely online"
        if "browser use cloud vendor sweep" in lowered:
            return "finish the visual vendor search when the research tool is available"
        if "gifting hero" in lowered:
            return "replace the retired gift packaging shown to customers"
        if "linked write discloses" in lowered:
            return "make every setup change explain where it was saved"
        if "supported host file is a symlink" in lowered:
            return "keep every AI assistant on one shared set of Shadow instructions"
        if "shadow accept" in lowered and "contradictions" in lowered:
            return "prevent disputed foundations from being marked finished"
        if "m3 closeout" in lowered and "soft" in lowered:
            return "finish the evidence-backed packaging shortlist"
        if "reconcile every resplit row" in lowered and "four shadow views" in lowered:
            return "bring Resplit’s product, release, support, and growth picture into one trustworthy view"
        if "account data deletion" in lowered and "trip link" in lowered:
            return "prove people can delete their account safely from every trip setup"
        if "outside project completes" in lowered and "uncoached" in lowered:
            return "prove a new project can move from intent to verified completion without coaching"
        if "multi-person navigation latency" in lowered:
            return "prove shared-trip navigation is fast enough against a clear benchmark"
        if "differently shaped real snowcubes input" in lowered:
            return "prove a second kind of customer request enters the right Snowcubes workflow"
        if "intake-and-routing contract" in lowered:
            return "turn messy Snowcubes notes into clear, correctly routed work"
        if "shadow throw" in lowered and ("requires a pull request" in lowered or "protected trunk" in lowered):
            return "prove Shadow can begin work safely when changes must be reviewed first"
        if "exact calendar target" in lowered and "first case" in lowered:
            return "choose where the first Snowcubes commitment should live before changing anything"
        if ":" in text:
            text = text.split(":", 1)[0].strip()
        text = text.replace("`", "").replace("/", " and ")
        text = re.sub(r"\s+", " ", text).strip(" .")
        if len(text) > 120:
            text = text[:117].rstrip() + "…"
        return text

    all_entities = [row for row in (board.get("entities") or []) if isinstance(row, dict)]
    unavailable_entities = [
        row for row in all_entities if row.get("availability") == "unavailable"
    ]
    entities = [row for row in all_entities if row.get("availability") != "unavailable"]
    claims = [row for row in (board.get("claims") or []) if isinstance(row, dict)]
    claim_rows = _claim_index(claims)
    ranked = sorted(
        entities,
        key=lambda row: (row.get("priority") is None, row.get("priority") or 99, row.get("project") or ""),
    )
    open_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    blocked_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entity in ranked:
        open_rows.extend((entity, cp) for cp in (entity.get("open_checkpoints") or []))
        blocked_rows.extend((entity, cp) for cp in (entity.get("blocked") or []))
    claimed = [pair for pair in open_rows if _claim_key_for(*pair) in claim_rows]
    unclaimed = [pair for pair in open_rows if _claim_key_for(*pair) not in claim_rows]
    dirty = [repo for repo in repos if repo.dirty]
    stale = [repo for repo in repos if repo.stale]
    healthy_vercel = sum(
        1 for row in (vercel.get("deployments") or []) if str(row.get("state") or "").upper() == "READY"
    )
    healthy_db = sum(
        1 for row in (supabase.get("projects") or []) if "HEALTHY" in str(row.get("status") or "").upper()
    )
    source_gaps = [name for name, health in source_health.items() if not health.get("available")]
    decision_source_gaps = source_gaps
    material_changes = build_material_changes(
        board=board,
        repos=repos,
        github=github,
        vercel=vercel,
    )

    if unavailable_entities:
        unavailable_count = len(unavailable_entities)
        readable_count = len(entities)
        if claimed:
            first_entity, first_cp = claimed[0]
            first_project = human_project_label(first_entity.get("project") or "the visible work")
            first_title = readable_outcome(first_cp.get("title"))
            visible_motion = (
                f"Among the {readable_count} readable plan source"
                f"{'s' if readable_count != 1 else ''}, {first_project} has an owned obligation: "
                f"{first_title.rstrip('.')}."
            )
        else:
            visible_motion = (
                f"The {readable_count} readable plan source"
                f"{'s show' if readable_count != 1 else ' shows'} {len(open_rows)} visible open outcome"
                f"{'s' if len(open_rows) != 1 else ''}; ownership outside that readable subset is not inferred."
            )
        opening = (
            f"{unavailable_count} Shadow plan source"
            f"{'s are' if unavailable_count != 1 else ' is'} unavailable, so portfolio-wide priority, "
            f"ownership, and open-work totals are UNKNOWN. {visible_motion}"
        )
    elif material_changes:
        lead = material_changes[0]
        ownership = (
            f" {len(claimed)} concrete outcome{'s are' if len(claimed) != 1 else ' is'} actively owned, so there is an accountable path from this work to proof."
            if claimed
            else " No outcome is visibly owned, so the work does not yet have an accountable path to proof."
        )
        opening = (
            f"{lead['project']} carries the most consequential change in this window. {lead['headline']}. "
            f"{lead['meaning']}{ownership}"
        )
    elif claimed:
        first_entity, first_cp = claimed[0]
        first_project = human_project_label(first_entity.get("project") or "the current priority")
        first_title = readable_outcome(first_cp.get("title"))
        opening = (
            f"The portfolio is moving, but the scarce resource is attention rather than ideas. "
            f"{len(claimed)} concrete outcome{'s are' if len(claimed) != 1 else ' is'} actively owned, "
            f"and {first_project} is carrying the first concrete obligation: {first_title.rstrip('.')}."
        )
    else:
        opening = (
            f"The portfolio has {len(open_rows)} open outcomes but none is visibly owned. "
            "That is a coordination failure, not a shortage of possible work."
        )
    if material_changes:
        secondary = material_changes[1:3]
        secondary_read = " ".join(
            (
                f"{change['project']} deserves attention for a different reason. "
                if index == 0
                else f"{change['project']} is moving too. "
            )
            + f"{str(change['headline']).rstrip('.')}. {change['meaning']}"
            for index, change in enumerate(secondary)
        )
        operations = secondary_read + (
            " Across the supporting systems, review work is active, and the web and data-service signals are available. "
            "They are separate kinds of evidence—not a single claim that everything is finished. "
            "Internal working notes stay private unless they change the next decision or block an owned outcome."
        )
    else:
        operations = (
            "No recent product-level source movement could be reconstructed from the reporting window. "
            "That is an evidence gap, not a claim that nothing changed."
        )
    if mail.get("available"):
        if mail.get("cursor_limit_threads"):
            mail_read = (
                f"Mail adds an important operational signal: {mail.get('threads_returned', 0)} recent threads were sampled, "
                f"{mail.get('github_notification_threads', 0)} came from development systems, and "
                f"{mail.get('cursor_limit_threads', 0)} mention Cursor review capacity limits. "
                "That makes review throughput a real constraint; it does not automatically make the underlying product work wrong."
            )
        else:
            mail_read = (
                f"Mail is dominated by automated development traffic: {mail.get('github_notification_threads', 0)} of "
                f"{mail.get('threads_returned', 0)} sampled threads came from automated development systems. "
                "That corroborates a high volume of implementation and review activity, but it adds almost no independent customer or commercial evidence."
            )
    else:
        mail_read = "Mail could not be read, so external requests and review notifications are an acknowledged blind spot in this note."
    if decision_source_gaps:
        missing_labels = {
            "astro_aso": "App Store search visibility",
            "ahrefs_seo": "web search visibility",
            "app_store_connect": "App Store delivery status",
        }
        mail_read += " The note is also missing " + ", ".join(
            missing_labels.get(name, name.replace("_", " ")) for name in decision_source_gaps[:5]
        ) + "; those absences lower confidence rather than being treated as zero activity."

    decided: list[dict[str, Any]] = []
    if unavailable_entities:
        decided.append({
            "title": "Hold portfolio ranking until every plan is readable",
            "prose": (
                f"{len(unavailable_entities)} plan source"
                f"{'s are' if len(unavailable_entities) != 1 else ' is'} unavailable. "
                "I am keeping visible owned work visible, but I am not treating a lower readable project as the portfolio priority or missing work as zero."
            ),
            "evidence": ["Shadow board partial-read receipt", "exact plan recovery wake"],
            "confidence": "high",
        })
    if claimed:
        decided.append({
            "title": "Protect the work already in motion",
            "prose": (
                f"I am holding the portfolio to the {len(claimed)} outcomes already in motion before widening scope. "
                "New ideas stay as context unless they remove a blocker or materially change the value of work already promised."
            ),
            "evidence": ["active ownership records", "current product plans"],
            "confidence": "high",
        })
    if material_changes:
        lead = material_changes[0]
        proof_boundary = {
            "local work in progress": "The change exists only in unfinished local work.",
            "verified in source": "The change is recorded in source but has not yet been proved on a live surface.",
            "awaiting review": "The change is still a proposal under review.",
            "live web receipt": "A web provider reports a live release, but customer use is still a separate question.",
        }.get(str(lead.get("status") or ""), "The strongest receipt is still upstream of customer use.")
        decided.append({
            "title": f"Keep {lead['project']} on the right side of the proof boundary",
            "prose": (
                f"{proof_boundary} I am treating “{lead['headline']}” as real progress while holding release, live use, "
                "and customer consequence to their own receipts."
            ),
            "evidence": list(lead.get("evidence") or []),
            "confidence": "high",
        })
    if mail.get("cursor_limit_threads"):
        decided.append({
            "title": "Treat Cursor’s review limit as degraded capacity, not a veto",
            "prose": (
                f"The mailbox contains {mail.get('cursor_limit_threads')} recent thread"
                f"{'s' if mail.get('cursor_limit_threads') != 1 else ''} mentioning a usage or spend limit. I am separating that missing automated opinion from product correctness: affected changes still need independent evidence, but they should not be described as failed merely because the automated reviewer skipped them."
            ),
            "evidence": ["Superhuman all-account 90-day declared scan", "GitHub review notifications"],
            "confidence": "high",
        })
    decided.append({
        "title": "Do not manufacture completion dates",
        "prose": (
            "An owner’s next check-in is an accountability moment, not an ETA for the finished product. "
            "Where a plan lacks a known sequence of remaining work and observed cycle time, this memo will say ‘unknown’ and name the missing evidence instead of producing calendar theater."
        ),
        "evidence": ["agreed next check-in dates", "evidence required to call work done"],
        "confidence": "high",
    })
    architecture: list[dict[str, Any]] = []
    for entity in ranked:
        for raw in (entity.get("decisions") or [])[-1:]:
            left, _, rest = str(raw).partition("| winner:")
            winner, marker, status_tail = re.split(r"\| (closed|opened)\s+", rest, maxsplit=1) if re.search(r"\| (closed|opened)\s+", rest) else (rest, "", "")
            if not winner:
                continue
            decision_text = winner.strip()
            tradeoff_text = left.strip()
            lower_decision = decision_text.lower()
            if "keep local; skip fleet remount" in lower_decision:
                decision_text = "Keep Shadow local-first until a real remote surface needs activation."
                tradeoff_text = "installing everywhere in advance versus activating only where a person will use it"
            elif "reader html explains" in lower_decision:
                decision_text = "Keep troubleshooting instructions out of the reader-facing note while preserving them privately for recovery."
                tradeoff_text = "full technical detail in the email versus a report a nondeveloper can understand"
            elif "email shows products, promises, motion" in lower_decision:
                decision_text = "Tell the portfolio story through products, promises, decisions, risks, and simple diagrams; keep implementation identifiers private."
                tradeoff_text = "an engineering inventory versus a human portfolio story"
            elif "source-labelled brief is the sole dashboard" in lower_decision:
                decision_text = "Make the new Snowcubes operating brief the one front door and retire the duplicate old view."
                tradeoff_text = "preserving history versus forcing people to choose between two competing dashboards"
            elif "exact location and partner-specific formulas" in lower_decision:
                decision_text = "Keep each Snowcubes partner’s commercial model distinct; prose may explain money but never settle it."
                tradeoff_text = "one reusable visit template versus truthful partner-specific economics"
            elif "snowcubes becomes one explained workstream" in lower_decision:
                decision_text = "Keep one local report for the whole portfolio; Snowcubes is one explained workstream, not a separate morning product."
                tradeoff_text = "a Snowcubes-first email versus one consistent chief-of-staff brief at both daily windows"
            elif "canonical git source and owner boundary win" in lower_decision:
                decision_text = "Keep one canonical copy of every skill; installed copies are generated outputs and must be replaced when they drift."
                tradeoff_text = "easy local installation versus confidence that every assistant is using the same current capability"
            elif "keep tested specialist capability but route it internally" in lower_decision:
                decision_text = "Keep specialist capabilities behind Shadow and Switchboard instead of making people choose from a technical tool menu."
                tradeoff_text = "direct access for expert operators versus a calmer front door for everyone else"
            elif "cally" in lower_decision and "maily" in lower_decision:
                decision_text = "Move personal scheduling into one Leo-facing assistant after its safeguards are preserved."
                tradeoff_text = "keeping two overlapping personal assistants versus one clear front door with safe calendar controls"
            else:
                decision_text = "The current operating decision is recorded; its implementation stays in the private plan."
                tradeoff_text = "the practical options remain documented in the current product plan"
            status = f"{marker} {human_datetime(status_tail)}".strip() if marker else "recorded in the current plan"
            architecture.append({
                "project": human_project_label(entity.get("project") or "unknown"),
                "decision": decision_text,
                "tradeoff": tradeoff_text,
                "status": status,
                "evidence": "recorded in the current product plan",
            })
    material_order = {
        str(change.get("project")): index
        for index, change in enumerate(material_changes)
        if isinstance(change, dict)
    }
    architecture.sort(
        key=lambda item: (
            0 if item.get("project") == "Twice-daily report" else 1,
            material_order.get(str(item.get("project")), 99),
            str(item.get("project") or ""),
        )
    )
    if not architecture:
        architecture.append({
            "project": "portfolio",
            "decision": "Shadow remains the priority and ownership authority; external systems are evidence sources, not replacement queues.",
            "tradeoff": "richer source aggregation versus duplicated task truth",
            "status": "active architecture",
            "evidence": "Shadow board and report contract",
        })

    questions: list[dict[str, str]] = []
    if material_changes:
        lead = material_changes[0]
        questions.append({
            "question": f"What would make “{lead['headline']}” visible to a customer or operator, rather than only true in source?",
            "why": "The strongest new evidence is still upstream of live use; naming the observable consequence prevents source activity from becoming the success metric.",
        })
    if len(claimed) > 3:
        questions.append({
            "question": f"Are {len(claimed)} simultaneous commitments truly independent, or are we disguising context switching as throughput?",
            "why": "If several outcomes depend on the same person or verification step, fewer active commitments would finish sooner.",
        })
    if mail.get("cursor_limit_threads"):
        questions.append({
            "question": "Which changes genuinely require the automated code reviewer, and which inherited that gate by habit?",
            "why": "The inbox shows repeated skipped automated reviews; a universal gate can stall safe work without increasing confidence.",
        })
    if dirty:
        questions.append({
            "question": f"Which of the {len(dirty)} unfinished projects could actually hurt today’s outcome?",
            "why": "A large cleanup count feels urgent while saying little about customer or release risk.",
        })
    if decision_source_gaps:
        questions.append({
            "question": "Are we willing to make growth and release calls while web search, App Store visibility, or delivery evidence is absent?",
            "why": "Missing acquisition and store signals can make engineering motion look more valuable than it is.",
        })
    questions = questions[:5]

    direct_asks: list[dict[str, str]] = []
    for entity, cp in open_rows + blocked_rows:
        title = str(cp.get("title") or "")
        lowered = title.lower()
        if re.match(
            r"^(needs leo|leo needs to|leo authorizes|requires leo(?:'s)? (?:decision|approval))\b",
            lowered,
        ):
            direct_asks.append({
                "project": human_project_label(entity.get("project") or "unknown"),
                "ask": readable_outcome(title),
            })
    needs_leo = {
        "requires_response": bool(direct_asks),
        "title": (
            f"{len(direct_asks)} decision{'s' if len(direct_asks) != 1 else ''} need you now"
            if direct_asks
            else (
                "No readable plan needs a decision from you"
                if unavailable_entities
                else "No decision needs you right now"
            )
        ),
        "prose": (
            (
                "The requests below are the only current work that cannot continue without your decision."
                if direct_asks
                else "The active work can continue without a reply to this note. The questions below are challenges for your point of view, not blockers."
            )
            + (
                f" {len(unavailable_entities)} plan source"
                f"{'s are' if len(unavailable_entities) != 1 else ' is'} unavailable, so a request for you "
                "may still be waiting inside them; this is not a portfolio-wide all-clear."
                if unavailable_entities
                else ""
            )
        ),
        "asks": direct_asks[:3],
    }

    etas: list[dict[str, str]] = []
    now = datetime.now(REPORT_TIMEZONE)
    for entity, cp in claimed[:5]:
        claim = claim_rows.get(_claim_key_for(entity, cp), {})
        checkpoint = readable_outcome(cp.get("title"))
        raw_return = str(claim.get("return_by") or "")
        eta = raw_return or "unknown"
        basis = "next owner evidence check; completion after that remains unknown"
        confidence = "medium" if raw_return else "low"
        if raw_return:
            try:
                if datetime.fromisoformat(raw_return.replace("Z", "+00:00")) <= now:
                    eta = "unknown"
                    basis = "the owner’s evidence check is overdue; a new completion estimate would be fiction"
                    confidence = "low"
            except ValueError:
                eta = "unknown"
                basis = "the recorded evidence-check time is invalid"
                confidence = "low"
        etas.append({
            "project": human_project_label(entity.get("project") or "unknown"),
            "outcome": checkpoint,
            "eta": eta,
            "basis": basis,
            "confidence": confidence,
        })
    for entity, cp in unclaimed[: max(0, 5 - len(etas))]:
        etas.append({
            "project": human_project_label(entity.get("project") or "unknown"),
            "outcome": readable_outcome(cp.get("title")),
            "eta": "unknown",
            "basis": "no active owner and no measured sequence of remaining work",
            "confidence": "low",
        })

    stalling: list[dict[str, str]] = []
    stalled_projects: set[str] = set()
    for entity, cp in blocked_rows[:4]:
        project = human_project_label(entity.get("project") or "unknown")
        if project in stalled_projects:
            continue
        stalled_projects.add(project)
        stalling.append({
            "project": project,
            "signal": readable_outcome(cp.get("title") or "blocked work"),
            "improvement": "write the one condition that restarts it, free the owner to work elsewhere, and return only when that condition changes",
        })
    unclaimed_by_project: dict[str, int] = {}
    for entity, _ in unclaimed:
        project = human_project_label(entity.get("project") or "unknown")
        unclaimed_by_project[project] = unclaimed_by_project.get(project, 0) + 1
    for project, count in sorted(unclaimed_by_project.items(), key=lambda item: (-item[1], item[0])):
        if len(stalling) >= 5:
            break
        if project in stalled_projects:
            continue
        stalled_projects.add(project)
        stalling.append({
            "project": project,
            "signal": (
                f"{count} ready checkpoints make the lane too broad to communicate a real priority"
                if count > 5
                else f"{count} ready checkpoint{'s' if count != 1 else ''} {'have' if count != 1 else 'has'} no owner"
            ),
            "improvement": (
                "promote one outcome that can be finished and verified now; keep the rest as backlog rather than presenting all of it as active"
                if count > 5
                else "start the highest-value result that can be finished and verified now, or explicitly leave it for later"
            ),
        })
    if stale and len(stalling) < 5:
        stalling.append({
            "project": "local workspaces",
            "signal": f"{len(stale)} older workspaces still contain unfinished changes",
            "improvement": "inspect only the ones that overlap an owned result; archive or ignore the rest instead of launching a cleanup campaign",
        })

    return {
        "executive_read": [opening, operations, mail_read],
        "material_changes": material_changes,
        "decided_for_you": decided[:5],
        "needs_leo": needs_leo,
        "architecture_decisions": architecture[:5],
        "questions_to_challenge": questions,
        "etas": etas,
        "stalling_lanes": stalling,
        "source_gaps": [
            {
                "source": name,
                "error": str(health.get("error") or "unavailable"),
                "wake": str(health.get("wake") or "no wake recorded"),
            }
            for name, health in source_health.items()
            if not health.get("available")
        ],
        "reasoning_contract": {
            "authority": "current Shadow portfolio and active product plans",
            "current_evidence": ["local Git", "GitHub", "Vercel", "Supabase", "Superhuman"],
            "rule": "missing or stale sources lower confidence; they never become zero activity or override today’s active plans",
        },
        "future_of_building": (
            "Building is no longer the technical inventory shown in the old report. It is a loop of promises: decide what should change, "
            "make the smallest real version, prove it with evidence, put it where people can reach it, and learn from what happens next. "
            "The report’s job is to show where each product sits in that loop and what is preventing the promise from moving forward."
        ),
    }


def collect_packet(*, slot: str | None = None) -> dict[str, Any]:
    started = datetime.now(REPORT_TIMEZONE)
    if slot is None:
        slot = "morning" if started.hour < 14 else "evening"
    root = portfolio_root()
    repos = collect_repos(root)
    github = collect_github()
    vercel = collect_vercel()
    supabase = collect_supabase()
    mail = collect_superhuman_context()
    snowcubes_mail = superhuman_account_context(mail, SNOWCUBES_BUSINESS_MAIL)
    growth_health = collect_growth_source_status()
    paint_health = {
        "local_git": build_local_git_health(root, repos),
        **build_paint_health(github, vercel),
        "supabase": (
            {"available": True}
            if supabase.get("available")
            else {
                "available": False,
                "error": str(supabase.get("error") or "Supabase unavailable"),
                "wake": "supabase projects list --output json",
            }
        ),
        "superhuman": (
            {"available": True}
            if mail.get("available")
            else {
                "available": False,
                "error": str(
                    mail.get("error")
                    or "; ".join(str(value) for value in (mail.get("problems") or []))
                    or "Superhuman coverage is UNKNOWN"
                ),
                "wake": str(
                    mail.get("wake")
                    or "refresh Superhuman mcp-remote OAuth, then run a read-only list_threads check"
                ),
            }
        ),
        **growth_health,
    }
    github_query = {
        "limit": GITHUB_PR_LIMIT,
        "returned": len(github),
        "may_be_truncated": len(github) == GITHUB_PR_LIMIT,
    }
    # Finish every slow paint/status read before taking the authority snapshot.
    status_excerpt = collect_shadow_status_excerpt()
    board: dict[str, Any] = {}
    board_snapshot = {"consistent": False, "attempts": 0, "revision": None}
    for attempt in range(1, 4):
        board = collect_board()
        final_revision = _read_board_revision()
        board_revision = board.get("revision")
        board_snapshot = {
            "consistent": (
                isinstance(board_revision, int)
                and not isinstance(board_revision, bool)
                and isinstance(final_revision, int)
                and not isinstance(final_revision, bool)
                and board_revision == final_revision
            ),
            "attempts": attempt,
            "revision": final_revision,
        }
        if board_snapshot["consistent"]:
            break
    paint_health["shadow_board"] = build_shadow_board_health(board)
    # The Snowcubes work card and the packet must describe the same final
    # authority snapshot. Passing the already-collected mail signal avoids a
    # second provider read after that snapshot.
    snowcubes = collect_snowcubes_context(
        vercel=vercel,
        board=board,
        mail=snowcubes_mail,
    )
    recs = build_recommendations(board, repos)
    analysis = build_chief_of_staff_analysis(
        board=board,
        repos=repos,
        github=github,
        vercel=vercel,
        supabase=supabase,
        mail=mail,
        source_health=paint_health,
    )
    generated = datetime.now(REPORT_TIMEZONE)
    packet = {
        "generated_at": generated.isoformat(timespec="seconds"),
        "slot": slot,
        "host": os.uname().nodename,
        "board": board,
        "repos": [asdict(r) for r in repos],
        "github_open_prs": github,
        "github_query": github_query,
        "vercel": vercel,
        "supabase": supabase,
        "superhuman_context": mail,
        "producer": producer_provenance(),
        "snowcubes_context": snowcubes,
        "paint_health": paint_health,
        "analysis": analysis,
        "recommendations": [asdict(r) for r in recs],
        "shadow_status_excerpt": status_excerpt,
        "authority": {
            "board": str(BOARD_PATH),
            "board_snapshot": board_snapshot,
            "portfolio": str(portfolio_root()),
            "note": "Shadow board is authority; every other source is evidence, not another queue.",
        },
    }
    return packet


def _esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def reader_safe_mail_wake(
    value: Any,
    *,
    row: dict[str, Any] | None = None,
    mail: dict[str, Any] | None = None,
) -> str:
    """Keep the concrete wake while removing private provider mechanics."""
    text = str(value or "").strip()
    if not text:
        return ""
    subject = str((row or {}).get("subject") or "this item").strip()
    signals = [row] if isinstance(row, dict) else []
    if isinstance(mail, dict):
        signals.extend(
            signal
            for signal in (mail.get("signals") or [])
            if isinstance(signal, dict)
        )
    opaque_ids: set[str] = set()
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        for key in ("thread_id", "last_message_id"):
            candidate = str(signal.get(key) or "").strip()
            if candidate:
                opaque_ids.add(candidate)
        for source in signal.get("source_threads") or []:
            if not isinstance(source, dict):
                continue
            for key in ("thread_id", "last_message_id"):
                candidate = str(source.get(key) or "").strip()
                if candidate:
                    opaque_ids.add(candidate)
    replacement = f"for {subject}"
    for opaque_id in sorted(opaque_ids, key=len, reverse=True):
        text = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(opaque_id)}(?![A-Za-z0-9])",
            replacement,
            text,
        )
    text = re.sub(
        r"(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?",
        r"\1",
        text,
    )
    text = re.sub(
        r"exhaust every cursor",
        "finish the full declared scan",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"pagination cursor",
        "mailbox continuation",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bcursor\b", "continuation", text, flags=re.IGNORECASE)
    return text.replace("thread_id", "thread identity").replace(
        "message_id", "message identity"
    )


def human_datetime(value: Any) -> str:
    """Render machine timestamps as calm local reader copy."""
    raw = str(value or "").strip()
    if not raw or raw.lower() == "unknown":
        return raw or "unknown"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(REPORT_TIMEZONE)
    month_day = parsed.strftime("%b %d").replace(" 0", " ")
    hour = parsed.strftime("%I").lstrip("0") or "12"
    return f"{month_day} · {hour}:{parsed.strftime('%M')} {parsed.strftime('%p')}"


def _reader_generation_marker(slot: Any, generated_at: Any) -> str:
    if not isinstance(slot, str) or not slot.strip():
        return ""
    return f"{slot.title()} note · twice-daily · {human_datetime(generated_at)}"


def render_html(packet: dict[str, Any]) -> str:
    slot = packet.get("slot") or "brief"
    when = packet.get("generated_at") or ""
    board = packet.get("board") or {}
    all_entities = [row for row in (board.get("entities") or []) if isinstance(row, dict)]
    unavailable_entities = [
        row for row in all_entities if row.get("availability") == "unavailable"
    ]
    entities = [row for row in all_entities if row.get("availability") != "unavailable"]
    unavailable_n = len(unavailable_entities)
    repos = packet.get("repos") or []
    prs = packet.get("github_open_prs") or []
    recs = packet.get("recommendations") or []
    claims = board.get("claims") or []
    analysis = packet.get("analysis") or {}
    snowcubes = packet.get("snowcubes_context") or {}

    open_n = sum(len(e.get("open_checkpoints") or []) for e in entities)
    blocked_n = sum(len(e.get("blocked") or []) for e in entities)
    dirty_n = sum(1 for r in repos if r.get("dirty"))
    stale_n = sum(1 for r in repos if r.get("stale"))

    def section(title: str, body: str) -> str:
        return f'<section class="block"><h2>{_esc(title)}</h2>{body}</section>'

    def project_label(value: Any) -> str:
        return human_project_label(value)

    def checkpoint_title(value: Any, project: Any = "") -> str:
        text = " ".join(str(value or "the next useful step").split())
        lowered = text.lower()
        project_text = str(project or "").lower()
        if "morning and evening report" in lowered and "arrives correctly" in lowered:
            return "prove the morning and evening report arrives correctly"
        if "two consecutive natural" in lowered and "08:00/20:00" in lowered:
            return "prove the morning and evening report arrives correctly"
        if "local collector survives" in lowered and "pools current board" in lowered:
            return "make the brief stay complete even while one project plan is changing"
        if "every morning means two consecutive natural 08" in lowered:
            return "prove the Snowcubes morning signal remains reliable across two natural mornings"
        if "one ordinary workday closes only after all six loops" in lowered:
            return "prove one ordinary Resplit workday can move from decision through customer learning"
        if "publish and merge the proven candidate" in lowered:
            return "move the verified Resplit change through review without confusing it with a release"
        if "m1 identity" in lowered and "runner" in lowered:
            return "confirm the new build runner is ready"
        if "physical m1" in lowered:
            return "bring the dedicated build computer safely online"
        if "browser use cloud vendor sweep" in lowered:
            return "finish the visual vendor search when the research tool is available"
        if "gifting hero" in lowered:
            return "replace the retired gift packaging shown to customers"
        if "linked write discloses" in lowered:
            return "make every setup change explain where it was saved"
        if "supported host file is a symlink" in lowered:
            return "keep every AI assistant on one shared set of Shadow instructions"
        if "shadow accept" in lowered and "contradictions" in lowered:
            return "prevent disputed foundations from being marked finished"
        if "m3 closeout" in lowered and "soft" in lowered:
            return "finish the evidence-backed packaging shortlist"
        if "reconcile every resplit row" in lowered and "four shadow views" in lowered:
            return "bring Resplit’s product, release, support, and growth picture into one trustworthy view"
        if "account data deletion" in lowered and "trip link" in lowered:
            return "prove people can delete their account safely from every trip setup"
        if "outside project completes" in lowered and "uncoached" in lowered:
            return "prove a new project can move from intent to verified completion without coaching"
        if "multi-person navigation latency" in lowered:
            return "prove shared-trip navigation is fast enough against a clear benchmark"
        if "differently shaped real snowcubes input" in lowered:
            return "prove a second kind of customer request enters the right Snowcubes workflow"
        if "shadow throw" in lowered and ("requires a pull request" in lowered or "protected trunk" in lowered):
            return "prove Shadow can begin work safely when changes must be reviewed first"
        if "exact calendar target" in lowered and "first case" in lowered:
            return "choose where the first Snowcubes commitment should live before changing anything"
        if ":" in text:
            prefix = text.split(":", 1)[0].strip()
            if len(prefix) >= 10:
                text = prefix
        text = text.replace("/", " and ")
        text = re.sub(r"\s+", " ", text).strip(" .")
        text = re.sub(r"\brelease loop\b", "release path", text, flags=re.IGNORECASE)
        if text.lower().startswith("prove the ") and "works" not in text.lower():
            text += " works end to end"
        if len(text) > 105 and "," in text:
            text = text.split(",", 1)[0].strip()
        if len(text) > 105:
            text = text[:102].rstrip() + "…"
        if project_text == "ai-leo" and "report" in lowered:
            return "prove the morning and evening report arrives correctly"
        return text

    claim_keys = _claim_index([c for c in claims if isinstance(c, dict)])
    active_entities = [
        ent for ent in entities if (ent.get("open_checkpoints") or ent.get("blocked"))
    ]
    focus_ent = None
    focus_cp = None
    for ent in active_entities:
        for cp in ent.get("open_checkpoints") or []:
            if _claim_key_for(ent, cp) in claim_keys:
                focus_ent, focus_cp = ent, cp
                break
        if focus_ent:
            break
    if focus_ent is None and not unavailable_entities:
        for ent in active_entities:
            opens = ent.get("open_checkpoints") or []
            if opens:
                focus_ent, focus_cp = ent, opens[0]
                break

    focus_project = project_label((focus_ent or {}).get("project"))
    focus_title = checkpoint_title(
        (focus_cp or {}).get("title"), (focus_ent or {}).get("project")
    )
    material_lead = next(
        (
            item
            for item in (analysis.get("material_changes") or [])
            if isinstance(item, dict) and item.get("headline")
        ),
        None,
    )
    if material_lead and not unavailable_entities:
        headline = str(material_lead.get("headline")).rstrip(". ") + "."
        summary = str(material_lead.get("meaning") or "").strip()
        if not summary:
            summary = "The change is real, but its live consequence still needs a separate receipt."
    elif focus_ent:
        headline = (
            f"{focus_project} is the visible move."
            if unavailable_entities
            else f"{focus_project} is the main move."
        )
        quoted_focus = focus_title.rstrip(".!?") + "."
        motion = (
            "It is already in motion."
            if _claim_key_for(focus_ent or {}, focus_cp or {}) in claim_keys
            else "It is ready to move."
        )
        summary = f"{motion} The work in front is “{quoted_focus}” "
        if unavailable_entities:
            summary += (
                f"{unavailable_n} plan source{'s are' if unavailable_n != 1 else ' is'} unavailable, "
                "so this is not a portfolio-wide priority claim."
            )
        else:
            summary += "Everything else should support that result or wait."
    elif unavailable_entities:
        headline = "Part of the portfolio is unreadable."
        summary = (
            f"{unavailable_n} Shadow plan source{'s are' if unavailable_n != 1 else ' is'} unavailable. "
            "Portfolio priority and open-work totals are UNKNOWN until the exact recovery wake succeeds."
        )
    else:
        headline = "Nothing needs forcing right now."
        summary = (
            "The board has no ready work demanding attention. Use the quiet to finish, "
            "archive, or clarify what is already open before starting something new."
        )

    next_ent = next((ent for ent in active_entities if ent is not focus_ent), None)
    if next_ent:
        next_project = project_label(next_ent.get("project"))
        next_opens = next_ent.get("open_checkpoints") or []
        next_title = (
            checkpoint_title(next_opens[0].get("title"), next_ent.get("project"))
            if next_opens
            else "Waiting for a clear restart."
        )
    else:
        next_project = "Keep the runway clear"
        next_title = "Finish the main move before widening the day."
    if unavailable_entities:
        waiting_title = (
            f"At least {blocked_n} visible item{'s' if blocked_n != 1 else ''} waiting"
            if blocked_n
            else "Waiting state incomplete"
        )
        waiting_copy = (
            f"{unavailable_n} plan source{'s need' if unavailable_n != 1 else ' needs'} the named read wake before totals are trusted."
        )
    else:
        waiting_title = (
            f"{blocked_n} item{'s' if blocked_n != 1 else ''} waiting"
            if blocked_n
            else "No hard blocker"
        )
        waiting_copy = (
            "Each needs one clear restart condition before it returns to the day."
            if blocked_n
            else "Nothing is currently forcing a context switch."
        )
    map_html = f"""
      <table class="attention-map" role="presentation" width="100%" cellspacing="0" cellpadding="0">
        <tr>
          <td class="map-node map-now"><span>Now</span><strong>{_esc(focus_project if focus_ent else ('UNKNOWN' if unavailable_entities else 'Quiet'))}</strong><small>{_esc('Current visible focus' if focus_ent and unavailable_entities else ('Current focus' if focus_ent else ('Restore plan reads.' if unavailable_entities else 'Finish before expanding.')))}</small></td>
          <td class="map-arrow">→</td>
          <td class="map-node"><span>Then</span><strong>{_esc(next_project)}</strong><small>{_esc('Next in line' if next_ent else next_title)}</small></td>
          <td class="map-arrow">→</td>
          <td class="map-node map-wait"><span>Waiting</span><strong>{_esc(waiting_title)}</strong><small>{_esc(waiting_copy)}</small></td>
        </tr>
      </table>
    """

    stream_rows = []
    for ent in active_entities[:6]:
        opens = ent.get("open_checkpoints") or []
        blocked = ent.get("blocked") or []
        moving = [cp for cp in opens if _claim_key_for(ent, cp) in claim_keys]
        if moving:
            state = "Moving"
            outcome = checkpoint_title(moving[0].get("title"), ent.get("project"))
            state_class = "moving"
        elif opens:
            state = "Ready"
            outcome = checkpoint_title(opens[0].get("title"), ent.get("project"))
            state_class = "ready"
        else:
            state = "Waiting"
            outcome = checkpoint_title((blocked[0] if blocked else {}).get("title"), ent.get("project"))
            state_class = "waiting"
        stream_rows.append(
            "<tr>"
            f"<td><strong>{_esc(project_label(ent.get('project')))}</strong></td>"
            f"<td><span class='stream-state {state_class}'>{_esc(state)}</span></td>"
            f"<td>{_esc(outcome.rstrip('.!?') + '.')}</td>"
            "</tr>"
        )
    workstreams_html = (
        "<p class='section-intro'>Each workstream is a promise being moved forward, not a technical container.</p>"
        "<table class='stream-table' width='100%' cellspacing='0' cellpadding='0'>"
        "<thead><tr><th>Product</th><th>Motion</th><th>What it means for a person</th></tr></thead>"
        f"<tbody>{''.join(stream_rows)}</tbody></table>"
        if stream_rows
        else "<p class='empty'>No product stream has a clear promise in motion.</p>"
    )
    building_html = f"""
      <p class="essay">{_esc(analysis.get('future_of_building') or 'Building is a loop from intent to evidence and learning.')}</p>
      <table class="build-loop" role="presentation" width="100%" cellspacing="0" cellpadding="0">
        <tr>
          <td><span>1</span><strong>Choose</strong><small>Name the human change.</small></td><td class="loop-arrow">→</td>
          <td><span>2</span><strong>Make</strong><small>Create the smallest real version.</small></td><td class="loop-arrow">→</td>
          <td><span>3</span><strong>Prove</strong><small>Show that it works.</small></td><td class="loop-arrow">→</td>
          <td><span>4</span><strong>Reach</strong><small>Put it where people can use it.</small></td><td class="loop-arrow">→</td>
          <td><span>5</span><strong>Learn</strong><small>Let real response shape the next move.</small></td>
        </tr>
      </table>
    """

    story_cards = []
    story_entities = ([focus_ent] if focus_ent else []) + [
        ent for ent in active_entities if ent is not focus_ent
    ]
    for index, ent in enumerate(story_entities[:3]):
        project = project_label(ent.get("project"))
        opens = ent.get("open_checkpoints") or []
        blocked = ent.get("blocked") or []
        first = (
            checkpoint_title(opens[0].get("title"), ent.get("project"))
            if opens
            else "No ready next step."
        )
        already_moving = any(
            _claim_key_for(ent, cp) in claim_keys for cp in opens
        )
        if already_moving:
            copy = f"Already in motion. The current job is “{first.rstrip('.!?')}.”"
        elif index == 0:
            copy = f"Ready now. The useful next result is “{first.rstrip('.!?')}.”"
        else:
            copy = f"Ready after the main move. Its clearest next result is “{first.rstrip('.!?')}.”"
        if blocked:
            copy += f" It also has {len(blocked)} item{'s' if len(blocked) != 1 else ''} waiting for a restart condition."
        story_cards.append(
            f"<article class='story'><h3>{_esc(project)}</h3><p>{_esc(copy)}</p></article>"
        )
    if not story_cards and recs:
        story_cards = [
            f"<article class='story'><h3>A useful correction</h3><p>{_esc(r.get('text'))}</p></article>"
            for r in recs[:3]
        ]
    attention_html = "".join(story_cards) or (
        "<p class='quiet'>There is no urgent work to elevate in this snapshot.</p>"
    )

    forgotten_n = sum(len(ent.get("forgotten") or []) for ent in entities)
    wait_sentences = []
    if unavailable_entities:
        wait_sentences.append(
            f"{unavailable_n} Shadow plan source{'s are' if unavailable_n != 1 else ' is'} unavailable. "
            "Their work and priority remain UNKNOWN until the exact read wake succeeds."
        )
    if dirty_n and stale_n:
        wait_sentences.append(
            f"Cleanup is real: {dirty_n} project{'s' if dirty_n != 1 else ''} have unfinished changes, "
            f"including {stale_n} older workspace{'s' if stale_n != 1 else ''}. "
            "That is not today’s agenda; touch one only when it blocks the main move."
        )
    elif dirty_n:
        wait_sentences.append(
            f"{dirty_n} project{'s' if dirty_n != 1 else ''} have unfinished local changes. "
            "That is context, not today’s agenda; touch one only when it blocks the main move."
        )
    if forgotten_n:
        wait_sentences.append(
            f"{forgotten_n} older task{'s' if forgotten_n != 1 else ''} have lost a clear next move. Fold them into current work or leave them parked."
        )
    if not wait_sentences:
        wait_sentences.append(
            "There is no cleanup signal strong enough to interrupt the main move."
        )
    what_can_wait_html = "".join(f"<p>{_esc(text)}</p>" for text in wait_sentences)

    pr_html = ""
    if prs and not (len(prs) == 1 and prs[0].get("error")):
        review_counts: dict[str, int] = {}
        for item in prs:
            if not isinstance(item, dict):
                continue
            repo_value = item.get("repository") or ""
            repo_name = (
                str(repo_value.get("nameWithOwner") or "").split("/")[-1]
                if isinstance(repo_value, dict)
                else str(repo_value).split("/")[-1]
            )
            label = project_label(repo_name or "Other work")
            review_counts[label] = review_counts.get(label, 0) + 1
        shown_reviews = sorted(review_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        github_query = packet.get("github_query") or {}
        cap_note = (
            " More may exist beyond this sample."
            if github_query.get("may_be_truncated")
            else ""
        )
        pr_html = "<ul>" + "".join(
            f"<li><strong>{_esc(name)}</strong> · {_esc(count)} change{'s' if count != 1 else ''} awaiting review</li>"
            for name, count in shown_reviews
        ) + "</ul>" + (
            f"<p class='meta'>{_esc(len(prs))} changes awaiting review across {_esc(len(review_counts))} products."
            f"{cap_note}</p>"
        )
    else:
        err = prs[0].get("error") if prs and isinstance(prs[0], dict) else None
        github_available = bool((packet.get("paint_health") or {}).get("github", {}).get("available"))
        empty_message = "No open code reviews." if github_available else "GitHub could not be checked."
        pr_html = f"<p class='empty'>{_esc(err or empty_message)}</p>"

    local_git_health = (packet.get("paint_health") or {}).get("local_git") or {}
    scanned_roots = local_git_health.get("scanned_roots")
    if not isinstance(scanned_roots, int):
        scanned_roots = len(repos)
    dirty_total = sum(1 for r in repos if r.get("dirty"))
    dirty_html = (
        "<p>There is background work in the portfolio. It is private context, not a call to interrupt "
        "the priorities above; raise it only when it blocks a current decision.</p>"
        if dirty_total
        else "<p class='empty'>No background work needs attention in this snapshot.</p>"
    )

    vercel = packet.get("vercel") or {}
    vercel_available = bool((packet.get("paint_health") or {}).get("vercel", {}).get("available"))
    vercel_html = (
        "<p class='empty'>No web releases were returned.</p>"
        if vercel_available
        else "<p class='empty'>Web releases could not be checked.</p>"
    )
    if vercel.get("deployments"):
        release_states: dict[str, int] = {}
        for deployment in vercel["deployments"]:
            state = str(deployment.get("state") or "unknown").lower().replace("_", " ")
            release_states[state] = release_states.get(state, 0) + 1
        vercel_html = "<ul>" + "".join(
            f"<li>{_esc(count)} web product{'s' if count != 1 else ''} {_esc(state)}</li>"
            for state, count in sorted(release_states.items())
        ) + "</ul>" + f"<p class='meta'>{_esc(vercel.get('total_projects', len(vercel['deployments'])))} web products checked.</p>"
    elif vercel.get("error"):
        vercel_html = f"<p class='empty'>{_esc(vercel.get('error'))}</p>"

    supabase = packet.get("supabase") or {}
    db_projects = supabase.get("projects") or []
    healthy_data = sum(1 for row in db_projects if "HEALTHY" in str(row.get("status") or "").upper())
    inactive_data = sum(1 for row in db_projects if "INACTIVE" in str(row.get("status") or "").upper())
    supabase_html = (
        f"<p>{_esc(healthy_data)} data service{'s' if healthy_data != 1 else ''} healthy; "
        f"{_esc(inactive_data)} inactive. Inactive is context, not automatically a defect.</p>"
        if db_projects
        else "<p class='empty'>Database project health could not be established.</p>"
    )
    mail = packet.get("superhuman_context") or {}
    coverage_rows = []
    for row in mail.get("coverage") or []:
        if not isinstance(row, dict):
            continue
        pagination = row.get("pagination") or {}
        query = row.get("query_range") or {}
        source_age = row.get("source_age_hours")
        message_age = row.get("newest_message_age_hours")
        source_copy = (
            "source observation unavailable"
            if source_age is None
            else f"source observed {source_age}h ago"
        )
        message_copy = (
            "no message timestamp"
            if message_age is None
            else f"newest message {message_age}h old"
        )
        age_copy = f"{source_copy} · {message_copy}"
        lookback_days = query.get("lookback_days") or mail.get("query_range", {}).get("lookback_days") or SUPERHUMAN_LOOKBACK_DAYS
        scan_state = (
            "complete"
            if row.get("status") == "COMPLETE"
            and pagination.get("exhausted")
            and not pagination.get("truncated")
            else "partial"
        )
        if not row.get("linked"):
            reader_boundary = reader_safe_mail_wake(
                row.get("wake")
                or "Link this expected identity before relying on mail coverage.",
                mail=mail,
            )
        elif row.get("status") == "UNKNOWN":
            reader_boundary = reader_safe_mail_wake(
                row.get("wake")
                or "Open this account in Superhuman and finish its named UNKNOWN read before relying on an all-clear.",
                mail=mail,
            )
        else:
            reader_boundary = "No source recovery is needed for this declared scan."
        coverage_rows.append(
            "<tr>"
            f"<td><strong>{_esc(row.get('acting_email'))}</strong></td>"
            f"<td>{_esc(lookback_days)}-day declared scan {_esc(scan_state)}</td>"
            f"<td>{_esc(age_copy)}</td>"
            f"<td>{_esc(reader_boundary)}</td>"
            "</tr>"
        )
    coverage_html = (
        "<table class='stream-table' width='100%' cellspacing='0' cellpadding='0'>"
        "<thead><tr><th>Identity</th><th>Declared scan</th><th>Checked</th><th>Finding</th></tr></thead>"
        f"<tbody>{''.join(coverage_rows)}</tbody></table>"
        if coverage_rows
        else "<p class='empty'>No Superhuman identity coverage was available.</p>"
    )
    action_groups = (
        ("Urgent reply", mail.get("urgent_replies") or []),
        ("Waiting reply", mail.get("waiting_replies") or []),
        ("Forgotten obligation", mail.get("forgotten_obligations") or []),
        ("Order or return", mail.get("order_return_follow_up") or []),
        ("Proactive Snowcubes candidate", mail.get("proactive_candidates") or []),
    )
    action_cards: list[str] = []
    seen_action_ids: set[str] = set()
    for label, rows in action_groups:
        for row in rows:
            if not isinstance(row, dict):
                continue
            signal_id = str(row.get("signal_id") or row.get("thread_id") or "")
            if signal_id in seen_action_ids:
                continue
            seen_action_ids.add(signal_id)
            source = ", ".join(str(value) for value in (row.get("source_identities") or []))
            action_cards.append(
                "<article class='signal-note'>"
                f"<h3>{_esc(label)} · {_esc(row.get('semantic_status') or 'UNKNOWN')}</h3>"
                f"<p>{_esc(row.get('subject') or 'Private thread')}</p>"
                f"<p class='confidence'>{_esc(row.get('confidence') or 'LOW')} confidence · "
                f"source observed {_esc(row.get('source_age_hours') if row.get('source_age_hours') is not None else 'UNKNOWN')}h ago · "
                f"newest message {_esc(row.get('message_age_hours') if row.get('message_age_hours') is not None else 'UNKNOWN')}h old</p>"
                f"<p class='meta'>{_esc(row.get('proposal') or 'Proposal only: read the exact source before acting.')}</p>"
                f"<p class='source-note'>{_esc(source or 'Superhuman')} · observed {_esc(human_datetime(row.get('last_message_at')))}"
                + (
                    f"<br/>Wake: {_esc(reader_safe_mail_wake(row.get('wake'), row=row))}"
                    if row.get("wake")
                    else ""
                )
                + "</p></article>"
            )
    actions_html = "".join(action_cards) or (
        "<p class='empty'>No action candidate was strong enough to elevate from the declared read.</p>"
    )
    calendar_cards = "".join(
        "<article class='signal-note'>"
        f"<h3>{_esc(row.get('acting_email'))} · {_esc(row.get('status') or 'PROPOSAL')}</h3>"
        f"<p>{_esc(row.get('summary') or 'Calendar follow-through is unavailable.')}</p>"
        f"<p class='confidence'>{_esc(row.get('confidence') or 'LOW')} confidence · "
        f"source observed {_esc(row.get('source_age_hours') if row.get('source_age_hours') is not None else 'UNKNOWN')}h ago</p>"
        "<p class='meta'>Proposal only: no event, invitation, booking, or notification was created.</p>"
        + (f"<p class='source-note'>Wake: {_esc(row.get('wake'))}</p>" if row.get("wake") else "")
        + "</article>"
        for row in (mail.get("calendar_proposals") or [])
        if isinstance(row, dict)
    ) or "<p class='empty'>No read-only calendar proposal was available.</p>"
    mail_summary = (
        f"{mail.get('threads_unique', 0)} unique threads across {len(mail.get('coverage') or [])} expected or discovered identities. "
        + (
            "Every declared query completed, but proposals still stop at their named read or authorization boundary."
            if mail.get("all_clear_allowed")
            else "At least one identity, source read, body, attachment, or calendar boundary remains UNKNOWN, so this is not an all-clear."
        )
        if mail.get("available")
        else "Superhuman account discovery or mailbox access was unavailable, so mail and calendar state remain UNKNOWN."
    )
    mail_section_html = (
        "<article class='judgment'>"
        f"<h3>Overall verdict · {_esc(mail.get('status') or 'UNKNOWN')}</h3>"
        f"<p>{_esc(mail_summary)}</p>"
        f"<p class='confidence'>{'MEDIUM' if mail.get('all_clear_allowed') else 'LOW'} confidence</p>"
        + (
            f"<p class='source-note'>Wake: {_esc(reader_safe_mail_wake(mail.get('wake'), mail=mail))}</p>"
            if mail.get("wake")
            else ""
        )
        + "</article><h3>Read-only follow-through</h3>"
        + actions_html
        + "<h3>Calendar proposals</h3>"
        + calendar_cards
        + "<h3>What was checked</h3>"
        + coverage_html
    )

    paint_health = packet.get("paint_health") or {}
    unavailable = [
        (source, health)
        for source, health in paint_health.items()
        if isinstance(health, dict) and not health.get("available")
    ]
    source_gap_copy = {
        "github": ("Code review", "Review activity may be incomplete until the account connection is restored."),
        "vercel": ("Web delivery", "The note cannot confirm whether the latest web versions are ready."),
        "supabase": ("Data services", "The note cannot confirm current data-service health."),
        "superhuman": ("Mail", "External requests and review notifications may be missing from this read."),
        "astro_aso": ("App Store visibility", "Keyword movement, ratings, and competitive search position are absent."),
        "ahrefs_seo": ("Web search visibility", "Organic demand, backlinks, and search-performance changes are absent."),
        "app_store_connect": ("App Store delivery", "The note cannot confirm processing, testing, or release state from App Store Connect."),
        "local_git": ("Local work", "The private machine inventory could not be checked."),
        "shadow_board": ("Shadow plans", "One or more board-owned plans could not be read, so their execution state remains unknown."),
    }
    recovery_html = (
        "<ul>" + "".join(
            f"<li><strong>{_esc(source_gap_copy.get(source, (source.replace('_', ' ').title(), 'This source is missing.'))[0])}</strong> — "
            f"{_esc(source_gap_copy.get(source, ('', 'This source is missing.'))[1])}</li>"
            for source, _health in unavailable
        ) + "</ul><p class='meta'>Exact technical recovery instructions remain in the private machine receipt, not in this reader-facing note.</p>"
        if unavailable
        else "<p class='empty'>Every supporting source was available for this note.</p>"
    )

    snowcubes_surfaces = [
        item for item in (snowcubes.get("surfaces") or []) if isinstance(item, dict)
    ]
    snowcubes_cards = "".join(
        "<article class='story'>"
        f"<h3>{_esc(item.get('name'))} · {_esc(str(item.get('state') or 'unknown').upper())}</h3>"
        f"<p>{_esc(item.get('now'))}</p><p class='meta'>{_esc(item.get('next'))}</p>"
        f"<p class='meta'>Source: {_esc(item.get('source'))} · observed {_esc(human_datetime(item.get('observed_at')))}"
        + (f"<br/>Proposal: {_esc(item.get('proposal'))}" if item.get("proposal") else "")
        + (
            f"<br/><a href='{_esc(item.get('native_link'))}' target='_blank' rel='noopener'>Open native source</a>"
            if item.get("native_link")
            else ""
        )
        + (f"<br/>Wake: {_esc(item.get('wake'))}" if item.get("wake") else "")
        + "</p></article>"
        for item in snowcubes_surfaces
    ) or "<p class='empty'>Snowcubes sources were not collected.</p>"
    snowcubes_html = (
        "<p class='section-intro'>One read-only morning companion. Reply and relationship signals rank first; every unavailable business source is explicit rather than guessed.</p>"
        + snowcubes_cards
    )
    snowcubes_priorities = "".join(
        "<article class='story'>"
        f"<p class='meta'>Priority {rank}</p>"
        f"<h3>{_esc(item.get('name'))} · {_esc(str(item.get('state') or 'unknown').upper())}</h3>"
        f"<p>{_esc(item.get('now'))}</p><p class='meta'>{_esc(item.get('next'))}</p>"
        f"<p class='meta'>Source: {_esc(item.get('source'))} · observed {_esc(human_datetime(item.get('observed_at')))}"
        + (f"<br/>Proposal: {_esc(item.get('proposal'))}" if item.get("proposal") else "")
        + (
            f"<br/><a href='{_esc(item.get('native_link'))}' target='_blank' rel='noopener'>Open native source</a>"
            if item.get("native_link")
            else ""
        )
        + (f"<br/>Wake: {_esc(item.get('wake'))}" if item.get("wake") else "")
        + "</p></article>"
        for rank, item in enumerate(snowcubes_surfaces[:3], start=1)
    ) or "<p class='empty'>Snowcubes sources were not collected. Restore the named source before acting.</p>"
    snowcubes_coverage = "<ul class='coverage-list'>" + "".join(
        "<li>"
        f"<strong>{_esc(item.get('name'))}</strong> · {_esc(str(item.get('state') or 'unknown').upper())} — "
        f"{_esc(item.get('source'))}"
        + (
            f" · <a href='{_esc(item.get('native_link'))}' target='_blank' rel='noopener'>Open native source</a>"
            if item.get("native_link")
            else ""
        )
        + (f" · Wake: {_esc(item.get('wake'))}" if item.get("wake") else "")
        + "</li>"
        for item in snowcubes_surfaces
    ) + "</ul>" if snowcubes_surfaces else "<p class='empty'>Snowcubes sources were not collected.</p>"
    snowcubes_reader_states = {"available", "attention", "discrepancy", "unknown"}
    snowcubes_reader_surfaces = [
        item
        for item in snowcubes_surfaces
        if str(item.get("state") or "").lower() in snowcubes_reader_states
    ][:2]
    snowcubes_unavailable_n = sum(
        1
        for item in snowcubes_surfaces
        if str(item.get("state") or "").lower() == "unavailable"
    )
    snowcubes_reader_cards = "".join(
        "<article class='signal-note'>"
        f"<h3>{_esc(item.get('name'))}</h3>"
        f"<p>{_esc(item.get('now'))}</p>"
        f"<p class='meta'>{_esc(item.get('next'))}</p>"
        + (f"<p><strong>Proposal:</strong> {_esc(item.get('proposal'))}</p>" if item.get("proposal") else "")
        + (
            f"<p class='source-note'>{_esc(item.get('source'))} · <a href='{_esc(item.get('native_link'))}' target='_blank' rel='noopener'>Open native source</a> · observed {_esc(human_datetime(item.get('observed_at')))}</p>"
            if item.get("native_link")
            else f"<p class='source-note'>{_esc(item.get('source'))} · observed {_esc(human_datetime(item.get('observed_at')))}</p>"
        )
        + "</article>"
        for item in snowcubes_reader_surfaces
    )
    if not snowcubes_reader_cards:
        snowcubes_reader_cards = (
            "<p class='empty'>No current Snowcubes business signal was strong enough to elevate into the main read.</p>"
        )
    snowcubes_reader_html = (
        "<p class='essay'>Snowcubes is one workstream inside the portfolio brief. Only current business signals belong here; connector recovery and the full coverage inventory stay below as evidence.</p>"
        + snowcubes_reader_cards
        + (
            f"<p class='source-note'>{_esc(snowcubes_unavailable_n)} Snowcubes sources were unavailable in this window. Their exact recovery wakes remain in the private packet.</p>"
            if snowcubes_unavailable_n
            else "<p class='source-note'>All configured Snowcubes sources returned a readable state.</p>"
        )
    )

    evidence_html = f"""
      <p class="evidence-intro">These details support the read above. They are receipts, not a second list of work.</p>
      <div class="evidence-grid">
        <article><h3>Changes awaiting review</h3>{pr_html}</article>
        <article><h3>Background work</h3>{dirty_html}</article>
        <article><h3>Web delivery</h3>{vercel_html}</article>
        <article><h3>Data services</h3>{supabase_html}</article>
      </div>
    """

    executive_html = "".join(
        f"<p class='essay'>{_esc(paragraph)}</p>"
        for paragraph in (analysis.get("executive_read") or [summary])
    )
    material_changes_html = "".join(
        "<article class='change-note'>"
        f"<h3>{_esc(item.get('headline'))}</h3>"
        f"<p class='change-status'>{_esc(item.get('project'))} · {_esc(str(item.get('status') or 'evidence').upper())}</p>"
        f"<p><strong>What changed:</strong> {_esc(item.get('fact'))}</p>"
        f"<p class='interpretation'><strong>Why it matters:</strong> {_esc(item.get('meaning'))}</p>"
        f"<p class='source-note'>Evidence: {_esc(' · '.join(str(value) for value in (item.get('evidence') or [])))}"
        + "".join(
            f" · <a href='{_esc(link.get('url'))}' target='_blank' rel='noopener'>{_esc(link.get('label') or 'Open source')}</a>"
            for link in (item.get("links") or [])
            if isinstance(link, dict) and link.get("url")
        )
        + "</p></article>"
        for item in (analysis.get("material_changes") or [])
        if isinstance(item, dict)
    ) or "<p class='empty'>No product-level source change could be reconstructed for this window. That is an evidence gap, not proof of inactivity.</p>"
    decided_html = "".join(
        "<article class='judgment'>"
        f"<h3>{_esc(item.get('title'))}</h3>"
        f"<p class='confidence'>{_esc(str(item.get('confidence') or 'unknown').upper())} confidence</p>"
        f"<p>{_esc(item.get('prose'))}</p>"
        f"<p class='source-note'>Because: {_esc(' · '.join(str(value) for value in (item.get('evidence') or [])))}</p>"
        "</article>"
        for item in (analysis.get("decided_for_you") or [])
        if isinstance(item, dict)
    ) or "<p class='empty'>No reversible operating decision was strong enough to make in this snapshot.</p>"
    needs_leo = analysis.get("needs_leo") or {
        "requires_response": False,
        "title": "No decision needs you right now",
        "prose": "The active work can continue without a reply to this note.",
        "asks": [],
    }
    needs_leo_items = "".join(
        f"<li><strong>{_esc(item.get('project'))}</strong> — {_esc(item.get('ask'))}</li>"
        for item in (needs_leo.get("asks") or [])
        if isinstance(item, dict)
    )
    needs_leo_html = (
        "<article class='judgment'>"
        f"<h3>{_esc(needs_leo.get('title'))}</h3>"
        f"<p class='confidence'>{'RESPONSE NEEDED' if needs_leo.get('requires_response') else 'NO RESPONSE NEEDED'}</p>"
        f"<p>{_esc(needs_leo.get('prose'))}</p>"
        + (f"<ul>{needs_leo_items}</ul>" if needs_leo_items else "")
        + "</article>"
    )
    architecture_html = "".join(
        "<article class='decision-record'>"
        f"<h3>{_esc(item.get('decision'))}</h3>"
        f"<p class='project-chip'>{_esc(item.get('project'))}</p>"
        f"<p><strong>The tradeoff:</strong> {_esc(item.get('tradeoff'))}</p>"
        f"<p class='meta'>{_esc(item.get('status'))} · {_esc(item.get('evidence'))}</p>"
        "</article>"
        for item in (analysis.get("architecture_decisions") or [])
        if isinstance(item, dict)
    ) or "<p class='empty'>No current-plan architecture decision was found.</p>"
    questions_html = "".join(
        "<article class='challenge'>"
        f"<h3>{_esc(item.get('question'))}</h3>"
        f"<p>{_esc(item.get('why'))}</p>"
        "</article>"
        for item in (analysis.get("questions_to_challenge") or [])
        if isinstance(item, dict)
    ) or "<p class='empty'>No challenge is more valuable than finishing the current work.</p>"
    eta_rows = "".join(
        "<tr>"
        f"<td><strong>{_esc(item.get('project'))}</strong><br/><span>{_esc(checkpoint_title(item.get('outcome'), item.get('project')))}</span></td>"
        f"<td>{_esc(human_datetime(item.get('eta')))}<br/><small>{_esc(item.get('confidence'))} confidence</small></td>"
        f"<td>{_esc(item.get('basis'))}</td>"
        "</tr>"
        for item in (analysis.get("etas") or [])
        if isinstance(item, dict)
    )
    etas_html = (
        "<p class='section-intro'>These are evidence checkpoints. Unknown is preferable to a precise-looking guess.</p>"
        "<table class='eta-table' width='100%' cellspacing='0' cellpadding='0'>"
        "<thead><tr><th>Outcome</th><th>Next checkpoint</th><th>Basis</th></tr></thead>"
        f"<tbody>{eta_rows}</tbody></table>"
        if eta_rows
        else "<p class='empty'>No owned work has enough evidence for even a checkpoint estimate.</p>"
    )
    stalling_html = "".join(
        "<article class='stall'>"
        f"<h3>{_esc(item.get('project'))}</h3>"
        f"<p><strong>Signal:</strong> {_esc(item.get('signal'))}</p>"
        f"<p><strong>Improve it:</strong> {_esc(item.get('improvement'))}</p>"
        "</article>"
        for item in (analysis.get("stalling_lanes") or [])
        if isinstance(item, dict)
    ) or "<p class='empty'>No stalled work is important enough to elevate.</p>"

    reasoning = analysis.get("reasoning_contract") or {}
    source_flow_html = f"""
      <table class="source-flow" role="presentation" width="100%" cellspacing="0" cellpadding="0">
        <tr>
          <td><span>LIVE FACTS</span><strong>Board · code · mail · releases · data</strong><small>What changed, with freshness and source identity.</small></td>
          <td class="map-arrow">→</td>
          <td><span>RECONCILE</span><strong>Conflicts · dependencies · confidence</strong><small>Today’s active plans outrank stale context.</small></td>
          <td class="map-arrow">→</td>
          <td><span>CHIEF-OF-STAFF READ</span><strong>Decisions · challenges · ETAs</strong><small>What Leo should believe and do next.</small></td>
        </tr>
      </table>
      <p class="meta">{_esc(reasoning.get('rule') or 'Missing evidence lowers confidence; it never becomes zero activity.')}</p>
    """

    title = f"Shadow {slot.title()} Note — {human_datetime(when)}"
    report_body = (
        section("What materially changed", material_changes_html)
        + section("The chief-of-staff read", executive_html)
        + section("Decided for you", decided_html)
        + section("Needs Leo now", needs_leo_html)
        + section("Mail and calendar coverage", mail_section_html)
        + section("Architecture decisions you need to know about", architecture_html)
        + section("Questions to challenge your point of view", questions_html)
        + section("Completion outlook", etas_html)
        + section("Lanes losing momentum — and how to improve them", stalling_html)
        + section("Snowcubes in the portfolio", snowcubes_reader_html)
        + section("Evidence and blind spots", evidence_html + recovery_html)
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="icon" href="data:,"/>
<title>{_esc(title)}</title>
<style>
  :root {{
    --bg: #f6f1e8;
    --ink: #1c1915;
    --muted: #6b645a;
    --line: #d9d0c3;
    --card: #fffdf8;
    --accent: #0f5c4c;
    --soft: #e9f0ec;
    --sun: #f2dfaa;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font: 16px/1.45 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    color: var(--ink);
    background:
      radial-gradient(1200px 600px at 10% -10%, #efe6d6 0%, transparent 55%),
      radial-gradient(900px 500px at 100% 0%, #e4efe9 0%, transparent 50%),
      var(--bg);
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 32px 20px 64px; }}
  header {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: 16px;
    margin-bottom: 22px;
  }}
  h1 {{
    font-size: 36px;
    line-height: 1.15;
    margin: 8px 0 6px;
    font-weight: 700;
  }}
  .stamp {{ color: var(--muted); margin: 0 0 18px; font-size: 13px; }}
  .summary {{ font-size: 20px; line-height: 1.55; margin: 0; max-width: 36em; }}
  h2 {{
    font-size: 13px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-family: "Avenir Next", sans-serif;
    border-top: 1px solid var(--line);
    padding-top: 18px;
    margin: 28px 0 12px;
  }}
  .block {{ margin-bottom: 8px; }}
  .story {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 12px 14px;
    margin-bottom: 10px;
  }}
  .story h3 {{ margin: 0 0 6px; font-size: 18px; }}
  .story p {{ margin: 0; }}
  .essay {{ font-size: 18px; line-height: 1.65; margin: 0 0 16px; max-width: 68ch; }}
  .change-note {{
    border-top: 2px solid var(--ink);
    padding: 18px 0 20px;
  }}
  .change-note:first-child {{ border-top-width: 0; padding-top: 0; }}
  .change-note h3 {{ margin: 0 0 4px; font-size: 24px; line-height: 1.22; }}
  .change-note p {{ margin: 9px 0; max-width: 68ch; }}
  .change-status, .confidence, .project-chip {{
    color: var(--accent);
    font: 700 10px/1.3 "Avenir Next", "Segoe UI", sans-serif;
    letter-spacing: .1em;
    text-transform: uppercase;
  }}
  .interpretation {{ font-size: 17px; line-height: 1.58; }}
  .source-note {{ color: var(--muted); font-size: 13px; line-height: 1.45; }}
  .judgment, .decision-record, .challenge, .stall, .signal-note {{
    border-top: 1px solid var(--line);
    padding: 15px 0 17px;
    margin-bottom: 0;
  }}
  .judgment h3, .decision-record h3, .challenge h3, .stall h3, .signal-note h3 {{
    margin: 2px 0 8px;
    font-size: 19px;
    line-height: 1.3;
  }}
  .judgment p, .decision-record p, .challenge p, .stall p, .signal-note p {{ margin: 7px 0; }}
  .challenge {{ border-top-color: #9fbfb6; }}
  .stall {{ border-top-color: #d6b66b; }}
  .section-intro {{ color: var(--muted); }}
  .eta-table {{ border-collapse: collapse; table-layout: fixed; }}
  .eta-table th, .eta-table td {{ border-top: 1px solid var(--line); padding: 11px 8px; text-align: left; vertical-align: top; }}
  .eta-table th {{ color: var(--muted); font: 700 11px/1.2 "Avenir Next", sans-serif; letter-spacing: .08em; text-transform: uppercase; }}
  .eta-table td:first-child {{ width: 38%; }}
  .eta-table td:nth-child(2) {{ width: 24%; }}
  .eta-table small {{ color: var(--muted); }}
  .source-flow {{ table-layout: fixed; }}
  .source-flow td:not(.map-arrow) {{ width: 29%; border: 1px solid var(--line); background: var(--card); padding: 14px; vertical-align: top; }}
  .source-flow span {{ display: block; color: var(--accent); font: 700 10px/1.2 "Avenir Next", sans-serif; letter-spacing: .1em; margin-bottom: 7px; }}
  .source-flow strong, .source-flow small {{ display: block; }}
  .source-flow small {{ color: var(--muted); margin-top: 6px; line-height: 1.35; }}
  .build-loop {{ table-layout: fixed; margin-top: 12px; }}
  .build-loop td:not(.loop-arrow) {{ width: 16%; border-top: 3px solid var(--accent); background: var(--card); padding: 12px 9px; vertical-align: top; }}
  .build-loop span {{ display: block; color: var(--accent); font: 700 10px/1 "Avenir Next", sans-serif; }}
  .build-loop strong, .build-loop small {{ display: block; }}
  .build-loop small {{ color: var(--muted); line-height: 1.3; margin-top: 5px; }}
  .loop-arrow {{ width: 5%; text-align: center; color: var(--accent); }}
  .stream-table {{ border-collapse: collapse; table-layout: fixed; }}
  .stream-table th, .stream-table td {{ border-top: 1px solid var(--line); padding: 12px 8px; text-align: left; vertical-align: top; }}
  .stream-table th {{ color: var(--muted); font: 700 11px/1.2 "Avenir Next", sans-serif; letter-spacing: .08em; text-transform: uppercase; }}
  .stream-table td:first-child {{ width: 23%; }}
  .stream-table td:nth-child(2) {{ width: 16%; }}
  .stream-state {{ font: 700 10px/1.2 "Avenir Next", sans-serif; letter-spacing: .08em; text-transform: uppercase; }}
  .stream-state.moving {{ color: var(--accent); }}
  .stream-state.ready {{ color: #7b5b14; }}
  .stream-state.waiting {{ color: var(--muted); }}
  ul {{ padding-left: 1.1em; margin: 8px 0; }}
  li {{ margin: 4px 0; }}
  .meta {{ color: var(--muted); font-size: 13px; }}
  .attention-map {{ margin: 8px 0 4px; table-layout: fixed; }}
  .map-node {{
    width: 29%;
    vertical-align: top;
    background: var(--card);
    border: 1px solid var(--line);
    padding: 14px;
  }}
  .map-now {{ background: var(--soft); border-color: #b7ccc2; }}
  .map-wait {{ background: #fbf4e2; border-color: #dfc985; }}
  .map-node span {{
    display: block;
    color: var(--accent);
    font: 700 10px/1.2 "Avenir Next", "Segoe UI", sans-serif;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 7px;
  }}
  .map-node strong {{ display: block; font-size: 16px; line-height: 1.25; margin-bottom: 6px; }}
  .map-node small {{ display: block; color: var(--muted); font-size: 12px; line-height: 1.35; }}
  .map-arrow {{ width: 6.5%; text-align: center; vertical-align: middle; color: var(--accent); font-size: 22px; }}
  .evidence-intro {{ color: var(--muted); }}
  .evidence-grid article {{ border-top: 1px solid var(--line); padding: 12px 0; }}
  .evidence-grid h3 {{ margin: 0 0 6px; font-size: 16px; }}
  .quiet {{ color: var(--muted); font-style: italic; }}
  p, li, td, code {{ overflow-wrap: anywhere; }}
  ::selection {{ background: var(--sun); color: var(--ink); }}
  a {{ color: var(--accent); text-underline-offset: .16em; }}
  a:focus-visible {{ outline: 3px solid var(--accent); outline-offset: 3px; }}
  footer strong {{ color: var(--ink); }}
  footer .identity {{ display: block; margin-top: 6px; }}
  footer {{
    margin-top: 36px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 12px;
    font-family: "Avenir Next", sans-serif;
  }}
  .empty {{ color: var(--muted); font-style: italic; }}
  @media (max-width: 560px) {{
    .wrap {{ padding: 22px 14px 48px; }}
    h1 {{ font-size: 31px; }}
    .summary {{ font-size: 18px; }}
    .attention-map, .attention-map tbody, .attention-map tr {{ display: block; }}
    .map-node, .map-arrow {{ display: block; width: 100%; }}
    .map-arrow {{ padding: 2px 0; transform: rotate(90deg); }}
    .source-flow, .source-flow tbody, .source-flow tr {{ display: block; }}
    .source-flow td:not(.map-arrow), .source-flow .map-arrow {{ display: block; width: 100%; }}
    .build-loop, .build-loop tbody, .build-loop tr {{ display: block; }}
    .build-loop td:not(.loop-arrow), .build-loop .loop-arrow {{ display: block; width: 100%; }}
    .build-loop .loop-arrow {{ padding: 2px 0; transform: rotate(90deg); }}
    .stream-table, .stream-table tbody, .stream-table tr, .stream-table td {{ display: block; width: 100% !important; }}
    .stream-table thead {{ display: none; }}
    .stream-table tr {{ margin-bottom: 10px; border: 1px solid var(--line); background: var(--card); }}
    .stream-table td {{ border-top: 0; padding-top: 5px; padding-bottom: 5px; }}
    .eta-table, .eta-table tbody, .eta-table tr, .eta-table td {{ display: block; width: 100% !important; }}
    .eta-table thead {{ display: none; }}
    .eta-table tr {{ margin-bottom: 10px; border: 1px solid var(--line); background: var(--card); }}
    .eta-table td {{ border-top: 0; }}
  }}
</style>
</head>
<body>
  <!-- private machine identity: board rev {_esc(board.get('revision'))} -->
  <div class="wrap">
    <header>
      <h1>{_esc(headline)}</h1>
      <p class="stamp">{_esc(_reader_generation_marker(slot, when))}</p>
      <h2>Today’s read</h2>
      <p class="summary">{_esc(summary)}</p>
    </header>

    {report_body}

    <footer>
      <strong>Supporting checks inform the note; they do not create another to-do list.</strong>
      <span class="identity">Prepared from the current Shadow portfolio at {_esc(human_datetime(when))}. Technical identity and recovery receipts remain private.</span>
    </footer>
  </div>
</body>
</html>
"""


def write_packet(packet: dict[str, Any], out_json: Path, out_html: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    out_html.write_text(render_html(packet), encoding="utf-8")


def macos_notify(title: str, body: str) -> dict[str, Any]:
    script = f'display notification "{body.replace(chr(34), "")}" with title "{title.replace(chr(34), "")}"'
    try:
        proc = _run(["osascript", "-e", script], timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "blocked",
            "title": title,
            "body": body,
            "returncode": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "ok" if proc.returncode == 0 else "blocked",
        "title": title,
        "body": body,
        "returncode": proc.returncode,
        "error": (proc.stderr or "")[:300] or None,
    }


def scheduled_window(now: datetime | None = None) -> dict[str, Any]:
    # Verification enforces the report timezone, so the producer has to record it:
    # a run started on a host in another timezone still stamps America/New_York.
    current = now or datetime.now(REPORT_TIMEZONE)
    if current.tzinfo is None or current.utcoffset() is None:
        return {"on_schedule": False, "slot": None, "scheduled_for": None}
    current = current.astimezone(REPORT_TIMEZONE)
    on_schedule = current.hour in SLOT_HOURS and 0 <= current.minute <= 30
    scheduled = current.replace(minute=0, second=0, microsecond=0) if on_schedule else None
    return {
        "on_schedule": on_schedule,
        "slot": "morning" if current.hour == 8 else "evening" if current.hour == 20 else None,
        "scheduled_for": scheduled.isoformat(timespec="seconds") if scheduled else None,
    }


def natural_windows_are_consecutive(first: datetime, second: datetime) -> bool:
    if any(value != 0 for value in (first.minute, first.second, second.minute, second.second)):
        return False
    if not _is_report_timezone_timestamp(first) or not _is_report_timezone_timestamp(second):
        return False
    elapsed = second.astimezone(timezone.utc) - first.astimezone(timezone.utc)
    if elapsed <= timedelta(0):
        return False
    if first.hour == 8:
        return (
            second.hour == 20
            and second.date() == first.date()
            and elapsed == timedelta(hours=12)
        )
    if first.hour == 20:
        return (
            second.hour == 8
            and second.date() == first.date() + timedelta(days=1)
            and timedelta(hours=11) <= elapsed <= timedelta(hours=13)
        )
    return False


def _parse_aware_datetime(raw: Any) -> datetime | None:
    try:
        encoded = str(raw or "")
        if encoded.endswith("Z"):
            encoded = f"{encoded[:-1]}+00:00"
        value = datetime.fromisoformat(encoded)
        if value.tzinfo is None or value.utcoffset() is None:
            return None
    except (TypeError, ValueError):
        return None
    return value


def _is_report_timezone_timestamp(value: datetime) -> bool:
    if value.tzinfo is None or value.utcoffset() is None:
        return False
    local = value.astimezone(REPORT_TIMEZONE)
    return (
        (
            local.year,
            local.month,
            local.day,
            local.hour,
            local.minute,
            local.second,
            local.microsecond,
        )
        == (
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
        )
        and local.utcoffset() == value.utcoffset()
    )


def _scheduled_window_instant(row: dict[str, Any]) -> datetime | None:
    value = _parse_aware_datetime(row.get("scheduled_for"))
    if value is None or not _is_report_timezone_timestamp(value):
        return None
    return value.astimezone(timezone.utc)


def _scheduled_for_is_canonical(row: dict[str, Any]) -> bool:
    raw = row.get("scheduled_for")
    value = _parse_aware_datetime(raw)
    return bool(
        isinstance(raw, str)
        and value is not None
        and _is_report_timezone_timestamp(value)
        and value.microsecond == 0
        and raw
        == value.astimezone(REPORT_TIMEZONE).isoformat(timespec="seconds")
    )


def _eligible_natural_window_receipts(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("schema") == WINDOW_RECEIPT_SCHEMA
        and row.get("on_schedule") is True
        and row.get("trigger") == "launchd-calendar"
        and isinstance(row.get("slot"), str)
        and row.get("slot") in {"morning", "evening"}
        and _scheduled_window_instant(row) is not None
    ]


def _scheduled_window_sort_key(row: dict[str, Any]) -> datetime:
    return _scheduled_window_instant(row) or datetime.min.replace(tzinfo=timezone.utc)


def _parse_launchctl_loaded_job(output: str) -> dict[str, Any] | None:
    """Parse the three top-level identity fields emitted by launchctl print."""
    program_matches = re.findall(
        r"(?m)^[ \t]+program = ([^\r\n]+)[ \t]*$",
        output,
    )
    path_matches = re.findall(
        r"(?m)^[ \t]+path = ([^\r\n]+)[ \t]*$",
        output,
    )
    block_matches = list(
        re.finditer(r"(?m)^(?P<indent>[ \t]+)arguments = \{[ \t]*$", output)
    )
    if (
        len(program_matches) != 1
        or len(path_matches) != 1
        or len(block_matches) != 1
    ):
        return None
    block = block_matches[0]
    indent = block.group("indent")
    lines = output[block.end() :].splitlines()
    if lines and not lines[0]:
        lines.pop(0)
    arguments: list[str] = []
    closed = False
    for line in lines:
        if line == f"{indent}}}":
            closed = True
            break
        if not line.startswith(indent) or not line[len(indent) :].startswith((" ", "\t")):
            return None
        argument = line.strip()
        if not argument:
            return None
        arguments.append(argument)
    if not closed or not arguments:
        return None
    return {
        "program": program_matches[0].strip(),
        "arguments": arguments,
        "path": path_matches[0].strip(),
    }


def _expected_loaded_job() -> dict[str, Any]:
    arguments = launch_agent_plist(Path(__file__).resolve())["ProgramArguments"]
    return {
        "program": arguments[0],
        "arguments": arguments,
        "path": str(
            Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        ),
    }


def _loaded_job_matches_current(loaded: Any) -> bool:
    if not isinstance(loaded, dict):
        return False
    try:
        expected = _expected_loaded_job()
    except (OSError, RuntimeError):
        return False
    return loaded == expected


def launch_trigger_proof() -> dict[str, Any]:
    """Bind this process to the one canonical launchd job, not just its parent."""
    uid = os.getuid()
    domain = f"gui/{uid}"
    current_pid = os.getpid()
    parent_pid = os.getppid()
    probe_errors: dict[str, str] = {}
    proc: subprocess.CompletedProcess[str] | None = None
    try:
        proc = _run(["/bin/ps", "-p", str(parent_pid), "-o", "comm="], timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        probe_errors["ps"] = f"{type(exc).__name__}: {exc}"
    parent_command = (proc.stdout or "").strip() if proc is not None else ""
    xpc_service_name = os.environ.get("XPC_SERVICE_NAME")
    launchctl: subprocess.CompletedProcess[str] | None = None
    try:
        launchctl = _run(
            ["/bin/launchctl", "print", f"{domain}/{LABEL}"],
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        probe_errors["launchctl"] = f"{type(exc).__name__}: {exc}"
    pid_matches = re.findall(
        r"(?m)^[ \t]*pid = ([0-9]+)[ \t]*$",
        (launchctl.stdout or "") if launchctl is not None else "",
    )
    job_pid = int(pid_matches[0]) if len(pid_matches) == 1 else None
    loaded_job = _parse_launchctl_loaded_job(
        (launchctl.stdout or "") if launchctl is not None else ""
    )
    try:
        expected_loaded_job = _expected_loaded_job()
    except (OSError, RuntimeError) as exc:
        probe_errors["expected_job"] = f"{type(exc).__name__}: {exc}"
        loaded_command_matches = False
    else:
        loaded_command_matches = (
            isinstance(loaded_job, dict) and loaded_job == expected_loaded_job
        )
    service_matches_label = xpc_service_name == LABEL
    exact_job = bool(
        proc is not None
        and proc.returncode == 0
        and Path(parent_command).name == "launchd"
        and launchctl is not None
        and launchctl.returncode == 0
        and service_matches_label
        and job_pid == current_pid
        and loaded_command_matches
    )
    return {
        "is_launchd": bool(
            exact_job
        ),
        "parent_pid": parent_pid,
        "parent_command": parent_command or None,
        "label": LABEL,
        "domain": domain,
        "current_pid": current_pid,
        "job_pid": job_pid,
        "xpc_service_name": xpc_service_name,
        "service_matches_label": service_matches_label,
        "loaded_program": loaded_job.get("program") if loaded_job else None,
        "loaded_program_arguments": loaded_job.get("arguments") if loaded_job else None,
        "loaded_path": loaded_job.get("path") if loaded_job else None,
        "loaded_command_matches": loaded_command_matches,
        "exact_job": exact_job,
        "probe_errors": probe_errors,
    }


def scheduled_trigger_is_authorized(
    scheduled_trigger: bool,
    trigger_proof: dict[str, Any] | None,
) -> bool:
    return bool(
        scheduled_trigger
        and isinstance(trigger_proof, dict)
        and trigger_proof.get("is_launchd") is True
        and isinstance(trigger_proof.get("parent_pid"), int)
        and not isinstance(trigger_proof.get("parent_pid"), bool)
        and Path(str(trigger_proof.get("parent_command") or "")).name == "launchd"
        and trigger_proof.get("label") == LABEL
        and trigger_proof.get("domain") == f"gui/{os.getuid()}"
        and trigger_proof.get("xpc_service_name") == LABEL
        and trigger_proof.get("service_matches_label") is True
        and trigger_proof.get("loaded_command_matches") is True
        and _loaded_job_matches_current(
            {
                "program": trigger_proof.get("loaded_program"),
                "arguments": trigger_proof.get("loaded_program_arguments"),
                "path": trigger_proof.get("loaded_path"),
            }
        )
        and trigger_proof.get("exact_job") is True
        and isinstance(trigger_proof.get("current_pid"), int)
        and not isinstance(trigger_proof.get("current_pid"), bool)
        and isinstance(trigger_proof.get("job_pid"), int)
        and not isinstance(trigger_proof.get("job_pid"), bool)
        and trigger_proof.get("job_pid") == trigger_proof.get("current_pid")
    )


def _is_full_git_object_id(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value)
    )


def _valid_producer_provenance(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("schema") == PRODUCER_PROVENANCE_SCHEMA
        and _is_full_git_object_id(value.get("source_commit"))
        and isinstance(value.get("script_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", value["script_sha256"])
        and value.get("source_matches_commit") is True
    )


def _superhuman_receipt_problems(mail: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(mail, dict):
        return ["Superhuman context missing"]
    if mail.get("schema") != SUPERHUMAN_CONTEXT_SCHEMA:
        problems.append("Superhuman context schema mismatch")
    if mail.get("expected_identities") != list(EXPECTED_SUPERHUMAN_IDENTITIES):
        problems.append("expected Superhuman identity roster mismatch")
    account_discovery = mail.get("account_discovery")
    if not isinstance(account_discovery, dict):
        problems.append("Superhuman account_discovery must be an object")
        account_discovery = {}
    discovery_status = account_discovery.get("status")
    malformed_rows = account_discovery.get("malformed_rows")
    malformed_count_valid = (
        isinstance(malformed_rows, int)
        and not isinstance(malformed_rows, bool)
        and malformed_rows >= 0
    )
    if not isinstance(discovery_status, str) or discovery_status not in {
        "COMPLETE",
        "UNKNOWN",
    }:
        problems.append(
            "Superhuman account_discovery status must be COMPLETE or UNKNOWN"
        )
    if not malformed_count_valid:
        problems.append(
            "Superhuman account_discovery malformed_rows must be a nonnegative integer"
        )
    if (
        discovery_status == "COMPLETE"
        and malformed_count_valid
        and malformed_rows != 0
    ):
        problems.append(
            "COMPLETE Superhuman account discovery contains malformed rows"
        )
    discovery_unknown = bool(
        discovery_status != "COMPLETE"
        or not malformed_count_valid
        or malformed_rows != 0
    )
    discovery_wake = account_discovery.get("wake")
    if discovery_unknown and not (
        isinstance(discovery_wake, str) and discovery_wake.strip()
    ):
        problems.append("UNKNOWN Superhuman account discovery lacks exact wake")
    if discovery_unknown and (
        mail.get("status") != "UNKNOWN"
        or mail.get("complete") is not False
        or mail.get("all_clear_allowed") is not False
    ):
        problems.append("UNKNOWN Superhuman account discovery claimed an all-clear")
    linked_value = mail.get("linked_accounts")
    if not isinstance(linked_value, list):
        problems.append("Superhuman linked_accounts must be a list")
        linked_value = []
    linked_emails: list[str] = []
    for linked_row in linked_value:
        if not isinstance(linked_row, dict):
            problems.append("Superhuman linked_accounts row must be an object")
            continue
        acting_email_value = linked_row.get("acting_email")
        acting_email = (
            acting_email_value.strip().lower()
            if isinstance(acting_email_value, str)
            else ""
        )
        sender_identities = linked_row.get("sender_identities")
        valid_sender_identities = bool(
            isinstance(sender_identities, list)
            and sender_identities
            and all(
                isinstance(value, str)
                and re.fullmatch(
                    r"[^@\s]+@[^@\s]+\.[^@\s]+",
                    value.strip().lower(),
                )
                for value in sender_identities
            )
        )
        valid_row = bool(
            re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", acting_email)
            and isinstance(linked_row.get("is_primary"), bool)
            and isinstance(linked_row.get("added_at"), str)
            and valid_sender_identities
            and isinstance(linked_row.get("sender_identity_complete"), bool)
        )
        if not valid_row:
            problems.append(
                "invalid Superhuman linked_accounts row shape: "
                f"{acting_email or '<unknown>'}"
            )
            continue
        linked_emails.append(acting_email)
    action_bucket_keys = (
        "signals",
        "urgent_replies",
        "waiting_replies",
        "forgotten_obligations",
        "order_return_follow_up",
        "proactive_candidates",
        "calendar_proposals",
    )
    buckets: dict[str, list[Any]] = {}
    for key in ("coverage", *action_bucket_keys):
        value = mail.get(key)
        if not isinstance(value, list):
            problems.append(f"Superhuman {key} bucket must be a list")
            buckets[key] = []
        else:
            buckets[key] = value
    coverage = [row for row in buckets["coverage"] if isinstance(row, dict)]
    if len(coverage) != len(buckets["coverage"]):
        problems.append("Superhuman coverage row must be an object")
    for key in action_bucket_keys:
        object_rows = [row for row in buckets[key] if isinstance(row, dict)]
        if len(object_rows) != len(buckets[key]):
            problems.append(f"Superhuman {key} row must be an object")
        buckets[key] = object_rows
    coverage_emails = [
        str(row.get("acting_email") or "").strip().lower()
        for row in coverage
    ]
    linked_coverage_emails = [
        str(row.get("acting_email") or "").strip().lower()
        for row in coverage
        if row.get("linked") is True
    ]
    coverage_identity_universe = set(EXPECTED_SUPERHUMAN_IDENTITIES) | set(
        linked_emails
    )
    if (
        set(coverage_emails) != coverage_identity_universe
        or len(coverage_emails) != len(coverage_identity_universe)
    ):
        problems.append("Superhuman coverage identity universe mismatch")
    if (
        len(linked_emails) != len(set(linked_emails))
        or any(coverage_emails.count(email) != 1 for email in linked_emails)
        or any(linked_coverage_emails.count(email) != 1 for email in linked_emails)
        or set(linked_coverage_emails) != set(linked_emails)
    ):
        problems.append("linked Superhuman account coverage mismatch")
    expected_rows = [
        row
        for row in coverage
        if str(row.get("acting_email") or "").strip().lower()
        in EXPECTED_SUPERHUMAN_IDENTITIES
    ]
    covered = [str(row.get("acting_email") or "").strip().lower() for row in expected_rows]
    if (
        set(covered) != set(EXPECTED_SUPERHUMAN_IDENTITIES)
        or len(covered) != len(EXPECTED_SUPERHUMAN_IDENTITIES)
        or any(row.get("expected") is not True for row in expected_rows)
    ):
        problems.append("expected Superhuman identity coverage mismatch")

    def linked_complete_coverage(row: dict[str, Any]) -> bool:
        pagination = row.get("pagination")
        pages = pagination.get("pages") if isinstance(pagination, dict) else None
        row_problems = row.get("problems")
        return bool(
            row.get("linked") is True
            and row.get("status") == "COMPLETE"
            and isinstance(pagination, dict)
            and isinstance(pages, int)
            and not isinstance(pages, bool)
            and pages > 0
            and pagination.get("exhausted") is True
            and pagination.get("truncated") is False
            and (row_problems is None or row_problems == [])
        )

    unknown_coverage = len(expected_rows) != len(EXPECTED_SUPERHUMAN_IDENTITIES)
    for row in expected_rows:
        linked = row.get("linked")
        status_value = row.get("status")
        row_problems = row.get("problems")
        wake = row.get("wake")
        linked_complete = linked_complete_coverage(row)
        honest_unknown = (
            (linked is True or linked is False)
            and status_value == "UNKNOWN"
            and isinstance(row_problems, list)
            and bool(row_problems)
            and all(
                isinstance(problem, str) and problem.strip()
                for problem in row_problems
            )
            and isinstance(wake, str)
            and bool(wake.strip())
        )
        if not linked_complete and not honest_unknown:
            identity = str(row.get("acting_email") or "").strip().lower()
            problems.append(
                f"invalid expected Superhuman identity coverage state: {identity}"
            )
        if not linked_complete:
            unknown_coverage = True
    dynamic_linked_rows = [
        row
        for row in coverage
        if str(row.get("acting_email") or "").strip().lower() in linked_emails
        and str(row.get("acting_email") or "").strip().lower()
        not in EXPECTED_SUPERHUMAN_IDENTITIES
    ]
    for row in dynamic_linked_rows:
        identity = str(row.get("acting_email") or "").strip().lower()
        if row.get("expected") is not False:
            problems.append(
                "dynamic linked Superhuman identity expected marker mismatch: "
                f"{identity}"
            )
        row_problems = row.get("problems")
        wake = row.get("wake")
        linked_complete = linked_complete_coverage(row)
        honest_unknown = bool(
            row.get("linked") is True
            and row.get("status") == "UNKNOWN"
            and isinstance(row_problems, list)
            and row_problems
            and all(
                isinstance(problem, str) and problem.strip()
                for problem in row_problems
            )
            and isinstance(wake, str)
            and wake.strip()
        )
        if not linked_complete and not honest_unknown:
            problems.append(
                f"invalid linked Superhuman identity coverage state: {identity}"
            )
        if not linked_complete:
            unknown_coverage = True
    if unknown_coverage and (
        mail.get("status") != "UNKNOWN"
        or mail.get("complete") is not False
        or mail.get("all_clear_allowed") is not False
    ):
        problems.append("UNKNOWN mail coverage claimed an all-clear")
    obligation_keys = (
        "forgotten_obligations",
        "urgent_replies",
        "waiting_replies",
        "order_return_follow_up",
    )
    linked_source_identities = set(linked_coverage_emails)

    def valid_obligation(signal: Any) -> bool:
        if not isinstance(signal, dict):
            return False
        signal_id = signal.get("signal_id")
        subject = signal.get("subject")
        proposal = signal.get("proposal")
        action_tags = signal.get("action_tags")
        source_identities = signal.get("source_identities")
        thread_id = signal.get("thread_id")
        message_id = signal.get("last_message_id")
        return bool(
            signal.get("stable_provider_identity") is True
            and signal.get("semantic_status") == "PROPOSAL"
            and signal.get("thread_body_read") is True
            and signal.get("proposal_only") is True
            and isinstance(signal_id, str)
            and signal_id.strip()
            and isinstance(subject, str)
            and subject.strip()
            and isinstance(proposal, str)
            and proposal.strip()
            and isinstance(action_tags, list)
            and action_tags
            and all(isinstance(tag, str) and tag.strip() for tag in action_tags)
            and isinstance(source_identities, list)
            and source_identities
            and all(
                isinstance(identity, str) and identity.strip()
                for identity in source_identities
            )
            and {
                identity.strip().lower()
                for identity in source_identities
                if isinstance(identity, str)
            }.issubset(linked_source_identities)
            and (
                isinstance(thread_id, str) and bool(thread_id.strip())
                or isinstance(message_id, str) and bool(message_id.strip())
            )
        )

    master_signals = [
        signal for signal in buckets["signals"] if valid_obligation(signal)
    ]

    def retained_by_master(signal: dict[str, Any]) -> bool:
        for master in master_signals:
            if signal["signal_id"] == master["signal_id"]:
                return True
            for key in ("thread_id", "last_message_id"):
                identity = signal.get(key)
                if (
                    isinstance(identity, str)
                    and identity.strip()
                    and identity == master.get(key)
                ):
                    return True
        return False

    def matches_obligation_bucket(key: str, signal: dict[str, Any]) -> bool:
        tags = set(signal.get("action_tags") or [])
        if key == "urgent_replies":
            return "urgent" in tags and bool(tags & {"reply", "waiting_reply"})
        if key == "waiting_replies":
            return "waiting_reply" in tags
        if key == "order_return_follow_up":
            return "order_return" in tags
        if key == "forgotten_obligations":
            return bool(
                tags
                & {
                    "obligation",
                    "order_return",
                    "waiting_reply",
                    "reply",
                    "calendar",
                }
            )
        return False

    real_obligation = any(
        valid_obligation(signal)
        and retained_by_master(signal)
        and matches_obligation_bucket(key, signal)
        for key in obligation_keys
        for signal in buckets[key]
        if isinstance(signal, dict)
    )
    if not real_obligation:
        problems.append("no real mail obligation or action proposal")
    return problems


def _scheduled_archive_stem(row: dict[str, Any]) -> str | None:
    scheduled = _parse_aware_datetime(row.get("scheduled_for"))
    if scheduled is None or not _is_report_timezone_timestamp(scheduled):
        return None
    return scheduled.astimezone(REPORT_TIMEZONE).strftime("%Y%m%d-%H%M%S")


def _declared_archive_path(
    evidence_dir: Path,
    row: dict[str, Any],
    *,
    key: str,
    suffix: str,
) -> Path | None:
    stem = _scheduled_archive_stem(row)
    if stem is None:
        return None
    root = evidence_dir.resolve()
    declared = Path(str(row.get(key) or ""))
    if (
        not declared.is_absolute()
        or declared.name != f"brief-{stem}{suffix}"
        or declared.parent.resolve() != root
        or declared.is_symlink()
    ):
        return None
    try:
        identity = declared.lstat()
    except OSError:
        return None
    if (
        not stat.S_ISREG(identity.st_mode)
        or stat.S_IMODE(identity.st_mode) != 0o400
        or identity.st_nlink != 1
    ):
        return None
    return declared


def _scheduled_attempt_barrier_is_valid(
    ledger_dir: Path,
    row: dict[str, Any],
) -> bool:
    stem = _scheduled_archive_stem(row)
    receipt = row.get("attempt_barrier")
    if stem is None or not isinstance(receipt, dict):
        return False
    root = ledger_dir.absolute()
    expected = root / f"scheduled-attempt-{stem}.json"
    declared = Path(str(receipt.get("path") or ""))
    if (
        receipt.get("state") != "PRESENT"
        or not declared.is_absolute()
        or declared != expected
        or declared.parent != root
        or declared.is_symlink()
    ):
        return False
    flags = os.O_RDONLY | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(declared, flags)
        identity = os.fstat(descriptor)
        named_identity = os.lstat(declared)
        if (
            not stat.S_ISREG(identity.st_mode)
            or stat.S_IMODE(identity.st_mode) != 0o400
            or identity.st_nlink != 1
            or stat.S_ISLNK(named_identity.st_mode)
            or (identity.st_dev, identity.st_ino)
            != (named_identity.st_dev, named_identity.st_ino)
        ):
            return False
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = None
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return bool(
        isinstance(payload, dict)
        and payload.get("schema") == SCHEDULED_ATTEMPT_SCHEMA
        and payload.get("state") == "RESERVED"
        and payload.get("scheduled_for") == row.get("scheduled_for")
        and payload.get("slot") == row.get("slot")
    )


def _read_send_attempt_proof(path: Path) -> list[dict[str, Any]] | None:
    flags = os.O_RDONLY | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        identity = os.fstat(descriptor)
        named_identity = os.lstat(path)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != os.getuid()
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
            or stat.S_ISLNK(named_identity.st_mode)
            or (identity.st_dev, identity.st_ino)
            != (named_identity.st_dev, named_identity.st_ino)
        ):
            return None
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = None
            text = handle.read()
    except (OSError, UnicodeError):
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, RecursionError):
            return None
        if not isinstance(row, dict):
            return None
        rows.append(row)
    return rows or None


def _send_attempt_proof_is_valid(
    row: dict[str, Any],
    archive_html: Path,
    attempt_rows: list[dict[str, Any]] | None,
) -> bool:
    receipt = row.get("receipt")
    if not isinstance(receipt, dict) or attempt_rows is None:
        return False
    attempt_id = receipt.get("attempt_id")
    if not (
        isinstance(attempt_id, str)
        and re.fullmatch(r"[0-9a-f]{24}", attempt_id)
    ):
        return False
    matching = [candidate for candidate in attempt_rows if candidate.get("attempt_id") == attempt_id]
    if (
        len(matching) != 2
        or matching[0].get("state") != "UNKNOWN_NO_RETRY"
        or matching[1].get("state") != "PROVISIONAL_SENT"
    ):
        return False
    intent, outcome = matching
    intent_keys = {
        "schema",
        "state",
        "created_at",
        "attempt_id",
        "acting_email",
        "from",
        "to",
        "subject",
        "draft_id",
        "thread_id",
        "html_sha256",
    }
    outcome_keys = {
        "schema",
        "state",
        "recorded_at",
        "attempt_id",
        "message_id",
        "thread_id",
        "sent_at",
    }
    if set(intent) != intent_keys or set(outcome) != outcome_keys:
        return False
    identity = dict(intent)
    identity.pop("attempt_id")
    recomputed_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    generated = _parse_aware_datetime(row.get("generated_at"))
    created = _parse_aware_datetime(intent.get("created_at"))
    recorded = _parse_aware_datetime(outcome.get("recorded_at"))
    sent = _parse_aware_datetime(outcome.get("sent_at"))
    intent_thread_id = intent.get("thread_id")
    outcome_thread_id = outcome.get("thread_id")
    receipt_thread_id = receipt.get("thread_id")
    optional_thread_ids_are_valid = all(
        value is None or (isinstance(value, str) and bool(value.strip()))
        for value in (intent_thread_id, outcome_thread_id, receipt_thread_id)
    )
    return bool(
        intent.get("schema") == SEND_ATTEMPT_SCHEMA
        and outcome.get("schema") == SEND_ATTEMPT_SCHEMA
        and recomputed_id == attempt_id
        and intent.get("acting_email") == SELF_MAIL
        and intent.get("from") == SELF_MAIL
        and intent.get("to") == [SELF_MAIL]
        and intent.get("subject") == receipt.get("subject")
        and intent.get("draft_id") == receipt.get("draft_id")
        and isinstance(intent.get("draft_id"), str)
        and bool(intent["draft_id"].strip())
        and isinstance(intent.get("html_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", intent["html_sha256"])
        and intent.get("html_sha256") == row.get("html_sha256")
        and receipt.get("local_html") == str(archive_html)
        and receipt.get("attempt_state") == "PROVISIONAL_SENT"
        and receipt.get("acting_email") == SELF_MAIL
        and receipt.get("from") == SELF_MAIL
        and receipt.get("to") == [SELF_MAIL]
        and isinstance(outcome.get("message_id"), str)
        and bool(outcome["message_id"].strip())
        and isinstance(receipt.get("message_id"), str)
        and bool(receipt["message_id"].strip())
        and optional_thread_ids_are_valid
        and outcome.get("message_id") == receipt.get("message_id")
        and outcome.get("thread_id") == receipt.get("thread_id")
        and outcome.get("sent_at") == receipt.get("sent_at")
        and generated is not None
        and created is not None
        and recorded is not None
        and sent is not None
        and generated <= created <= recorded
        and created <= sent
    )


def verify_window_receipts(
    rows: list[dict[str, Any]],
    *,
    evidence_dir: Path | None = None,
    ledger_dir: Path | None = None,
    send_attempt_log: Path | None = None,
) -> dict[str, Any]:
    scheduled = [
        row
        for row in rows
        if row.get("on_schedule") is True and row.get("scheduled_for")
    ]
    ignored_legacy = [
        str(row["scheduled_for"])
        for row in scheduled
        if row.get("schema") != WINDOW_RECEIPT_SCHEMA
    ]
    ignored_noncalendar = [
        str(row["scheduled_for"])
        for row in scheduled
        if row.get("schema") == WINDOW_RECEIPT_SCHEMA
        and row.get("trigger") != "launchd-calendar"
    ]
    ignored_nonslot = [
        str(row["scheduled_for"])
        for row in scheduled
        if row.get("schema") == WINDOW_RECEIPT_SCHEMA
        and row.get("trigger") == "launchd-calendar"
        and (
            not isinstance(row.get("slot"), str)
            or row.get("slot") not in {"morning", "evening"}
        )
    ]
    eligible = _eligible_natural_window_receipts(scheduled)
    receipts_by_window: dict[datetime, list[dict[str, Any]]] = {}
    for row in eligible:
        scheduled_instant = _scheduled_window_instant(row)
        if scheduled_instant is not None:
            receipts_by_window.setdefault(scheduled_instant, []).append(row)
    selected_groups = sorted(
        receipts_by_window.values(),
        key=lambda group: _scheduled_window_sort_key(group[-1]),
    )[-2:]
    latest = [group[-1] for group in selected_groups]
    problems: list[str] = []
    for group in selected_groups:
        for candidate in group:
            if not _scheduled_for_is_canonical(candidate):
                raw = str(candidate.get("scheduled_for") or "")
                problems.append(
                    f"{raw}: scheduled_for is not a canonical report-window timestamp"
                )
        if len(group) > 1:
            instant = _scheduled_window_instant(group[-1])
            label = (
                instant.astimezone(REPORT_TIMEZONE).isoformat(timespec="seconds")
                if instant is not None
                else str(group[-1].get("scheduled_for") or "")
            )
            problems.append(f"{label}: duplicate natural-window receipts found")
    attempt_rows = (
        _read_send_attempt_proof(send_attempt_log)
        if send_attempt_log is not None
        else None
    )
    if len(latest) != 2:
        problems.append(
            f"need two distinct current-schema natural 08:00/20:00 windows; found {len(latest)}"
        )
    else:
        first = datetime.fromisoformat(str(latest[0]["scheduled_for"]))
        second = datetime.fromisoformat(str(latest[1]["scheduled_for"]))
        if not natural_windows_are_consecutive(first, second):
            problems.append("latest natural 08:00/20:00 windows are not consecutive")
        for row in latest:
            scheduled_for = str(row["scheduled_for"])
            receipt_value = row.get("receipt")
            if not isinstance(receipt_value, dict):
                problems.append(f"{scheduled_for}: receipt must be an object")
                receipt: dict[str, Any] = {}
            else:
                receipt = receipt_value
            notification_value = row.get("notification")
            if not isinstance(notification_value, dict):
                problems.append(f"{scheduled_for}: notification must be an object")
                notification: dict[str, Any] = {}
            else:
                notification = notification_value
            if ledger_dir is not None and not _scheduled_attempt_barrier_is_valid(
                ledger_dir,
                row,
            ):
                problems.append(
                    f"{scheduled_for}: scheduled attempt barrier is invalid"
                )
            if not scheduled_trigger_is_authorized(True, row.get("trigger_proof")):
                problems.append(f"{scheduled_for}: launchd trigger proof missing")
            scheduled_at = _parse_aware_datetime(scheduled_for)
            generated = _parse_aware_datetime(row.get("generated_at"))
            if scheduled_at is None or generated is None:
                problems.append(f"{scheduled_for}: generated_at invalid")
            else:
                expected_slot = "morning" if scheduled_at.hour == 8 else "evening"
                if row.get("slot") != expected_slot:
                    problems.append(f"{scheduled_for}: scheduled slot mismatch")
                if not scheduled_at <= generated <= scheduled_at + timedelta(minutes=30):
                    problems.append(f"{scheduled_for}: report generation is not fresh for slot")
            if not (
                isinstance(row.get("board_revision"), int)
                and not isinstance(row.get("board_revision"), bool)
            ):
                problems.append(f"{scheduled_for}: missing board revision")
            if len(str(row.get("html_sha256") or "")) != 64:
                problems.append(f"{scheduled_for}: missing HTML hash")
            if len(str(row.get("json_sha256") or "")) != 64:
                problems.append(f"{scheduled_for}: missing JSON hash")
            if not _valid_producer_provenance(row.get("producer")):
                problems.append(f"{scheduled_for}: runtime producer provenance missing")
            if notification.get("status") != "ok":
                problems.append(f"{scheduled_for}: notification failed")
            if (
                notification.get("title") != "Shadow brief ready"
                or notification.get("body")
                != f"{row.get('slot')} · board rev {row.get('board_revision')}"
            ):
                problems.append(f"{scheduled_for}: notification identity mismatch")
            message_id = receipt.get("message_id")
            if (
                receipt.get("status") != "ok"
                or receipt.get("delivery_status") != "sent"
                or not isinstance(message_id, str)
                or not message_id.strip()
            ):
                problems.append(f"{scheduled_for}: sent-message receipt missing")
            attempt_id = receipt.get("attempt_id")
            if (
                receipt.get("attempt_state") != "PROVISIONAL_SENT"
                or not isinstance(attempt_id, str)
                or re.fullmatch(r"[0-9a-f]{24}", attempt_id) is None
            ):
                problems.append(f"{scheduled_for}: durable pre-send attempt receipt missing")
            if (
                receipt.get("acting_email") != SELF_MAIL
                or receipt.get("from") != SELF_MAIL
                or receipt.get("to") != [SELF_MAIL]
            ):
                problems.append(f"{scheduled_for}: exact self-mail route missing")
            expected_subject = brief_subject(row.get("slot"), row.get("generated_at"))
            if receipt.get("subject") != expected_subject:
                problems.append(f"{scheduled_for}: sent-message subject mismatch")
            sent_at = _parse_aware_datetime(receipt.get("sent_at"))
            if sent_at is None:
                problems.append(f"{scheduled_for}: sent timestamp invalid")
            elif (
                scheduled_at is None
                or generated is None
                or not generated <= sent_at <= scheduled_at + timedelta(minutes=30)
            ):
                problems.append(f"{scheduled_for}: sent timestamp is not fresh for slot")
            paint_health = row.get("paint_health")
            if not isinstance(paint_health, dict):
                problems.append(f"{row['scheduled_for']}: missing paint health")
            else:
                for source in ("local_git", "github", "vercel"):
                    health = paint_health.get(source)
                    if not isinstance(health, dict) or not isinstance(health.get("available"), bool):
                        problems.append(f"{row['scheduled_for']}: missing {source} paint health")
                    elif not health.get("available") and not health.get("wake"):
                        problems.append(f"{source} paint unavailable without exact wake")
        sent_message_ids = [
            receipt.get("message_id") if isinstance(receipt := row.get("receipt"), dict) else None
            for row in latest
        ]
        if (
            all(
                isinstance(value, str) and bool(value.strip())
                for value in sent_message_ids
            )
            and len(set(sent_message_ids)) != len(sent_message_ids)
        ):
            problems.append("scheduled windows do not have distinct sent-message receipts")
        attempt_ids = [
            receipt.get("attempt_id") if isinstance(receipt := row.get("receipt"), dict) else None
            for row in latest
        ]
        if (
            all(
                isinstance(value, str)
                and re.fullmatch(r"[0-9a-f]{24}", value) is not None
                for value in attempt_ids
            )
            and len(set(attempt_ids)) != len(attempt_ids)
        ):
            problems.append("scheduled windows do not have distinct send-attempt receipts")
        if evidence_dir is not None:
            archive_pairs: list[tuple[Path, Path]] = []
            for row in latest:
                scheduled_for = str(row["scheduled_for"])
                archive = _declared_archive_path(
                    evidence_dir,
                    row,
                    key="archive_html",
                    suffix=".html",
                )
                if archive is None:
                    problems.append(f"{scheduled_for}: declared archived HTML is invalid")
                    continue
                json_archive = _declared_archive_path(
                    evidence_dir,
                    row,
                    key="archive_json",
                    suffix=".json",
                )
                if json_archive is None:
                    problems.append(f"{scheduled_for}: declared archived JSON is invalid")
                    continue
                archive_pairs.append((archive, json_archive))
                try:
                    html_bytes = archive.read_bytes()
                except OSError:
                    problems.append(f"{scheduled_for}: archived HTML unreadable")
                    continue
                if hashlib.sha256(html_bytes).hexdigest() != row.get("html_sha256"):
                    problems.append(f"{scheduled_for}: declared archived HTML hash mismatch")
                    continue
                if send_attempt_log is not None and not _send_attempt_proof_is_valid(
                    row,
                    archive,
                    attempt_rows,
                ):
                    problems.append(
                        f"{scheduled_for}: scheduled send attempt ledger proof is invalid"
                    )
                try:
                    rendered = html_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    problems.append(f"{scheduled_for}: archived HTML unreadable")
                    continue
                if f"board rev {row.get('board_revision')}" not in rendered:
                    problems.append(f"{scheduled_for}: archived HTML board revision mismatch")
                generation_marker = _reader_generation_marker(
                    row.get("slot"),
                    row.get("generated_at"),
                )
                if not generation_marker or generation_marker not in rendered:
                    problems.append(
                        f"{scheduled_for}: archived HTML generation marker mismatch"
                    )
                required_html = (
                    "<!DOCTYPE html>",
                    'name="viewport"',
                    "Today’s read",
                    "What materially changed",
                    "The chief-of-staff read",
                    "Decided for you",
                    "Needs Leo now",
                    "Architecture decisions you need to know about",
                    "Questions to challenge your point of view",
                    "Completion outlook",
                    "Lanes losing momentum — and how to improve them",
                    "Snowcubes in the portfolio",
                    "Evidence and blind spots",
                    "Supporting checks inform the note; they do not create another to-do list.",
                )
                if any(marker not in rendered for marker in required_html):
                    problems.append(f"{scheduled_for}: archived HTML missing report structure")
                if rendered.count("<h2>Mail and calendar coverage</h2>") != 1:
                    problems.append(
                        f"{scheduled_for}: archived HTML must contain exactly one Mail and calendar coverage section"
                    )
                try:
                    json_bytes = json_archive.read_bytes()
                except OSError:
                    problems.append(f"{scheduled_for}: archived JSON unreadable")
                    continue
                if hashlib.sha256(json_bytes).hexdigest() != row.get("json_sha256"):
                    problems.append(f"{scheduled_for}: declared archived JSON hash mismatch")
                    continue
                try:
                    packet = json.loads(json_bytes.decode("utf-8"))
                except (UnicodeDecodeError, ValueError, RecursionError):
                    problems.append(f"{scheduled_for}: archived JSON unreadable")
                    continue
                if not isinstance(packet, dict):
                    problems.append(
                        f"{scheduled_for}: archived JSON root must be an object"
                    )
                    continue
                if packet.get("generated_at") != row.get("generated_at"):
                    problems.append(f"{scheduled_for}: archived JSON generation mismatch")
                board = packet.get("board")
                if not isinstance(board, dict):
                    problems.append(
                        f"{scheduled_for}: archived JSON board must be an object"
                    )
                elif not (
                    isinstance(board.get("revision"), int)
                    and not isinstance(board.get("revision"), bool)
                    and board.get("revision") == row.get("board_revision")
                ):
                    problems.append(
                        f"{scheduled_for}: archived JSON board revision mismatch"
                    )
                authority = packet.get("authority")
                board_snapshot: Any = None
                if not isinstance(authority, dict):
                    problems.append(
                        f"{scheduled_for}: archived JSON authority must be an object"
                    )
                else:
                    board_snapshot = authority.get("board_snapshot")
                if not isinstance(board_snapshot, dict) or (
                    board_snapshot.get("consistent") is not True
                    or not isinstance(board_snapshot.get("revision"), int)
                    or isinstance(board_snapshot.get("revision"), bool)
                    or board_snapshot.get("revision") != row.get("board_revision")
                ):
                    problems.append(f"{scheduled_for}: board snapshot consistency missing")
                if (packet.get("paint_health") or {}) != (row.get("paint_health") or {}):
                    problems.append(f"{scheduled_for}: archived JSON paint health mismatch")
                packet_producer = packet.get("producer")
                if (
                    not _valid_producer_provenance(packet_producer)
                    or packet_producer != row.get("producer")
                ):
                    problems.append(f"{scheduled_for}: archived producer provenance mismatch")
                problems.extend(
                    f"{scheduled_for}: {problem}"
                    for problem in _superhuman_receipt_problems(
                        packet.get("superhuman_context")
                    )
                )
            flattened = [path for pair in archive_pairs for path in pair]
            if len(flattened) != len(set(flattened)):
                problems.append("natural windows do not have distinct immutable archives")
    return {
        "ok": not problems,
        "problems": problems,
        "windows": [row.get("scheduled_for") for row in latest],
        "message_ids": [
            receipt.get("message_id") if isinstance(receipt := row.get("receipt"), dict) else None
            for row in latest
        ],
        "ignored_legacy_windows": ignored_legacy,
        "ignored_noncalendar_windows": ignored_noncalendar,
        "ignored_nonslot_windows": ignored_nonslot,
    }


def verify_mailbox_readbacks(
    windows: list[dict[str, Any]],
    readbacks: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_by_window = {
        str(row.get("scheduled_for")): row
        for row in readbacks
        if row.get("schema") == MAILBOX_READBACK_SCHEMA
        and row.get("status") == "EXACT_SENT_CONFIRMED"
        and row.get("scheduled_for")
    }
    problems: list[str] = []
    confirmed: list[dict[str, Any]] = []
    for window in windows:
        scheduled_for = str(window.get("scheduled_for") or "")
        window_receipt_value = window.get("receipt")
        if not isinstance(window_receipt_value, dict):
            problems.append(f"{scheduled_for}: window receipt must be an object")
            window_receipt: dict[str, Any] = {}
        else:
            window_receipt = window_receipt_value
        readback = latest_by_window.get(scheduled_for)
        if readback is None or readback.get("status") != "EXACT_SENT_CONFIRMED":
            problems.append(f"{scheduled_for}: exact mailbox readback missing")
            continue
        confirmed.append(readback)
        if (
            readback.get("acting_email") != SELF_MAIL
            or readback.get("from") != SELF_MAIL
            or readback.get("to") != [SELF_MAIL]
        ):
            problems.append(f"{scheduled_for}: mailbox self-route mismatch")
        if readback.get("subject") != window_receipt.get("subject"):
            problems.append(f"{scheduled_for}: mailbox subject mismatch")
        if readback.get("generated_at") != window.get("generated_at"):
            problems.append(f"{scheduled_for}: mailbox generation mismatch")
        window_revision = window.get("board_revision")
        readback_revision = readback.get("board_revision")
        if not (
            isinstance(window_revision, int)
            and not isinstance(window_revision, bool)
            and isinstance(readback_revision, int)
            and not isinstance(readback_revision, bool)
        ):
            problems.append(f"{scheduled_for}: mailbox board revision invalid")
        elif readback_revision != window_revision:
            problems.append(f"{scheduled_for}: mailbox board revision mismatch")
        message_id = readback.get("message_id")
        thread_id = readback.get("thread_id")
        if not (
            isinstance(message_id, str)
            and message_id.strip()
            and isinstance(thread_id, str)
            and thread_id.strip()
        ):
            problems.append(f"{scheduled_for}: stable mailbox identity missing")
        labels = readback.get("labels")
        if not (
            isinstance(labels, list)
            and all(isinstance(label, str) for label in labels)
        ):
            problems.append(f"{scheduled_for}: mailbox labels must be a string list")
        elif "SENT" not in labels:
            problems.append(f"{scheduled_for}: SENT label missing")
        raw_html_sha256 = readback.get("raw_html_sha256")
        if not (
            isinstance(raw_html_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", raw_html_sha256)
        ):
            problems.append(f"{scheduled_for}: mailbox HTML hash missing")
        scheduled_at = _parse_aware_datetime(scheduled_for)
        sent_at = _parse_aware_datetime(readback.get("sent_at"))
        if scheduled_at is None or sent_at is None:
            problems.append(f"{scheduled_for}: mailbox sent timestamp invalid")
        elif not scheduled_at <= sent_at <= scheduled_at + timedelta(minutes=30):
            problems.append(f"{scheduled_for}: mailbox sent timestamp is not fresh")
    message_ids = [row.get("message_id") for row in confirmed]
    if (
        len(message_ids) == len(windows)
        and all(
            isinstance(value, str) and bool(value.strip())
            for value in message_ids
        )
        and len(set(message_ids)) != len(message_ids)
    ):
        problems.append("mailbox readbacks do not have distinct message IDs")
    return {
        "ok": not problems,
        "problems": problems,
        "message_ids": message_ids,
    }


def append_scheduled_window(
    summary: dict[str, Any],
    *,
    scheduled_trigger: bool = False,
    now: datetime | None = None,
    window: dict[str, Any] | None = None,
) -> None:
    if not scheduled_trigger_is_authorized(scheduled_trigger, summary.get("trigger_proof")):
        return
    # Record the window this run was admitted under, not the window it happens to
    # finish in; a send that crosses minute 30 must still leave a durable receipt.
    if window is None:
        recorded_window = summary.get("scheduled_window")
        if isinstance(recorded_window, dict) and recorded_window.get("scheduled_for"):
            # Keep the launchd slot captured before collection/delivery. Delivery may
            # finish after minute 30, but it still belongs to the accepted trigger.
            window = {
                "on_schedule": True,
                "slot": recorded_window.get("slot"),
                "scheduled_for": recorded_window.get("scheduled_for"),
            }
        else:
            window = scheduled_window(now)
    if not window.get("on_schedule"):
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    row = {**window, "trigger": "launchd-calendar", **summary}
    _append_private_jsonl(WINDOW_LOG, row)


def _refresh_mcp_remote_token(token_path: Path, tokens: dict[str, Any]) -> str | None:
    import urllib.error
    import urllib.parse
    import urllib.request

    prefix = token_path.name.removesuffix("_tokens.json")
    client_path = token_path.with_name(f"{prefix}_client_info.json")
    try:
        client = json.loads(client_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    refresh_token = tokens.get("refresh_token")
    client_id = client.get("client_id")
    if not refresh_token or not client_id:
        return None
    form = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": str(refresh_token),
            "client_id": str(client_id),
            "resource": SUPERHUMAN_MCP_RESOURCE,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        SUPERHUMAN_TOKEN_ENDPOINT,
        data=form,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            fresh = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    access_token = fresh.get("access_token") if isinstance(fresh, dict) else None
    if not access_token:
        return None
    saved = {"refresh_token": refresh_token, **fresh}
    tmp = token_path.with_name(f".{token_path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(token_path)
    except OSError:
        tmp.unlink(missing_ok=True)
        return None
    return str(access_token)


def _mcp_remote_token() -> str | None:
    auth_root = Path.home() / ".mcp-auth"
    if not auth_root.is_dir():
        return None
    tokens = sorted(
        auth_root.glob(f"mcp-remote-*/{SUPERHUMAN_MCP_CACHE_KEY}_tokens.json")
    )
    if not tokens:
        return None
    try:
        token_path = max(tokens, key=lambda path: (path.stat().st_mtime_ns, str(path)))
        data = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    tok = data.get("access_token")
    expires_in = data.get("expires_in")
    if (
        tok
        and data.get("refresh_token")
        and isinstance(expires_in, (int, float))
    ):
        expires_at = token_path.stat().st_mtime + float(expires_in)
        if time.time() >= expires_at - 300:
            refreshed = _refresh_mcp_remote_token(token_path, data)
            if refreshed:
                return refreshed
            if time.time() >= expires_at:
                return None
    return str(tok) if tok else None


def _parse_mcp_sse(raw: str) -> dict[str, Any]:
    chunks = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
    if not chunks:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"raw": raw[:500]}
        except (ValueError, RecursionError):
            return {"raw": raw[:500]}
    for chunk in reversed(chunks):
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, RecursionError):
            continue
    return {"raw": "\n".join(chunks)[:800]}


def _mcp_text_payload(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    envelope = result.get("result")
    if not isinstance(envelope, dict):
        return {}
    content = envelope.get("content")
    if not isinstance(content, list):
        return {}
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            payload = json.loads(text)
        except (ValueError, RecursionError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _append_private_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = os.open(path, flags, 0o600)
    identity: os.stat_result | None = None
    try:
        identity = os.fstat(descriptor)
        named_identity = os.lstat(path)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != os.getuid()
            or identity.st_nlink != 1
            or stat.S_ISLNK(named_identity.st_mode)
            or named_identity.st_uid != os.getuid()
            or named_identity.st_nlink != 1
            or (identity.st_dev, identity.st_ino)
            != (named_identity.st_dev, named_identity.st_ino)
        ):
            raise PermissionError(f"unsafe private JSONL identity: {path}")
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "a", encoding="utf-8")
        descriptor = None
        with handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        named_identity = os.lstat(path)
        if (
            not stat.S_ISREG(named_identity.st_mode)
            or named_identity.st_uid != os.getuid()
            or named_identity.st_nlink != 1
            or (identity.st_dev, identity.st_ino)
            != (named_identity.st_dev, named_identity.st_ino)
        ):
            raise PermissionError(f"private JSONL identity changed while appending: {path}")
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    _fsync_directory(path.parent)


def record_send_attempt(
    html_path: Path,
    *,
    subject: str,
    draft_id: str,
    thread_id: str | None,
) -> dict[str, Any]:
    _read_jsonl(SEND_ATTEMPT_LOG)
    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    intent = {
        "schema": SEND_ATTEMPT_SCHEMA,
        "state": "UNKNOWN_NO_RETRY",
        "created_at": created_at,
        "acting_email": SELF_MAIL,
        "from": SELF_MAIL,
        "to": [SELF_MAIL],
        "subject": subject,
        "draft_id": draft_id,
        "thread_id": thread_id,
        "html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
    }
    intent["attempt_id"] = hashlib.sha256(
        json.dumps(intent, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    _append_private_jsonl(SEND_ATTEMPT_LOG, intent)
    return intent


def ambiguous_send_receipt(
    attempt: dict[str, Any],
    *,
    subject: str,
    notes: str,
) -> dict[str, Any]:
    thread_id = attempt.get("thread_id")
    return {
        "status": "unknown",
        "delivery_status": "unknown_no_retry",
        "attempt_state": "UNKNOWN_NO_RETRY",
        "attempt_id": attempt.get("attempt_id"),
        "draft_id": attempt.get("draft_id"),
        "thread_id": thread_id,
        "acting_email": SELF_MAIL,
        "from": SELF_MAIL,
        "to": [SELF_MAIL],
        "subject": subject,
        "sent_at": None,
        "notes": notes,
        "wake": (
            f"read-only list_threads as {SELF_MAIL} with labels=[SENT], exact "
            f"subject_contains={subject!r}, from/to={SELF_MAIL}, and the attempt time bound; "
            "require one candidate, then exact get_thread and get_message with "
            "include_raw_html=true; never retry send_draft"
        ),
    }


def _delivery_exception_receipt(subject: str, exc: Exception) -> dict[str, Any]:
    attempt: dict[str, Any] | None = None
    attempt_ledger_error: Exception | None = None
    try:
        for candidate in reversed(_read_jsonl(SEND_ATTEMPT_LOG)):
            if (
                candidate.get("schema") == SEND_ATTEMPT_SCHEMA
                and candidate.get("subject") == subject
                and candidate.get("attempt_id")
            ):
                attempt = candidate
                break
    except (OSError, UnicodeError) as read_error:
        attempt = None
        attempt_ledger_error = read_error
    notes = f"Superhuman delivery raised after its outcome became unknown: {exc}"
    if attempt_ledger_error is not None:
        notes += (
            "; send-attempt ledger is unsafe or corrupt: "
            f"{attempt_ledger_error}"
        )
    if attempt is not None:
        return ambiguous_send_receipt(
            attempt,
            subject=subject,
            notes=notes,
        )
    return {
        "status": "unknown",
        "delivery_status": "unknown_no_retry",
        "attempt_state": "UNKNOWN_NO_RETRY",
        "attempt_id": None,
        "draft_id": None,
        "thread_id": None,
        "acting_email": SELF_MAIL,
        "from": SELF_MAIL,
        "to": [SELF_MAIL],
        "subject": subject,
        "sent_at": None,
        "notes": notes,
        "wake": (
            (
                f"repair the unsafe or corrupt send-attempt ledger at {SEND_ATTEMPT_LOG}; "
                if attempt_ledger_error is not None
                else f"inspect {SEND_ATTEMPT_LOG}; "
            )
            + f"inspect the exact {SELF_MAIL} SENT mailbox route for subject {subject!r}; "
            "never retry delivery for this scheduled window"
        ),
    }


def _normalized_email(value: Any) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", str(value), re.I)
    return match.group(0).lower() if match else ""


def fetch_superhuman_mailbox_readback(window: dict[str, Any]) -> dict[str, Any]:
    """Confirm one sent report through stable mailbox thread/message reads."""
    import urllib.error
    import urllib.request

    if not isinstance(window, dict):
        return {
            "schema": MAILBOX_READBACK_SCHEMA,
            "status": "blocked",
            "wake": "window receipt must be a JSON object before mailbox readback",
            "problems": ["window row shape invalid"],
        }
    scheduled_for = str(window.get("scheduled_for") or "")
    receipt_value = window.get("receipt")
    receipt = receipt_value if isinstance(receipt_value, dict) else {}
    subject_value = receipt.get("subject")
    subject = subject_value if isinstance(subject_value, str) else ""
    base = {
        "schema": MAILBOX_READBACK_SCHEMA,
        "scheduled_for": scheduled_for,
        "generated_at": window.get("generated_at"),
        "board_revision": window.get("board_revision"),
        "acting_email": SELF_MAIL,
        "subject": subject,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not isinstance(receipt_value, dict) or not subject.strip():
        return {
            **base,
            "status": "blocked",
            "wake": "window receipt must contain an exact string subject before mailbox readback",
            "problems": ["window receipt shape invalid"],
        }
    scheduled_at = _parse_aware_datetime(scheduled_for)
    if scheduled_at is None or not _is_report_timezone_timestamp(scheduled_at):
        return {**base, "status": "blocked", "wake": "scheduled_for parses as ISO 8601"}
    token = _mcp_remote_token()
    if not token:
        return {
            **base,
            "status": "blocked",
            "wake": "refresh Superhuman mcp-remote OAuth; perform read-only mailbox readback",
        }
    url = SUPERHUMAN_MCP_RESOURCE

    def post(
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if session_id:
            headers["mcp-session-id"] = session_id
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            sid = response.headers.get("mcp-session-id") or session_id
            raw = response.read().decode("utf-8", errors="replace")
            return sid, _parse_mcp_sse(raw)

    try:
        sid, _init = post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "shadow-brief-readback", "version": "1.0"},
                },
            }
        )
        post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            session_id=sid,
        )
        start = scheduled_at.astimezone(timezone.utc)
        end = start + timedelta(minutes=30)
        _sid, listed = post(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "list_threads",
                    "arguments": {
                        "acting_email": SELF_MAIL,
                        "labels": ["SENT"],
                        "subject_contains": subject,
                        "from": [SELF_MAIL],
                        "to": [SELF_MAIL],
                        "start_date": start.isoformat(timespec="seconds"),
                        "end_date": end.isoformat(timespec="seconds"),
                        "limit": 2,
                        "sort": "newest",
                    },
                },
            },
            session_id=sid,
        )
        listed_payload = _mcp_text_payload(listed)
        listed_threads = listed_payload.get("threads")
        if not isinstance(listed_threads, list):
            return {
                **base,
                "status": "blocked",
                "wake": "inspect malformed Superhuman list_threads readback; never retry send_draft",
                "problems": ["thread list shape invalid"],
            }
        malformed_threads: list[str] = []
        for index, item in enumerate(listed_threads):
            if not isinstance(item, dict):
                malformed_threads.append(f"thread {index} row shape invalid")
                continue
            labels = item.get("labels")
            if not isinstance(labels, list) or any(
                not isinstance(label, str) for label in labels
            ):
                malformed_threads.append(f"thread {index} labels shape invalid")
            if not isinstance(item.get("subject"), str):
                malformed_threads.append(f"thread {index} subject shape invalid")
            for key in ("thread_id", "last_message_id"):
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    malformed_threads.append(f"thread {index} {key} shape invalid")
        if malformed_threads:
            return {
                **base,
                "status": "blocked",
                "wake": "inspect malformed Superhuman list_threads readback; never retry send_draft",
                "problems": malformed_threads,
            }
        candidates = [
            item
            for item in listed_threads
            if item.get("subject") == subject and "SENT" in item["labels"]
        ]
        if len(candidates) != 1:
            return {
                **base,
                "status": "blocked",
                "wake": (
                    f"exact SENT readback for {subject!r} returns one candidate; "
                    "never retry send_draft"
                ),
                "candidate_count": len(candidates),
            }
        candidate = candidates[0]
        thread_id = candidate["thread_id"]
        message_id = candidate["last_message_id"]
        _sid, thread_result = post(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_thread",
                    "arguments": {
                        "acting_email": SELF_MAIL,
                        "thread_id": thread_id,
                        "include_drafts": True,
                        "message_limit": 100,
                    },
                },
            },
            session_id=sid,
        )
        thread = _mcp_text_payload(thread_result)
        _sid, message_result = post(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_message",
                    "arguments": {
                        "acting_email": SELF_MAIL,
                        "message_id": message_id,
                        "include_raw_html": True,
                    },
                },
            },
            session_id=sid,
        )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            **base,
            "status": "blocked",
            "wake": f"repeat read-only Superhuman mailbox readback after transport recovery: {exc}",
        }

    message_payload = _mcp_text_payload(message_result)
    message_value = message_payload.get("message")
    message = message_value if isinstance(message_value, dict) else {}
    raw_html_value = message.get("raw_html")
    raw_html = raw_html_value if isinstance(raw_html_value, str) else ""
    from_value = message.get("from")
    from_email = _normalized_email(from_value) if isinstance(from_value, str) else ""
    to_value = message.get("to")
    to_emails = (
        [_normalized_email(value) for value in to_value]
        if isinstance(to_value, list)
        and all(isinstance(value, str) for value in to_value)
        else []
    )
    labels_value = message.get("labels")
    labels = (
        labels_value
        if isinstance(labels_value, list)
        and all(isinstance(label, str) for label in labels_value)
        else []
    )
    sent_at_value = message.get("sent_at")
    sent_at = sent_at_value if isinstance(sent_at_value, str) else ""
    problems: list[str] = []
    if not isinstance(message_value, dict):
        problems.append("message row shape invalid")
    if not isinstance(raw_html_value, str):
        problems.append("raw HTML shape invalid")
    if not isinstance(from_value, str) or not (
        isinstance(to_value, list)
        and all(isinstance(value, str) for value in to_value)
    ):
        problems.append("mailbox route shape invalid")
    if not (
        isinstance(labels_value, list)
        and all(isinstance(label, str) for label in labels_value)
    ):
        problems.append("message labels shape invalid")
    if not isinstance(sent_at_value, str):
        problems.append("sent timestamp shape invalid")
    for key in ("message_id", "thread_id"):
        value = message.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"message {key} shape invalid")
    if (
        thread.get("thread_id") != thread_id
        or thread.get("last_message_id") != message_id
        or thread.get("subject") != subject
    ):
        problems.append("exact thread identity mismatch")
    if message.get("message_id") != message_id or message.get("thread_id") != thread_id:
        problems.append("exact message identity mismatch")
    if from_email != SELF_MAIL or to_emails != [SELF_MAIL]:
        problems.append("exact self-route mismatch")
    if message.get("subject") != subject or "SENT" not in labels:
        problems.append("subject or SENT label mismatch")
    sent = _parse_aware_datetime(sent_at)
    if sent is None:
        problems.append("sent timestamp invalid")
    elif not scheduled_at <= sent <= scheduled_at + timedelta(minutes=30):
        problems.append("sent timestamp outside scheduled window")
    required_html = (
        _reader_generation_marker(window.get("slot"), window.get("generated_at")),
        f"board rev {window.get('board_revision')}",
        "Supporting checks inform the note; they do not create another to-do list.",
    )
    if not all(required_html) or any(marker not in raw_html for marker in required_html):
        problems.append("mailbox HTML does not match scheduled report identity")
    if problems:
        return {
            **base,
            "status": "blocked",
            "wake": "inspect exact thread/message readback; never retry send_draft",
            "problems": problems,
        }
    return {
        **base,
        "status": "EXACT_SENT_CONFIRMED",
        "from": from_email,
        "to": to_emails,
        "message_id": message_id,
        "thread_id": thread_id,
        "sent_at": sent_at,
        "labels": labels,
        "raw_html_sha256": hashlib.sha256(raw_html.encode("utf-8")).hexdigest(),
    }


def deliver_superhuman_http(
    html_path: Path,
    *,
    subject: str,
    send_authorized_self: bool = False,
) -> dict[str, Any] | None:
    """Draft via Superhuman Streamable-HTTP MCP using mcp-remote OAuth cache.

    Returns a receipt dict on success/hard failure, or None when token/transport
    is unavailable so the caller can fall back.
    """
    import urllib.error
    import urllib.request

    tok = _mcp_remote_token()
    if not tok:
        return None
    body_html = html_path.read_text(encoding="utf-8")
    url = "https://mcp.mail.superhuman.com/mcp"

    def post(payload: dict[str, Any], session_id: str | None = None) -> tuple[str | None, dict[str, Any]]:
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {tok}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if session_id:
            headers["mcp-session-id"] = session_id
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            sid = resp.headers.get("mcp-session-id") or session_id
            raw = resp.read().decode("utf-8", errors="replace")
            return sid, _parse_mcp_sse(raw)

    try:
        sid, _init = post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "shadow-brief", "version": "1.0"},
                },
            }
        )
        post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, session_id=sid)
        _sid, result = post(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "create_or_update_draft",
                    "arguments": {
                        "type": "new",
                        "acting_email": SELF_MAIL,
                        "from": SELF_MAIL,
                        "to": [SELF_MAIL],
                        "subject": subject,
                        "body": body_html,
                    },
                },
            },
            session_id=sid,
        )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "blocked",
            "draft_id": None,
            "acting_email": SELF_MAIL,
            "subject": subject,
            "sent_at": None,
            "notes": f"Superhuman HTTP MCP transport failed: {exc}",
            "wake": "refresh Superhuman mcp-remote OAuth (npx mcp-remote …) and re-run deliver",
        }

    if result.get("error"):
        return {
            "status": "blocked",
            "draft_id": None,
            "acting_email": SELF_MAIL,
            "subject": subject,
            "sent_at": None,
            "notes": f"Superhuman MCP error: {result.get('error')}",
            "wake": "create_or_update_draft returns schema-valid draft_id for leojkwan@gmail.com",
        }

    payload = _mcp_text_payload(result)
    draft = payload.get("draft") if isinstance(payload, dict) else None
    draft_id = draft.get("draft_id") if isinstance(draft, dict) else None
    thread_id = draft.get("thread_id") if isinstance(draft, dict) else None
    if not draft_id:
        return {
            "status": "blocked",
            "draft_id": None,
            "acting_email": SELF_MAIL,
            "subject": subject,
            "sent_at": None,
            "notes": f"Superhuman MCP returned no draft_id: {str(result)[:400]}",
            "wake": "create_or_update_draft returns schema-valid draft_id for leojkwan@gmail.com",
        }
    if not send_authorized_self:
        return {
            "status": "ok",
            "delivery_status": "drafted",
            "draft_id": draft_id,
            "thread_id": thread_id,
            "acting_email": SELF_MAIL,
            "from": SELF_MAIL,
            "to": [SELF_MAIL],
            "subject": subject,
            "sent_at": None,
            "notes": "create_or_update_draft via Superhuman HTTP MCP (draft-only)",
            "local_html": str(html_path),
        }

    try:
        attempt = record_send_attempt(
            html_path,
            subject=subject,
            draft_id=draft_id,
            thread_id=thread_id,
        )
    except OSError as exc:
        return {
            "status": "blocked",
            "delivery_status": "not_sent",
            "draft_id": draft_id,
            "thread_id": thread_id,
            "acting_email": SELF_MAIL,
            "from": SELF_MAIL,
            "to": [SELF_MAIL],
            "subject": subject,
            "sent_at": None,
            "notes": f"durable pre-send attempt could not be written: {exc}",
            "wake": f"restore mode-600 write access to {SEND_ATTEMPT_LOG}; do not send",
        }

    try:
        _sid, send_result = post(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "send_draft",
                    "arguments": {
                        "acting_email": SELF_MAIL,
                        "draft_id": draft_id,
                        "undo_timeout": 1,
                    },
                },
            },
            session_id=sid,
        )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return ambiguous_send_receipt(
            attempt,
            subject=subject,
            notes=f"Superhuman send_draft transport result is ambiguous: {exc}",
        )
    send_payload = _mcp_text_payload(send_result)
    if send_result.get("error") or not send_payload.get("success") or not send_payload.get("message_id"):
        return ambiguous_send_receipt(
            attempt,
            subject=subject,
            notes=f"Superhuman send_draft result is ambiguous: {str(send_result)[:400]}",
        )
    outcome = {
        "schema": SEND_ATTEMPT_SCHEMA,
        "state": "PROVISIONAL_SENT",
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "attempt_id": attempt.get("attempt_id"),
        "message_id": send_payload.get("message_id"),
        "thread_id": send_payload.get("thread_id") or thread_id,
        "sent_at": send_payload.get("sent_at"),
    }
    try:
        _append_private_jsonl(SEND_ATTEMPT_LOG, outcome)
    except OSError as exc:
        return ambiguous_send_receipt(
            attempt,
            subject=subject,
            notes=f"send returned success but durable outcome write failed: {exc}",
        )
    return {
        "status": "ok",
        "delivery_status": "sent",
        "attempt_state": "PROVISIONAL_SENT",
        "attempt_id": attempt.get("attempt_id"),
        "draft_id": draft_id,
        "message_id": send_payload.get("message_id"),
        "thread_id": send_payload.get("thread_id") or thread_id,
        "acting_email": SELF_MAIL,
        "from": SELF_MAIL,
        "to": [SELF_MAIL],
        "subject": subject,
        "sent_at": send_payload.get("sent_at"),
        "notes": "create_or_update_draft + send_draft via Superhuman HTTP MCP; exact self-send guard",
        "local_html": str(html_path),
    }


def deliver_superhuman(
    html_path: Path,
    *,
    subject: str,
    dry_run: bool = False,
    send_authorized_self: bool = False,
) -> dict[str, Any]:
    receipt_path = EVIDENCE_DIR / "superhuman-receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return {
            "status": "dry-run",
            "html": str(html_path),
            "note": "skipped Superhuman delivery",
        }

    # The only delivery mechanism is Superhuman's authenticated MCP endpoint.
    # Never fall back to an IDE agent: a missing token must fail closed, not
    # consume a separate provider or create an unreviewable send path.
    http_receipt = deliver_superhuman_http(
        html_path,
        subject=subject,
        send_authorized_self=send_authorized_self,
    )
    if http_receipt is not None:
        receipt_path.write_text(json.dumps(http_receipt, indent=2) + "\n", encoding="utf-8")
        return http_receipt

    receipt = {
        "status": "blocked",
        "delivery_status": "not_sent",
        "subject": subject,
        "sent_at": None,
        "acting_email": SELF_MAIL,
        "from": SELF_MAIL,
        "to": [SELF_MAIL],
        "notes": "Superhuman HTTP OAuth is unavailable; exact self-send fails closed",
        "wake": "refresh Superhuman mcp-remote OAuth and wait for the next natural scheduled self-send",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def launch_agent_plist(program: Path) -> dict[str, Any]:
    python = sys.executable
    home = Path.home()
    return {
        "Label": LABEL,
        "ProgramArguments": [
            python,
            str(program),
            "run",
            "--deliver",
            "--send-authorized-self",
            "--scheduled-trigger",
        ],
        "StartCalendarInterval": [
            {"Hour": 8, "Minute": 0},
            {"Hour": 20, "Minute": 0},
        ],
        "RunAtLoad": False,
        "StandardOutPath": str(LOG_DIR / "launchd.out.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd.err.log"),
        "EnvironmentVariables": {
            "HOME": str(home),
            "PATH": ":".join(
                [
                    str(home / ".local" / "bin"),
                    "/opt/homebrew/bin",
                    "/usr/local/bin",
                    "/usr/bin",
                    "/bin",
                    "/usr/sbin",
                    "/sbin",
                ]
            ),
            "SHADOW_PORTFOLIO_ROOT": str(portfolio_root()),
        },
    }


def _host_timezone_name() -> str | None:
    try:
        target = str(Path("/etc/localtime").resolve(strict=True))
    except OSError:
        target = ""
    marker = "/zoneinfo/"
    if marker in target:
        return target.split(marker, 1)[1]
    key = getattr(datetime.now().astimezone().tzinfo, "key", None)
    return str(key) if key else None


def host_timezone_matches_report(host_timezone: str | None = None) -> bool:
    """launchd calendar intervals fire in host-local time.

    Matching one current UTC offset is insufficient because another zone may follow
    different daylight-saving rules. Require the actual IANA zone that launchd uses.
    """
    return (host_timezone or _host_timezone_name()) == REPORT_TIMEZONE_NAME


def schedule_configuration_problems(
    installed: dict[str, Any],
    expected: dict[str, Any],
    *,
    host_timezone: str | None = None,
) -> list[str]:
    keys = (
        "Label",
        "ProgramArguments",
        "StartCalendarInterval",
        "RunAtLoad",
        "StandardOutPath",
        "StandardErrorPath",
        "EnvironmentVariables",
    )
    problems = [key for key in keys if installed.get(key) != expected.get(key)]
    if not host_timezone_matches_report(host_timezone):
        problems.append("HostTimezone")
    return problems


def schedule_configuration_recovery(problems: list[str]) -> str:
    steps: list[str] = []
    if "HostTimezone" in problems:
        steps.append(
            f"set the macOS system timezone to {REPORT_TIMEZONE_NAME}, then run schedule --status"
        )
    duplicate_agents = [
        problem.split(":", 1)[1]
        for problem in problems
        if problem.startswith("OtherScheduledBriefLaunchAgent:")
    ]
    if duplicate_agents:
        steps.append(
            "bootout and remove the other scheduled brief LaunchAgent plist(s) "
            + ", ".join(duplicate_agents)
            + ", then run schedule --status"
        )
    if any(
        problem != "HostTimezone"
        and not problem.startswith("OtherScheduledBriefLaunchAgent:")
        for problem in problems
    ):
        steps.append("run schedule --install, then run schedule --status")
    return "; ".join(steps)


def _command_targets_scheduled_brief(values: list[str]) -> bool:
    command = list(values)
    assignment = r"[A-Za-z_][A-Za-z0-9_]*=.*"
    while command and (
        command[0] == "exec"
        or re.fullmatch(assignment, command[0]) is not None
    ):
        command.pop(0)
    if command and Path(command[0]).name == "env":
        command.pop(0)
        while command:
            value = command[0]
            if re.fullmatch(assignment, value) is not None:
                command.pop(0)
                continue
            if value == "--":
                command.pop(0)
                break
            if value in {"-S", "--split-string"}:
                if len(command) < 2:
                    return False
                try:
                    split_command = shlex.split(command[1], posix=True)
                except ValueError:
                    return False
                command = split_command + command[2:]
                break
            if value.startswith("-S") and value != "-S":
                try:
                    split_command = shlex.split(value[2:], posix=True)
                except ValueError:
                    return False
                command = split_command + command[1:]
                break
            if value.startswith("--split-string="):
                try:
                    split_command = shlex.split(value.split("=", 1)[1], posix=True)
                except ValueError:
                    return False
                command = split_command + command[1:]
                break
            if value in {
                "-u",
                "--unset",
                "-C",
                "--chdir",
                "-P",
                "-a",
                "--argv0",
            }:
                if len(command) < 2:
                    return False
                del command[:2]
                continue
            if value in {"-i", "--ignore-environment", "-0", "--null"}:
                command.pop(0)
                continue
            if (
                re.fullmatch(r"-u.+", value)
                or value.startswith("--unset=")
                or value.startswith("--chdir=")
                or value.startswith("--argv0=")
            ):
                command.pop(0)
                continue
            if value.startswith("-"):
                return False
            break
        while command and (
            command[0] == "exec"
            or re.fullmatch(assignment, command[0]) is not None
        ):
            command.pop(0)
    if "--scheduled-trigger" not in command:
        return False
    if not command:
        return False
    program = Path(command[0]).name
    if (
        program == "shadow"
        and len(command) >= 3
        and command[1:3] == ["brief", "run"]
    ):
        return True
    if program == "shadow-brief.py":
        return True
    if re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", program) is None:
        return False
    arguments = command[1:]
    index = 0
    while index < len(arguments):
        value = arguments[index]
        if value == "--":
            index += 1
            break
        if value in {"-c", "-m"}:
            return False
        if not value.startswith("-") or value == "-":
            break
        if value in {"-W", "-X", "--check-hash-based-pycs"}:
            index += 2
        else:
            index += 1
    return bool(
        index < len(arguments)
        and Path(arguments[index]).name == "shadow-brief.py"
    )


def _shell_simple_commands(command_text: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(
            command_text,
            posix=True,
            punctuation_chars=";&|",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return []
    commands: list[list[str]] = []
    command: list[str] = []
    for token in tokens:
        if token and all(character in ";&|" for character in token):
            if command:
                commands.append(command)
            command = []
            continue
        command.append(token)
    if command:
        commands.append(command)
    return commands


def _targets_scheduled_brief(doc: dict[str, Any]) -> bool:
    arguments = doc.get("ProgramArguments")
    if not isinstance(arguments, list):
        return False
    values = [str(value) for value in arguments]
    if _command_targets_scheduled_brief(values):
        return True
    if not values or Path(values[0]).name not in {"sh", "bash", "dash", "ksh", "zsh"}:
        return False
    command_text: str | None = None
    for index, value in enumerate(values[1:], start=1):
        if value == "--":
            break
        command_option = value == "-c" or (
            value.startswith("-")
            and not value.startswith("--")
            and "c" in value[1:]
        )
        if command_option:
            if index + 1 < len(values):
                command_text = values[index + 1]
            break
        if not value.startswith("-"):
            break
    if command_text is None:
        return False
    return any(
        _command_targets_scheduled_brief(command)
        for command in _shell_simple_commands(command_text)
    )


def _other_scheduled_brief_agents(canonical: Path) -> list[Path]:
    agents = canonical.parent
    if not agents.is_dir():
        return []
    found: list[Path] = []
    for candidate in sorted(agents.glob("*.plist")):
        if candidate == canonical:
            continue
        try:
            with candidate.open("rb") as handle:
                doc = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException):
            continue
        if isinstance(doc, dict) and _targets_scheduled_brief(doc):
            found.append(candidate)
    return found


def schedule_install() -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    program = Path(__file__).resolve()
    doc = launch_agent_plist(program)
    rendered = plistlib.dumps(doc, fmt=plistlib.FMT_XML, sort_keys=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = plist_path.with_suffix(".plist.tmp")
    tmp.write_bytes(rendered)
    tmp.replace(plist_path)
    uid = os.getuid()
    _run(["/bin/launchctl", "bootout", f"gui/{uid}", str(plist_path)])
    load = _run(["/bin/launchctl", "bootstrap", f"gui/{uid}", str(plist_path)])
    status = schedule_status()
    return {
        "plist": str(plist_path),
        "bootstrap_rc": load.returncode,
        "bootstrap_err": (load.stderr or "")[:300],
        "hours": list(SLOT_HOURS),
        "report_timezone": REPORT_TIMEZONE_NAME,
        "host_timezone": _host_timezone_name(),
        "host_timezone_matches_report": host_timezone_matches_report(),
        "configuration_ok": status.get("configuration_ok") is True,
        "configuration_problems": status.get("configuration_problems") or [],
        "launchctl_ok": status.get("launchctl_ok") is True,
        "post_install_status": status,
    }


def schedule_status() -> dict[str, Any]:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    duplicate_problems = [
        f"OtherScheduledBriefLaunchAgent:{path.name}"
        for path in _other_scheduled_brief_agents(plist_path)
    ]
    if not plist_path.is_file():
        host_timezone = _host_timezone_name()
        host_timezone_ok = host_timezone_matches_report(host_timezone)
        return {
            "installed": False,
            "plist": str(plist_path),
            "configuration_ok": False,
            "configuration_problems": (
                ([] if host_timezone_ok else ["HostTimezone"])
                + duplicate_problems
            ),
            "report_timezone": REPORT_TIMEZONE_NAME,
            "host_timezone": host_timezone,
            "host_timezone_matches_report": host_timezone_ok,
            "launchctl_ok": False,
        }
    with plist_path.open("rb") as fh:
        doc = plistlib.load(fh)
    program = Path(__file__).resolve()
    expected = launch_agent_plist(program)
    configuration_problems = (
        schedule_configuration_problems(doc, expected) + duplicate_problems
    )
    if not program.is_file():
        configuration_problems.append("ProgramFile")
    uid = os.getuid()
    try:
        print_out = _run(["/bin/launchctl", "print", f"gui/{uid}/{LABEL}"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        print_out = subprocess.CompletedProcess(
            ["/bin/launchctl", "print", f"gui/{uid}/{LABEL}"],
            1,
            "",
            f"{type(exc).__name__}: {exc}",
        )
    loaded_job = _parse_launchctl_loaded_job(print_out.stdout or "")
    loaded_job_matches = _loaded_job_matches_current(loaded_job)
    if print_out.returncode != 0 or not loaded_job_matches:
        configuration_problems.append("LoadedJob")
    return {
        "installed": True,
        "plist": str(plist_path),
        "StartCalendarInterval": doc.get("StartCalendarInterval"),
        "ProgramArguments": doc.get("ProgramArguments"),
        "EnvironmentVariables": doc.get("EnvironmentVariables"),
        "configuration_ok": not configuration_problems,
        "configuration_problems": configuration_problems,
        "report_timezone": REPORT_TIMEZONE_NAME,
        "host_timezone": _host_timezone_name(),
        "host_timezone_matches_report": host_timezone_matches_report(),
        "launchctl_rc": print_out.returncode,
        "launchctl_ok": print_out.returncode == 0 and loaded_job_matches,
        "loaded_program": loaded_job.get("program") if loaded_job else None,
        "loaded_program_arguments": loaded_job.get("arguments") if loaded_job else None,
        "loaded_path": loaded_job.get("path") if loaded_job else None,
    }


def doctor() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVIDENCE_DIR / "latest.json"
    html_path = EVIDENCE_DIR / "latest.html"
    problems: list[str] = []
    if not BOARD_PATH.is_file():
        problems.append("missing ~/.shadow/board.json")
    if not json_path.is_file():
        problems.append("missing latest.json — run collect")
    if not html_path.is_file():
        problems.append("missing latest.html — run render")
    sched = schedule_status()
    if not sched.get("installed") or not sched.get("launchctl_ok"):
        problems.append("schedule not armed — run schedule --install")
    configuration_problems = sched.get("configuration_problems") or []
    if configuration_problems:
        problems.append(
            "schedule configuration drift: "
            + ", ".join(configuration_problems)
            + " — "
            + schedule_configuration_recovery(configuration_problems)
        )
    if not _mcp_remote_token():
        problems.append(
            "Superhuman OAuth unavailable — refresh the exact Superhuman mcp-remote "
            "authorization and confirm a read-only personal-account lookup; never use "
            "Gmail MCP or a second delivery queue"
        )
    receipt = EVIDENCE_DIR / "superhuman-receipt.json"
    if not receipt.is_file():
        problems.append("missing superhuman-receipt.json — run deliver or record wake")
    else:
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if data.get("status") not in {"ok", "dry-run", "blocked"}:
                problems.append("receipt status unexpected")
            if data.get("status") == "blocked" and not data.get("wake"):
                problems.append("blocked receipt lacks wake")
        except json.JSONDecodeError:
            problems.append("receipt json invalid")
    print(json.dumps({"ok": not problems, "problems": problems, "schedule": sched}, indent=2))
    return 0 if not problems else 1


def cmd_collect(args: argparse.Namespace) -> int:
    packet = collect_packet(slot=args.slot)
    out = Path(args.out) if args.out else EVIDENCE_DIR / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        # Still write — proof needs the artifact; dry-run skips remote side effects only
        out.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        print(str(out))
        return 0
    out.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    print(str(out))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    src = Path(args.input) if args.input else EVIDENCE_DIR / "latest.json"
    out = Path(args.out) if args.out else EVIDENCE_DIR / "latest.html"
    packet = json.loads(src.read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(packet), encoding="utf-8")
    print(str(out))
    return 0


def run_exit_code(
    receipt: dict[str, Any],
    notification: dict[str, Any],
    *,
    scheduled_trigger: bool,
) -> int:
    if notification.get("status") != "ok":
        return 1
    if scheduled_trigger:
        return 0 if (
            receipt.get("status") == "ok"
            and receipt.get("delivery_status") == "sent"
            and receipt.get("message_id")
        ) else 1
    return 0 if receipt.get("status") in {"ok", "dry-run", "skipped"} else 1


def _acquire_scheduled_run_lock() -> Any | None:
    """Take the one nonblocking lock before any scheduled provider collection."""
    path = LOG_DIR / "scheduled-run.lock"
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = os.open(path, flags, 0o600)
    locked = False
    try:
        identity = os.fstat(descriptor)
        named_identity = os.lstat(path)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != os.getuid()
            or identity.st_nlink != 1
            or (identity.st_dev, identity.st_ino)
            != (named_identity.st_dev, named_identity.st_ino)
        ):
            raise PermissionError(f"unsafe scheduled run lock identity: {path}")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        locked = True
        locked_identity = os.fstat(descriptor)
        locked_named_identity = os.lstat(path)
        if (
            not stat.S_ISREG(locked_identity.st_mode)
            or not stat.S_ISREG(locked_named_identity.st_mode)
            or locked_identity.st_uid != os.getuid()
            or locked_named_identity.st_uid != os.getuid()
            or locked_identity.st_nlink != 1
            or locked_named_identity.st_nlink != 1
            or (locked_identity.st_dev, locked_identity.st_ino)
            != (locked_named_identity.st_dev, locked_named_identity.st_ino)
        ):
            raise PermissionError(f"unsafe scheduled run lock identity after flock: {path}")
        handle = os.fdopen(descriptor, "r+", encoding="utf-8")
        descriptor = None
        return handle
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                os.close(descriptor)
            except OSError:
                pass


def _release_scheduled_run_lock(handle: Any | None) -> None:
    if handle is None:
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (OSError, ValueError):
        pass
    try:
        handle.close()
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _place_private_archive(path: Path, content: bytes) -> None:
    """Publish complete immutable bytes once; an existing name is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    temporary: Path | None = None
    for nonce in range(100):
        candidate = path.parent / f".{path.name}.{os.getpid()}.{nonce}.tmp"
        try:
            descriptor = os.open(candidate, flags, 0o600)
        except FileExistsError:
            continue
        temporary = candidate
        break
    if descriptor is None or temporary is None:
        raise FileExistsError(f"could not reserve a private archive temporary for {path}")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            os.fchmod(handle.fileno(), 0o400)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            raise FileExistsError(f"immutable archive already exists: {path}") from None
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
        _fsync_directory(path.parent)


def _archive_stamp(
    *,
    scheduled_trigger: bool,
    trigger_window: dict[str, Any],
) -> str:
    if scheduled_trigger:
        scheduled = _parse_aware_datetime(trigger_window.get("scheduled_for"))
        if scheduled is None or not _is_report_timezone_timestamp(scheduled):
            raise ValueError("scheduled archive has no canonical report window")
        return scheduled.astimezone(REPORT_TIMEZONE).strftime("%Y%m%d-%H%M%S")
    now = datetime.now(REPORT_TIMEZONE)
    return f"{now.strftime('%Y%m%d-%H%M%S-%f')}-{secrets.token_hex(16)}"


def _write_last_run_best_effort(summary: dict[str, Any]) -> bool:
    try:
        (LOG_DIR / "last-run.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return False
    return True


def _print_json_best_effort(payload: dict[str, Any], *, file: Any = None) -> bool:
    try:
        print(json.dumps(payload, indent=2), file=file)
    except OSError:
        return False
    return True


def cmd_run(args: argparse.Namespace) -> int:
    trigger_proof: dict[str, Any] = {}
    if args.scheduled_trigger:
        trigger_proof = launch_trigger_proof()
        if not scheduled_trigger_is_authorized(True, trigger_proof):
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "error": "scheduled trigger was not started by launchd",
                        "trigger_proof": trigger_proof,
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lock_handle = None
    if args.scheduled_trigger:
        try:
            lock_handle = _acquire_scheduled_run_lock()
        except OSError as exc:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "error": f"scheduled run lock unavailable: {exc}",
                        "trigger_proof": trigger_proof,
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 3
        if lock_handle is None:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "error": "another scheduled brief invocation holds the run lock",
                        "trigger_proof": trigger_proof,
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 3
    try:
        return _cmd_run_locked(args, trigger_proof)
    finally:
        _release_scheduled_run_lock(lock_handle)


def _cmd_run_locked(args: argparse.Namespace, trigger_proof: dict[str, Any]) -> int:
    trigger_window: dict[str, Any] = {}
    attempt_barrier: dict[str, str] | None = None
    scheduled_stamp: str | None = None
    if args.scheduled_trigger:
        trigger_window = scheduled_window(datetime.now(REPORT_TIMEZONE))
        if not trigger_window.get("on_schedule"):
            if not host_timezone_matches_report():
                reason = (
                    "the host timezone does not match "
                    f"{REPORT_TIMEZONE}, so the launchd 08:00/20:00 calendar does not "
                    "land on the report windows; set the macOS system timezone to "
                    f"{REPORT_TIMEZONE_NAME}, then run schedule --status"
                )
            else:
                reason = "scheduled trigger is outside the 08:00/20:00 freshness window"
            print(
                json.dumps(
                    {
                        "schema": WINDOW_RECEIPT_SCHEMA,
                        "status": "blocked",
                        "trigger_proof": trigger_proof,
                        "scheduled_window": trigger_window,
                        "wake": f"{reason}; do not collect, notify, or send",
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 3
        scheduled_stamp = _archive_stamp(
            scheduled_trigger=True,
            trigger_window=trigger_window,
        )
        archive_html_path = EVIDENCE_DIR / f"brief-{scheduled_stamp}.html"
        archive_json_path = EVIDENCE_DIR / f"brief-{scheduled_stamp}.json"
        attempt_barrier_path = (
            LOG_DIR / f"scheduled-attempt-{scheduled_stamp}.json"
        )
        try:
            existing_window_rows = _read_jsonl(WINDOW_LOG)
        except PrivateJSONLError as exc:
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "wake": (
                    f"window ledger is unsafe or corrupt at {WINDOW_LOG}: {exc}; "
                    "repair the exact private ledger; do not collect, notify, send, "
                    "overwrite, or retry this scheduled window"
                ),
            }
            _write_last_run_best_effort(summary)
            _print_json_best_effort(summary, file=sys.stderr)
            return 3
        try:
            _read_jsonl(SEND_ATTEMPT_LOG)
        except PrivateJSONLError as exc:
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "wake": (
                    f"send-attempt ledger is unsafe or corrupt at {SEND_ATTEMPT_LOG}: {exc}; "
                    "repair the exact private ledger; do not collect, notify, send, "
                    "overwrite, or retry this scheduled window"
                ),
            }
            _write_last_run_best_effort(summary)
            _print_json_best_effort(summary, file=sys.stderr)
            return 3
        existing_window = any(
            row.get("schema") == WINDOW_RECEIPT_SCHEMA
            and row.get("trigger") == "launchd-calendar"
            and row.get("scheduled_for") == trigger_window.get("scheduled_for")
            for row in existing_window_rows
        )
        archive_barrier = os.path.lexists(archive_html_path) or os.path.lexists(
            archive_json_path
        )
        existing_attempt_barrier = os.path.lexists(attempt_barrier_path)
        if existing_window or archive_barrier or existing_attempt_barrier:
            reason = (
                "this scheduled window already has a durable receipt"
                if existing_window
                else (
                    "this scheduled window already has an immutable archive barrier"
                    if archive_barrier
                    else "this scheduled window already has a durable attempt barrier"
                )
            )
            barrier_receipt = {
                "path": str(attempt_barrier_path),
                "state": "EXISTS" if existing_attempt_barrier else "ABSENT",
            }
            print(
                json.dumps(
                    {
                        "schema": WINDOW_RECEIPT_SCHEMA,
                        "status": "blocked",
                        "trigger_proof": trigger_proof,
                        "scheduled_window": trigger_window,
                        "scheduled_for": trigger_window.get("scheduled_for"),
                        "archive_html": str(archive_html_path),
                        "archive_json": str(archive_json_path),
                        "attempt_barrier": barrier_receipt,
                        "wake": f"{reason}; do not collect, notify, send, overwrite, or retry",
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 3
        barrier_payload = {
            "schema": SCHEDULED_ATTEMPT_SCHEMA,
            "state": "RESERVED",
            "scheduled_for": trigger_window.get("scheduled_for"),
            "slot": trigger_window.get("slot"),
        }
        try:
            _place_private_archive(
                attempt_barrier_path,
                (json.dumps(barrier_payload, sort_keys=True) + "\n").encode("utf-8"),
            )
        except OSError as exc:
            barrier_state = (
                "PRESENT" if os.path.lexists(attempt_barrier_path) else "UNAVAILABLE"
            )
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "archive_html": str(archive_html_path),
                "archive_json": str(archive_json_path),
                "attempt_barrier": {
                    "path": str(attempt_barrier_path),
                    "state": barrier_state,
                },
                "wake": (
                    f"scheduled attempt barrier publication failed: {exc}; "
                    "do not collect, notify, send, overwrite, or retry until the "
                    "exact local barrier path is inspected"
                ),
            }
            print(json.dumps(summary, indent=2), file=sys.stderr)
            _write_last_run_best_effort(summary)
            return 3
        attempt_barrier = {
            "path": str(attempt_barrier_path),
            "state": "PRESENT",
        }
    try:
        packet = collect_packet(slot=args.slot)
    except (
        OSError,
        subprocess.TimeoutExpired,
        ValueError,
        RecursionError,
    ) as exc:
        if not args.scheduled_trigger:
            raise
        summary = {
            "schema": WINDOW_RECEIPT_SCHEMA,
            "status": "blocked",
            "trigger_proof": trigger_proof,
            "scheduled_window": trigger_window,
            "scheduled_for": trigger_window.get("scheduled_for"),
            "attempt_barrier": attempt_barrier,
            "collection_error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "wake": (
                "scheduled packet collection failed after reserving this window; "
                "repair the exact collector process error before the next natural "
                "window; do not notify or send, and never retry this reserved window"
            ),
        }
        _write_last_run_best_effort(summary)
        _print_json_best_effort(summary, file=sys.stderr)
        return 3
    board_snapshot = ((packet.get("authority") or {}).get("board_snapshot") or {})
    if board_snapshot.get("consistent") is not True:
        summary = {
            "schema": WINDOW_RECEIPT_SCHEMA,
            "status": "blocked",
            "generated_at": packet.get("generated_at"),
            "board_revision": (packet.get("board") or {}).get("revision"),
            "producer": packet.get("producer"),
            "trigger_proof": trigger_proof,
            "board_snapshot": board_snapshot,
            **(
                {"attempt_barrier": attempt_barrier}
                if attempt_barrier is not None
                else {}
            ),
            "wake": (
                "shadow status --json --by codex stabilizes at one board revision; "
                "then run read-only shadow-brief collect; never retry the scheduled send"
            ),
        }
        print(json.dumps(summary, indent=2))
        _write_last_run_best_effort(summary)
        return 1
    if args.scheduled_trigger:
        scheduled_at = _parse_aware_datetime(trigger_window.get("scheduled_for"))
        generated_at = _parse_aware_datetime(packet.get("generated_at"))
        if (
            scheduled_at is None
            or generated_at is None
            or not scheduled_at <= generated_at <= scheduled_at + timedelta(minutes=30)
        ):
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "generated_at": packet.get("generated_at"),
                "board_revision": (packet.get("board") or {}).get("revision"),
                "producer": packet.get("producer"),
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "attempt_barrier": attempt_barrier,
                "wake": (
                    "collection did not finish within the admitted scheduled window; "
                    "do not notify or send, and wait for the next natural window"
                ),
            }
            print(json.dumps(summary, indent=2), file=sys.stderr)
            _write_last_run_best_effort(summary)
            return 3
        if not _valid_producer_provenance(packet.get("producer")):
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "generated_at": packet.get("generated_at"),
                "board_revision": (packet.get("board") or {}).get("revision"),
                "producer": packet.get("producer"),
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "attempt_barrier": attempt_barrier,
                "wake": (
                    "runtime producer provenance is invalid; inspect the checked-in "
                    "script bytes and source commit before the next natural window; "
                    "do not notify, send, overwrite, or retry this scheduled window"
                ),
            }
            print(json.dumps(summary, indent=2), file=sys.stderr)
            _write_last_run_best_effort(summary)
            return 3
        try:
            existing_window_rows = _read_jsonl(WINDOW_LOG)
        except PrivateJSONLError as exc:
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "generated_at": packet.get("generated_at"),
                "board_revision": (packet.get("board") or {}).get("revision"),
                "producer": packet.get("producer"),
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "attempt_barrier": attempt_barrier,
                "wake": (
                    f"window ledger is unsafe or corrupt at {WINDOW_LOG}: {exc}; "
                    "repair the exact private ledger; do not notify, send, overwrite, "
                    "or retry this reserved scheduled window"
                ),
            }
            _write_last_run_best_effort(summary)
            _print_json_best_effort(summary, file=sys.stderr)
            return 3
        existing_window = any(
            row.get("schema") == WINDOW_RECEIPT_SCHEMA
            and row.get("trigger") == "launchd-calendar"
            and row.get("scheduled_for") == trigger_window.get("scheduled_for")
            for row in existing_window_rows
        )
        if existing_window:
            reason = "this scheduled window already has a durable receipt"
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "generated_at": packet.get("generated_at"),
                "board_revision": (packet.get("board") or {}).get("revision"),
                "producer": packet.get("producer"),
                "trigger_proof": trigger_proof,
                "scheduled_window": trigger_window,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "attempt_barrier": attempt_barrier,
                "wake": f"{reason}; do not notify or send again",
            }
            print(json.dumps(summary, indent=2))
            _write_last_run_best_effort(summary)
            return 3
    json_path = EVIDENCE_DIR / "latest.json"
    html_path = EVIDENCE_DIR / "latest.html"
    try:
        stamp = scheduled_stamp or _archive_stamp(
            scheduled_trigger=False,
            trigger_window=trigger_window,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 3
    archive_prefix = "brief" if args.scheduled_trigger else "manual-brief"
    archive_html_path = EVIDENCE_DIR / f"{archive_prefix}-{stamp}.html"
    archive_json_path = EVIDENCE_DIR / f"{archive_prefix}-{stamp}.json"
    json_bytes = (json.dumps(packet, indent=2) + "\n").encode("utf-8")
    html_bytes = render_html(packet).encode("utf-8")
    try:
        _place_private_archive(archive_html_path, html_bytes)
        _place_private_archive(archive_json_path, json_bytes)
    except OSError as exc:
        summary = {
            "schema": WINDOW_RECEIPT_SCHEMA,
            "status": "blocked",
            "generated_at": packet.get("generated_at"),
            "board_revision": (packet.get("board") or {}).get("revision"),
            "producer": packet.get("producer"),
            "trigger_proof": trigger_proof,
            "scheduled_window": trigger_window,
            "scheduled_for": trigger_window.get("scheduled_for"),
            "archive_html": str(archive_html_path),
            "archive_json": str(archive_json_path),
            **(
                {"attempt_barrier": attempt_barrier}
                if attempt_barrier is not None
                else {}
            ),
            "wake": (
                f"{exc}; do not notify, send, overwrite, or retry this scheduled window; "
                "inspect the immutable archive pair and scheduled-window ledger"
            ),
        }
        print(json.dumps(summary, indent=2), file=sys.stderr)
        _write_last_run_best_effort(summary)
        return 3
    try:
        write_packet(packet, json_path, html_path)
    except OSError:
        # latest.* is a convenience view. The immutable run-local pair above is
        # the delivery and verification authority for a scheduled window.
        pass
    subject = brief_subject(packet["slot"], packet["generated_at"])
    notification = macos_notify(
        "Shadow brief ready",
        f"{packet['slot']} · board rev {packet.get('board', {}).get('revision')}",
    )
    receipt: dict[str, Any] = {"status": "skipped", "notes": "deliver not requested"}
    notification_blocked = bool(
        args.scheduled_trigger and notification.get("status") != "ok"
    )
    if notification_blocked:
        receipt = {
            "status": "blocked",
            "delivery_status": "not_sent",
            "subject": subject,
            "notes": "scheduled notification did not complete; delivery was not attempted",
        }
    elif args.deliver:
        try:
            receipt = deliver_superhuman(
                archive_html_path,
                subject=subject,
                dry_run=args.dry_run,
                send_authorized_self=args.send_authorized_self,
            )
        except Exception as exc:
            receipt = _delivery_exception_receipt(subject, exc)
    summary = {
        "schema": WINDOW_RECEIPT_SCHEMA,
        "trigger_proof": trigger_proof,
        "scheduled_window": trigger_window,
        "scheduled_for": trigger_window.get("scheduled_for"),
        "generated_at": packet["generated_at"],
        "board_revision": packet.get("board", {}).get("revision"),
        "producer": packet.get("producer"),
        "json": str(json_path),
        "html": str(html_path),
        "archive_html": str(archive_html_path),
        "archive_json": str(archive_json_path),
        **(
            {"attempt_barrier": attempt_barrier}
            if attempt_barrier is not None
            else {}
        ),
        "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
        "json_sha256": hashlib.sha256(json_bytes).hexdigest(),
        "notification": notification,
        "paint_health": packet.get("paint_health") or {},
        "receipt": receipt,
    }
    if notification_blocked:
        summary.update(
            {
                "status": "blocked",
                "wake": (
                    "scheduled macOS notification is blocked; repair the exact "
                    "notification error before the next natural window; do not send "
                    "or retry this reserved window"
                ),
            }
        )
    _write_last_run_best_effort(summary)
    try:
        append_scheduled_window(
            summary,
            scheduled_trigger=args.scheduled_trigger,
            window=trigger_window,
        )
    except OSError as exc:
        recovery = {
            **summary,
            "status": "blocked",
            "wake": (
                f"scheduled window ledger append failed after delivery outcome: {exc}; "
                "the durable attempt barrier remains authoritative; inspect the "
                "delivery attempt and immutable archives, and never resend this window"
            ),
        }
        _write_last_run_best_effort(recovery)
        _print_json_best_effort(recovery, file=sys.stderr)
        return 3
    if notification_blocked:
        _print_json_best_effort(summary, file=sys.stderr)
        return 3
    _print_json_best_effort(summary)
    return run_exit_code(receipt, notification, scheduled_trigger=args.scheduled_trigger)


def cmd_deliver(args: argparse.Namespace) -> int:
    html_path = Path(args.html) if args.html else EVIDENCE_DIR / "latest.html"
    if not html_path.is_file():
        print("missing html — run render first", file=sys.stderr)
        return 2
    packet_path = EVIDENCE_DIR / "latest.json"
    slot = "brief"
    when = datetime.now(REPORT_TIMEZONE).isoformat(timespec="seconds")
    if packet_path.is_file():
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        slot = packet.get("slot") or slot
        when = packet.get("generated_at") or when
    subject = args.subject or brief_subject(slot, when)
    receipt = deliver_superhuman(
        html_path,
        subject=subject,
        dry_run=args.dry_run,
        send_authorized_self=args.send_authorized_self,
    )
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("status") in {"ok", "dry-run"} else 1


def cmd_schedule(args: argparse.Namespace) -> int:
    if args.install:
        installed = schedule_install()
        print(json.dumps(installed, indent=2))
        return 0 if (
            installed.get("bootstrap_rc") == 0
            and installed.get("host_timezone_matches_report") is True
            and installed.get("configuration_ok") is True
            and installed.get("launchctl_ok") is True
        ) else 1
    status = schedule_status()
    print(json.dumps(status, indent=2))
    return 0 if (
        status.get("installed") is True
        and status.get("configuration_ok") is True
        and status.get("launchctl_ok") is True
    ) else 1


def cmd_proof(_args: argparse.Namespace) -> int:
    """Machine-rerunnable accept proof: collect+render under /tmp only."""
    proof_dir = Path("/tmp/shadow-brief-proof")
    proof_dir.mkdir(parents=True, exist_ok=True)
    packet = collect_packet()
    if not ((packet.get("authority") or {}).get("board_snapshot") or {}).get(
        "consistent"
    ):
        print("board snapshot did not stabilize", file=sys.stderr)
        return 1
    json_path = proof_dir / "latest.json"
    html_path = proof_dir / "latest.html"
    json_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(packet), encoding="utf-8")
    if not json_path.is_file() or html_path.stat().st_size < 500:
        return 1
    print(f"{json_path}\n{html_path}")
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    flags = os.O_RDONLY | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    identity: os.stat_result | None = None
    try:
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as exc:
            if not os.path.lexists(path):
                return []
            raise PrivateJSONLError(
                f"unsafe or corrupt private JSONL ledger {path}: unresolved path"
            ) from exc
        except OSError as exc:
            raise PrivateJSONLError(
                f"unsafe or corrupt private JSONL ledger {path}: open failed: {exc}"
            ) from exc
        identity = os.fstat(descriptor)
        named_identity = os.lstat(path)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != os.getuid()
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
            or stat.S_ISLNK(named_identity.st_mode)
            or not stat.S_ISREG(named_identity.st_mode)
            or named_identity.st_uid != os.getuid()
            or stat.S_IMODE(named_identity.st_mode) != 0o600
            or named_identity.st_nlink != 1
            or (identity.st_dev, identity.st_ino)
            != (named_identity.st_dev, named_identity.st_ino)
        ):
            raise PrivateJSONLError(
                f"unsafe or corrupt private JSONL ledger {path}: unsafe file identity"
            )
        handle = os.fdopen(descriptor, "r", encoding="utf-8")
        descriptor = None
        with handle:
            text = handle.read()
            final_identity = os.fstat(handle.fileno())
            final_named_identity = os.lstat(path)
            if (
                not stat.S_ISREG(final_identity.st_mode)
                or final_identity.st_uid != os.getuid()
                or stat.S_IMODE(final_identity.st_mode) != 0o600
                or final_identity.st_nlink != 1
                or stat.S_ISLNK(final_named_identity.st_mode)
                or not stat.S_ISREG(final_named_identity.st_mode)
                or final_named_identity.st_uid != os.getuid()
                or stat.S_IMODE(final_named_identity.st_mode) != 0o600
                or final_named_identity.st_nlink != 1
                or (identity.st_dev, identity.st_ino)
                != (final_identity.st_dev, final_identity.st_ino)
                or (identity.st_dev, identity.st_ino)
                != (final_named_identity.st_dev, final_named_identity.st_ino)
            ):
                raise PrivateJSONLError(
                    f"unsafe or corrupt private JSONL ledger {path}: identity changed while reading"
                )
    except PrivateJSONLError:
        raise
    except (OSError, UnicodeError) as exc:
        raise PrivateJSONLError(
            f"unsafe or corrupt private JSONL ledger {path}: read failed: {exc}"
        ) from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, RecursionError) as exc:
            raise PrivateJSONLError(
                f"unsafe or corrupt private JSONL ledger {path}: invalid JSON on line {line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise PrivateJSONLError(
                f"unsafe or corrupt private JSONL ledger {path}: non-object row on line {line_number}"
            )
        rows.append(row)
    return rows


def cmd_readback_window(args: argparse.Namespace) -> int:
    try:
        rows = _eligible_natural_window_receipts(_read_jsonl(WINDOW_LOG))
    except PrivateJSONLError as exc:
        result = {
            "schema": MAILBOX_READBACK_SCHEMA,
            "status": "blocked",
            "wake": (
                f"window ledger is unsafe or corrupt at {WINDOW_LOG}: {exc}; "
                "repair the exact private ledger before any mailbox provider read or append"
            ),
        }
        print(json.dumps(result, indent=2))
        return 1
    try:
        _read_jsonl(MAILBOX_READBACK_LOG)
    except PrivateJSONLError as exc:
        result = {
            "schema": MAILBOX_READBACK_SCHEMA,
            "status": "blocked",
            "wake": (
                f"mailbox ledger is unsafe or corrupt at {MAILBOX_READBACK_LOG}: {exc}; "
                "repair the exact private ledger before any mailbox provider read or append"
            ),
        }
        print(json.dumps(result, indent=2))
        return 1
    if args.scheduled_for:
        candidates = [
            row for row in rows if row.get("scheduled_for") == args.scheduled_for
        ]
    else:
        candidates = [row for row in rows if row.get("scheduled_for")]
    if not candidates:
        print("no matching scheduled-window receipt", file=sys.stderr)
        return 2
    readback = fetch_superhuman_mailbox_readback(
        sorted(candidates, key=_scheduled_window_sort_key)[-1]
    )
    _append_private_jsonl(MAILBOX_READBACK_LOG, readback)
    print(json.dumps(readback, indent=2))
    return 0 if readback.get("status") == "EXACT_SENT_CONFIRMED" else 1


def cmd_verify_windows(_args: argparse.Namespace) -> int:
    try:
        rows = _read_jsonl(WINDOW_LOG)
    except PrivateJSONLError as exc:
        result = {
            "ok": False,
            "status": "blocked",
            "problems": [
                f"window ledger is unsafe or corrupt at {WINDOW_LOG}: {exc}"
            ],
            "windows": [],
            "message_ids": [],
            "ignored_legacy_windows": [],
            "ignored_noncalendar_windows": [],
            "ignored_nonslot_windows": [],
            "mailbox_readbacks": {
                "ok": False,
                "problems": ["window ledger unavailable; mailbox proof was not read"],
                "message_ids": [],
            },
        }
        print(json.dumps(result, indent=2))
        return 1
    try:
        mailbox_rows = _read_jsonl(MAILBOX_READBACK_LOG)
    except PrivateJSONLError as exc:
        result = {
            "ok": False,
            "status": "blocked",
            "problems": [
                f"mailbox ledger is unsafe or corrupt at {MAILBOX_READBACK_LOG}: {exc}"
            ],
            "windows": [],
            "message_ids": [],
            "ignored_legacy_windows": [],
            "ignored_noncalendar_windows": [],
            "ignored_nonslot_windows": [],
            "mailbox_readbacks": {
                "ok": False,
                "problems": [
                    f"mailbox ledger is unsafe or corrupt at {MAILBOX_READBACK_LOG}: {exc}"
                ],
                "message_ids": [],
            },
        }
        print(json.dumps(result, indent=2))
        return 1
    result = verify_window_receipts(
        rows,
        evidence_dir=EVIDENCE_DIR,
        ledger_dir=LOG_DIR,
        send_attempt_log=SEND_ATTEMPT_LOG,
    )
    if len(result["windows"]) == 2:
        by_window = {
            str(row.get("scheduled_for")): row
            for row in _eligible_natural_window_receipts(rows)
        }
        latest = [by_window[str(value)] for value in result["windows"]]
        mailbox = verify_mailbox_readbacks(latest, mailbox_rows)
        result["mailbox_readbacks"] = mailbox
        result["problems"].extend(mailbox["problems"])
        result["ok"] = result["ok"] and mailbox["ok"]
    else:
        result["mailbox_readbacks"] = {
            "ok": False,
            "problems": ["waiting for two valid scheduled windows"],
            "message_ids": [],
        }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shadow-brief")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect")
    c.add_argument("--out")
    c.add_argument("--slot", choices=["morning", "evening"])
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_collect)

    r = sub.add_parser("render")
    r.add_argument("--in", dest="input")
    r.add_argument("--out")
    r.set_defaults(func=cmd_render)

    run = sub.add_parser("run")
    run.add_argument("--slot", choices=["morning", "evening"])
    run.add_argument("--deliver", action="store_true")
    run.add_argument("--send-authorized-self", action="store_true")
    run.add_argument("--scheduled-trigger", action="store_true", help=argparse.SUPPRESS)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    d = sub.add_parser("deliver")
    d.add_argument("--html")
    d.add_argument("--subject")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--send-authorized-self", action="store_true")
    d.set_defaults(func=cmd_deliver)

    s = sub.add_parser("schedule")
    s.add_argument("--install", action="store_true")
    s.add_argument("--status", action="store_true")
    s.set_defaults(func=cmd_schedule)

    pr = sub.add_parser("proof")
    pr.set_defaults(func=cmd_proof)

    vw = sub.add_parser("verify-windows")
    vw.set_defaults(func=cmd_verify_windows)

    rb = sub.add_parser("readback-window")
    rb.add_argument("--scheduled-for")
    rb.set_defaults(func=cmd_readback_window)

    doc = sub.add_parser("doctor")
    doc.set_defaults(func=lambda _a: doctor())
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
