#!/usr/bin/env python3
"""Observe FirstBite local-CI reports and propose Vidux drift records.

This is the M22/P3 "recursive bridge" brake: it reads report.json files,
deterministically ranks red/stale lane observations, and emits advisory
`vidux-drift-log.py` arguments. It never mutates PLAN.md and never dispatches
workers.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SCRIPT_NAME = "vidux-firstbite-observe.py"
DISPATCH_ENV = "BRAIN_AUTODISPATCH"
TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LaneObservation:
    report_path: Path
    run_id: str
    lane: str
    repo: str | None
    status: str
    trust_status: str | None
    reason: str | None
    log_path: str | None
    source_commit: str | None
    proof_age_hours: float | None
    stale_proof: bool


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _unwrap_mcp_text(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept either raw report JSON or an MCP call wrapper with text JSON."""
    content = payload.get("content")
    if not isinstance(content, list):
        return payload
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            nested = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(nested, dict):
            return nested
    return payload


def _lane_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(report.get("lanes"), list):
        return [lane for lane in report["lanes"] if isinstance(lane, dict)]
    if isinstance(report.get("latest_lane_proof"), list):
        return [lane for lane in report["latest_lane_proof"] if isinstance(lane, dict)]
    return []


def _report_id(report: dict[str, Any], path: Path) -> str:
    explicit = report.get("run_id") or report.get("id")
    if explicit:
        return str(explicit)
    if path.parent.name.lower() in {"evidence", "reports", "snapshots"}:
        return path.stem
    return path.parent.name or path.stem


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_bool(value: Any) -> bool:
    return value is True


def observations_from_report(path: Path) -> list[LaneObservation]:
    report = _unwrap_mcp_text(_read_json(path))
    fallback_run_id = _report_id(report, path)
    observations: list[LaneObservation] = []
    for lane in _lane_rows(report):
        lane_name = lane.get("lane")
        status = str(lane.get("status") or "unknown").lower()
        trust_status = lane.get("trust_status")
        stale_proof = _as_bool(lane.get("stale_proof"))
        if status in {"pass", "ready", "ok"} and not stale_proof:
            continue
        if not isinstance(lane_name, str) or not lane_name.strip():
            continue
        lane_report_path = Path(
            str(lane.get("report_path") or lane.get("reportPath") or path)
        )
        lane_run_id = str(lane.get("run_id") or lane.get("runId") or fallback_run_id)
        observations.append(
            LaneObservation(
                report_path=lane_report_path,
                run_id=lane_run_id,
                lane=lane_name.strip(),
                repo=str(lane.get("repo")) if lane.get("repo") is not None else None,
                status=status,
                trust_status=str(trust_status).lower() if trust_status is not None else None,
                reason=str(lane.get("reason")) if lane.get("reason") is not None else None,
                log_path=str(lane.get("log_path") or lane.get("logPath"))
                if lane.get("log_path") is not None or lane.get("logPath") is not None
                else None,
                source_commit=str(lane.get("source_commit") or lane.get("resolved_source_ref") or "")
                or None,
                proof_age_hours=_as_float(lane.get("proof_age_hours")),
                stale_proof=stale_proof,
            )
        )
    return observations


def _priority(observation: LaneObservation) -> tuple[int, float, str]:
    severity = 0
    if observation.status in {"fail", "failed", "error", "red"}:
        severity = 40
    elif observation.status in {"warn", "warning", "yellow"}:
        severity = 30
    elif observation.status in {"missing", "unknown"}:
        severity = 20
    if observation.stale_proof:
        severity += 10
    age = observation.proof_age_hours if observation.proof_age_hours is not None else -1.0
    return (-severity, -age, observation.lane)


def _evidence_refs(observation: LaneObservation) -> list[str]:
    refs = [str(observation.report_path)]
    if observation.log_path:
        refs.append(observation.log_path)
    return refs


def _meaningful_run_id(run_id: str) -> bool:
    lowered = run_id.strip().lower()
    if lowered in {"", "evidence", "report", "report.json", "status", "snapshot"}:
        return False
    return len(lowered) >= 8


def _plan_record_state(observation: LaneObservation, plan_text: str | None) -> tuple[str, str]:
    if plan_text is None:
        return ("unknown", "plan file was not readable")
    lines = plan_text.splitlines()
    meaningful_run_id = _meaningful_run_id(observation.run_id)
    if meaningful_run_id:
        for line in lines:
            if "Drift" in line and observation.lane in line and observation.run_id in line:
                return ("already_recorded", "plan drift line contains this run id and lane")
        for line in lines:
            if observation.lane in line and observation.run_id in line:
                return ("already_recorded", "plan line contains this run id and lane")
        for line in lines:
            if "Drift" in line and observation.lane in line:
                return ("lane_seen_without_run", "plan drift line contains this lane but not this run id")
    else:
        for line in lines:
            if "Drift" in line and observation.lane in line:
                return ("already_recorded", "plan drift line contains this lane and run id is not specific enough")
    if observation.lane in plan_text:
        return ("lane_seen_without_run", "plan text contains this lane but not this run id")
    return ("missing_record", "plan text does not contain this lane observation")


