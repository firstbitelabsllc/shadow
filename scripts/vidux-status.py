#!/usr/bin/env python3
"""vidux-status — read-only scan of all PLAN.md files on the machine.

Renders a two-bucket board: "Tied to this chat" (focus repos) and "Other
tracked plans" (everything else). Each row: 10-cell progress bar, remaining
AI-hours from [ETA: Xh] tags on pending+in_progress, last-Progress timestamp.

Usage:
    vidux-status.py                         # compact board, cwd's repo is focus
    vidux-status.py --all                   # include empty / shipped / stale
    vidux-status.py --json                  # machine-readable
    vidux-status.py --focus repo1 repo2     # explicit focus repos
    vidux-status.py --root /path/to/scan    # override search root (default ~/Development)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_ROOT = Path.home() / "Development"
SKIP_PARTS = {"node_modules", ".git", "_archive", ".next", "dist", "build", "worktrees"}
SKIP_SUBSTRINGS = ("-worktrees/", "/.agents/skills/vidux/", "/ai/skills/vidux/")

STATUS_TAGS = ("pending", "in_progress", "completed", "blocked")
STATUS_RE = re.compile(r"^-\s+\[(pending|in_progress|completed|blocked)\]", re.MULTILINE)
ETA_RE = re.compile(r"\[ETA:\s*(\d+(?:\.\d+)?)h\]")
PROGRESS_LINE_RE = re.compile(r"^-\s*\[?(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?Z?)?)")


@dataclass
class PlanStatus:
    path: str
    short: str
    pending: int
    in_progress: int
    completed: int
    blocked: int
    eta_hours: float
    progress_ts: Optional[str]
    mtime_ts: str

    @property
    def denom(self) -> int:
        return self.pending + self.in_progress + self.completed

    @property
    def percent(self) -> int:
        return round(100 * self.completed / self.denom) if self.denom else 0

    @property
    def is_empty(self) -> bool:
        return (self.pending + self.in_progress + self.completed + self.blocked) == 0

    @property
    def is_shipped(self) -> bool:
        return self.pending == 0 and self.in_progress == 0 and self.completed > 0

    @property
    def latest(self) -> str:
        return self.progress_ts or self.mtime_ts


def find_plans(root: Path) -> list[Path]:
    out = []
    for p in root.rglob("PLAN.md"):
        s = str(p)
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        if any(sub in s for sub in SKIP_SUBSTRINGS):
            continue
        out.append(p)
    return out


def parse_plan(p: Path, dev_root: Path) -> PlanStatus:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    counts = {tag: 0 for tag in STATUS_TAGS}
    for m in STATUS_RE.finditer(text):
        counts[m.group(1)] += 1

    eta_sum = 0.0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- [pending]") or s.startswith("- [in_progress]"):
            for m in ETA_RE.finditer(s):
                try:
                    eta_sum += float(m.group(1))
                except ValueError:
                    pass

    progress_ts: Optional[str] = None
    in_progress_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Progress"):
            in_progress_section = True
            continue
        if in_progress_section and stripped.startswith("## "):
            break
        if in_progress_section:
            m = PROGRESS_LINE_RE.match(line.lstrip())
            if m:
                ts = m.group(1)
                if progress_ts is None or ts > progress_ts:
                    progress_ts = ts

    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)

    try:
        rel = p.relative_to(dev_root)
        short = str(rel).removesuffix("/PLAN.md")
    except ValueError:
        short = str(p).removesuffix("/PLAN.md")
    short = short.replace("/vidux/", "/")

    return PlanStatus(
        path=str(p),
        short=short,
        pending=counts["pending"],
        in_progress=counts["in_progress"],
        completed=counts["completed"],
        blocked=counts["blocked"],
        eta_hours=eta_sum,
        progress_ts=progress_ts,
        mtime_ts=mtime.strftime("%Y-%m-%d"),
    )


def current_repo() -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).name
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def is_tied(plan: PlanStatus, focus: set[str]) -> bool:
    return any(part in focus for part in plan.short.split("/"))


def bar(percent: int, cells: int = 10) -> str:
    filled = round(percent / 100 * cells)
    return "▓" * filled + "░" * (cells - filled)


def eta_col(plan: PlanStatus) -> str:
    if plan.is_shipped and plan.pending == 0 and plan.in_progress == 0 and plan.denom:
        return "shipped"
    if plan.eta_hours == 0:
        return "∅ AI-hrs"
    return f"{plan.eta_hours:.1f} AI-hrs left"


def staleness(mtime: str) -> str:
    try:
        m = datetime.strptime(mtime, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc).date() - m.date()).days
    except ValueError:
        return mtime
    if days <= 0:
        return "today"
    if days == 1:
        return "1d"
    if days <= 7:
        return f"{days}d"
    return f"{days}d stale"


def render_row(plan: PlanStatus, name_width: int = 34) -> str:
    name = plan.short if len(plan.short) <= name_width else plan.short[: name_width - 1] + "…"
    name = name.ljust(name_width)
    pct = plan.percent
    extra = ""
    if pct == 0 and plan.pending > 0:
        parts = [f"{plan.pending}p"]
        if plan.in_progress:
            parts.append(f"{plan.in_progress}i")
        if plan.blocked:
            parts.append(f"{plan.blocked}b")
        extra = "  [" + "/".join(parts) + "]"
    return f"  {name} {bar(pct)} {pct:>3}%  ·  {eta_col(plan):<15}  ·  {staleness(plan.mtime_ts)}{extra}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan PLAN.md files and render a status board.")
    ap.add_argument("--all", action="store_true", help="Include empty / shipped / stale plans")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    ap.add_argument("--focus", nargs="*", default=None, help="Repo names to put in 'tied' bucket")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Search root (default ~/Development)")
    args = ap.parse_args()

    if not args.root.is_dir():
        print(f"error: search root does not exist: {args.root}", flush=True)
        return 1

    plans = [parse_plan(p, args.root) for p in find_plans(args.root)]

    if not args.all:
        plans = [p for p in plans if not p.is_empty and not p.is_shipped]

    focus: set[str] = set(args.focus) if args.focus is not None else set()
    cwd_repo = current_repo()
    if cwd_repo and not args.focus:
        focus.add(cwd_repo)

    tied = sorted([p for p in plans if is_tied(p, focus)], key=lambda p: (-p.percent, p.mtime_ts), reverse=False)
    other = sorted([p for p in plans if not is_tied(p, focus)], key=lambda p: (-p.percent, p.mtime_ts), reverse=False)

    if args.json:
        print(json.dumps({
            "focus_repos": sorted(focus),
            "tied": [asdict(p) for p in tied],
            "other": [asdict(p) for p in other],
        }, indent=2))
        return 0

    focus_label = ", ".join(sorted(focus)) if focus else "(none — pass --focus to set)"
    print(f"🎯 Tied to this chat  ({focus_label})")
    print("━" * 70)
    if not tied:
        print("  (no active plans in focus)")
    else:
        for p in tied:
            print(render_row(p))
    print()
    print(f"📋 Other tracked plans  ({len(other)} active)")
    print("━" * 70)
    for p in other[:20]:
        print(render_row(p))
    if len(other) > 20:
        print(f"  … {len(other) - 20} more (use --all to see full list)")

    total_eta = sum(p.eta_hours for p in plans)
    n_with_eta = sum(1 for p in plans if p.eta_hours > 0)
    if total_eta > 8:
        print()
        print(f"⚠  heavy queue: {total_eta:.1f} AI-hrs in flight across {n_with_eta} plan(s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
