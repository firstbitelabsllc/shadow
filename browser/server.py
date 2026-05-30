#!/usr/bin/env python3
"""
vidux browser — local web UI for viewing PLAN.md across the fleet.

Read-mostly viewer. Local-only write endpoints append artifacts/INBOX notes.
Stdlib only. See projects/vidux-browser/PLAN.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import uuid
from glob import glob
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Receipt corpus lab handlers (math-fortress T9). Sibling package — server.py
# is callable both as __main__ (sys.path[0] = browser/) and via importlib spec
# from tests (sys.path[0] = caller CWD). Insert browser/ explicitly so the
# import resolves regardless of caller.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import handler as _receipts_handler

DEV_ROOT = Path(os.environ.get("VIDUX_DEV_ROOT", Path.home() / "Development")).expanduser().resolve()
HOST = os.environ.get("VIDUX_BROWSER_HOST", "127.0.0.1")
PORT = int(os.environ.get("VIDUX_BROWSER_PORT", "7191"))

BROWSER_DIR = Path(__file__).resolve().parent
STATIC_DIR = BROWSER_DIR / "static"
ARTIFACTS_DIR = BROWSER_DIR / "artifacts"

# Plan-layout conventions. The two-segment vidux/projects/ai patterns catch
# parent plans (e.g., `vidux/design-overhaul/PLAN.md`); the `**` recursive forms
# pick up sub-plans nested under those parents (e.g.,
# `vidux/design-overhaul/<child>/PLAN.md`). Recursive globs land MORE files but
# `discover_plans()` dedupes by resolved path so we never count twice. Override
# via env `VIDUX_PLAN_GLOBS` (colon-separated) for non-standard fleets.
PLAN_GLOBS = (
    os.environ.get("VIDUX_PLAN_GLOBS", "").split(":")
    if os.environ.get("VIDUX_PLAN_GLOBS")
    else [
        "*/ai/plans/*/PLAN.md",
        "*/vidux/*/PLAN.md",
        "*/vidux/**/PLAN.md",
        "*/projects/*/PLAN.md",
        "*/projects/**/PLAN.md",
        "*/PLAN.md",
    ]
)

# Aliases for historical checkout names that can still contain copied vidux
# plans (e.g., a repo was renamed but old clones still exist). When the same
# plan resolves under both names, prefer the canonical checkout. Override via
# env `VIDUX_REPO_ALIASES` as JSON (e.g. '{"oldname": "newname"}').
def _parse_repo_aliases():
    raw = os.environ.get("VIDUX_REPO_ALIASES", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}
LEGACY_REPO_ALIASES = _parse_repo_aliases()

PLANS_CACHE_TTL_SECONDS = float(os.environ.get("VIDUX_PLANS_CACHE_TTL_SECONDS", "20"))
_PLANS_CACHE_LOCK = threading.Lock()
_PLANS_CACHE: dict[str, object] = {
    "key": None,
    "expires_at": 0.0,
    "plans": None,
}


def clear_plans_cache() -> None:
    with _PLANS_CACHE_LOCK:
        _PLANS_CACHE["key"] = None
        _PLANS_CACHE["expires_at"] = 0.0
        _PLANS_CACHE["plans"] = None


def discover_plans_cached() -> list[dict]:
    """Cache the fleet index briefly so auto-refresh does not rescan every hit."""
    if PLANS_CACHE_TTL_SECONDS <= 0:
        return discover_plans()

    key = (str(DEV_ROOT), tuple(PLAN_GLOBS), tuple(sorted(LEGACY_REPO_ALIASES.items())))
    now = time.monotonic()
    with _PLANS_CACHE_LOCK:
        plans = _PLANS_CACHE["plans"]
        if plans is not None and _PLANS_CACHE["key"] == key and now < _PLANS_CACHE["expires_at"]:
            return plans  # type: ignore[return-value]

        plans = discover_plans()
        _PLANS_CACHE["key"] = key
        _PLANS_CACHE["expires_at"] = time.monotonic() + PLANS_CACHE_TTL_SECONDS
        _PLANS_CACHE["plans"] = plans
        return plans

# Files to expose alongside PLAN.md when present.
# Note: PLAN.md, INBOX.md, investigations/, evidence/ are core /vidux per the
# canonical doctrine (DOCTRINE.md + guides/fleet-ops.md + guides/investigation.md
# + guides/evidence-format.md). PROGRESS.md as a separate file and ASK-LEO.md
# are Leo-fleet extensions; the browser surfaces them when present but does not
# require them — a clean canonical-vidux repo without those files still works.
SIBLING_FILES = ["PROGRESS.md", "INBOX.md", "ASK-LEO.md", "DOCTRINE.md", "README.md"]

# safe_resolve() whitelist. Any other filename under DEV_ROOT is rejected —
# without this gate, a malicious page could fetch /api/file?path=…/.env or
# …/.ssh/config from a browser tab on Leo's machine.
ALLOWED_PLAN_FILES = frozenset({"PLAN.md", *SIBLING_FILES})

HOT_DAYS = 7
STALE_DAYS = 30

ARTIFACT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ARTIFACT_MAX_BYTES = 1024 * 1024  # 1 MB cap on POSTed HTML
ARTIFACT_TITLE_RE = re.compile(
    r"<title>([^<]+)</title>|<h1[^>]*>([^<]+)</h1>", re.I
)
PLAN_NOTE_MAX_BYTES = 16 * 1024
PLAN_NOTE_SOURCE_RE = re.compile(r"[^A-Za-z0-9_.:/@ -]+")
COMMENTS_FILE = Path(
    os.environ.get("VIDUX_BROWSER_COMMENTS_FILE", Path.home() / ".vidux-browser" / "comments.jsonl")
).expanduser()
COMMENT_BODY_MAX_BYTES = 8 * 1024
COMMENT_AUTHOR_MAX_CHARS = 80
COMMENT_AUTHOR_RE = re.compile(r"[^A-Za-z0-9_.:/@' -]+")
COMMENT_ANCHOR_FIELD_LIMITS = {
    "selector": 160,
    "label": 180,
    "excerpt": 360,
    "tag": 32,
    "kind": 32,
}
COMMENT_ANCHOR_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
JSON_CONTENT_TYPE = "application/json"

# /vidux task-FSM markers. Used by task_stats() to compute completion-bar.
# Per /vidux doctrine: completion (X/Y tasks) is the headline; ETA is parsed
# but does not drive the UI (tasks vary in difficulty, ETA is fiction).
TASKS_SECTION_RE = re.compile(r"^##\s+Tasks\s*\n(.*?)(?=^##\s|\Z)", re.M | re.S)
TASK_LINE_RE = re.compile(r"^-\s+\[(pending|in_progress|in_review|completed|blocked)\]", re.M)
ETA_RE = re.compile(r"\[ETA:\s*([\d.]+)h\]")
INVESTIGATION_RE = re.compile(r"\[Investigation:\s*([^\]]+?)\]")
PLAN_BRIEF_TASK_RE = re.compile(
    r"^-\s+\[(?P<status>pending|in_progress|in_review|completed|blocked)\]\s+(?P<body>.+?)\s*$",
    re.M,
)
PLAN_BRIEF_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<body>.+?)\s*$")
PLAN_BRIEF_TAG_RE = re.compile(r"\s*\[[A-Za-z][A-Za-z0-9 _/-]*:\s*[^\]]+\]")
PLAN_BRIEF_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
EVIDENCE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-_].*)?\.md$")
DECISION_LOG_HEADING_RE = re.compile(r"^(?P<indent>[ \t]{0,3})(?P<marks>#{2,6})\s+decision\s+log\s*#*\s*$", re.I)
MARKDOWN_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})\s+\S")
DECISION_ENTRY_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<body>.+?)\s*$")
DECISION_KIND_RE = re.compile(r"^\[(?P<kind>[A-Z][A-Z0-9_-]{1,31})\]\s*(?P<rest>.*)$")
DECISION_DATE_RE = re.compile(r"^\[?(?P<date>\d{4}-\d{2}-\d{2}(?:[^\]]{0,60})?)\]?\s*(?P<rest>.*)$")
DECISION_DIRECTION_KINDS = frozenset({
    "DIRECTION",
    "PIVOT",
    "REFRAME",
    "DELETION",
    "MERGE",
    "STUCK",
})
# Sub-plan backlink: child plans declare their parent on a line near the top
# matching either `> Parent: <relpath>` or `**Parent:** <relpath>`. The relpath
# is taken verbatim and normalized to a string later.
PARENT_REF_RE = re.compile(
    r"^(?:>\s*Parent:|\*\*Parent:\*\*)\s*([^\s][^\n]*?)\s*$",
    re.M,
)
TASK_STATUSES = ("pending", "in_progress", "in_review", "completed", "blocked")


def discover_plans() -> list[dict]:
    """Walk DEV_ROOT and return one entry per PLAN.md found.

    Post-processing wires up:
      * `children`: list of child plan-dicts that backlink this plan via
        `> Parent: <relpath>`. The list lives directly on the parent so the
        client can render indented sidebar rows without a second pass.
      * `aggregate_stats`: rolled-up `task_stats` across this plan plus every
        descendant in the parent→children tree. Cycle-safe via visited-set.
    """
    seen: set[Path] = set()
    plans: list[dict] = []
    for pattern in PLAN_GLOBS:
        # recursive=True so `**` in patterns expands to "any depth"; deduped
        # against the seen-set below so the shallow + recursive variants
        # of the same pattern don't double-count.
        for hit in glob(str(DEV_ROOT / pattern), recursive=True):
            path = Path(hit).resolve()
            if path in seen:
                continue
            if "node_modules" in path.parts:
                continue
            seen.add(path)
            plans.append(plan_meta(path))
    plans = dedupe_legacy_repo_plans(plans)
    plans = attach_children(plans)
    aggregate_memo: dict[str, dict] = {}
    for plan in plans:
        plan["aggregate_stats"] = aggregate_stats(plan, _memo=aggregate_memo)
    plans.sort(key=lambda p: (-p["mtime"], p["repo"], p["slug"]))
    return plans


def plan_list_payload(plans: list[dict]) -> list[dict]:
    """Return sidebar-safe plan metadata without recursively embedding children.

    `discover_plans()` keeps full child objects in memory because aggregate
    stats and tests use that shape. The HTTP list endpoint should not duplicate
    every child subtree in JSON; the browser can rehydrate child objects from
    these rels after one pass through the flat list.
    """
    payload: list[dict] = []
    for plan in plans:
        item = {k: v for k, v in plan.items() if k != "children"}
        item["child_rels"] = [child["rel"] for child in plan.get("children", [])]
        payload.append(item)
    return payload


def attach_children(plans: list[dict]) -> list[dict]:
    """Group plans by parent_rel and attach `children` lists in place.

    Lookup is two-tier: prefer an exact match against full DEV_ROOT-rel paths
    (e.g., `repo/vidux/foo/PLAN.md`), then fall back to a repo-scoped match
    where the backlink is written relative to the repo root (e.g.,
    `vidux/foo/PLAN.md` from a child living in the same repo). Authors write
    backlinks the natural way — relative to where they are — so the resolver
    has to bridge both shapes.

    Children are sorted by rel-path for deterministic UI order. Plans without
    a recognized parent get `children = []` so the frontend can branch on
    existence-only rather than presence checks.
    """
    by_rel: dict[str, dict] = {p["rel"]: p for p in plans}
    by_path: dict[Path, dict] = {Path(p["path"]).resolve(): p for p in plans}
    # Repo-scoped index: ('<repo>', '<repo-relative-rel>') → plan. The
    # repo-relative rel strips the leading `<repo>/` so a child's
    # `vidux/foo/PLAN.md` backlink finds `<repo>/vidux/foo/PLAN.md`.
    by_repo_rel: dict[tuple[str, str], dict] = {}
    for plan in plans:
        parts = plan["rel"].split("/")
        if len(parts) >= 2:
            by_repo_rel[(plan["repo"], "/".join(parts[1:]))] = plan
    for plan in plans:
        plan["children"] = []
    for plan in plans:
        parent_rel = plan.get("parent_rel")
        if not parent_rel:
            continue
        parent = by_rel.get(parent_rel)
        if parent is None:
            parent = resolve_relative_parent(plan, parent_rel, by_path)
        if parent is None:
            # Backlink wasn't a full DEV_ROOT-rel — try repo-scoped resolution.
            parent = by_repo_rel.get((plan["repo"], parent_rel))
        if parent is None:
            # Dangling backlink — child references a parent we didn't discover
            # in either repo. Leave it ungrouped at the sidebar root.
            continue
        if parent is plan:
            # Self-reference (a plan that says "Parent: <self>"). Ignore.
            continue
        parent["children"].append(plan)
    for plan in plans:
        plan["children"].sort(key=lambda c: c["rel"])
    return plans


def resolve_relative_parent(plan: dict, parent_ref: str, by_path: dict[Path, dict]) -> dict | None:
    """Resolve `Parent: ../../PLAN.md` style refs from the child plan's directory."""
    if not parent_ref.startswith(("./", "../")):
        return None
    try:
        candidate = (Path(plan["path"]).resolve().parent / parent_ref).resolve()
        candidate.relative_to(DEV_ROOT)
    except (OSError, ValueError):
        return None
    return by_path.get(candidate)


