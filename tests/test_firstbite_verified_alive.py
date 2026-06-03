"""Tests for scripts/vidux-firstbite-verified-alive.py."""

from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-firstbite-verified-alive.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vidux_firstbite_verified_alive", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verified_alive = _load_module()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class FirstBiteVerifiedAliveTests(unittest.TestCase):
    def test_build_payload_rolls_up_ready_warning_and_non_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = root / "status.json"
            retention = root / "retention.json"
            observe = root / "observe.json"
            health = root / "health.json"
            providers = root / "providers.json"
            local_ci = root / "local-ci.json"
            captain = root / "captain-audit.json"

            _write_json(
                status,
                {
                    "catalog": {"lane_count": 43, "repo_count": 6, "catalog_stale": False},
                    "freshness_contract": {
                        "catalog_stale": False,
                        "catalog_age_seconds": 3,
                        "stale_proof_count": 5,
                        "unknown_proof_age_count": 1,
                        "rule": "passing lanes need current-source proof",
                    },
                    "latest_lane_proof": [{"lane": "alpha"}],
                    "disk_guard": {
                        "status": "warning",
                        "live_headroom": {
                            "disk_available_gib": 41,
                            "disk_capacity_percent": 96,
                            "write_floor_blocked": False,
                        },
                    },
                },
            )
            _write_json(
                retention,
                {
                    "readonly": True,
                    "deletion_performed": False,
                    "install_performed": False,
                    "cadence_seconds": 1800,
                    "totals": {
                        "approval_required_gib": 11.94,
                        "proof_prune_candidate_count": 307,
                        "cache_prune_candidate_count": 2,
                        "cache_active_count": 0,
                    },
                    "launchagent": {"installed": False, "template_path": "/tmp/template.plist"},
                },
            )
            _write_json(
                observe,
                {
                    "advisory_count": 5,
                    "plan_lint": {
                        "status": "ready",
                        "record_counts": {"already_recorded": 5, "missing_record": 0},
                    },
                    "dispatch_policy": {
                        "status": "observe_only",
                        "dispatch_allowed": False,
                        "blockers": ["m22_observe_only_brake"],
                        "cockpit_gate": {"allowed": False},
                    },
                },
            )
            _write_json(health, {"ok": True, "codex": {"ready": True}, "hermes": {"ready": True}})
            _write_json(
                providers,
                {
                    "defaultProvider": "local",
                    "providers": {
                        "local": {"ready": True, "message": "gpt-oss:20b ready"},
                        "codex": {"ready": True, "message": "Codex CLI installed"},
                        "claude": {"ready": False, "message": "credential-gated"},
                    },
                },
            )
            _write_json(
                local_ci,
                {
                    "ok": True,
                    "launchTrust": {
                        "status": "blocked",
                        "summary": "4/12 launch trust gate(s) ready; 3 blocked",
                        "readyGateCount": 4,
                        "warningGateCount": 5,
                        "blockedGateCount": 3,
                    },
                    "runnerReadiness": {
                        "status": "warning",
                        "summary": "cockpit warning",
                        "mcpClient": {
                            "status": "stale_processes_visible",
                            "claimStatus": "blocked",
                            "latestRefreshPlan": {
                                "runId": "refresh-a",
                                "verdict": "stale_loaded_clients_need_host_app_restart",
                                "reportPath": "/tmp/refresh-a/report.json",
                                "summaryPath": "/tmp/refresh-a/summary.md",
                                "readOnly": True,
                                "killsProcesses": False,
                                "restartsApps": False,
                                "runsCi": False,
                                "mutatesRepos": False,
                                "staleProcessCount": 5,
                                "processCount": 5,
                                "laneCount": 43,
                                "declaredCount": 43,
                                "latestLanePassCount": 40,
                                "latestLaneFailCount": 3,
                            },
                        },
                    },
                    "operatorApproval": {
                        "status": "ready_for_approval",
                        "approvalGateStatus": "operator_gated",
                        "approvalPacketPath": "/tmp/approval-packet.json",
                        "candidatePath": "/tmp/consignment-tracker",
                        "candidateReady": True,
                        "sourceRef": "4a7eded7c0d5f840570d21debd9de3dc428b9320",
                        "sourceRefReady": True,
                        "canonicalTrackerComplete": False,
                        "trackerFilesCopied": False,
                        "localCiLanesExecuted": False,
                        "readonly": True,
                    },
                },
            )
            _write_json(
                captain,
                {
                    "command": ["bash", "/Users/leokwan/Development/ai/skills/captain/scripts/audit_skills.sh"],
                    "cwd": "/Users/leokwan/Development/ai",
                    "exit_code": 0,
                    "stdout": "\n".join(
                        [
                            "== Git Sync Status ==",
                            "  ahead of upstream",
                            "",
                            "== Tool Skill Roots ==",
                            "  ~/.claude/skills -> /Users/leokwan/.ai/skills-active",
                            "  ~/.codex/skills -> /Users/leokwan/.ai/skills-active",
                            "  ~/.cursor/skills -> /Users/leokwan/.ai/skills-active",
                            "",
                            "== Frontmatter Health ==",
                            "  - source:/Users/leokwan/Development/vidux/SKILL.md: WARN description 321 chars (>300)",
                            "  OK",
                            "",
                            "== Setup Policy Warnings ==",
                            "  - overlay:local-ci/SKILL.md: SETUP-POLICY missing first-screen setup section",
                            "  - shared:moussey/SKILL.md: SETUP-POLICY missing first-screen setup section",
                            "",
                            "== Redirect Target Health ==",
                            "  OK",
                            "",
                            "== Profiles ==",
                            "  shared",
                            "    ok captain",
                            "",
                        ]
                    ),
                    "stderr": "",
                },
            )

            payload = verified_alive.build_payload(
                status_path=status,
                retention_path=retention,
                observe_path=observe,
                health_path=health,
                chat_providers_path=providers,
                local_ci_path=local_ci,
                captain_audit_path=captain,
            )

            self.assertEqual(payload["mode"], "read_only_verified_alive")
            self.assertEqual(payload["status"], "warning")
            self.assertIn("This rollup did not execute local-CI lanes.", payload["non_claims"])
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["firstbite_catalog"]["status"], "ready")
            self.assertEqual(checks["lane_proof_freshness"]["status"], "warning")
            self.assertEqual(checks["disk_guard"]["facts"]["disk_available_gib"], 41)
            self.assertEqual(checks["retention_watchdog"]["status"], "warning")
            self.assertEqual(checks["drift_tile"]["status"], "ready")
            self.assertEqual(checks["moussey_health"]["status"], "ready")
            self.assertEqual(checks["chat_front_door"]["status"], "warning")
            self.assertEqual(checks["moussey_local_ci_endpoint"]["status"], "warning")
            self.assertEqual(checks["captain_setup_health"]["status"], "warning")
            captain_facts = checks["captain_setup_health"]["facts"]
            self.assertEqual(captain_facts["exit_code"], 0)
            self.assertEqual(captain_facts["git_sync_status"], "ahead of upstream")
            self.assertEqual(captain_facts["setup_policy_warning_count"], 2)
            self.assertEqual(captain_facts["frontmatter_warning_count"], 1)
            self.assertEqual(captain_facts["tool_root_problem_count"], 0)
            local_ci_facts = checks["moussey_local_ci_endpoint"]["facts"]
            self.assertEqual(local_ci_facts["mcp_refresh_run_id"], "refresh-a")
            self.assertEqual(
                local_ci_facts["mcp_refresh_verdict"],
                "stale_loaded_clients_need_host_app_restart",
            )
            self.assertEqual(local_ci_facts["mcp_refresh_stale_process_count"], 5)
            self.assertEqual(local_ci_facts["mcp_refresh_lane_count"], 43)
            self.assertEqual(local_ci_facts["mcp_refresh_report_path"], "/tmp/refresh-a/report.json")
            self.assertTrue(local_ci_facts["mcp_refresh_safety_ok"])
            self.assertEqual(local_ci_facts["operator_approval_status"], "ready_for_approval")
            self.assertEqual(local_ci_facts["operator_approval_gate_status"], "operator_gated")
            self.assertEqual(local_ci_facts["operator_approval_packet_path"], "/tmp/approval-packet.json")
            self.assertEqual(local_ci_facts["operator_approval_candidate_path"], "/tmp/consignment-tracker")
            self.assertTrue(local_ci_facts["operator_approval_candidate_ready"])
            self.assertEqual(
                local_ci_facts["operator_approval_source_ref"],
                "4a7eded7c0d5f840570d21debd9de3dc428b9320",
            )
            self.assertTrue(local_ci_facts["operator_approval_source_ref_ready"])
            self.assertFalse(local_ci_facts["operator_approval_canonical_tracker_complete"])
            self.assertFalse(local_ci_facts["operator_approval_tracker_files_copied"])
            self.assertFalse(local_ci_facts["operator_approval_local_ci_lanes_executed"])
            self.assertTrue(local_ci_facts["operator_approval_readonly"])
            markdown = verified_alive._markdown(payload)
            self.assertIn("MCP refresh: `refresh-a` -> `stale_loaded_clients_need_host_app_restart`", markdown)
            self.assertIn("MCP refresh report: `/tmp/refresh-a/report.json`", markdown)
            self.assertIn("Loaded MCP processes stale: `5/5`", markdown)
            self.assertIn("MCP refresh safety ok: `True`", markdown)
            self.assertIn("Operator approval: `ready_for_approval` / `operator_gated`", markdown)
            self.assertIn("Operator approval packet: `/tmp/approval-packet.json`", markdown)
            self.assertIn("tracker_files_copied=`False`", markdown)
            self.assertIn("local_ci_lanes_executed=`False`", markdown)
            self.assertIn("Captain audit exit code: `0`", markdown)
            self.assertIn("Captain git sync status: `ahead of upstream`", markdown)
            self.assertIn("Captain warnings: `2` setup-policy, `1` frontmatter", markdown)

    def test_loaded_mcp_ready_claim_overrides_historical_stale_refresh_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_ci = root / "local-ci.json"
            _write_json(
                local_ci,
                {
                    "ok": True,
                    "launchTrust": {
                        "status": "blocked",
                        "summary": "6/12 launch trust gate(s) ready; 1 blocked",
                        "readyGateCount": 6,
                        "warningGateCount": 5,
                        "blockedGateCount": 1,
                    },
                    "runnerReadiness": {
                        "status": "warning",
                        "summary": "MCP client audit current enough",
                        "mcpClient": {
                            "status": "current_only",
                            "claimStatus": "ready",
                            "latestRefreshPlan": {
                                "runId": "older-refresh",
                                "verdict": "stale_loaded_clients_need_host_app_restart",
                                "reportPath": "/tmp/older-refresh/report.json",
                                "readOnly": True,
                                "killsProcesses": False,
                                "restartsApps": False,
                                "runsCi": False,
                                "mutatesRepos": False,
                                "staleProcessCount": 5,
                                "processCount": 5,
                            },
                        },
                    },
                },
            )

            check = verified_alive._check_moussey_local_ci(
                json.loads(local_ci.read_text(encoding="utf-8")),
                local_ci,
            )

            self.assertEqual(check["status"], "warning")
            self.assertIn("loaded MCP client claim is current", check["summary"])
            self.assertNotIn("stale_loaded_clients_need_host_app_restart", check["summary"])
            self.assertTrue(check["facts"]["mcp_effective_ready"])
            self.assertEqual(check["facts"]["mcp_claim_status"], "ready")
            self.assertEqual(check["facts"]["mcp_status"], "current_only")
            self.assertEqual(
                check["facts"]["mcp_refresh_verdict"],
                "stale_loaded_clients_need_host_app_restart",
            )
            self.assertEqual(check["facts"]["mcp_effective_stale_process_count"], 0)

            payload = {
                "generated_at": "2026-06-02T00:00:00Z",
                "status": "warning",
                "summary": "warning",
                "inputs": {"local_ci": str(local_ci)},
                "checks": [check],
                "non_claims": [],
            }
            markdown = verified_alive._markdown(payload)
            self.assertIn("Loaded MCP processes effective stale: `0/5`", markdown)
            self.assertIn("historical refresh `5/5`", markdown)
            self.assertNotIn("Loaded MCP processes stale: `5/5`", markdown)

    def test_dispatch_allowed_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = root / "status.json"
            retention = root / "retention.json"
            observe = root / "observe.json"
            _write_json(
                status,
                {
                    "catalog": {"lane_count": 1, "repo_count": 1, "catalog_stale": False},
                    "freshness_contract": {"stale_proof_count": 0, "unknown_proof_age_count": 0},
                    "latest_lane_proof": [{"lane": "alpha"}],
                    "disk_guard": {"status": "ready", "write_floor_blocked": False},
                },
            )
            _write_json(
                retention,
                {
                    "readonly": True,
                    "deletion_performed": False,
                    "install_performed": False,
                    "launchagent": {"installed": True},
                },
            )
            _write_json(
                observe,
                {
                    "plan_lint": {"status": "ready", "record_counts": {}},
                    "dispatch_policy": {"status": "observe_only", "dispatch_allowed": True},
                },
            )

            payload = verified_alive.build_payload(
                status_path=status,
                retention_path=retention,
                observe_path=observe,
                health_path=None,
                chat_providers_path=None,
                local_ci_path=None,
            )

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["drift_tile"]["status"], "blocked")
            self.assertEqual(payload["status"], "blocked")

    def test_cli_markdown_accepts_mcp_wrapper_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = root / "status-wrapper.json"
            retention = root / "retention.json"
            observe = root / "observe.json"
            inner = {
                "catalog": {"lane_count": 1, "repo_count": 1, "catalog_stale": False},
                "freshness_contract": {"stale_proof_count": 0, "unknown_proof_age_count": 0},
                "latest_lane_proof": [{"lane": "alpha"}],
                "disk_guard": {"status": "ready", "write_floor_blocked": False},
            }
            _write_json(status, {"content": [{"type": "text", "text": json.dumps(inner)}]})
            _write_json(
                retention,
                {
                    "readonly": True,
                    "deletion_performed": False,
                    "install_performed": False,
                    "launchagent": {"installed": True},
                },
            )
            _write_json(
                observe,
                {
                    "plan_lint": {"status": "ready", "record_counts": {}},
                    "dispatch_policy": {"status": "observe_only", "dispatch_allowed": False},
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--status",
                    str(status),
                    "--retention",
                    str(retention),
                    "--observe",
                    str(observe),
                    "--markdown",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# FirstBite Verified-Alive Rollup", result.stdout)
            self.assertIn("`drift_tile`", result.stdout)

    def test_refresh_evidence_writes_inputs_without_mutating(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            retention = root / "retention-report.json"
            _write_json(
                retention,
                {
                    "readonly": True,
                    "deletion_performed": False,
                    "install_performed": False,
                    "launchagent": {"installed": False},
                },
            )

            status_payload = {
                "catalog": {"lane_count": 43, "repo_count": 6, "catalog_stale": False},
                "freshness_contract": {"stale_proof_count": 0, "unknown_proof_age_count": 0},
                "latest_lane_proof": [],
                "disk_guard": {"status": "ready", "write_floor_blocked": False},
            }
            observe_payload = {
                "advisory_count": 0,
                "plan_lint": {"status": "ready", "record_counts": {"already_recorded": 0}},
                "dispatch_policy": {"status": "observe_only", "dispatch_allowed": False},
            }
            fetched_payloads = [
                {"ok": True, "codex": {"ready": True}, "hermes": {"ready": True}},
                {
                    "defaultProvider": "local",
                    "providers": {
                        "local": {"ready": True},
                        "codex": {"ready": True},
                        "claude": {"ready": True},
                    },
                },
                {"ok": True, "launchTrust": {"summary": "ready"}, "runnerReadiness": {"summary": "ready"}},
            ]

            captain_payload = {
                "command": ["bash", "/tmp/audit_skills.sh"],
                "cwd": "/tmp",
                "exit_code": 0,
                "stdout": "== Git Sync Status ==\n  up to date\n\n== Tool Skill Roots ==\n  ok\n\n== Frontmatter Health ==\n  OK\n\n== Setup Policy Warnings ==\n  OK\n",
                "stderr": "",
            }

            with mock.patch.object(
                verified_alive,
                "_run_json_command",
                side_effect=[status_payload, observe_payload],
            ) as run_json, mock.patch.object(
                verified_alive,
                "_run_captured_command",
                return_value=captain_payload,
            ) as run_capture, mock.patch.object(
                verified_alive,
                "_fetch_json",
                side_effect=fetched_payloads,
            ) as fetch_json:
                paths = verified_alive.refresh_evidence(
                    evidence_dir=root,
                    prefix="proof",
                    retention_path=retention,
                    firstbite_mcp_dir=root,
                    plan_path=root / "PLAN.md",
                    moussey_base_url="http://127.0.0.1:4321",
                )

            self.assertEqual(run_json.call_count, 2)
            self.assertEqual(run_capture.call_count, 1)
            self.assertEqual(fetch_json.call_count, 3)
            self.assertEqual(
                fetch_json.call_args_list[2].args[0],
                "http://127.0.0.1:4321/api/coding/local-ci?view=launch-trust",
            )
            self.assertEqual(paths["retention"], retention)
            self.assertEqual(json.loads(paths["status"].read_text())["catalog"]["lane_count"], 43)
            self.assertEqual(json.loads(paths["observe"].read_text())["dispatch_policy"]["status"], "observe_only")
            self.assertTrue(paths["health"].exists())
            self.assertTrue(paths["chat_providers"].exists())
            self.assertTrue(paths["local_ci"].exists())
            self.assertTrue(paths["captain_audit"].exists())
            self.assertEqual(json.loads(paths["captain_audit"].read_text())["exit_code"], 0)

    def test_main_empty_argv_does_not_read_process_argv(self):
        """Programmatic main([]) must not roll up/write from ambient sys.argv."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = root / "status.json"
            retention = root / "retention.json"
            observe = root / "observe.json"
            out_json = root / "rollup.json"
            _write_json(
                status,
                {
                    "catalog": {"lane_count": 1, "repo_count": 1, "catalog_stale": False},
                    "freshness_contract": {},
                    "latest_lane_proof": [],
                    "disk_guard": {"status": "ready"},
                },
            )
            _write_json(
                retention,
                {
                    "readonly": True,
                    "deletion_performed": False,
                    "install_performed": False,
                    "totals": {},
                    "launchagent": {},
                },
            )
            _write_json(
                observe,
                {
                    "advisory_count": 0,
                    "plan_lint": {"status": "ready", "record_counts": {"already_recorded": 0}},
                    "dispatch_policy": {"status": "observe_only", "dispatch_allowed": False},
                },
            )
            original_argv = sys.argv[:]
            sys.argv = [
                "probe",
                "--status",
                str(status),
                "--retention",
                str(retention),
                "--observe",
                str(observe),
                "--write-json",
                str(out_json),
            ]
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with (
                    self.assertRaises(SystemExit) as raised,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    verified_alive.main([])
            finally:
                sys.argv = original_argv

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("--status, --retention, and --observe are required", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(out_json.exists())


if __name__ == "__main__":
    unittest.main()
