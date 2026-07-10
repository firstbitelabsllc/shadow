"""Adversarial integrity coverage for the non-runnable benchmark v4."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-benchmark-v4.py"
MANIFEST_PATH = ROOT / "benchmarks" / "v4" / "manifest.json"
STATUS_PATH = ROOT / "benchmarks" / "v4" / "STATUS.json"

spec = importlib.util.spec_from_file_location("vidux_benchmark_v4", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class BenchmarkV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.fixtures = self.root / "fixtures"
        self.artifacts.mkdir()
        self.fixtures.mkdir()
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))

    def store(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        (self.artifacts / digest).write_bytes(raw)
        return digest

    def store_json(self, value: dict) -> str:
        return self.store(mod.canonical_json(value))

    def profile(self, pair_id: str) -> dict:
        provider, runner = {
            "anthropic_claude": ("anthropic", "claude_code"),
            "openai_codex": ("openai", "codex"),
        }[pair_id]
        artifact_fields = {
            key: self.store(f"{pair_id}:{key}\n".encode("utf-8"))
            for key in (
                "inference_profile_sha256",
                "runner_binary_sha256",
                "runner_args_sha256",
                "permission_profile_sha256",
                "tool_surface_sha256",
                "base_prompt_sha256",
                "system_instructions_sha256",
                "developer_instructions_sha256",
            )
        }
        return {
            "schema_version": 1,
            "pair_id": pair_id,
            "provider": provider,
            "requested_model_id": f"{pair_id}-requested",
            "resolved_model_id": f"{pair_id}-resolved",
            "provider_api_surface": "bounded-cli-v1",
            "runner_family": runner,
            "runtime_version": "test-runtime-1",
            **artifact_fields,
        }

    def fixture(self, stage: str, scenario: str, index: int) -> tuple[dict, dict]:
        fixture_id = f"{stage}-{scenario.replace('_', '-')}-{index:02d}"
        workspace_digest = self.store(f"workspace:{fixture_id}\n".encode("utf-8"))
        interruption = (
            {
                "trigger": "terminate after the second required transition",
                "resume_entrypoint": "restart in the same fresh fixture workspace",
            }
            if scenario == "interruption_recovery"
            else None
        )
        payload = {
            "schema_version": 1,
            "fixture_id": fixture_id,
            "stage": stage,
            "scenario_class": scenario,
            "task_prompt": f"Complete the bounded {scenario} task for fixture {fixture_id}.",
            "workspace_snapshot": {
                "artifact_sha256": workspace_digest,
                "format": "tar_posix_ustar_v1",
            },
            "execution_contract": {
                "scenario_class": scenario,
                "required_state_transitions": ["inspect authority", "complete task", "record proof"],
                "proof_requirements": ["machine-readable result", "command receipt"],
                "interruption": interruption,
            },
        }
        raw = mod.canonical_json(payload)
        relative = Path(stage) / scenario / f"{fixture_id}.json"
        path = self.fixtures / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        entry = {
            "stage": stage,
            "scenario_class": scenario,
            "fixture_id": fixture_id,
            "fixture_path": relative.as_posix(),
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        }
        return payload, entry

    def sign_release(self, release: dict, private_key: Path) -> None:
        message = self.root / "release-core.bin"
        message.write_bytes(mod.release_core_bytes(release))
        signature_path = Path(str(message) + ".sig")
        signature_path.unlink(missing_ok=True)
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(private_key),
                "-n",
                mod.SIGNATURE_NAMESPACE,
                str(message),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        signature_digest = self.store(signature_path.read_bytes())
        receipt = {
            "schema_version": 1,
            "evaluator_registration_sha256": release["evaluator_registration_sha256"],
            "release_core_sha256": mod.release_core_digest(release),
            "signature_sha256": signature_digest,
        }
        release["evaluator_release_receipt_sha256"] = self.store_json(receipt)

    def signed_release(self, *, evidence_mode: str = "real") -> tuple[dict, str]:
        if shutil.which("ssh-keygen") is None:
            self.skipTest("OpenSSH ssh-keygen is required for the authenticated release proof")
        private_key = self.root / "evaluator-key"
        generated = subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.private_key = private_key
        public_key_digest = self.store(private_key.with_suffix(".pub").read_bytes())
        implementation_digest = self.store(b"bounded hidden evaluator implementation\n")
        registration = {
            "schema_version": 1,
            "evaluator_id": "external-evaluator-test",
            "signature_scheme": "openssh_sshsig_ed25519",
            "signature_namespace": mod.SIGNATURE_NAMESPACE,
            "public_key_sha256": public_key_digest,
            "implementation_sha256": implementation_digest,
            "registered_at": "2026-07-10T15:20:41Z",
        }
        registration_digest = self.store_json(registration)
        provider_profiles = {
            pair_id: self.store_json(self.profile(pair_id))
            for pair_id in mod.PAIR_IDS
        }
        entries: list[dict] = []
        for scenario in mod.SCENARIO_IDS:
            _fixture, entry = self.fixture("pilot", scenario, 0)
            entries.append(entry)
            for index in range(12):
                _fixture, entry = self.fixture("full", scenario, index)
                entries.append(entry)
        release = {
            "schema_version": 1,
            "release_id": "external-release-test",
            "protocol_id": mod.PROTOCOL_ID,
            "protocol_digest": mod.digest_json(self.manifest, "manifest"),
            "evidence_mode": evidence_mode,
            "randomization_seed": hashlib.sha256(b"randomization seed").hexdigest(),
            "evaluator_registration_sha256": registration_digest,
            "evaluator_release_receipt_sha256": "0" * 64,
            "provider_profiles": provider_profiles,
            "fixtures": entries,
        }
        self.sign_release(release, private_key)
        return release, registration_digest

    def schedule(self, release: dict, registration_digest: str) -> dict:
        return mod.build_schedule(
            self.manifest,
            release,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )

    def signed_evaluator_result_receipt(
        self,
        release: dict,
        schedule: dict,
    ) -> tuple[dict, dict, dict]:
        run = schedule["runs"][0]
        receipt_digests = {
            "provider_receipt_sha256": self.store(b"provider receipt\n"),
            "runner_receipt_sha256": self.store(b"runner receipt\n"),
            "transcript_receipt_sha256": self.store(b"transcript receipt\n"),
        }
        runner_result = {
            "schema_version": 1,
            "protocol_id": mod.PROTOCOL_ID,
            "protocol_digest": schedule["protocol_digest"],
            "release_core_sha256": schedule["release_core_sha256"],
            "schedule_digest": mod.schedule_digest(schedule),
            "run_id": run["run_id"],
            "attempt_number": 1,
            "attempt_id": mod.attempt_id_for(run["run_id"], 1),
            "status": "runner_completed",
            "metrics": {
                "elapsed_ms": 1000,
                "tokens": 100,
                "cost_microusd": 1000,
                "operator_touches": 0,
            },
            **receipt_digests,
        }
        runner_result_digest = self.store_json(runner_result)
        evaluator_result = {
            "schema_version": 1,
            "protocol_id": mod.PROTOCOL_ID,
            "protocol_digest": schedule["protocol_digest"],
            "release_core_sha256": schedule["release_core_sha256"],
            "schedule_digest": mod.schedule_digest(schedule),
            "run_id": run["run_id"],
            "attempt_number": 1,
            "attempt_id": mod.attempt_id_for(run["run_id"], 1),
            "fixture_id": run["fixture_id"],
            "runner_result_sha256": runner_result_digest,
            "evaluator_run_sha256": self.store(b"hidden evaluator run receipt\n"),
            "checks": [
                {
                    "id": "required-oracle",
                    "required": True,
                    "passed": True,
                    "evidence_sha256": self.store(b"hidden check evidence\n"),
                }
            ],
            "resume_transitions": {"missed": 0, "repeated": 0, "invented": 0},
            "forbidden_action": False,
        }
        evaluator_result_digest = self.store_json(evaluator_result)
        message = self.root / "evaluator-result.bin"
        message.write_bytes(mod.evaluator_result_bytes(evaluator_result))
        signature_path = Path(str(message) + ".sig")
        signature_path.unlink(missing_ok=True)
        signed = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(self.private_key),
                "-n",
                mod.SIGNATURE_NAMESPACE,
                str(message),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(signed.returncode, 0, signed.stderr)
        receipt = {
            "schema_version": 1,
            "evaluator_registration_sha256": release["evaluator_registration_sha256"],
            "evaluator_result_sha256": evaluator_result_digest,
            "signature_sha256": self.store(signature_path.read_bytes()),
        }
        return receipt, runner_result, evaluator_result

    def test_static_preflight_is_valid_non_runnable_and_has_no_runner_commands(self) -> None:
        self.assertEqual(mod.validate_manifest(self.manifest), [])
        self.assertEqual(mod.validate_status(self.status, self.manifest), [])
        receipt = mod.readiness(self.manifest, self.status)
        self.assertTrue(receipt["integrity_preflight_valid"])
        self.assertFalse(receipt["ready_for_provider_spend"])
        self.assertFalse(receipt["claim_eligible"])
        self.assertIn("benchmark v4 remains a non-runnable integrity preflight", receipt["gates"])
        self.assertIn("provider transport is not implemented", receipt["gates"])

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        cli = json.loads(result.stdout)
        self.assertFalse(cli["runnable"])
        self.assertIn("schedule", cli["commands"])
        self.assertIn("result-check", cli["commands"])
        self.assertNotIn("decide", cli["commands"])

    def test_manifest_rejects_synthetic_claim_retry_and_recovery_drift(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["evidence_modes"]["synthetic"]["claim_eligible"] = True
        tampered["measurement_contract"]["retry_counting"] = "Ignore retry usage."
        tampered["journal_contract"]["torn_tail_policy"] = "reject"
        errors = mod.validate_manifest(tampered)
        self.assertTrue(any("synthetic" in error for error in errors), errors)
        self.assertTrue(any("measurement_contract" in error for error in errors), errors)
        self.assertTrue(any("recovery" in error for error in errors), errors)

    def test_authenticated_real_release_resolves_every_bound_artifact(self) -> None:
        release, registration_digest = self.signed_release()
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertEqual(errors, [])
        registered_status = {
            **self.status,
            "evaluator_registration_sha256": registration_digest,
            "next_gate": "validate_authenticated_external_evaluator_release_then_review_runner",
        }
        self.assertEqual(mod.validate_status(registered_status, self.manifest), [])
        readiness = mod.readiness(
            self.manifest,
            registered_status,
            release=release,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
        )
        self.assertNotIn("evaluator registration is not frozen", readiness["gates"])
        self.assertNotIn("authenticated external evaluator release is required", readiness["gates"])
        self.assertFalse(readiness["ready_for_provider_spend"])
        self.assertIn("provider transport is not implemented", readiness["gates"])
        self.assertFalse(
            mod.claim_eligible("real", self.status, self.manifest, bundle_errors=errors),
            "a valid release cannot bypass the non-runnable administrative status",
        )

    def test_embedded_outcome_contracts_exactly_match_retired_v3(self) -> None:
        v3 = json.loads((ROOT / "benchmarks" / "v3" / "manifest.json").read_text(encoding="utf-8"))
        for key in self.manifest["preserved_experiment_contract"]["embedded_outcome_contracts"]:
            with self.subTest(key=key):
                self.assertEqual(self.manifest[key], v3[key])

    def test_authenticated_release_generates_one_deterministic_complete_schedule(self) -> None:
        release, registration_digest = self.signed_release()
        first = self.schedule(release, registration_digest)
        second = self.schedule(release, registration_digest)
        self.assertEqual(first, second)
        self.assertEqual(len(first["runs"]), 208)
        self.assertEqual(sum(run["stage"] == "pilot" for run in first["runs"]), 16)
        self.assertEqual(sum(run["stage"] == "full" for run in first["runs"]), 192)
        self.assertEqual(len({run["run_id"] for run in first["runs"]}), 208)
        self.assertEqual(
            mod.validate_schedule(
                first,
                self.manifest,
                release,
                fixture_root=self.fixtures,
                artifact_root=self.artifacts,
                expected_registration_sha256=registration_digest,
            ),
            [],
        )

        tampered = copy.deepcopy(first)
        tampered["runs"][0]["budget"]["tokens"] += 1
        errors = mod.validate_schedule(
            tampered,
            self.manifest,
            release,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("deterministic" in error for error in errors), errors)

    def test_signed_evaluator_result_resolves_evidence_and_tamper_fails_closed(self) -> None:
        release, registration_digest = self.signed_release()
        schedule = self.schedule(release, registration_digest)
        receipt, _runner_result, evaluator_result = self.signed_evaluator_result_receipt(
            release,
            schedule,
        )
        errors = mod.validate_evaluator_result_bundle(
            receipt,
            schedule,
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertEqual(errors, [])

        tampered_result = copy.deepcopy(evaluator_result)
        tampered_result["forbidden_action"] = True
        tampered_receipt = {
            **receipt,
            "evaluator_result_sha256": self.store_json(tampered_result),
        }
        errors = mod.validate_evaluator_result_bundle(
            tampered_receipt,
            schedule,
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("signature verification failed" in error for error in errors), errors)

        wrong_identity = {**receipt, "evaluator_registration_sha256": "f" * 64}
        errors = mod.validate_evaluator_result_bundle(
            wrong_identity,
            schedule,
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("registration" in error for error in errors), errors)

    def test_dispatch_reservation_prevents_reinvoke_and_reconciles_cumulative_receipts(self) -> None:
        release, registration_digest = self.signed_release()
        schedule = self.schedule(release, registration_digest)
        run = schedule["runs"][0]
        journal = self.root / "dispatch.jsonl"
        mod.initialize_dispatch_journal(journal, schedule, operation_id="initialize-dispatch")
        request_digest = self.store(b"provider request\n")
        reservation = mod.reserve_provider_dispatch(
            journal,
            schedule,
            operation_id="reserve-first-attempt",
            run_id=run["run_id"],
            attempt_number=1,
            request_sha256=request_digest,
        )
        self.assertTrue(reservation["provider_invocation_authorized_once"])
        rows = mod.validate_journal_bytes(journal.read_bytes(), schedule)
        gate = mod.dispatch_gate(rows, schedule, run["run_id"], 1)
        self.assertEqual(gate["state"], "reconciliation_required")
        self.assertFalse(gate["may_invoke_provider"])
        self.assertTrue(gate["must_reconcile_receipt"])

        with self.assertRaisesRegex(mod.ValidationError, "prior_reconciliation_required"):
            mod.reserve_provider_dispatch(
                journal,
                schedule,
                operation_id="reserve-second-before-receipt",
                run_id=run["run_id"],
                attempt_number=2,
                request_sha256=request_digest,
            )

        with self.assertRaisesRegex(mod.ValidationError, "operation_id is duplicated"):
            mod.reserve_provider_dispatch(
                journal,
                schedule,
                operation_id="reserve-first-attempt",
                run_id=run["run_id"],
                attempt_number=1,
                request_sha256=request_digest,
            )

        with self.assertRaisesRegex(mod.ValidationError, "reinvocation is forbidden"):
            mod.reserve_provider_dispatch(
                journal,
                schedule,
                operation_id="reserve-same-attempt-again",
                run_id=run["run_id"],
                attempt_number=1,
                request_sha256=request_digest,
            )

        provider_receipt = self.store(b"provider receipt bytes\n")
        metrics = {
            "elapsed_ms": 1000,
            "tokens": 100,
            "cost_microusd": 1000,
            "operator_touches": 0,
        }
        mod.reconcile_provider_receipt(
            journal,
            schedule,
            operation_id="reconcile-first-attempt",
            run_id=run["run_id"],
            attempt_number=1,
            provider_receipt_sha256=provider_receipt,
            metrics=metrics,
            artifact_root=self.artifacts,
        )
        with self.assertRaisesRegex(mod.ValidationError, "retry_authorization_required"):
            mod.reserve_provider_dispatch(
                journal,
                schedule,
                operation_id="reserve-second-without-failure",
                run_id=run["run_id"],
                attempt_number=2,
                request_sha256=request_digest,
            )
        failure_receipt = self.store(b"bounded infrastructure failure receipt\n")
        mod.authorize_provider_retry(
            journal,
            schedule,
            operation_id="authorize-second-attempt",
            run_id=run["run_id"],
            attempt_number=2,
            failure_receipt_sha256=failure_receipt,
            artifact_root=self.artifacts,
        )
        mod.reserve_provider_dispatch(
            journal,
            schedule,
            operation_id="reserve-second-attempt",
            run_id=run["run_id"],
            attempt_number=2,
            request_sha256=request_digest,
        )
        second_provider_receipt = self.store(b"second provider receipt bytes\n")
        mod.reconcile_provider_receipt(
            journal,
            schedule,
            operation_id="reconcile-second-attempt",
            run_id=run["run_id"],
            attempt_number=2,
            provider_receipt_sha256=second_provider_receipt,
            metrics=metrics,
            artifact_root=self.artifacts,
        )
        rows = mod.validate_journal_bytes(journal.read_bytes(), schedule)
        summary = mod.dispatch_summary(rows, schedule)
        self.assertEqual(summary["reserved_attempts"], 2)
        self.assertEqual(summary["reconciled_attempts"], 2)
        self.assertEqual(summary["ambiguous_attempts"], [])
        self.assertEqual(
            summary["cumulative_metrics"],
            {key: value * 2 for key, value in metrics.items()},
        )
        self.assertEqual(
            mod.dispatch_gate(rows, schedule, run["run_id"], 1)["state"],
            "receipt_bound",
        )

    def test_synthetic_release_is_permanently_claim_ineligible(self) -> None:
        release, registration_digest = self.signed_release(evidence_mode="synthetic")
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertEqual(errors, [])
        permissive_status = {
            **self.status,
            "runnable": True,
            "provider_transport_enabled": True,
            "claim_eligible": True,
            "evaluator_registration_sha256": registration_digest,
        }
        self.assertFalse(
            mod.claim_eligible(
                "synthetic",
                permissive_status,
                self.manifest,
                bundle_errors=[],
            )
        )
        self.assertFalse(
            mod.claim_eligible(
                "real",
                permissive_status,
                self.manifest,
                bundle_errors=[],
            ),
            "caller-forged status booleans cannot bypass the validated administrative state",
        )

    def test_digest_shaped_missing_or_aliased_artifact_is_not_evidence(self) -> None:
        release, registration_digest = self.signed_release()
        profile_digest = release["provider_profiles"]["anthropic_claude"]
        profile = json.loads((self.artifacts / profile_digest).read_text(encoding="utf-8"))
        target = self.artifacts / profile["runner_binary_sha256"]
        original = target.read_bytes()
        target.unlink()
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("runner_binary" in error and "opened safely" in error for error in errors), errors)

        external = self.root / "external-artifact"
        external.write_bytes(original)
        os.link(external, target)
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("single-link regular" in error for error in errors), errors)

    def test_fixture_semantics_are_checked_after_hash_verification(self) -> None:
        release, registration_digest = self.signed_release()
        entry = release["fixtures"][0]
        path = self.fixtures / entry["fixture_path"]
        fixture = json.loads(path.read_text(encoding="utf-8"))
        fixture["task_prompt"] = ""
        raw = mod.canonical_json(fixture)
        path.write_bytes(raw)
        entry["fixture_sha256"] = hashlib.sha256(raw).hexdigest()
        private_key = self.root / "evaluator-key"
        self.sign_release(release, private_key)
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("task_prompt" in error for error in errors), errors)

    def test_release_signature_tamper_fails_closed(self) -> None:
        release, registration_digest = self.signed_release()
        release["randomization_seed"] = hashlib.sha256(b"changed seed").hexdigest()
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("canonical release core" in error for error in errors), errors)

    def test_rebound_invalid_signature_bytes_fail_openssh_verification(self) -> None:
        release, registration_digest = self.signed_release()
        receipt_digest = release["evaluator_release_receipt_sha256"]
        receipt = json.loads((self.artifacts / receipt_digest).read_text(encoding="utf-8"))
        receipt["signature_sha256"] = self.store(b"not an OpenSSH signature\n")
        release["evaluator_release_receipt_sha256"] = self.store_json(receipt)
        errors = mod.validate_release_bundle(
            release,
            self.manifest,
            fixture_root=self.fixtures,
            artifact_root=self.artifacts,
            expected_registration_sha256=registration_digest,
        )
        self.assertTrue(any("signature verification failed" in error for error in errors), errors)

    def test_torn_tail_recovery_is_bounded_hash_chained_and_idempotent(self) -> None:
        schedule_sha256 = "a" * 64
        run_id = "run-" + "b" * 20
        first = mod.make_journal_row(
            0,
            "initialize-journal",
            "journal_initialized",
            {"run_count": 1},
            None,
            schedule_sha256=schedule_sha256,
        )
        second = mod.make_journal_row(
            1,
            "reserve-attempt",
            "provider_dispatch_reserved",
            {
                "dispatch_id": mod.dispatch_id_for(schedule_sha256, run_id, 1),
                "request_sha256": "c" * 64,
                "provider_pair_id": "anthropic_claude",
            },
            first["event_sha256"],
            schedule_sha256=schedule_sha256,
            run_id=run_id,
            attempt_number=1,
            attempt_id=mod.attempt_id_for(run_id, 1),
        )
        path = self.root / "journal.jsonl"
        torn = mod.canonical_json(second)[:47]
        path.write_bytes(mod.canonical_json(first) + b"\n" + torn)
        receipt = mod.recover_journal_tail(path)
        self.assertTrue(receipt["recovered"])
        self.assertEqual(receipt["discarded_fragment_sha256"], hashlib.sha256(torn).hexdigest())
        rows = mod.validate_journal_bytes(path.read_bytes())
        self.assertEqual([row["event"] for row in rows], ["journal_initialized", "journal_tail_recovered"])
        self.assertEqual(rows[-1]["previous_event_sha256"], first["event_sha256"])
        self.assertEqual(rows[-1]["event_sha256"], receipt["recovery_receipt_sha256"])
        self.assertFalse(mod.recover_journal_tail(path)["recovered"])

    def test_journal_initialization_fsyncs_the_parent_directory(self) -> None:
        release, registration_digest = self.signed_release()
        schedule = self.schedule(release, registration_digest)
        path = self.root / "durable-journal.jsonl"
        with mock.patch.object(mod, "_fsync_directory", wraps=mod._fsync_directory) as directory_fsync:
            mod.initialize_dispatch_journal(
                path,
                schedule,
                operation_id="initialize-durable-journal",
            )
        directory_fsync.assert_called_once_with(path.parent)

    def test_recovery_rejects_invalid_committed_provider_metrics_without_schedule(self) -> None:
        schedule_sha256 = "a" * 64
        run_id = "run-" + "b" * 20
        initialized = mod.make_journal_row(
            0,
            "initialize-journal",
            "journal_initialized",
            {"run_count": 1},
            None,
            schedule_sha256=schedule_sha256,
        )
        reserved = mod.make_journal_row(
            1,
            "reserve-attempt",
            "provider_dispatch_reserved",
            {
                "dispatch_id": mod.dispatch_id_for(schedule_sha256, run_id, 1),
                "request_sha256": "c" * 64,
                "provider_pair_id": "anthropic_claude",
            },
            initialized["event_sha256"],
            schedule_sha256=schedule_sha256,
            run_id=run_id,
            attempt_number=1,
            attempt_id=mod.attempt_id_for(run_id, 1),
        )
        reconciled = mod.make_journal_row(
            2,
            "reconcile-attempt",
            "provider_receipt_reconciled",
            {
                "dispatch_id": mod.dispatch_id_for(schedule_sha256, run_id, 1),
                "provider_receipt_sha256": "d" * 64,
                "metrics": {"elapsed_ms": -1},
            },
            reserved["event_sha256"],
            schedule_sha256=schedule_sha256,
            run_id=run_id,
            attempt_number=1,
            attempt_id=mod.attempt_id_for(run_id, 1),
        )
        path = self.root / "invalid-metrics.jsonl"
        path.write_bytes(
            b"".join(
                mod.canonical_json(row) + b"\n"
                for row in (initialized, reserved, reconciled)
            )
        )
        with self.assertRaisesRegex(mod.ValidationError, "metrics must contain exactly"):
            mod.recover_journal_tail(path)

        invalid_initialization = mod.make_journal_row(
            0,
            "initialize-invalid-journal",
            "journal_initialized",
            {"run_count": True},
            None,
            schedule_sha256=schedule_sha256,
        )
        path.write_bytes(mod.canonical_json(invalid_initialization) + b"\n")
        with self.assertRaisesRegex(mod.ValidationError, "schedule run count"):
            mod.recover_journal_tail(path)

        invalid_pair = mod.make_journal_row(
            1,
            "reserve-invalid-pair",
            "provider_dispatch_reserved",
            {
                "dispatch_id": mod.dispatch_id_for(schedule_sha256, run_id, 1),
                "request_sha256": "c" * 64,
                "provider_pair_id": "unregistered_provider",
            },
            initialized["event_sha256"],
            schedule_sha256=schedule_sha256,
            run_id=run_id,
            attempt_number=1,
            attempt_id=mod.attempt_id_for(run_id, 1),
        )
        path.write_bytes(
            mod.canonical_json(initialized) + b"\n" + mod.canonical_json(invalid_pair) + b"\n"
        )
        with self.assertRaisesRegex(mod.ValidationError, "provider dispatch pair is invalid"):
            mod.recover_journal_tail(path)

    def test_terminated_invalid_journal_row_and_hardlink_still_fail_closed(self) -> None:
        row = mod.make_journal_row(
            0,
            "initialize-journal",
            "journal_initialized",
            {"run_count": 1},
            None,
            schedule_sha256="a" * 64,
        )
        row["payload"]["tampered"] = True
        path = self.root / "invalid.jsonl"
        path.write_bytes(mod.canonical_json(row) + b"\n")
        with self.assertRaisesRegex(mod.ValidationError, "event hash is invalid"):
            mod.recover_journal_tail(path)

        path.unlink()
        external = self.root / "external-journal"
        external.write_bytes(mod.canonical_json(row) + b"\n")
        os.link(external, path)
        with self.assertRaisesRegex(mod.ValidationError, "single-link regular file"):
            mod.recover_journal_tail(path)

    def test_cli_readiness_is_explicitly_gated(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "readiness"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertFalse(receipt["ready_for_provider_spend"])
        self.assertFalse(receipt["claim_eligible"])
        self.assertEqual(receipt["verified_net_win_classes"], 0)

    def test_public_benchmark_front_door_routes_to_v4_and_refuses_legacy_runs(self) -> None:
        env = {**os.environ, "VIDUX_ROOT": str(ROOT)}
        validate = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "benchmark", "validate"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)
        validated = json.loads(validate.stdout)
        self.assertEqual(validated["protocol_id"], mod.PROTOCOL_ID)
        self.assertFalse(validated["runnable"])

        default = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "benchmark"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(default.returncode, 2, default.stderr)
        readiness = json.loads(default.stdout)
        self.assertEqual(readiness["protocol_id"], mod.PROTOCOL_ID)
        self.assertFalse(readiness["ready_for_provider_spend"])

        for legacy_action in ("v2", "v3", "run", "pilot", "full", "decide"):
            with self.subTest(legacy_action=legacy_action):
                refused = subprocess.run(
                    [str(ROOT / "bin" / "vidux"), "benchmark", legacy_action],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(refused.returncode, 2)
                self.assertIn("vidux-cockpit-v4", refused.stderr)
                self.assertIn("historical evidence only", refused.stderr)

    def test_benchmark_help_completions_and_skill_name_one_current_authority(self) -> None:
        help_result = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "help", "benchmark"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertEqual(help_result.stderr, "")
        self.assertIn("current benchmark authority", help_result.stdout)
        self.assertIn("Legacy v2/v3", help_result.stdout)

        for shell in ("bash", "zsh", "fish"):
            with self.subTest(shell=shell):
                completion = subprocess.run(
                    [str(ROOT / "scripts" / "vidux-completion.sh"), shell],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completion.returncode, 0, completion.stderr)
                self.assertIn("benchmark", completion.stdout)
                self.assertIn("release-check", completion.stdout)
                self.assertIn("schedule", completion.stdout)
                self.assertIn("result-check", completion.stdout)

        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Current Benchmark Authority", skill)
        self.assertIn("vidux benchmark", skill)
        self.assertIn("historical evidence", skill)


if __name__ == "__main__":
    unittest.main()