def _lint_advisories(advisories: list[dict[str, Any]], *, plan_readable: bool) -> dict[str, Any]:
    counts = {
        "already_recorded": 0,
        "lane_seen_without_run": 0,
        "missing_record": 0,
        "unknown": 0,
    }
    missing_evidence = 0
    blocking_missing_evidence = 0
    for item in advisories:
        state = str(item.get("plan_record_state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            missing_evidence += 1
            if item.get("impact") == "blocking":
                blocking_missing_evidence += 1

    if blocking_missing_evidence:
        status = "blocked"
        summary = f"{blocking_missing_evidence} blocking advisory/advisories missing evidence refs"
    elif not plan_readable:
        status = "warning"
        summary = "plan file was not readable; duplicate-record lint is unknown"
    elif counts["missing_record"] or counts["lane_seen_without_run"]:
        status = "warning"
        summary = (
            f"{counts['missing_record']} missing record(s), "
            f"{counts['lane_seen_without_run']} lane-only match(es), "
            f"{counts['already_recorded']} already recorded"
        )
    else:
        status = "ready"
        summary = f"all {counts['already_recorded']} advisory/advisories already appear recorded in the plan"

    return {
        "status": status,
        "summary": summary,
        "plan_readable": plan_readable,
        "record_counts": counts,
        "missing_evidence_ref_count": missing_evidence,
        "blocking_missing_evidence_ref_count": blocking_missing_evidence,
        "rule": "M22 remains observe-only: plan-lint may recommend drift records but must not write the plan, drift cache, or dispatch workers.",
    }


def _dispatch_policy(
    advisories: list[dict[str, Any]],
    plan_lint: dict[str, Any],
    *,
    autodispatch_requested: bool,
) -> dict[str, Any]:
    record_counts = plan_lint.get("record_counts") if isinstance(plan_lint, dict) else None
    if not isinstance(record_counts, dict):
        record_counts = {}
    manual_record_pending_count = int(record_counts.get("missing_record") or 0) + int(
        record_counts.get("lane_seen_without_run") or 0
    )

    blockers = ["m22_observe_only_brake"]
    if plan_lint.get("status") != "ready":
        blockers.append("plan_lint_not_ready")
    if manual_record_pending_count:
        blockers.append("manual_drift_records_pending")
    if int(plan_lint.get("blocking_missing_evidence_ref_count") or 0):
        blockers.append("blocking_advisory_missing_evidence")

    if manual_record_pending_count:
        next_action = "record_missing_drift_advisories_manually"
    elif plan_lint.get("status") != "ready":
        next_action = "fix_plan_lint_before_policy_promotion"
    else:
        next_action = "keep_observe_only_until_operator_promotes_cockpit_gate"

    status = "observe_only" if blockers == ["m22_observe_only_brake"] else "blocked"
    return {
        "status": status,
        "dispatch_allowed": False,
        "requested": autodispatch_requested,
        "advisory_count": len(advisories),
        "manual_record_pending_count": manual_record_pending_count,
        "blockers": blockers,
        "next_action": next_action,
        "cockpit_gate": {
            "name": "M22 recursive bridge cockpit gate",
            "allowed": False,
            "reason": "observe-only policy is explicit; dispatch promotion requires a separate operator-approved plan change",
        },
        "rule": "This observer may rank evidence and explain policy state, but it must not dispatch workers or promote BRAIN_AUTODISPATCH on its own.",
    }


def _impact(observation: LaneObservation) -> str:
    if observation.status in {"fail", "failed", "error", "red"}:
        return "blocking"
    if observation.stale_proof or observation.status in {"missing", "unknown"}:
        return "material"
    return "minor"


def _actual(observation: LaneObservation) -> str:
    parts = [
        f"FirstBite report {observation.run_id} observed {observation.lane} as {observation.status}",
    ]
    if observation.trust_status:
        parts.append(f"trust={observation.trust_status}")
    if observation.stale_proof:
        parts.append("stale_proof=true")
    if observation.proof_age_hours is not None:
        parts.append(f"proof_age_hours={observation.proof_age_hours:g}")
    return "; ".join(parts) + "."


def drift_command(
    observation: LaneObservation,
    *,
    plan_path: Path,
    drift_script: Path,
    cache_path: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(drift_script),
        str(plan_path),
        "--task",
        f"M22 observe-only FirstBite lane {observation.lane}",
        "--planned",
        "FirstBite lane proof should be current, evidence-backed, and safe to route into the Vidux plan.",
        "--actual",
        _actual(observation),
        "--why",
        observation.reason or "The local-CI report is red, stale, warning, or missing current proof.",
        "--plan-update",
        "Keep recursive bridge observe-only; record evidence-backed drift before any plan block or dispatch.",
        "--next",
        f"Diagnose {observation.lane} from its report/log evidence, then rerun the lane from a clean source ref.",
        "--cause",
        "verification_failure",
        "--impact",
        _impact(observation),
        "--prevention",
        "Before dispatch, convert red or stale FirstBite lane proof into an evidence-backed Vidux drift record.",
        "--tag",
        "firstbite",
        "--tag",
        "observe-only",
        "--tag",
        observation.lane,
    ]
    for ref in _evidence_refs(observation):
        command.extend(["--evidence-ref", ref])
    if cache_path is not None:
        command.extend(["--cache", str(cache_path)])
    return command


def _shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def build_payload(
    reports: list[Path],
    *,
    plan_path: Path,
    drift_script: Path,
    cache_path: Path | None,
    limit: int | None = None,
) -> dict[str, Any]:
    observations: list[LaneObservation] = []
    report_summaries: list[dict[str, Any]] = []
    for report_path in reports:
        report = _unwrap_mcp_text(_read_json(report_path))
        lane_count = len(_lane_rows(report))
        found = observations_from_report(report_path)
        observations.extend(found)
        report_summaries.append(
            {
                "path": str(report_path),
                "run_id": _report_id(report, report_path),
                "overall": report.get("overall"),
                "lane_count": lane_count,
                "observed_count": len(found),
            }
        )

    observations.sort(key=_priority)
    if limit is not None:
        observations = observations[:limit]

    plan_text: str | None
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError:
        plan_text = None

    env_value = os.environ.get(DISPATCH_ENV, "off")
    autodispatch_requested = env_value.strip().lower() in TRUTHY
    advisories = []
    for index, observation in enumerate(observations, start=1):
        command = drift_command(
            observation,
            plan_path=plan_path,
            drift_script=drift_script,
            cache_path=cache_path,
        )
        record_state, record_reason = _plan_record_state(observation, plan_text)
        impact = _impact(observation)
        advisories.append(
            {
                "rank": index,
                "lane": observation.lane,
                "repo": observation.repo,
                "run_id": observation.run_id,
                "status": observation.status,
                "trust_status": observation.trust_status,
                "impact": impact,
                "reason": observation.reason,
                "source_commit": observation.source_commit,
                "proof_age_hours": observation.proof_age_hours,
                "stale_proof": observation.stale_proof,
                "evidence_refs": _evidence_refs(observation),
                "plan_record_state": record_state,
                "plan_record_reason": record_reason,
                "recommended_action": "skip_duplicate_record"
                if record_state == "already_recorded"
                else "record_drift_manually",
                "drift_command": command,
                "drift_command_shell": _shell_join(command),
            }
        )

    plan_lint = _lint_advisories(advisories, plan_readable=plan_text is not None)
    dispatch_policy = _dispatch_policy(
        advisories,
        plan_lint,
        autodispatch_requested=autodispatch_requested,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "source": SCRIPT_NAME,
        "mode": "observe_only",
        "plan_path": str(plan_path),
        "reports": report_summaries,
        "autodispatch": {
            "env": DISPATCH_ENV,
            "value": env_value,
            "requested": autodispatch_requested,
            "dispatch_allowed": False,
            "action": "suppressed_observe_only" if autodispatch_requested else "off",
        },
        "plan_lint": plan_lint,
        "dispatch_policy": dispatch_policy,
        "advisory_count": len(advisories),
        "advisories": advisories,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Observe FirstBite report.json files and emit Vidux drift advisories."
    )
    parser.add_argument("reports", nargs="+", type=Path, help="FirstBite report.json path(s)")
    parser.add_argument(
        "--plan",
        type=Path,
        default=root / "projects" / "firstbite-local-ci-mega" / "PLAN.md",
        help="PLAN.md path used in emitted vidux-drift-log commands.",
    )
    parser.add_argument(
        "--drift-script",
        type=Path,
        default=root / "scripts" / "vidux-drift-log.py",
        help="Path to vidux-drift-log.py.",
    )
    parser.add_argument("--cache", type=Path, default=None, help="Optional drift cache JSONL path.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum advisories to emit.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a compact text list.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = build_payload(
            args.reports,
            plan_path=args.plan,
            drift_script=args.drift_script,
            cache_path=args.cache,
            limit=args.limit,
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{SCRIPT_NAME}: {exc}\n")
        return 2

    if args.json:
        print(json.dumps(payload, sort_keys=True))
        return 0

    if not payload["advisories"]:
        print("no red/stale FirstBite lane observations")
        return 0
    print(
        f"{payload['advisory_count']} observe-only FirstBite drift advisories "
        f"(dispatch_allowed=false)"
    )
    for item in payload["advisories"]:
        print(
            f"- #{item['rank']} {item['lane']}: {item['status']} "
            f"[{item['plan_record_state']}] -> {item['drift_command_shell']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
