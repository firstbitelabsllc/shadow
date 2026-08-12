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
import hashlib
import html
import json
import os
import plistlib
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LABEL = "com.leokwan.shadow-bidaily-brief"
SLOT_HOURS = (8, 20)
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
WINDOW_RECEIPT_SCHEMA = "shadow.bidaily-window.v2"
MAILBOX_READBACK_SCHEMA = "shadow.superhuman-mailbox-readback.v1"
SUPERHUMAN_MCP_RESOURCE = "https://mcp.mail.superhuman.com/mcp"
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
    stale: bool = False


@dataclass
class Recommendation:
    kind: str  # unify | streamline | challenge | focus | kill
    text: str
    source: str


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


def portfolio_root() -> Path:
    raw = os.environ.get("SHADOW_PORTFOLIO_ROOT") or os.environ.get("SHADOW_DEV_ROOT")
    return Path(raw).expanduser() if raw else DEFAULT_PORTFOLIO


def parse_plan(path: Path) -> EntityBrief:
    text = path.read_text(encoding="utf-8", errors="replace")
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
        if section_name == "contradictions" and clean.startswith("- ") and "| winner:" in clean:
            decisions.append(clean[2:])
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


def collect_board() -> dict[str, Any]:
    if not BOARD_PATH.is_file():
        return {"revision": None, "entities": [], "projects": [], "error": "board missing"}
    board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    entities: list[EntityBrief] = []
    for ent in board.get("entities") or []:
        plan_path = Path(ent.get("plan") or "")
        if not plan_path.is_file():
            entities.append(
                EntityBrief(
                    project=str(ent.get("project") or "unknown"),
                    plan=str(plan_path),
                    resume=ent.get("resume"),
                    entity_id=str(ent.get("id") or ""),
                    open_checkpoints=[],
                    blocked=[],
                    forgotten=[],
                )
            )
            continue
        brief = parse_plan(plan_path)
        brief.resume = ent.get("resume")
        brief.entity_id = str(ent.get("id") or "")
        if not brief.project:
            brief.project = str(ent.get("project") or brief.project)
        entities.append(brief)
    return {
        "revision": board.get("revision"),
        "schema": board.get("schema"),
        "projects": board.get("projects") or [],
        "claims": board.get("claims") or [],
        "entities": [asdict(e) for e in entities],
    }


def _read_board_revision() -> int | None:
    try:
        board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    revision = board.get("revision")
    return revision if isinstance(revision, int) else None


def collect_repos(root: Path, *, max_age_h: float = 168.0) -> list[RepoPaint]:
    paints: list[RepoPaint] = []
    if not root.is_dir():
        return paints
    now = time.time()
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
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


def collect_nia_status() -> dict[str, Any]:
    """Check whether the unattended runtime can use Nia without synthesizing claims."""
    nia = shutil.which("nia")
    if not nia:
        return {"available": False, "error": "Nia CLI is not installed"}
    proc = _run(
        [nia, "status", "--json"],
        timeout=20,
        env={
            "HOME": str(Path.home()),
            "PATH": os.environ.get("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"),
        },
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if proc.returncode != 0 or error:
        return {
            "available": False,
            "error": str(error or proc.stderr or "Nia CLI is not authenticated")[:300],
        }
    return {"available": True, "status": payload}


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


def collect_superhuman_context(*, acting_email: str = SELF_MAIL) -> dict[str, Any]:
    """Collect a privacy-bounded 24-hour mailbox signal rollup, never full bodies."""
    import urllib.error
    import urllib.request

    token = _mcp_remote_token()
    if not token:
        return {"available": False, "error": "Superhuman OAuth is unavailable"}
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
        start = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
        _, result = post({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "list_threads",
                "arguments": {
                    "acting_email": acting_email,
                    "start_date": start,
                    "limit": 25,
                    "sort": "newest",
                },
            },
        }, sid)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"available": False, "error": f"Superhuman read failed: {exc}"[:300]}
    payload = _mcp_text_payload(result)
    threads = [row for row in (payload.get("threads") or []) if isinstance(row, dict)]
    if not threads and payload.get("error"):
        return {"available": False, "error": str(payload.get("error"))[:300]}
    github = 0
    cursor_limit = 0
    human = 0
    unread = 0
    signals: list[dict[str, str]] = []
    for row in threads:
        subject = str(row.get("subject") or "")
        snippet = str(row.get("snippet") or "")
        participants = " ".join(str(value) for value in (row.get("participants") or []))
        message_text = " ".join(
            f"{message.get('subject', '')} {message.get('snippet', '')}"
            for message in (row.get("messages") or [])
            if isinstance(message, dict)
        )
        combined = f"{subject} {snippet} {participants} {message_text}".lower()
        if "unread" in [str(label).lower() for label in (row.get("labels") or [])]:
            unread += 1
        if "github" in combined:
            github += 1
        elif "noreply" not in combined and "no-reply" not in combined:
            human += 1
        if "usage limit" in combined or "usage/spend limit" in combined:
            cursor_limit += 1
        if len(signals) < 5:
            signals.append({
                "subject": subject[:160],
                "last_message_at": str(row.get("last_message_at") or ""),
                "kind": "github" if "github" in combined else "human_or_other",
            })
    return {
        "available": True,
        "acting_email": acting_email,
        "window_hours": 24,
        "threads_returned": len(threads),
        "total_estimate": payload.get("total_estimate"),
        "unread_threads": unread,
        "github_notification_threads": github,
        "human_or_other_threads": human,
        "cursor_limit_threads": cursor_limit,
        "signals": signals,
    }