def aggregate_stats(
    plan: dict,
    _visited: set[str] | None = None,
    _memo: dict[str, dict] | None = None,
) -> dict:
    """Recursively roll up task_stats across a plan and all descendants.

    Returns the same shape as `task_stats()` (counts/total/eta_total/
    eta_tagged/eta_eligible) plus a `descendants` count. Cycle-safe: the
    visited set tracks rel-paths so a cyclic Parent: chain (broken plan
    authorship) never recurses forever.
    """
    if _visited is None:
        _visited = set()
    if _memo is None:
        _memo = {}
    rel = plan.get("rel", "")
    if rel in _memo:
        return _memo[rel]
    if rel in _visited:
        return {
            "counts": {s: 0 for s in TASK_STATUSES},
            "total": 0,
            "eta_total": 0.0,
            "eta_tagged": 0,
            "eta_eligible": 0,
            "descendants": 0,
        }
    _visited.add(rel)

    own = plan.get("task_stats") or {}
    counts = {s: int((own.get("counts") or {}).get(s, 0)) for s in TASK_STATUSES}
    total = int(own.get("total", 0))
    eta_total = float(own.get("eta_total", 0.0))
    eta_tagged = int(own.get("eta_tagged", 0))
    eta_eligible = int(own.get("eta_eligible", 0))
    descendants = 0

    for child in plan.get("children", []) or []:
        sub = aggregate_stats(child, _visited.copy(), _memo)
        for s in TASK_STATUSES:
            counts[s] += int((sub.get("counts") or {}).get(s, 0))
        total += int(sub.get("total", 0))
        eta_total += float(sub.get("eta_total", 0.0))
        eta_tagged += int(sub.get("eta_tagged", 0))
        eta_eligible += int(sub.get("eta_eligible", 0))
        descendants += 1 + int(sub.get("descendants", 0))

    result = {
        "counts": counts,
        "total": total,
        "eta_total": round(eta_total, 2),
        "eta_tagged": eta_tagged,
        "eta_eligible": eta_eligible,
        "descendants": descendants,
    }
    _memo[rel] = result
    return result


