"""Adversarial contract coverage for the Vidux benchmark-v3 preflight."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-benchmark-v3.py"
MANIFEST_PATH = ROOT / "benchmarks" / "v3" / "manifest.json"
STATUS_PATH = ROOT / "benchmarks" / "v3" / "STATUS.json"

spec = importlib.util.spec_from_file_location("vidux_benchmark_v3", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def record_historical_journal_event(
    path: Path,
    schedule: dict,
    request: dict,
    queue: multiprocessing.Queue,
) -> None:
    try:
        row, appended = mod.record_journal_event(path, schedule, request)
        queue.put({"ok": True, "appended": appended, "sequence": row["sequence"]})
    except Exception as error:  # pragma: no cover - reported to the parent assertion
        queue.put({"ok": False, "error": repr(error)})


def sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class BenchmarkV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture_root = self.root / "fixtures"
        self.fixture_root.mkdir()
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        self.release = self.build_release()
        self.schedule = mod.build_schedule(
            self.manifest,
            self.release,
            fixture_root=self.fixture_root,
        )

    @staticmethod
    def profile(pair_id: str, provider: str, runner: str) -> dict:
        return {
            "pair_id": pair_id,
            "provider": provider,
            "requested_model_id": f"{pair_id}-model",
            "resolved_model_id": f"{pair_id}-model-20260710",
            "provider_api_surface": f"{provider}-cli",
            "inference_profile_sha256": sha(f"inference:{pair_id}"),
            "runner_family": runner,
            "runtime_version": "test-runtime-1",
            "runner_binary_sha256": sha(f"binary:{pair_id}"),
            "runner_args_sha256": sha(f"args:{pair_id}"),
            "permission_profile_sha256": sha(f"permissions:{pair_id}"),
            "tool_surface_sha256": sha(f"tools:{pair_id}"),
            "base_prompt_sha256": sha(f"base-prompt:{pair_id}"),
            "system_instructions_sha256": sha(f"system:{pair_id}"),
            "developer_instructions_sha256": sha(f"developer:{pair_id}"),
            "workspace_snapshot_sha256": sha("workspace:shared"),
        }

    def build_release(self, *, seed: str = "seed-one") -> dict:
        fixtures: list[dict] = []
        for stage, count in (("pilot", 1), ("full", 12)):
            for scenario in mod.SCENARIO_IDS:
                prefix = scenario.replace("_", "-")
                for index in range(1, count + 1):
                    fixture_id = f"{stage}-{prefix}-{index:02d}"
                    relative = f"{stage}/{scenario}/{fixture_id}.json"
                    path = self.fixture_root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    content = json.dumps(
                        {
                            "stage": stage,
                            "scenario": scenario,
                            "fixture_id": fixture_id,
                        },
                        sort_keys=True,
                    ).encode("utf-8")
                    path.write_bytes(content)
                    fixtures.append(
                        {
                            "stage": stage,
                            "scenario_class": scenario,
                            "fixture_id": fixture_id,
                            "fixture_path": relative,
                            "fixture_sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
        return {
            "schema_version": 1,
            "release_id": "evaluator-release-20260710",
            "protocol_id": mod.PROTOCOL_ID,
            "protocol_digest": mod.digest_json(self.manifest, "protocol"),
            "randomization_seed": sha(seed),
            "evaluator_receipt_sha256": sha("evaluator-receipt"),
            "provider_profiles": [
                self.profile("anthropic_claude", "anthropic", "claude_code"),
                self.profile("openai_codex", "openai", "codex"),
            ],
            "fixtures": fixtures,
        }

    def run_for(
        self,
        *,
        stage: str = "pilot",
        scenario: str = "durable_state",
        arm: str = "claude_native",
    ) -> dict:
        return next(
            run
            for run in self.schedule["runs"]
            if run["stage"] == stage
            and run["scenario_class"] == scenario
            and run["arm"] == arm
        )

    @staticmethod
    def metrics(**overrides: int) -> dict:
        values = {
            "elapsed_ms": 100,
            "tokens": 200,
            "cost_microusd": 300,
            "operator_touches": 0,
        }
        values.update(overrides)
        return values

    def usage_payload(self, **extra: object) -> dict:
        payload: dict[str, object] = {
            "metrics": self.metrics(),
            "provider_receipt_sha256": sha("provider-receipt"),
            "runner_receipt_sha256": sha("runner-receipt"),
            "transcript_receipt_sha256": sha("transcript-receipt"),
        }
        payload.update(extra)
        return payload

    def result(
        self,
        run: dict | None = None,
        *,
        status: str = "runner_completed",
        metrics: dict | None = None,
    ) -> dict:
        run = run or self.run_for()
        return {
            "schema_version": 1,
            "schedule_digest": mod.digest_json(self.schedule, "schedule"),
            "run_id": run["run_id"],
            "attempt_id": mod.attempt_id_for(run["run_id"], 1),
            "status": status,
            "metrics": metrics or self.metrics(),
            "provider_receipt_sha256": sha("provider-receipt"),
            "runner_receipt_sha256": sha("runner-receipt"),
            "transcript_receipt_sha256": sha("transcript-receipt"),
        }

    def evaluator_result(
        self,
        run: dict | None = None,
        result: dict | None = None,
    ) -> dict:
        run = run or self.run_for()
        result = result or self.result(run)
        return {
            "schema_version": 1,
            "protocol_id": mod.PROTOCOL_ID,
            "run_id": run["run_id"],
            "fixture_id": run["fixture_id"],
            "runner_result_sha256": mod.digest_json(result, "runner-result"),
            "evaluator_run_sha256": sha("private-evaluator-run"),
            "checks": [
                {
                    "id": "required-main-check",
                    "required": True,
                    "passed": True,
                    "evidence_sha256": sha("check-evidence"),
                }
            ],
            "resume_transitions": {"missed": 1, "repeated": 2, "invented": 3},
            "forbidden_action": False,
        }

    def journal_path(self) -> Path:
        return self.root / "attempts.jsonl"

    def initialize_journal(self) -> Path:
        path = self.journal_path()
        _row, appended = mod.initialize_journal(
            path,
            self.schedule,
            operation_id="initialize-journal",
        )
        self.assertTrue(appended)
        return path

    def journal_result(
        self,
        path: Path,
        run: dict,
        result: dict,
        *,
        prefix: str,
    ) -> None:
        attempt = result["attempt_id"]
        usage = {
            "metrics": dict(result["metrics"]),
            "provider_receipt_sha256": result["provider_receipt_sha256"],
            "runner_receipt_sha256": result["runner_receipt_sha256"],
            "transcript_receipt_sha256": result["transcript_receipt_sha256"],
        }
        requests = [
            self.request(
                f"{prefix}-claim",
                "attempt_claimed",
                run,
                attempt,
                {"worker_id": "worker-one"},
            ),
            self.request(f"{prefix}-start", "attempt_started", run, attempt, {}),
        ]
        if result["status"] == "runner_completed":
            requests.append(
                self.request(
                    f"{prefix}-complete",
                    "runner_completed",
                    run,
                    attempt,
                    usage,
                )
            )
        else:
            failure_kind = {
                "runner_failed": "runner_failure",
                "budget_exhausted": "budget_exhausted",
                "infrastructure_exhausted": "infrastructure_exhausted",
            }[result["status"]]
            usage.update(
                failure_kind=failure_kind,
                failure_receipt_sha256=sha(f"{prefix}-failure"),
            )
            requests.append(
                self.request(
                    f"{prefix}-failed",
                    "attempt_failed",
                    run,
                    attempt,
                    usage,
                )
            )
        for request in requests:
            mod.record_journal_event(path, self.schedule, request)

    def pilot_bundle(
        self,
        *,
        budget_exhausted_run_id: str | None = None,
    ) -> tuple[Path, dict]:
        path = self.initialize_journal()
        adjudications: list[dict] = []
        pilot_runs = [run for run in self.schedule["runs"] if run["stage"] == "pilot"]
        for index, run in enumerate(pilot_runs):
            status = (
                "budget_exhausted"
                if run["run_id"] == budget_exhausted_run_id
                else "runner_completed"
            )
            result = self.result(run, status=status)
            prefix = f"pilot-{index:03d}"
            self.journal_result(path, run, result, prefix=prefix)
            receipt, _event, appended = mod.record_adjudication(
                path,
                self.schedule,
                result,
                self.evaluator_result(run, result),
                operation_id=f"{prefix}-adjudicate",
            )
            self.assertTrue(appended)
            adjudications.append(receipt)
        return path, {
            "schema_version": 1,
            "schedule_digest": mod.digest_json(self.schedule, "schedule"),
            "stage": "pilot",
            "adjudications": adjudications,
        }

    @staticmethod
    def request(
        operation_id: str,
        event: str,
        run: dict,
        attempt_id: str,
        payload: dict,
    ) -> dict:
        return {
            "operation_id": operation_id,
            "event": event,
            "run_id": run["run_id"],
            "attempt_id": attempt_id,
            "payload": payload,
        }

    def test_frozen_manifest_is_valid_and_status_is_retired(self):
        self.assertEqual(mod.validate_manifest(self.manifest), [])
        self.assertEqual(mod.validate_status(self.status, self.manifest), [])
        receipt = mod.readiness(self.manifest, self.status)
        self.assertFalse(receipt["preflight_ready"])
        self.assertFalse(receipt["ready_for_provider_spend"])
        self.assertEqual(receipt["gates"], [mod.NON_RUNNABLE_GATE])

    def test_frozen_protocol_forbids_post_release_exclusions(self):
        self.assertEqual(
            self.manifest["exclusion_policy"]["post_release_run_or_block_exclusion"],
            "forbidden",
        )
        tampered = copy.deepcopy(self.manifest)
        tampered["exclusion_policy"]["evaluator_defect"] = "exclude_block"
        errors = mod.validate_manifest(tampered)
        self.assertIn("exclusion_policy must forbid all post-release exclusions", errors)

        path = self.initialize_journal()
        run = self.run_for()
        with self.assertRaisesRegex(mod.ValidationError, "journal request event is invalid"):
            mod.record_journal_event(
                path,
                self.schedule,
                self.request(
                    "exclude-after-release",
                    "block_excluded",
                    run,
                    mod.attempt_id_for(run["run_id"], 1),
                    {},
                ),
            )

    def test_synthetic_shape_complete_release_cannot_restore_runnable_state(self):
        receipt = mod.readiness(
            self.manifest,
            self.status,
            release=self.release,
            fixture_root=self.fixture_root,
            schedule=self.schedule,
        )
        self.assertFalse(receipt["preflight_ready"])
        self.assertFalse(receipt["ready_for_provider_spend"])
        self.assertEqual(receipt["gates"], [mod.NON_RUNNABLE_GATE])

    def test_release_freezes_disjoint_pilot_and_full_fixture_sets(self):
        self.assertEqual(mod.validate_release(self.release, self.manifest), [])
        pilot = {row["fixture_id"] for row in self.release["fixtures"] if row["stage"] == "pilot"}
        full = {row["fixture_id"] for row in self.release["fixtures"] if row["stage"] == "full"}
        self.assertEqual(len(pilot), 4)
        self.assertEqual(len(full), 48)
        self.assertFalse(pilot & full)

        tampered = copy.deepcopy(self.release)
        tampered["fixtures"][-1]["fixture_sha256"] = tampered["fixtures"][0][
            "fixture_sha256"
        ]
        errors = mod.validate_release(tampered, self.manifest)
        self.assertTrue(any("bytes must be disjoint" in error for error in errors))

    def test_release_requires_exact_fixture_counts_and_provider_profiles(self):
        tampered = copy.deepcopy(self.release)
        tampered["fixtures"].pop()
        tampered["provider_profiles"][0]["resolved_model_id"] = ""
        errors = mod.validate_release(tampered, self.manifest)
        self.assertTrue(any("exactly 12 full proof_inspection" in error for error in errors))
        self.assertTrue(any("resolved_model_id must be a non-empty string" in error for error in errors))

    def test_release_rejects_private_evaluator_fields_and_unknown_fields(self):
        tampered = copy.deepcopy(self.release)
        tampered["oracle_commitment_sha256"] = sha("oracle")
        errors = mod.validate_release(tampered, self.manifest)
        self.assertIn("release must contain exactly the public release fields", errors)
        self.assertIn(
            "public release must not contain hidden evaluator or adjudication fields",
            errors,
        )

    def test_schedule_is_deterministic_complete_and_input_order_independent(self):
        reversed_release = copy.deepcopy(self.release)
        reversed_release["fixtures"].reverse()
        reversed_release["provider_profiles"].reverse()
        rebuilt = mod.build_schedule(
            self.manifest,
            reversed_release,
            fixture_root=self.fixture_root,
        )
        self.assertEqual(self.schedule, rebuilt)
        self.assertEqual(len(self.schedule["runs"]), 208)
        self.assertEqual(
            sum(run["stage"] == "pilot" for run in self.schedule["runs"]),
            16,
        )
        self.assertEqual(
            sum(run["stage"] == "full" for run in self.schedule["runs"]),
            192,
        )
        self.assertEqual(
            [run["sequence"] for run in self.schedule["runs"]],
            list(range(208)),
        )

    def test_new_seed_changes_order_without_changing_run_membership(self):
        changed_release = copy.deepcopy(self.release)
        changed_release["randomization_seed"] = sha("new-seed")
        changed = mod.build_schedule(
            self.manifest,
            changed_release,
            fixture_root=self.fixture_root,
        )
        key = lambda run: (run["stage"], run["scenario_class"], run["fixture_id"], run["arm"])
        self.assertEqual({key(run) for run in self.schedule["runs"]}, {key(run) for run in changed["runs"]})
        self.assertNotEqual([key(run) for run in self.schedule["runs"]], [key(run) for run in changed["runs"]])

    def test_every_provider_block_contains_exact_native_and_vidux_arms(self):
        blocks: dict[tuple[str, str, str, str], set[str]] = {}
        for run in self.schedule["runs"]:
            key = (run["stage"], run["scenario_class"], run["fixture_id"], run["pair_id"])
            blocks.setdefault(key, set()).add(run["arm"])
        self.assertEqual(len(blocks), 104)
        for key, arms in blocks.items():
            expected = (
                {"claude_native", "claude_vidux"}
                if key[-1] == "anthropic_claude"
                else {"codex_native", "codex_vidux"}
            )
            self.assertEqual(arms, expected)

    def test_schedule_validation_rejects_omission_duplicate_or_reassignment(self):
        for mutate in ("omit", "duplicate", "reassign"):
            with self.subTest(mutate=mutate):
                tampered = copy.deepcopy(self.schedule)
                if mutate == "omit":
                    tampered["runs"].pop()
                elif mutate == "duplicate":
                    tampered["runs"][-1] = copy.deepcopy(tampered["runs"][0])
                else:
                    tampered["runs"][0]["arm"] = "codex_native"
                errors = mod.validate_schedule(
                    tampered,
                    self.manifest,
                    self.release,
                    fixture_root=self.fixture_root,
                )
                self.assertIn(
                    "schedule must exactly match deterministic complete regeneration",
                    errors,
                )

    def test_packet_is_scheduled_provider_matched_and_evaluator_independent(self):
        native_run = self.run_for(arm="claude_native")
        vidux_run = self.run_for(arm="claude_vidux")
        native = mod.build_run_packet(
            self.manifest,
            self.release,
            self.schedule,
            fixture_root=self.fixture_root,
            run_id=native_run["run_id"],
        )
        vidux = mod.build_run_packet(
            self.manifest,
            self.release,
            self.schedule,
            fixture_root=self.fixture_root,
            run_id=vidux_run["run_id"],
        )
        serialized = json.dumps(vidux, sort_keys=True).lower()
        for forbidden in ("oracle", "hidden", "adjudicat", "evaluator"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(native["provider_profile"], vidux["provider_profile"])
        self.assertEqual(native["fixture"], vidux["fixture"])
        self.assertEqual(native["budget"], vidux["budget"])
        for packet in (native, vidux):
            for field in ("run_id", "sequence", "arm", "mode", "intervention"):
                packet.pop(field)
        self.assertEqual(native, vidux)

    def test_packet_rejects_unknown_or_unscheduled_run(self):
        with self.assertRaisesRegex(mod.ValidationError, "unknown run_id"):
            mod.build_run_packet(
                self.manifest,
                self.release,
                self.schedule,
                fixture_root=self.fixture_root,
                run_id="run-00000000000000000000",
            )

    def test_fixture_reads_reject_symlink_and_hard_link_aliases(self):
        fixture = self.release["fixtures"][0]
        path = self.fixture_root / fixture["fixture_path"]
        external = self.root / "external-secret.json"
        external.write_text("secret", encoding="utf-8")
        original = path.read_bytes()

        path.unlink()
        path.symlink_to(external)
        errors = mod.validate_release_files(self.release, self.fixture_root)
        self.assertTrue(any("cannot be opened safely" in error for error in errors))

        path.unlink()
        external.write_bytes(original)
        fixture["fixture_sha256"] = hashlib.sha256(original).hexdigest()
        os.link(external, path)
        errors = mod.validate_release_files(self.release, self.fixture_root)
        self.assertTrue(any("single-link regular file" in error for error in errors))

    def test_strict_json_rejects_duplicate_keys_nonfinite_numbers_and_deep_values(self):
        with self.assertRaisesRegex(mod.ValidationError, "duplicate JSON key"):
            mod.strict_json_loads('{"protocol_id":"a","protocol_id":"b"}')
        with self.assertRaisesRegex(mod.ValidationError, "non-finite"):
            mod.strict_json_loads('{"value": NaN}')
        deep = "[" * 66 + "0" + "]" * 66
        with self.assertRaisesRegex(mod.ValidationError, "nesting depth"):
            mod.strict_json_loads(deep)

    def test_result_schema_rejects_self_reported_outcomes_receipt_drift_and_budget_overrun(self):
        result = self.result()
        result["success"] = 1
        errors = mod.validate_result(result, self.schedule)
        self.assertTrue(any("exactly" in error for error in errors))

        result.pop("success")
        result["provider_receipt_sha256"] = "receipt-id"
        result["metrics"]["tokens"] = 60001
        errors = mod.validate_result(result, self.schedule)
        self.assertTrue(any("provider_receipt_sha256" in error for error in errors))
        self.assertTrue(any("tokens exceeds" in error for error in errors))

        result = self.result()
        result["attempt_id"] = "attempt-invented"
        errors = mod.validate_result(result, self.schedule)
        self.assertIn("runner result attempt_id must be schedule-derived", errors)

    def test_adjudication_is_deterministic_and_derived_only_from_bound_inputs(self):
        result = self.result()
        evaluator = self.evaluator_result(result=result)
        path = self.initialize_journal()
        self.journal_result(path, self.run_for(), result, prefix="deterministic")
        rows = mod.load_journal(path, self.schedule)
        first = mod.adjudicate(self.schedule, result, evaluator, rows)
        second = mod.adjudicate(
            self.schedule,
            copy.deepcopy(result),
            copy.deepcopy(evaluator),
            rows,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["success"], 1)
        self.assertEqual(first["resume_loss"], 6)
        self.assertEqual(first["terminal_outcome"], "pass")

        evaluator["forbidden_action"] = True
        blocked = mod.adjudicate(self.schedule, result, evaluator, rows)
        self.assertEqual(blocked["success"], 0)
        self.assertEqual(blocked["terminal_outcome"], "disqualified_for_forbidden_action")

    def test_adjudication_rejects_unknown_checks_and_cross_run_results(self):
        result = self.result()
        evaluator = self.evaluator_result()
        evaluator["checks"][0]["weight"] = 1
        errors = mod.validate_evaluator_result(evaluator, self.schedule, result)
        self.assertTrue(any("exactly the check fields" in error for error in errors))

        evaluator = self.evaluator_result()
        evaluator["run_id"] = self.run_for(arm="codex_native")["run_id"]
        errors = mod.validate_evaluator_result(evaluator, self.schedule, result)
        self.assertIn("evaluator result run_id must match the runner result", errors)

        evaluator = self.evaluator_result()
        evaluator["runner_result_sha256"] = sha("different-runner-result")
        errors = mod.validate_evaluator_result(evaluator, self.schedule, result)
        self.assertIn("evaluator result must bind the exact runner result", errors)

    def test_journal_initialization_is_idempotent_and_hash_chained(self):
        path = self.journal_path()
        first, appended = mod.initialize_journal(
            path,
            self.schedule,
            operation_id="initialize-journal",
        )
        replay, replay_appended = mod.initialize_journal(
            path,
            self.schedule,
            operation_id="initialize-journal",
        )
        self.assertTrue(appended)
        self.assertFalse(replay_appended)
        self.assertEqual(first, replay)
        summary = mod.journal_summary(path, self.schedule)
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["run_states"], {"pending": 208})

    def test_journal_claim_is_schedule_derived_and_operation_replay_is_exact(self):
        path = self.initialize_journal()
        run = self.run_for()
        attempt = mod.attempt_id_for(run["run_id"], 1)
        request = self.request(
            "claim-first-attempt",
            "attempt_claimed",
            run,
            attempt,
            {"worker_id": "worker-one"},
        )
        first, appended = mod.record_journal_event(path, self.schedule, request)
        replay, replay_appended = mod.record_journal_event(path, self.schedule, request)
        self.assertTrue(appended)
        self.assertFalse(replay_appended)
        self.assertEqual(first, replay)
        self.assertEqual(first["payload"]["attempt_number"], 1)

        changed = copy.deepcopy(request)
        changed["payload"]["worker_id"] = "worker-two"
        with self.assertRaisesRegex(mod.ValidationError, "changed the original event intent"):
            mod.record_journal_event(path, self.schedule, changed)

    def test_journal_rejects_invented_attempt_id_and_injected_identifier(self):
        path = self.initialize_journal()
        run = self.run_for()
        request = self.request(
            "claim-first-attempt",
            "attempt_claimed",
            run,
            "attempt-invented",
            {"worker_id": "worker-one"},
        )
        with self.assertRaisesRegex(mod.ValidationError, "schedule-derived attempt_id"):
            mod.record_journal_event(path, self.schedule, request)

        request["attempt_id"] = mod.attempt_id_for(run["run_id"], 1)
        request["payload"]["worker_id"] = 'worker"}\n{"forged":"event'
        with self.assertRaisesRegex(mod.ValidationError, "worker_id is invalid"):
            mod.record_journal_event(path, self.schedule, request)

    def test_journal_complete_adjudicate_flow_and_terminal_fencing(self):
        path = self.initialize_journal()
        run = self.run_for()
        result = self.result(run)
        self.journal_result(path, run, result, prefix="complete-first-attempt")
        receipt, _event, appended = mod.record_adjudication(
            path,
            self.schedule,
            result,
            self.evaluator_result(run, result),
            operation_id="adjudicate-first-attempt",
        )
        self.assertTrue(appended)
        self.assertEqual(receipt["success"], 1)
        summary = mod.journal_summary(path, self.schedule)
        self.assertEqual(summary["run_states"]["adjudicated"], 1)
        self.assertEqual(summary["spent"], self.metrics())

        with self.assertRaisesRegex(mod.ValidationError, "cannot be claimed from adjudicated"):
            mod.record_journal_event(
                path,
                self.schedule,
                self.request(
                    "claim-after-terminal",
                    "attempt_claimed",
                    run,
                    mod.attempt_id_for(run["run_id"], 2),
                    {"worker_id": "worker-two"},
                ),
            )

    def test_adjudication_rejects_result_drift_from_journal_and_direct_event(self):
        path = self.initialize_journal()
        run = self.run_for()
        result = self.result(run)
        self.journal_result(path, run, result, prefix="journal-bound")
        tampered = copy.deepcopy(result)
        tampered["provider_receipt_sha256"] = sha("tampered-provider-receipt")
        evaluator = self.evaluator_result(run, tampered)
        with self.assertRaisesRegex(mod.ValidationError, "provider_receipt_sha256"):
            mod.adjudicate(
                self.schedule,
                tampered,
                evaluator,
                mod.load_journal(path, self.schedule),
            )

        with self.assertRaisesRegex(mod.ValidationError, "emitted by the adjudicator"):
            mod.record_journal_event(
                path,
                self.schedule,
                self.request(
                    "forge-adjudication",
                    "adjudicated",
                    run,
                    result["attempt_id"],
                    {"adjudication_receipt_sha256": sha("forged")},
                ),
            )

    def test_journal_allows_one_documented_retry_and_fences_stale_attempt(self):
        path = self.initialize_journal()
        run = self.run_for()
        first = mod.attempt_id_for(run["run_id"], 1)
        second = mod.attempt_id_for(run["run_id"], 2)
        for request in (
            self.request(
                "claim-first-attempt",
                "attempt_claimed",
                run,
                first,
                {"worker_id": "worker-one"},
            ),
            self.request("start-first-attempt", "attempt_started", run, first, {}),
            self.request(
                "retry-first-attempt",
                "infra_retryable",
                run,
                first,
                self.usage_payload(reason_receipt_sha256=sha("infra-reason")),
            ),
            self.request(
                "claim-second-attempt",
                "attempt_claimed",
                run,
                second,
                {"worker_id": "worker-two"},
            ),
        ):
            mod.record_journal_event(path, self.schedule, request)

        with self.assertRaisesRegex(mod.ValidationError, "attempt_id does not match"):
            mod.record_journal_event(
                path,
                self.schedule,
                self.request("stale-start", "attempt_started", run, first, {}),
            )

    def test_journal_retry_usage_cannot_exceed_the_logical_run_budget(self):
        path = self.initialize_journal()
        run = self.run_for()
        first = mod.attempt_id_for(run["run_id"], 1)
        second = mod.attempt_id_for(run["run_id"], 2)
        first_metrics = self.metrics(tokens=run["budget"]["tokens"] - 1)
        retry_payload = self.usage_payload(reason_receipt_sha256=sha("infra-reason"))
        retry_payload["metrics"] = first_metrics
        for request in (
            self.request("claim-first", "attempt_claimed", run, first, {"worker_id": "worker-one"}),
            self.request("start-first", "attempt_started", run, first, {}),
            self.request("retry-first", "infra_retryable", run, first, retry_payload),
            self.request("claim-second", "attempt_claimed", run, second, {"worker_id": "worker-two"}),
            self.request("start-second", "attempt_started", run, second, {}),
        ):
            mod.record_journal_event(path, self.schedule, request)

        with self.assertRaisesRegex(mod.ValidationError, "cumulative tokens budget"):
            mod.record_journal_event(
                path,
                self.schedule,
                self.request(
                    "complete-second",
                    "runner_completed",
                    run,
                    second,
                    self.usage_payload(),
                ),
            )

    def test_decision_receipt_is_deterministic_complete_and_never_claims_from_pilot(self):
        failed_run = next(
            run
            for run in self.schedule["runs"]
            if run["stage"] == "pilot" and run["arm"] == "claude_native"
        )
        path, bundle = self.pilot_bundle(
            budget_exhausted_run_id=failed_run["run_id"]
        )
        rows = mod.load_journal(path, self.schedule)
        first = mod.decide(
            self.manifest,
            self.release,
            self.schedule,
            fixture_root=self.fixture_root,
            journal_rows=rows,
            bundle=bundle,
        )
        reversed_bundle = copy.deepcopy(bundle)
        reversed_bundle["adjudications"].reverse()
        second = mod.decide(
            self.manifest,
            self.release,
            self.schedule,
            fixture_root=self.fixture_root,
            journal_rows=rows,
            bundle=reversed_bundle,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["run_count"], 16)
        self.assertFalse(first["claim_eligible"])
        self.assertEqual(first["verified_net_win_classes"], 0)
        self.assertEqual(first["verdict"], "pilot_directional")

    def test_zero_resolved_ratio_is_a_non_win_instead_of_an_exception(self):
        pairs = [
            {
                "native": {
                    "success": 0,
                    "metrics": self.metrics(),
                    "resume_loss": 0,
                },
                "vidux": {
                    "success": 1,
                    "metrics": self.metrics(),
                    "resume_loss": 0,
                },
            }
            for _ in range(12)
        ]
        comparison = mod._comparison(
            pairs,
            schedule=self.schedule,
            stage="full",
            pair_id="anthropic_claude",
            scenario_id="durable_state",
            rules=self.manifest["decision_rules"],
        )
        self.assertEqual(comparison["status"], "no_win")
        self.assertFalse(
            comparison["metrics"]["tokens_per_resolved_ratio_basis_points"][
                "defined"
            ]
        )

    def test_historical_library_synthetic_full_decision_proves_retirement_need(self):
        path = self.initialize_journal()
        adjudications: list[dict] = []
        native_counts: dict[tuple[str, str], int] = {}
        full_runs = [run for run in self.schedule["runs"] if run["stage"] == "full"]
        for index, run in enumerate(full_runs):
            result = self.result(run)
            prefix = f"full-{index:03d}"
            self.journal_result(path, run, result, prefix=prefix)
            evaluator = self.evaluator_result(run, result)
            if run["mode"] == "native":
                key = (run["pair_id"], run["scenario_class"])
                native_counts[key] = native_counts.get(key, 0) + 1
                evaluator["checks"][0]["passed"] = native_counts[key] <= 7
            receipt, _event, _appended = mod.record_adjudication(
                path,
                self.schedule,
                result,
                evaluator,
                operation_id=f"{prefix}-adjudicate",
            )
            adjudications.append(receipt)
        bundle = {
            "schema_version": 1,
            "schedule_digest": mod.digest_json(self.schedule, "schedule"),
            "stage": "full",
            "adjudications": adjudications,
        }
        decision = mod.decide(
            self.manifest,
            self.release,
            self.schedule,
            fixture_root=self.fixture_root,
            journal_rows=mod.load_journal(path, self.schedule),
            bundle=bundle,
        )
        self.assertTrue(decision["claim_eligible"])
        self.assertEqual(decision["run_count"], 192)
        self.assertEqual(decision["verified_net_win_classes"], 4)
        self.assertEqual(decision["verdict"], "verified_net_win")

    def test_journal_reserves_stage_and_protocol_budgets_before_claim(self):
        schedule = copy.deepcopy(self.schedule)
        run = next(run for run in schedule["runs"] if run["stage"] == "pilot")
        schedule["stage_budgets"]["pilot"]["tokens"] = run["budget"]["tokens"] - 1
        path = self.root / "budget-journal.jsonl"
        mod.initialize_journal(path, schedule, operation_id="initialize-budget-journal")
        with self.assertRaisesRegex(mod.ValidationError, "pilot tokens budget would be exceeded"):
            mod.record_journal_event(
                path,
                schedule,
                self.request(
                    "claim-over-budget",
                    "attempt_claimed",
                    run,
                    mod.attempt_id_for(run["run_id"], 1),
                    {"worker_id": "worker-one"},
                ),
            )

    def test_journal_rejects_hash_tamper_blank_tail_symlink_and_hardlink(self):
        path = self.initialize_journal()
        original = path.read_text(encoding="utf-8")
        row = json.loads(original)
        row["payload"]["run_count"] = 1
        path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(mod.ValidationError, "event hash is invalid"):
            mod.load_journal(path, self.schedule)

        path.write_text(original + "\n", encoding="utf-8")
        with self.assertRaisesRegex(mod.ValidationError, "is blank"):
            mod.load_journal(path, self.schedule)

        path.write_text(original.rstrip("\n"), encoding="utf-8")
        with self.assertRaisesRegex(mod.ValidationError, "unterminated tail"):
            mod.load_journal(path, self.schedule)

        path.unlink()
        external = self.root / "external-journal"
        external.write_text(original, encoding="utf-8")
        path.symlink_to(external)
        with self.assertRaises(mod.ValidationError):
            mod.load_journal(path, self.schedule)

        path.unlink()
        os.link(external, path)
        with self.assertRaisesRegex(mod.ValidationError, "single-link regular file"):
            mod.load_journal(path, self.schedule)

    def test_concurrent_duplicate_claim_has_one_append_and_one_sequence(self):
        path = self.initialize_journal()
        run = self.run_for()
        request = self.request(
            "concurrent-claim",
            "attempt_claimed",
            run,
            mod.attempt_id_for(run["run_id"], 1),
            {"worker_id": "worker-one"},
        )
        context = multiprocessing.get_context("fork")
        queue = context.Queue()
        processes = [
            context.Process(
                target=record_historical_journal_event,
                args=(path, self.schedule, request, queue),
            )
            for _ in range(8)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=20)
        receipts = [queue.get(timeout=2) for _ in processes]
        self.assertTrue(all(receipt["ok"] for receipt in receipts), receipts)
        self.assertTrue(all(process.exitcode == 0 for process in processes), receipts)
        self.assertEqual(sum(receipt["appended"] for receipt in receipts), 1)
        rows = mod.load_journal(path, self.schedule)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["sequence"], 1)

    def test_cli_validate_and_readiness_are_fail_closed(self):
        valid = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertFalse(json.loads(valid.stdout)["runnable"])

        not_ready = subprocess.run(
            [sys.executable, str(SCRIPT), "readiness"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(not_ready.returncode, 2, not_ready.stderr)
        receipt = json.loads(not_ready.stdout)
        self.assertFalse(receipt["ready_for_provider_spend"])
        self.assertEqual(receipt["gates"], [mod.NON_RUNNABLE_GATE])

    def test_every_operational_cli_command_refuses_before_loading_artifacts(self):
        missing = str(self.root / "does-not-exist.json")
        commands = [
            ["schedule", "--release", missing, "--fixture-root", missing],
            [
                "packet", "--release", missing, "--fixture-root", missing,
                "--schedule", missing, "--run-id", "run-00000000000000000000",
            ],
            ["journal-init", "--schedule", missing, "--journal", missing, "--operation-id", "op"],
            ["journal-event", "--schedule", missing, "--journal", missing, "--request", missing],
            ["journal-verify", "--schedule", missing, "--journal", missing],
            [
                "adjudicate", "--schedule", missing, "--journal", missing,
                "--result", missing, "--evaluator-result", missing, "--operation-id", "op",
            ],
            [
                "decide", "--release", missing, "--fixture-root", missing,
                "--schedule", missing, "--journal", missing, "--adjudications", missing,
            ],
        ]
        for command in commands:
            with self.subTest(command=command[0]):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *command],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(mod.NON_RUNNABLE_GATE, result.stderr)
                self.assertNotIn("does-not-exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
