"""Tests for scripts/vidux-firstbite-diagnose.py."""

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


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-firstbite-diagnose.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vidux_firstbite_diagnose", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


diagnose = _load_module()


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class FirstBiteDiagnoseTests(unittest.TestCase):
    def test_build_payload_clusters_failed_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_a = root / "missing-a.log"
            missing_b = root / "missing-b.log"
            xcode = root / "xcode.log"
            jest = root / "jest.log"
            _write(
                missing_a,
                "Error: Cannot find module '/tmp/worktree/scripts/ensure-local-supabase-running.mjs'\n",
            )
            _write(
                missing_b,
                "command_template=node scripts/ensure-local-supabase-running.mjs\n"
                "Error: Cannot find module '/tmp/worktree/scripts/ensure-local-supabase-running.mjs'\n",
            )
            _write(
                xcode,
                "/tmp/ResplitUITests.swift:1478: error: -[ResplitUITests.ResplitUITests testTripDetailTripSummaryRendersAtAccessibilityXXXLarge] : XCTAssertTrue failed - Expected base currency pill\n"
                "Test Case '-[ResplitUITests.ResplitUITests testTripDetailTripSummaryRendersAtAccessibilityXXXLarge]' failed (24.224 seconds).\n"
                "xcode_result={\"ok\":false,\"failed_tests\":1,\"total_tests\":10}\n",
            )
            _write(
                jest,
                "FAIL test/marketing/navigation-bar.test.tsx\n"
                "TestingLibraryElementError: Unable to find an accessible element with the role \"link\" and name `/word glossary/i`\n"
                "Test Suites: 1 failed, 9 passed, 10 total\n",
            )
            report = root / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "run_id": "mcp-fixture",
                        "overall": "fail",
                        "mode": "execute",
                        "lanes": [
                            {"lane": "green", "status": "pass"},
                            {
                                "lane": "strongyes_web_ui",
                                "repo": "strongyes_web",
                                "kind": "ui",
                                "status": "fail",
                                "rc": 1,
                                "reason": "command exited with code 1",
                                "log_path": str(missing_a),
                                "resolved_source_ref": "abc",
                            },
                            {
                                "lane": "strongyes_web_dsa_chat",
                                "repo": "strongyes_web",
                                "kind": "ui",
                                "status": "fail",
                                "rc": 1,
                                "reason": "command exited with code 1",
                                "log_path": str(missing_b),
                                "resolved_source_ref": "abc",
                            },
                            {
                                "lane": "resplit_ios_ui_full",
                                "repo": "resplit_ios",
                                "kind": "ui",
                                "status": "fail",
                                "rc": 65,
                                "reason": "xcode result contains failed tests",
                                "log_path": str(xcode),
                                "resolved_source_ref": "def",
                                "xcode_result": {"failed_tests": 1, "total_tests": 10},
                            },
                            {
                                "lane": "strongyes_web_unit",
                                "repo": "strongyes_web",
                                "kind": "unit",
                                "status": "fail",
                                "rc": 1,
                                "reason": "command exited with code 1",
                                "log_path": str(jest),
                                "resolved_source_ref": "ghi",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = diagnose.build_payload([report])

            self.assertEqual(payload["failed_lane_count"], 4)
            self.assertEqual(payload["mode"], "read_only_failed_execute_diagnosis")
            self.assertFalse(payload["next_resume"]["local_ci_lanes_executed"])
            categories = {group["category"]: group for group in payload["groups"]}
            self.assertEqual(len(categories["missing_module_in_clean_source"]["lanes"]), 2)
            self.assertEqual(categories["xcode_failed_tests"]["lanes"], ["resplit_ios_ui_full"])
            self.assertIn("Jest navigation assertion", categories["jest_accessible_element_assertion"]["summary"])

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "lane.log"
            report = root / "report.json"
            out_json = root / "diagnosis.json"
            out_md = root / "diagnosis.md"
            _write(log, "Error: Cannot find module '/tmp/worktree/scripts/ensure-local-supabase-running.mjs'\n")
            report.write_text(
                json.dumps(
                    {
                        "run_id": "mcp-cli",
                        "overall": "fail",
                        "lanes": [
                            {
                                "lane": "strongyes_web_ui",
                                "repo": "strongyes_web",
                                "status": "fail",
                                "log_path": str(log),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(report),
                    "--write-json",
                    str(out_json),
                    "--write-markdown",
                    str(out_md),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["group_count"], 1)
            self.assertTrue(out_json.exists())
            markdown = out_md.read_text(encoding="utf-8")
            self.assertIn("No local-CI lane was executed or rerun.", markdown)
            self.assertIn("missing_module_in_clean_source", markdown)

    def test_build_payload_reads_verified_alive_failing_lanes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            yellow_log = root / "fx.log"
            snowcubes_log = root / "snowcubes.log"
            _write(
                yellow_log,
                "expected yellow: source-promotion trust contract still needs reviewed-current proof\n"
                "Grafana OTEL proof missing\n",
            )
            _write(
                snowcubes_log,
                "resolved_source_ref=5706b2884943bb665faddaf4b7e3e37023782422\n"
                "expected generated E2E bundle status\n\n"
                "false !== true\n",
            )
            report = root / "verified-alive.json"
            report.write_text(
                json.dumps(
                    {
                        "run_id": "verified-alive",
                        "goal_audit": {
                            "local_ci_launch_trust": {
                                "summary": "6/12 launch trust gate(s) ready; 1 blocked; 5 warning/unknown.",
                                "blocked_gates": [
                                    {
                                        "id": "declared-lanes",
                                        "summary": "40/43 declared pass; 3 non-pass; 0 stale/missing.",
                                    }
                                ],
                                "failing_lanes": [
                                    {
                                        "lane": "resplit_web_integration",
                                        "repo": "Resplit Web",
                                        "status": "missing",
                                        "reason": "no executable proof found for this catalog lane",
                                        "report_path": None,
                                        "log_path": None,
                                    },
                                    {
                                        "lane": "resplit_currency_api_trust_preflight",
                                        "repo": "Resplit FX",
                                        "status": "warn",
                                        "rc": 1,
                                        "reason": "command exited with expected yellow code 1",
                                        "report_path": str(root / "fx-report.json"),
                                        "log_path": str(yellow_log),
                                    },
                                    {
                                        "lane": "moussey_snowcubes_readiness",
                                        "repo": "Moussey",
                                        "status": "fail",
                                        "rc": 1,
                                        "reason": "command exited with code 1",
                                        "report_path": str(root / "moussey-report.json"),
                                        "log_path": str(snowcubes_log),
                                    },
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = diagnose.build_payload([report])

            self.assertEqual(payload["failed_lane_count"], 3)
            self.assertEqual(payload["aggregate_nonpass_lane_count"], 3)
            self.assertEqual(payload["diagnosis_coverage_status"], "complete")
            self.assertEqual(payload["undocumented_nonpass_lane_count"], 0)
            self.assertEqual(
                payload["reports"][0]["launch_trust_summary"],
                "6/12 launch trust gate(s) ready; 1 blocked; 5 warning/unknown.",
            )
            self.assertEqual(
                payload["reports"][0]["declared_lanes_summary"],
                "40/43 declared pass; 3 non-pass; 0 stale/missing.",
            )
            categories = {group["category"]: group for group in payload["groups"]}
            self.assertEqual(
                categories["missing_executable_proof"]["lanes"],
                ["resplit_web_integration"],
            )
            self.assertEqual(
                categories["expected_yellow_trust_gate"]["lanes"],
                ["resplit_currency_api_trust_preflight"],
            )
            self.assertEqual(
                categories["snowcubes_generated_e2e_bundle_status"]["lanes"],
                ["moussey_snowcubes_readiness"],
            )
            self.assertEqual(
                categories["snowcubes_generated_e2e_bundle_status"]["source_refs"],
                ["5706b2884943bb665faddaf4b7e3e37023782422"],
            )
            lane_reports = {lane["lane"]: lane["report_path"] for lane in payload["lanes"]}
            self.assertEqual(
                lane_reports["resplit_currency_api_trust_preflight"],
                str(root / "fx-report.json"),
            )
            self.assertEqual(
                lane_reports["resplit_web_integration"],
                str(report),
            )

    def test_build_payload_marks_verified_alive_diagnosis_partial_when_gate_count_exceeds_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "lane.log"
            _write(log, "Error: Cannot find module '/tmp/worktree/scripts/ensure-local-supabase-running.mjs'\n")
            report = root / "verified-alive.json"
            report.write_text(
                json.dumps(
                    {
                        "run_id": "verified-alive-partial",
                        "goal_audit": {
                            "local_ci_launch_trust": {
                                "blocked_gates": [
                                    {
                                        "id": "declared-lanes",
                                        "summary": "19/33 declared pass; 14 non-pass; 0 stale/missing.",
                                    }
                                ],
                                "failing_lanes": [
                                    {
                                        "lane": "strongyes_web_dsa_chat",
                                        "repo": "StrongYes Web",
                                        "status": "fail",
                                        "reason": "command exited with code 1",
                                        "log_path": str(log),
                                    },
                                    {
                                        "lane": "resplit_web_integration",
                                        "repo": "Resplit Web",
                                        "status": "missing",
                                        "reason": "no executable proof found for this catalog lane",
                                    },
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = diagnose.build_payload([report])

            self.assertEqual(payload["visible_failed_lane_count"], 2)
            self.assertEqual(payload["aggregate_nonpass_lane_count"], 14)
            self.assertEqual(payload["diagnosis_coverage_status"], "partial")
            self.assertEqual(payload["undocumented_nonpass_lane_count"], 12)
            self.assertEqual(payload["next_resume"]["diagnosis_coverage_status"], "partial")
            report_summary = payload["reports"][0]
            self.assertEqual(report_summary["diagnosis_coverage_status"], "partial")
            self.assertEqual(report_summary["undocumented_nonpass_lane_count"], 12)

    def test_main_empty_argv_does_not_read_process_argv(self):
        """Programmatic main([]) must not diagnose/write from ambient sys.argv."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "lane.log"
            report = root / "report.json"
            out_json = root / "diagnosis.json"
            _write(log, "Error: Cannot find module '/tmp/worktree/scripts/ensure-local-supabase-running.mjs'\n")
            report.write_text(
                json.dumps(
                    {
                        "run_id": "ambient-diagnose",
                        "overall": "fail",
                        "lanes": [
                            {
                                "lane": "strongyes_web_ui",
                                "repo": "strongyes_web",
                                "status": "fail",
                                "log_path": str(log),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            original_argv = sys.argv[:]
            sys.argv = ["probe", str(report), "--write-json", str(out_json), "--json"]
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with (
                    self.assertRaises(SystemExit) as raised,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    diagnose.main([])
            finally:
                sys.argv = original_argv

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("the following arguments are required", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(out_json.exists())


if __name__ == "__main__":
    unittest.main()