def collect_snowcubes_context() -> dict[str, Any]:
    """Read the bounded business-mail signal and name every missing authority.

    This is deliberately a companion inside the one Shadow producer: it is not
    a storefront mirror, customer database, or separate task queue.
    """
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mail = collect_superhuman_context(acting_email=SNOWCUBES_BUSINESS_MAIL)
    if mail.get("available"):
        human = [row for row in mail.get("signals") or [] if row.get("kind") == "human_or_other"]
        reply = (
            "Reply now: review the newest human thread before any automated notification."
            if human
            else "No human reply was surfaced in the bounded 24-hour read."
        )
        relationship = (
            "Nurture: keep the next non-automated relationship visible after the reply-now item."
            if human
            else "Nurture: no relationship follow-up is inferred from an empty bounded read."
        )
        mail_state = "available"
        mail_wake = None
    else:
        reply = "Reply priority is unavailable; no inbox state is inferred."
        relationship = "Relationship follow-up is unavailable; no customer action is invented."
        mail_state = "unavailable"
        mail_wake = "Link trysnowcubes@gmail.com in Superhuman, then run the bounded read-only 24-hour thread query."

    unavailable = {
        "commerce": "Shopify read-only order and fulfillment adapter is not configured for this producer.",
        "funnel": "PostHog read-only Snowcubes project adapter is not configured for this producer.",
        "search": "Search Console read-only property adapter is not configured for this producer.",
        "local": "Google Business Profile read-only location adapter is not configured for this producer.",
        "lifecycle": "Resend/Supabase read-only lifecycle adapter is not configured for this producer.",
    }
    surfaces = [
        {
            "name": "Reply and relationships",
            "state": mail_state,
            "now": reply,
            "next": relationship,
            "source": "Superhuman business inbox",
            "observed_at": observed_at,
            "wake": mail_wake,
        },
        *[
            {
                "name": name.title(),
                "state": "unavailable",
                "now": "No current business fact is claimed.",
                "next": reason,
                "source": name,
                "observed_at": observed_at,
                "wake": f"Configure the read-only Snowcubes {name} adapter; the next natural morning window will read it.",
            }
            for name, reason in unavailable.items()
        ],
    ]
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
    entities = board.get("entities") or []
    claims = board.get("claims") or []

    # Focus: live claim first (what this computer is already doing), else priority resume.
    claimed_ids = {
        str(c.get("row") or c.get("task") or c.get("id") or "").lstrip("~")
        for c in claims
        if isinstance(c, dict)
    }
    ranked = sorted(
        entities,
        key=lambda e: (e.get("priority") is None, e.get("priority") or 99, e.get("project") or ""),
    )
    focus_ent = None
    focus_cp = None
    for ent in ranked:
        opens = ent.get("open_checkpoints") or []
        for cp in opens:
            if str(cp.get("id") or "") in claimed_ids:
                focus_ent, focus_cp = ent, cp
                break
        if focus_ent:
            break
    if focus_ent is None:
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
                text=f"Keep {focus_ent.get('project')} first: {title}",
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

    if not claims and ranked:
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
    friendly = {
        "ai-leo": "Twice-daily report",
        "resplit-ios": "Resplit",
        "resplit-runner": "Resplit build service",
        "local workspaces": "Local work",
        "portfolio": "All products",
    }
    if text.lower() in friendly:
        return friendly[text.lower()]
    words = text.replace("-", " ").split()
    return " ".join("iOS" if word.lower() == "ios" else word.capitalize() for word in words)


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

    entities = board.get("entities") or []
    claims = [row for row in (board.get("claims") or []) if isinstance(row, dict)]
    claim_rows = {str(row.get("row") or "").lstrip("~"): row for row in claims}
    ranked = sorted(
        entities,
        key=lambda row: (row.get("priority") is None, row.get("priority") or 99, row.get("project") or ""),
    )
    open_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    blocked_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entity in ranked:
        open_rows.extend((entity, cp) for cp in (entity.get("open_checkpoints") or []))
        blocked_rows.extend((entity, cp) for cp in (entity.get("blocked") or []))
    claimed = [pair for pair in open_rows if str(pair[1].get("id") or "") in claim_rows]
    unclaimed = [pair for pair in open_rows if str(pair[1].get("id") or "") not in claim_rows]
    dirty = [repo for repo in repos if repo.dirty]
    stale = [repo for repo in repos if repo.stale]
    healthy_vercel = sum(
        1 for row in (vercel.get("deployments") or []) if str(row.get("state") or "").upper() == "READY"
    )
    healthy_db = sum(
        1 for row in (supabase.get("projects") or []) if "HEALTHY" in str(row.get("status") or "").upper()
    )
    source_gaps = [name for name, health in source_health.items() if not health.get("available")]

    if claimed:
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
    operations = (
        f"The delivery surface is mixed but legible: {len(github)} proposed change"
        f"{'s are' if len(github) != 1 else ' is'} waiting for review; {healthy_vercel} web product"
        f"{'s are' if healthy_vercel != 1 else ' is'} ready; and {healthy_db} data service"
        f"{'s report' if healthy_db != 1 else ' reports'} healthy. "
        f"Local work is much noisier—{len(dirty)} projects have unfinished changes"
        + (f", including {len(stale)} older workspaces" if stale else "")
        + "—so unfinished local changes should explain risk, not become a parallel agenda."
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
    if source_gaps:
        missing_labels = {
            "nia": "fresh project history",
            "astro_aso": "App Store search visibility",
            "ahrefs_seo": "web search visibility",
            "app_store_connect": "App Store delivery status",
        }
        mail_read += " The note is also missing " + ", ".join(
            missing_labels.get(name, name.replace("_", " ")) for name in source_gaps[:5]
        ) + "; those absences lower confidence rather than being treated as zero activity."

    decided: list[dict[str, Any]] = []
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
    if mail.get("cursor_limit_threads"):
        decided.append({
            "title": "Treat Cursor’s review limit as degraded capacity, not a veto",
            "prose": (
                f"The mailbox contains {mail.get('cursor_limit_threads')} recent thread"
                f"{'s' if mail.get('cursor_limit_threads') != 1 else ''} mentioning a usage or spend limit. I am separating that missing automated opinion from product correctness: affected changes still need independent evidence, but they should not be described as failed merely because the automated reviewer skipped them."
            ),
            "evidence": ["Superhuman 24-hour thread sample", "GitHub review notifications"],
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
    if not source_health.get("nia", {}).get("available"):
        decided.append({
            "title": "Keep Nia as historical context until unattended freshness is proven",
            "prose": (
                "Nia surfaced valuable product history, but the automatic history check could not sign in and some indexed evidence predates today’s plans. "
                "Its conclusions may challenge a current decision; they may not silently replace today’s active plans."
            ),
            "evidence": ["Nia project-history research", "automatic Nia history check", "today’s portfolio snapshot"],
            "confidence": "high",
        })

    architecture: list[dict[str, Any]] = []
    for entity in ranked:
        for raw in (entity.get("decisions") or [])[-2:]:
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
            status = f"{marker} {human_datetime(status_tail)}".strip() if marker else "recorded in the current plan"
            architecture.append({
                "project": human_project_label(entity.get("project") or "unknown"),
                "decision": decision_text,
                "tradeoff": tradeoff_text,
                "status": status,
                "evidence": "recorded in the current product plan",
            })
    if not architecture:
        architecture.append({
            "project": "portfolio",
            "decision": "Shadow remains the priority and ownership authority; external systems are evidence sources, not replacement queues.",
            "tradeoff": "richer source aggregation versus duplicated task truth",
            "status": "active architecture",
            "evidence": "Shadow board and report contract",
        })

    questions: list[dict[str, str]] = []
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
    if source_gaps:
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
            else "No decision needs you right now"
        ),
        "prose": (
            "The requests below are the only current work that cannot continue without your decision."
            if direct_asks
            else "The active work can continue without a reply to this note. The questions below are challenges for your point of view, not blockers."
        ),
        "asks": direct_asks[:3],
    }

    etas: list[dict[str, str]] = []
    for entity, cp in claimed[:5]:
        claim = claim_rows.get(str(cp.get("id") or ""), {})
        checkpoint = readable_outcome(cp.get("title"))
        etas.append({
            "project": human_project_label(entity.get("project") or "unknown"),
            "outcome": checkpoint,
            "eta": str(claim.get("return_by") or "unknown"),
            "basis": "next scheduled evidence check; this is not a completion promise",
            "confidence": "medium" if claim.get("return_by") else "low",
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
    for entity, cp in blocked_rows[:4]:
        stalling.append({
            "project": human_project_label(entity.get("project") or "unknown"),
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
        stalling.append({
            "project": project,
            "signal": f"{count} ready pieces of work without an owner",
            "improvement": "start the most valuable result that can be finished and verified now, or explicitly leave the rest for later",
        })
    if stale and len(stalling) < 5:
        stalling.append({
            "project": "local workspaces",
            "signal": f"{len(stale)} older workspaces still contain unfinished changes",
            "improvement": "inspect only the ones that overlap an owned result; archive or ignore the rest instead of launching a cleanup campaign",
        })

    return {
        "executive_read": [opening, operations, mail_read],
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
            "historical_context": ["Nia indexed sources"],
            "rule": "missing or stale sources lower confidence; they never become zero activity or override today’s active plans",
        },
        "future_of_building": (
            "Building is no longer the technical inventory shown in the old report. It is a loop of promises: decide what should change, "
            "make the smallest real version, prove it with evidence, put it where people can reach it, and learn from what happens next. "
            "The report’s job is to show where each product sits in that loop and what is preventing the promise from moving forward."
        ),
    }


def collect_packet(*, slot: str | None = None) -> dict[str, Any]:
    started = datetime.now().astimezone()
    if slot is None:
        slot = "morning" if started.hour < 14 else "evening"
    root = portfolio_root()
    repos = collect_repos(root)
    github = collect_github()
    vercel = collect_vercel()
    supabase = collect_supabase()
    nia = collect_nia_status()
    mail = collect_superhuman_context()
    snowcubes = collect_snowcubes_context()
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
                "error": str(mail.get("error") or "Superhuman unavailable"),
                "wake": "refresh Superhuman mcp-remote OAuth, then run a read-only list_threads check",
            }
        ),
        "nia": (
            {"available": True}
            if nia.get("available")
            else {
                "available": False,
                "error": str(nia.get("error") or "Nia unavailable"),
                "wake": "nia login && nia status --json",
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
    status = _run(["shadow", "status", "--by", "leo"], timeout=60)
    board: dict[str, Any] = {}
    board_snapshot = {"consistent": False, "attempts": 0, "revision": None}
    for attempt in range(1, 4):
        board = collect_board()
        final_revision = _read_board_revision()
        board_snapshot = {
            "consistent": (
                isinstance(board.get("revision"), int)
                and board.get("revision") == final_revision
            ),
            "attempts": attempt,
            "revision": final_revision,
        }
        if board_snapshot["consistent"]:
            break
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
    generated = datetime.now().astimezone()
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
        "nia": nia,
        "superhuman_context": mail,
        "snowcubes_context": snowcubes,
        "paint_health": paint_health,
        "analysis": analysis,
        "recommendations": [asdict(r) for r in recs],
        "shadow_status_excerpt": (status.stdout or status.stderr or "")[:4000],
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
        parsed = parsed.astimezone()
    month_day = parsed.strftime("%b %d").replace(" 0", " ")
    hour = parsed.strftime("%I").lstrip("0") or "12"
    return f"{month_day} · {hour}:{parsed.strftime('%M')} {parsed.strftime('%p')}"


def render_html(packet: dict[str, Any]) -> str:
    slot = packet.get("slot") or "brief"
    when = packet.get("generated_at") or ""
    board = packet.get("board") or {}
    entities = board.get("entities") or []
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

    claimed_ids = {
        str(c.get("row") or c.get("task") or c.get("id") or "").lstrip("~")
        for c in claims
        if isinstance(c, dict)
    }
    active_entities = [
        ent for ent in entities if (ent.get("open_checkpoints") or ent.get("blocked"))
    ]
    focus_ent = None
    focus_cp = None
    for ent in active_entities:
        for cp in ent.get("open_checkpoints") or []:
            if str(cp.get("id") or "") in claimed_ids:
                focus_ent, focus_cp = ent, cp
                break
        if focus_ent:
            break
    if focus_ent is None:
        for ent in active_entities:
            opens = ent.get("open_checkpoints") or []
            if opens:
                focus_ent, focus_cp = ent, opens[0]
                break

    focus_project = project_label((focus_ent or {}).get("project"))
    focus_title = checkpoint_title(
        (focus_cp or {}).get("title"), (focus_ent or {}).get("project")
    )
    if focus_ent:
        headline = f"{focus_project} is the main move."
        quoted_focus = focus_title.rstrip(".!?") + "."
        motion = (
            "It is already in motion."
            if str((focus_cp or {}).get("id") or "") in claimed_ids
            else "It is ready to move."
        )
        summary = (
            f"{motion} The work in front is “{quoted_focus}” "
            f"Everything else should support that result or wait."
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
          <td class="map-node map-now"><span>Now</span><strong>{_esc(focus_project if focus_ent else 'Quiet')}</strong><small>{_esc('Current focus' if focus_ent else 'Finish before expanding.')}</small></td>
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
        moving = [cp for cp in opens if str(cp.get("id") or "") in claimed_ids]
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
            str(cp.get("id") or "") in claimed_ids for cp in opens
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
        f"<p>{_esc(dirty_total)} of {_esc(scanned_roots)} checked projects contain unfinished local work. "
        "That count is a risk signal, not a cleanup assignment; the exact technical inventory stays in the private machine receipt.</p>"
        if dirty_total
        else f"<p class='empty'>All {_esc(scanned_roots)} checked projects are clean.</p>"
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
    mail_html = (
        f"<p>{_esc(mail.get('threads_returned', 0))} recent threads sampled; "
        f"{_esc(mail.get('github_notification_threads', 0))} from automated development systems, "
        f"{_esc(mail.get('human_or_other_threads', 0))} human or other, and "
        f"{_esc(mail.get('cursor_limit_threads', 0))} mentioning Cursor capacity limits.</p>"
        if mail.get("available")
        else "<p class='empty'>Mail context could not be checked.</p>"
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
        "nia": ("Project history", "Historical product context was not refreshed, so it cannot strengthen or overturn today’s judgment."),
        "astro_aso": ("App Store visibility", "Keyword movement, ratings, and competitive search position are absent."),
        "ahrefs_seo": ("Web search visibility", "Organic demand, backlinks, and search-performance changes are absent."),
        "app_store_connect": ("App Store delivery", "The note cannot confirm processing, testing, or release state from App Store Connect."),
        "local_git": ("Local work", "The private machine inventory could not be checked."),
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

    snowcubes_cards = "".join(
        "<article class='story'>"
        f"<h3>{_esc(item.get('name'))} · {_esc(str(item.get('state') or 'unknown').upper())}</h3>"
        f"<p>{_esc(item.get('now'))}</p><p class='meta'>{_esc(item.get('next'))}</p>"
        f"<p class='meta'>Source: {_esc(item.get('source'))} · observed {_esc(human_datetime(item.get('observed_at')))}"
        + (f"<br/>Wake: {_esc(item.get('wake'))}" if item.get("wake") else "")
        + "</p></article>"
        for item in (snowcubes.get("surfaces") or [])
        if isinstance(item, dict)
    ) or "<p class='empty'>Snowcubes sources were not collected.</p>"
    snowcubes_html = (
        "<p class='section-intro'>One read-only morning companion. Reply and relationship signals rank first; every unavailable business source is explicit rather than guessed.</p>"
        + snowcubes_cards
    )

    evidence_html = f"""
      <p class="evidence-intro">These details support the read above. They are receipts, not a second list of work.</p>
      <div class="evidence-grid">
        <article><h3>Changes awaiting review</h3>{pr_html}</article>
        <article><h3>Unfinished local work</h3>{dirty_html}</article>
        <article><h3>Web delivery</h3>{vercel_html}</article>
        <article><h3>Data services</h3>{supabase_html}</article>
        <article><h3>Mail signal</h3>{mail_html}</article>
      </div>
    """

    executive_html = "".join(
        f"<p class='essay'>{_esc(paragraph)}</p>"
        for paragraph in (analysis.get("executive_read") or [summary])
    )
    decided_html = "".join(
        "<article class='judgment'>"
        f"<div class='confidence'>{_esc(str(item.get('confidence') or 'unknown').upper())} confidence</div>"
        f"<h3>{_esc(item.get('title'))}</h3>"
        f"<p>{_esc(item.get('prose'))}</p>"
        f"<p class='meta'>Because: {_esc(' · '.join(str(value) for value in (item.get('evidence') or [])))}</p>"
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
        f"<div class='confidence'>{'RESPONSE NEEDED' if needs_leo.get('requires_response') else 'NO RESPONSE NEEDED'}</div>"
        f"<h3>{_esc(needs_leo.get('title'))}</h3>"
        f"<p>{_esc(needs_leo.get('prose'))}</p>"
        + (f"<ul>{needs_leo_items}</ul>" if needs_leo_items else "")
        + "</article>"
    )
    architecture_html = "".join(
        "<article class='decision-record'>"
        f"<div class='project-chip'>{_esc(item.get('project'))}</div>"
        f"<h3>{_esc(item.get('decision'))}</h3>"
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

    title = f"Shadow {slot.title()} Note — {when}"
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
  .judgment, .decision-record, .challenge, .stall {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 16px 17px;
    margin-bottom: 12px;
  }}
  .judgment h3, .decision-record h3, .challenge h3, .stall h3 {{
    margin: 2px 0 8px;
    font-size: 19px;
    line-height: 1.3;
  }}
  .judgment p, .decision-record p, .challenge p, .stall p {{ margin: 7px 0; }}
  .confidence, .project-chip {{
    color: var(--accent);
    font: 700 10px/1.2 "Avenir Next", "Segoe UI", sans-serif;
    letter-spacing: .1em;
    text-transform: uppercase;
  }}
  .challenge {{ border-top: 3px solid var(--accent); }}
  .stall {{ border-top: 3px solid #c08a22; }}
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
      <p class="stamp">{_esc(slot.title())} note · twice-daily · {_esc(human_datetime(when))}</p>
      <h2>Today’s read</h2>
      <p class="summary">{_esc(summary)}</p>
    </header>

    {section("How this note thinks", source_flow_html)}
    {section("Snowcubes morning companion", snowcubes_html)}
    {section("What building looks like now", building_html)}
    {section("Where attention is going", map_html + attention_html)}
    {section("Every workstream, in human terms", workstreams_html)}
    {section("The deeper read", executive_html)}
    {section("Decided for you", decided_html)}
    {section("Needs Leo now", needs_leo_html)}
    {section("Architecture decisions you need to know about", architecture_html)}
    {section("Questions I’m challenging you on", questions_html)}
    {section("ETAs for completion", etas_html)}
    {section("Work that is stalling — and how to improve it", stalling_html)}
    {section("What can wait", what_can_wait_html)}
    {section("Supporting evidence", evidence_html)}
    {section("If a source could not be checked", recovery_html)}

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
    proc = _run(["osascript", "-e", script], timeout=10)
    return {
        "status": "ok" if proc.returncode == 0 else "blocked",
        "title": title,
        "body": body,
        "returncode": proc.returncode,
        "error": (proc.stderr or "")[:300] or None,
    }


def scheduled_window(now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now().astimezone()
    on_schedule = current.hour in SLOT_HOURS and 0 <= current.minute <= 30
    scheduled = current.replace(minute=0, second=0, microsecond=0) if on_schedule else None
    return {
        "on_schedule": on_schedule,
        "slot": "morning" if current.hour == 8 else "evening" if current.hour == 20 else None,
        "scheduled_for": scheduled.isoformat(timespec="seconds") if scheduled else None,
    }


def scheduled_windows_are_consecutive(first: datetime, second: datetime) -> bool:
    if any(value != 0 for value in (first.minute, first.second, second.minute, second.second)):
        return False
    if first.hour == 8:
        return second.date() == first.date() and second.hour == 20
    if first.hour == 20:
        return second.date() == first.date() + timedelta(days=1) and second.hour == 8
    return False


def launch_trigger_proof() -> dict[str, Any]:
    """Record whether this process was started directly by macOS launchd."""
    parent_pid = os.getppid()
    proc = _run(["ps", "-p", str(parent_pid), "-o", "comm="], timeout=5)
    parent_command = (proc.stdout or "").strip()
    return {
        "is_launchd": proc.returncode == 0 and Path(parent_command).name == "launchd",
        "parent_pid": parent_pid,
        "parent_command": parent_command or None,
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
        and Path(str(trigger_proof.get("parent_command") or "")).name == "launchd"
    )


def verify_window_receipts(
    rows: list[dict[str, Any]],
    *,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    scheduled = [row for row in rows if row.get("on_schedule") and row.get("scheduled_for")]
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
    eligible = [
        row
        for row in scheduled
        if row.get("schema") == WINDOW_RECEIPT_SCHEMA
        and row.get("trigger") == "launchd-calendar"
    ]
    latest_by_window = {str(row["scheduled_for"]): row for row in eligible}
    latest = [latest_by_window[key] for key in sorted(latest_by_window)[-2:]]
    problems: list[str] = []
    if len(latest) != 2:
        problems.append(
            f"need two distinct current-schema scheduled windows; found {len(latest)}"
        )
    else:
        first = datetime.fromisoformat(str(latest[0]["scheduled_for"]))
        second = datetime.fromisoformat(str(latest[1]["scheduled_for"]))
        if not scheduled_windows_are_consecutive(first, second):
            problems.append("latest scheduled windows are not consecutive")
        for row in latest:
            scheduled_for = str(row["scheduled_for"])
            receipt = row.get("receipt") or {}
            notification = row.get("notification") or {}
            if not scheduled_trigger_is_authorized(True, row.get("trigger_proof")):
                problems.append(f"{scheduled_for}: launchd trigger proof missing")
            scheduled_at: datetime | None = None
            generated: datetime | None = None
            try:
                scheduled_at = datetime.fromisoformat(scheduled_for)
                generated = datetime.fromisoformat(str(row.get("generated_at") or ""))
                expected_slot = "morning" if scheduled_at.hour == 8 else "evening"
                if row.get("slot") != expected_slot:
                    problems.append(f"{scheduled_for}: scheduled slot mismatch")
                if not scheduled_at <= generated <= scheduled_at + timedelta(minutes=30):
                    problems.append(f"{scheduled_for}: report generation is not fresh for slot")
            except ValueError:
                problems.append(f"{scheduled_for}: generated_at invalid")
            if not isinstance(row.get("board_revision"), int):
                problems.append(f"{scheduled_for}: missing board revision")
            if len(str(row.get("html_sha256") or "")) != 64:
                problems.append(f"{scheduled_for}: missing HTML hash")
            if len(str(row.get("json_sha256") or "")) != 64:
                problems.append(f"{scheduled_for}: missing JSON hash")
            if notification.get("status") != "ok":
                problems.append(f"{scheduled_for}: notification failed")
            if (
                notification.get("title") != "Shadow brief ready"
                or notification.get("body")
                != f"{row.get('slot')} · board rev {row.get('board_revision')}"
            ):
                problems.append(f"{scheduled_for}: notification identity mismatch")
            if receipt.get("status") != "ok" or receipt.get("delivery_status") != "sent" or not receipt.get("message_id"):
                problems.append(f"{scheduled_for}: sent-message receipt missing")
            if (
                receipt.get("attempt_state") != "PROVISIONAL_SENT"
                or len(str(receipt.get("attempt_id") or "")) != 24
            ):
                problems.append(f"{scheduled_for}: durable pre-send attempt receipt missing")
            if (
                receipt.get("acting_email") != SELF_MAIL
                or receipt.get("from") != SELF_MAIL
                or receipt.get("to") != [SELF_MAIL]
            ):
                problems.append(f"{scheduled_for}: exact self-mail route missing")
            expected_subject = f"Shadow {row.get('slot')} brief — {row.get('generated_at')}"
            if receipt.get("subject") != expected_subject:
                problems.append(f"{scheduled_for}: sent-message subject mismatch")
            try:
                sent_at = datetime.fromisoformat(str(receipt.get("sent_at") or ""))
                if (
                    scheduled_at is None
                    or generated is None
                    or not generated <= sent_at <= scheduled_at + timedelta(minutes=30)
                ):
                    problems.append(f"{scheduled_for}: sent timestamp is not fresh for slot")
            except ValueError:
                problems.append(f"{scheduled_for}: sent timestamp invalid")
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
        sent_message_ids = [(row.get("receipt") or {}).get("message_id") for row in latest]
        if all(sent_message_ids) and len(set(sent_message_ids)) != len(sent_message_ids):
            problems.append("scheduled windows do not have distinct sent-message receipts")
        if evidence_dir is not None:
            archives_by_hash: dict[str, Path] = {}
            for archive in evidence_dir.glob("brief-*.html"):
                try:
                    archives_by_hash[hashlib.sha256(archive.read_bytes()).hexdigest()] = archive
                except OSError:
                    continue
            json_archives_by_hash: dict[str, Path] = {}
            for archive in evidence_dir.glob("brief-*.json"):
                try:
                    json_archives_by_hash[hashlib.sha256(archive.read_bytes()).hexdigest()] = archive
                except OSError:
                    continue
            for row in latest:
                scheduled_for = str(row["scheduled_for"])
                archive = archives_by_hash.get(str(row.get("html_sha256") or ""))
                if archive is None:
                    problems.append(f"{scheduled_for}: no archived HTML matches receipt hash")
                    continue
                try:
                    rendered = archive.read_text(encoding="utf-8")
                except OSError:
                    problems.append(f"{scheduled_for}: archived HTML unreadable")
                    continue
                if f"board rev {row.get('board_revision')}" not in rendered:
                    problems.append(f"{scheduled_for}: archived HTML board revision mismatch")
                required_html = (
                    "<!DOCTYPE html>",
                    'name="viewport"',
                    str(row.get("generated_at") or ""),
                    "Today’s read",
                    "How this note thinks",
                    "What building looks like now",
                    "Where attention is going",
                    "Every workstream, in human terms",
                    "The deeper read",
                    "Decided for you",
                    "Needs Leo now",
                    "Architecture decisions you need to know about",
                    "Questions I’m challenging you on",
                    "ETAs for completion",
                    "Work that is stalling — and how to improve it",
                    "What can wait",
                    "Supporting evidence",
                    "If a source could not be checked",
                    "Supporting checks inform the note; they do not create another to-do list.",
                )
                if any(marker not in rendered for marker in required_html):
                    problems.append(f"{scheduled_for}: archived HTML missing report structure")
                json_archive = json_archives_by_hash.get(str(row.get("json_sha256") or ""))
                if json_archive is None:
                    problems.append(f"{scheduled_for}: no archived JSON matches receipt hash")
                    continue
                try:
                    packet = json.loads(json_archive.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    problems.append(f"{scheduled_for}: archived JSON unreadable")
                    continue
                if packet.get("generated_at") != row.get("generated_at"):
                    problems.append(f"{scheduled_for}: archived JSON generation mismatch")
                if (packet.get("board") or {}).get("revision") != row.get("board_revision"):
                    problems.append(f"{scheduled_for}: archived JSON board revision mismatch")
                board_snapshot = (packet.get("authority") or {}).get("board_snapshot") or {}
                if (
                    board_snapshot.get("consistent") is not True
                    or board_snapshot.get("revision") != row.get("board_revision")
                ):
                    problems.append(f"{scheduled_for}: board snapshot consistency missing")
                if (packet.get("paint_health") or {}) != (row.get("paint_health") or {}):
                    problems.append(f"{scheduled_for}: archived JSON paint health mismatch")
    return {
        "ok": not problems,
        "problems": problems,
        "windows": [row.get("scheduled_for") for row in latest],
        "message_ids": [(row.get("receipt") or {}).get("message_id") for row in latest],
        "ignored_legacy_windows": ignored_legacy,
        "ignored_noncalendar_windows": ignored_noncalendar,
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
        if readback.get("subject") != (window.get("receipt") or {}).get("subject"):
            problems.append(f"{scheduled_for}: mailbox subject mismatch")
        if readback.get("generated_at") != window.get("generated_at"):
            problems.append(f"{scheduled_for}: mailbox generation mismatch")
        if readback.get("board_revision") != window.get("board_revision"):
            problems.append(f"{scheduled_for}: mailbox board revision mismatch")
        if not readback.get("message_id") or not readback.get("thread_id"):
            problems.append(f"{scheduled_for}: stable mailbox identity missing")
        if "SENT" not in (readback.get("labels") or []):
            problems.append(f"{scheduled_for}: SENT label missing")
        if len(str(readback.get("raw_html_sha256") or "")) != 64:
            problems.append(f"{scheduled_for}: mailbox HTML hash missing")
        try:
            scheduled_at = datetime.fromisoformat(scheduled_for)
            sent_at = datetime.fromisoformat(str(readback.get("sent_at") or ""))
            if not scheduled_at <= sent_at <= scheduled_at + timedelta(minutes=30):
                problems.append(f"{scheduled_for}: mailbox sent timestamp is not fresh")
        except ValueError:
            problems.append(f"{scheduled_for}: mailbox sent timestamp invalid")
    message_ids = [row.get("message_id") for row in confirmed]
    if len(message_ids) == len(windows) and len(set(message_ids)) != len(message_ids):
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
) -> None:
    if not scheduled_trigger_is_authorized(scheduled_trigger, summary.get("trigger_proof")):
        return
    window = scheduled_window(now)
    if not window["on_schedule"]:
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
        except json.JSONDecodeError:
            return {"raw": raw[:500]}
    for chunk in reversed(chunks):
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {"raw": "\n".join(chunks)[:800]}


def _mcp_text_payload(result: dict[str, Any]) -> dict[str, Any]:
    content = ((result.get("result") or {}).get("content") or [])
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        try:
            payload = json.loads(item.get("text") or "")
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _append_private_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    try:
        handle = os.fdopen(descriptor, "a", encoding="utf-8")
    except BaseException:
        os.close(descriptor)
        raise
    with handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)


def record_send_attempt(
    html_path: Path,
    *,
    subject: str,
    draft_id: str,
    thread_id: str | None,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    intent = {
        "schema": "shadow.superhuman-send-attempt.v1",
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


def _normalized_email(value: Any) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", str(value), re.I)
    return match.group(0).lower() if match else ""


def fetch_superhuman_mailbox_readback(window: dict[str, Any]) -> dict[str, Any]:
    """Confirm one sent report through stable mailbox thread/message reads."""
    import urllib.error
    import urllib.request

    scheduled_for = str(window.get("scheduled_for") or "")
    receipt = window.get("receipt") or {}
    subject = str(receipt.get("subject") or "")
    base = {
        "schema": MAILBOX_READBACK_SCHEMA,
        "scheduled_for": scheduled_for,
        "generated_at": window.get("generated_at"),
        "board_revision": window.get("board_revision"),
        "acting_email": SELF_MAIL,
        "subject": subject,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        scheduled_at = datetime.fromisoformat(scheduled_for)
    except ValueError:
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
        candidates = [
            item
            for item in (listed_payload.get("threads") or [])
            if isinstance(item, dict)
            and item.get("subject") == subject
            and "SENT" in (item.get("labels") or [])
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
        thread_id = str(candidate.get("thread_id") or "")
        message_id = str(candidate.get("last_message_id") or "")
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
    message = message_payload.get("message") or {}
    raw_html = str(message.get("raw_html") or "")
    from_email = _normalized_email(message.get("from"))
    to_emails = [_normalized_email(value) for value in (message.get("to") or [])]
    labels = message.get("labels") or []
    sent_at = str(message.get("sent_at") or "")
    problems: list[str] = []
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
    try:
        sent = datetime.fromisoformat(sent_at)
        if not scheduled_at <= sent <= scheduled_at + timedelta(minutes=30):
            problems.append("sent timestamp outside scheduled window")
    except ValueError:
        problems.append("sent timestamp invalid")
    required_html = (
        str(window.get("generated_at") or ""),
        f"board rev {window.get('board_revision')}",
        "Supporting checks inform the note; they do not create another to-do list.",
    )
    if any(marker not in raw_html for marker in required_html):
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
        "schema": "shadow.superhuman-send-attempt.v1",
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


def schedule_configuration_problems(
    installed: dict[str, Any],
    expected: dict[str, Any],
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
    return [key for key in keys if installed.get(key) != expected.get(key)]


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
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)])
    load = _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)])
    return {
        "plist": str(plist_path),
        "bootstrap_rc": load.returncode,
        "bootstrap_err": (load.stderr or "")[:300],
        "hours": list(SLOT_HOURS),
    }


def schedule_status() -> dict[str, Any]:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    if not plist_path.is_file():
        return {"installed": False, "plist": str(plist_path)}
    with plist_path.open("rb") as fh:
        doc = plistlib.load(fh)
    arguments = doc.get("ProgramArguments") or []
    program = Path(arguments[1]) if len(arguments) > 1 else Path(__file__).resolve()
    expected = launch_agent_plist(program)
    configuration_problems = schedule_configuration_problems(doc, expected)
    if not program.is_file():
        configuration_problems.append("ProgramFile")
    uid = os.getuid()
    print_out = _run(["launchctl", "print", f"gui/{uid}/{LABEL}"])
    return {
        "installed": True,
        "plist": str(plist_path),
        "StartCalendarInterval": doc.get("StartCalendarInterval"),
        "ProgramArguments": doc.get("ProgramArguments"),
        "EnvironmentVariables": doc.get("EnvironmentVariables"),
        "configuration_ok": not configuration_problems,
        "configuration_problems": configuration_problems,
        "launchctl_rc": print_out.returncode,
        "launchctl_ok": print_out.returncode == 0,
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
    elif not sched.get("configuration_ok"):
        problems.append(
            "schedule configuration drift: "
            + ", ".join(sched.get("configuration_problems") or [])
            + " — run schedule --install"
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
    packet = collect_packet(slot=args.slot)
    board_snapshot = ((packet.get("authority") or {}).get("board_snapshot") or {})
    if board_snapshot.get("consistent") is not True:
        summary = {
            "schema": WINDOW_RECEIPT_SCHEMA,
            "status": "blocked",
            "generated_at": packet.get("generated_at"),
            "board_revision": (packet.get("board") or {}).get("revision"),
            "trigger_proof": trigger_proof,
            "board_snapshot": board_snapshot,
            "wake": (
                "shadow status --json --by codex stabilizes at one board revision; "
                "then run read-only shadow-brief collect; never retry the scheduled send"
            ),
        }
        print(json.dumps(summary, indent=2))
        (LOG_DIR / "last-run.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        return 1
    if args.scheduled_trigger:
        try:
            trigger_window = scheduled_window(
                datetime.fromisoformat(str(packet.get("generated_at") or ""))
            )
        except ValueError:
            trigger_window = {"on_schedule": False, "scheduled_for": None}
        existing_window = any(
            row.get("schema") == WINDOW_RECEIPT_SCHEMA
            and row.get("trigger") == "launchd-calendar"
            and row.get("scheduled_for") == trigger_window.get("scheduled_for")
            for row in _read_jsonl(WINDOW_LOG)
        )
        if not trigger_window.get("on_schedule") or existing_window:
            reason = (
                "scheduled trigger is outside the 08:00/20:00 freshness window"
                if not trigger_window.get("on_schedule")
                else "this scheduled window already has a durable receipt"
            )
            summary = {
                "schema": WINDOW_RECEIPT_SCHEMA,
                "status": "blocked",
                "generated_at": packet.get("generated_at"),
                "board_revision": (packet.get("board") or {}).get("revision"),
                "trigger_proof": trigger_proof,
                "scheduled_for": trigger_window.get("scheduled_for"),
                "wake": f"{reason}; do not notify or send again",
            }
            print(json.dumps(summary, indent=2))
            (LOG_DIR / "last-run.json").write_text(
                json.dumps(summary, indent=2) + "\n",
                encoding="utf-8",
            )
            return 3
    json_path = EVIDENCE_DIR / "latest.json"
    html_path = EVIDENCE_DIR / "latest.html"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    write_packet(packet, json_path, html_path)
    archive_html_path = EVIDENCE_DIR / f"brief-{stamp}.html"
    archive_html_path.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
    archive_json_path = EVIDENCE_DIR / f"brief-{stamp}.json"
    archive_json_path.write_bytes(json_path.read_bytes())
    subject = f"Shadow {packet['slot']} brief — {packet['generated_at']}"
    notification = macos_notify(
        "Shadow brief ready",
        f"{packet['slot']} · board rev {packet.get('board', {}).get('revision')}",
    )
    receipt: dict[str, Any] = {"status": "skipped", "notes": "deliver not requested"}
    if args.deliver:
        receipt = deliver_superhuman(
            html_path,
            subject=subject,
            dry_run=args.dry_run,
            send_authorized_self=args.send_authorized_self,
        )
    summary = {
        "schema": WINDOW_RECEIPT_SCHEMA,
        "trigger_proof": trigger_proof,
        "generated_at": packet["generated_at"],
        "board_revision": packet.get("board", {}).get("revision"),
        "json": str(json_path),
        "html": str(html_path),
        "archive_html": str(archive_html_path),
        "archive_json": str(archive_json_path),
        "html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
        "json_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
        "notification": notification,
        "paint_health": packet.get("paint_health") or {},
        "receipt": receipt,
    }
    print(json.dumps(summary, indent=2))
    (LOG_DIR / "last-run.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    append_scheduled_window(summary, scheduled_trigger=args.scheduled_trigger)
    return run_exit_code(receipt, notification, scheduled_trigger=args.scheduled_trigger)


def cmd_deliver(args: argparse.Namespace) -> int:
    html_path = Path(args.html) if args.html else EVIDENCE_DIR / "latest.html"
    if not html_path.is_file():
        print("missing html — run render first", file=sys.stderr)
        return 2
    packet_path = EVIDENCE_DIR / "latest.json"
    slot = "brief"
    when = datetime.now().astimezone().isoformat(timespec="seconds")
    if packet_path.is_file():
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        slot = packet.get("slot") or slot
        when = packet.get("generated_at") or when
    subject = args.subject or f"Shadow {slot} brief — {when}"
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
        print(json.dumps(schedule_install(), indent=2))
        return 0
    print(json.dumps(schedule_status(), indent=2))
    return 0 if schedule_status().get("launchctl_ok") else 1


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
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def cmd_readback_window(args: argparse.Namespace) -> int:
    rows = _read_jsonl(WINDOW_LOG)
    if args.scheduled_for:
        candidates = [
            row for row in rows if row.get("scheduled_for") == args.scheduled_for
        ]
    else:
        candidates = [row for row in rows if row.get("scheduled_for")]
    if not candidates:
        print("no matching scheduled-window receipt", file=sys.stderr)
        return 2
    readback = fetch_superhuman_mailbox_readback(candidates[-1])
    _append_private_jsonl(MAILBOX_READBACK_LOG, readback)
    print(json.dumps(readback, indent=2))
    return 0 if readback.get("status") == "EXACT_SENT_CONFIRMED" else 1


def cmd_verify_windows(_args: argparse.Namespace) -> int:
    rows = _read_jsonl(WINDOW_LOG)
    result = verify_window_receipts(rows, evidence_dir=EVIDENCE_DIR)
    if len(result["windows"]) == 2:
        by_window = {
            str(row.get("scheduled_for")): row
            for row in rows
            if row.get("schema") == WINDOW_RECEIPT_SCHEMA
            and row.get("trigger") == "launchd-calendar"
        }
        latest = [by_window[str(value)] for value in result["windows"]]
        mailbox = verify_mailbox_readbacks(latest, _read_jsonl(MAILBOX_READBACK_LOG))
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
