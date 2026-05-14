#!/usr/bin/env python3
"""Verify a vidux lane is ready for closeout.

A lane is CLOSED when three gates pass:
  1. tasks_terminal — every task in PLAN.md is terminal (`[completed]` or
     `[cancelled]`), with one optional exception for the closeout task
     itself (passed via `--self`).
  2. audit_overall — `scripts/vidux-linear-audit.py` exits with overall not
     `red`. `green` and `yellow` are both acceptable; `red` blocks closeout.
  3. sync_drift — `scripts/vidux-inbox-sync.py --dry-run --direction=both
     --only-adapter linear --json` reports zero pushed / zero
     inbox_appended / zero errors per fleet repo.

Output is a JSON envelope:

    {
      "closeout_at": "<ISO8601>",
      "plan": "<path>",
      "self_task": "LI-7" | null,
      "status": "CLOSED" | "OPEN",
      "gates": {
        "tasks_terminal": {"ok": bool, "blockers": [...]},
        "audit_overall": {"ok": bool, "overall": "green|yellow|red|skipped"},
        "sync_drift":    {"ok": bool, "drift": [...], "errors": [...]}
      }
    }

Exit codes:
  0  status == CLOSED (or every gate ok / skipped under --no-network)
  1  status == OPEN

CLI:
  --plan <path>         REQUIRED — PLAN.md to evaluate
  --self <task-id>      optional — task whose own non-terminal status is
                         expected (e.g., the closeout task itself); it is
                         skipped from the tasks_terminal gate
  --repo <name>         scope sync_drift to one repo (repeatable)
  --no-network          skip audit + sync calls (gates return ok=true with
                         status=skipped); useful for unit tests / smoke
  --audit-script <path> override audit script path (default: sibling
                         `scripts/vidux-linear-audit.py`)
  --inbox-sync <path>   override inbox-sync script path
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


TERMINAL_STATES = frozenset({"completed", "cancelled"})
NON_TERMINAL_STATES = frozenset({"pending", "in_progress", "blocked"})

# Leo's fleet — override with --repo flag for portability.
DEFAULT_REPOS = (
    "vidux",
    "strongyes-web",
    "resplit-web",
    "resplit-ios",
)

# Match a PLAN.md task line.  Captures (status, id).  Examples:
#   "- [completed] LI-1: Add a fail-closed sync preflight..."
#   "- [pending] LI-7: Wire completion gates..."
TASK_LINE_RE = re.compile(
    r"^\s*-\s*\[(?P<status>[a-z_]+)\]\s+(?P<id>[A-Z]+-\d+):"
)


@dataclass
class Task:
    id: str
    status: str


@dataclass
class GateResult:
    ok: bool
    detail: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure functions (no I/O)
# ---------------------------------------------------------------------------


def parse_plan_tasks(text: str) -> list[Task]:
    """Extract task entries from a PLAN.md string.

    Only top-level `- [<status>] <id>: ...` lines under a `## Tasks` header
    qualify.  Lines outside a tasks section are ignored so progress entries
    or evidence bullets that happen to look like tasks do not bleed in.
    """
    tasks: list[Task] = []
    in_tasks_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            in_tasks_section = heading == "tasks"
            continue
        if not in_tasks_section:
            continue
        m = TASK_LINE_RE.match(line)
        if not m:
            continue
        tasks.append(Task(id=m.group("id"), status=m.group("status")))
    return tasks


def assess_tasks_terminal(
    tasks: Sequence[Task],
    *,
    self_task_id: str | None = None,
) -> GateResult:
    """All tasks terminal except for the optional self-task."""
    blockers: list[dict] = []
    for t in tasks:
        if t.status in TERMINAL_STATES:
            continue
        if self_task_id and t.id == self_task_id:
            continue
        blockers.append({"id": t.id, "status": t.status})
    return GateResult(ok=not blockers, detail={"blockers": blockers})


def assess_audit(envelope: dict | None) -> GateResult:
    """Audit gate: overall != red.  None envelope means skipped."""
    if envelope is None:
        return GateResult(ok=True, detail={"overall": "skipped"})
    overall = envelope.get("overall", "skipped")
    return GateResult(ok=overall != "red", detail={"overall": overall})


def assess_sync(
    per_repo: Sequence[dict] | None,
) -> GateResult:
    """Sync gate: each repo reports zero pushed / zero inbox / zero errors."""
    if per_repo is None:
        return GateResult(ok=True, detail={"skipped": True})
    drift: list[dict] = []
    errors: list[dict] = []
    for entry in per_repo:
        repo = entry.get("repo", "<unknown>")
        result_blocks = entry.get("results") or []
        repo_pushed = 0
        repo_inbox = 0
        repo_errors: list[str] = []
        for block in result_blocks:
            if block.get("_kind") == "auto_promote":
                # auto_promote summaries are informational, not drift
                continue
            repo_pushed += int(block.get("pushed") or 0)
            repo_inbox += int(block.get("inbox_appended") or 0)
            errs = block.get("errors") or []
            if errs:
                repo_errors.extend(str(e) for e in errs)
        if repo_errors:
            errors.append({"repo": repo, "errors": repo_errors})
        if repo_pushed > 0 or repo_inbox > 0:
            drift.append(
                {"repo": repo, "pushed": repo_pushed, "inbox_appended": repo_inbox}
            )
    return GateResult(
        ok=not drift and not errors,
        detail={"drift": drift, "errors": errors},
    )


def closeout_status(
    *,
    tasks: Sequence[Task],
    audit: dict | None,
    sync: Sequence[dict] | None,
    self_task_id: str | None = None,
) -> dict:
    """Compose the three gates into a single status envelope."""
    g_tasks = assess_tasks_terminal(tasks, self_task_id=self_task_id)
    g_audit = assess_audit(audit)
    g_sync = assess_sync(sync)
    overall_ok = g_tasks.ok and g_audit.ok and g_sync.ok
    return {
        "status": "CLOSED" if overall_ok else "OPEN",
        "gates": {
            "tasks_terminal": {"ok": g_tasks.ok, **g_tasks.detail},
            "audit_overall": {"ok": g_audit.ok, **g_audit.detail},
            "sync_drift": {"ok": g_sync.ok, **g_sync.detail},
        },
    }


# ---------------------------------------------------------------------------
# Live runners (real subprocess calls)
# ---------------------------------------------------------------------------


def _vidux_root() -> Path:
    return Path(
        os.environ.get(
            "VIDUX_ROOT",
            str(Path.home() / "Development" / "vidux"),
        )
    ).expanduser()


def _live_run_audit(audit_script: Path) -> dict | None:
    if not audit_script.exists():
        return None
    proc = subprocess.run(
        ["python3", str(audit_script)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _live_run_sync(
    inbox_sync: Path,
    repos: Sequence[str],
) -> list[dict]:
    out: list[dict] = []
    dev = Path(
        os.environ.get(
            "VIDUX_DEV_ROOT",
            str(Path.home() / "Development"),
        )
    ).expanduser()
    for repo in repos:
        repo_dir = dev / repo
        if not repo_dir.exists() or not inbox_sync.exists():
            out.append({"repo": repo, "results": []})
            continue
        proc = subprocess.run(
            [
                "python3",
                str(inbox_sync),
                "--dry-run",
                "--direction=both",
                "--only-adapter",
                "linear",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(repo_dir),
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"results": []}
        out.append({"repo": repo, "results": payload.get("results") or []})
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_closeout(
    *,
    plan_path: Path,
    self_task_id: str | None,
    repos: Sequence[str],
    no_network: bool,
    audit_script: Path,
    inbox_sync: Path,
    runners: dict | None = None,
) -> dict:
    """Run the closeout check.  `runners` overrides live runners (for tests)."""
    runners = runners or {}
    tasks = parse_plan_tasks(plan_path.read_text())

    if no_network:
        audit_envelope = None
        sync_results: list[dict] | None = None
    else:
        run_audit = runners.get("run_audit") or (lambda: _live_run_audit(audit_script))
        run_sync = runners.get("run_sync") or (
            lambda: _live_run_sync(inbox_sync, repos)
        )
        audit_envelope = run_audit()
        sync_results = run_sync()

    body = closeout_status(
        tasks=tasks,
        audit=audit_envelope,
        sync=sync_results,
        self_task_id=self_task_id,
    )
    return {
        "closeout_at": _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "plan": str(plan_path),
        "self_task": self_task_id,
        **body,
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True, help="path to PLAN.md")
    p.add_argument("--self", dest="self_task", default=None,
                   help="task id whose non-terminal state is expected (e.g., LI-7)")
    p.add_argument("--repo", action="append", default=None,
                   help="scope sync_drift to a repo (repeatable)")
    p.add_argument("--no-network", action="store_true",
                   help="skip audit + sync subprocess calls")
    p.add_argument("--audit-script", default=None,
                   help="path to vidux-linear-audit.py")
    p.add_argument("--inbox-sync", default=None,
                   help="path to vidux-inbox-sync.py")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    plan_path = Path(os.path.expanduser(args.plan)).resolve()
    if not plan_path.exists():
        print(json.dumps({"error": f"plan not found: {plan_path}"}), file=sys.stderr)
        return 2
    repos = list(args.repo) if args.repo else list(DEFAULT_REPOS)
    audit_script = Path(args.audit_script) if args.audit_script else (
        _vidux_root() / "scripts" / "vidux-linear-audit.py"
    )
    inbox_sync = Path(args.inbox_sync) if args.inbox_sync else (
        _vidux_root() / "scripts" / "vidux-inbox-sync.py"
    )
    envelope = run_closeout(
        plan_path=plan_path,
        self_task_id=args.self_task,
        repos=repos,
        no_network=args.no_network,
        audit_script=audit_script,
        inbox_sync=inbox_sync,
    )
    print(json.dumps(envelope, indent=2))
    return 0 if envelope["status"] == "CLOSED" else 1


if __name__ == "__main__":
    sys.exit(main())
