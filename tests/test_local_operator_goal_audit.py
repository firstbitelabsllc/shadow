"""Tests for scripts/vidux-local-operator-goal-audit.py."""

from __future__ import annotations

import importlib.util
import json
import http.server
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-local-operator-goal-audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vidux_local_operator_goal_audit", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


goal_audit = _load_module()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class _OkHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/chat/providers":
            body = json.dumps(
                {
                    "defaultProvider": "local",
                    "providers": {
                        "local": {"ready": True, "message": "gpt-oss:20b ready"},
                        "local-mlx": {"ready": True, "message": "mlx ready"},
                        "codex": {"ready": True, "message": "Codex CLI installed"},
                        "claude": {
                            "ready": False,
                            "message": "Claude CLI auth failed recently on this Mac; sign in again with `claude`.",
                        },
                    },
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/contracts?view=claude-mega-goal":
            body = json.dumps({"ok": True, "view": "claude-mega-goal"}).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<html><body>ok</body></html>")

    def log_message(self, format: str, *args: object) -> None:
        return


class _FirstProbeSlowHandler(http.server.BaseHTTPRequestHandler):
    request_count = 0

    def do_GET(self) -> None:
        type(self).request_count += 1
        if type(self).request_count == 1:
            time.sleep(0.08)
        body = b"<html><body>ok</body></html>"
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            return

    def log_message(self, format: str, *args: object) -> None:
        return


def _start_ok_server() -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def _start_first_probe_slow_server() -> tuple[http.server.HTTPServer, str]:
    _FirstProbeSlowHandler.request_count = 0
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FirstProbeSlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def _write_deferred_perf_ui_evidence(root: Path, moussey_repo: Path) -> None:
    for spec in goal_audit.MOUSSEY_DEFERRED_PERF_UI_EVIDENCE:
        base = moussey_repo if spec["path_kind"] == "moussey" else root
        path = base / spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"redacted proof placeholder\n")


def _write_chat_front_door_evidence(root: Path, moussey_repo: Path) -> None:
    for spec in goal_audit.MOUSSEY_CHAT_FRONT_DOOR_EVIDENCE:
        base = moussey_repo if spec["path_kind"] == "moussey" else root
        path = base / spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"redacted proof placeholder\n")


def _write_litty_boundary_evidence(root: Path, litty_repo: Path) -> None:
    for spec in goal_audit.LITTY_COCKPIT_BOUNDARY_EVIDENCE:
        base = litty_repo if spec["path_kind"] == "litty" else root
        path = base / spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "AGENTS.md":
            path.write_text(
                "Litty is the standalone cockpit\n"
                "Moussey stays the LAN/data hub\n"
                "Do not port or copy Moussey's old UI\n",
                encoding="utf-8",
            )
        elif path.name == "PLAN.md" and path.parent.name == "litty" and "projects" in path.parts:
            path.write_text(
                "Litty extracts the cockpit logic\n"
                "Moussey stays as the LAN routing/data hub\n"
                "C225 publish step completed\n"
                "C226 Goose local-driver trust summary completed\n",
                encoding="utf-8",
            )
        else:
            path.write_bytes(b"redacted proof placeholder\n")


