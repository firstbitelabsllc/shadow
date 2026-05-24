#!/usr/bin/env python3
"""Audit Linear coverage health across the vidux fleet.

Runs N independent checks and emits one JSON envelope. Each check is a pure
function that takes injected fetchers (for unit-testability) and returns a
`CheckResult` of shape `{name, status, details, evidence}`.

Exit codes:
  0  all checks pass (green) OR yellow checks present (non-blocking)
  1  one or more checks are red

CLI flags:
  --check <name>     run only the named check (repeatable)
  --repo <name>      scope repo-level checks to one repo
  --no-network       skip Linear/gh calls (returns SKIPPED for those checks)

Output schema:
    {
      "audit_at": "<ISO8601>",
      "overall": "green" | "yellow" | "red",
      "summary": {"green": N, "yellow": N, "red": N, "skipped": N},
      "checks": [{"name": ..., "status": ..., "details": ..., "evidence": ...}, ...]
    }

This file is the standalone audit. It is not invoked by the
linear-health-watch cron lane (which would violate Hard NEVER #6 — no
Linear MCP cold-path calls from this lane). It IS what Leo or CI runs to
get a snapshot of Linear coverage health on demand.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Sequence


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GREEN = "green"
YELLOW = "yellow"
RED = "red"
SKIPPED = "skipped"

# Worst-of semantics: red beats yellow beats green; skipped is neutral.
STATUS_RANK = {GREEN: 0, YELLOW: 1, RED: 2, SKIPPED: -1}

# Leo's fleet — override with --repo flag for portability.
DEFAULT_REPOS = (
    "vidux",
    "strongyes-web",
    "resplit-web",
    "resplit-ios",
    "fcp-workflow",
)

# GitHub owner — per-repo mapping wins; falls back to VIDUX_GH_OWNER env,
# then DEFAULT_GH_OWNER for unknown repos. Multi-org fleets need this
# because Leo's repos live under both `firstbitelabsllc` (vidux,
# resplit-ios) and `leojkwan` (strongyes-web, resplit-web, fcp-workflow).
REPO_OWNERS: dict[str, str] = {
    "vidux": "firstbitelabsllc",
    "resplit-ios": "firstbitelabsllc",
    "strongyes-web": "leojkwan",
    "resplit-web": "leojkwan",
    "fcp-workflow": "leojkwan",
}

DEFAULT_GH_OWNER = "firstbitelabsllc"

# LI-4 managed labels — the Linear adapter creates/maintains these.
MANAGED_LABELS = (
    "pr-open",
    "pr-merged",
    "review-pending",
    "review-passed",
    "blocked",
)

AUTOMATION_LOGINS = ("codex", "vidux-bot")
AUTOMATION_PREFIXES = ("claude", "cursor")

LINEAR_REF_RE = re.compile(r"Linear:\s*[A-Z]+-\d+")
GITHUB_PR_MARKDOWN_RE = re.compile(r"\[[^\]]*?#\d+\]\([^)]*?github\.com[^)]*?\)")

CHECK_NAMES = (
    "repo_config",
    "no_project_issues",
    "label_taxonomy",
    "pr_linear_links",
    "draft_age",
    "description_format",
    "sync_deltas",
)


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    status: str
    details: str = ""
    evidence: list[dict] = field(default_factory=list)


def _result(name: str, status: str, details: str = "", evidence=None) -> CheckResult:
    return CheckResult(
        name=name,
        status=status,
        details=details,
        evidence=list(evidence or []),
    )


# ---------------------------------------------------------------------------
# Check 1: repo_config
# ---------------------------------------------------------------------------


def assess_repo_config(
    *,
    load_config: Callable[[str], dict | None],
    repos: Sequence[str] = DEFAULT_REPOS,
) -> CheckResult:
    """Each repo must declare Linear sources with project_id+project_name OR an explicit team_wide_intake flag."""
    missing_pair: list[dict] = []
    team_wide_undeclared: list[dict] = []
    no_config: list[dict] = []
    no_linear_source: list[dict] = []

    for repo in repos:
        cfg = load_config(repo)
        if cfg is None:
            no_config.append({"repo": repo, "reason": "config not found"})
            continue
        sources = (cfg.get("linear") or {}).get("sources") or []
        if not sources:
            no_linear_source.append({"repo": repo})
            continue
        for src in sources:
            project_id = src.get("project_id")
            project_name = src.get("project_name")
            team_wide = src.get("team_wide_intake")
            if team_wide is True:
                continue
            if project_id and project_name:
                continue
            # Distinguish: someone tried to set the pair but botched it (RED)
            # vs no project fields present at all (could be team-wide intent
            # without an explicit flag — YELLOW).
            has_any_project_field = "project_id" in src or "project_name" in src
            if has_any_project_field:
                missing_pair.append(
                    {
                        "repo": repo,
                        "source": src.get("name") or src.get("team_id") or "<unnamed>",
                        "project_id": project_id,
                        "project_name": project_name,
                    }
                )
            else:
                team_wide_undeclared.append(
                    {
                        "repo": repo,
                        "source": src.get("name") or src.get("team_id") or "<unnamed>",
                    }
                )

    evidence = []
    if missing_pair:
        evidence.append({"missing_pair": missing_pair})
    if team_wide_undeclared:
        evidence.append({"team_wide_undeclared": team_wide_undeclared})
    if no_config:
        evidence.append({"no_config": no_config})
    if no_linear_source:
        evidence.append({"no_linear_source": no_linear_source})

    if missing_pair:
        return _result(
            "repo_config",
            RED,
            f"{len(missing_pair)} Linear source(s) missing project_id/project_name",
            evidence,
        )
    if team_wide_undeclared:
        return _result(
            "repo_config",
            YELLOW,
            f"{len(team_wide_undeclared)} Linear source(s) team-wide without explicit flag",
            evidence,
        )
    return _result(
        "repo_config",
        GREEN,
        f"all {len(repos)} repos declare Linear sources cleanly",
        evidence,
    )


# ---------------------------------------------------------------------------
# Check 2: no_project_issues
# ---------------------------------------------------------------------------


def assess_no_project_issues(
    *,
    fetch_no_project_issues: Callable[[], list[dict]],
) -> CheckResult:
    """Linear should have zero non-terminal issues without a project assignment."""
    issues = fetch_no_project_issues()
    if not issues:
        return _result(
            "no_project_issues", GREEN, "0 non-terminal issues without a project"
        )
    return _result(
        "no_project_issues",
        RED,
        f"{len(issues)} non-terminal issue(s) without a project",
        issues,
    )


# ---------------------------------------------------------------------------
# Check 3: label_taxonomy
# ---------------------------------------------------------------------------


def assess_label_taxonomy(
    *,
    fetch_labels: Callable[[], list[str]],
    fetch_open_issues: Callable[[], list[dict]],
    managed: Sequence[str] = MANAGED_LABELS,
) -> CheckResult:
    """All LI-4 managed labels must exist; managed-label coverage on open issues should be >=50%."""
    labels = set(fetch_labels())
    missing = [m for m in managed if m not in labels]
    if missing:
        return _result(
            "label_taxonomy",
            RED,
            f"{len(missing)} managed label(s) missing from workspace",
            [{"missing": missing}],
        )

    open_issues = fetch_open_issues()
    if not open_issues:
        return _result(
            "label_taxonomy",
            GREEN,
            "all managed labels present; no open issues to gauge coverage",
        )

    managed_set = set(managed)
    covered = 0
    for issue in open_issues:
        issue_labels = set(issue.get("labels") or [])
        if issue_labels & managed_set:
            covered += 1
    coverage_pct = round(covered * 100 / len(open_issues))
    if coverage_pct < 50:
        return _result(
            "label_taxonomy",
            YELLOW,
            f"managed-label coverage on open issues {coverage_pct}% (< 50%)",
            [{"covered": covered, "total": len(open_issues)}],
        )
    return _result(
        "label_taxonomy",
        GREEN,
        f"managed-label coverage {coverage_pct}% across {len(open_issues)} open issues",
    )


# ---------------------------------------------------------------------------
# Check 4: pr_linear_links
# ---------------------------------------------------------------------------


def assess_pr_linear_links(
    *,
    fetch_open_prs: Callable[[str], list[dict]],
    fetch_linear_attachment: Callable[[str, int], bool],
    repos: Sequence[str] = DEFAULT_REPOS,
) -> CheckResult:
    """Each open PR should carry `Linear: EVE-N` in body OR a Linear attachment."""
    unlinked: list[dict] = []
    total_prs = 0
    for repo in repos:
        prs = fetch_open_prs(repo)
        for pr in prs:
            total_prs += 1
            body = pr.get("body") or ""
            if LINEAR_REF_RE.search(body):
                continue
            if fetch_linear_attachment(repo, pr.get("number") or 0):
                continue
            unlinked.append(
                {
                    "repo": repo,
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "headRefName": pr.get("headRefName"),
                }
            )

    if not unlinked:
        return _result(
            "pr_linear_links",
            GREEN,
            f"all {total_prs} open PR(s) carry a Linear link",
        )
    return _result(
        "pr_linear_links",
        YELLOW,
        f"{len(unlinked)} of {total_prs} open PR(s) missing Linear link",
        unlinked,
    )


# ---------------------------------------------------------------------------
# Check 5: draft_age
# ---------------------------------------------------------------------------


def _is_automation_login(login: str) -> bool:
    if not login:
        return False
    lo = login.lower()
    if lo in AUTOMATION_LOGINS:
        return True
    return any(lo.startswith(prefix) for prefix in AUTOMATION_PREFIXES)


def assess_draft_age(
    *,
    fetch_open_drafts: Callable[[str], list[dict]],
    repos: Sequence[str] = DEFAULT_REPOS,
    now: _dt.datetime | None = None,
) -> CheckResult:
    """Automation-authored draft PRs older than 24h are yellow; older than 72h are red."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    yellow_drafts: list[dict] = []
    red_drafts: list[dict] = []
    inspected = 0
    for repo in repos:
        for pr in fetch_open_drafts(repo):
            login = (pr.get("author") or {}).get("login") or ""
            if not _is_automation_login(login):
                continue
            inspected += 1
            created_at = pr.get("createdAt")
            if not created_at:
                continue
            try:
                ts = _dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            hours_old = round((now - ts).total_seconds() / 3600, 1)
            entry = {
                "repo": repo,
                "number": pr.get("number"),
                "author": login,
                "hours_old": hours_old,
            }
            if hours_old >= 72:
                red_drafts.append(entry)
            elif hours_old >= 24:
                yellow_drafts.append(entry)

    if red_drafts:
        return _result(
            "draft_age",
            RED,
            f"{len(red_drafts)} automation draft(s) older than 72h",
            red_drafts + yellow_drafts,
        )
    if yellow_drafts:
        return _result(
            "draft_age",
            YELLOW,
            f"{len(yellow_drafts)} automation draft(s) older than 24h",
            yellow_drafts,
        )
    return _result(
        "draft_age",
        GREEN,
        f"all {inspected} automation draft(s) under 24h",
    )