def dedupe_legacy_repo_plans(plans: list[dict]) -> list[dict]:
    """Drop legacy-checkout duplicates when a canonical repo has the same plan."""
    winners: dict[tuple[str, ...], dict] = {}
    for plan in plans:
        parts = Path(plan["rel"]).parts
        if not parts:
            continue
        canonical_repo = LEGACY_REPO_ALIASES.get(plan["repo"], plan["repo"])
        key = (canonical_repo, *parts[1:])
        current = winners.get(key)
        if current is None or plan_preference(plan) > plan_preference(current):
            winners[key] = plan
            continue
        if plan_preference(plan) == plan_preference(current) and plan["mtime"] > current["mtime"]:
            winners[key] = plan
    return list(winners.values())


def plan_preference(plan: dict) -> int:
    return 0 if plan["repo"] in LEGACY_REPO_ALIASES else 1


def plan_meta(path: Path) -> dict:
    rel = path.relative_to(DEV_ROOT)
    parts = rel.parts
    repo = parts[0]
    # Slug is the directory name containing PLAN.md, or "_root_" for repo-root plans.
    parent_dir = path.parent
    if parent_dir == DEV_ROOT / repo:
        slug = "_root_"
    else:
        slug = parent_dir.name
    mtime = path.stat().st_mtime
    age_days = (time.time() - mtime) / 86400
    if age_days <= HOT_DAYS:
        status = "hot"
    elif age_days <= STALE_DAYS:
        status = "stale"
    else:
        status = "cold"
    siblings = [f for f in SIBLING_FILES if (parent_dir / f).is_file()]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    purpose = extract_purpose_from_text(text)
    stats = task_stats(text)
    decision_log = parse_decision_log(text)
    investigations = discover_investigations(parent_dir, text)
    evidence = discover_evidence(parent_dir)
    parent_rel = extract_parent_rel(text)
    return {
        "repo": repo,
        "slug": slug,
        "path": str(path),
        "rel": str(rel),
        "size": path.stat().st_size,
        "mtime": mtime,
        "age_days": round(age_days, 1),
        "status": status,
        "siblings": siblings,
        "purpose": purpose,
        "task_stats": stats,
        "brief": plan_brief(text, purpose, stats, decision_log),
        "decision_log": decision_log,
        "investigations": investigations,
        "evidence": evidence,
        "parent_rel": parent_rel,
    }


def extract_parent_rel(text: str) -> str | None:
    """Pull the rel-path from a `> Parent:` or `**Parent:**` backlink.

    Returns a forward-slash rel-path (e.g., `vidux/design-overhaul/PLAN.md`)
    with surrounding backticks/quotes stripped. Anything after whitespace
    in the value (e.g., `... task D2`) is dropped — only the path is meaningful
    for parent→children grouping. Returns None if no backlink is present.
    """
    m = PARENT_REF_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Drop backticks/quotes/markdown emphasis around the path token.
    raw = raw.strip("`'\"")
    # Some plans extend the backlink with `... task D2` — keep only the path.
    token = raw.split()[0] if raw else ""
    token = token.strip("`'\",")
    if not token or token in (".", ".."):
        return None
    # Normalize to forward slashes; PLAN.md `rel` strings always use / on POSIX
    # because `Path.relative_to(...)` plus `str()` round-trips that way on macOS.
    return token.replace("\\", "/")


