#!/usr/bin/env python3
"""Read-only audit for recurring PLAN.md closure and enforcement drift.

This script scans one or more roots for PLAN.md files and reports the plan-bank
patterns that make Vidux work hard to close safely:

  * missing structure sections such as Progress, Evidence, Constraints,
    Decision Log, Drift Log, and Closeout / Terminal Verdict
  * archived plans that still contain non-terminal rows
  * blocked rows without an explicit blocked_since marker
  * unchecked verification/gate checkboxes
  * temporary proof paths such as /tmp/... in durable plan text

The default mode is observe-only and exits 0.  Use --fail-on when the audit is
wired into a smoke lane or CI gate.  Use --output-jsonl to preserve each watch
iteration as a durable smoke artifact without mutating audited repos.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "test-results",
        ".next",
        ".turbo",
    }
)
FIXTURE_PARTS = frozenset({"fixtures", "fixture", "examples", "example"})
AGENT_MIRROR_DIRS = frozenset({".agents", ".claude", ".codex"})
REQUIRED_SECTIONS = (
    "purpose",
    "evidence",
    "constraints",
    "tasks",
    "decision log",
    "progress",
)
TERMINAL_CLOSE_SECTIONS = frozenset({"close", "closeout", "terminal verdict"})
NON_TERMINAL_STATUSES = frozenset(
    {"pending", "in_progress", "blocked", "unchecked"}
)
VALID_STATUSES = frozenset(
    {
        "archived",
        "blocked",
        "cancelled",
        "completed",
        "done",
        "done_with_concerns",
        "in_progress",
        "pending",
        "unchecked",
        "x",
    }
)
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FAIL_THRESHOLDS = {
    "none": -1,
    "critical": 0,
    "high": 1,
    "medium": 2,
    "any": 3,
}

HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
TASK_STATUS_RE = re.compile(r"^\s*[-*]\s*\[(?P<status>[^\]]*)\]")
TMP_PATH_RE = re.compile(r"(?<![\w.-])/tmp/[^\s)]+")
GATE_HEADING_RE = re.compile(
    r"\b(gate|verification|definition of done|acceptance|closeout|launch)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    line: int | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "line": self.line,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PlanReport:
    path: str
    archived: bool
    sections: list[str]
    status_counts: dict[str, int]
    issues: list[Issue]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "archived": self.archived,
            "sections": self.sections,
            "status_counts": self.status_counts,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _is_fixture_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & FIXTURE_PARTS)


def _normalize_status(raw: str) -> str | None:
    stripped = raw.strip().lower()
    if not stripped:
        return "unchecked"
    if stripped not in VALID_STATUSES:
        return None
    if stripped == "x":
        return "completed"
    return stripped


def _normalize_heading(raw: str) -> str:
    return raw.strip().strip("#").strip().lower()


def _relative_path(path: Path, roots: Sequence[Path]) -> str:
    resolved = path.resolve()
    for root in roots:
        try:
            rel = str(resolved.relative_to(root.resolve()))
            if len(roots) > 1:
                return f"{root.name}/{rel}"
            return rel
        except ValueError:
            continue
    return str(path)


def discover_plan_files(
    roots: Sequence[Path],
    *,
    include_fixtures: bool = False,
    include_agent_mirrors: bool = False,
) -> list[Path]:
    """Find PLAN.md files under roots while skipping dependency/cache trees."""
    plans: list[Path] = []
    for root in roots:
        root = root.expanduser()
        if root.is_file():
            if root.name == "PLAN.md":
                if include_fixtures or not _is_fixture_path(root):
                    plans.append(root)
            continue
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            skipped_dirs = set(SKIP_DIRS)
            if not include_agent_mirrors:
                skipped_dirs.update(AGENT_MIRROR_DIRS)
            dirnames[:] = sorted(d for d in dirnames if d not in skipped_dirs)
            current = Path(dirpath)
            if not include_fixtures and _is_fixture_path(current):
                dirnames[:] = []
                continue
            if "PLAN.md" in filenames:
                plans.append(current / "PLAN.md")
    return sorted(set(plans))


def _archived(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    return "_archive" in lowered or "archive" in lowered


def _issue(
    issues: list[Issue],
    *,
    severity: str,
    code: str,
    path: str,
    detail: str,
    line: int | None = None,
) -> None:
    issues.append(
        Issue(
            severity=severity,
            code=code,
            path=path,
            line=line,
            detail=detail,
        )
    )


def audit_plan(path: Path, *, display_path: str | None = None) -> PlanReport:
    text = path.read_text(encoding="utf-8")
    display = display_path or str(path)
    sections: list[str] = []
    section_set: set[str] = set()
    status_counts: dict[str, int] = {}
    issues: list[Issue] = []
    current_heading = ""

    for line_no, line in enumerate(text.splitlines(), start=1):
        heading = HEADING_RE.match(line)
        if heading:
            current_heading = _normalize_heading(heading.group("title"))
            sections.append(current_heading)
            section_set.add(current_heading)

        status_match = TASK_STATUS_RE.match(line)
        if status_match:
            status = _normalize_status(status_match.group("status"))
            if status is None:
                continue
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == "blocked" and "blocked_since" not in line:
                _issue(
                    issues,
                    severity="high",
                    code="blocked_without_since",
                    path=display,
                    line=line_no,
                    detail="blocked row has no blocked_since marker",
                )
            if _archived(path) and status in NON_TERMINAL_STATUSES:
                _issue(
                    issues,
                    severity="critical",
                    code="archived_non_terminal_row",
                    path=display,
                    line=line_no,
                    detail=f"archived plan contains [{status}] row",
                )
            if status == "unchecked" and GATE_HEADING_RE.search(current_heading):
                _issue(
                    issues,
                    severity="high",
                    code="unchecked_gate_checkbox",
                    path=display,
                    line=line_no,
                    detail=f"unchecked checkbox under {current_heading!r}",
                )

        for match in TMP_PATH_RE.finditer(line):
            _issue(
                issues,
                severity="medium",
                code="temporary_proof_path",
                path=display,
                line=line_no,
                detail=f"durable plan references temporary proof path {match.group(0)}",
            )

    for section in REQUIRED_SECTIONS:
        if section not in section_set:
            _issue(
                issues,
                severity="high" if section in {"progress", "evidence"} else "medium",
                code=f"missing_{section.replace(' ', '_')}_section",
                path=display,
                line=None,
                detail=f"missing required ## {section.title()} section",
            )
    if "drift log" not in section_set:
        _issue(
            issues,
            severity="medium",
            code="missing_drift_log_section",
            path=display,
            line=None,
            detail="missing ## Drift Log section for planned-vs-actual drift",
        )
    if not (section_set & TERMINAL_CLOSE_SECTIONS):
        _issue(
            issues,
            severity="medium",
            code="missing_terminal_closeout_section",
            path=display,
            line=None,
            detail="missing ## Closeout, ## Close, or ## Terminal Verdict section",
        )

    return PlanReport(
        path=display,
        archived=_archived(path),
        sections=sections,
        status_counts=status_counts,
        issues=issues,
    )


def audit_roots(
    roots: Sequence[Path],
    *,
    include_fixtures: bool = False,
    include_agent_mirrors: bool = False,
) -> dict:
    """Audit all PLAN.md files under roots and return a JSON-safe snapshot."""
    resolved_roots = [root.expanduser().resolve() for root in roots]
    reports: list[PlanReport] = []
    for plan_path in discover_plan_files(
        resolved_roots,
        include_fixtures=include_fixtures,
        include_agent_mirrors=include_agent_mirrors,
    ):
        display = _relative_path(plan_path, resolved_roots)
        reports.append(audit_plan(plan_path, display_path=display))

    issues = [issue for report in reports for issue in report.issues]
    severity_counts = {severity: 0 for severity in SEVERITY_ORDER}
    issue_code_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for report in reports:
        for status, count in report.status_counts.items():
            status_counts[status] = status_counts.get(status, 0) + count
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        issue_code_counts[issue.code] = issue_code_counts.get(issue.code, 0) + 1

    return {
        "audit_at": _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "roots": [str(root) for root in resolved_roots],
        "plans_total": len(reports),
        "archived_plans": sum(1 for report in reports if report.archived),
        "status_counts": dict(sorted(status_counts.items())),
        "severity_counts": severity_counts,
        "issue_code_counts": dict(sorted(issue_code_counts.items())),
        "issues_total": len(issues),
        "reports": [report.to_dict() for report in reports],
        "issues": [
            issue.to_dict()
            for issue in sorted(
                issues,
                key=lambda item: (
                    SEVERITY_ORDER.get(item.severity, 99),
                    item.path,
                    item.line or 0,
                    item.code,
                ),
            )
        ],
    }


def exit_code_for(snapshot: dict, fail_on: str) -> int:
    threshold = FAIL_THRESHOLDS[fail_on]
    if threshold < 0:
        return 0
    counts = snapshot.get("severity_counts", {})
    for severity, rank in SEVERITY_ORDER.items():
        if rank <= threshold and int(counts.get(severity, 0)) > 0:
            return 1
    return 0


def _top_items(counts: dict[str, int], *, limit: int) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _count_delta(first: Mapping[str, int], last: Mapping[str, int]) -> dict[str, int]:
    keys = sorted(set(first) | set(last))
    return {key: int(last.get(key, 0)) - int(first.get(key, 0)) for key in keys}


def _summary_bucket_for_path(path: str, roots: Sequence[str]) -> str:
    root_names = [Path(root).name for root in roots]
    if len(root_names) == 1:
        return root_names[0]
    head = path.split("/", 1)[0]
    if head in root_names:
        return head
    return "<unknown>"


def _root_breakdown(snapshot: Mapping) -> dict[str, dict]:
    roots = snapshot.get("roots", [])
    breakdown: dict[str, dict] = {}
    for root in roots:
        breakdown[Path(root).name] = {
            "plans": 0,
            "archived_plans": 0,
            "status_counts": {},
            "severity_counts": {severity: 0 for severity in SEVERITY_ORDER},
            "issue_code_counts": {},
        }

    for report in snapshot.get("reports", []):
        bucket = _summary_bucket_for_path(report.get("path", ""), roots)
        entry = breakdown.setdefault(
            bucket,
            {
                "plans": 0,
                "archived_plans": 0,
                "status_counts": {},
                "severity_counts": {severity: 0 for severity in SEVERITY_ORDER},
                "issue_code_counts": {},
            },
        )
        entry["plans"] += 1
        if report.get("archived"):
            entry["archived_plans"] += 1
        for status, count in (report.get("status_counts") or {}).items():
            entry["status_counts"][status] = entry["status_counts"].get(status, 0) + int(
                count
            )
        for issue in report.get("issues", []):
            severity = issue.get("severity", "low")
            code = issue.get("code", "unknown")
            entry["severity_counts"][severity] = (
                entry["severity_counts"].get(severity, 0) + 1
            )
            entry["issue_code_counts"][code] = (
                entry["issue_code_counts"].get(code, 0) + 1
            )

    return breakdown


def summarize_jsonl(path: Path) -> dict:
    envelopes: list[dict] = []
    for line in path.expanduser().read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        envelopes.append(json.loads(line))
    if not envelopes:
        raise ValueError(f"{path} contains no JSONL iteration rows")

    snapshots = [envelope["snapshot"] for envelope in envelopes]
    first = snapshots[0]
    last = snapshots[-1]
    durations = [
        float(snapshot.get("duration_seconds", 0.0))
        for snapshot in snapshots
        if "duration_seconds" in snapshot
    ]
    last_issue_counts = last.get("issue_code_counts", {})
    sample_issues_by_code: dict[str, dict] = {}
    for code, _count in _top_items(last_issue_counts, limit=12):
        for issue in last.get("issues", []):
            if issue.get("code") == code:
                sample_issues_by_code[code] = issue
                break

    return {
        "path": str(path),
        "iterations": len(envelopes),
        "first_audit_at": first.get("audit_at"),
        "last_audit_at": last.get("audit_at"),
        "roots": last.get("roots", []),
        "plans_total": {
            "first": first.get("plans_total", 0),
            "last": last.get("plans_total", 0),
            "delta": int(last.get("plans_total", 0)) - int(first.get("plans_total", 0)),
        },
        "archived_plans": {
            "first": first.get("archived_plans", 0),
            "last": last.get("archived_plans", 0),
            "delta": int(last.get("archived_plans", 0))
            - int(first.get("archived_plans", 0)),
        },
        "duration_seconds": {
            "min": min(durations) if durations else None,
            "max": max(durations) if durations else None,
        },
        "severity_delta": _count_delta(
            first.get("severity_counts", {}),
            last.get("severity_counts", {}),
        ),
        "status_delta": _count_delta(
            first.get("status_counts", {}),
            last.get("status_counts", {}),
        ),
        "issue_code_delta": _count_delta(
            first.get("issue_code_counts", {}),
            last.get("issue_code_counts", {}),
        ),
        "last_severity_counts": last.get("severity_counts", {}),
        "last_status_counts": last.get("status_counts", {}),
        "last_issue_code_counts": last_issue_counts,
        "sample_issues_by_code": sample_issues_by_code,
        "root_breakdown": _root_breakdown(last),
    }


def render_summary(summary: dict) -> str:
    lines: list[str] = []
    lines.append("Vidux plan-bank audit smoke summary")
    lines.append(f"path: {summary['path']}")
    lines.append(f"iterations: {summary['iterations']}")
    lines.append(
        f"window: {summary['first_audit_at']} -> {summary['last_audit_at']}"
    )
    lines.append(f"roots: {', '.join(summary['roots'])}")
    lines.append(
        "plans: "
        f"first={summary['plans_total']['first']} "
        f"last={summary['plans_total']['last']} "
        f"delta={summary['plans_total']['delta']}"
    )
    durations = summary["duration_seconds"]
    lines.append(
        "duration_seconds: "
        f"min={durations['min']} max={durations['max']}"
    )
    lines.append("last severity counts:")
    for severity, count in _top_items(summary["last_severity_counts"], limit=8):
        delta = summary["severity_delta"].get(severity, 0)
        lines.append(f"- {severity}: {count} (delta {delta:+d})")
    lines.append("top last issue codes:")
    for code, count in _top_items(summary["last_issue_code_counts"], limit=12):
        delta = summary["issue_code_delta"].get(code, 0)
        lines.append(f"- {code}: {count} (delta {delta:+d})")
    if summary.get("root_breakdown"):
        lines.append("root breakdown:")
        for root, entry in sorted(summary["root_breakdown"].items()):
            severities = entry["severity_counts"]
            lines.append(
                f"- {root}: plans={entry['plans']} archived={entry['archived_plans']} "
                f"critical={severities.get('critical', 0)} "
                f"high={severities.get('high', 0)} "
                f"medium={severities.get('medium', 0)}"
            )
    if summary.get("sample_issues_by_code"):
        lines.append("sample issues by code:")
        for code, issue in summary["sample_issues_by_code"].items():
            location = issue["path"]
            if issue.get("line"):
                location = f"{location}:{issue['line']}"
            lines.append(
                f"- {code}: [{issue['severity']}] {location} - {issue['detail']}"
            )
    return "\n".join(lines)


def render_human(snapshot: dict, *, issue_limit: int = 30) -> str:
    lines: list[str] = []
    lines.append("Vidux plan-bank audit")
    lines.append(f"audit_at: {snapshot['audit_at']}")
    if "duration_seconds" in snapshot:
        lines.append(f"duration_seconds: {snapshot['duration_seconds']}")
    lines.append(f"roots: {', '.join(snapshot['roots'])}")
    lines.append(
        "plans: "
        f"total={snapshot['plans_total']} "
        f"archived={snapshot['archived_plans']}"
    )
    severities = snapshot["severity_counts"]
    lines.append(
        "issues: "
        f"critical={severities.get('critical', 0)} "
        f"high={severities.get('high', 0)} "
        f"medium={severities.get('medium', 0)} "
        f"low={severities.get('low', 0)}"
    )
    if snapshot["status_counts"]:
        status_bits = [
            f"{status}={count}"
            for status, count in _top_items(snapshot["status_counts"], limit=12)
        ]
        lines.append(f"statuses: {', '.join(status_bits)}")
    if snapshot["issue_code_counts"]:
        lines.append("top issue codes:")
        for code, count in _top_items(snapshot["issue_code_counts"], limit=12):
            lines.append(f"- {code}: {count}")
    if snapshot["issues"]:
        lines.append("sample issues:")
        for issue in snapshot["issues"][:issue_limit]:
            location = issue["path"]
            if issue["line"]:
                location = f"{location}:{issue['line']}"
            lines.append(
                f"- [{issue['severity']}] {issue['code']} {location} "
                f"- {issue['detail']}"
            )
    return "\n".join(lines)


def _run_once(args: argparse.Namespace) -> dict:
    roots = [Path(root) for root in args.roots]
    started = time.monotonic()
    snapshot = audit_roots(
        roots,
        include_fixtures=args.include_fixtures,
        include_agent_mirrors=args.include_agent_mirrors,
    )
    snapshot["duration_seconds"] = round(time.monotonic() - started, 3)
    return snapshot


def _iter_snapshots(args: argparse.Namespace) -> Iterable[dict]:
    for index in range(args.watch_iterations):
        if index > 0:
            time.sleep(args.watch_interval_seconds)
        yield _run_once(args)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        default=["."],
        help="repo roots or PLAN.md files to audit (default: cwd)",
    )
    parser.add_argument(
        "--include-fixtures",
        action="store_true",
        help="include fixture/example PLAN.md files in the audit",
    )
    parser.add_argument(
        "--include-agent-mirrors",
        action="store_true",
        help="include .claude/.agents/.codex plan mirrors and worktrees",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument(
        "--fail-on",
        choices=sorted(FAIL_THRESHOLDS),
        default="none",
        help="exit nonzero when issues at or above this severity exist",
    )
    parser.add_argument(
        "--issue-limit",
        type=int,
        default=30,
        help="maximum sample issues in human output",
    )
    parser.add_argument(
        "--watch-iterations",
        type=int,
        default=1,
        help="repeat the read-only audit N times for long smoke runs",
    )
    parser.add_argument(
        "--watch-interval-seconds",
        type=float,
        default=0,
        help="sleep between watch iterations",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        help="write each iteration envelope as one JSON line to this file",
    )
    parser.add_argument(
        "--summarize-jsonl",
        type=Path,
        help="summarize a JSONL smoke artifact and exit",
    )
    return parser.parse_args(argv)


def _prepare_output_jsonl(path: Path) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _append_output_jsonl(path: Path, envelope: dict) -> None:
    with path.expanduser().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, sort_keys=True))
        handle.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.summarize_jsonl is not None:
        summary = summarize_jsonl(args.summarize_jsonl)
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(render_summary(summary))
        return 0

    if args.watch_iterations < 1:
        raise SystemExit("--watch-iterations must be >= 1")
    if args.watch_interval_seconds < 0:
        raise SystemExit("--watch-interval-seconds must be >= 0")
    if args.output_jsonl is not None:
        _prepare_output_jsonl(args.output_jsonl)

    final_snapshot: dict | None = None
    exit_code = 0
    for index, snapshot in enumerate(_iter_snapshots(args)):
        final_snapshot = snapshot
        exit_code = max(exit_code, exit_code_for(snapshot, args.fail_on))
        envelope = {"iteration": index + 1, "snapshot": snapshot}
        if args.output_jsonl is not None:
            _append_output_jsonl(args.output_jsonl, envelope)
        if args.json:
            print(
                json.dumps(
                    envelope,
                    indent=2 if args.watch_iterations == 1 else None,
                )
            )
        else:
            if index > 0:
                print()
            if args.watch_iterations > 1:
                print(f"Iteration {index + 1}/{args.watch_iterations}")
            print(render_human(snapshot, issue_limit=args.issue_limit))
        sys.stdout.flush()

    return exit_code if final_snapshot is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
