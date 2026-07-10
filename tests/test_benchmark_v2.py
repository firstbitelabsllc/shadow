"""Contract coverage for the preregistered Vidux benchmark-v2 scaffold."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-benchmark-v2.py"
MANIFEST_PATH = ROOT / "benchmarks" / "v2" / "manifest.json"

spec = importlib.util.spec_from_file_location("vidux_benchmark_v2", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class BenchmarkV2Tests(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def sealed_manifest(self) -> dict:
        manifest = self.manifest()
        manifest["status"] = "ready_for_transport"
        for index, scenario in enumerate(manifest["scenario_classes"], start=1):
            scenario["oracle_state"] = "sealed"
            scenario["oracle_commitment_sha256"] = f"{index:064x}"
        return manifest

    def result_rows(self, manifest: dict, *, include_all_arms: bool = True) -> list[dict]:
        commitment = manifest["scenario_classes"][0]["oracle_commitment_sha256"]
        rows: list[dict] = []
        for index in range(20):
            fixture_id = f"durable-{index:02d}"
            for arm in ("vidux_cockpit", "claude_native", "codex_native"):
                if arm != "vidux_cockpit" and not include_all_arms:
                    continue
                baseline_success = 0 if index < 8 else 1
                success = 1 if arm == "vidux_cockpit" else baseline_success
                rows.append(
                    {
                        "scenario_class": "durable_state",
                        "fixture_id": fixture_id,
                        "replica": 1,
                        "arm": arm,
                        "status": "complete",
                        "success": success,
                        "wall_seconds": 90 if arm == "vidux_cockpit" else 120,
                        "tokens": 900 if arm == "vidux_cockpit" else 1200,
                        "dollars": 0.09 if arm == "vidux_cockpit" else 0.2,
                        "operator_touches": 1 if arm == "vidux_cockpit" else 2,
                        "resume_loss": 0 if arm == "vidux_cockpit" else 1,
                        "oracle_commitment_sha256": commitment,
                        "protocol_digest": mod.manifest_digest(manifest),
                        "provider_model": f"{arm}-model",
                        "runtime_version": "test-runtime-1",
                        "provider_receipt_id": f"provider-{arm}-{index}",
                        "runner_receipt_id": f"runner-{arm}-{index}",
                        "transcript_receipt_id": f"transcript-{arm}-{index}",
                    }
                )
        return rows

    def test_frozen_manifest_is_valid_but_not_transport_ready(self):
        manifest = self.manifest()

        self.assertEqual(mod.validate_manifest(manifest), [])
        readiness = mod.transport_readiness(manifest)

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["status"], "protocol_frozen_pending_fixture_seal")
        self.assertIn("durable_state hidden oracle is not sealed", readiness["gates"])

    def test_native_controls_must_keep_ordinary_filesystem_access(self):
        manifest = self.manifest()
        for arm in manifest["arms"]:
            if arm["id"] == "claude_native":
                arm["ordinary_filesystem"] = False

        errors = mod.validate_manifest(manifest)

        self.assertTrue(any("claude_native must retain ordinary_filesystem access" in error for error in errors))

    def test_run_packet_refuses_unsealed_oracles(self):
        with self.assertRaisesRegex(mod.ValidationError, "not transport-ready"):
            mod.build_run_packet(
                self.manifest(),
                arm="vidux_cockpit",
                scenario_class="durable_state",
                fixture_id="durable-00",
                replica=1,
            )

    def test_ready_manifest_emits_packet_without_oracle_payload(self):
        packet = mod.build_run_packet(
            self.sealed_manifest(),
            arm="vidux_cockpit",
            scenario_class="durable_state",
            fixture_id="durable-00",
            replica=1,
        )

        self.assertEqual(packet["arm"], "vidux_cockpit")
        self.assertEqual(packet["additional_surface"], "read_only_cockpit_packet")
        self.assertEqual(packet["prohibited_surface"], "sealed_hidden_oracle")
        self.assertNotIn("oracle_answer", json.dumps(packet))

    def test_results_require_complete_paired_blocks(self):
        manifest = self.sealed_manifest()

        with self.assertRaisesRegex(mod.ValidationError, "missing arm"):
            mod.validate_result_rows(self.result_rows(manifest, include_all_arms=False), manifest)

    def test_score_requires_evidence_before_a_class_can_win(self):
        score = mod.score_result_rows([], self.sealed_manifest())

        self.assertEqual(score["status"], "unproven")
        self.assertEqual(score["verified_net_win_scenario_classes"], [])

    def test_paired_score_can_only_win_against_both_native_controls(self):
        manifest = self.sealed_manifest()
        score = mod.score_result_rows(self.result_rows(manifest), manifest)
        durable = score["scenario_classes"]["durable_state"]

        self.assertEqual(durable["status"], "win")
        self.assertEqual(durable["comparisons"]["claude_native"]["status"], "win")
        self.assertEqual(durable["comparisons"]["codex_native"]["status"], "win")
        self.assertEqual(score["verified_net_win_scenario_classes"], ["durable_state"])
        self.assertEqual(score["status"], "unproven")

    def test_zero_resolved_control_is_inconclusive_not_a_cost_win(self):
        manifest = self.sealed_manifest()
        rows = self.result_rows(manifest)
        for row in rows:
            if row["arm"] != "vidux_cockpit":
                row["success"] = 0
        score = mod.score_result_rows(rows, manifest)

        durable = score["scenario_classes"]["durable_state"]
        self.assertEqual(durable["status"], "inconclusive")
        self.assertEqual(durable["comparisons"]["claude_native"]["status"], "inconclusive")

    def test_high_token_overhead_cannot_claim_a_net_value_win(self):
        manifest = self.sealed_manifest()
        rows = self.result_rows(manifest)
        for row in rows:
            if row["arm"] == "vidux_cockpit":
                row["tokens"] = 10_000

        score = mod.score_result_rows(rows, manifest)

        durable = score["scenario_classes"]["durable_state"]
        self.assertEqual(durable["status"], "inconclusive")
        self.assertEqual(durable["comparisons"]["claude_native"]["status"], "inconclusive")

    def test_rows_must_bind_to_the_sealed_manifest_digest(self):
        manifest = self.sealed_manifest()
        rows = self.result_rows(manifest)
        rows[0]["protocol_digest"] = "0" * 64

        with self.assertRaisesRegex(mod.ValidationError, "protocol digest does not match"):
            mod.validate_result_rows(rows, manifest)

    def test_cli_exposes_validity_and_pending_transport_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps(self.manifest()), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = mod.main(["validate", "--manifest", str(manifest_path)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["transport_ready"])

    def test_manifest_rules_cannot_mutate_to_posthoc_thresholds(self):
        manifest = copy.deepcopy(self.manifest())
        manifest["amendment_policy"]["posthoc_threshold_changes_forbidden"] = False

        errors = mod.validate_manifest(manifest)

        self.assertTrue(any("forbid posthoc threshold changes" in error for error in errors))
