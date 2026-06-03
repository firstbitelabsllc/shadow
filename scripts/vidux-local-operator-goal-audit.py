#!/usr/bin/env python3
"""Audit the Moussey + Vidux local operator stack goal against current evidence.

This is a read-only completion audit. It does not try to make the goal look
done; it names what current disk evidence proves, what remains partial, and
which gates are operator/credential/hardware/follow-up gates.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SCRIPT_NAME = "vidux-local-operator-goal-audit.py"
DEFAULT_FIRSTBITE_PLAN = Path("projects/firstbite-local-ci-mega/PLAN.md")
DEFAULT_DEFERRALS_GLOB = "projects/firstbite-local-ci-mega/evidence/*m24-honest-deferrals-firewall.json"
DEFAULT_SNOWCUBES_CLEAN_SOURCE_GLOB = (
    "projects/firstbite-local-ci-mega/evidence/*snowcubes-clean-source-candidate.md"
)
DEFAULT_SNOWCUBES_APPROVAL_PACKET_GLOB = (
    "projects/firstbite-local-ci-mega/evidence/*snowcubes-readiness-approval-packet.json"
)
DEFAULT_NONPASS_DIAGNOSIS_GLOBS = (
    "projects/firstbite-local-ci-mega/evidence/*current-nonpass-diagnosis.json",
    "projects/firstbite-local-ci-mega/evidence/*nonpass-diagnosis-coverage.json",
)
DEFAULT_VERIFIED_ALIVE_GLOB = (
    "/Users/leokwan/.agent-ledger/vidux-firstbite-verified-alive-runner/*/report.json"
)
DEFAULT_MOUSSEY_REPO = Path("/Users/leokwan/Development/moussey")
DEFAULT_MOUSSEY_BASE_URL = "http://127.0.0.1:4321"
DEFAULT_LITTY_REPO = Path("/Users/leokwan/Development/litty")
DEFAULT_LITTY_BASE_URL = "http://127.0.0.1:4400"
DEFAULT_SNOWCUBES_CANONICAL_TRACKER = Path(
    "/Users/leokwan/Development/trysnowcubes-web-consign/outputs/consignment-tracker"
)
DEFAULT_SNOWCUBES_TRACKER_SEARCH_ROOT = Path("/Users/leokwan/Development")
SNOWCUBES_TRACKER_FILES = [
    "snowcubes-consignment-partners.csv",
    "snowcubes-consignment-live-ledger.csv",
]
MOUSSEY_LOCAL_CI_CURRENT_SOURCE_FILES = [
    ".firstbite/local-ci.json",
    "package.json",
    "app/api/snowcubes/shopify-invoice/route.ts",
    "app/api/snowcubes/shopify-invoice/route.test.ts",
    "scripts/snowcubes-invoice-readiness.ts",
    "scripts/snowcubes-invoice-e2e-bundle.ts",
]
MOUSSEY_LOCAL_CI_ADJACENT_FILES = [
    "package-lock.json",
]
MOUSSEY_SNOWCUBES_PACKAGE_SCRIPT = "test:snowcubes:invoice:e2e-bundle"
MOUSSEY_SNOWCUBES_PACKAGE_RELATED_PREFIXES = (
    "test:snowcubes:",
)
SNOWCUBES_CANDIDATE_EXPECTED_FILES = {
    ".firstbite/local-ci.json",
    "package.json",
    "app/api/snowcubes/shopify-invoice/route.ts",
    "app/api/snowcubes/shopify-invoice/route.test.ts",
    "scripts/snowcubes-invoice-readiness.ts",
    "scripts/snowcubes-invoice-e2e-bundle.ts",
}
SNOWCUBES_CANDIDATE_FORBIDDEN_FILES = {"package-lock.json"}
MOUSSEY_DEFERRED_PERF_UI_EVIDENCE = [
    {
        "id": "household_post_rip_ui",
        "path_kind": "moussey",
        "path": "evidence/2026-05-17-household-rip-proof/README.md",
        "note": "post-rip household UI visual and behavioral proof",
    },
    {
        "id": "household_mobile_screenshot",
        "path_kind": "moussey",
        "path": "evidence/2026-05-17-household-rip-proof/11-mobile-final-touch-targets.png",
        "note": "mobile household touch target screenshot",
    },
    {
        "id": "household_calendar_screenshot",
        "path_kind": "moussey",
        "path": "evidence/2026-05-17-household-rip-proof/15-calendar-mobile-390x844.png",
        "note": "mobile household calendar screenshot",
    },
    {
        "id": "react_perf_closeout",
        "path_kind": "vidux",
        "path": "projects/agentic-coding-workbench/evidence/2026-05-31-c99-moussey-react-perf-finalize.md",
        "note": "deferred React perf and submit-guard closeout",
    },
    {
        "id": "react_perf_chat_mobile",
        "path_kind": "vidux",
        "path": "projects/agentic-coding-workbench/evidence/2026-05-31-c99-chat-mobile.png",
        "note": "C99 chat mobile browser proof",
    },
    {
        "id": "react_perf_coding_mobile",
        "path_kind": "vidux",
        "path": "projects/agentic-coding-workbench/evidence/2026-05-31-c99-coding-hydrated-mobile.png",
        "note": "C99 coding mobile browser proof",
    },
    {
        "id": "voice_first_paint_perf",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-01-ux8-ux12-voice-first-paint-perf.md",
        "note": "voice first-paint and first-load perf proof",
    },
    {
        "id": "voice_first_paint_mobile",
        "path_kind": "moussey",
        "path": "evidence/2026-06-01-voice-first-paint-mobile.png",
        "note": "voice first-paint mobile screenshot",
    },
    {
        "id": "consignment_degraded_ui",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-01-c3-consignment-bookmark-reconciliation.md",
        "note": "consignment degraded-state browser proof",
    },
    {
        "id": "consignment_mobile_fixed",
        "path_kind": "moussey",
        "path": "evidence/2026-06-01-consignment-studio-mobile-fixed.png",
        "note": "Studio consignment mobile degraded-state screenshot",
    },
    {
        "id": "pwa_metadata",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-01-c7-pwa-metadata-icon-viewport.md",
        "note": "PWA metadata, icon, and viewport proof",
    },
    {
        "id": "chat_passcode_mobile",
        "path_kind": "moussey",
        "path": "evidence/2026-06-01-chat-passcode-flow-mobile.png",
        "note": "chat mobile passcode recovery screenshot",
    },
]
MOUSSEY_DEFERRED_PERF_UI_ROUTES = [
    "/household",
    "/household/calendar",
    "/chat",
    "/voice",
    "/consignment",
    "/coding?fresh=goal-audit",
]
MOUSSEY_CHAT_FRONT_DOOR_EVIDENCE = [
    {
        "id": "chat_front_door_routing_packet",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-02-moussey-chat-front-door-routing.md",
        "note": "current-source chat routing, target picker, tool chips, and virtualized transcript proof",
    },
    {
        "id": "chat_front_door_desktop",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-02-moussey-chat-front-door-desktop.png",
        "note": "desktop chat front-door browser proof",
    },
    {
        "id": "chat_front_door_mobile",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-02-moussey-chat-front-door-mobile.png",
        "note": "mobile chat front-door browser proof",
    },
    {
        "id": "chat_routes_sheet_mobile",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-02-moussey-chat-routes-sheet-mobile.png",
        "note": "mobile Routes sheet interaction proof",
    },
    {
        "id": "chat_target_picker_mobile",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-02-moussey-chat-target-drawer-mobile.png",
        "note": "mobile Target picker sheet proof with Self and auto-router visible",
    },
    {
        "id": "chat_passcode_mobile",
        "path_kind": "moussey",
        "path": "evidence/2026-06-01-chat-passcode-flow-mobile.png",
        "note": "mobile chat passcode recovery proof",
    },
    {
        "id": "chat_passcode_desktop",
        "path_kind": "moussey",
        "path": "evidence/2026-06-01-chat-passcode-flow-desktop.png",
        "note": "desktop chat passcode recovery proof",
    },
    {
        "id": "chat_source_modality_slack",
        "path_kind": "moussey",
        "path": "evidence/2026-06-01-chat-source-modality-slack-readonly.png",
        "note": "chat sourceModality Slack read-only proof",
    },
    {
        "id": "current_chat_auth_port",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-01-current-chat-auth-port.md",
        "note": "current-source chat auth/passcode port evidence",
    },
    {
        "id": "source_modality_audit_propagation",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-01-c25-source-modality-audit-propagation.md",
        "note": "sourceModality propagation through chat, LAN trigger, SSE, and audit rows",
    },
    {
        "id": "safe_error_envelope",
        "path_kind": "vidux",
        "path": "projects/connect-the-fleet/evidence/2026-06-01-c19-safe-error-envelope-hardening.md",
        "note": "safe chat/voice error envelope proof",
    },
    {
        "id": "chat_providers_refresh",
        "path_kind": "vidux",
        "path": "projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-chat-providers.json",
        "note": "M23 refreshed chat provider readiness packet",
    },
    {
        "id": "chat_front_door_live_smoke",
        "path_kind": "vidux",
        "path": "projects/firstbite-local-ci-mega/evidence/2026-06-01-chat-front-door-live-smoke.md",
        "note": "live local /api/chat/ask smoke through the chat front door",
    },
]
MOUSSEY_CHAT_FRONT_DOOR_ROUTES = ["/chat", "/api/chat/providers"]
LITTY_COCKPIT_BOUNDARY_EVIDENCE = [
    {
        "id": "litty_agents_boundary",
        "path_kind": "litty",
        "path": "AGENTS.md",
        "note": "repo instructions define Litty as standalone cockpit and Moussey as LAN/data hub",
    },
    {
        "id": "litty_cloneable_plan",
        "path_kind": "litty",
        "path": "PLAN.md",
        "note": "cloneable Litty resume plan",
    },
    {
        "id": "litty_vidux_plan",
        "path_kind": "vidux",
        "path": "projects/litty/PLAN.md",
        "note": "canonical Vidux Litty plan with C225/C226 source and driver truth",
    },
    {
        "id": "c215_handoff",
        "path_kind": "vidux",
        "path": "projects/litty/evidence/2026-05-28-c215-claude-local-agent-handoff.md",
        "note": "durable Claude/Codex handoff and read order",
    },
    {
        "id": "c220a_honest_dispatch",
        "path_kind": "vidux",
        "path": "projects/litty/evidence/2026-05-28-c220a-honest-lane-dispatch.md",
        "note": "honest lane dispatch proof; no old Moussey coding UI revival",
    },
    {
        "id": "c220b_c222_composer_help",
        "path_kind": "vidux",
        "path": "projects/litty/evidence/2026-05-28-c220b-c222-composer-and-help.md",
        "note": "handoffs/new composer and in-app runbook proof",
    },
    {
        "id": "local_coding_runbook",
        "path_kind": "litty",
        "path": "docs/local-coding-runbook.md",
        "note": "operator-facing local coding runbook",
    },
    {
        "id": "c226_goose_driver_trust",
        "path_kind": "vidux",
        "path": "projects/litty/evidence/2026-06-01-c226-goose-local-driver-trust-summary.md",
        "note": "Goose local read+edit driver trust summary",
    },
    {
        "id": "litty_clean_branch_green",
        "path_kind": "vidux",
        "path": "projects/litty/evidence/2026-06-01-litty-live-moussey-minimal-clean-green.md",
        "note": "clean-branch Litty three-lane FirstBite proof and open PR boundary",
    },
]
LITTY_COCKPIT_BOUNDARY_ROUTES = [
    "/",
    "/workers",
    "/handoffs/new",
    "/help",
    "/api/contracts?view=claude-mega-goal",
]
RESUME_PRIORITY = [
    "local_ci_current_machine",
    "moussey_deferred_perf_ui",
    "chat_operator_front_door",
    "litty_cockpit_boundaries",
    "proof_discipline",
    "remaining_work_classified",
    "mobile_operator_rows",
    "captain_setup_health",
]


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


def _latest_file(pattern: str, *, root: Path | None = None) -> Path | None:
    base = root or Path("/")
    search_pattern = pattern if root is not None else pattern.removeprefix("/")
    matches = sorted(base.glob(search_pattern), key=lambda path: path.stat().st_mtime)
    return matches[-1] if matches else None


def _latest_file_any(patterns: tuple[str, ...], *, root: Path | None = None) -> Path | None:
    base = root or Path("/")
    matches: list[Path] = []
    for pattern in patterns:
        search_pattern = pattern if root is not None else pattern.removeprefix("/")
        matches.extend(base.glob(search_pattern))
    unique_matches = sorted(set(matches), key=lambda path: path.stat().st_mtime)
    return unique_matches[-1] if unique_matches else None


def _nonpass_diagnosis(repo_root: Path) -> dict[str, Any]:
    path = _latest_file_any(DEFAULT_NONPASS_DIAGNOSIS_GLOBS, root=repo_root)
    if path is None:
        return {
            "exists": False,
            "path": None,
            "summary": "No current non-pass diagnosis packet found.",
            "groups": [],
        }

    payload = _read_json(path)
    next_resume = payload.get("next_resume") if isinstance(payload.get("next_resume"), dict) else {}
    groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
    compact_groups = [
        {
            "category": group.get("category"),
            "summary": group.get("summary"),
            "confidence": group.get("confidence"),
            "lanes": group.get("lanes") if isinstance(group.get("lanes"), list) else [],
            "source_refs": group.get("source_refs") if isinstance(group.get("source_refs"), list) else [],
            "rerun_gate": group.get("rerun_gate"),
        }
        for group in groups
        if isinstance(group, dict)
    ]
    return {
        "exists": True,
        "path": str(path),
        "mode": payload.get("mode"),
        "failed_lane_count": payload.get("failed_lane_count"),
        "visible_failed_lane_count": payload.get("visible_failed_lane_count"),
        "aggregate_nonpass_lane_count": payload.get("aggregate_nonpass_lane_count"),
        "undocumented_nonpass_lane_count": payload.get("undocumented_nonpass_lane_count"),
        "diagnosis_coverage_status": payload.get("diagnosis_coverage_status"),
        "group_count": payload.get("group_count"),
        "local_ci_lanes_executed": next_resume.get("local_ci_lanes_executed"),
        "dispatch_allowed": next_resume.get("dispatch_allowed"),
        "rerun_gate": next_resume.get("rerun_gate"),
        "summary": next_resume.get("summary"),
        "groups": compact_groups,
    }


def _checks_by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rollup = report.get("rollup") if isinstance(report.get("rollup"), dict) else {}
    checks = rollup.get("checks") if isinstance(rollup.get("checks"), list) else []
    return {
        str(check.get("id")): check
        for check in checks
        if isinstance(check, dict) and check.get("id")
    }


def _line_refs(plan_path: Path, patterns: list[str]) -> list[dict[str, Any]]:
    if not plan_path.exists():
        return []
    refs: list[dict[str, Any]] = []
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    for pattern in patterns:
        for index, line in enumerate(lines, start=1):
            if pattern in line:
                refs.append({"path": str(plan_path), "line": index, "pattern": pattern})
                break
    return refs


def _criterion(
    *,
    id: str,
    label: str,
    status: str,
    summary: str,
    evidence: list[dict[str, Any]] | None = None,
    blockers: list[str] | None = None,
    next_resume: list[str] | None = None,
    resume_class: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "status": status,
        "summary": summary,
        "evidence": evidence or [],
        "blockers": blockers or [],
        "next_resume": next_resume or [],
        "resume_class": resume_class,
    }


def _evidence_path(path: Path | None, note: str) -> dict[str, Any]:
    return {
        "type": "path",
        "path": str(path) if path is not None else None,
        "exists": bool(path and path.exists()),
        "note": note,
    }


def _required_evidence_item(
    *,
    repo_root: Path,
    moussey_repo_path: Path,
    spec: dict[str, str],
) -> dict[str, Any]:
    base = moussey_repo_path if spec["path_kind"] == "moussey" else repo_root
    path = base / spec["path"]
    return {
        "id": spec["id"],
        "type": "path",
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "note": spec["note"],
    }


def _required_litty_evidence_item(
    *,
    repo_root: Path,
    litty_repo_path: Path,
    spec: dict[str, str],
) -> dict[str, Any]:
    base = litty_repo_path if spec["path_kind"] == "litty" else repo_root
    path = base / spec["path"]
    return {
        "id": spec["id"],
        "type": "path",
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "note": spec["note"],
    }


def _probe_local_route(
    base_url: str,
    route: str,
    *,
    timeout_seconds: float = 4.0,
    attempts: int = 1,
    retry_delay_seconds: float = 0.25,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{route}"
    max_attempts = max(1, attempts)
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"user-agent": "vidux-local-operator-goal-audit"})
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(1_000_000)
                return {
                    "route": route,
                    "url": url,
                    "ok": 200 <= response.status < 400,
                    "status": response.status,
                    "bytes": len(body),
                    "error": None,
                    "attempts": attempt,
                    "errors": errors,
                }
        except urllib.error.HTTPError as exc:
            return {
                "route": route,
                "url": url,
                "ok": False,
                "status": exc.code,
                "bytes": 0,
                "error": str(exc),
                "attempts": attempt,
                "errors": [*errors, str(exc)],
            }
        except (OSError, urllib.error.URLError) as exc:
            errors.append(str(exc))
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            return {
                "route": route,
                "url": url,
                "ok": False,
                "status": None,
                "bytes": 0,
                "error": str(exc),
                "attempts": attempt,
                "errors": errors,
            }
    raise AssertionError("unreachable local route probe loop")


def _read_local_json(base_url: str, route: str, *, timeout_seconds: float = 4.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{route}"
    try:
        request = urllib.request.Request(url, headers={"user-agent": "vidux-local-operator-goal-audit"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(1_000_000)
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return {
                    "route": route,
                    "url": url,
                    "ok": False,
                    "status": response.status,
                    "bytes": len(body),
                    "payload": None,
                    "error": f"invalid JSON response: {exc}",
                }
            return {
                "route": route,
                "url": url,
                "ok": 200 <= response.status < 400 and isinstance(payload, dict),
                "status": response.status,
                "bytes": len(body),
                "payload": payload if isinstance(payload, dict) else None,
                "error": None if isinstance(payload, dict) else "JSON response was not an object",
            }
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        status = exc.code if isinstance(exc, urllib.error.HTTPError) else None
        return {
            "route": route,
            "url": url,
            "ok": False,
            "status": status,
            "bytes": 0,
            "payload": None,
            "error": str(exc),
        }


def _moussey_deferred_perf_ui_audit(
    *,
    repo_root: Path,
    moussey_repo_path: Path | None,
    moussey_base_url: str,
) -> dict[str, Any]:
    repo_path = moussey_repo_path or DEFAULT_MOUSSEY_REPO
    evidence = [
        _required_evidence_item(repo_root=repo_root, moussey_repo_path=repo_path, spec=spec)
        for spec in MOUSSEY_DEFERRED_PERF_UI_EVIDENCE
    ]
    route_probes = [
        _probe_local_route(moussey_base_url, route)
        for route in MOUSSEY_DEFERRED_PERF_UI_ROUTES
    ]
    missing_evidence = [item for item in evidence if not item["exists"]]
    failed_routes = [item for item in route_probes if not item["ok"]]
    ready = not missing_evidence and not failed_routes
    blockers: list[str] = []
    if missing_evidence:
        blockers.append(f"{len(missing_evidence)} required Moussey perf/UI evidence artifact(s) are missing.")
    if failed_routes:
        blockers.append(f"{len(failed_routes)} live Moussey route probe(s) failed or did not return 2xx/3xx.")
    return {
        "status": "ready" if ready else "partial",
        "summary": (
            "Moussey deferred perf/UI closeout is evidence-backed: household, C99 React perf, chat, voice, consignment, PWA metadata, and live route probes are present."
            if ready
            else "Moussey deferred perf/UI closeout has partial evidence; inspect missing artifacts or route probes before claiming done."
        ),
        "evidence": evidence,
        "route_probes": route_probes,
        "missing_evidence": missing_evidence,
        "failed_routes": failed_routes,
        "blockers": blockers,
        "non_claims": [
            "This audit does not claim mobile DERP/LTE tailnet proof.",
            "This audit does not claim real iPhone Add-to-Home-Screen proof.",
            "This audit does not reopen Moussey /coding product UI polish; Litty remains the standalone cockpit.",
            "This audit does not prove Snowcubes tracker data exists on Studio.",
        ],
    }


def _provider_summary(provider_payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = provider_payload or {}
    providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
    provider_states: dict[str, dict[str, Any]] = {}
    for name in ["local", "local-mlx", "codex", "claude"]:
        state = providers.get(name) if isinstance(providers.get(name), dict) else {}
        provider_states[name] = {
            "ready": state.get("ready") is True,
            "message": state.get("message"),
        }
    claude_message = str(provider_states["claude"].get("message") or "")
    return {
        "default_provider": payload.get("defaultProvider"),
        "providers": provider_states,
        "local_ready": provider_states["local"]["ready"],
        "local_mlx_ready": provider_states["local-mlx"]["ready"],
        "codex_ready": provider_states["codex"]["ready"],
        "claude_ready": provider_states["claude"]["ready"],
        "claude_auth_gated": (
            not provider_states["claude"]["ready"]
            and "auth" in claude_message.lower()
        ),
    }


def _moussey_chat_front_door_audit(
    *,
    repo_root: Path,
    moussey_repo_path: Path | None,
    moussey_base_url: str,
) -> dict[str, Any]:
    repo_path = moussey_repo_path or DEFAULT_MOUSSEY_REPO
    evidence = [
        _required_evidence_item(repo_root=repo_root, moussey_repo_path=repo_path, spec=spec)
        for spec in MOUSSEY_CHAT_FRONT_DOOR_EVIDENCE
    ]
    route_probes = [
        _probe_local_route(moussey_base_url, route)
        for route in MOUSSEY_CHAT_FRONT_DOOR_ROUTES
    ]
    provider_probe = _read_local_json(moussey_base_url, "/api/chat/providers")
    providers = _provider_summary(provider_probe.get("payload") if provider_probe["ok"] else None)
    missing_evidence = [item for item in evidence if not item["exists"]]
    failed_routes = [item for item in route_probes if not item["ok"]]
    blockers: list[str] = []
    credential_gates: list[str] = []
    operator_gates: list[str] = [
        "Real live MOUSSEY_CHAT_AUTH=enforce flip and Leo/Nicole phone passcode setup remain operator-gated.",
    ]
    if missing_evidence:
        blockers.append(f"{len(missing_evidence)} required chat/front-door evidence artifact(s) are missing.")
    if failed_routes:
        blockers.append(f"{len(failed_routes)} live chat/front-door route probe(s) failed or did not return 2xx/3xx.")
    if not provider_probe["ok"]:
        blockers.append("Live /api/chat/providers did not return a usable JSON provider packet.")
    if not providers["local_ready"]:
        blockers.append("Default local provider is not ready.")
    if not providers["codex_ready"]:
        blockers.append("Codex provider is not ready.")
    if providers["claude_auth_gated"]:
        credential_gates.append("Claude escalation is credential-gated on this Mac; sign in with `claude` before claiming all-provider routing.")
    elif not providers["claude_ready"]:
        blockers.append("Claude escalation provider is not ready for a non-auth reason.")

    local_front_door_ready = (
        not missing_evidence
        and not failed_routes
        and provider_probe["ok"]
        and providers["local_ready"]
        and providers["codex_ready"]
    )
    all_missing = (
        len(missing_evidence) == len(evidence)
        and len(failed_routes) == len(route_probes)
        and not provider_probe["ok"]
    )
    if all_missing:
        status = "missing"
        summary = "No usable Moussey chat/front-door evidence, route probes, or provider packet was found."
    elif local_front_door_ready and providers["claude_ready"]:
        status = "ready"
        summary = "Moussey chat front door is live and evidence-backed across local, Codex, and Claude providers."
    elif local_front_door_ready and credential_gates:
        status = "gated"
        summary = "Moussey chat front door is live for local/Codex operator use; Claude escalation remains credential-gated."
    else:
        status = "partial"
        summary = "Moussey chat front door has partial proof; inspect missing evidence, route probes, or provider readiness before claiming trust."

    return {
        "status": status,
        "summary": summary,
        "evidence": evidence,
        "route_probes": route_probes,
        "provider_probe": provider_probe,
        "providers": providers,
        "missing_evidence": missing_evidence,
        "failed_routes": failed_routes,
        "blockers": blockers,
        "credential_gates": credential_gates,
        "operator_gates": operator_gates,
        "non_claims": [
            "This audit does not sign in Claude or claim Claude escalation is usable.",
            "This audit does not flip MOUSSEY_CHAT_AUTH=enforce in the live LaunchAgent/server environment.",
            "This audit does not set, read, print, or rotate Leo's real chat passcode.",
            "This audit does not prove Nicole/iPhone behavior after an enforce flip.",
        ],
    }


def _text_contains(path: Path, patterns: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "matches": {}, "all_present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = {pattern: pattern in text for pattern in patterns}
    return {
        "path": str(path),
        "exists": True,
        "matches": matches,
        "all_present": all(matches.values()),
    }


def _litty_cockpit_boundaries_audit(
    *,
    repo_root: Path,
    litty_repo_path: Path | None,
    litty_base_url: str,
) -> dict[str, Any]:
    repo_path = litty_repo_path or DEFAULT_LITTY_REPO
    evidence = [
        _required_litty_evidence_item(repo_root=repo_root, litty_repo_path=repo_path, spec=spec)
        for spec in LITTY_COCKPIT_BOUNDARY_EVIDENCE
    ]
    route_probes = [
        _probe_local_route(litty_base_url, route, timeout_seconds=8.0, attempts=3)
        for route in LITTY_COCKPIT_BOUNDARY_ROUTES
    ]
    contract_probe = _read_local_json(litty_base_url, "/api/contracts?view=claude-mega-goal")
    vidux_plan = repo_root / "projects/litty/PLAN.md"
    agents = repo_path / "AGENTS.md"
    boundary_text_checks = {
        "agents": _text_contains(
            agents,
            [
                "Litty is the standalone cockpit",
                "Moussey stays the LAN/data hub",
                "Do not port or copy Moussey's old",
            ],
        ),
        "vidux_plan": _text_contains(
            vidux_plan,
            [
                "Litty extracts the cockpit logic",
                "Moussey stays as the LAN routing/data hub",
                "C225 publish step completed",
                "C226 Goose local-driver trust summary completed",
            ],
        ),
    }
    missing_evidence = [item for item in evidence if not item["exists"]]
    failed_routes = [item for item in route_probes if not item["ok"]]
    contract_payload = contract_probe.get("payload") if contract_probe["ok"] else {}
    contract_ok = isinstance(contract_payload, dict) and contract_payload.get("ok") is True
    missing_text_checks = [
        name for name, check in boundary_text_checks.items() if not check["all_present"]
    ]

    blockers: list[str] = []
    source_gates = [
        "C225 clean Litty three-lane proof is green on branch ab44223..., but PR #1/open source promotion is not proven landed on origin/main.",
    ]
    operator_gates = [
        "Primary :4400 production/LaunchAgent handoff remains operator-gated; do not restart or replace the live owner process without explicit approval.",
    ]
    if missing_evidence:
        blockers.append(f"{len(missing_evidence)} required Litty boundary evidence artifact(s) are missing.")
    if failed_routes:
        blockers.append(f"{len(failed_routes)} live Litty route probe(s) failed or did not return 2xx/3xx.")
    if not contract_ok:
        blockers.append("Live Litty Claude mega-goal contract did not return ok=true JSON.")
    if missing_text_checks:
        blockers.append(f"Litty boundary text checks failed in: {', '.join(missing_text_checks)}.")

    boundary_ready = (
        not missing_evidence
        and not failed_routes
        and contract_ok
        and not missing_text_checks
    )
    if boundary_ready:
        status = "gated"
        summary = (
            "Litty/Moussey cockpit boundaries are durable and live: Litty is the standalone cockpit, "
            "Moussey remains the LAN/data hub, handoff/runbook/local-driver proof exists, and remaining work is source-promotion/runtime-handoff gated."
        )
    else:
        status = "partial"
        summary = "Litty/Moussey cockpit boundaries have partial proof; inspect missing evidence, text checks, contract, or live routes."

    return {
        "status": status,
        "summary": summary,
        "evidence": evidence,
        "route_probes": route_probes,
        "contract_probe": contract_probe,
        "contract_ok": contract_ok,
        "boundary_text_checks": boundary_text_checks,
        "missing_evidence": missing_evidence,
        "failed_routes": failed_routes,
        "blockers": blockers,
        "source_gates": source_gates if boundary_ready else [],
        "operator_gates": operator_gates if boundary_ready else [],
        "non_claims": [
            "This audit does not claim PR #1 is merged or origin/main is green for Litty's three lanes.",
            "This audit does not restart, replace, or install the primary Litty runtime or LaunchAgent.",
            "This audit does not revive or port the old Moussey /coding UI.",
            "This audit does not execute local-CI lanes.",
            "This audit does not dispatch handoffs, patch promotes, commits, pushes, or worker actions.",
        ],
    }


def _status_counts(criteria: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in criteria:
        status = str(item["status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def _compact_action(gate: dict[str, Any]) -> dict[str, Any]:
    action = gate.get("action") if isinstance(gate.get("action"), dict) else {}
    return {
        "label": action.get("label"),
        "run_on": action.get("runOn"),
        "safety": action.get("safety"),
    }


def _compact_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": gate.get("id"),
        "label": gate.get("label"),
        "status": gate.get("status"),
        "summary": gate.get("summary"),
        "action": _compact_action(gate),
    }


def _compact_failing_lane(lane: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo": lane.get("repo"),
        "lane": lane.get("lane"),
        "status": lane.get("status"),
        "rc": lane.get("rc"),
        "reason": lane.get("reason"),
        "report_path": lane.get("reportPath"),
        "log_path": lane.get("logPath"),
    }


def _run_git(repo_path: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    if not repo_path.exists():
        return None
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None


def _git_status_by_path(repo_path: Path, files: list[str]) -> dict[str, str]:
    result = _run_git(repo_path, ["status", "--short", "--", *files])
    if result is None or result.returncode != 0:
        return {}
    statuses: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        status = line[:2].strip() or "clean"
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1]
        statuses[path] = status
    return statuses


def _git_tracked_paths(repo_path: Path, files: list[str]) -> set[str]:
    result = _run_git(repo_path, ["ls-files", "--", *files])
    if result is None or result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _json_file_at_head(repo_path: Path, path: str) -> dict[str, Any]:
    result = _run_git(repo_path, ["show", f"HEAD:{path}"])
    if result is None or result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_markdown_bullet(markdown: str, label: str) -> str | None:
    pattern = re.compile(rf"^- {re.escape(label)}:\s+`([^`]+)`", re.MULTILINE)
    match = pattern.search(markdown)
    return match.group(1) if match else None


def _snowcubes_clean_source_candidate(repo_root: Path) -> dict[str, Any]:
    evidence_path = _latest_file(DEFAULT_SNOWCUBES_CLEAN_SOURCE_GLOB, root=repo_root)
    if evidence_path is None:
        return {
            "status": "missing",
            "evidence_path": None,
            "summary": "No Snowcubes clean-source candidate evidence file was found.",
        }

    markdown = evidence_path.read_text(encoding="utf-8")
    worktree_value = _extract_markdown_bullet(markdown, "Worktree")
    source_ref = _extract_markdown_bullet(markdown, "Source ref")
    branch = _extract_markdown_bullet(markdown, "Branch")
    base_ref = _extract_markdown_bullet(markdown, "Base")
    worktree_path = Path(worktree_value).expanduser() if worktree_value else None

    head = None
    status_short = None
    changed_files: list[str] = []
    git_available = False
    if worktree_path and worktree_path.exists():
        head_result = _run_git(worktree_path, ["rev-parse", "HEAD"])
        status_result = _run_git(worktree_path, ["status", "--short"])
        files_result = _run_git(worktree_path, ["diff", "--name-only", "HEAD^", "HEAD"])
        if head_result and head_result.returncode == 0:
            git_available = True
            head = head_result.stdout.strip()
        if status_result and status_result.returncode == 0:
            status_short = status_result.stdout.strip()
        if files_result and files_result.returncode == 0:
            changed_files = sorted(line.strip() for line in files_result.stdout.splitlines() if line.strip())

    changed_set = set(changed_files)
    expected_present = sorted(SNOWCUBES_CANDIDATE_EXPECTED_FILES & changed_set)
    missing_expected = sorted(SNOWCUBES_CANDIDATE_EXPECTED_FILES - changed_set)
    forbidden_present = sorted(SNOWCUBES_CANDIDATE_FORBIDDEN_FILES & changed_set)
    worktree_clean = status_short == ""
    commit_matches = bool(source_ref and head == source_ref)
    valid = (
        bool(evidence_path.exists())
        and bool(worktree_path and worktree_path.exists())
        and git_available
        and worktree_clean
        and commit_matches
        and not missing_expected
        and not forbidden_present
    )

    return {
        "status": "ready" if valid else "invalid",
        "evidence_path": str(evidence_path),
        "worktree": str(worktree_path) if worktree_path else None,
        "worktree_exists": bool(worktree_path and worktree_path.exists()),
        "worktree_clean": worktree_clean,
        "branch": branch,
        "source_ref": source_ref,
        "base_ref": base_ref,
        "head": head,
        "commit_matches_source_ref": commit_matches,
        "changed_files": changed_files,
        "expected_files_present": expected_present,
        "missing_expected_files": missing_expected,
        "forbidden_files_present": forbidden_present,
        "summary": (
            f"Clean Snowcubes source candidate is ready at {source_ref}; package-lock is excluded."
            if valid
            else "Snowcubes clean-source candidate evidence exists, but the worktree/source-ref validation is incomplete."
        ),
    }


def _file_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    try:
        line_count = path.read_bytes().count(b"\n")
    except OSError:
        line_count = None
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "line_count": line_count,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _git_context(path: Path) -> dict[str, Any]:
    top_level = _run_git(path, ["rev-parse", "--show-toplevel"])
    head = _run_git(path, ["rev-parse", "HEAD"])
    status = _run_git(path, ["status", "--short", "--branch"])
    return {
        "worktree_root": top_level.stdout.strip() if top_level and top_level.returncode == 0 else None,
        "head": head.stdout.strip() if head and head.returncode == 0 else None,
        "status_short_branch": status.stdout.strip().splitlines()[0]
        if status and status.returncode == 0 and status.stdout.strip()
        else None,
    }


def _tracker_candidate_score(candidate: dict[str, Any]) -> tuple[str, int, int]:
    files = candidate.get("files") if isinstance(candidate.get("files"), dict) else {}
    metadata = [item for item in files.values() if isinstance(item, dict)]
    latest_mtime = max((str(item.get("mtime") or "") for item in metadata), default="")
    total_size = sum(int(item.get("size_bytes") or 0) for item in metadata)
    total_lines = sum(int(item.get("line_count") or 0) for item in metadata)
    return latest_mtime, total_size, total_lines


def _tracker_candidate_recommendation(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    recommended = max(candidates, key=_tracker_candidate_score)
    latest_mtime, total_size, total_lines = _tracker_candidate_score(recommended)
    return {
        "path": recommended.get("path"),
        "git": recommended.get("git") if isinstance(recommended.get("git"), dict) else {},
        "latest_mtime": latest_mtime or None,
        "total_size_bytes": total_size,
        "total_line_count": total_lines,
        "ranking_basis": [
            "newest required-file mtime",
            "largest total required-file size",
            "largest total required-file line count",
        ],
        "restore_requires_explicit_approval": True,
        "local_ci_execute_requires_explicit_approval": True,
        "product_authority_unproven": True,
        "private_fields_redacted": True,
        "summary": (
            "Recommended default tracker restore/provide candidate by metadata only; "
            "product authority still requires operator approval."
        ),
    }


def _snowcubes_tracker_diagnosis(
    *,
    canonical_tracker: Path = DEFAULT_SNOWCUBES_CANONICAL_TRACKER,
    search_root: Path = DEFAULT_SNOWCUBES_TRACKER_SEARCH_ROOT,
) -> dict[str, Any]:
    canonical_files = {name: _file_metadata(canonical_tracker / name) for name in SNOWCUBES_TRACKER_FILES}
    canonical_complete = canonical_tracker.exists() and all(
        metadata["exists"] for metadata in canonical_files.values()
    )

    candidates: list[dict[str, Any]] = []
    if search_root.exists():
        for repo_like_root in sorted(search_root.glob("trysnowcubes-web*")):
            if not repo_like_root.is_dir():
                continue
            for tracker_dir in sorted(repo_like_root.glob("**/outputs/consignment-tracker")):
                if tracker_dir == canonical_tracker:
                    continue
                files = {name: _file_metadata(tracker_dir / name) for name in SNOWCUBES_TRACKER_FILES}
                complete = all(metadata["exists"] for metadata in files.values())
                if not complete:
                    continue
                candidates.append(
                    {
                        "path": str(tracker_dir),
                        "complete": True,
                        "files": files,
                        "git": _git_context(tracker_dir),
                    }
                )

    recommended_candidate = None if canonical_complete else _tracker_candidate_recommendation(candidates)

    if canonical_complete:
        status = "canonical_ready"
        summary = "Canonical Snowcubes tracker CSV inputs exist at the expected path."
    elif candidates:
        status = "candidate_data_present_off_canonical"
        summary = (
            f"Canonical tracker path is missing/incomplete, but {len(candidates)} off-canonical "
            "tracker candidate(s) contain both required CSV filenames."
        )
    else:
        status = "missing"
        summary = "Canonical tracker CSV inputs are missing and no off-canonical candidates were found."

    return {
        "status": status,
        "canonical_tracker": str(canonical_tracker),
        "canonical_tracker_exists": canonical_tracker.exists(),
        "canonical_complete": canonical_complete,
        "required_files": SNOWCUBES_TRACKER_FILES,
        "canonical_files": canonical_files,
        "off_canonical_candidates": candidates,
        "candidate_count": len(candidates),
        "recommended_candidate": recommended_candidate,
        "private_fields_redacted": True,
        "summary": summary,
    }


def _snowcubes_approval_packet(repo_root: Path) -> dict[str, Any]:
    path = _latest_file(DEFAULT_SNOWCUBES_APPROVAL_PACKET_GLOB, root=repo_root)
    if path is None:
        return {
            "exists": False,
            "path": None,
            "status": "missing",
            "summary": "No Snowcubes readiness approval packet was found.",
            "readonly": None,
            "tracker_files_copied": None,
            "local_ci_lanes_executed": None,
            "candidate_path": None,
            "candidate_ready": None,
            "source_ref": None,
            "source_ref_ready": None,
            "canonical_tracker_complete": None,
            "approval_gate_status": None,
        }

    try:
        payload = _read_json(path)
    except (OSError, ValueError) as exc:
        return {
            "exists": True,
            "path": str(path),
            "status": "invalid",
            "summary": f"Snowcubes readiness approval packet exists but could not be parsed: {exc}",
            "readonly": None,
            "tracker_files_copied": None,
            "local_ci_lanes_executed": None,
            "candidate_path": None,
            "candidate_ready": None,
            "source_ref": None,
            "source_ref_ready": None,
            "canonical_tracker_complete": None,
            "approval_gate_status": None,
        }

    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    source_ref = payload.get("source_ref") if isinstance(payload.get("source_ref"), dict) else {}
    canonical_tracker = (
        payload.get("canonical_tracker") if isinstance(payload.get("canonical_tracker"), dict) else {}
    )
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    approval_gate = next(
        (
            check
            for check in checks
            if isinstance(check, dict) and check.get("id") == "approval_gate"
        ),
        {},
    )
    status = str(payload.get("status") or "unknown")
    return {
        "exists": True,
        "path": str(path),
        "status": status,
        "summary": payload.get("summary")
        or (
            "Snowcubes readiness approval packet is ready for explicit operator approval."
            if status == "ready_for_approval"
            else "Snowcubes readiness approval packet exists."
        ),
        "readonly": payload.get("readonly") is True,
        "tracker_files_copied": payload.get("tracker_files_copied") is True,
        "local_ci_lanes_executed": payload.get("local_ci_lanes_executed") is True,
        "candidate_path": candidate.get("path"),
        "candidate_ready": candidate.get("ready") is True,
        "source_ref": source_ref.get("ref"),
        "source_ref_ready": source_ref.get("ready") is True,
        "canonical_tracker_complete": canonical_tracker.get("complete") is True,
        "approval_gate_status": payload.get("approval_gate_status") or approval_gate.get("status"),
        "restore_requires_explicit_approval": payload.get("restore_requires_explicit_approval") is True,
        "execute_requires_explicit_approval": payload.get("execute_requires_explicit_approval") is True,
        "next_action": payload.get("next_action"),
        "required_files": payload.get("required_files") if isinstance(payload.get("required_files"), list) else [],
    }


def _read_repo_json(repo_path: Path, path: str) -> dict[str, Any]:
    file_path = repo_path / path
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _object_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    keys = set(before) | set(after)
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []
    for key in sorted(keys):
        if key not in before:
            added.append(key)
        elif key not in after:
            removed.append(key)
        elif before[key] != after[key]:
            changed.append(key)
    return {"added": added, "removed": removed, "changed": changed}


def _package_json_delta(repo_path: Path) -> dict[str, Any]:
    before = _json_file_at_head(repo_path, "package.json")
    after = _read_repo_json(repo_path, "package.json")
    before_scripts = before.get("scripts") if isinstance(before.get("scripts"), dict) else {}
    after_scripts = after.get("scripts") if isinstance(after.get("scripts"), dict) else {}
    before_deps = before.get("dependencies") if isinstance(before.get("dependencies"), dict) else {}
    after_deps = after.get("dependencies") if isinstance(after.get("dependencies"), dict) else {}
    before_dev_deps = before.get("devDependencies") if isinstance(before.get("devDependencies"), dict) else {}
    after_dev_deps = after.get("devDependencies") if isinstance(after.get("devDependencies"), dict) else {}

    script_delta = _object_delta(before_scripts, after_scripts)
    dep_delta = _object_delta(before_deps, after_deps)
    dev_dep_delta = _object_delta(before_dev_deps, after_dev_deps)
    script_changes = sorted(set(script_delta["added"] + script_delta["removed"] + script_delta["changed"]))
    dep_changes = sorted(set(dep_delta["added"] + dep_delta["removed"] + dep_delta["changed"]))
    dev_dep_changes = sorted(set(dev_dep_delta["added"] + dev_dep_delta["removed"] + dev_dep_delta["changed"]))
    required_script_present = after_scripts.get(MOUSSEY_SNOWCUBES_PACKAGE_SCRIPT) is not None
    unrelated_scripts = [
        name
        for name in script_changes
        if not name.startswith(MOUSSEY_SNOWCUBES_PACKAGE_RELATED_PREFIXES)
    ]
    unrelated_dependencies = dep_changes + dev_dep_changes
    clean_candidate = required_script_present and not unrelated_scripts and not unrelated_dependencies
    return {
        "path": "package.json",
        "status": "clean_snowcubes_candidate" if clean_candidate else "mixed_or_missing",
        "required_script": MOUSSEY_SNOWCUBES_PACKAGE_SCRIPT,
        "required_script_present": required_script_present,
        "script_changes": script_changes,
        "dependency_changes": dep_changes,
        "dev_dependency_changes": dev_dep_changes,
        "unrelated_script_changes": unrelated_scripts,
        "unrelated_dependency_changes": unrelated_dependencies,
        "clean_snowcubes_package_candidate": clean_candidate,
        "summary": (
            "package.json currently contains only Snowcubes-related script drift needed by the local-CI package."
            if clean_candidate
            else "package.json mixes Snowcubes local-CI drift with unrelated or missing package changes; split before packaging source."
        ),
    }


def _local_ci_current_source_notes(
    moussey_repo_path: Path | None,
    *,
    repo_root: Path,
    snowcubes_canonical_tracker: Path = DEFAULT_SNOWCUBES_CANONICAL_TRACKER,
    snowcubes_tracker_search_root: Path = DEFAULT_SNOWCUBES_TRACKER_SEARCH_ROOT,
) -> dict[str, Any]:
    repo_path = moussey_repo_path or DEFAULT_MOUSSEY_REPO
    clean_source_candidate = _snowcubes_clean_source_candidate(repo_root)
    tracker_diagnosis = _snowcubes_tracker_diagnosis(
        canonical_tracker=snowcubes_canonical_tracker,
        search_root=snowcubes_tracker_search_root,
    )
    approval_packet = _snowcubes_approval_packet(repo_root)
    files = MOUSSEY_LOCAL_CI_CURRENT_SOURCE_FILES
    if not repo_path.exists():
        return {
            "repo": "moussey",
            "repo_path": str(repo_path),
            "status": "unavailable",
            "summary": "Moussey repo path was not found; current-source inclusion could not be audited.",
            "files": [],
            "adjacent_files": [],
            "package_json_delta": {},
            "clean_source_candidate": clean_source_candidate,
            "tracker_diagnosis": tracker_diagnosis,
            "approval_packet": approval_packet,
            "worktree_execute_would_include_current_source": None,
            "clean_snowcubes_package_candidate": None,
            "reason": "repo path missing",
            "safe_next_action": "Verify the canonical Moussey checkout path before running FirstBite local-CI lanes.",
        }

    adjacent_files = MOUSSEY_LOCAL_CI_ADJACENT_FILES
    status_by_path = _git_status_by_path(repo_path, files + adjacent_files)
    tracked_paths = _git_tracked_paths(repo_path, files + adjacent_files)
    file_states: list[dict[str, Any]] = []
    dirty_or_untracked = False
    for file in files:
        exists = (repo_path / file).exists()
        tracked = file in tracked_paths
        status = status_by_path.get(file)
        if status is None:
            status = "clean" if tracked and exists else "absent"
        if status != "clean" or not tracked:
            dirty_or_untracked = True
        file_states.append(
            {
                "path": file,
                "exists": exists,
                "tracked": tracked,
                "status": status,
            }
        )
    adjacent_file_states: list[dict[str, Any]] = []
    for file in adjacent_files:
        exists = (repo_path / file).exists()
        tracked = file in tracked_paths
        status = status_by_path.get(file)
        if status is None:
            status = "clean" if tracked and exists else "absent"
        adjacent_file_states.append(
            {
                "path": file,
                "exists": exists,
                "tracked": tracked,
                "status": status,
            }
        )

    package_delta = _package_json_delta(repo_path)
    worktree_execute_includes_current_source = not dirty_or_untracked
    package_clean = package_delta.get("clean_snowcubes_package_candidate") is True
    clean_candidate_ready = clean_source_candidate.get("status") == "ready"
    tracker_candidates_exist = tracker_diagnosis.get("status") == "candidate_data_present_off_canonical"
    tracker_recommendation = tracker_diagnosis.get("recommended_candidate")
    tracker_recommendation_path = (
        tracker_recommendation.get("path")
        if isinstance(tracker_recommendation, dict)
        else None
    )
    approval_packet_ready = approval_packet.get("status") == "ready_for_approval"
    approval_packet_path = approval_packet.get("path")
    status = "source_state_clean" if worktree_execute_includes_current_source else "source_state_warning"
    if not worktree_execute_includes_current_source and clean_candidate_ready:
        status = "clean_source_candidate_ready"
    return {
        "repo": "moussey",
        "repo_path": str(repo_path),
        "status": status,
        "summary": (
            "Moussey local-CI source inputs are clean/tracked; a clean FirstBite worktree execute should include the current source."
            if worktree_execute_includes_current_source
            else (
                "Primary Moussey checkout remains dirty, but a clean committed Snowcubes source candidate exists for source-ref execution."
                if clean_candidate_ready
                else "Moussey local-CI blocker proof is present only in dirty/untracked source; a clean FirstBite worktree execute from HEAD would re-prove older source."
            )
        ),
        "files": file_states,
        "adjacent_files": adjacent_file_states,
        "package_json_delta": package_delta,
        "clean_source_candidate": clean_source_candidate,
        "tracker_diagnosis": tracker_diagnosis,
        "approval_packet": approval_packet,
        "worktree_execute_would_include_current_source": worktree_execute_includes_current_source,
        "clean_snowcubes_package_candidate": package_clean or clean_candidate_ready,
        "reason": None
        if worktree_execute_includes_current_source
        else (
            "primary checkout is dirty; clean source-ref candidate is available for the Snowcubes lane"
            if clean_candidate_ready
            else "current structured blocker proof is dirty/untracked; FirstBite clean worktree execution is source-ref based"
        ),
        "safe_next_action": (
            "Rerun the scoped FirstBite lane from the clean source ref."
            if worktree_execute_includes_current_source
            else f"Use approval packet {approval_packet_path}; with explicit restore/provide and local-CI execute approval, restore the recommended tracker CSVs and run moussey_snowcubes_readiness from source ref {clean_source_candidate.get('source_ref')}."
            if clean_candidate_ready and approval_packet_ready and approval_packet_path
            else f"Approve Candidate B/default recommended tracker candidate ({tracker_recommendation_path}), restore/provide its two CSVs at the canonical tracker path, then run moussey_snowcubes_readiness from source ref {clean_source_candidate.get('source_ref')} with explicit local-CI execute approval."
            if clean_candidate_ready and tracker_candidates_exist and tracker_recommendation_path
            else f"Choose/approve one off-canonical tracker candidate, restore/provide it at the canonical tracker path, then run moussey_snowcubes_readiness from source ref {clean_source_candidate.get('source_ref')} with explicit local-CI execute approval."
            if clean_candidate_ready and tracker_candidates_exist
            else f"Restore/provide canonical tracker CSVs, then run moussey_snowcubes_readiness from source ref {clean_source_candidate.get('source_ref')} with explicit local-CI execute approval."
            if clean_candidate_ready
            else "Split the Snowcubes local-CI source package away from unrelated package drift, then rerun moussey_snowcubes_readiness from that source."
            if not package_clean
            else "Package the intended source first, then rerun moussey_snowcubes_readiness from that source; avoid a clean worktree execute before source packaging."
        ),
    }


def _local_ci_input_path(report: dict[str, Any]) -> Path | None:
    rollup = report.get("rollup") if isinstance(report.get("rollup"), dict) else {}
    inputs = rollup.get("inputs") if isinstance(rollup.get("inputs"), dict) else {}
    value = inputs.get("local_ci")
    return Path(str(value)).expanduser() if value else None


def _local_ci_launch_trust(
    report: dict[str, Any],
    *,
    repo_root: Path,
    moussey_repo_path: Path | None = None,
    snowcubes_canonical_tracker: Path = DEFAULT_SNOWCUBES_CANONICAL_TRACKER,
    snowcubes_tracker_search_root: Path = DEFAULT_SNOWCUBES_TRACKER_SEARCH_ROOT,
) -> dict[str, Any]:
    path = _local_ci_input_path(report)
    source: dict[str, Any] = {}
    if path is not None and path.exists():
        source = _read_json(path)

    launch = source.get("launchTrust") if isinstance(source.get("launchTrust"), dict) else {}
    gates = launch.get("gates") if isinstance(launch.get("gates"), list) else []
    failing_lanes = source.get("failingLanes") if isinstance(source.get("failingLanes"), list) else []
    manifest = source.get("manifestReadiness") if isinstance(source.get("manifestReadiness"), dict) else {}
    manifest_blockers = manifest.get("blockingRepos") if isinstance(manifest.get("blockingRepos"), list) else []
    runner = source.get("runnerReadiness") if isinstance(source.get("runnerReadiness"), dict) else {}
    mcp_client = runner.get("mcpClient") if isinstance(runner.get("mcpClient"), dict) else {}
    refresh = mcp_client.get("latestRefreshPlan") if isinstance(mcp_client.get("latestRefreshPlan"), dict) else {}
    loaded_mcp_effective_ready = (
        mcp_client.get("claimStatus") == "ready" or mcp_client.get("status") == "current_only"
    )
    historical_stale_process_count = refresh.get("staleProcessCount")

    return {
        "source_path": str(path) if path is not None else None,
        "source_exists": bool(path and path.exists()),
        "status": launch.get("status"),
        "summary": launch.get("summary"),
        "ready_gate_count": launch.get("readyGateCount"),
        "blocked_gate_count": launch.get("blockedGateCount"),
        "warning_gate_count": launch.get("warningGateCount"),
        "total_gate_count": launch.get("totalGateCount"),
        "blocked_gates": [
            _compact_gate(gate)
            for gate in gates
            if isinstance(gate, dict) and gate.get("status") == "blocked"
        ],
        "warning_gates": [
            _compact_gate(gate)
            for gate in gates
            if isinstance(gate, dict) and gate.get("status") == "warning"
        ],
        "failing_lanes": [
            _compact_failing_lane(lane)
            for lane in failing_lanes
            if isinstance(lane, dict)
        ],
        "nonpass_diagnosis": _nonpass_diagnosis(repo_root),
        "manifest_blocking_repos": [
            {
                "repo": repo.get("repo"),
                "status": repo.get("status"),
                "portability_status": repo.get("portabilityStatus"),
                "summary": repo.get("summary"),
            }
            for repo in manifest_blockers
            if isinstance(repo, dict)
        ],
        "loaded_mcp_client": {
            "status": mcp_client.get("status"),
            "claim_status": mcp_client.get("claimStatus"),
            "effective_ready": loaded_mcp_effective_ready,
            "summary": mcp_client.get("summary"),
            "refresh_run_id": refresh.get("runId"),
            "refresh_verdict": refresh.get("verdict"),
            "stale_process_count": historical_stale_process_count,
            "historical_stale_process_count": historical_stale_process_count,
            "effective_stale_process_count": 0
            if loaded_mcp_effective_ready
            else historical_stale_process_count,
            "process_count": refresh.get("processCount"),
            "read_only": refresh.get("readOnly"),
            "report_path": refresh.get("reportPath"),
        },
        "current_source_notes": _local_ci_current_source_notes(
            moussey_repo_path,
            repo_root=repo_root,
            snowcubes_canonical_tracker=snowcubes_canonical_tracker,
            snowcubes_tracker_search_root=snowcubes_tracker_search_root,
        ),
    }


def _resume_order(criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item["id"]): item for item in criteria}
    ordered: list[dict[str, Any]] = []
    for criterion_id in RESUME_PRIORITY:
        item = by_id.get(criterion_id)
        if not item or item["status"] in {"ready", "documented_non_blocking"}:
            continue
        resume_class = item.get("resume_class") or (
            "operator_gated" if item["status"] == "gated" else "agent_doable"
        )
        ordered.append(
            {
                "rank": len(ordered) + 1,
                "criterion_id": item["id"],
                "status": item["status"],
                "resume_class": resume_class,
                "why_next": item["blockers"][0] if item["blockers"] else item["summary"],
                "next_resume": item["next_resume"],
            }
        )
    return ordered


def _recommended_next_goal(resume_order: list[dict[str, Any]]) -> dict[str, Any]:
    first = resume_order[0] if resume_order else None
    return {
        "objective": (
            "Move the local operator stack from honest yellow toward launch-trust by closing the "
            "highest-ranked unclosed criterion, while preserving review-only/non-destructive guardrails."
        ),
        "first_resume_criterion": first["criterion_id"] if first else None,
        "first_resume_class": first["resume_class"] if first else None,
        "guardrails": [
            "Do not mark the active goal complete until all eight criteria are ready, gated, or documented non-blocking.",
            "Do not install LaunchAgents, execute local-CI lanes, restart host apps, or dispatch workers without a separate explicit operation.",
            "Use the latest verified-alive packet and FirstBite plan evidence before changing any status.",
        ],
    }


def _criterion_path_evidence_failures(criteria: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for item in criteria:
        if item["status"] not in {"ready", "gated", "documented_non_blocking"}:
            continue
        for evidence in item.get("evidence", []):
            if evidence.get("type") == "path" and not evidence.get("exists"):
                failures.append(f"{item['id']} evidence path missing: {evidence.get('path')}")
    return failures


def _proof_discipline_audit(
    *,
    criteria: list[dict[str, Any]],
    surface_audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    failures = _criterion_path_evidence_failures(criteria)
    for name, audit in surface_audits.items():
        missing = audit.get("missing_evidence") if isinstance(audit.get("missing_evidence"), list) else []
        failed_routes = audit.get("failed_routes") if isinstance(audit.get("failed_routes"), list) else []
        if missing:
            failures.append(f"{name} has {len(missing)} missing evidence artifact(s).")
        if failed_routes:
            failures.append(f"{name} has {len(failed_routes)} failed live route probe(s).")
        if name == "litty_cockpit_boundaries" and audit.get("contract_ok") is not True:
            failures.append("litty_cockpit_boundaries contract_ok is not true.")
    if failures:
        return {
            "status": "partial",
            "summary": "Some ready/gated/documented claims still lack direct mechanical proof in this audit.",
            "blockers": failures,
            "next_resume": [
                "Open each failed evidence path/probe named here and rerun the scoped verifier before flipping proof discipline.",
            ],
        }
    return {
        "status": "ready",
        "summary": "Every ready, gated, or documented-non-blocking claim in this audit has direct evidence paths and/or live route proof.",
        "blockers": [],
        "next_resume": [
            "For any new claim, add it to the audit with direct evidence before treating it as complete.",
        ],
    }


def _remaining_work_classification_audit(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    unclosed: list[dict[str, Any]] = []
    unclassified: list[dict[str, Any]] = []
    for item in criteria:
        if item["status"] in {"ready", "gated", "documented_non_blocking"}:
            continue
        resume_class = item.get("resume_class") or (
            "operator_gated" if item["status"] == "gated" else "agent_doable"
        )
        record = {
            "criterion_id": item["id"],
            "status": item["status"],
            "resume_class": resume_class,
            "blockers": item.get("blockers", []),
            "next_resume": item.get("next_resume", []),
        }
        unclosed.append(record)
        if resume_class == "agent_doable":
            unclassified.append(record)

    if unclassified:
        return {
            "status": "partial",
            "summary": f"{len(unclassified)} remaining criterion/criteria still have agent-doable work before the parent goal can close.",
            "blockers": [
                f"{item['criterion_id']} remains {item['status']} with resume_class={item['resume_class']}."
                for item in unclassified
            ],
            "classified_remaining_work": unclosed,
            "next_resume": [
                "Close or explicitly gate the agent-doable remaining criteria, then regenerate this audit.",
            ],
        }

    return {
        "status": "ready",
        "summary": "All remaining unclosed criteria are explicitly operator/credential/source/hardware gated with exact resume paths.",
        "blockers": [],
        "classified_remaining_work": unclosed,
        "next_resume": [
            "Do not execute gated work from this audit; use the exact next_resume rows and require explicit approval where named.",
        ],
    }


def build_payload(
    *,
    repo_root: Path,
    verified_alive_report_path: Path | None,
    deferrals_path: Path | None,
    plan_path: Path | None = None,
    moussey_repo_path: Path | None = None,
    moussey_base_url: str = DEFAULT_MOUSSEY_BASE_URL,
    litty_repo_path: Path | None = None,
    litty_base_url: str = DEFAULT_LITTY_BASE_URL,
    snowcubes_canonical_tracker: Path = DEFAULT_SNOWCUBES_CANONICAL_TRACKER,
    snowcubes_tracker_search_root: Path = DEFAULT_SNOWCUBES_TRACKER_SEARCH_ROOT,
) -> dict[str, Any]:
    plan = plan_path or (repo_root / DEFAULT_FIRSTBITE_PLAN)
    verified_report = _read_json(verified_alive_report_path) if verified_alive_report_path else {}
    deferrals = _read_json(deferrals_path) if deferrals_path else {}
    checks = _checks_by_id(verified_report)
    local_ci_launch_trust = _local_ci_launch_trust(
        verified_report,
        repo_root=repo_root,
        moussey_repo_path=moussey_repo_path,
        snowcubes_canonical_tracker=snowcubes_canonical_tracker,
        snowcubes_tracker_search_root=snowcubes_tracker_search_root,
    )
    moussey_deferred_perf_ui = _moussey_deferred_perf_ui_audit(
        repo_root=repo_root,
        moussey_repo_path=moussey_repo_path,
        moussey_base_url=moussey_base_url,
    )
    chat_front_door = _moussey_chat_front_door_audit(
        repo_root=repo_root,
        moussey_repo_path=moussey_repo_path,
        moussey_base_url=moussey_base_url,
    )
    litty_cockpit_boundaries = _litty_cockpit_boundaries_audit(
        repo_root=repo_root,
        litty_repo_path=litty_repo_path,
        litty_base_url=litty_base_url,
    )

    local_ci = checks.get("moussey_local_ci_endpoint", {})
    local_ci_facts = local_ci.get("facts") if isinstance(local_ci.get("facts"), dict) else {}
    captain = checks.get("captain_setup_health", {})
    drift = checks.get("drift_tile", {})
    deferral_status = str(deferrals.get("status") or "missing")

    line_refs = {
        "lcq": _line_refs(plan, ["LCQ-5", "Local Chat Quality Track"]),
        "litty": _line_refs(plan, ["M7: Litty lane smoke", "M3: LaunchAgent handoff"]),
        "local_ci": _line_refs(plan, ["Moussey compact local-CI view now surfaces", "M23/P4"]),
        "captain": _line_refs(plan, ["Captain skill audit", "Verified-alive now carries Captain"]),
        "summary": _line_refs(plan, ["Verified-alive runner summary now names"]),
    }
    local_ci_source_notes = local_ci_launch_trust.get("current_source_notes")
    local_ci_safe_next = (
        str(local_ci_source_notes.get("safe_next_action") or "")
        if isinstance(local_ci_source_notes, dict)
        else ""
    )
    loaded_mcp_client = local_ci_launch_trust.get("loaded_mcp_client")
    loaded_mcp_effective_ready = (
        isinstance(loaded_mcp_client, dict) and loaded_mcp_client.get("effective_ready") is True
    )
    local_ci_resume_class = "agent_doable"
    local_ci_resume_gates: list[str] = []
    approval_packet = (
        local_ci_source_notes.get("approval_packet")
        if isinstance(local_ci_source_notes, dict) and isinstance(local_ci_source_notes.get("approval_packet"), dict)
        else {}
    )
    approval_packet_operator_gated = approval_packet.get("approval_gate_status") == "operator_gated"
    local_ci_execute_operator_gated = (
        "local-CI execute approval" in local_ci_safe_next
        or "local-ci execute approval" in local_ci_safe_next.lower()
        or approval_packet_operator_gated
    )
    if local_ci_execute_operator_gated:
        local_ci_resume_class = "operator_gated"
        local_ci_resume_gates.append("moussey_snowcubes_readiness execute requires explicit local-CI approval.")
    if isinstance(loaded_mcp_client, dict) and loaded_mcp_client.get("claim_status") == "blocked":
        local_ci_resume_class = "operator_gated"
        local_ci_resume_gates.append("Loaded MCP client convergence requires a host-app restart outside this audit.")
    local_ci_next_resume = [
        "Open the latest verified-alive summary and Moussey compact local-CI endpoint before running any lane.",
    ]
    if local_ci_safe_next:
        local_ci_next_resume.append(local_ci_safe_next)
    local_ci_mcp_summary = (
        f"loadedMcp={loaded_mcp_client.get('claim_status')}/{loaded_mcp_client.get('status')}"
        if loaded_mcp_effective_ready and isinstance(loaded_mcp_client, dict)
        else f"MCP refresh verdict={local_ci_facts.get('mcp_refresh_verdict')}"
    )
    local_ci_blockers = [
        (
            "Launch trust remains blocked/warning until non-pass lanes and stale proof are resolved."
            if loaded_mcp_effective_ready
            else "Launch trust remains blocked/warning until non-pass lanes, stale proof, and stale loaded MCP clients are resolved."
        ),
        *local_ci_resume_gates,
    ]
    local_ci_status = "missing"
    if local_ci:
        local_ci_status = "partial"
        if (
            local_ci_resume_class == "operator_gated"
            and loaded_mcp_effective_ready
            and isinstance(local_ci_source_notes, dict)
            and local_ci_source_notes.get("status") == "clean_source_candidate_ready"
            and approval_packet.get("status") == "ready_for_approval"
            and approval_packet.get("restore_requires_explicit_approval") is True
            and approval_packet.get("execute_requires_explicit_approval") is True
            and approval_packet.get("source_ref_ready") is True
        ):
            local_ci_status = "gated"
    local_ci_summary = (
        f"Verified-alive local-CI check is {local_ci.get('status')}; "
        f"launchTrust={local_ci_facts.get('launch_trust_status')}; "
        f"{local_ci_mcp_summary}."
    )
    if local_ci_status == "gated":
        local_ci_summary = (
            f"Verified-alive current-machine proof exists; launchTrust={local_ci_facts.get('launch_trust_status')}; "
            f"{local_ci_mcp_summary}; remaining restore/execute work is operator-gated."
        )

    criteria = [
        _criterion(
            id="moussey_deferred_perf_ui",
            label="Moussey deferred perf/UI closeout",
            status=moussey_deferred_perf_ui["status"],
            summary=moussey_deferred_perf_ui["summary"],
            evidence=[
                _evidence_path(plan, "FirstBite plan contains Moussey refresh and LCQ proof rows"),
                *line_refs["lcq"],
            ],
            blockers=moussey_deferred_perf_ui["blockers"]
            if "blockers" in moussey_deferred_perf_ui
            else [
                *(
                    [f"{len(moussey_deferred_perf_ui['missing_evidence'])} required evidence artifact(s) are missing."]
                    if moussey_deferred_perf_ui["missing_evidence"]
                    else []
                ),
                *(
                    [f"{len(moussey_deferred_perf_ui['failed_routes'])} live route probe(s) failed."]
                    if moussey_deferred_perf_ui["failed_routes"]
                    else []
                ),
            ],
            next_resume=[
                "Use local_ci_current_machine next; Moussey deferred perf/UI has its own evidence packet."
                if moussey_deferred_perf_ui["status"] == "ready"
                else "Inspect /Users/leokwan/Development/moussey/PLAN.md deferred rows, C99 evidence, and live route probes.",
            ],
        ),
        _criterion(
            id="local_ci_current_machine",
            label="Local CI readiness has current-machine proof",
            status=local_ci_status,
            summary=local_ci_summary if local_ci else "No verified-alive local-CI check was found.",
            evidence=[
                _evidence_path(verified_alive_report_path, "verified-alive runner report"),
                *line_refs["local_ci"],
            ],
            blockers=local_ci_blockers,
            next_resume=local_ci_next_resume,
            resume_class=local_ci_resume_class,
        ),
        _criterion(
            id="chat_operator_front_door",
            label="Chat/operator routing is tested enough to trust as front door",
            status=chat_front_door["status"],
            summary=chat_front_door["summary"],
            evidence=[
                _evidence_path(verified_alive_report_path, "verified-alive runner report"),
                *line_refs["lcq"],
            ],
            blockers=[*chat_front_door["blockers"], *chat_front_door["credential_gates"], *chat_front_door["operator_gates"]],
            next_resume=[
                "Run /api/chat/providers and /chat probes from the live Moussey server before changing this classification.",
                "Claude sign-in and real enforce/passcode rollout stay operator-gated unless Leo explicitly asks for those actions.",
            ],
        ),
        _criterion(
            id="mobile_operator_rows",
            label="Mobile/operator rows completed or explicitly Leo-gated",
            status="gated" if deferral_status == "ready" else "missing",
            summary=(
                "M24 honest-deferrals firewall has canonical owners and re-entry gates for mobile/LAN/device work."
                if deferral_status == "ready"
                else "No ready M24 deferrals firewall was found."
            ),
            evidence=[
                _evidence_path(deferrals_path, "M24 deferrals firewall JSON"),
            ],
            blockers=[
                "Nicole device, Tailscale, and some mobile proof remain human/device/operator gated.",
            ],
            next_resume=[
                "Resume from connect-the-fleet and moussey-mobile-operator rows named by the deferrals firewall.",
            ],
        ),
        _criterion(
            id="litty_cockpit_boundaries",
            label="Litty/coding cockpit boundaries are clear",
            status=litty_cockpit_boundaries["status"],
            summary=litty_cockpit_boundaries["summary"],
            evidence=[
                _evidence_path(plan, "FirstBite plan M3/M7 and Litty progress rows"),
                *line_refs["litty"],
            ],
            blockers=[
                *litty_cockpit_boundaries["blockers"],
                *litty_cockpit_boundaries["source_gates"],
                *litty_cockpit_boundaries["operator_gates"],
            ],
            next_resume=[
                "Open /Users/leokwan/Development/vidux/projects/litty/PLAN.md around C225/C226 and the latest live-runtime rows.",
                "Do not restart :4400, install LaunchAgents, merge PR #1, or execute Litty lanes unless that operation is explicitly approved.",
            ],
            resume_class="operator_gated" if litty_cockpit_boundaries["status"] == "gated" else "agent_doable",
        ),
        _criterion(
            id="captain_setup_health",
            label="Captain skill/setup audit findings addressed or non-blocking",
            status="documented_non_blocking" if captain else "missing",
            summary=(
                f"Captain check is {captain.get('status')}: {captain.get('summary')}"
                if captain
                else "No Captain setup health check was found."
            ),
            evidence=[
                _evidence_path(verified_alive_report_path, "verified-alive runner report"),
                *line_refs["captain"],
            ],
            blockers=[
                "Remaining Captain findings are setup-policy/frontmatter hygiene, not local operator blockers.",
            ]
            if captain
            else ["Run Captain audit and refresh verified-alive."],
            next_resume=[
                "Use /Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-captain-health-verified-alive.md.",
            ],
        ),
    ]

    proof_discipline = _proof_discipline_audit(
        criteria=criteria,
        surface_audits={
            "moussey_deferred_perf_ui": moussey_deferred_perf_ui,
            "chat_operator_front_door": chat_front_door,
            "litty_cockpit_boundaries": litty_cockpit_boundaries,
        },
    )
    criteria.append(
        _criterion(
            id="proof_discipline",
            label="Every completed claim has mechanical proof",
            status=proof_discipline["status"],
            summary=proof_discipline["summary"],
            evidence=[
                _evidence_path(verified_alive_report_path, "latest runner report"),
                _evidence_path(plan, "plan rows cite evidence paths"),
                *line_refs["summary"],
            ],
            blockers=proof_discipline["blockers"],
            next_resume=proof_discipline["next_resume"],
        )
    )
    remaining_work_classified = _remaining_work_classification_audit(criteria)
    criteria.append(
        _criterion(
            id="remaining_work_classified",
            label="Remaining work only gated/credential/hardware/follow-up",
            status=remaining_work_classified["status"],
            summary=remaining_work_classified["summary"],
            evidence=[
                _evidence_path(deferrals_path, "deferrals firewall"),
                _evidence_path(verified_alive_report_path, "verified-alive runner report"),
            ],
            blockers=remaining_work_classified["blockers"],
            next_resume=remaining_work_classified["next_resume"],
        )
    )

    complete = all(item["status"] in {"ready", "documented_non_blocking", "gated"} for item in criteria)
    counts = _status_counts(criteria)
    resume_order = _resume_order(criteria)
    blocked_count = counts.get("missing", 0) + counts.get("blocked", 0)
    partial_count = counts.get("partial", 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SCRIPT_NAME,
        "mode": "local_operator_goal_completion_audit",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "status": "complete" if complete else "incomplete",
        "summary": (
            f"incomplete: {partial_count} partial criterion/criteria, {blocked_count} missing/blocked; "
            "full goal remains active"
        )
        if not complete
        else "complete: all criteria are proven ready, gated, or documented non-blocking",
        "inputs": {
            "firstbite_plan": str(plan),
            "verified_alive_report": str(verified_alive_report_path) if verified_alive_report_path else None,
            "deferrals": str(deferrals_path) if deferrals_path else None,
        },
        "status_counts": counts,
        "recommended_next_goal": _recommended_next_goal(resume_order),
        "next_resume_order": resume_order,
        "local_ci_launch_trust": local_ci_launch_trust,
        "moussey_deferred_perf_ui": moussey_deferred_perf_ui,
        "chat_operator_front_door": chat_front_door,
        "litty_cockpit_boundaries": litty_cockpit_boundaries,
        "proof_discipline": proof_discipline,
        "remaining_work_classified": remaining_work_classified,
        "criteria": criteria,
        "non_claims": [
            "This audit did not mark the active goal complete.",
            "This audit did not execute local-CI lanes.",
            "This audit did not install LaunchAgents.",
            "This audit did not edit Moussey, Litty, /ai, or /ai-leo source.",
            "This audit does not replace scoped tests, browser proof, or simulator proof.",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Local Operator Goal Audit - {payload['generated_at']}",
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
    lines.extend(["", "## Status Counts", ""])
    for status, count in sorted(payload["status_counts"].items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Recommended Next Goal", ""])
    next_goal = payload["recommended_next_goal"]
    lines.extend(
        [
            f"- `objective`: {next_goal['objective']}",
            f"- `first_resume_criterion`: `{next_goal['first_resume_criterion']}`",
            f"- `first_resume_class`: `{next_goal['first_resume_class']}`",
            "- `guardrails`:",
        ]
    )
    for guardrail in next_goal["guardrails"]:
        lines.append(f"  - {guardrail}")
    lines.extend(["", "## Resume Order", ""])
    for item in payload["next_resume_order"]:
        lines.extend(
            [
                f"### {item['rank']}. {item['criterion_id']}",
                "",
                f"- `status`: `{item['status']}`",
                f"- `resume_class`: `{item['resume_class']}`",
                f"- `why_next`: {item['why_next']}",
            ]
        )
        if item["next_resume"]:
            lines.append("- `next_resume`:")
            for resume in item["next_resume"]:
                lines.append(f"  - {resume}")
        lines.append("")
    perf_ui = payload.get("moussey_deferred_perf_ui") or {}
    lines.extend(
        [
            "## Moussey Deferred Perf/UI",
            "",
            f"- `status`: `{perf_ui.get('status')}`",
            f"- `summary`: {perf_ui.get('summary')}",
            "",
            "### Evidence Artifacts",
            "",
        ]
    )
    for item in perf_ui.get("evidence", []):
        lines.append(
            f"- `{item.get('id')}` exists=`{item.get('exists')}` size=`{item.get('size_bytes')}` "
            f"path=`{item.get('path')}` - {item.get('note')}"
        )
    lines.extend(["", "### Live Route Probes", ""])
    for item in perf_ui.get("route_probes", []):
        lines.append(
            f"- `{item.get('route')}` ok=`{item.get('ok')}` status=`{item.get('status')}` bytes=`{item.get('bytes')}`"
        )
    if perf_ui.get("non_claims"):
        lines.extend(["", "### Perf/UI Non-Claims", ""])
        for item in perf_ui["non_claims"]:
            lines.append(f"- {item}")
    lines.append("")
    chat = payload.get("chat_operator_front_door") or {}
    providers = chat.get("providers") if isinstance(chat.get("providers"), dict) else {}
    provider_states = providers.get("providers") if isinstance(providers.get("providers"), dict) else {}
    lines.extend(
        [
            "## Chat Operator Front Door",
            "",
            f"- `status`: `{chat.get('status')}`",
            f"- `summary`: {chat.get('summary')}",
            f"- `default_provider`: `{providers.get('default_provider')}`",
            "",
            "### Providers",
            "",
        ]
    )
    for name, state in provider_states.items():
        if not isinstance(state, dict):
            continue
        lines.append(f"- `{name}` ready=`{state.get('ready')}` - {state.get('message')}")
    lines.extend(["", "### Evidence Artifacts", ""])
    for item in chat.get("evidence", []):
        lines.append(
            f"- `{item.get('id')}` exists=`{item.get('exists')}` size=`{item.get('size_bytes')}` "
            f"path=`{item.get('path')}` - {item.get('note')}"
        )
    lines.extend(["", "### Live Route Probes", ""])
    for item in chat.get("route_probes", []):
        lines.append(
            f"- `{item.get('route')}` ok=`{item.get('ok')}` status=`{item.get('status')}` bytes=`{item.get('bytes')}`"
        )
    if chat.get("credential_gates"):
        lines.extend(["", "### Credential Gates", ""])
        for item in chat["credential_gates"]:
            lines.append(f"- {item}")
    if chat.get("operator_gates"):
        lines.extend(["", "### Operator Gates", ""])
        for item in chat["operator_gates"]:
            lines.append(f"- {item}")
    if chat.get("non_claims"):
        lines.extend(["", "### Chat Non-Claims", ""])
        for item in chat["non_claims"]:
            lines.append(f"- {item}")
    lines.append("")
    litty = payload.get("litty_cockpit_boundaries") or {}
    lines.extend(
        [
            "## Litty Cockpit Boundaries",
            "",
            f"- `status`: `{litty.get('status')}`",
            f"- `summary`: {litty.get('summary')}",
            f"- `contract_ok`: `{litty.get('contract_ok')}`",
            "",
            "### Evidence Artifacts",
            "",
        ]
    )
    for item in litty.get("evidence", []):
        lines.append(
            f"- `{item.get('id')}` exists=`{item.get('exists')}` size=`{item.get('size_bytes')}` "
            f"path=`{item.get('path')}` - {item.get('note')}"
        )
    lines.extend(["", "### Live Route Probes", ""])
    for item in litty.get("route_probes", []):
        lines.append(
            f"- `{item.get('route')}` ok=`{item.get('ok')}` status=`{item.get('status')}` bytes=`{item.get('bytes')}`"
        )
    if litty.get("source_gates"):
        lines.extend(["", "### Source Gates", ""])
        for item in litty["source_gates"]:
            lines.append(f"- {item}")
    if litty.get("operator_gates"):
        lines.extend(["", "### Operator Gates", ""])
        for item in litty["operator_gates"]:
            lines.append(f"- {item}")
    if litty.get("non_claims"):
        lines.extend(["", "### Litty Non-Claims", ""])
        for item in litty["non_claims"]:
            lines.append(f"- {item}")
    lines.append("")
    local_ci = payload["local_ci_launch_trust"]
    lines.extend(
        [
            "## Local CI Launch Trust",
            "",
            f"- `source_path`: `{local_ci['source_path']}`",
            f"- `source_exists`: `{local_ci['source_exists']}`",
            f"- `status`: `{local_ci['status']}`",
            f"- `summary`: {local_ci['summary']}",
            f"- `ready_gate_count`: `{local_ci['ready_gate_count']}`",
            f"- `blocked_gate_count`: `{local_ci['blocked_gate_count']}`",
            f"- `warning_gate_count`: `{local_ci['warning_gate_count']}`",
            f"- `total_gate_count`: `{local_ci['total_gate_count']}`",
            "",
            "### Blocked Gates",
            "",
        ]
    )
    for gate in local_ci["blocked_gates"]:
        lines.append(f"- `{gate['id']}`: {gate['summary']}")
    lines.extend(["", "### Warning Gates", ""])
    for gate in local_ci["warning_gates"]:
        lines.append(f"- `{gate['id']}`: {gate['summary']}")
    lines.extend(["", "### Non-Pass Lanes", ""])
    for lane in local_ci["failing_lanes"]:
        lines.append(
            f"- `{lane['lane']}` ({lane['repo']}): `{lane['status']}` rc=`{lane['rc']}` - {lane['reason']}"
        )
    diagnosis = local_ci.get("nonpass_diagnosis") if isinstance(local_ci.get("nonpass_diagnosis"), dict) else {}
    lines.extend(
        [
            "",
            "### Non-Pass Diagnosis",
            "",
            f"- `exists`: `{diagnosis.get('exists')}`",
            f"- `path`: `{diagnosis.get('path')}`",
            f"- `failed_lane_count`: `{diagnosis.get('failed_lane_count')}`",
            f"- `visible_failed_lane_count`: `{diagnosis.get('visible_failed_lane_count')}`",
            f"- `aggregate_nonpass_lane_count`: `{diagnosis.get('aggregate_nonpass_lane_count')}`",
            f"- `undocumented_nonpass_lane_count`: `{diagnosis.get('undocumented_nonpass_lane_count')}`",
            f"- `diagnosis_coverage_status`: `{diagnosis.get('diagnosis_coverage_status')}`",
            f"- `group_count`: `{diagnosis.get('group_count')}`",
            f"- `local_ci_lanes_executed`: `{diagnosis.get('local_ci_lanes_executed')}`",
            f"- `dispatch_allowed`: `{diagnosis.get('dispatch_allowed')}`",
            f"- `rerun_gate`: `{diagnosis.get('rerun_gate')}`",
            f"- `summary`: {diagnosis.get('summary')}",
        ]
    )
    for group in diagnosis.get("groups") or []:
        if not isinstance(group, dict):
            continue
        lanes = ", ".join(f"`{lane}`" for lane in group.get("lanes", []))
        refs = ", ".join(f"`{ref}`" for ref in group.get("source_refs", [])) or "`unknown`"
        lines.append(
            f"  - `{group.get('category')}` confidence=`{group.get('confidence')}` lanes={lanes} source_refs={refs}"
        )
    source_notes = local_ci["current_source_notes"]
    lines.extend(
        [
            "",
            "### Current Source Notes",
            "",
            f"- `repo`: `{source_notes['repo']}`",
            f"- `repo_path`: `{source_notes['repo_path']}`",
            f"- `status`: `{source_notes['status']}`",
            f"- `summary`: {source_notes['summary']}",
            f"- `worktree_execute_would_include_current_source`: `{source_notes['worktree_execute_would_include_current_source']}`",
            f"- `clean_snowcubes_package_candidate`: `{source_notes['clean_snowcubes_package_candidate']}`",
            f"- `reason`: {source_notes['reason']}",
            f"- `safe_next_action`: {source_notes['safe_next_action']}",
            "- `files`:",
        ]
    )
    for file_state in source_notes["files"]:
        lines.append(
            f"  - `{file_state['path']}` tracked=`{file_state['tracked']}` "
            f"exists=`{file_state['exists']}` status=`{file_state['status']}`"
        )
    lines.append("- `adjacent_files`:")
    for file_state in source_notes["adjacent_files"]:
        lines.append(
            f"  - `{file_state['path']}` tracked=`{file_state['tracked']}` "
            f"exists=`{file_state['exists']}` status=`{file_state['status']}`"
        )
    package_delta = source_notes["package_json_delta"]
    lines.extend(
        [
            "- `package_json_delta`:",
            f"  - `status`: `{package_delta.get('status')}`",
            f"  - `required_script_present`: `{package_delta.get('required_script_present')}`",
            f"  - `clean_snowcubes_package_candidate`: `{package_delta.get('clean_snowcubes_package_candidate')}`",
            f"  - `unrelated_script_changes`: `{', '.join(package_delta.get('unrelated_script_changes') or [])}`",
            f"  - `unrelated_dependency_changes`: `{', '.join(package_delta.get('unrelated_dependency_changes') or [])}`",
            f"  - `summary`: {package_delta.get('summary')}",
        ]
    )
    clean_candidate = source_notes.get("clean_source_candidate") or {}
    lines.extend(
        [
            "- `clean_source_candidate`:",
            f"  - `status`: `{clean_candidate.get('status')}`",
            f"  - `source_ref`: `{clean_candidate.get('source_ref')}`",
            f"  - `worktree`: `{clean_candidate.get('worktree')}`",
            f"  - `evidence_path`: `{clean_candidate.get('evidence_path')}`",
            f"  - `worktree_clean`: `{clean_candidate.get('worktree_clean')}`",
            f"  - `commit_matches_source_ref`: `{clean_candidate.get('commit_matches_source_ref')}`",
            f"  - `forbidden_files_present`: `{', '.join(clean_candidate.get('forbidden_files_present') or [])}`",
            f"  - `summary`: {clean_candidate.get('summary')}",
        ]
    )
    tracker = source_notes.get("tracker_diagnosis") or {}
    lines.extend(
        [
            "- `tracker_diagnosis`:",
            f"  - `status`: `{tracker.get('status')}`",
            f"  - `canonical_tracker`: `{tracker.get('canonical_tracker')}`",
            f"  - `canonical_tracker_exists`: `{tracker.get('canonical_tracker_exists')}`",
            f"  - `canonical_complete`: `{tracker.get('canonical_complete')}`",
            f"  - `candidate_count`: `{tracker.get('candidate_count')}`",
            f"  - `summary`: {tracker.get('summary')}",
            f"  - `private_fields_redacted`: `{tracker.get('private_fields_redacted')}`",
        ]
    )
    recommendation = tracker.get("recommended_candidate") if isinstance(tracker.get("recommended_candidate"), dict) else {}
    if recommendation:
        lines.extend(
            [
                "  - `recommended_candidate`:",
                f"    - `path`: `{recommendation.get('path')}`",
                f"    - `latest_mtime`: `{recommendation.get('latest_mtime')}`",
                f"    - `total_size_bytes`: `{recommendation.get('total_size_bytes')}`",
                f"    - `total_line_count`: `{recommendation.get('total_line_count')}`",
                f"    - `restore_requires_explicit_approval`: `{recommendation.get('restore_requires_explicit_approval')}`",
                f"    - `local_ci_execute_requires_explicit_approval`: `{recommendation.get('local_ci_execute_requires_explicit_approval')}`",
                f"    - `product_authority_unproven`: `{recommendation.get('product_authority_unproven')}`",
                f"    - `summary`: {recommendation.get('summary')}",
            ]
        )
    approval_packet = source_notes.get("approval_packet") or {}
    lines.extend(
        [
            "- `approval_packet`:",
            f"  - `exists`: `{approval_packet.get('exists')}`",
            f"  - `path`: `{approval_packet.get('path')}`",
            f"  - `status`: `{approval_packet.get('status')}`",
            f"  - `readonly`: `{approval_packet.get('readonly')}`",
            f"  - `tracker_files_copied`: `{approval_packet.get('tracker_files_copied')}`",
            f"  - `local_ci_lanes_executed`: `{approval_packet.get('local_ci_lanes_executed')}`",
            f"  - `candidate_path`: `{approval_packet.get('candidate_path')}`",
            f"  - `candidate_ready`: `{approval_packet.get('candidate_ready')}`",
            f"  - `source_ref`: `{approval_packet.get('source_ref')}`",
            f"  - `source_ref_ready`: `{approval_packet.get('source_ref_ready')}`",
            f"  - `canonical_tracker_complete`: `{approval_packet.get('canonical_tracker_complete')}`",
            f"  - `approval_gate_status`: `{approval_packet.get('approval_gate_status')}`",
            f"  - `summary`: {approval_packet.get('summary')}",
        ]
    )
    for candidate in tracker.get("off_canonical_candidates", [])[:5]:
        if not isinstance(candidate, dict):
            continue
        files = candidate.get("files") if isinstance(candidate.get("files"), dict) else {}
        git = candidate.get("git") if isinstance(candidate.get("git"), dict) else {}
        lines.extend(
            [
                f"  - `candidate`: `{candidate.get('path')}`",
                f"    - `git_head`: `{git.get('head')}`",
                f"    - `git_status`: `{git.get('status_short_branch')}`",
            ]
        )
        for name in tracker.get("required_files", []):
            metadata = files.get(name) if isinstance(files.get(name), dict) else {}
            lines.append(
                f"    - `{name}` exists=`{metadata.get('exists')}` "
                f"size=`{metadata.get('size_bytes')}` lines=`{metadata.get('line_count')}` "
                f"mtime=`{metadata.get('mtime')}`"
            )
    lines.extend(["", "### Manifest Blocking Repos", ""])
    for repo in local_ci["manifest_blocking_repos"]:
        lines.append(f"- `{repo['repo']}`: `{repo['portability_status']}` - {repo['summary']}")
    mcp = local_ci["loaded_mcp_client"]
    lines.extend(
        [
            "",
            "### Loaded MCP Client",
            "",
            f"- `status`: `{mcp['status']}`",
            f"- `claim_status`: `{mcp['claim_status']}`",
            f"- `summary`: {mcp['summary']}",
            f"- `refresh_run_id`: `{mcp['refresh_run_id']}`",
            f"- `refresh_verdict`: `{mcp['refresh_verdict']}`",
            f"- `effective_stale_process_count`: `{mcp.get('effective_stale_process_count')}`",
            f"- `historical_stale_process_count`: `{mcp.get('historical_stale_process_count')}`",
            f"- `process_count`: `{mcp['process_count']}`",
            "",
        ]
    )
    lines.extend(["## Criteria", ""])
    for item in payload["criteria"]:
        lines.extend(
            [
                f"### {item['label']}",
                "",
                f"- `id`: `{item['id']}`",
                f"- `status`: `{item['status']}`",
                f"- `resume_class`: `{item.get('resume_class')}`",
                f"- `summary`: {item['summary']}",
            ]
        )
        if item["blockers"]:
            lines.append("- `blockers`:")
            for blocker in item["blockers"]:
                lines.append(f"  - {blocker}")
        if item["next_resume"]:
            lines.append("- `next_resume`:")
            for resume in item["next_resume"]:
                lines.append(f"  - {resume}")
        if item["evidence"]:
            lines.append("- `evidence`:")
            for evidence in item["evidence"]:
                if evidence.get("type") == "path":
                    lines.append(
                        f"  - `{evidence.get('path')}` exists=`{evidence.get('exists')}` - {evidence.get('note')}"
                    )
                else:
                    suffix = f":{evidence['line']}" if evidence.get("line") else ""
                    lines.append(f"  - `{evidence['path']}{suffix}` pattern=`{evidence['pattern']}`")
        lines.append("")
    lines.extend(["## Non-Claims", ""])
    for item in payload["non_claims"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the local operator goal against current evidence.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Vidux repository root.")
    parser.add_argument("--verified-alive-report", type=Path, default=None, help="Verified-alive runner report JSON.")
    parser.add_argument("--deferrals", type=Path, default=None, help="M24 deferrals firewall JSON.")
    parser.add_argument("--plan", type=Path, default=None, help="FirstBite plan path.")
    parser.add_argument("--moussey-repo", type=Path, default=DEFAULT_MOUSSEY_REPO, help="Canonical Moussey repo path.")
    parser.add_argument(
        "--moussey-base-url",
        default=DEFAULT_MOUSSEY_BASE_URL,
        help="Local Moussey base URL for read-only route probes.",
    )
    parser.add_argument("--litty-repo", type=Path, default=DEFAULT_LITTY_REPO, help="Canonical Litty repo path.")
    parser.add_argument(
        "--litty-base-url",
        default=DEFAULT_LITTY_BASE_URL,
        help="Local Litty base URL for read-only route probes.",
    )
    parser.add_argument(
        "--snowcubes-canonical-tracker",
        type=Path,
        default=DEFAULT_SNOWCUBES_CANONICAL_TRACKER,
        help="Canonical Snowcubes tracker directory expected by the readiness lane.",
    )
    parser.add_argument(
        "--snowcubes-tracker-search-root",
        type=Path,
        default=DEFAULT_SNOWCUBES_TRACKER_SEARCH_ROOT,
        help="Root to scan for off-canonical Snowcubes tracker candidates.",
    )
    parser.add_argument("--write-json", type=Path, default=None, help="Optional output JSON path.")
    parser.add_argument("--write-markdown", type=Path, default=None, help="Optional output markdown path.")
    parser.add_argument("--markdown", action="store_true", help="Print markdown instead of JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    verified_alive = args.verified_alive_report or _latest_file(DEFAULT_VERIFIED_ALIVE_GLOB)
    deferrals = args.deferrals or _latest_file(DEFAULT_DEFERRALS_GLOB, root=repo_root)
    try:
        payload = build_payload(
            repo_root=repo_root,
            verified_alive_report_path=verified_alive,
            deferrals_path=deferrals,
            plan_path=args.plan,
            moussey_repo_path=args.moussey_repo,
            moussey_base_url=args.moussey_base_url,
            litty_repo_path=args.litty_repo,
            litty_base_url=args.litty_base_url,
            snowcubes_canonical_tracker=args.snowcubes_canonical_tracker,
            snowcubes_tracker_search_root=args.snowcubes_tracker_search_root,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(f"{SCRIPT_NAME}: {exc}") from exc

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