def task_stats(text: str) -> dict:
    """Parse the `## Tasks` section into status counts + ETA total.

    Returns counts for every known status, total tasks, ETA hours summed
    over pending+in_progress+in_review (ETAs on terminal states are ignored
    per /vidux), and how many of those eligible tasks actually have an ETA
    tag (eta_tagged) vs. how many should (eta_eligible).
    """
    counts = {s: 0 for s in TASK_STATUSES}
    eta_total = 0.0
    eta_tagged = 0
    eta_eligible = 0
    m = TASKS_SECTION_RE.search(text)
    if not m:
        return {
            "counts": counts,
            "total": 0,
            "eta_total": 0.0,
            "eta_tagged": 0,
            "eta_eligible": 0,
        }
    body = m.group(1)
    for line in body.splitlines():
        lm = TASK_LINE_RE.match(line)
        if not lm:
            continue
        status = lm.group(1)
        counts[status] += 1
        if status in ("pending", "in_progress", "in_review"):
            eta_eligible += 1
            em = ETA_RE.search(line)
            if em:
                eta_tagged += 1
                try:
                    eta_total += float(em.group(1))
                except ValueError:
                    pass
    return {
        "counts": counts,
        "total": sum(counts.values()),
        "eta_total": round(eta_total, 2),
        "eta_tagged": eta_tagged,
        "eta_eligible": eta_eligible,
    }


