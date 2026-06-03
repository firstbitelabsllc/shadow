#!/usr/bin/env python3
"""Build a read-only verified-alive rollup for FirstBite operator truth.

This is the M23/P4 bridge layer: it reads existing evidence packets and
summarizes what a cockpit/digest may render. It never runs local-CI lanes,
installs LaunchAgents, deletes files, writes drift records, or dispatches
workers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


SCHEMA_VERSION = 1
SCRIPT_NAME = "vidux-firstbite-verified-alive.py"
DEFAULT_EVIDENCE_DIR = Path("projects/firstbite-local-ci-mega/evidence")
DEFAULT_FIRSTBITE_MCP_DIR = Path(
    "/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci"
)
DEFAULT_PLAN_PATH = Path("projects/firstbite-local-ci-mega/PLAN.md")
DEFAULT_MOUSSEY_BASE_URL = "http://127.0.0.1:4321"
DEFAULT_AI_REPO = Path("/Users/leokwan/Development/ai")
DEFAULT_CAPTAIN_AUDIT_SCRIPT = DEFAULT_AI_REPO / "skills/captain/scripts/audit_skills.sh"
RETENTION_REPORT_GLOB = (
    "/Users/leokwan/.agent-ledger/firstbite-retention-review-runner/*/report.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _unwrap_mcp_text(payload: dict[str, Any]) -> dict[str, Any]:
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


def _status_rank(status: str) -> int:
    return {"ready": 0, "warning": 1, "blocked": 2}.get(status, 1)


def _worst_status(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "warning"
    return max((str(check.get("status") or "warning") for check in checks), key=_status_rank)


def _as_bool(value: Any) -> bool:
    return value is True


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _first_output_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _latest_file(pattern: str) -> Path:
    matches = sorted(Path("/").glob(pattern.removeprefix("/")), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise ValueError(f"no files matched {pattern}")
    return matches[-1]


def _run_json_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise ValueError(f"{command[0]} failed with rc={result.returncode}: {message}")
    text = result.stdout.strip()
    if not text:
        raise ValueError(f"{command[0]} produced no JSON output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{command[0]} output was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{command[0]} output must be a JSON object")
    return payload


def _run_captured_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _fetch_json(url: str, *, timeout: float = 12.0) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to fetch JSON from {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{url} must return a JSON object")
    return payload


def _default_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-m23-refresh")


def refresh_evidence(
    *,
    evidence_dir: Path,
    prefix: str,
    retention_path: Path | None,
    firstbite_mcp_dir: Path,
    plan_path: Path,
    moussey_base_url: str,
) -> dict[str, Path]:
    retention = retention_path or _latest_file(RETENTION_REPORT_GLOB)
    status_path = evidence_dir / f"{prefix}-firstbite-status.json"
    observe_path = evidence_dir / f"{prefix}-observe-policy.json"
    health_path = evidence_dir / f"{prefix}-moussey-health.json"
    chat_path = evidence_dir / f"{prefix}-chat-providers.json"
    local_ci_path = evidence_dir / f"{prefix}-moussey-local-ci.json"
    captain_audit_path = evidence_dir / f"{prefix}-captain-audit.json"

    status_payload = _run_json_command(
        ["npm", "run", "--silent", "call", "--", "status", '{"limit":8}'],
        cwd=firstbite_mcp_dir,
    )
    _write_json(status_path, status_payload)

    observe_payload = _run_json_command(
        [
            sys.executable,
            str(Path(__file__).with_name("vidux-firstbite-observe.py")),
            str(status_path),
            "--plan",
            str(plan_path),
            "--limit",
            "8",
            "--json",
        ],
        cwd=Path.cwd(),
    )
    _write_json(observe_path, observe_payload)

    base = moussey_base_url.rstrip("/")
    _write_json(health_path, _fetch_json(f"{base}/api/health"))
    _write_json(chat_path, _fetch_json(f"{base}/api/chat/providers"))
    _write_json(local_ci_path, _fetch_json(f"{base}/api/coding/local-ci?view=launch-trust"))
    _write_json(
        captain_audit_path,
        _run_captured_command(["bash", str(DEFAULT_CAPTAIN_AUDIT_SCRIPT)], cwd=DEFAULT_AI_REPO),
    )

    return {
        "status": status_path,
        "retention": retention,
        "observe": observe_path,
        "health": health_path,
        "chat_providers": chat_path,
        "local_ci": local_ci_path,
        "captain_audit": captain_audit_path,
    }


def _check_status_snapshot(status: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    catalog = status.get("catalog") if isinstance(status.get("catalog"), dict) else {}
    freshness = (
        status.get("freshness_contract")
        if isinstance(status.get("freshness_contract"), dict)
        else {}
    )
    disk_guard = status.get("disk_guard") if isinstance(status.get("disk_guard"), dict) else {}
    live_headroom = (
        disk_guard.get("live_headroom") if isinstance(disk_guard.get("live_headroom"), dict) else {}
    )

    lane_count = _as_int(catalog.get("lane_count") or catalog.get("declared_count"))
    catalog_stale = _as_bool(catalog.get("catalog_stale") or freshness.get("catalog_stale"))
    checks = [
        {
            "id": "firstbite_catalog",
            "status": "blocked" if lane_count <= 0 else "warning" if catalog_stale else "ready",
            "summary": (
                "repo-backed catalog is stale"
                if catalog_stale
                else f"repo-backed catalog has {lane_count} declared lane(s)"
            ),
            "source": str(source_path),
            "facts": {
                "lane_count": lane_count,
                "repo_count": _as_int(catalog.get("repo_count")),
                "catalog_stale": catalog_stale,
                "catalog_age_seconds": catalog.get("catalog_age_seconds")
                or freshness.get("catalog_age_seconds"),
            },
        }
    ]

    stale_count = _as_int(freshness.get("stale_proof_count"))
    unknown_count = _as_int(freshness.get("unknown_proof_age_count"))
    latest_lane_count = len(status.get("latest_lane_proof") or [])
    proof_status = "warning" if stale_count or unknown_count else "ready"
    checks.append(
        {
            "id": "lane_proof_freshness",
            "status": proof_status,
            "summary": (
                f"{stale_count} stale and {unknown_count} unknown proof-age lane(s)"
                if proof_status == "warning"
                else "all latest lane proofs are current-age"
            ),
            "source": str(source_path),
            "facts": {
                "latest_lane_count": latest_lane_count,
                "stale_proof_count": stale_count,
                "unknown_proof_age_count": unknown_count,
                "rule": freshness.get("rule"),
            },
        }
    )

    disk_blocked = _as_bool(
        disk_guard.get("blocked")
        or disk_guard.get("write_floor_blocked")
        or live_headroom.get("write_floor_blocked")
    )
    disk_status = str(disk_guard.get("status") or live_headroom.get("status") or "unknown").lower()
    checks.append(
        {
            "id": "disk_guard",
            "status": "blocked" if disk_blocked else "warning" if disk_status == "warning" else "ready",
            "summary": (
                "disk guard blocks writes"
                if disk_blocked
                else f"disk guard reports {disk_status or 'unknown'}"
            ),
            "source": str(source_path),
            "facts": {
                "disk_guard_status": disk_status,
                "disk_available_gib": disk_guard.get("disk_available_gib")
                or live_headroom.get("disk_available_gib"),
                "disk_capacity_percent": disk_guard.get("disk_capacity_percent")
                or live_headroom.get("disk_capacity_percent"),
                "write_floor_blocked": disk_blocked,
                "host": disk_guard.get("host") or live_headroom.get("host"),
            },
        }
    )
    return checks


def _check_retention(retention: dict[str, Any], source_path: Path) -> dict[str, Any]:
    totals = retention.get("totals") if isinstance(retention.get("totals"), dict) else {}
    launchagent = (
        retention.get("launchagent") if isinstance(retention.get("launchagent"), dict) else {}
    )
    readonly_safe = (
        _as_bool(retention.get("readonly"))
        and not _as_bool(retention.get("deletion_performed"))
        and not _as_bool(retention.get("install_performed"))
    )
    installed = _as_bool(launchagent.get("installed"))
    status = "blocked" if not readonly_safe else "ready" if installed else "warning"
    summary = (
        "retention report is not read-only safe"
        if not readonly_safe
        else "retention LaunchAgent is installed"
        if installed
        else "retention review template exists but is not installed"
    )
    return {
        "id": "retention_watchdog",
        "status": status,
        "summary": summary,
        "source": str(source_path),
        "facts": {
            "readonly": retention.get("readonly"),
            "deletion_performed": retention.get("deletion_performed"),
            "install_performed": retention.get("install_performed"),
            "cadence_seconds": retention.get("cadence_seconds"),
            "approval_required_gib": totals.get("approval_required_gib"),
            "proof_prune_candidate_count": totals.get("proof_prune_candidate_count"),
            "cache_prune_candidate_count": totals.get("cache_prune_candidate_count"),
            "cache_active_count": totals.get("cache_active_count"),
            "launchagent_installed": installed,
            "launchagent_template_path": launchagent.get("template_path"),
        },
    }


def _check_observe_policy(observe: dict[str, Any], source_path: Path) -> dict[str, Any]:
    plan_lint = observe.get("plan_lint") if isinstance(observe.get("plan_lint"), dict) else {}
    policy = (
        observe.get("dispatch_policy")
        if isinstance(observe.get("dispatch_policy"), dict)
        else {}
    )
    autodispatch = (
        observe.get("autodispatch") if isinstance(observe.get("autodispatch"), dict) else {}
    )
    plan_lint_status = str(plan_lint.get("status") or "unknown")
    dispatch_allowed = _as_bool(policy.get("dispatch_allowed")) or _as_bool(
        autodispatch.get("dispatch_allowed")
    )
    policy_status = str(policy.get("status") or "unknown")
    if dispatch_allowed:
        status = "blocked"
        summary = "dispatch policy unexpectedly allows dispatch"
    elif plan_lint_status != "ready":
        status = "warning"
        summary = f"drift plan-lint is {plan_lint_status}"
    elif policy_status != "observe_only":
        status = "warning"
        summary = f"dispatch policy is {policy_status}"
    else:
        status = "ready"
        summary = "drift tile is recorded and dispatch remains observe-only"
    return {
        "id": "drift_tile",
        "status": status,
        "summary": summary,
        "source": str(source_path),
        "facts": {
            "advisory_count": observe.get("advisory_count"),
            "plan_lint_status": plan_lint_status,
            "plan_record_counts": plan_lint.get("record_counts"),
            "dispatch_policy_status": policy_status,
            "dispatch_allowed": dispatch_allowed,
            "policy_blockers": policy.get("blockers"),
            "cockpit_gate": policy.get("cockpit_gate"),
        },
    }


def _check_moussey_health(health: dict[str, Any], source_path: Path) -> dict[str, Any]:
    ok = _as_bool(health.get("ok"))
    return {
        "id": "moussey_health",
        "status": "ready" if ok else "blocked",
        "summary": "Moussey health endpoint is ok" if ok else "Moussey health endpoint is not ok",
        "source": str(source_path),
        "facts": {
            "ok": health.get("ok"),
            "codex_ready": (health.get("codex") or {}).get("ready")
            if isinstance(health.get("codex"), dict)
            else None,
            "hermes_ready": (health.get("hermes") or {}).get("ready")
            if isinstance(health.get("hermes"), dict)
            else None,
        },
    }


def _check_chat_providers(providers_payload: dict[str, Any], source_path: Path) -> dict[str, Any]:
    providers = (
        providers_payload.get("providers")
        if isinstance(providers_payload.get("providers"), dict)
        else {}
    )
    local_ready = _as_bool((providers.get("local") or {}).get("ready"))
    codex_ready = _as_bool((providers.get("codex") or {}).get("ready"))
    claude_ready = _as_bool((providers.get("claude") or {}).get("ready"))
    if not local_ready:
        status = "blocked"
        summary = "local chat provider is not ready"
    elif not codex_ready or not claude_ready:
        status = "warning"
        summary = "local chat works, but one or more escalation providers are gated"
    else:
        status = "ready"
        summary = "local and escalation chat providers are ready"
    return {
        "id": "chat_front_door",
        "status": status,
        "summary": summary,
        "source": str(source_path),
        "facts": {
            "default_provider": providers_payload.get("defaultProvider"),
            "local_ready": local_ready,
            "local_message": (providers.get("local") or {}).get("message"),
            "codex_ready": codex_ready,
            "codex_message": (providers.get("codex") or {}).get("message"),
            "claude_ready": claude_ready,
            "claude_message": (providers.get("claude") or {}).get("message"),
        },
    }


def _check_moussey_local_ci(local_ci: dict[str, Any], source_path: Path) -> dict[str, Any]:
    ok = _as_bool(local_ci.get("ok"))
    launch_trust = local_ci.get("launchTrust") if isinstance(local_ci.get("launchTrust"), dict) else {}
    runner_readiness = (
        local_ci.get("runnerReadiness") if isinstance(local_ci.get("runnerReadiness"), dict) else {}
    )
    mcp_client = (
        runner_readiness.get("mcpClient")
        if isinstance(runner_readiness.get("mcpClient"), dict)
        else {}
    )
    latest_refresh = (
        mcp_client.get("latestRefreshPlan")
        if isinstance(mcp_client.get("latestRefreshPlan"), dict)
        else {}
    )
    operator_approval = (
        local_ci.get("operatorApproval")
        if isinstance(local_ci.get("operatorApproval"), dict)
        else {}
    )
    launch_summary = (
        launch_trust.get("summary")
        if launch_trust
        else local_ci.get("launchTrust")
    )
    runner_summary = (
        runner_readiness.get("summary")
        if runner_readiness
        else local_ci.get("runnerReadiness")
    )
    warning_text = " ".join(
        str(value or "")
        for value in [
            launch_summary,
            runner_summary,
            launch_trust.get("status"),
            runner_readiness.get("status"),
            mcp_client.get("claimStatus"),
        ]
    ).lower()
    status = (
        "blocked"
        if not ok
        else "warning"
        if "blocked" in warning_text or "warning" in warning_text
        else "ready"
    )
    refresh_run_id = latest_refresh.get("runId")
    refresh_verdict = latest_refresh.get("verdict")
    mcp_status = mcp_client.get("status")
    mcp_claim_status = mcp_client.get("claimStatus")
    mcp_effective_ready = mcp_claim_status == "ready" or mcp_status == "current_only"
    summary = "Moussey local-CI endpoint failed"
    if ok and mcp_effective_ready:
        summary = "Moussey local-CI endpoint responds; loaded MCP client claim is current"
    elif ok and refresh_run_id and refresh_verdict:
        summary = f"Moussey local-CI endpoint responds; MCP refresh {refresh_run_id} says {refresh_verdict}"
    elif ok:
        summary = "Moussey local-CI endpoint responds"
    approval_status = operator_approval.get("status")
    approval_gate_status = operator_approval.get("approvalGateStatus")
    approval_packet_path = operator_approval.get("approvalPacketPath") or operator_approval.get(
        "packetPath"
    )
    if ok and approval_status:
        approval_summary = str(approval_status)
        if approval_gate_status:
            approval_summary = f"{approval_summary}/{approval_gate_status}"
        summary = f"{summary}; operator approval {approval_summary}"
    refresh_safety_ok = (
        _as_bool(latest_refresh.get("readOnly"))
        and not _as_bool(latest_refresh.get("killsProcesses"))
        and not _as_bool(latest_refresh.get("restartsApps"))
        and not _as_bool(latest_refresh.get("runsCi"))
        and not _as_bool(latest_refresh.get("mutatesRepos"))
    )
    return {
        "id": "moussey_local_ci_endpoint",
        "status": status,
        "summary": summary,
        "source": str(source_path),
        "facts": {
            "ok": ok,
            "launch_trust_status": launch_trust.get("status"),
            "launch_trust_summary": launch_summary,
            "ready_gate_count": launch_trust.get("readyGateCount"),
            "warning_gate_count": launch_trust.get("warningGateCount"),
            "blocked_gate_count": launch_trust.get("blockedGateCount"),
            "runner_readiness_status": runner_readiness.get("status"),
            "runner_readiness_summary": runner_summary,
            "mcp_status": mcp_status,
            "mcp_claim_status": mcp_claim_status,
            "mcp_effective_ready": mcp_effective_ready,
            "mcp_refresh_run_id": refresh_run_id,
            "mcp_refresh_verdict": refresh_verdict,
            "mcp_refresh_report_path": latest_refresh.get("reportPath"),
            "mcp_refresh_summary_path": latest_refresh.get("summaryPath"),
            "mcp_refresh_read_only": latest_refresh.get("readOnly"),
            "mcp_refresh_kills_processes": latest_refresh.get("killsProcesses"),
            "mcp_refresh_restarts_apps": latest_refresh.get("restartsApps"),
            "mcp_refresh_runs_ci": latest_refresh.get("runsCi"),
            "mcp_refresh_mutates_repos": latest_refresh.get("mutatesRepos"),
            "mcp_refresh_safety_ok": refresh_safety_ok,
            "mcp_refresh_stale_process_count": latest_refresh.get("staleProcessCount"),
            "mcp_refresh_process_count": latest_refresh.get("processCount"),
            "mcp_effective_stale_process_count": 0
            if mcp_effective_ready
            else latest_refresh.get("staleProcessCount"),
            "mcp_refresh_lane_count": latest_refresh.get("laneCount"),
            "mcp_refresh_declared_count": latest_refresh.get("declaredCount"),
            "mcp_refresh_latest_lane_pass_count": latest_refresh.get("latestLanePassCount"),
            "mcp_refresh_latest_lane_fail_count": latest_refresh.get("latestLaneFailCount"),
            "operator_approval_status": approval_status,
            "operator_approval_gate_status": approval_gate_status,
            "operator_approval_packet_path": approval_packet_path,
            "operator_approval_candidate_path": operator_approval.get("candidatePath"),
            "operator_approval_candidate_ready": operator_approval.get("candidateReady"),
            "operator_approval_source_ref": operator_approval.get("sourceRef"),
            "operator_approval_source_ref_ready": operator_approval.get("sourceRefReady"),
            "operator_approval_canonical_tracker_complete": operator_approval.get(
                "canonicalTrackerComplete"
            ),
            "operator_approval_tracker_files_copied": operator_approval.get("trackerFilesCopied"),
            "operator_approval_local_ci_lanes_executed": operator_approval.get(
                "localCiLanesExecuted"
            ),
            "operator_approval_readonly": operator_approval.get("readonly"),
        },
    }


def _section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == heading:
            in_section = True
            continue
        if in_section and line.startswith("== ") and line.endswith(" =="):
            break
        if in_section:
            collected.append(line.rstrip())
    return collected


def _bullet_lines(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:])
    return bullets


def _check_captain_audit(audit: dict[str, Any], source_path: Path) -> dict[str, Any]:
    exit_code = audit.get("exit_code")
    stdout = audit.get("stdout") if isinstance(audit.get("stdout"), str) else ""
    stderr = audit.get("stderr") if isinstance(audit.get("stderr"), str) else ""
    git_sync_lines = [line.strip() for line in _section_lines(stdout, "== Git Sync Status ==") if line.strip()]
    tool_root_lines = [line.strip() for line in _section_lines(stdout, "== Tool Skill Roots ==") if line.strip()]
    frontmatter_warnings = [
        line
        for line in _bullet_lines(_section_lines(stdout, "== Frontmatter Health =="))
        if "WARN" in line or ">300" in line
    ]
    setup_warnings = _bullet_lines(_section_lines(stdout, "== Setup Policy Warnings =="))
    profile_missing = [
        line.strip()
        for line in _section_lines(stdout, "== Profiles ==")
        if "MISSING" in line
    ]
    redirect_issues = [
        line
        for line in _bullet_lines(_section_lines(stdout, "== Redirect Target Health =="))
        if line != "OK"
    ]
    tool_root_problem_count = sum(
        1 for line in tool_root_lines if "BROKEN" in line or "MISSING" in line or "REAL DIR" in line
    )
    hard_issue_count = tool_root_problem_count + len(profile_missing) + len(redirect_issues)
    warning_count = len(frontmatter_warnings) + len(setup_warnings)
    if exit_code != 0 or hard_issue_count:
        status = "blocked"
        summary = f"Captain audit hard checks failed with exit {exit_code}"
    elif warning_count:
        status = "warning"
        summary = (
            f"Captain audit exits 0 with {len(setup_warnings)} setup-policy warning(s) "
            f"and {len(frontmatter_warnings)} frontmatter warning(s)"
        )
    else:
        status = "ready"
        summary = "Captain audit exits 0 with no setup or frontmatter warnings"
    return {
        "id": "captain_setup_health",
        "status": status,
        "summary": summary,
        "source": str(source_path),
        "facts": {
            "exit_code": exit_code,
            "cwd": audit.get("cwd"),
            "command": audit.get("command"),
            "git_sync_status": git_sync_lines[0] if git_sync_lines else None,
            "tool_root_problem_count": tool_root_problem_count,
            "frontmatter_warning_count": len(frontmatter_warnings),
            "frontmatter_warnings": frontmatter_warnings,
            "setup_policy_warning_count": len(setup_warnings),
            "setup_policy_warnings": setup_warnings,
            "profile_missing_count": len(profile_missing),
            "redirect_issue_count": len(redirect_issues),
            "stderr_first_line": _first_output_line(stderr),
        },
    }


def build_payload(
    *,
    status_path: Path,
    retention_path: Path,
    observe_path: Path,
    health_path: Path | None,
    chat_providers_path: Path | None,
    local_ci_path: Path | None,
    captain_audit_path: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status_payload = _unwrap_mcp_text(_read_json(status_path))
    checks.extend(_check_status_snapshot(status_payload, status_path))
    checks.append(_check_retention(_read_json(retention_path), retention_path))
    checks.append(_check_observe_policy(_read_json(observe_path), observe_path))
    if health_path is not None:
        checks.append(_check_moussey_health(_read_json(health_path), health_path))
    if chat_providers_path is not None:
        checks.append(_check_chat_providers(_read_json(chat_providers_path), chat_providers_path))
    if local_ci_path is not None:
        checks.append(_check_moussey_local_ci(_read_json(local_ci_path), local_ci_path))
    if captain_audit_path is not None:
        checks.append(_check_captain_audit(_read_json(captain_audit_path), captain_audit_path))

    status = _worst_status(checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SCRIPT_NAME,
        "mode": "read_only_verified_alive",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "summary": f"{status}: {sum(1 for check in checks if check['status'] == 'ready')} ready, "
        f"{sum(1 for check in checks if check['status'] == 'warning')} warning, "
        f"{sum(1 for check in checks if check['status'] == 'blocked')} blocked",
        "inputs": {
            "status": str(status_path),
            "retention": str(retention_path),
            "observe": str(observe_path),
            "health": str(health_path) if health_path is not None else None,
            "chat_providers": str(chat_providers_path) if chat_providers_path is not None else None,
            "local_ci": str(local_ci_path) if local_ci_path is not None else None,
            "captain_audit": str(captain_audit_path) if captain_audit_path is not None else None,
        },
        "checks": checks,
        "non_claims": [
            "This rollup did not execute local-CI lanes.",
            "This rollup did not install or bootstrap a LaunchAgent.",
            "This rollup did not delete files.",
            "This rollup did not write drift records.",
            "This rollup did not dispatch workers.",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# FirstBite Verified-Alive Rollup - {payload['generated_at']}",
        "",
        f"Status: `{payload['status']}`",
        "",
        payload["summary"],
        "",
        "## Inputs",
        "",
    ]
    for key, value in payload["inputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    for check in payload["checks"]:
        lines.append(f"- `{check['id']}`: `{check['status']}` - {check['summary']}")
        if check.get("id") == "moussey_local_ci_endpoint" and isinstance(check.get("facts"), dict):
            facts = check["facts"]
            mcp_claim = facts.get("mcp_claim_status")
            mcp_status = facts.get("mcp_status")
            mcp_effective_ready = facts.get("mcp_effective_ready")
            if mcp_claim or mcp_status:
                lines.append(
                    "  - Loaded MCP client claim: "
                    f"`{mcp_claim or 'unknown'}` / `{mcp_status or 'unknown'}` "
                    f"(effective_ready=`{mcp_effective_ready}`)"
                )
            refresh_run = facts.get("mcp_refresh_run_id")
            refresh_verdict = facts.get("mcp_refresh_verdict")
            if refresh_run or refresh_verdict:
                lines.append(
                    f"  - MCP refresh: `{refresh_run or 'unknown'}` -> `{refresh_verdict or 'unknown'}`"
                )
            report_path = facts.get("mcp_refresh_report_path")
            if report_path:
                lines.append(f"  - MCP refresh report: `{report_path}`")
            stale_count = facts.get("mcp_refresh_stale_process_count")
            process_count = facts.get("mcp_refresh_process_count")
            if stale_count is not None and process_count is not None:
                effective_stale_count = facts.get("mcp_effective_stale_process_count")
                if facts.get("mcp_effective_ready") is True and effective_stale_count is not None:
                    lines.append(
                        "  - Loaded MCP processes effective stale: "
                        f"`{effective_stale_count}/{process_count}` "
                        f"(historical refresh `{stale_count}/{process_count}`)"
                    )
                else:
                    lines.append(f"  - Loaded MCP processes stale: `{stale_count}/{process_count}`")
            safety_ok = facts.get("mcp_refresh_safety_ok")
            if safety_ok is not None:
                lines.append(f"  - MCP refresh safety ok: `{safety_ok}`")
            approval_status = facts.get("operator_approval_status")
            if approval_status:
                lines.append(
                    "  - Operator approval: "
                    f"`{approval_status}` / `{facts.get('operator_approval_gate_status') or 'unknown'}`"
                )
            approval_packet = facts.get("operator_approval_packet_path")
            if approval_packet:
                lines.append(f"  - Operator approval packet: `{approval_packet}`")
            if approval_status:
                lines.append(
                    "  - Operator approval guardrails: "
                    f"candidate_ready=`{facts.get('operator_approval_candidate_ready')}`, "
                    f"source_ref_ready=`{facts.get('operator_approval_source_ref_ready')}`, "
                    "canonical_tracker_complete="
                    f"`{facts.get('operator_approval_canonical_tracker_complete')}`, "
                    f"tracker_files_copied=`{facts.get('operator_approval_tracker_files_copied')}`, "
                    "local_ci_lanes_executed="
                    f"`{facts.get('operator_approval_local_ci_lanes_executed')}`, "
                    f"readonly=`{facts.get('operator_approval_readonly')}`"
                )
        if check.get("id") == "captain_setup_health" and isinstance(check.get("facts"), dict):
            facts = check["facts"]
            lines.append(f"  - Captain audit exit code: `{facts.get('exit_code')}`")
            git_sync = facts.get("git_sync_status")
            if git_sync:
                lines.append(f"  - Captain git sync status: `{git_sync}`")
            setup_count = facts.get("setup_policy_warning_count")
            frontmatter_count = facts.get("frontmatter_warning_count")
            lines.append(
                f"  - Captain warnings: `{setup_count}` setup-policy, `{frontmatter_count}` frontmatter"
            )
    lines.extend(["", "## Non-Claims", ""])
    for item in payload["non_claims"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only FirstBite verified-alive rollup.")
    parser.add_argument("--status", type=Path, help="FirstBite status JSON path.")
    parser.add_argument("--retention", type=Path, help="Retention review report JSON path.")
    parser.add_argument("--observe", type=Path, help="M22 observe-policy JSON path.")
    parser.add_argument("--health", type=Path, default=None, help="Optional Moussey /api/health JSON path.")
    parser.add_argument(
        "--chat-providers",
        type=Path,
        default=None,
        help="Optional Moussey /api/chat/providers JSON path.",
    )
    parser.add_argument(
        "--local-ci",
        type=Path,
        default=None,
        help="Optional Moussey /api/coding/local-ci JSON path.",
    )
    parser.add_argument(
        "--captain-audit",
        type=Path,
        default=None,
        help="Optional Captain audit captured JSON path.",
    )
    parser.add_argument(
        "--refresh-dir",
        type=Path,
        default=None,
        help="Refresh read-only evidence snapshots into this directory before building the rollup.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Filename prefix for --refresh-dir outputs. Defaults to the current UTC date.",
    )
    parser.add_argument(
        "--firstbite-mcp-dir",
        type=Path,
        default=DEFAULT_FIRSTBITE_MCP_DIR,
        help="FirstBite local-CI MCP directory used by --refresh-dir.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help="PLAN.md path used by the observe-policy refresh.",
    )
    parser.add_argument(
        "--moussey-base-url",
        default=DEFAULT_MOUSSEY_BASE_URL,
        help="Moussey base URL used by --refresh-dir.",
    )
    parser.add_argument(
        "--write-json",
        type=Path,
        default=None,
        help="Optional path to write the rollup JSON payload.",
    )
    parser.add_argument(
        "--write-markdown",
        type=Path,
        default=None,
        help="Optional path to write the rollup markdown payload.",
    )
    parser.add_argument("--markdown", action="store_true", help="Emit markdown instead of JSON.")
    args = parser.parse_args(argv)
    if args.refresh_dir is None and (args.status is None or args.retention is None or args.observe is None):
        parser.error("--status, --retention, and --observe are required unless --refresh-dir is used")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.refresh_dir is not None:
            refreshed = refresh_evidence(
                evidence_dir=args.refresh_dir,
                prefix=args.prefix or _default_prefix(),
                retention_path=args.retention,
                firstbite_mcp_dir=args.firstbite_mcp_dir,
                plan_path=args.plan,
                moussey_base_url=args.moussey_base_url,
            )
            args.status = refreshed["status"]
            args.retention = refreshed["retention"]
            args.observe = refreshed["observe"]
            args.health = refreshed["health"]
            args.chat_providers = refreshed["chat_providers"]
            args.local_ci = refreshed["local_ci"]
            args.captain_audit = refreshed["captain_audit"]

        payload = build_payload(
            status_path=args.status,
            retention_path=args.retention,
            observe_path=args.observe,
            health_path=args.health,
            chat_providers_path=args.chat_providers,
            local_ci_path=args.local_ci,
            captain_audit_path=args.captain_audit,
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{SCRIPT_NAME}: {exc}\n")
        return 2
    if args.write_json is not None:
        _write_json(args.write_json, payload)
    if args.write_markdown is not None:
        args.write_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.write_markdown.write_text(_markdown(payload), encoding="utf-8")
    if args.markdown:
        print(_markdown(payload), end="")
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
