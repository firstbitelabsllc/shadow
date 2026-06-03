#!/usr/bin/env python3
"""Diagnose failed FirstBite local-CI execute reports without rerunning lanes.

The M22 observer records red lanes as drift. This helper performs the next
read-only step: inspect report.json plus referenced run.log files, cluster
failure signatures, and emit a resume packet for the owning plan.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SCRIPT_NAME = "vidux-firstbite-diagnose.py"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
MAX_LINE_CHARS = 260
DECLARED_NONPASS_RE = re.compile(
    r"\b(?P<passing>\d+)\s*/\s*(?P<total>\d+)\s+declared pass;\s*"
    r"(?P<nonpass>\d+)\s+non-pass\b"
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _report_id(report: dict[str, Any], path: Path) -> str:
    explicit = report.get("run_id") or report.get("id")
    if explicit:
        return str(explicit)
    return path.parent.name or path.stem


def _lane_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    lanes = report.get("lanes")
    if isinstance(lanes, list):
        return [lane for lane in lanes if isinstance(lane, dict)]
    failing_lanes = (
        report.get("goal_audit", {})
        .get("local_ci_launch_trust", {})
        .get("failing_lanes")
    )
    if isinstance(failing_lanes, list):
        return [lane for lane in failing_lanes if isinstance(lane, dict)]
    return []


def _launch_trust(report: dict[str, Any]) -> dict[str, Any]:
    launch = (
        report.get("goal_audit", {})
        .get("local_ci_launch_trust", {})
    )
    if isinstance(launch, dict):
        return launch
    return {}


def _declared_lanes_summary(launch: dict[str, Any]) -> str | None:
    for key in ("blocked_gates", "warning_gates", "ready_gates", "gates"):
        gates = launch.get(key)
        if not isinstance(gates, list):
            continue
        for gate in gates:
            if not isinstance(gate, dict) or gate.get("id") != "declared-lanes":
                continue
            summary = gate.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
    return None


def _parse_declared_nonpass_count(summary: str | None) -> dict[str, int] | None:
    if not summary:
        return None
    match = DECLARED_NONPASS_RE.search(summary)
    if not match:
        return None
    return {
        "declared_passing_lane_count": int(match.group("passing")),
        "declared_total_lane_count": int(match.group("total")),
        "aggregate_nonpass_lane_count": int(match.group("nonpass")),
    }


def _coverage_status(visible_count: int, aggregate_count: int | None) -> tuple[str, int | None]:
    if aggregate_count is None:
        return "detail_only", None
    undocumented_count = max(aggregate_count - visible_count, 0)
    if aggregate_count > visible_count:
        return "partial", undocumented_count
    if aggregate_count < visible_count:
        return "inconsistent", 0
    return "complete", 0


def _is_failed_lane(lane: dict[str, Any]) -> bool:
    status = str(lane.get("status") or "").lower()
    return status not in {"", "pass", "ready", "ok"}


def _clean_line(line: str) -> str:
    cleaned = ANSI_RE.sub("", line).replace("\r", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > MAX_LINE_CHARS:
        return cleaned[: MAX_LINE_CHARS - 1] + "..."
    return cleaned


def _read_log(path_text: str | None) -> tuple[bool, list[str]]:
    if not path_text:
        return False, []
    path = Path(path_text)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, []
    return True, [_clean_line(line) for line in text.splitlines()]


def _line_hits(lines: list[str], pattern: str, *, limit: int) -> list[dict[str, Any]]:
    regex = re.compile(pattern)
    hits: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if not regex.search(line):
            continue
        hits.append({"line": index, "text": line})
        if len(hits) >= limit:
            break
    return hits


def _first_match(lines: list[str], pattern: str) -> re.Match[str] | None:
    regex = re.compile(pattern)
    for line in lines:
        match = regex.search(line)
        if match:
            return match
    return None


def _failed_test_names(lines: list[str], *, limit: int) -> list[str]:
    names: list[str] = []
    patterns = [
        re.compile(r"Test Case '([^']+)' failed"),
        re.compile(r"error: -\[([^\]]+)\] : (.+)$"),
        re.compile(r"^\s*\[[^\]]+\]\s+›\s+(.+)$"),
        re.compile(r"^\s*FAIL\s+(.+)$"),
        re.compile(r"^\s*.\s+(.+?)\s*$"),
    ]
    for line in lines:
        for regex in patterns:
            match = regex.search(line)
            if not match:
                continue
            name = " ".join(part.strip() for part in match.groups() if part.strip())
            if name and name not in names:
                names.append(name)
            break
        if len(names) >= limit:
            break
    return names


def _xcode_summary(lane: dict[str, Any], lines: list[str]) -> tuple[str, dict[str, Any]]:
    result = lane.get("xcode_result")
    if not isinstance(result, dict):
        result = {}
    failed = result.get("failed_tests")
    total = result.get("total_tests")
    tests = _failed_test_names(
        [line for line in lines if "error: -[" in line or "Test Case '" in line and " failed" in line],
        limit=12,
    )
    if failed is not None and total is not None:
        summary = f"xcode result failed with {failed}/{total} failed tests"
    else:
        summary = "xcode result contains failed tests"
    return summary, {"xcode_result": result, "failed_tests": tests}


def _classify_lane(lane: dict[str, Any], log_found: bool, lines: list[str]) -> dict[str, Any]:
    status = str(lane.get("status") or "unknown").lower()
    reason = str(lane.get("reason") or "")
    evidence: list[dict[str, Any]] = []
    extras: dict[str, Any] = {}
    category = "unknown_failure"
    confidence = "low"
    summary = reason or "lane failed"
    rerun_gate = "operator_approval_required"

    missing_module = _first_match(lines, r"Error: Cannot find module '([^']+)'")
    if status == "missing" or "no executable proof found" in reason.lower():
        category = "missing_executable_proof"
        confidence = "high"
        summary = reason or "catalog lane has no executable proof in the current launch-trust packet"
        evidence = _line_hits(lines, r"missing|proof|catalog|lane", limit=6)
    elif "expected yellow" in reason.lower() or status == "warn":
        category = "expected_yellow_trust_gate"
        confidence = "high" if "expected yellow" in reason.lower() else "medium"
        summary = reason or "lane is warning/yellow and remains a launch-trust follow-up"
        evidence = _line_hits(
            lines,
            r"expected yellow|yellow|trust|contract|Grafana|OTEL|otel|source|review",
            limit=10,
        )
    elif missing_module:
        module_path = missing_module.group(1)
        category = "missing_module_in_clean_source"
        confidence = "high"
        summary = f"clean worktree cannot find {Path(module_path).name}"
        extras["missing_module"] = module_path
        evidence = _line_hits(lines, r"Cannot find module|command_template=|resolved_source_ref=", limit=6)
    elif _first_match(lines, r"expected generated E2E bundle status|false !== true"):
        category = "snowcubes_generated_e2e_bundle_status"
        confidence = "high"
        summary = "Snowcubes readiness expected the generated E2E bundle status to be true"
        evidence = _line_hits(
            lines,
            r"expected generated E2E bundle status|false !== true|command_template=|resolved_source_ref=",
            limit=8,
        )
    elif status == "fail" and "xcode result contains failed tests" in reason.lower():
        category = "xcode_failed_tests"
        confidence = "high"
        summary, extras = _xcode_summary(lane, lines)
        evidence = _line_hits(lines, r"error: -\[|Test Case '.*' failed|xcode_result=|Executed [0-9]+ tests, with [1-9][0-9]* failure", limit=12)
    elif _first_match(lines, r"TestingLibraryElementError|Unable to find an accessible element"):
        category = "jest_accessible_element_assertion"
        confidence = "high"
        summary = "Jest navigation assertion could not find the expected accessible element"
        extras["failed_tests"] = _failed_test_names(
            [line for line in lines if "FAIL " in line or "● " in line], limit=8
        )
        evidence = _line_hits(
            lines,
            r"FAIL |TestingLibraryElementError|Unable to find an accessible element|Test Suites: [1-9][0-9]* failed|Tests: [1-9][0-9]* failed",
            limit=10,
        )
    elif _first_match(lines, r"^\s*[0-9]+ failed\b|^\s*\[[^\]]+\]\s+›"):
        category = "playwright_expectation_failures"
        confidence = "medium"
        summary = "Playwright reached the app and failed user-visible assertions"
        extras["failed_tests"] = _failed_test_names(
            [
                line
                for line in lines
                if re.search(r"^\s*\[[^\]]+\]\s+›|^\s*[0-9]+ failed\b", line)
            ],
            limit=12,
        )
        evidence = _line_hits(
            lines,
            r"^[ ]*[0-9]+ failed\b|^\s*\[[^\]]+\]\s+›|Error: .*to(BeVisible|Contain)",
            limit=14,
        )
        if _first_match(lines, r"Supabase admin access is not configured|STRIPE_PRICE_"):
            extras["environment_warnings"] = [
                hit["text"]
                for hit in _line_hits(
                    lines,
                    r"Supabase admin access is not configured|STRIPE_PRICE_",
                    limit=6,
                )
            ]
    elif _first_match(lines, r"timeout|timed out|no output",):
        category = "timeout_or_stall"
        confidence = "medium"
        summary = "log contains timeout or stall language"
        evidence = _line_hits(lines, r"timeout|timed out|no output", limit=8)
    elif log_found:
        evidence = _line_hits(lines, r"Error:|FAIL|failed|TEST FAILED|rc=", limit=10)

    if not log_found and category == "unknown_failure":
        category = "missing_log"
        confidence = "medium"
        summary = "report references no readable run.log"

    resolved_source_ref = lane.get("resolved_source_ref")
    if not resolved_source_ref:
        resolved_match = _first_match(lines, r"\bresolved_source_ref=([0-9a-f]{7,40})\b")
        if resolved_match:
            resolved_source_ref = resolved_match.group(1)

    return {
        "lane": lane.get("lane"),
        "repo": lane.get("repo"),
        "kind": lane.get("kind"),
        "status": status,
        "rc": lane.get("rc"),
        "trust_status": lane.get("trust_status"),
        "reason": reason or None,
        "source_head": lane.get("source_head"),
        "resolved_source_ref": resolved_source_ref,
        "log_path": lane.get("log_path"),
        "log_found": log_found,
        "category": category,
        "confidence": confidence,
        "summary": summary,
        "rerun_gate": rerun_gate,
        "evidence": evidence,
        **extras,
    }


def _group_key(diagnosis: dict[str, Any]) -> str:
    category = str(diagnosis.get("category") or "unknown_failure")
    if category == "missing_module_in_clean_source":
        module = Path(str(diagnosis.get("missing_module") or "")).name
        return f"{category}:{module}"
    if category == "xcode_failed_tests":
        return category
    if category == "jest_accessible_element_assertion":
        tests = diagnosis.get("failed_tests")
        first = tests[0] if isinstance(tests, list) and tests else ""
        return f"{category}:{first}"
    if category == "playwright_expectation_failures":
        return category
    return category


def _build_groups(diagnoses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for diagnosis in diagnoses:
        key = _group_key(diagnosis)
        group = grouped.setdefault(
            key,
            {
                "key": key,
                "category": diagnosis.get("category"),
                "summary": diagnosis.get("summary"),
                "confidence": diagnosis.get("confidence"),
                "lanes": [],
                "source_refs": [],
                "rerun_gate": "operator_approval_required",
            },
        )
        group["lanes"].append(diagnosis.get("lane"))
        source_ref = diagnosis.get("resolved_source_ref") or diagnosis.get("source_head")
        if source_ref and source_ref not in group["source_refs"]:
            group["source_refs"].append(source_ref)
    return sorted(
        grouped.values(),
        key=lambda item: (-len(item["lanes"]), str(item["category"]), str(item["key"])),
    )


def build_payload(reports: list[Path]) -> dict[str, Any]:
    report_summaries: list[dict[str, Any]] = []
    diagnoses: list[dict[str, Any]] = []
    aggregate_nonpass_total = 0
    has_aggregate_nonpass_count = False
    for report_path in reports:
        report = _read_json(report_path)
        run_id = _report_id(report, report_path)
        launch = _launch_trust(report)
        declared_summary = _declared_lanes_summary(launch)
        declared_counts = _parse_declared_nonpass_count(declared_summary)
        failed_lanes = [lane for lane in _lane_rows(report) if _is_failed_lane(lane)]
        aggregate_nonpass_count = None
        if declared_counts:
            aggregate_nonpass_count = declared_counts["aggregate_nonpass_lane_count"]
            aggregate_nonpass_total += aggregate_nonpass_count
            has_aggregate_nonpass_count = True
        report_coverage_status, report_undocumented_count = _coverage_status(
            len(failed_lanes),
            aggregate_nonpass_count,
        )
        report_summaries.append(
            {
                "path": str(report_path),
                "run_id": run_id,
                "overall": report.get("overall"),
                "mode": report.get("mode"),
                "source_ref": report.get("source_ref"),
                "plan_path": report.get("plan_path"),
                "failed_lane_count": len(failed_lanes),
                "completed_lanes": report.get("completed_lanes"),
                "launch_trust_summary": launch.get("summary"),
                "declared_lanes_summary": declared_summary,
                "declared_passing_lane_count": (
                    declared_counts.get("declared_passing_lane_count") if declared_counts else None
                ),
                "declared_total_lane_count": (
                    declared_counts.get("declared_total_lane_count") if declared_counts else None
                ),
                "aggregate_nonpass_lane_count": aggregate_nonpass_count,
                "diagnosis_coverage_status": report_coverage_status,
                "undocumented_nonpass_lane_count": report_undocumented_count,
            }
        )
        for lane in failed_lanes:
            log_found, lines = _read_log(str(lane.get("log_path") or ""))
            diagnosis = _classify_lane(lane, log_found, lines)
            diagnosis["run_id"] = run_id
            diagnosis["report_path"] = str(lane.get("report_path") or report_path)
            diagnoses.append(diagnosis)

    groups = _build_groups(diagnoses)
    unresolved = len(diagnoses)
    aggregate_nonpass_lane_count = aggregate_nonpass_total if has_aggregate_nonpass_count else None
    diagnosis_coverage_status, undocumented_nonpass_lane_count = _coverage_status(
        unresolved,
        aggregate_nonpass_lane_count,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SCRIPT_NAME,
        "mode": "read_only_failed_execute_diagnosis",
        "reports": report_summaries,
        "failed_lane_count": unresolved,
        "visible_failed_lane_count": unresolved,
        "aggregate_nonpass_lane_count": aggregate_nonpass_lane_count,
        "undocumented_nonpass_lane_count": undocumented_nonpass_lane_count,
        "diagnosis_coverage_status": diagnosis_coverage_status,
        "group_count": len(groups),
        "groups": groups,
        "lanes": sorted(diagnoses, key=lambda item: (str(item.get("repo")), str(item.get("lane")))),
        "next_resume": {
            "status": "needs_owner_lane_fixes_then_operator_rerun",
            "local_ci_lanes_executed": False,
            "dispatch_allowed": False,
            "rerun_gate": "operator_approval_required",
            "diagnosis_coverage_status": diagnosis_coverage_status,
            "undocumented_nonpass_lane_count": undocumented_nonpass_lane_count,
            "summary": "Diagnoses are read-only; lane fixes and any clean-source FirstBite execute rerun remain outside this helper.",
        },
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# FirstBite Failed Execute Diagnosis",
        "",
        f"- Mode: `{payload['mode']}`",
        f"- Visible failed lanes: `{payload['visible_failed_lane_count']}`",
        f"- Aggregate non-pass lanes: `{payload['aggregate_nonpass_lane_count']}`",
        f"- Diagnosis coverage: `{payload['diagnosis_coverage_status']}`",
        f"- Undocumented non-pass lanes: `{payload['undocumented_nonpass_lane_count']}`",
        f"- Failure groups: `{payload['group_count']}`",
        "- Local-CI lanes executed: `false`",
        "- Dispatch allowed: `false`",
        "- Rerun gate: `operator_approval_required`",
        "",
        "## Reports",
        "",
    ]
    for report in payload["reports"]:
        lines.append(
            f"- `{report['run_id']}`: overall=`{report.get('overall')}`, "
            f"visible_failed_lanes=`{report['failed_lane_count']}`, "
            f"aggregate_nonpass_lanes=`{report['aggregate_nonpass_lane_count']}`, "
            f"coverage=`{report['diagnosis_coverage_status']}`, path=`{report['path']}`"
        )
    lines.extend(["", "## Failure Groups", ""])
    for group in payload["groups"]:
        lanes = ", ".join(f"`{lane}`" for lane in group["lanes"])
        refs = ", ".join(f"`{ref}`" for ref in group["source_refs"]) or "`unknown`"
        lines.extend(
            [
                f"### {group['category']}",
                "",
                f"- Summary: {group['summary']}",
                f"- Lanes: {lanes}",
                f"- Source refs: {refs}",
                f"- Confidence: `{group['confidence']}`",
                f"- Rerun gate: `{group['rerun_gate']}`",
                "",
            ]
        )
    lines.extend(["## Lane Evidence", ""])
    for lane in payload["lanes"]:
        lines.extend(
            [
                f"### {lane['lane']}",
                "",
                f"- Run: `{lane['run_id']}`",
                f"- Repo: `{lane.get('repo')}`",
                f"- Category: `{lane['category']}`",
                f"- Summary: {lane['summary']}",
                f"- Log: `{lane.get('log_path')}`",
                "",
            ]
        )
        evidence = lane.get("evidence") if isinstance(lane.get("evidence"), list) else []
        if evidence:
            lines.append("Evidence snippets:")
            for hit in evidence[:8]:
                lines.append(f"- line {hit['line']}: {hit['text']}")
            lines.append("")
    lines.extend(
        [
            "## Non-Claims",
            "",
            "- No local-CI lane was executed or rerun.",
            "- No external repo was mutated.",
            "- No drift cache, plan block, worker dispatch, LaunchAgent, cleanup, staging, commit, or push was performed by this helper.",
            "- Aggregate launch-trust counts may include non-pass lanes that the compact failing-lane detail did not enumerate; coverage fields make that gap explicit.",
            "- The two FirstBite execute report rows remain red in ledger health until owner-lane fixes land and an explicitly approved clean-source rerun passes.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read failed FirstBite report.json files and cluster run.log failure signatures."
    )
    parser.add_argument("reports", nargs="+", type=Path, help="FirstBite report.json path(s)")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    parser.add_argument("--write-json", type=Path, default=None, help="Write JSON payload to this path.")
    parser.add_argument("--write-markdown", type=Path, default=None, help="Write Markdown diagnosis to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = build_payload(args.reports)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{SCRIPT_NAME}: {exc}\n")
        return 2

    if args.write_json is not None:
        args.write_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_markdown is not None:
        write_markdown(payload, args.write_markdown)

    if args.json:
        print(json.dumps(payload, sort_keys=True))
        return 0

    print(
        f"{payload['visible_failed_lane_count']} visible failed FirstBite lane(s), "
        f"{payload['group_count']} diagnosis group(s), "
        f"coverage={payload['diagnosis_coverage_status']}, local_ci_lanes_executed=false"
    )
    for group in payload["groups"]:
        lanes = ", ".join(str(lane) for lane in group["lanes"])
        print(f"- {group['category']}: {group['summary']} [{lanes}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
