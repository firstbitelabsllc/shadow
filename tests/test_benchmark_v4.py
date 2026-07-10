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
        self.assertNotIn("schedule", cli["commands"])
        self.assertNotIn("decide", cli["commands"])

    def test_manifest_rejects_synthetic_claim_retry_and_recovery_drift(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["evidence_modes"]["synthetic"]["claim_eligible"] = True
        tampered["measurement_contract"]["retry_usage_is_cumulative_in_decision_statistics"] = False
        tampered["journal_contract"]["torn_tail_policy"] = "reject"
        errors = mod.validate_manifest(tampered)
        self.assertTrue(any("synthetic" in error for error in errors), errors)
        self.assertTrue(any("retry" in error for error in errors), errors)
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
        self.assertFalse(
            mod.claim_eligible("real", self.status, self.manifest, bundle_errors=errors),
            "a valid release cannot bypass the non-runnable administrative status",
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
        first = mod.make_journal_row(0, "initialize-journal", "journal_initialized", {}, None)
        second = mod.make_journal_row(
            1,
            "start-attempt",
            "attempt_started",
            {"attempt": 1},
            first["event_sha256"],
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

    def test_terminated_invalid_journal_row_and_hardlink_still_fail_closed(self) -> None:
        row = mod.make_journal_row(0, "initialize-journal", "journal_initialized", {}, None)
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


if __name__ == "__main__":
    unittest.main()