def _init_dirty_moussey_repo(root: Path) -> Path:
    repo = root / "moussey"
    (repo / ".firstbite").mkdir(parents=True)
    (repo / "app" / "api" / "snowcubes" / "shopify-invoice").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    (repo / ".firstbite" / "local-ci.json").write_text("{}", encoding="utf-8")
    (repo / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
    (repo / "package-lock.json").write_text('{"name":"moussey","lockfileVersion":3}\n', encoding="utf-8")
    (repo / "app" / "api" / "snowcubes" / "shopify-invoice" / "route.ts").write_text(
        "export {};\n",
        encoding="utf-8",
    )
    (repo / "app" / "api" / "snowcubes" / "shopify-invoice" / "route.test.ts").write_text(
        "import 'node:test';\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "snowcubes-invoice-readiness.ts").write_text("export {};\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(
        [
            "git",
            "add",
            ".firstbite/local-ci.json",
            "package.json",
            "package-lock.json",
            "app/api/snowcubes/shopify-invoice/route.ts",
            "app/api/snowcubes/shopify-invoice/route.test.ts",
            "scripts/snowcubes-invoice-readiness.ts",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Vidux Test",
            "-c",
            "user.email=vidux-test@example.invalid",
            "commit",
            "-m",
            "seed",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    (repo / ".firstbite" / "local-ci.json").write_text('{"changed":true}\n', encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "test:snowcubes:invoice:e2e-bundle": "tsx script.ts",
                    "test:slack": "tsx slack.ts",
                },
                "dependencies": {"@slack/bolt": "^4.7.3"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "package-lock.json").write_text('{"name":"moussey","lockfileVersion":3,"changed":true}\n', encoding="utf-8")
    (repo / "app" / "api" / "snowcubes" / "shopify-invoice" / "route.ts").write_text(
        "export const changed = true;\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "snowcubes-invoice-readiness.ts").write_text("export const changed = true;\n", encoding="utf-8")
    (repo / "scripts" / "snowcubes-invoice-e2e-bundle.ts").write_text("export const blocker = true;\n", encoding="utf-8")
    return repo


def _init_clean_snowcubes_candidate(root: Path) -> tuple[Path, str]:
    repo = root / "moussey-candidate"
    (repo / ".firstbite").mkdir(parents=True)
    (repo / "app" / "api" / "snowcubes" / "shopify-invoice").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    seed_files = {
        ".firstbite/local-ci.json": "{}\n",
        "package.json": '{"scripts":{}}\n',
        "package-lock.json": '{"name":"moussey","lockfileVersion":3}\n',
        "app/api/snowcubes/shopify-invoice/route.ts": "export {};\n",
        "app/api/snowcubes/shopify-invoice/route.test.ts": "import 'node:test';\n",
        "scripts/snowcubes-invoice-readiness.ts": "export {};\n",
    }
    for rel, contents in seed_files.items():
        (repo / rel).write_text(contents, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Vidux Test",
            "-c",
            "user.email=vidux-test@example.invalid",
            "commit",
            "-m",
            "seed",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = {
        ".firstbite/local-ci.json": '{"lanes":["moussey_snowcubes_readiness"]}\n',
        "package.json": '{"scripts":{"test:snowcubes:invoice:e2e-bundle":"tsx scripts/snowcubes-invoice-e2e-bundle.ts"}}\n',
        "app/api/snowcubes/shopify-invoice/route.ts": "export const changed = true;\n",
        "app/api/snowcubes/shopify-invoice/route.test.ts": "import 'node:test';\nexport const changed = true;\n",
        "scripts/snowcubes-invoice-readiness.ts": "export const changed = true;\n",
        "scripts/snowcubes-invoice-e2e-bundle.ts": "export const blocker = true;\n",
    }
    for rel, contents in changed_files.items():
        (repo / rel).write_text(contents, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Vidux Test",
            "-c",
            "user.email=vidux-test@example.invalid",
            "commit",
            "-m",
            "package snowcubes local-ci source",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return repo, head


def _init_off_canonical_tracker_candidate(root: Path) -> Path:
    repo = root / "trysnowcubes-web-worktrees" / "reviews-otel-traces"
    tracker = repo / "outputs" / "consignment-tracker"
    tracker.mkdir(parents=True)
    (tracker / "snowcubes-consignment-partners.csv").write_text("redacted\n", encoding="utf-8")
    (tracker / "snowcubes-consignment-live-ledger.csv").write_text("redacted\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Vidux Test",
            "-c",
            "user.email=vidux-test@example.invalid",
            "commit",
            "-m",
            "seed tracker",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return tracker


def _write_snowcubes_approval_packet(root: Path, tracker_candidate: Path, source_ref: str) -> Path:
    packet = (
        root
        / "projects"
        / "firstbite-local-ci-mega"
        / "evidence"
        / "2026-06-01-snowcubes-readiness-approval-packet.json"
    )
    _write_json(
        packet,
        {
            "status": "ready_for_approval",
            "summary": "Approval packet is ready for operator review.",
            "readonly": True,
            "tracker_files_copied": False,
            "local_ci_lanes_executed": False,
            "approval_required": True,
            "restore_requires_explicit_approval": True,
            "execute_requires_explicit_approval": True,
            "required_files": [
                "snowcubes-consignment-partners.csv",
                "snowcubes-consignment-live-ledger.csv",
            ],
            "candidate": {"path": str(tracker_candidate), "ready": True},
            "source_ref": {"ref": source_ref, "ready": True},
            "canonical_tracker": {"complete": False},
            "checks": [
                {
                    "id": "approval_gate",
                    "status": "operator_gated",
                    "summary": "Restore/provide and run_lanes execute are not performed by this packet.",
                }
            ],
        },
    )
    return packet


def _write_nonpass_diagnosis(root: Path) -> Path:
    packet = (
        root
        / "projects"
        / "firstbite-local-ci-mega"
        / "evidence"
        / "2026-06-02-m66-current-nonpass-diagnosis.json"
    )
    _write_json(
        packet,
        {
            "mode": "read_only_failed_execute_diagnosis",
            "failed_lane_count": 1,
            "visible_failed_lane_count": 1,
            "aggregate_nonpass_lane_count": 2,
            "undocumented_nonpass_lane_count": 1,
            "diagnosis_coverage_status": "partial",
            "group_count": 1,
            "groups": [
                {
                    "category": "snowcubes_generated_e2e_bundle_status",
                    "summary": "Snowcubes readiness expected generated E2E bundle status",
                    "confidence": "high",
                    "lanes": ["moussey_snowcubes_readiness"],
                    "source_refs": ["5706b2884943bb665faddaf4b7e3e37023782422"],
                    "rerun_gate": "operator_approval_required",
                }
            ],
            "next_resume": {
                "local_ci_lanes_executed": False,
                "dispatch_allowed": False,
                "rerun_gate": "operator_approval_required",
                "diagnosis_coverage_status": "partial",
                "undocumented_nonpass_lane_count": 1,
                "summary": "Diagnoses are read-only.",
            },
        },
    )
    return packet


class LocalOperatorGoalAuditTests(unittest.TestCase):
    def test_build_payload_maps_done_criteria_without_claiming_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            moussey_repo = _init_dirty_moussey_repo(root)
            litty_repo = root / "litty"
            _write_chat_front_door_evidence(root, moussey_repo)
            plan = root / "projects" / "firstbite-local-ci-mega" / "PLAN.md"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                "\n".join(
                    [
                        "- [completed] LCQ-5 local chat proof.",
                        "- [blocked] M3: LaunchAgent handoff.",
                        "- [completed] M7: Litty lane smoke.",
                        "- [completed] M23/P4 verified-alive.",
                        "- Moussey compact local-CI view now surfaces the latest MCP refresh packet.",
                        "- Captain skill audit refreshed for the local operator stack.",
                        "- Verified-alive now carries Captain setup health.",
                        "- Verified-alive runner summary now names the resume checks directly.",
                    ]
                ),
                encoding="utf-8",
            )
            report = root / "report.json"
            local_ci_input = root / "local-ci.json"
            _write_json(
                local_ci_input,
                {
                    "launchTrust": {
                        "status": "blocked",
                        "summary": "4/12 launch trust gate(s) ready; 3 blocked; 5 warning/unknown.",
                        "readyGateCount": 4,
                        "blockedGateCount": 3,
                        "warningGateCount": 5,
                        "totalGateCount": 12,
                        "gates": [
                            {
                                "id": "declared-lanes",
                                "label": "Declared Lanes",
                                "status": "blocked",
                                "summary": "40/43 declared pass; 3 non-pass; 0 stale/missing.",
                                "action": {"label": "Rerun lane", "runOn": "Mac Studio", "safety": "worktree"},
                            },
                            {
                                "id": "disk-headroom",
                                "label": "Disk Headroom",
                                "status": "warning",
                                "summary": "disk warning",
                            },
                        ],
                    },
                    "failingLanes": [
                        {
                            "repo": "Moussey",
                            "lane": "moussey_snowcubes_readiness",
                            "status": "fail",
                            "rc": 1,
                            "reason": "command exited with code 1",
                            "reportPath": "/tmp/report.json",
                            "logPath": "/tmp/run.log",
                        }
                    ],
                    "manifestReadiness": {
                        "blockingRepos": [
                            {
                                "repo": "Moussey",
                                "status": "warning",
                                "portabilityStatus": "tracked_uncommitted",
                                "summary": "active checkout dirty",
                            }
                        ]
                    },
                    "runnerReadiness": {
                        "mcpClient": {
                            "status": "stale_processes_visible",
                            "claimStatus": "blocked",
                            "summary": "5/5 loaded MCP process(es) are stale",
                            "latestRefreshPlan": {
                                "runId": "refresh-1",
                                "verdict": "stale_loaded_clients_need_host_app_restart",
                                "staleProcessCount": 5,
                                "processCount": 5,
                                "readOnly": True,
                                "reportPath": "/tmp/refresh-report.json",
                            },
                        }
                    },
                },
            )
            _write_json(
                report,
                {
                    "rollup": {
                        "inputs": {"local_ci": str(local_ci_input)},
                        "checks": [
                            {
                                "id": "moussey_local_ci_endpoint",
                                "status": "warning",
                                "summary": "Moussey local-CI endpoint responds",
                                "facts": {
                                    "launch_trust_status": "blocked",
                                    "mcp_refresh_verdict": "stale_loaded_clients_need_host_app_restart",
                                },
                            },
                            {
                                "id": "chat_front_door",
                                "status": "warning",
                                "summary": "local chat works, but escalation providers are gated",
                            },
                            {
                                "id": "captain_setup_health",
                                "status": "warning",
                                "summary": "Captain audit exits 0 with setup-policy warnings",
                            },
                            {
                                "id": "drift_tile",
                                "status": "ready",
                                "summary": "dispatch remains observe-only",
                            },
                        ]
                    }
                },
            )
            deferrals = root / "deferrals.json"
            _write_json(deferrals, {"status": "ready"})
            nonpass_diagnosis = _write_nonpass_diagnosis(root)

            payload = goal_audit.build_payload(
                repo_root=root,
                verified_alive_report_path=report,
                deferrals_path=deferrals,
                plan_path=plan,
                moussey_repo_path=moussey_repo,
                moussey_base_url="http://127.0.0.1:9",
                litty_repo_path=litty_repo,
                litty_base_url="http://127.0.0.1:9",
                snowcubes_canonical_tracker=root / "missing-canonical" / "outputs" / "consignment-tracker",
                snowcubes_tracker_search_root=root,
            )

            self.assertEqual(payload["status"], "incomplete")
            self.assertIn("full goal remains active", payload["summary"])
            criteria = {item["id"]: item for item in payload["criteria"]}
            self.assertEqual(criteria["local_ci_current_machine"]["status"], "partial")
            self.assertIn("launchTrust=blocked", criteria["local_ci_current_machine"]["summary"])
            self.assertEqual(criteria["moussey_deferred_perf_ui"]["status"], "partial")
            self.assertEqual(criteria["chat_operator_front_door"]["status"], "partial")
            self.assertEqual(criteria["mobile_operator_rows"]["status"], "gated")
            self.assertEqual(criteria["captain_setup_health"]["status"], "documented_non_blocking")
            self.assertEqual(criteria["remaining_work_classified"]["status"], "partial")
            self.assertEqual(payload["status_counts"]["partial"], 6)
            self.assertEqual(payload["status_counts"]["gated"], 1)
            self.assertEqual(payload["status_counts"]["documented_non_blocking"], 1)
            self.assertEqual(payload["recommended_next_goal"]["first_resume_criterion"], "local_ci_current_machine")
            self.assertEqual(payload["recommended_next_goal"]["first_resume_class"], "operator_gated")
            self.assertEqual(payload["next_resume_order"][0]["criterion_id"], "local_ci_current_machine")
            self.assertEqual(payload["next_resume_order"][0]["resume_class"], "operator_gated")
            self.assertEqual(payload["next_resume_order"][-1]["criterion_id"], "mobile_operator_rows")
            self.assertEqual(payload["next_resume_order"][-1]["resume_class"], "operator_gated")
            self.assertEqual(payload["local_ci_launch_trust"]["status"], "blocked")
            self.assertEqual(payload["local_ci_launch_trust"]["blocked_gates"][0]["id"], "declared-lanes")
            self.assertEqual(payload["local_ci_launch_trust"]["failing_lanes"][0]["lane"], "moussey_snowcubes_readiness")
            diagnosis = payload["local_ci_launch_trust"]["nonpass_diagnosis"]
            self.assertTrue(diagnosis["exists"])
            self.assertEqual(diagnosis["path"], str(nonpass_diagnosis))
            self.assertEqual(diagnosis["failed_lane_count"], 1)
            self.assertEqual(diagnosis["visible_failed_lane_count"], 1)
            self.assertEqual(diagnosis["aggregate_nonpass_lane_count"], 2)
            self.assertEqual(diagnosis["undocumented_nonpass_lane_count"], 1)
            self.assertEqual(diagnosis["diagnosis_coverage_status"], "partial")
            self.assertEqual(diagnosis["group_count"], 1)
            self.assertFalse(diagnosis["local_ci_lanes_executed"])
            self.assertFalse(diagnosis["dispatch_allowed"])
            self.assertEqual(diagnosis["rerun_gate"], "operator_approval_required")
            self.assertEqual(
                diagnosis["groups"][0]["category"],
                "snowcubes_generated_e2e_bundle_status",
            )
            self.assertEqual(payload["local_ci_launch_trust"]["manifest_blocking_repos"][0]["repo"], "Moussey")
            self.assertEqual(payload["local_ci_launch_trust"]["loaded_mcp_client"]["stale_process_count"], 5)
            source_notes = payload["local_ci_launch_trust"]["current_source_notes"]
            self.assertEqual(source_notes["status"], "source_state_warning")
            self.assertFalse(source_notes["worktree_execute_would_include_current_source"])
            source_files = {item["path"]: item for item in source_notes["files"]}
            self.assertEqual(source_files[".firstbite/local-ci.json"]["status"], "M")
            self.assertEqual(source_files["package.json"]["status"], "M")
            self.assertEqual(source_files["app/api/snowcubes/shopify-invoice/route.ts"]["status"], "M")
            self.assertEqual(source_files["app/api/snowcubes/shopify-invoice/route.test.ts"]["status"], "clean")
            self.assertEqual(source_files["scripts/snowcubes-invoice-readiness.ts"]["status"], "M")
            self.assertFalse(source_files["scripts/snowcubes-invoice-e2e-bundle.ts"]["tracked"])
            self.assertEqual(source_files["scripts/snowcubes-invoice-e2e-bundle.ts"]["status"], "??")
            self.assertIn("Split the Snowcubes local-CI source package", source_notes["safe_next_action"])
            self.assertFalse(source_notes["clean_snowcubes_package_candidate"])
            adjacent_files = {item["path"]: item for item in source_notes["adjacent_files"]}
            self.assertEqual(adjacent_files["package-lock.json"]["status"], "M")
            package_delta = source_notes["package_json_delta"]
            self.assertEqual(package_delta["status"], "mixed_or_missing")
            self.assertTrue(package_delta["required_script_present"])
            self.assertIn("test:slack", package_delta["unrelated_script_changes"])
            self.assertIn("@slack/bolt", package_delta["unrelated_dependency_changes"])
            self.assertIn("did not mark the active goal complete", " ".join(payload["non_claims"]))

    def test_missing_inputs_stay_incomplete_and_identify_missing_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = goal_audit.build_payload(
                repo_root=root,
                verified_alive_report_path=None,
                deferrals_path=None,
                plan_path=root / "missing-plan.md",
                moussey_repo_path=root / "missing-moussey",
                moussey_base_url="http://127.0.0.1:9",
                litty_repo_path=root / "missing-litty",
                litty_base_url="http://127.0.0.1:9",
                snowcubes_canonical_tracker=root / "missing-canonical" / "outputs" / "consignment-tracker",
                snowcubes_tracker_search_root=root,
            )

            criteria = {item["id"]: item for item in payload["criteria"]}
            self.assertEqual(payload["status"], "incomplete")
            self.assertFalse(payload["local_ci_launch_trust"]["source_exists"])
            self.assertEqual(payload["status_counts"]["missing"], 4)
            self.assertEqual(criteria["local_ci_current_machine"]["status"], "missing")
            self.assertEqual(criteria["chat_operator_front_door"]["status"], "missing")
            self.assertEqual(criteria["mobile_operator_rows"]["status"], "missing")
            self.assertEqual(criteria["captain_setup_health"]["status"], "missing")
            self.assertEqual(payload["recommended_next_goal"]["first_resume_criterion"], "local_ci_current_machine")

    def test_clean_snowcubes_candidate_changes_resume_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            moussey_repo = _init_dirty_moussey_repo(root)
            candidate_repo, source_ref = _init_clean_snowcubes_candidate(root)
            tracker_candidate = _init_off_canonical_tracker_candidate(root)
            approval_packet_path = _write_snowcubes_approval_packet(root, tracker_candidate, source_ref)
            evidence = root / "projects" / "firstbite-local-ci-mega" / "evidence" / "2026-06-01-moussey-snowcubes-clean-source-candidate.md"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                "\n".join(
                    [
                        "# Moussey Snowcubes Clean Source Candidate",
                        "",
                        f"- Worktree: `{candidate_repo}`",
                        "- Branch: `codex/snowcubes-local-ci-source-20260601`",
                        f"- Source ref: `{source_ref}`",
                        "- Base: `seed`",
                    ]
                ),
                encoding="utf-8",
            )
            report = root / "report.json"
            local_ci_input = root / "local-ci.json"
            _write_json(
                local_ci_input,
                {
                    "launchTrust": {"status": "blocked", "summary": "blocked"},
                    "failingLanes": [],
                    "manifestReadiness": {},
                    "runnerReadiness": {
                        "mcpClient": {
                            "status": "current_only",
                            "claimStatus": "ready",
                            "summary": "10/10 loaded MCP process(es) are current",
                        },
                    },
                },
            )
            _write_json(
                report,
                {
                    "rollup": {
                        "inputs": {"local_ci": str(local_ci_input)},
                        "checks": [
                            {
                                "id": "moussey_local_ci_endpoint",
                                "status": "warning",
                                "facts": {"launch_trust_status": "blocked"},
                            }
                        ],
                    }
                },
            )

            payload = goal_audit.build_payload(
                repo_root=root,
                verified_alive_report_path=report,
                deferrals_path=None,
                plan_path=root / "missing-plan.md",
                moussey_repo_path=moussey_repo,
                moussey_base_url="http://127.0.0.1:9",
                litty_repo_path=root / "missing-litty",
                litty_base_url="http://127.0.0.1:9",
                snowcubes_canonical_tracker=root / "missing-canonical" / "outputs" / "consignment-tracker",
                snowcubes_tracker_search_root=root,
            )

            source_notes = payload["local_ci_launch_trust"]["current_source_notes"]
            self.assertEqual(source_notes["status"], "clean_source_candidate_ready")
            self.assertTrue(source_notes["clean_snowcubes_package_candidate"])
            self.assertIn(source_ref, source_notes["safe_next_action"])
            self.assertIn("approval packet", source_notes["safe_next_action"])
            self.assertIn(str(approval_packet_path), source_notes["safe_next_action"])
            criteria = {item["id"]: item for item in payload["criteria"]}
            self.assertEqual(criteria["local_ci_current_machine"]["status"], "gated")
            self.assertEqual(criteria["local_ci_current_machine"]["resume_class"], "operator_gated")
            self.assertIn("remaining restore/execute work is operator-gated", criteria["local_ci_current_machine"]["summary"])
            self.assertIn(
                "moussey_snowcubes_readiness execute requires explicit local-CI approval.",
                criteria["local_ci_current_machine"]["blockers"],
            )
            next_rows = {item["criterion_id"]: item for item in payload["next_resume_order"]}
            self.assertEqual(next_rows["local_ci_current_machine"]["resume_class"], "operator_gated")
            approval_packet = source_notes["approval_packet"]
            self.assertTrue(approval_packet["exists"])
            self.assertEqual(approval_packet["path"], str(approval_packet_path))
            self.assertEqual(approval_packet["status"], "ready_for_approval")
            self.assertTrue(approval_packet["readonly"])
            self.assertFalse(approval_packet["tracker_files_copied"])
            self.assertFalse(approval_packet["local_ci_lanes_executed"])
            self.assertEqual(approval_packet["candidate_path"], str(tracker_candidate))
            self.assertTrue(approval_packet["candidate_ready"])
            self.assertEqual(approval_packet["source_ref"], source_ref)
            self.assertTrue(approval_packet["source_ref_ready"])
            self.assertFalse(approval_packet["canonical_tracker_complete"])
            self.assertEqual(approval_packet["approval_gate_status"], "operator_gated")
            candidate = source_notes["clean_source_candidate"]
            self.assertEqual(candidate["status"], "ready")
            self.assertEqual(candidate["source_ref"], source_ref)
            self.assertTrue(candidate["worktree_clean"])
            self.assertTrue(candidate["commit_matches_source_ref"])
            self.assertNotIn("package-lock.json", candidate["changed_files"])
            tracker = source_notes["tracker_diagnosis"]
            self.assertEqual(tracker["status"], "candidate_data_present_off_canonical")
            self.assertEqual(tracker["candidate_count"], 1)
            self.assertEqual(tracker["off_canonical_candidates"][0]["path"], str(tracker_candidate))
            self.assertEqual(
                tracker["off_canonical_candidates"][0]["files"]["snowcubes-consignment-live-ledger.csv"]["line_count"],
                1,
            )
            self.assertEqual(tracker["recommended_candidate"]["path"], str(tracker_candidate))
            self.assertTrue(tracker["recommended_candidate"]["restore_requires_explicit_approval"])
            self.assertTrue(tracker["recommended_candidate"]["local_ci_execute_requires_explicit_approval"])
            self.assertTrue(tracker["recommended_candidate"]["product_authority_unproven"])
            self.assertTrue(tracker["private_fields_redacted"])

    def test_deferred_perf_ui_ready_when_evidence_and_routes_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            moussey_repo = _init_dirty_moussey_repo(root)
            litty_repo = root / "litty"
            _write_deferred_perf_ui_evidence(root, moussey_repo)
            _write_chat_front_door_evidence(root, moussey_repo)
            _write_litty_boundary_evidence(root, litty_repo)
            report = root / "report.json"
            local_ci_input = root / "local-ci.json"
            _write_json(local_ci_input, {"launchTrust": {"status": "blocked", "summary": "blocked"}})
            _write_json(
                report,
                {
                    "rollup": {
                        "inputs": {"local_ci": str(local_ci_input)},
                        "checks": [
                            {
                                "id": "moussey_local_ci_endpoint",
                                "status": "warning",
                                "facts": {"launch_trust_status": "blocked"},
                            }
                        ],
                    }
                },
            )
            server, base_url = _start_ok_server()
            self.addCleanup(server.shutdown)
            self.addCleanup(server.server_close)

            payload = goal_audit.build_payload(
                repo_root=root,
                verified_alive_report_path=report,
                deferrals_path=None,
                plan_path=root / "missing-plan.md",
                moussey_repo_path=moussey_repo,
                moussey_base_url=base_url,
                litty_repo_path=litty_repo,
                litty_base_url=base_url,
                snowcubes_canonical_tracker=root / "missing-canonical" / "outputs" / "consignment-tracker",
                snowcubes_tracker_search_root=root,
            )

            audit = payload["moussey_deferred_perf_ui"]
            self.assertEqual(audit["status"], "ready")
            self.assertFalse(audit["missing_evidence"])
            self.assertFalse(audit["failed_routes"])
            criteria = {item["id"]: item for item in payload["criteria"]}
            self.assertEqual(criteria["moussey_deferred_perf_ui"]["status"], "ready")
            self.assertEqual(criteria["chat_operator_front_door"]["status"], "gated")
            self.assertNotIn("moussey_deferred_perf_ui", [item["criterion_id"] for item in payload["next_resume_order"]])
            chat = payload["chat_operator_front_door"]
            self.assertTrue(chat["providers"]["local_ready"])
            self.assertTrue(chat["providers"]["codex_ready"])
            self.assertFalse(chat["providers"]["claude_ready"])
            self.assertTrue(chat["providers"]["claude_auth_gated"])
            self.assertIn("Claude escalation is credential-gated", chat["credential_gates"][0])
            chat_evidence = {item["id"]: item for item in chat["evidence"]}
            self.assertTrue(chat_evidence["chat_front_door_routing_packet"]["exists"])
            self.assertTrue(chat_evidence["chat_routes_sheet_mobile"]["exists"])
            self.assertTrue(chat_evidence["chat_target_picker_mobile"]["exists"])

    def test_local_route_probe_retries_transient_cold_timeout(self):
        server, base_url = _start_first_probe_slow_server()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)

        probe = goal_audit._probe_local_route(
            base_url,
            "/workers",
            timeout_seconds=0.01,
            attempts=2,
            retry_delay_seconds=0.01,
        )

        self.assertTrue(probe["ok"])
        self.assertEqual(probe["status"], 200)
        self.assertEqual(probe["attempts"], 2)
        self.assertGreaterEqual(len(probe["errors"]), 1)

    def test_local_ci_launch_trust_marks_loaded_mcp_effectively_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_ci = root / "local-ci.json"
            _write_json(
                local_ci,
                {
                    "launchTrust": {"status": "blocked", "summary": "blocked"},
                    "runnerReadiness": {
                        "mcpClient": {
                            "status": "current_only",
                            "claimStatus": "ready",
                            "latestRefreshPlan": {
                                "runId": "older-refresh",
                                "verdict": "stale_loaded_clients_need_host_app_restart",
                                "staleProcessCount": 5,
                                "processCount": 5,
                                "readOnly": True,
                                "reportPath": "/tmp/older-refresh/report.json",
                            },
                        },
                    },
                },
            )
            report = {"rollup": {"inputs": {"local_ci": str(local_ci)}}}

            launch_trust = goal_audit._local_ci_launch_trust(report, repo_root=root)

            self.assertTrue(launch_trust["loaded_mcp_client"]["effective_ready"])
            self.assertEqual(launch_trust["loaded_mcp_client"]["claim_status"], "ready")
            self.assertEqual(launch_trust["loaded_mcp_client"]["status"], "current_only")
            self.assertEqual(
                launch_trust["loaded_mcp_client"]["refresh_verdict"],
                "stale_loaded_clients_need_host_app_restart",
            )
            self.assertEqual(
                launch_trust["loaded_mcp_client"]["historical_stale_process_count"],
                5,
            )
            self.assertEqual(
                launch_trust["loaded_mcp_client"]["effective_stale_process_count"],
                0,
            )

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "projects" / "firstbite-local-ci-mega" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("- Verified-alive runner summary now names the resume checks directly.\n", encoding="utf-8")
            report = root / "report.json"
            _write_json(report, {"rollup": {"checks": []}})
            deferrals = root / "deferrals.json"
            _write_json(deferrals, {"status": "ready"})
            _write_nonpass_diagnosis(root)
            out_json = root / "audit.json"
            out_md = root / "audit.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(root),
                    "--verified-alive-report",
                    str(report),
                    "--deferrals",
                    str(deferrals),
                    "--plan",
                    str(plan),
                    "--moussey-repo",
                    str(root / "missing-moussey"),
                    "--moussey-base-url",
                    "http://127.0.0.1:9",
                    "--litty-repo",
                    str(root / "missing-litty"),
                    "--litty-base-url",
                    "http://127.0.0.1:9",
                    "--snowcubes-canonical-tracker",
                    str(root / "missing-canonical" / "outputs" / "consignment-tracker"),
                    "--snowcubes-tracker-search-root",
                    str(root),
                    "--write-json",
                    str(out_json),
                    "--write-markdown",
                    str(out_md),
                    "--markdown",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Local Operator Goal Audit", result.stdout)
            self.assertEqual(json.loads(out_json.read_text())["status"], "incomplete")
            markdown = out_md.read_text()
            self.assertIn("## Recommended Next Goal", markdown)
            self.assertIn("## Resume Order", markdown)
            self.assertIn("## Chat Operator Front Door", markdown)
            self.assertIn("## Litty Cockpit Boundaries", markdown)
            self.assertIn("## Local CI Launch Trust", markdown)
            self.assertIn("### Non-Pass Diagnosis", markdown)
            self.assertIn("snowcubes_generated_e2e_bundle_status", markdown)
            self.assertIn("clean_source_candidate", markdown)
            self.assertIn("tracker_diagnosis", markdown)
            self.assertIn("approval_packet", markdown)
            self.assertIn("## Criteria", markdown)


if __name__ == "__main__":
    unittest.main()