# ---------------------------------------------------------------------------
# Check 6: description_format
# ---------------------------------------------------------------------------


def assess_description_format(
    *,
    fetch_issues_with_pr_markdown_no_attachment: Callable[[], list[dict]],
) -> CheckResult:
    """Linear issues with PR-markdown-in-body but no attachment are yellow; >10 is red."""
    issues = fetch_issues_with_pr_markdown_no_attachment()
    if not issues:
        return _result(
            "description_format",
            GREEN,
            "no issues with PR markdown but missing attachment",
        )
    if len(issues) > 10:
        return _result(
            "description_format",
            RED,
            f"{len(issues)} issue(s) with PR markdown but no attachment (> 10)",
            issues,
        )
    return _result(
        "description_format",
        YELLOW,
        f"{len(issues)} issue(s) with PR markdown but no attachment",
        issues,
    )


# ---------------------------------------------------------------------------
# Check 7: sync_deltas
# ---------------------------------------------------------------------------


def assess_sync_deltas(
    *,
    run_dry_sync: Callable[[str], dict],
    repos: Sequence[str] = DEFAULT_REPOS,
) -> CheckResult:
    """Per-repo Linear inbox-sync dry-run must show 0 errors and 0 drift."""
    errors_repos: list[dict] = []
    drift_repos: list[dict] = []
    clean_repos: list[str] = []

    for repo in repos:
        result = run_dry_sync(repo)
        results_list = result.get("results") or []
        repo_errors: list[dict] = []
        pushed = 0
        inbox_appended = 0
        for entry in results_list:
            errs = entry.get("errors") or []
            if errs:
                repo_errors.extend(
                    [
                        {"plan": entry.get("plan"), "error": err}
                        for err in errs
                    ]
                )
            pushed += int(entry.get("pushed") or 0)
            inbox_appended += int(entry.get("inbox_appended") or 0)

        if repo_errors:
            errors_repos.append({"repo": repo, "errors": repo_errors})
            continue
        if pushed > 0 or inbox_appended > 0:
            drift_repos.append(
                {"repo": repo, "pushed": pushed, "inbox_appended": inbox_appended}
            )
            continue
        clean_repos.append(repo)

    if errors_repos:
        return _result(
            "sync_deltas",
            RED,
            f"{len(errors_repos)} repo(s) with sync errors",
            errors_repos + drift_repos,
        )
    if drift_repos:
        return _result(
            "sync_deltas",
            YELLOW,
            f"{len(drift_repos)} repo(s) show drift in dry-run",
            drift_repos,
        )
    return _result(
        "sync_deltas",
        GREEN,
        f"all {len(clean_repos)} repo(s) sync-clean (push=0 inbox_appended=0 errors=0)",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


CHECK_DISPATCH = {
    "repo_config": assess_repo_config,
    "no_project_issues": assess_no_project_issues,
    "label_taxonomy": assess_label_taxonomy,
    "pr_linear_links": assess_pr_linear_links,
    "draft_age": assess_draft_age,
    "description_format": assess_description_format,
    "sync_deltas": assess_sync_deltas,
}


def overall_status(results: Sequence[CheckResult]) -> str:
    """Worst-of semantic across non-skipped results."""
    rank = -1
    for r in results:
        if r.status == SKIPPED:
            continue
        rank = max(rank, STATUS_RANK[r.status])
    if rank == STATUS_RANK[RED]:
        return RED
    if rank == STATUS_RANK[YELLOW]:
        return YELLOW
    if rank == STATUS_RANK[GREEN]:
        return GREEN
    return SKIPPED


def build_envelope(results: Sequence[CheckResult]) -> dict:
    summary = {GREEN: 0, YELLOW: 0, RED: 0, SKIPPED: 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return {
        "audit_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall": overall_status(results),
        "summary": summary,
        "checks": [asdict(r) for r in results],
    }


# ---------------------------------------------------------------------------
# Live fetchers (real-network implementations used when --no-network is off)
# ---------------------------------------------------------------------------


def _dev_root() -> Path:
    return Path(
        os.environ.get(
            "VIDUX_DEV_ROOT",
            str(Path.home() / "Development"),
        )
    ).expanduser()


def _gh_owner(repo: str) -> str:
    """Resolve GitHub owner for ``repo``.

    Precedence: ``VIDUX_GH_OWNER`` env var (global override, useful in CI)
    → ``REPO_OWNERS`` mapping (per-repo) → ``DEFAULT_GH_OWNER`` fallback
    (unknown repos).
    """

    env = os.environ.get("VIDUX_GH_OWNER")
    if env:
        return env
    return REPO_OWNERS.get(repo, DEFAULT_GH_OWNER)


def _live_load_config(repo: str) -> dict | None:
    path = _dev_root() / repo / "vidux.config.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _live_fetch_open_prs(repo: str) -> list[dict]:
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        f"{_gh_owner(repo)}/{repo}",
        "--state",
        "open",
        "--json",
        "number,body,title,headRefName",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []


def _live_fetch_open_drafts(repo: str) -> list[dict]:
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        f"{_gh_owner(repo)}/{repo}",
        "--state",
        "open",
        "--draft",
        "--json",
        "number,createdAt,author",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []


def _live_run_dry_sync(repo: str) -> dict:
    repo_dir = _dev_root() / repo
    inbox_sync = _dev_root() / "vidux" / "scripts" / "vidux-inbox-sync.py"
    if not inbox_sync.exists() or not repo_dir.exists():
        return {"results": []}
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
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"results": []}


def _network_unavailable_result(name: str) -> CheckResult:
    return _result(
        name,
        SKIPPED,
        "skipped: --no-network set or no live fetcher wired",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_audit(
    *,
    selected: Sequence[str] | None = None,
    repos: Sequence[str] | None = None,
    no_network: bool = False,
    fetchers: dict | None = None,
) -> dict:
    """Run the audit. `fetchers` overrides individual fetchers (for tests)."""
    selected = list(selected) if selected else list(CHECK_NAMES)
    invalid = [s for s in selected if s not in CHECK_DISPATCH]
    if invalid:
        raise ValueError(f"unknown check(s): {', '.join(invalid)}")
    repos = list(repos) if repos else list(DEFAULT_REPOS)
    f = dict(fetchers or {})

    results: list[CheckResult] = []
    for name in selected:
        if name == "repo_config":
            loader = f.get("load_config", _live_load_config)
            results.append(assess_repo_config(load_config=loader, repos=repos))
            continue
        if name == "no_project_issues":
            fetch = f.get("fetch_no_project_issues")
            if fetch is None and no_network:
                results.append(_network_unavailable_result(name))
                continue
            if fetch is None:
                results.append(_network_unavailable_result(name))
                continue
            results.append(assess_no_project_issues(fetch_no_project_issues=fetch))
            continue
        if name == "label_taxonomy":
            fl = f.get("fetch_labels")
            fi = f.get("fetch_open_issues")
            if fl is None or fi is None or no_network:
                results.append(_network_unavailable_result(name))
                continue
            results.append(
                assess_label_taxonomy(fetch_labels=fl, fetch_open_issues=fi)
            )
            continue
        if name == "pr_linear_links":
            gh = f.get("fetch_open_prs", _live_fetch_open_prs)
            attach = f.get("fetch_linear_attachment", lambda _r, _n: False)
            if no_network and "fetch_open_prs" not in f:
                results.append(_network_unavailable_result(name))
                continue
            results.append(
                assess_pr_linear_links(
                    fetch_open_prs=gh,
                    fetch_linear_attachment=attach,
                    repos=repos,
                )
            )
            continue
        if name == "draft_age":
            gh = f.get("fetch_open_drafts", _live_fetch_open_drafts)
            now = f.get("now")
            if no_network and "fetch_open_drafts" not in f:
                results.append(_network_unavailable_result(name))
                continue
            results.append(
                assess_draft_age(
                    fetch_open_drafts=gh, repos=repos, now=now
                )
            )
            continue
        if name == "description_format":
            fetch = f.get("fetch_issues_with_pr_markdown_no_attachment")
            if fetch is None or no_network:
                results.append(_network_unavailable_result(name))
                continue
            results.append(
                assess_description_format(
                    fetch_issues_with_pr_markdown_no_attachment=fetch
                )
            )
            continue
        if name == "sync_deltas":
            run = f.get("run_dry_sync", _live_run_dry_sync)
            if no_network and "run_dry_sync" not in f:
                results.append(_network_unavailable_result(name))
                continue
            results.append(assess_sync_deltas(run_dry_sync=run, repos=repos))
            continue

    return build_envelope(results)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check",
        action="append",
        default=None,
        help="run only the named check (repeatable)",
    )
    p.add_argument(
        "--repo",
        action="append",
        default=None,
        help="scope repo-level checks to one repo (repeatable)",
    )
    p.add_argument(
        "--owner",
        default=None,
        help=(
            "GitHub owner override for PR lookups (sets $VIDUX_GH_OWNER for "
            "the run). Without override, per-repo REPO_OWNERS mapping wins; "
            "unknown repos fall back to DEFAULT_GH_OWNER ('firstbitelabsllc')."
        ),
    )
    p.add_argument(
        "--no-network",
        action="store_true",
        help="skip Linear/gh calls; useful for unit tests and offline smoke",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.owner:
        os.environ["VIDUX_GH_OWNER"] = args.owner
    envelope = run_audit(
        selected=args.check,
        repos=args.repo,
        no_network=args.no_network,
    )
    print(json.dumps(envelope, indent=2))
    if envelope["overall"] == RED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
