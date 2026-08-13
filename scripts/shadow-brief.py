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

import shadow_root_board as _shadow_board

LABEL = "com.leokwan.shadow-bidaily-brief"
SLOT_HOURS = (8, 20)
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


def collect_shadow_status_excerpt() -> str:
    """Keep the optional seat summary from taking down the authoritative packet."""
    try:
        status = _run(["shadow", "status", "--by", "leo"], timeout=60)
    except subprocess.TimeoutExpired:
        return (
            "Optional seat-status summary timed out; the report continued from the "
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
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "revision": None,
            "entities": [],
            "projects": [],
            "claims": [],
            "error": f"board unreadable: {exc}",
            "wake": "Restore a readable local Shadow board, then run shadow status --by leo.",
        }
    # The root board owns project priority; a plan's own Priority line is stale
    # as soon as `shadow priority --value` moves the board-owned value.
    board_priority = {
        str(project.get("id") or ""): project.get("priority")
        for project in (board.get("projects") or [])
        if isinstance(project, dict) and isinstance(project.get("priority"), int)
    }
    entities: list[EntityBrief] = []
    for ent in board.get("entities") or []:
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
    human_signals: list[dict[str, Any]] = []
    other_signals: list[dict[str, Any]] = []
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
        if "unread" in [str(label).lower() for label in (row.get("labels") or [])]:
            unread += 1
        if "github" in combined:
            github += 1
            kind = "github"
        elif automated:
            kind = "automated"
        else:
            human += 1
            kind = "human_or_other"
        if "usage limit" in combined or "usage/spend limit" in combined:
            cursor_limit += 1
        # The connector occasionally supplies a direct thread URL. Keep it
        # only when it is a real HTTPS URL; never manufacture a provider URL
        # from an opaque ID. Thread IDs stay in the private packet so the
        # reader can reconcile a signal without copying the inbox.
        native_link = next(
            (
                str(row.get(key)).strip()
                for key in ("native_link", "thread_url", "web_url", "url", "link")
                if str(row.get(key) or "").strip().startswith(("https://", "http://"))
            ),
            None,
        )
        thread_id = row.get("thread_id") or row.get("id")
        labels = {str(label).lower() for label in (row.get("labels") or [])}
        signal = {
            "subject": subject[:160],
            "last_message_at": str(row.get("last_message_at") or ""),
            "kind": kind,
            "thread_id": str(thread_id)[:200] if thread_id else None,
            "unread": "unread" in labels,
            "native_link": native_link,
        }
        if kind == "human_or_other" and len(human_signals) < 5:
            human_signals.append(signal)
        elif len(other_signals) < 5:
            other_signals.append(signal)
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
        "signals": (human_signals + other_signals)[:5],
    }


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
    thread_id: str | None = None,
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
    if thread_id:
        # This is private evidence for reconciliation, not a customer queue.
        card["thread_id"] = thread_id
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
    if mail.get("available"):
        human = [row for row in mail.get("signals") or [] if row.get("kind") == "human_or_other"]
        newest = next((row for row in human if row.get("native_link")), None)
        if newest:
            reply = "Reply now: review the newest linked human thread before any automated notification."
            relationship = "Nurture: keep the next linked non-automated relationship visible after the reply-now item."
            mail_state = "available"
            mail_wake = None
            mail_link = newest.get("native_link")
            mail_thread_id = newest.get("thread_id")
            proposal = "Proposal only: open this thread in Superhuman and prepare a reply for Leo to approve; no draft or send was created."
        elif human:
            reply = "A possible human thread was read, but the connector did not supply a verified Superhuman link; it is not ranked as a reply."
            relationship = "No relationship follow-up is inferred until a direct native thread route is available."
            mail_state = "unknown"
            mail_wake = "Return a verified Superhuman thread URL from the bounded business-inbox read; do not manufacture a URL from an opaque thread ID."
            mail_link = None
            mail_thread_id = None
            proposal = None
        else:
            reply = "No human correspondence with a verified Superhuman link was surfaced in the bounded 24-hour read."
            relationship = "No relationship follow-up is inferred from the bounded read."
            mail_state = "unknown"
            mail_wake = "Return a bounded human correspondence result with a verified Superhuman thread URL; no inbox state is inferred from automated notices."
            mail_link = None
            mail_thread_id = None
            proposal = None
    else:
        reply = "Reply priority is unavailable; no inbox state is inferred."
        relationship = "Relationship follow-up is unavailable; no customer action is invented."
        mail_state = "unavailable"
        mail_wake = "Link trysnowcubes@gmail.com in Superhuman, then run the bounded read-only 24-hour thread query."
        mail_link = None
        mail_thread_id = None
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
            native_link=mail_link,
            proposal=proposal,
            thread_id=mail_thread_id,
        ),
        _snowcubes_surface(
            name="Relationships to nurture",
            state=mail_state,
            now=relationship,
            next_action=(
                "Keep the relationship visible after Leo reviews the reply-now item."
                if mail_state == "available"
                else "No relationship action is inferred until the business read includes a verified native thread route."
            ),
            source="Superhuman business inbox (trysnowcubes@gmail.com)",
            observed_at=observed_at,
            wake=mail_wake,
            native_link=mail_link,
            proposal=(
                "Proposal only: after Leo approves the reply, keep a short personal follow-up in view; no draft or send was created."
                if mail_state == "available" and newest
                else None
            ),
            thread_id=mail_thread_id,
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
            "The collector now reconstructs complete large plans instead of reading their pointer files, "
            "and the morning and evening editions now share one reader-first editorial contract."
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
            f"This window contains {len(subjects)} related source updates and {len(reviews)} open review"
            f"{'s' if len(reviews) != 1 else ''}, but their titles do not yet establish one product-level outcome."
        )
    if subjects:
        return (
            f"This window contains {len(subjects)} related source update{'s' if len(subjects) != 1 else ''}, "
            "but their titles do not yet establish one product-level outcome."
        )
    return (
        f"{len(reviews)} related proposal{'s are' if len(reviews) != 1 else ' is'} awaiting review, "
        "but the review titles do not yet establish one product-level outcome."
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
        evidence = [
            f"{len(subjects)} recent source change{'s' if len(subjects) != 1 else ''}"
            if subjects
            else f"{len(reviews)} open review{'s' if len(reviews) != 1 else ''}"
        ]
        if facts["plan"]:
            evidence.append("current operating-plan receipts")
        if reviews and subjects:
            evidence.append(f"{len(reviews)} open review{'s' if len(reviews) != 1 else ''}")
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
    decision_source_gaps = [name for name in source_gaps if name != "nia"]
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
            f" Across the supporting systems, {len(github)} proposed change"
            f"{'s remain' if len(github) != 1 else ' remains'} in review, {healthy_vercel} web product"
            f"{'s have' if healthy_vercel != 1 else ' has'} a ready provider receipt, and {healthy_db} data service"
            f"{'s report' if healthy_db != 1 else ' reports'} healthy. These are different proof levels, not a single ‘shipped’ count. "
            f"The {len(dirty)} projects with unfinished local changes stay in the evidence appendix unless one overlaps an owned outcome."
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
    now = datetime.now().astimezone()
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
    snowcubes_mail = collect_superhuman_context(acting_email=SNOWCUBES_BUSINESS_MAIL)
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
    status_excerpt = collect_shadow_status_excerpt()
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

    title = f"Shadow {slot.title()} Note — {when}"
    report_body = (
        section("What materially changed", material_changes_html)
        + section("The chief-of-staff read", executive_html)
        + section("Decided for you", decided_html)
        + section("Needs Leo now", needs_leo_html)
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
      <p class="stamp">{_esc(slot.title())} note · twice-daily · {_esc(human_datetime(when))}</p>
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


def natural_windows_are_consecutive(first: datetime, second: datetime) -> bool:
    if any(value != 0 for value in (first.minute, first.second, second.minute, second.second)):
        return False
    if first.hour == 8:
        return second.hour == 20 and second.date() == first.date()
    if first.hour == 20:
        return second.hour == 8 and second.date() == first.date() + timedelta(days=1)
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
    ignored_nonslot = [
        str(row["scheduled_for"])
        for row in scheduled
        if row.get("schema") == WINDOW_RECEIPT_SCHEMA
        and row.get("trigger") == "launchd-calendar"
        and row.get("slot") not in {"morning", "evening"}
    ]
    eligible = [
        row
        for row in scheduled
        if row.get("schema") == WINDOW_RECEIPT_SCHEMA
        and row.get("trigger") == "launchd-calendar"
        and row.get("slot") in {"morning", "evening"}
    ]
    latest_by_window = {str(row["scheduled_for"]): row for row in eligible}
    latest = [latest_by_window[key] for key in sorted(latest_by_window)[-2:]]
    problems: list[str] = []
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
            expected_subject = brief_subject(row.get("slot"), row.get("generated_at"))
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
    trigger_window: dict[str, Any] = {}
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
                "scheduled_window": trigger_window,
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
    subject = brief_subject(packet["slot"], packet["generated_at"])
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
        "scheduled_window": trigger_window,
        "scheduled_for": trigger_window.get("scheduled_for"),
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
    append_scheduled_window(
        summary,
        scheduled_trigger=args.scheduled_trigger,
        window=trigger_window,
    )
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
            and row.get("slot") == "morning"
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
