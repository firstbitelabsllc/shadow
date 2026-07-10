"""Contract coverage for Vidux benchmark-v2's external fixture release gate."""

from __future__ import annotations

import contextlib
import copy
import hashlib
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
STATUS_PATH = ROOT / "benchmarks" / "v2" / "STATUS.json"

spec = importlib.util.spec_from_file_location("vidux_benchmark_v2", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class BenchmarkV2Tests(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def fixture_id(scenario_id: str, index: int) -> str:
        prefix = "durable" if scenario_id == "durable_state" else scenario_id.replace("_", "-")
        return f"{prefix}-{index:02d}"

    def release(self, manifest: dict, *, durable_count: int = 20) -> dict:
        fixtures: list[dict] = []
        for scenario_number, scenario in enumerate(manifest["scenario_classes"], start=1):
            scenario_id = scenario["id"]
            count = durable_count if scenario_id == "durable_state" else scenario["fixture_count_target"]
            for index in range(count):
                fixture_id = self.fixture_id(scenario_id, index)
                fixtures.append(
                    {
                        "scenario_class": scenario_id,
                        "fixture_id": fixture_id,
                        "fixture_path": f"{scenario_id}/{fixture_id}.json",
                        "fixture_sha256": hashlib.sha256(
                            f"fixture:{scenario_number}:{index}".encode("utf-8")
                        ).hexdigest(),
                        "oracle_commitment_sha256": hashlib.sha256(
                            f"oracle:{scenario_number}:{index}".encode("utf-8")
                        ).hexdigest(),
                    }
                )
        return {
            "schema_version": 1,
            "release_id": "v2-test-release",
            "protocol_id": manifest["protocol_id"],
            "source_manifest_digest": mod.manifest_digest(manifest),
            "evaluator_receipt_id": "evaluator-test-receipt",
            "fixtures": fixtures,
        }

    def result_rows(self, manifest: dict, release: dict, *, include_all_arms: bool = True) -> list[dict]:
        fixtures = mod._fixture_release_map(release)
        rows: list[dict] = []
        for index in range(20):
            fixture_id = self.fixture_id("durable_state", index)
            commitment = fixtures[("durable_state", fixture_id)]["oracle_commitment_sha256"]
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
                        "fixture_release_digest": mod.fixture_release_digest(release),
                        "provider_model": f"{arm}-model",
                        "runtime_version": "test-runtime-1",
                        "provider_receipt_id": f"provider-{arm}-{index}",
                        "runner_receipt_id": f"runner-{arm}-{index}",
                        "transcript_receipt_id": f"transcript-{arm}-{index}",
                    }
                )
        return rows

    def materialized_release(self, directory: Path) -> tuple[dict, dict, Path, Path, Path]:
        manifest = self.manifest()
        fixture_root = directory / "public-fixtures"
        oracle_root = directory / "private-oracles"
        fixture_root.mkdir()
        oracle_root.mkdir()
        index = {
            "release_id": "v2-fixture-release",
            "evaluator_receipt_id": "independent-evaluator-receipt",
            "fixtures": [],
        }
        for scenario in manifest["scenario_classes"]:
            scenario_id = scenario["id"]
            for index_number in range(scenario["fixture_count_target"]):
                fixture_id = self.fixture_id(scenario_id, index_number)
                relative_path = f"{scenario_id}/{fixture_id}.json"
                fixture_path = fixture_root / relative_path
                oracle_path = oracle_root / relative_path
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                oracle_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text(f"public fixture {scenario_id} {index_number}\n", encoding="utf-8")
                oracle_path.write_text(f"hidden oracle secret {scenario_id} {index_number}\n", encoding="utf-8")
                index["fixtures"].append(
                    {
                        "scenario_class": scenario_id,
                        "fixture_id": fixture_id,
                        "fixture_path": relative_path,
                        "oracle_path": relative_path,
                    }
                )
        release = mod.build_fixture_release(
            manifest,
            index,
            fixture_root=fixture_root,
            oracle_root=oracle_root,
        )
        return manifest, release, fixture_root, oracle_root, directory / "release.json"

    def test_frozen_manifest_is_valid_but_retired_from_transport(self):
        manifest = self.manifest()
        protocol_status = mod.load_protocol_status(STATUS_PATH)

        self.assertEqual(mod.validate_manifest(manifest), [])
        self.assertEqual(mod.validate_protocol_status(protocol_status, manifest), [])
        readiness = mod.transport_readiness(manifest, protocol_status=protocol_status)

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["status"], "protocol_frozen_pending_fixture_seal")
        self.assertEqual(readiness["protocol_status"], "retired_non_runnable")
        self.assertEqual(protocol_status["replacement_protocol_id"], "vidux-cockpit-v3")
        self.assertIn(mod.NON_RUNNABLE_GATE, readiness["gates"])
        self.assertIn("sealed external fixture release is required", readiness["gates"])

    def test_source_manifest_cannot_self_seal_or_hide_a_commitment(self):
        manifest = self.manifest()
        manifest["status"] = "ready_for_transport"
        manifest["scenario_classes"][0]["oracle_state"] = "sealed"
        manifest["scenario_classes"][0]["oracle_commitment_sha256"] = "0" * 64

        errors = mod.validate_manifest(manifest)

        self.assertTrue(any("source manifest must remain" in error for error in errors))
        self.assertTrue(any("source manifest oracle_state" in error for error in errors))
        self.assertTrue(any("must not expose an oracle commitment" in error for error in errors))

    def test_native_controls_must_keep_ordinary_filesystem_access(self):
        manifest = self.manifest()
        for arm in manifest["arms"]:
            if arm["id"] == "claude_native":
                arm["ordinary_filesystem"] = False

        errors = mod.validate_manifest(manifest)

        self.assertTrue(any("claude_native must retain ordinary_filesystem access" in error for error in errors))

    def test_frozen_manifest_requires_exactly_one_replica_per_fixture(self):
        manifest = self.manifest()
        manifest["trial_design"]["replicas_per_fixture"] = 2

        errors = mod.validate_manifest(manifest)

        self.assertIn("trial_design replicas_per_fixture must equal 1", errors)

    def test_release_requires_all_scenario_fixture_targets(self):
        manifest = self.manifest()
        release = self.release(manifest)
        release["fixtures"] = [
            fixture for fixture in release["fixtures"] if fixture["scenario_class"] == "durable_state"
        ]

        errors = mod.validate_fixture_release(release, manifest)

        self.assertTrue(any("interruption_recovery needs at least 12 fixtures" in error for error in errors))

    def test_release_rejects_oracle_path_and_fixture_path_escape(self):
        manifest = self.manifest()
        release = self.release(manifest)
        release["fixtures"][0]["oracle_path"] = "should-never-be-public.json"
        release["fixtures"][1]["fixture_path"] = "../escape.json"

        errors = mod.validate_fixture_release(release, manifest)

        self.assertTrue(any("exactly public fixture fields" in error for error in errors))
        self.assertTrue(any("normalized relative path" in error for error in errors))

    def test_seal_release_hashes_files_without_leaking_oracle_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, release, fixture_root, _oracle_root, _output = self.materialized_release(Path(tmp))

            readiness = mod.transport_readiness(manifest, release=release, fixture_root=fixture_root)
            serialized = json.dumps(release, sort_keys=True)
            file_errors = mod.validate_fixture_release_files(release, fixture_root)

        self.assertTrue(readiness["ready"])
        self.assertNotIn("hidden oracle secret", serialized)
        self.assertNotIn("oracle_path", serialized)
        self.assertEqual(file_errors, [])

    def test_fixture_bytes_must_match_the_sealed_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, release, fixture_root, _oracle_root, _output = self.materialized_release(Path(tmp))
            fixture_path = fixture_root / release["fixtures"][0]["fixture_path"]
            fixture_path.write_text("tampered public fixture\n", encoding="utf-8")

            readiness = mod.transport_readiness(manifest, release=release, fixture_root=fixture_root)

        self.assertFalse(readiness["ready"])
        self.assertTrue(any("fixture SHA-256 does not match" in gate for gate in readiness["gates"]))

    def test_fixture_and_oracle_roots_must_not_overlap(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = {"release_id": "v2-overlap", "evaluator_receipt_id": "receipt", "fixtures": []}

            with self.assertRaisesRegex(mod.ValidationError, "must not overlap"):
                mod.build_fixture_release(manifest, index, fixture_root=root, oracle_root=root)

    def test_seal_rejects_malformed_index_before_reading_any_files(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_root = root / "fixtures"
            oracle_root = root / "oracles"
            fixture_root.mkdir()
            oracle_root.mkdir()
            index = {"release_id": "BAD", "evaluator_receipt_id": "receipt", "fixtures": []}

            with self.assertRaisesRegex(mod.ValidationError, "release_id"):
                mod.build_fixture_release(manifest, index, fixture_root=fixture_root, oracle_root=oracle_root)

    def test_packet_requires_verified_release_and_never_contains_oracle_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, release, fixture_root, _oracle_root, _output = self.materialized_release(Path(tmp))
            packet = mod.build_run_packet(
                manifest,
                release=release,
                fixture_root=fixture_root,
                arm="vidux_cockpit",
                scenario_class="durable_state",
                fixture_id="durable-00",
                replica=1,
            )

        self.assertEqual(packet["arm"], "vidux_cockpit")
        self.assertEqual(packet["additional_surface"], "read_only_cockpit_packet")
        self.assertEqual(packet["prohibited_surface"], "sealed_hidden_oracle")
        self.assertIn("fixture_release_digest", packet)
        self.assertNotIn("hidden oracle secret", json.dumps(packet))
        self.assertNotIn("oracle_path", json.dumps(packet))
        expected_fixture = next(
            fixture
            for fixture in release["fixtures"]
            if fixture["scenario_class"] == "durable_state"
            and fixture["fixture_id"] == "durable-00"
        )
        self.assertEqual(
            packet["oracle_commitment_sha256"],
            expected_fixture["oracle_commitment_sha256"],
        )

    def test_results_require_complete_paired_blocks(self):
        manifest = self.manifest()
        release = self.release(manifest)

        with self.assertRaisesRegex(mod.ValidationError, "missing arm"):
            mod.validate_result_rows(
                self.result_rows(manifest, release, include_all_arms=False),
                manifest,
                release=release,
            )

    def test_score_requires_evidence_before_a_class_can_win(self):
        manifest = self.manifest()
        release = self.release(manifest)

        score = mod.score_result_rows([], manifest, release=release)

        self.assertEqual(score["status"], "unproven")
        self.assertEqual(score["verified_net_win_scenario_classes"], [])

    def test_paired_score_can_only_win_against_both_native_controls(self):
        manifest = self.manifest()
        release = self.release(manifest)
        score = mod.score_result_rows(self.result_rows(manifest, release), manifest, release=release)
        durable = score["scenario_classes"]["durable_state"]

        self.assertEqual(durable["status"], "win")
        self.assertEqual(durable["comparisons"]["claude_native"]["status"], "win")
        self.assertEqual(durable["comparisons"]["codex_native"]["status"], "win")
        self.assertEqual(score["verified_net_win_scenario_classes"], ["durable_state"])
        self.assertEqual(score["status"], "unproven")

    def test_zero_resolved_control_is_inconclusive_not_a_cost_win(self):
        manifest = self.manifest()
        release = self.release(manifest)
        rows = self.result_rows(manifest, release)
        for row in rows:
            if row["arm"] != "vidux_cockpit":
                row["success"] = 0

        score = mod.score_result_rows(rows, manifest, release=release)

        durable = score["scenario_classes"]["durable_state"]
        self.assertEqual(durable["status"], "inconclusive")
        self.assertEqual(durable["comparisons"]["claude_native"]["status"], "inconclusive")

    def test_high_token_overhead_cannot_claim_a_net_value_win(self):
        manifest = self.manifest()
        release = self.release(manifest)
        rows = self.result_rows(manifest, release)
        for row in rows:
            if row["arm"] == "vidux_cockpit":
                row["tokens"] = 10_000

        score = mod.score_result_rows(rows, manifest, release=release)

        durable = score["scenario_classes"]["durable_state"]
        self.assertEqual(durable["status"], "inconclusive")
        self.assertEqual(durable["comparisons"]["claude_native"]["status"], "inconclusive")

    def test_rows_must_bind_to_the_frozen_manifest_and_fixture_release(self):
        manifest = self.manifest()
        release = self.release(manifest)
        rows = self.result_rows(manifest, release)
        rows[0]["protocol_digest"] = "0" * 64

        with self.assertRaisesRegex(mod.ValidationError, "protocol digest does not match"):
            mod.validate_result_rows(rows, manifest, release=release)

        rows = self.result_rows(manifest, release)
        rows[0]["fixture_release_digest"] = "0" * 64
        with self.assertRaisesRegex(mod.ValidationError, "fixture release digest does not match"):
            mod.validate_result_rows(rows, manifest, release=release)

    def test_cli_refuses_to_seal_a_release_for_retired_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, _release, fixture_root, oracle_root, output = self.materialized_release(Path(tmp))
            index = {
                "release_id": "v2-cli-release",
                "evaluator_receipt_id": "independent-evaluator-receipt",
                "fixtures": [],
            }
            for scenario in manifest["scenario_classes"]:
                scenario_id = scenario["id"]
                for index_number in range(scenario["fixture_count_target"]):
                    fixture_id = self.fixture_id(scenario_id, index_number)
                    relative_path = f"{scenario_id}/{fixture_id}.json"
                    index["fixtures"].append(
                        {
                            "scenario_class": scenario_id,
                            "fixture_id": fixture_id,
                            "fixture_path": relative_path,
                            "oracle_path": relative_path,
                        }
                    )
            index_path = Path(tmp) / "private-index.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = mod.main(
                    [
                        "seal-release",
                        "--manifest",
                        str(manifest_path),
                        "--index",
                        str(index_path),
                        "--fixture-root",
                        str(fixture_root),
                        "--oracle-root",
                        str(oracle_root),
                        "--output",
                        str(output),
                    ]
                )
            error = json.loads(stderr.getvalue())

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertFalse(output.exists())
        self.assertIn("new protocol id", error["error"])

    def test_release_output_is_immutable_and_outside_secret_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, release, fixture_root, oracle_root, output = self.materialized_release(Path(tmp))
            output.write_text("already sealed", encoding="utf-8")
            with self.assertRaisesRegex(mod.ValidationError, "already exists"):
                mod.write_fixture_release(output, release, fixture_root=fixture_root, oracle_root=oracle_root)
            with self.assertRaisesRegex(mod.ValidationError, "outside fixture and oracle roots"):
                mod.write_fixture_release(
                    fixture_root / "release.json",
                    release,
                    fixture_root=fixture_root,
                    oracle_root=oracle_root,
                )

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
        self.assertEqual(payload["protocol_status"], "retired_non_runnable")
        self.assertIn(mod.NON_RUNNABLE_GATE, payload["gates"])

    def test_manifest_rules_cannot_mutate_to_posthoc_thresholds(self):
        manifest = copy.deepcopy(self.manifest())
        manifest["amendment_policy"]["posthoc_threshold_changes_forbidden"] = False

        errors = mod.validate_manifest(manifest)

        self.assertTrue(any("forbid posthoc threshold changes" in error for error in errors))