def section_body(text: str, heading: str) -> str:
    """Return a markdown section body by heading text."""
    lines = text.splitlines()
    start_index = None
    start_level = None
    heading_re = re.compile(
        rf"^[ \t]{{0,3}}(?P<marks>##{{1,6}})\s+{re.escape(heading)}\s*#*\s*$",
        re.I,
    )
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        start_index = i
        start_level = len(m.group("marks"))
        break
    if start_index is None or start_level is None:
        return ""
    body_lines: list[str] = []
    for line in lines[start_index + 1:]:
        hm = MARKDOWN_HEADING_RE.match(line)
        if hm and len(hm.group(1)) <= start_level:
            break
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def clean_plan_brief_text(value: str, limit: int = 180) -> str:
    """Compact markdown-ish plan text into a one-line UI summary."""
    text = PLAN_BRIEF_LINK_RE.sub(r"\1", value or "")
    text = PLAN_BRIEF_TAG_RE.sub("", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[*_#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    if len(text) <= limit:
        return text
    clipped = text[: max(0, limit - 3)].rsplit(" ", 1)[0].strip()
    return f"{clipped or text[: max(0, limit - 3)].strip()}..."


def extract_focus_tasks(text: str, limit: int = 3) -> list[dict]:
    body = section_body(text, "Tasks")
    if not body:
        return []
    tasks: list[dict] = []
    for m in PLAN_BRIEF_TASK_RE.finditer(body):
        label = clean_plan_brief_text(m.group("body"), 170)
        if not label:
            continue
        tasks.append({"status": m.group("status"), "label": label})
    order = {"in_progress": 0, "in_review": 1, "blocked": 2, "pending": 3, "completed": 4}
    tasks.sort(key=lambda item: order.get(item["status"], 9))
    return tasks[:limit]


def extract_latest_bullets(text: str, heading: str, limit: int = 1) -> list[str]:
    body = section_body(text, heading)
    if not body:
        return []
    bullets: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if PLAN_BRIEF_TASK_RE.match(line):
            continue
        m = PLAN_BRIEF_BULLET_RE.match(line)
        if m:
            if current:
                bullets.append(clean_plan_brief_text(" ".join(current), 220))
            current = [m.group("body")]
        elif current and line.strip():
            current.append(line.strip())
    if current:
        bullets.append(clean_plan_brief_text(" ".join(current), 220))
    return [b for b in bullets if b][-limit:]


def plan_state_label(stats: dict) -> str:
    counts = stats.get("counts") or {}
    total = int(stats.get("total") or 0)
    completed = int(counts.get("completed") or 0)
    if total and completed == total:
        return "shipped"
    if int(counts.get("blocked") or 0):
        return "blocked"
    if int(counts.get("in_review") or 0):
        return "in review"
    if int(counts.get("in_progress") or 0):
        return "in flight"
    if int(counts.get("pending") or 0):
        return "queued"
    return "no tasks"


def plan_brief(text: str, purpose: str, stats: dict, decision_log: dict) -> dict:
    counts = stats.get("counts") or {}
    total = int(stats.get("total") or 0)
    completed = int(counts.get("completed") or 0)
    latest_decision = ""
    recent_directions = decision_log.get("recent_directions") or []
    if recent_directions:
        latest = recent_directions[-1]
        latest_decision = clean_plan_brief_text(latest.get("body") or latest.get("raw") or "", 220)
    latest_progress = extract_latest_bullets(text, "Progress", 1)
    return {
        "summary": clean_plan_brief_text(purpose or "", 220),
        "state": plan_state_label(stats),
        "open_count": max(total - completed, 0),
        "focus_tasks": extract_focus_tasks(text, 3),
        "latest_progress": latest_progress[0] if latest_progress else "",
        "latest_decision": latest_decision,
    }


def decision_log_body(text: str) -> tuple[str, int | None]:
    """Return the Decision Log section body plus its 1-based heading line."""
    lines = text.splitlines()
    start_index = None
    start_level = None
    for i, line in enumerate(lines):
        m = DECISION_LOG_HEADING_RE.match(line)
        if not m:
            continue
        start_index = i
        start_level = len(m.group("marks"))
        break
    if start_index is None or start_level is None:
        return "", None

    body_lines: list[str] = []
    for line in lines[start_index + 1:]:
        hm = MARKDOWN_HEADING_RE.match(line)
        if hm and len(hm.group(1)) <= start_level:
            break
        body_lines.append(line)
    return "\n".join(body_lines).strip(), start_index + 1


def normalize_decision_entry(raw: str, index: int, line_number: int | None) -> dict:
    """Parse one Decision Log bullet into UI-friendly fields."""
    text = re.sub(r"\s+", " ", raw).strip()
    kind = "NOTE"
    m = DECISION_KIND_RE.match(text)
    if m:
        kind = m.group("kind").upper()
        text = m.group("rest").strip()

    date = ""
    dm = DECISION_DATE_RE.match(text)
    if dm:
        date = dm.group("date").strip()
        text = dm.group("rest").strip()

    body = text or raw.strip()
    return {
        "index": index,
        "line": line_number,
        "kind": kind,
        "date": date,
        "body": body,
        "raw": raw.strip(),
        "is_direction": kind in DECISION_DIRECTION_KINDS,
        "is_recent": False,
    }


def parse_decision_log(text: str) -> dict:
    """Extract Decision Log bullets as first-class read-only plan metadata."""
    body, heading_line = decision_log_body(text)
    entries: list[dict] = []
    if body:
        current: list[str] = []
        current_line: int | None = None
        base_line = (heading_line or 0) + 1
        for offset, line in enumerate(body.splitlines(), start=base_line):
            m = DECISION_ENTRY_RE.match(line)
            if m:
                if current:
                    entries.append(normalize_decision_entry(" ".join(current), len(entries), current_line))
                current = [m.group("body").strip()]
                current_line = offset
                continue
            if current and line.strip():
                current.append(line.strip())
        if current:
            entries.append(normalize_decision_entry(" ".join(current), len(entries), current_line))

    recent_indexes = {entry["index"] for entry in entries[-3:]}
    for entry in entries:
        entry["is_recent"] = entry["index"] in recent_indexes

    recent_directions = [entry for entry in entries if entry["is_direction"]][-3:]
    return {
        "present": heading_line is not None,
        "heading_line": heading_line,
        "count": len(entries),
        "entries": entries,
        "recent_directions": recent_directions,
    }


def discover_investigations(plan_dir: Path, plan_text: str) -> list[str]:
    """Auto-discover .md files under plan_dir/investigations/ + explicit refs.

    Canonical /vidux nesting: a parent task can carry [Investigation: <relpath>]
    pointing at a sub-plan. We surface BOTH the auto-discovered files AND any
    explicit refs from task lines (deduped by resolved path), to handle plans
    that drop investigations without linking them and plans that link without
    a directory.
    """
    found: set[str] = set()
    inv_dir = plan_dir / "investigations"
    if inv_dir.is_dir():
        for f in inv_dir.glob("*.md"):
            if f.is_file():
                found.add(str(f.resolve()))
    for ref in INVESTIGATION_RE.findall(plan_text):
        rel = ref.strip().strip("`'\"")
        try:
            candidate = (plan_dir / rel).resolve()
            candidate.relative_to(plan_dir.resolve())
        except (OSError, ValueError):
            continue
        if candidate.is_file() and candidate.suffix == ".md":
            found.add(str(candidate))
    return sorted(found)


def evidence_label(path: Path) -> str:
    stem = path.stem.strip()
    if not stem:
        return path.name
    dated = re.match(r"^(\d{4}-\d{2}-\d{2})[-_](.+)$", stem)
    if dated:
        slug = re.sub(r"[-_]+", " ", dated.group(2)).strip()
        return f"{dated.group(1)} - {slug}" if slug else dated.group(1)
    return re.sub(r"[-_]+", " ", stem)


def discover_evidence(plan_dir: Path) -> list[dict]:
    """Discover markdown evidence files in chronological order.

    Canonical evidence names are `YYYY-MM-DD-<slug>.md`, but real plans
    accumulate hand-written receipts. Non-markdown files and nested directories
    are ignored; oddly named markdown is still surfaced after dated evidence
    with a readable label so the browser fails open for receipts, not the page.
    """
    evidence_dir = plan_dir / "evidence"
    if not evidence_dir.is_dir():
        return []
    items: list[dict] = []
    for path in evidence_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        st = path.stat()
        date_match = EVIDENCE_DATE_RE.match(path.name)
        items.append({
            "path": str(path.resolve()),
            "name": path.name,
            "label": evidence_label(path),
            "date": date_match.group(1) if date_match else "",
            "mtime": st.st_mtime,
            "size": st.st_size,
            "is_dated": bool(date_match),
        })
    items.sort(key=lambda item: (
        0 if item["is_dated"] else 1,
        item["date"] or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(item["mtime"])),
        item["name"].lower(),
    ))
    return items


def extract_purpose_from_text(text: str) -> str:
    """Pull the first non-heading paragraph under '## Purpose' from plan text."""
    # Strip leading Parent: metadata blockquote / bold line so it doesn't
    # leak into the sidebar purpose preview.
    text = re.sub(
        r"^(#[^\n]*\n+)?(?:>[ \t]*Parent:|\*\*Parent:\*\*)[^\n]*\n+",
        lambda m: m.group(1) or "",
        text,
        count=1,
    )
    m = re.search(r"##\s+Purpose\s*\n+([^\n#].+?)(?=\n\s*\n|\n##|\Z)", text, re.S)
    if not m:
        # Fall back to first non-heading paragraph after the title.
        m = re.search(r"^#[^\n]*\n+([^\n#].+?)(?=\n\s*\n|\n##|\Z)", text, re.S | re.M)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:240]


