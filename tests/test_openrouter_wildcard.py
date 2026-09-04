"""Closed-contract tests for the intentionally inactive OpenRouter wildcard."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import shadow_openrouter_wildcard as wildcard
from shadow_execution_policy import HOSTS


SCRIPT = SCRIPTS / "shadow_openrouter_wildcard.py"


def valid_request() -> dict[str, object]:
    return {
        "schema": "shadow.openrouter-wildcard-request.v1",
        "task_sha256": "a" * 64,
        "work_class": "review",
        "operation": "advisory",
        "data_class": "non-sensitive",
        "admission": {"mode": "explicit"},
        "required_capabilities": ["text"],
        "request": {
            "model": "openrouter/free",
            "provider": {
                "zdr": True,
                "data_collection": "deny",
                "require_parameters": True,
                "allow_fallbacks": False,
                "max_price": {
                    "prompt": 0,
                    "completion": 0,
                    "request": 0,
                    "image": 0,
                },
            },
        },
    }


def request_digest(request: dict[str, object]) -> str:
    return hashlib.sha256(wildcard.canonical_request(request)).hexdigest()


def valid_result(
    request: dict[str, object],
    *,
    model: str = "meta-llama/llama-4-maverick:free",
) -> dict[str, object]:
    return {
        "schema": "shadow.openrouter-wildcard-result.v1",
        "request_sha256": request_digest(request),
        "response": {
            "model": model,
            "usage": {"cost": 0},
        },
    }


class RequestContractTests(unittest.TestCase):
    def assert_invalid(
        self,
        request: dict[str, object],
        kind: str = "openrouter_contract_invalid",
    ) -> None:
        with self.assertRaises(wildcard.WildcardContractError) as raised:
            wildcard.canonical_request(request)
        self.assertEqual(raised.exception.kind, kind)

    def test_canonical_request_is_stable_and_exact(self) -> None:
        request = valid_request()
        canonical = wildcard.canonical_request(request)
        self.assertEqual(json.loads(canonical), request)
        self.assertNotIn(b"\n", canonical)
        self.assertNotIn(b" ", canonical)

        reordered = dict(reversed(list(request.items())))
        self.assertEqual(wildcard.canonical_request(reordered), canonical)
        self.assertEqual(
            canonical,
            json.dumps(
                request,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8"),
        )

    def test_only_the_closed_top_level_shape_is_accepted(self) -> None:
        for mutation in ("missing", "unknown"):
            with self.subTest(mutation=mutation):
                request = valid_request()
                if mutation == "missing":
                    request.pop("task_sha256")
                else:
                    request["models"] = ["openrouter/free"]
                self.assert_invalid(request)

    def test_task_digest_must_be_exact_lowercase_sha256(self) -> None:
        for value in ("", "A" * 64, "a" * 63, "g" * 64, 7, None):
            with self.subTest(value=value):
                request = valid_request()
                request["task_sha256"] = value
                self.assert_invalid(request)

    def test_only_inert_explicit_text_advisory_work_is_accepted(self) -> None:
        mutations = {
            "coding": ("work_class", "coding"),
            "mutation": ("operation", "candidate-code"),
            "protected": ("data_class", "protected"),
            "tools": ("required_capabilities", ["text", "tools"]),
            "image": ("required_capabilities", ["image"]),
            "structured": ("required_capabilities", ["structured-output"]),
        }
        for name, (field, value) in mutations.items():
            with self.subTest(mutation=name):
                request = valid_request()
                request[field] = value
                self.assert_invalid(
                    request,
                    kind="openrouter_runtime_boundary_unproved",
                )

        for work_class in ("planning", "review", "lightweight"):
            with self.subTest(work_class=work_class):
                request = valid_request()
                request["work_class"] = work_class
                self.assertTrue(wildcard.canonical_request(request))

    def test_unhashable_work_class_fails_closed(self) -> None:
        request = valid_request()
        request["work_class"] = ["review"]
        self.assert_invalid(request)

    def test_unavailability_admission_stays_behind_the_activation_wake(self) -> None:
        request = valid_request()
        request["admission"] = {
            "mode": "ordinary-routes-unavailable",
            "receipts": [],
        }
        self.assert_invalid(
            request,
            kind="openrouter_runtime_boundary_unproved",
        )

    def test_router_model_and_provider_policy_are_exact(self) -> None:
        mutations: list[tuple[str, object]] = [
            ("model", "openrouter/auto"),
            ("model", "openai/gpt-5.6-sol"),
            ("zdr", False),
            ("data_collection", "allow"),
            ("require_parameters", False),
            ("allow_fallbacks", True),
        ]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                request = valid_request()
                payload = request["request"]
                assert isinstance(payload, dict)
                if field == "model":
                    payload[field] = value
                else:
                    provider = payload["provider"]
                    assert isinstance(provider, dict)
                    provider[field] = value
                self.assert_invalid(request)

    def test_provider_and_price_shapes_are_closed(self) -> None:
        for target in ("provider", "max_price"):
            for mutation in ("missing", "unknown"):
                with self.subTest(target=target, mutation=mutation):
                    request = valid_request()
                    payload = request["request"]
                    assert isinstance(payload, dict)
                    provider = payload["provider"]
                    assert isinstance(provider, dict)
                    container = provider
                    key = "zdr"
                    if target == "max_price":
                        container = provider["max_price"]
                        assert isinstance(container, dict)
                        key = "prompt"
                    if mutation == "missing":
                        container.pop(key)
                    else:
                        container["unknown"] = 0
                    self.assert_invalid(request)

    def test_every_price_ceiling_must_be_finite_numeric_zero(self) -> None:
        invalid_values = (True, False, 1, -1, 0.01, float("nan"), float("inf"))
        for field in ("prompt", "completion", "request", "image"):
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    request = valid_request()
                    payload = request["request"]
                    assert isinstance(payload, dict)
                    provider = payload["provider"]
                    assert isinstance(provider, dict)
                    prices = provider["max_price"]
                    assert isinstance(prices, dict)
                    prices[field] = value
                    self.assert_invalid(request)

        request = valid_request()
        payload = request["request"]
        assert isinstance(payload, dict)
        provider = payload["provider"]
        assert isinstance(provider, dict)
        prices = provider["max_price"]
        assert isinstance(prices, dict)
        prices["prompt"] = -0.0
        normalized = json.loads(wildcard.canonical_request(request))
        self.assertEqual(normalized["request"]["provider"]["max_price"]["prompt"], 0)


class ResultContractTests(unittest.TestCase):
    def assert_invalid(
        self,
        request: dict[str, object],
        result: dict[str, object],
    ) -> None:
        with self.assertRaises(wildcard.WildcardContractError) as raised:
            wildcard.validate_result(request, result)
        self.assertEqual(raised.exception.kind, "openrouter_contract_invalid")

    def test_result_binds_request_concrete_model_and_zero_cost(self) -> None:
        request = valid_request()
        result = valid_result(request)
        self.assertEqual(
            wildcard.validate_result(request, result),
            {
                "schema": "shadow.openrouter-wildcard-result.v1",
                "request_sha256": request_digest(request),
                "response": {
                    "model": "meta-llama/llama-4-maverick:free",
                    "usage": {"cost": 0},
                },
            },
        )

    def test_two_different_concrete_free_selections_validate_separately(self) -> None:
        request = valid_request()
        first = wildcard.validate_result(
            request,
            valid_result(request, model="meta-llama/llama-4-maverick:free"),
        )
        second = wildcard.validate_result(
            request,
            valid_result(request, model="google/gemma-3-27b-it:free"),
        )
        self.assertNotEqual(first["response"]["model"], second["response"]["model"])
        self.assertEqual(first["request_sha256"], second["request_sha256"])

    def test_result_shape_and_request_digest_are_closed(self) -> None:
        request = valid_request()
        for mutation in ("missing", "unknown", "digest"):
            with self.subTest(mutation=mutation):
                result = valid_result(request)
                if mutation == "missing":
                    result.pop("response")
                elif mutation == "unknown":
                    result["proof"] = "model-written"
                else:
                    result["request_sha256"] = "b" * 64
                self.assert_invalid(request, result)

    def test_result_requires_a_concrete_non_router_model(self) -> None:
        for model in (
            "",
            "openrouter/free",
            "openrouter/auto",
            "openrouter/not-a-concrete-model",
            "OpenRouter/not-a-concrete-model",
            "missing-slash",
            "provider/",
            "/model",
            "provider/model with space",
            7,
            None,
        ):
            with self.subTest(model=model):
                request = valid_request()
                result = valid_result(request)
                response = result["response"]
                assert isinstance(response, dict)
                response["model"] = model
                self.assert_invalid(request, result)

    def test_result_cost_must_be_present_finite_numeric_and_exactly_zero(self) -> None:
        for cost in (True, False, 0.01, -0.01, float("nan"), float("inf"), "0", None):
            with self.subTest(cost=cost):
                request = valid_request()
                result = valid_result(request)
                response = result["response"]
                assert isinstance(response, dict)
                usage = response["usage"]
                assert isinstance(usage, dict)
                usage["cost"] = cost
                self.assert_invalid(request, result)

        request = valid_request()
        result = valid_result(request)
        response = result["response"]
        assert isinstance(response, dict)
        response["usage"] = {}
        self.assert_invalid(request, result)


class InactiveBoundaryTests(unittest.TestCase):
    def test_wildcard_is_not_a_runnable_shadow_host(self) -> None:
        self.assertNotIn("openrouter-wildcard", HOSTS)
        source = (SCRIPTS / "shadow_execution_policy.py").read_text(encoding="utf-8")
        self.assertNotIn("openrouter-wildcard", source)

    def test_contract_module_has_no_runtime_or_write_capability(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imports: set[str] = set()
        forbidden_calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {
                    "write_text",
                    "write_bytes",
                    "unlink",
                    "rename",
                    "replace",
                    "rmdir",
                    "mkdir",
                }:
                    forbidden_calls.add(node.func.attr)
        self.assertTrue(
            imports.isdisjoint(
                {
                    "http",
                    "keyring",
                    "os",
                    "requests",
                    "shutil",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            ),
            imports,
        )
        self.assertEqual(forbidden_calls, set())


class CliTests(unittest.TestCase):
    def test_request_and_verify_print_only_canonical_sanitized_json(self) -> None:
        request = valid_request()
        result = valid_result(request)
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            request_path = root / "request.json"
            result_path = root / "result.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            result_path.write_text(json.dumps(result), encoding="utf-8")

            request_run = subprocess.run(
                [sys.executable, str(SCRIPT), "request", "--input", str(request_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(request_run.returncode, 0, request_run.stderr)
            self.assertEqual(
                request_run.stdout,
                wildcard.canonical_request(request).decode("utf-8") + "\n",
            )
            self.assertEqual(request_run.stderr, "")

            verify_run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "verify",
                    "--request",
                    str(request_path),
                    "--result",
                    str(result_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify_run.returncode, 0, verify_run.stderr)
            self.assertEqual(json.loads(verify_run.stdout), result)
            self.assertEqual(verify_run.stderr, "")

    def test_cli_rejects_duplicate_fields_and_nonfinite_json(self) -> None:
        invalid_documents = (
            '{"schema":"one","schema":"two"}',
            '{"price":NaN}',
            '{"price":Infinity}',
        )
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "invalid.json"
            for document in invalid_documents:
                with self.subTest(document=document):
                    path.write_text(document, encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), "request", "--input", str(path)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    error = json.loads(result.stderr)
                    self.assertEqual(error["status"], "blocked")
                    self.assertEqual(
                        error["blocked"]["kind"],
                        "openrouter_contract_invalid",
                    )

    def test_cli_rejects_an_oversized_contract_before_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "oversized.json"
            path.write_text(" " * (wildcard.MAX_DOCUMENT_BYTES + 1), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "request", "--input", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            json.loads(result.stderr)["blocked"]["kind"],
            "openrouter_contract_invalid",
        )

    def test_cli_reports_the_stable_activation_wake(self) -> None:
        request = valid_request()
        request["work_class"] = "coding"
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "request", "--input", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        error = json.loads(result.stderr)
        self.assertEqual(
            error["blocked"],
            {
                "kind": "openrouter_runtime_boundary_unproved",
                "wake": "openrouter_runtime_boundary_unproved",
            },
        )


if __name__ == "__main__":
    unittest.main()
