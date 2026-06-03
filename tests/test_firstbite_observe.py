"""Tests for scripts/vidux-firstbite-observe.py."""

from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-firstbite-observe.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vidux_firstbite_observe", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


observe = _load_module()


def _write_report(path: Path) -> None:
    payload = {
        "run_id": "mcp-fixture",
        "overall": "fail",
        "lanes": [
            {
                "lane": "alpha_green",
                "repo": "resplit_web",
                "status": "pass",
                "trust_status": "green",
                "log_path": "/tmp/alpha.log",
            },
            {
                "lane": "beta_stale",
                "repo": "litty",
                "status": "pass",
                "trust_status": "green",
                "stale_proof": True,
                "proof_age_hours": 72.5,
                "log_path": "/tmp/beta.log",
                "source_commit": "abc123",
            },
            {
                "lane": "gamma_red",
                "repo": "strongyes_web",
                "status": "fail",
                "trust_status": "red",
                "reason": "command exited with code 1",
                "log_path": "/tmp/gamma.log",
                "source_commit": "def456",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class FirstBiteObserveTests(unittest.TestCase):
    def test_build_payload_ranks_red_before_stale_and_skips_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            plan = root / "PLAN.md"
            cache = root / "drift-cache.jsonl"
            _write_report(report)
            plan.write_text("# Plan\n", encoding="utf-8")

            payload = observe.build_payload(
                [report],
                plan_path=plan,
                drift_script=SCRIPT.parent / "vidux-drift-log.py",
                cache_path=cache,
            )

            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["mode"], "observe_only")
            self.assertEqual(payload["advisory_count"], 2)
            self.assertFalse(payload["autodispatch"]["dispatch_allowed"])
            self.assertEqual(payload["plan_lint"]["status"], "warning")
            self.assertEqual(payload["plan_lint"]["record_counts"]["missing_record"], 2)
            self.assertEqual(payload["dispatch_policy"]["status"], "blocked")
            self.assertFalse(payload["dispatch_policy"]["dispatch_allowed"])
            self.assertIn("manual_drift_records_pending", payload["dispatch_policy"]["blockers"])
            self.assertEqual(payload["dispatch_policy"]["manual_record_pending_count"], 2)
            self.assertEqual(payload["advisories"][0]["lane"], "gamma_red")
            self.assertEqual(payload["advisories"][0]["status"], "fail")
            self.assertEqual(payload["advisories"][0]["impact"], "blocking")
            self.assertEqual(payload["advisories"][0]["plan_record_state"], "missing_record")
            self.assertEqual(payload["advisories"][0]["recommended_action"], "record_drift_manually")
            self.assertEqual(payload["advisories"][1]["lane"], "beta_stale")
            self.assertTrue(payload["advisories"][1]["stale_proof"])

            command = payload["advisories"][0]["drift_command"]
            self.assertIn("--impact", command)
            self.assertIn("blocking", command)
            self.assertIn("--evidence-ref", command)
            self.assertIn("/tmp/gamma.log", command)
            self.assertIn("--cache", command)
            self.assertIn(str(cache), command)

    def test_autodispatch_truthy_env_is_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            plan = Path(tmp) / "PLAN.md"
            _write_report(report)

            with patch.dict(os.environ, {"BRAIN_AUTODISPATCH": "on"}):
                payload = observe.build_payload(
                    [report],
                    plan_path=plan,
                    drift_script=SCRIPT.parent / "vidux-drift-log.py",
                    cache_path=None,
                    limit=1,
                )

            self.assertTrue(payload["autodispatch"]["requested"])
            self.assertFalse(payload["autodispatch"]["dispatch_allowed"])
            self.assertEqual(payload["autodispatch"]["action"], "suppressed_observe_only")
            self.assertTrue(payload["dispatch_policy"]["requested"])
            self.assertFalse(payload["dispatch_policy"]["dispatch_allowed"])
            self.assertIn("plan_lint_not_ready", payload["dispatch_policy"]["blockers"])
            self.assertEqual(payload["advisory_count"], 1)

    def test_generic_report_parent_name_is_not_a_duplicate_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_dir = root / "evidence"
            evidence_dir.mkdir()
            report = evidence_dir / "status-snapshot.json"
            plan = root / "PLAN.md"
            payload = {
                "overall": "fail",
                "lanes": [
                    {
                        "lane": "gamma_red",
                        "repo": "strongyes_web",
                        "status": "fail",
                        "trust_status": "red",
                        "log_path": "/tmp/gamma.log",
                    }
                ],
            }
            report.write_text(json.dumps(payload), encoding="utf-8")
            plan.write_text("Evidence mentions beta_stale but no drift line.\n", encoding="utf-8")

            payload = observe.build_payload(
                [report],
                plan_path=plan,
                drift_script=SCRIPT.parent / "vidux-drift-log.py",
                cache_path=None,
                limit=1,
            )

            self.assertEqual(payload["advisories"][0]["run_id"], "status-snapshot")
            self.assertEqual(payload["advisories"][0]["lane"], "gamma_red")
            self.assertEqual(payload["advisories"][0]["plan_record_state"], "missing_record")

    def test_plan_lint_marks_already_recorded_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            plan = root / "PLAN.md"
            _write_report(report)
            plan.write_text(
                "- [2026-06-01] Drift D-1: FirstBite report mcp-fixture observed gamma_red as fail.\n",
                encoding="utf-8",
            )

            payload = observe.build_payload(
                [report],
                plan_path=plan,
                drift_script=SCRIPT.parent / "vidux-drift-log.py",
                cache_path=None,
            )

            self.assertEqual(payload["plan_lint"]["status"], "warning")
            self.assertEqual(payload["plan_lint"]["record_counts"]["already_recorded"], 1)
            self.assertEqual(payload["plan_lint"]["record_counts"]["missing_record"], 1)
            self.assertEqual(payload["advisories"][0]["lane"], "gamma_red")
            self.assertEqual(payload["advisories"][0]["plan_record_state"], "already_recorded")
            self.assertEqual(payload["advisories"][0]["recommended_action"], "skip_duplicate_record")
            self.assertEqual(payload["advisories"][1]["lane"], "beta_stale")
            self.assertEqual(payload["advisories"][1]["plan_record_state"], "missing_record")

    def test_plan_lint_requires_same_run_id_for_duplicate_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            plan = root / "PLAN.md"
            _write_report(report)
            plan.write_text(
                "- [2026-06-01] Drift D-1: FirstBite report older-run observed gamma_red as fail.\n",
                encoding="utf-8",
            )

            payload = observe.build_payload(
                [report],
                plan_path=plan,
                drift_script=SCRIPT.parent / "vidux-drift-log.py",
                cache_path=None,
            )

            self.assertEqual(payload["plan_lint"]["status"], "warning")
            self.assertEqual(payload["plan_lint"]["record_counts"]["already_recorded"], 0)
            self.assertEqual(payload["plan_lint"]["record_counts"]["lane_seen_without_run"], 1)
            self.assertEqual(payload["plan_lint"]["record_counts"]["missing_record"], 1)
            self.assertEqual(payload["dispatch_policy"]["manual_record_pending_count"], 2)
            self.assertEqual(payload["advisories"][0]["lane"], "gamma_red")
            self.assertEqual(payload["advisories"][0]["plan_record_state"], "lane_seen_without_run")
            self.assertEqual(payload["advisories"][0]["recommended_action"], "record_drift_manually")

    def test_aggregate_latest_lane_proof_uses_lane_report_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aggregate = root / "runner-packet-status.json"
            plan = root / "PLAN.md"
            aggregate.write_text(
                json.dumps(
                    {
                        "latest_lane_proof": [
                            {
                                "lane": "gamma_red",
                                "repo": "strongyes_web",
                                "status": "fail",
                                "trust_status": "red",
                                "run_id": "mcp-lane-run-123",
                                "report_path": "/tmp/mcp-lane-run-123/report.json",
                                "log_path": "/tmp/mcp-lane-run-123/gamma_red/run.log",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            plan.write_text(
                "- [2026-06-02] Drift D-1: FirstBite report mcp-lane-run-123 observed gamma_red as fail.\n",
                encoding="utf-8",
            )

            payload = observe.build_payload(
                [aggregate],
                plan_path=plan,
                drift_script=SCRIPT.parent / "vidux-drift-log.py",
                cache_path=None,
            )

            advisory = payload["advisories"][0]
            self.assertEqual(advisory["run_id"], "mcp-lane-run-123")
            self.assertEqual(advisory["plan_record_state"], "already_recorded")
            self.assertEqual(advisory["evidence_refs"][0], "/tmp/mcp-lane-run-123/report.json")
            self.assertIn("/tmp/mcp-lane-run-123/gamma_red/run.log", advisory["evidence_refs"])
            self.assertEqual(payload["plan_lint"]["status"], "ready")

    def test_dispatch_policy_stays_observe_only_after_plan_lint_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            plan = root / "PLAN.md"
            _write_report(report)
            plan.write_text(
                "\n".join(
                    [
                        "- [2026-06-01] Drift D-1: FirstBite report mcp-fixture observed gamma_red as fail.",
                        "- [2026-06-01] Drift D-2: FirstBite report mcp-fixture observed beta_stale as pass.",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"BRAIN_AUTODISPATCH": "on"}):
                payload = observe.build_payload(
                    [report],
                    plan_path=plan,
                    drift_script=SCRIPT.parent / "vidux-drift-log.py",
                    cache_path=None,
                )

            self.assertEqual(payload["plan_lint"]["status"], "ready")
            self.assertEqual(payload["dispatch_policy"]["status"], "observe_only")
            self.assertTrue(payload["dispatch_policy"]["requested"])
            self.assertFalse(payload["dispatch_policy"]["dispatch_allowed"])
            self.assertEqual(payload["dispatch_policy"]["blockers"], ["m22_observe_only_brake"])
            self.assertEqual(
                payload["dispatch_policy"]["next_action"],
                "keep_observe_only_until_operator_promotes_cockpit_gate",
            )

    def test_cli_json_accepts_mcp_text_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "wrapped.json"
            inner = {
                "run_id": "wrapped-run",
                "latest_lane_proof": [
                    {
                        "lane": "wrapped_red",
                        "repo": "moussey",
                        "status": "fail",
                        "trust_status": "red",
                        "log_path": "/tmp/wrapped.log",
                    }
                ],
            }
            report.write_text(
                json.dumps({"content": [{"type": "text", "text": json.dumps(inner)}]}),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(report),
                    "--plan",
                    str(root / "PLAN.md"),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["reports"][0]["run_id"], "wrapped-run")
            self.assertEqual(payload["advisories"][0]["lane"], "wrapped_red")

    def test_main_empty_argv_does_not_read_process_argv(self):
        """Programmatic main([]) must not observe from ambient sys.argv."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            plan = root / "PLAN.md"
            _write_report(report)
            plan.write_text("# Plan\n", encoding="utf-8")
            original_argv = sys.argv[:]
            sys.argv = ["probe", str(report), "--plan", str(plan), "--json"]
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with (
                    self.assertRaises(SystemExit) as raised,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    observe.main([])
            finally:
                sys.argv = original_argv

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("the following arguments are required", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