def extract_purpose(path: Path) -> str:
    """Compatibility wrapper for callers that only have a path."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return extract_purpose_from_text(text)


def safe_resolve(raw: str) -> Path | None:
    """Allow PLAN.md + canonical siblings + .md files in investigations/ or evidence/.

    The whitelist is the read-only contract. node_modules paths are rejected
    even when the filename matches. The `investigations/` + `evidence/` rules
    are the canonical /vidux nesting per DOCTRINE.md + guides/investigation.md
    + guides/evidence-format.md — surfacing them is part of the viewer's job.
    """
    try:
        p = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        p.relative_to(DEV_ROOT)
    except ValueError:
        return None
    if "node_modules" in p.parts:
        return None
    if not p.is_file():
        return None
    if p.name in ALLOWED_PLAN_FILES:
        return p
    if p.suffix == ".md" and ("investigations" in p.parts or "evidence" in p.parts):
        return p
    return None


def safe_resolve_any(raw: str) -> Path | None:
    """safe_resolve() OR an .html artifact under ARTIFACTS_DIR. Read-only either way."""
    p = safe_resolve(raw)
    if p:
        return p
    try:
        candidate = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(ARTIFACTS_DIR.resolve())
    except ValueError:
        return None
    if candidate.suffix.lower() != ".html":
        return None
    if not candidate.is_file():
        return None
    return candidate


def discover_artifacts() -> list[dict]:
    """List ad-hoc HTML artifacts in ARTIFACTS_DIR, newest first."""
    if not ARTIFACTS_DIR.is_dir():
        return []
    items: list[dict] = []
    for path in ARTIFACTS_DIR.glob("*.html"):
        if not path.is_file():
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4096]
        except OSError:
            head = ""
        m = ARTIFACT_TITLE_RE.search(head)
        if m:
            raw_title = (m.group(1) or m.group(2) or "").strip()
            title = raw_title or path.stem
        else:
            title = path.stem
        st = path.stat()
        age_days = (time.time() - st.st_mtime) / 86400
        items.append({
            "slug": path.stem,
            "title": title[:200],
            "path": str(path),
            "size": st.st_size,
            "mtime": st.st_mtime,
            "age_days": round(age_days, 1),
        })
    items.sort(key=lambda a: -a["mtime"])
    return items


def write_artifact(slug: str, html: str) -> tuple[bool, str]:
    """Write an artifact. Returns (ok, message)."""
    if not ARTIFACT_SLUG_RE.match(slug):
        return False, "slug must match [a-z0-9][a-z0-9-]{0,63}"
    if len(html.encode("utf-8")) > ARTIFACT_MAX_BYTES:
        return False, f"html exceeds {ARTIFACT_MAX_BYTES} bytes"
    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        path = ARTIFACTS_DIR / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, str(path)


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


def is_json_content_type(value: str | None) -> bool:
    return (value or "").split(";", 1)[0].strip().lower() == JSON_CONTENT_TYPE


def origin_matches_host(raw: str, host: str) -> bool:
    if not raw or raw == "null" or not host:
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return parsed.netloc.lower() == host.lower()


def clean_note_label(raw: object, default: str) -> str:
    text = str(raw or default).strip()
    text = PLAN_NOTE_SOURCE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return (text or default)[:120]


def clean_comment_author(raw: object) -> str:
    text = str(raw or "").strip()
    text = COMMENT_AUTHOR_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return (text or "Anonymous")[:COMMENT_AUTHOR_MAX_CHARS]


def clean_comment_anchor_text(raw: object, limit: int) -> str:
    text = str(raw or "").strip()
    text = COMMENT_ANCHOR_CONTROL_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def clean_comment_anchor(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    anchor: dict[str, object] = {"version": 1}
    for key, limit in COMMENT_ANCHOR_FIELD_LIMITS.items():
        value = clean_comment_anchor_text(raw.get(key), limit)
        if value:
            anchor[key] = value
    if "index" in raw:
        try:
            index = int(raw.get("index"))
        except (TypeError, ValueError):
            index = None
        if index is not None and 0 <= index <= 100_000:
            anchor["index"] = index
    return anchor if len(anchor) > 1 else None


def comment_target_kind(path: Path) -> str:
    try:
        path.relative_to(ARTIFACTS_DIR.resolve())
    except ValueError:
        return "plan"
    return "artifact"


def append_comment(
    target_path: Path,
    author: object,
    body: str,
    remote_address: str,
    anchor: object = None,
) -> tuple[bool, str | dict]:
    text = body.strip()
    if not text:
        return False, "comment must be non-empty"
    if len(text.encode("utf-8")) > COMMENT_BODY_MAX_BYTES:
        return False, f"comment exceeds {COMMENT_BODY_MAX_BYTES} bytes"

    record = {
        "id": str(uuid.uuid4()),
        "target_path": str(target_path),
        "target_kind": comment_target_kind(target_path),
        "author": clean_comment_author(author),
        "body": text,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "remote_address": remote_address,
    }
    clean_anchor = clean_comment_anchor(anchor)
    if clean_anchor:
        record["anchor"] = clean_anchor

    try:
        COMMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with COMMENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, record


def read_comments(target_path: Path, limit: int = 100) -> list[dict]:
    if not COMMENTS_FILE.is_file():
        return []
    target = str(target_path)
    comments: list[dict] = []
    try:
        for line in COMMENTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("target_path") == target:
                comments.append(item)
    except OSError:
        return []
    return comments[-limit:]


def resolve_plan_note_target(raw: str) -> Path | None:
    p = safe_resolve(raw)
    if not p or p.name != "PLAN.md":
        return None
    return p


def write_plan_note(
    plan_path: Path,
    note: str,
    source: str = "vidux-browse-local",
    agent: str = "",
) -> tuple[bool, str]:
    """Append a local note to the plan directory's INBOX.md."""
    body = note.strip()
    if not body:
        return False, "note must be non-empty"
    if len(body.encode("utf-8")) > PLAN_NOTE_MAX_BYTES:
        return False, f"note exceeds {PLAN_NOTE_MAX_BYTES} bytes"

    source = clean_note_label(source, "vidux-browse-local")
    agent = clean_note_label(agent, "") if agent else ""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    title = re.sub(r"\s+", " ", body.splitlines()[0]).strip()[:96]
    inbox = plan_path.parent / "INBOX.md"
    quote = "\n".join(f"> {line}" if line else ">" for line in body.splitlines())
    lines = [
        f"### {stamp} - {title}",
        f"- Source: {source}",
    ]
    if agent:
        lines.append(f"- Agent: {agent}")
    entry = "\n".join(lines) + "\n\n" + quote + "\n\n"

    if inbox.exists():
        try:
            text = inbox.read_text(encoding="utf-8")
        except OSError as e:
            return False, f"read failed: {e}"
    else:
        text = f"# {plan_path.parent.name} Inbox\n\n## Open\n\n## Processed\n"

    marker = re.search(r"(^## Open\s*\n)", text, re.M)
    if marker:
        insert_at = marker.end()
        text = text[:insert_at] + "\n" + entry + text[insert_at:]
    else:
        text = text.rstrip() + "\n\n## Open\n\n" + entry

    try:
        inbox.write_text(text, encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, str(inbox)


class Handler(BaseHTTPRequestHandler):
    server_version = "viduxBrowser/0.1"

    def log_message(self, fmt, *args):  # noqa: N802 — stdlib override
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def do_GET(self):  # noqa: N802 — stdlib override
        url = urlparse(self.path)
        route = url.path
        qs = parse_qs(url.query)
        if route == "/" or route == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif route == "/receipts" or route == "/receipts/":
            self._serve_static("receipts.html", "text/html; charset=utf-8")
        elif route.startswith("/static/"):
            name = route[len("/static/"):]
            self._serve_static(name)
        elif route == "/api/health":
            self._json({"ok": True, "dev_root": str(DEV_ROOT), "port": PORT,
                        "artifacts_dir": str(ARTIFACTS_DIR)})
        elif route == "/api/plans":
            self._json({
                "plans": plan_list_payload(discover_plans_cached()),
                "dev_root": str(DEV_ROOT),
            })
        elif route == "/api/artifacts":
            self._json({"artifacts": discover_artifacts(),
                        "artifacts_dir": str(ARTIFACTS_DIR)})
        elif route == "/api/comments":
            raw = (qs.get("path") or [""])[0]
            p = safe_resolve_any(raw)
            if not p:
                self._send(403, "forbidden")
                return
            self._json({
                "ok": True,
                "path": str(p),
                "target_kind": comment_target_kind(p),
                "comments": read_comments(p),
            })
        elif route == "/api/file":
            raw = (qs.get("path") or [""])[0]
            p = safe_resolve_any(raw)  # plans + artifacts
            if not p:
                self._send(403, "forbidden")
                return
            ctype = ("text/html; charset=utf-8" if p.suffix.lower() == ".html"
                     else "text/markdown; charset=utf-8")
            self._send_with_type(p.read_bytes(), ctype)
        elif route == "/api/receipts/list":
            status, body = _receipts_handler.handle_list()
            self._send(status, "") if status >= 400 else self._json(body)
        elif route.startswith("/api/receipts/") and route.endswith("/image"):
            row_id = route[len("/api/receipts/"):-len("/image")]
            status, ctype, data = _receipts_handler.handle_image(row_id)
            if status == 200:
                self._send_with_type(data, ctype)
            else:
                self._send(status, data.get("error", "error") if isinstance(data, dict) else "error")
        else:
            self._send(404, "not found")

    def do_POST(self):  # noqa: N802 — stdlib override
        url = urlparse(self.path)
        if url.path == "/api/artifact":
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > ARTIFACT_MAX_BYTES + 1024:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            slug = str(payload.get("slug", "")).strip()
            html = payload.get("html", "")
            if not isinstance(html, str):
                self._send(400, "html must be a string")
                return
            ok, msg = write_artifact(slug, html)
            if not ok:
                self._send(400, msg)
                return
            self._json({"ok": True, "slug": slug, "path": msg})
        elif url.path == "/api/local-plan-note":
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > PLAN_NOTE_MAX_BYTES + 2048:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            plan_path = resolve_plan_note_target(str(payload.get("plan_path", "")))
            if not plan_path:
                self._send(403, "plan_path must be an allowed PLAN.md under dev_root")
                return
            note = payload.get("note", "")
            if not isinstance(note, str):
                self._send(400, "note must be a string")
                return
            ok, msg = write_plan_note(
                plan_path,
                note,
                source=str(payload.get("source", "vidux-browse-local")),
                agent=str(payload.get("agent", "")),
            )
            if not ok:
                self._send(400, msg)
                return
            self._json({"ok": True, "path": msg})
        elif url.path == "/api/upload-ref-audio":
            # Loopback-only personal use. Browser uploads a base64 audio sample
            # to be saved at /tmp/vidux-readaloud-ref-<sha8>.<ext> and the path
            # passed to mlx-audio.server's `ref_audio` field for voice cloning.
            # See projects/voxtral-reader-addon/PLAN.md M8.
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            # 15 MB cap — 30s of 24kHz 16-bit mono WAV is ~1.4 MB; large stereo
            # 48kHz samples can hit 5-8 MB; 15 MB has comfortable headroom.
            if length <= 0 or length > 15 * 1024 * 1024:
                self._send(400, "missing or oversized body (15 MB cap)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            b64 = payload.get("audio_base64", "")
            if not isinstance(b64, str) or not b64:
                self._send(400, "audio_base64 (string) is required")
                return
            ext = str(payload.get("ext", "wav")).lower().strip(".")
            if ext not in {"wav", "mp3", "m4a", "flac", "ogg"}:
                self._send(400, "ext must be one of wav|mp3|m4a|flac|ogg")
                return
            import base64 as _base64
            import hashlib as _hashlib
            import tempfile as _tempfile
            import time as _time
            try:
                audio_bytes = _base64.b64decode(b64, validate=True)
            except Exception as e:
                self._send(400, f"audio_base64 not valid base64: {e}")
                return
            if len(audio_bytes) < 1024:
                self._send(400, "audio sample too small (<1 KB)")
                return
            # Cheap sanity check: WAV files start with RIFF; MP3 with ID3 or 0xFFFB;
            # M4A with ftyp at offset 4. We don't reject on signature mismatch (some
            # tools omit headers), just refuse obviously not-audio (HTML/JSON/etc).
            head = audio_bytes[:8]
            if head[:1] in (b"<", b"{", b"["):
                self._send(400, "uploaded data does not look like audio")
                return
            sha = _hashlib.sha256(audio_bytes).hexdigest()[:12]
            tmp_dir = _tempfile.gettempdir()
            out_path = os.path.join(tmp_dir, f"vidux-readaloud-ref-{sha}.{ext}")
            try:
                with open(out_path, "wb") as f:
                    f.write(audio_bytes)
            except OSError as e:
                self._send(500, f"failed to write reference audio: {e}")
                return
            # Best-effort GC: prune our own tmp files older than 24 h. Bounded
            # work — only matches our prefix, so it can't sweep unrelated files.
            try:
                cutoff = _time.time() - 24 * 3600
                for entry in os.listdir(tmp_dir):
                    if entry.startswith("vidux-readaloud-ref-") and entry != f"vidux-readaloud-ref-{sha}.{ext}":
                        p = os.path.join(tmp_dir, entry)
                        try:
                            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                                os.remove(p)
                        except OSError:
                            pass
            except OSError:
                pass
            self._json({"ok": True, "path": out_path, "bytes": len(audio_bytes), "sha": sha})
        elif url.path == "/api/comments":
            if not self._require_browser_json(require_origin=True):
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > COMMENT_BODY_MAX_BYTES + 2048:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            target_path = safe_resolve_any(str(payload.get("target_path", "")))
            if not target_path:
                self._send(403, "target_path must be an allowed plan file or artifact")
                return
            body = payload.get("body", "")
            if not isinstance(body, str):
                self._send(400, "body must be a string")
                return
            ok, result = append_comment(
                target_path,
                payload.get("author", ""),
                body,
                self.client_address[0],
                anchor=payload.get("anchor"),
            )
            if not ok:
                self._send(400, str(result))
                return
            self._json({"ok": True, "comment": result})
        elif url.path == "/api/receipts/upload":
            if not self._require_json_write():
                return
            length = int(self.headers.get("Content-Length", "0"))
            # Cap matches handler.MAX_IMAGE_BYTES (15 MB) + base64 overhead (~33%) + JSON wrapper.
            if length <= 0 or length > 22 * 1024 * 1024:
                self._send(400, "missing or oversized body (22 MB cap for base64-wrapped JSON)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            status, body = _receipts_handler.handle_upload(payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/tag"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/tag")]
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16 * 1024:
                self._send(400, "missing or oversized body (16 KB cap for tag payload)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            status, body = _receipts_handler.handle_tag(row_id, payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/ocr"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/ocr")]
            status, body = _receipts_handler.handle_ocr(row_id)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/expected"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/expected")]
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64 * 1024:
                self._send(400, "missing or oversized body (64 KB cap for expected payload)")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            status, body = _receipts_handler.handle_set_expected(row_id, payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/delete"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/delete")]
            status, body = _receipts_handler.handle_delete(row_id)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        elif url.path.startswith("/api/receipts/") and url.path.endswith("/analyze"):
            if not self._require_json_write():
                return
            row_id = url.path[len("/api/receipts/"):-len("/analyze")]
            length = int(self.headers.get("Content-Length", "0"))
            payload = {}
            if 0 < length <= 4 * 1024:
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    payload = {}
            # Multi-provider extract + compare (claude + qwen + azure). Blocks ~30s; the
            # ThreadingHTTPServer handles it on its own thread.
            status, body = _receipts_handler.handle_analyze(row_id, payload)
            self._json(body) if status < 400 else self._send(status, body.get("error", "error"))
        else:
            self._send(404, "not found")

    def _require_json_write(self) -> bool:
        if not is_loopback_host(self.client_address[0]):
            self._send(403, "write endpoints require loopback client")
            return False
        return self._require_browser_json()

    def _require_browser_json(self, require_origin: bool = False) -> bool:
        if not is_json_content_type(self.headers.get("Content-Type")):
            self._send(415, "Content-Type must be application/json")
            return False
        ok, reason = self._same_origin_ok(require_origin=require_origin)
        if not ok:
            self._send(403, reason)
            return False
        return True

    def _same_origin_ok(self, require_origin: bool = False) -> tuple[bool, str]:
        host = (self.headers.get("Host") or "").strip()
        origin = (self.headers.get("Origin") or "").strip()
        referer = (self.headers.get("Referer") or "").strip()
        if origin:
            if origin_matches_host(origin, host):
                return True, ""
            return False, "Origin must match vidux-browse host"
        if referer:
            if origin_matches_host(referer, host):
                return True, ""
            return False, "Referer must match vidux-browse host"
        if require_origin:
            return False, "Origin or Referer required"
        return True, ""

    def _serve_static(self, name: str, ctype: str | None = None):
        if not name:
            self._send(404, "not found")
            return
        try:
            candidate = (STATIC_DIR / name).resolve()
            candidate.relative_to(STATIC_DIR.resolve())
        except (OSError, ValueError):
            self._send(404, "not found")
            return
        if not candidate.is_file():
            self._send(404, f"static asset missing: {name}")
            return
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or guess_content_type(candidate.name))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_with_type(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send(self, code: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def guess_content_type(name: str) -> str:
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    if name.endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"


def main(argv=None):
    """Entry point. CLI flags override env defaults so test harnesses and
    Playwright `webServer` can launch the server hermetically against a
    fixture root + ephemeral port without mutating the user's shell env."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="vidux browser",
        description="Plan + artifact viewer for /vidux fleets. LAN-safe (loopback default).",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Dev-root directory to scan for PLAN.md files. Defaults to env "
             "VIDUX_DEV_ROOT or ~/Development.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind. Defaults to env VIDUX_BROWSER_PORT or 7191.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind. Defaults to env VIDUX_BROWSER_HOST or 127.0.0.1. "
             "Use 0.0.0.0 to expose on LAN.",
    )
    parser.add_argument(
        "--comments-path",
        type=str,
        default=None,
        help="Path to comments JSONL file. Defaults to env "
             "VIDUX_BROWSER_COMMENTS_FILE or ~/.vidux-browser/comments.jsonl.",
    )
    args = parser.parse_args(argv)

    # CLI overrides module-level globals. Re-resolve so the server uses the
    # passed values rather than the env defaults captured at import time.
    global HOST, PORT, DEV_ROOT, COMMENTS_FILE
    if args.host is not None:
        HOST = args.host
    if args.port is not None:
        PORT = args.port
    if args.root is not None:
        DEV_ROOT = Path(args.root).expanduser().resolve()
    if args.comments_path is not None:
        COMMENTS_FILE = Path(args.comments_path).expanduser()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    sys.stderr.write(f"vidux browser → {url}  (dev_root={DEV_ROOT})\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nstopped\n")
        server.server_close()


if __name__ == "__main__":
    main()
