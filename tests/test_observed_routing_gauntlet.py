"""Mutation controls for the real four-harness observed-routing gauntlet."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

GAUNTLET_PATH = SCRIPTS / "dev" / "shadow-routing-gauntlet.py"
SPEC = importlib.util.spec_from_file_location("shadow_routing_gauntlet", GAUNTLET_PATH)
assert SPEC and SPEC.loader
gauntlet = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gauntlet
SPEC.loader.exec_module(gauntlet)

from shadow_execution_policy import (
    DELEGATION_MODES,
    ExecutionPolicyError,
    HOSTS,
    POLICY_VERSION,
    WORK_CLASSES,
    delegation_capability,
    resolve_route,
)


class ExecutionPolicyTests(unittest.TestCase):
    def test_policy_is_small_complete_and_native(self) -> None:
        self.assertEqual(POLICY_VERSION, "shadow.execution-policy.v2")
        self.assertEqual(WORK_CLASSES, ("planning", "coding", "review", "lightweight"))
        self.assertEqual(DELEGATION_MODES, ("direct", "required"))
        self.assertEqual(HOSTS, ("claude-code", "codex", "cursor", "grok"))
        for host in HOSTS:
            for work_class in WORK_CLASSES:
                route = resolve_route(host, work_class)
                self.assertEqual(route.host, host)
                self.assertEqual(route.work_class, work_class)
                self.assertTrue(route.model)
                self.assertTrue(route.observed_model_pattern)

        self.assertEqual(resolve_route("claude-code", "planning").model, "fable")
        self.assertEqual(resolve_route("claude-code", "coding").model, "opus")
        self.assertEqual(resolve_route("codex", "planning").model, "gpt-5.6-sol")
        self.assertEqual(resolve_route("codex", "lightweight").model, "gpt-5.6-luna")
        self.assertEqual(
            resolve_route("cursor", "planning").model,
            "claude-fable-5-thinking-high",
        )
        self.assertEqual(
            resolve_route("cursor", "coding").model,
            "claude-opus-5-thinking-high",
        )
        self.assertEqual(resolve_route("cursor", "review").model, "cursor-grok-4.6-high")
        self.assertEqual(resolve_route("cursor", "lightweight").model, "Auto")
        self.assertEqual(resolve_route("grok", "coding").model, "grok-4.6")
        self.assertEqual(resolve_route("grok", "lightweight").model, "grok-4.5")
        self.assertEqual(delegation_capability("claude-code", "required"), "Agent")
        self.assertEqual(delegation_capability("codex", "required"), "multi_agent")
        self.assertEqual(delegation_capability("grok", "required"), "spawn_subagent")
        self.assertIsNone(delegation_capability("cursor", "direct"))
        with self.assertRaises(ExecutionPolicyError):
            delegation_capability("cursor", "required")


class ScenarioContractTests(unittest.TestCase):
    def test_twelve_scenarios_expand_to_exactly_forty_eight_real_jobs(self) -> None:
        self.assertEqual(len(gauntlet.SCENARIOS), 12)
        matrix = gauntlet.matrix_jobs()
        self.assertEqual(len(matrix), 48)
        self.assertEqual(
            {(job.host, job.scenario.scenario_id) for job in matrix},
            {(host, scenario.scenario_id) for host in HOSTS for scenario in gauntlet.SCENARIOS},
        )
        for scenario in gauntlet.SCENARIOS:
            self.assertIn("Goal:", scenario.prompt)
            self.assertIn("Long job:", scenario.prompt)
            self.assertGreaterEqual(len(scenario.steps), 3)
            self.assertTrue(scenario.completion_sentinel.startswith("SHADOW_EVAL_"))

    def test_verifier_does_not_create_out_of_scope_bytecode(self) -> None:
        scenario = next(item for item in gauntlet.SCENARIOS if item.scenario_id == "exact-code")
        with tempfile.TemporaryDirectory() as temp:
            repo = gauntlet.prepare_fixture(Path(temp), scenario)
            (repo / "candidate.py").write_text(
                "def normalize(value: str) -> str:\n"
                "    return '-'.join(value.strip().lower().split())\n",
                encoding="utf-8",
            )
            (repo / "result.txt").write_text("PASS\n", encoding="utf-8")
            verified = subprocess.run(
                [sys.executable, "verify.py"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertFalse((repo / "__pycache__").exists())


class FalseGreenMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.good = gauntlet.RunObservation(
            run_id="0123456789abcdef",
            host="codex",
            scenario_id="exact-code",
            work_class="coding",
            requested_model="gpt-5.6-sol",
            observed_model="gpt-5.6-sol",
            exit_code=0,
            timed_out=False,
            completion_sentinel="SHADOW_EVAL_EXACT_CODE_OK",
            completion_observed=True,
            expected_paths=("result.txt",),
            changed_paths=("result.txt",),
            deterministic_checks=("fixture-check",),
            deterministic_checks_passed=True,
            delegation_required=False,
            child_spans=0,
            langfuse_trace_id="a" * 32,
            langfuse_write_verified=True,
            langfuse_readback_verified=True,
            input_tokens=100,
            output_tokens=10,
            cost_usd=0.01,
            error=None,
        )

    def assert_red(self, **changes: object) -> None:
        grade = gauntlet.grade_observation(replace(self.good, **changes))
        self.assertFalse(grade.passed, grade.checks)

    def test_wrong_model_is_red(self) -> None:
        self.assert_red(observed_model="gpt-5.6-luna")

    def test_selector_without_observation_is_red(self) -> None:
        self.assert_red(observed_model=None)

    def test_agent_prose_without_child_lineage_is_red(self) -> None:
        self.assert_red(delegation_required=True, child_spans=0)

    def test_prompt_echo_without_terminal_completion_is_red(self) -> None:
        self.assert_red(completion_observed=False)

    def test_missing_langfuse_delivery_or_readback_is_red(self) -> None:
        self.assert_red(langfuse_write_verified=False)
        self.assert_red(langfuse_readback_verified=False)

    def test_out_of_scope_edit_is_red(self) -> None:
        self.assert_red(changed_paths=("result.txt", "outside.txt"))

    def test_timeout_nonzero_or_failed_fixture_is_red(self) -> None:
        self.assert_red(timed_out=True)
        self.assert_red(exit_code=1)
        self.assert_red(deterministic_checks_passed=False)

    def test_unavailable_capability_is_error_not_pass(self) -> None:
        self.assert_red(error="native delegation unavailable")


class LocalSinkBoundaryTests(unittest.TestCase):
    @staticmethod
    def _passing_native_observation() -> object:
        return gauntlet.RunObservation(
            run_id="0123456789abcdef",
            host="codex",
            scenario_id="exact-code",
            work_class="coding",
            requested_model="gpt-5.6-sol",
            observed_model="gpt-5.6-sol",
            exit_code=0,
            timed_out=False,
            completion_sentinel="SHADOW_EVAL_EXACT_CODE_OK",
            completion_observed=True,
            expected_paths=("result.txt",),
            changed_paths=("result.txt",),
            deterministic_checks=("fixture-check",),
            deterministic_checks_passed=True,
            delegation_required=False,
            child_spans=0,
            langfuse_trace_id=None,
            langfuse_write_verified=False,
            langfuse_readback_verified=False,
            input_tokens=100,
            output_tokens=10,
            cost_usd=0.01,
            error=None,
        )

    @staticmethod
    def _span_facts(span: dict[str, object]) -> tuple[bool | None, bool | None, bool | None, int]:
        facts: dict[str, object] = {}
        for attribute in span["attributes"]:  # type: ignore[index]
            value = attribute["value"]  # type: ignore[index]
            facts[attribute["key"]] = next(iter(value.values()))  # type: ignore[index]
        return (
            facts.get("shadow.final"),
            facts.get("shadow.passed"),
            facts.get("shadow.langfuse_readback_verified"),
            span["status"]["code"],  # type: ignore[index]
        )

    def test_failed_readback_leaves_only_a_red_provisional_span(self) -> None:
        sink = object.__new__(gauntlet.LangfuseSink)
        events: list[tuple[object, ...]] = []

        def send(spans: list[dict[str, object]]) -> None:
            events.append(("send", *self._span_facts(spans[0])))

        def reject_readback(_trace_id: str) -> bool:
            events.append(("readback",))
            return False

        sink.send_spans = send
        sink.verify_trace = reject_readback
        try:
            with self.assertRaises(gauntlet.GauntletError):
                sink.emit_observation(self._passing_native_observation())
        except TypeError as exc:
            self.fail(f"emit_observation still requires pre-readback final state: {exc}")

        self.assertEqual(
            events,
            [("send", False, False, False, 2), ("readback",)],
        )

    def test_green_adjudication_is_emitted_only_after_exact_readback(self) -> None:
        sink = object.__new__(gauntlet.LangfuseSink)
        events: list[tuple[object, ...]] = []

        def send(spans: list[dict[str, object]]) -> None:
            events.append(("send", *self._span_facts(spans[0])))

        def accept_readback(_trace_id: str) -> bool:
            events.append(("readback",))
            return True

        sink.send_spans = send
        sink.verify_trace = accept_readback
        try:
            trace_id = sink.emit_observation(self._passing_native_observation())
        except TypeError as exc:
            self.fail(f"emit_observation still requires pre-readback final state: {exc}")

        self.assertRegex(trace_id, r"^[0-9a-f]{32}$")
        self.assertEqual(
            events,
            [
                ("send", False, False, False, 2),
                ("readback",),
                ("send", True, True, True, 1),
            ],
        )

    def test_langfuse_sink_accepts_only_explicit_loopback_endpoints(self) -> None:
        common = {
            "SHADOW_LANGFUSE_PUBLIC_KEY": "public-test",
            "SHADOW_LANGFUSE_SECRET_KEY": "secret-test",
            "SHADOW_LANGFUSE_PROJECT_ID": "project_test",
            "SHADOW_LANGFUSE_READBACK_URL": "http://127.0.0.1:18123",
        }
        with mock.patch.dict(
            os.environ,
            {**common, "SHADOW_LANGFUSE_HOST": "http://localhost:13000"},
            clear=False,
        ):
            sink = gauntlet.LangfuseSink()
            self.assertEqual(
                sink.endpoint,
                "http://localhost:13000/api/public/otel/v1/traces",
            )

        for remote in ("https://langfuse.example.com", "http://10.0.0.8:3000"):
            with self.subTest(remote=remote), mock.patch.dict(
                os.environ,
                {**common, "SHADOW_LANGFUSE_HOST": remote},
                clear=False,
            ):
                with self.assertRaises(gauntlet.GauntletError):
                    gauntlet.LangfuseSink()


class NativeStreamParserTests(unittest.TestCase):
    def test_claude_parent_model_is_not_replaced_by_helper_usage(self) -> None:
        raw = "\n".join((
            '{"type":"system","subtype":"init","model":"claude-sonnet-5"}',
            '{"type":"assistant","message":{"content":[{"type":"text","text":"DONE"}]}}',
            '{"type":"result","result":"DONE","usage":{"input_tokens":2,"output_tokens":3},"modelUsage":{"claude-haiku-4-5-20251001":{},"claude-sonnet-5":{}}}',
        ))
        observed, final, inputs, outputs, _, _ = gauntlet.parse_native_output("claude-code", raw)
        self.assertEqual(observed, "claude-sonnet-5")
        self.assertEqual(final, "DONE")
        self.assertEqual((inputs, outputs), (2, 3))

    def test_cursor_camel_case_usage_and_codex_item_are_observed(self) -> None:
        cursor = "\n".join((
            '{"type":"system","subtype":"init","model":"Auto"}',
            '{"type":"result","result":"CURSOR_DONE","usage":{"inputTokens":11,"outputTokens":7}}',
        ))
        observed, final, inputs, outputs, _, _ = gauntlet.parse_native_output("cursor", cursor)
        self.assertEqual((observed, final, inputs, outputs), ("Auto", "CURSOR_DONE", 11, 7))
        codex = '{"type":"item.completed","item":{"type":"agent_message","text":"CODEX_DONE"}}'
        self.assertEqual(gauntlet.parse_native_output("codex", codex)[1], "CODEX_DONE")

    def test_grok_text_deltas_model_and_usage_are_observed(self) -> None:
        raw = "\n".join((
            '{"type":"text","data":"GROK_"}',
            '{"type":"text","data":"DONE"}',
            '{"type":"end","usage":{"input_tokens":9,"output_tokens":4},"total_cost_usd":0.01,"modelUsage":{"grok-4.5-build":{}}}',
        ))
        observed, final, inputs, outputs, cost, _ = gauntlet.parse_native_output("grok", raw)
        self.assertEqual((observed, final, inputs, outputs, cost), ("grok-4.5-build", "GROK_DONE", 9, 4, 0.01))

    def test_nonzero_provider_limit_has_stable_wake_code(self) -> None:
        self.assertEqual(gauntlet._native_error(1, "You've hit your usage limit"), "provider_usage_limit")

    def test_native_child_tools_leave_lineage(self) -> None:
        for host, tool in (
            ("claude-code", "Agent"),
            ("codex", "spawn_agent"),
            ("grok", "spawn_subagent"),
        ):
            with self.subTest(host=host):
                raw = '{"type":"tool","name":"' + tool + '"}'
                self.assertGreater(gauntlet.parse_native_output(host, raw)[5], 0)

    def test_delegation_prompts_name_the_native_capability(self) -> None:
        scenario = next(
            item for item in gauntlet.SCENARIOS if item.scenario_id == "delegation-lineage"
        )
        self.assertIn("spawn_agent", gauntlet.prompt_for_host("codex", scenario))
        self.assertIn("shadow-evidence", gauntlet.prompt_for_host("claude-code", scenario))
        self.assertIn("spawn_subagent", gauntlet.prompt_for_host("grok", scenario))

        class Sink:
            @staticmethod
            def codex_config(_run_tag: str) -> tuple[list[str], dict[str, str]]:
                return [], {}

        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            for host, required in (
                ("claude-code", "--agents"),
                ("codex", "multi_agent"),
                ("grok", "20"),
            ):
                prompt = gauntlet.prompt_for_host(host, scenario)
                command, _, _ = gauntlet._command(
                    host, scenario, repo, Sink(), "eval-0123456789abcdef", prompt
                )
                self.assertIn(required, command)


if __name__ == "__main__":
    unittest.main()
