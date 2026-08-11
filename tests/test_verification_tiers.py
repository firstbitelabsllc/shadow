"""Focused verification is deterministic and can never silently select nothing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("shadow_ci", ROOT / "scripts" / "shadow-ci.py")
ci = importlib.util.module_from_spec(SPEC)
sys.modules["shadow_ci"] = ci
SPEC.loader.exec_module(ci)


class ASilentSkipFailsLoudly(unittest.TestCase):
    def test_a_known_runtime_change_selects_its_dependency_closure(self) -> None:
        selected = ci.select_paths(["scripts/shadow_root_board.py"])
        self.assertFalse(selected.run_all)
        self.assertIn("tests.test_root_board", selected.modules)
        self.assertIn("tests.test_throw", selected.modules)
        self.assertTrue(selected.modules)

    def test_a_changed_test_selects_itself(self) -> None:
        selected = ci.select_paths(["tests/test_return.py"])
        self.assertFalse(selected.run_all)
        self.assertIn("tests.test_return", selected.modules)

    def test_docs_select_the_authority_and_drift_contracts(self) -> None:
        selected = ci.select_paths(["docs/reference/grammar.md", "AGENT.md"])
        self.assertFalse(selected.run_all)
        self.assertIn("tests.test_grammar_contract", selected.modules)
        self.assertIn("tests.test_standing_goal", selected.browser_modules)

    def test_changelog_changes_run_the_release_contract(self) -> None:
        selected = ci.select_paths(["CHANGELOG.md"])
        self.assertTrue(selected.release_contract)

    def test_retirement_schema_runs_lifecycle_and_release_proof(self) -> None:
        selected = ci.select_paths(["schemas/retirement-manifest.v1.json"])
        self.assertFalse(selected.run_all)
        self.assertIn("tests.test_lifecycle", selected.modules)
        self.assertTrue(selected.release_contract)

    def test_local_event_boundary_runs_telemetry_and_release_proof(self) -> None:
        for path in ("scripts/shadow_telemetry.py", "docs/reference/telemetry.md"):
            selected = ci.select_paths([path])
            self.assertFalse(selected.run_all)
            self.assertIn("tests.test_telemetry", selected.modules)
            self.assertIn("tests.test_release_package", selected.modules)
        self.assertTrue(ci.select_paths(["scripts/shadow_telemetry.py"]).release_contract)
        throw = ci.select_paths(["scripts/shadow-throw.py"])
        self.assertIn("tests.test_telemetry", throw.modules)

    def test_remote_claim_transport_runs_throw_and_release_proof(self) -> None:
        selected = ci.select_paths(["scripts/shadow_remote_claim.py"])
        self.assertFalse(selected.run_all)
        self.assertIn("tests.test_throw", selected.modules)
        self.assertIn("tests.test_root_board", selected.modules)
        self.assertIn("tests.test_return", selected.modules)
        self.assertIn("tests.test_shadow_accept", selected.modules)
        self.assertTrue(selected.release_contract)

    def test_unknown_or_empty_changes_fall_back_to_full(self) -> None:
        for paths in ([], ["new-unmapped-root/file.xyz"]):
            selected = ci.select_paths(paths)
            self.assertTrue(selected.run_all)
            self.assertIn("full", selected.reason)

    def test_an_empty_or_untrusted_module_packet_is_an_error(self) -> None:
        for packet in ("[]", '["os.system"]', "not-json"):
            with self.assertRaises(ValueError):
                ci.run_selected(False, packet)

    def test_missing_or_unreachable_comparison_base_becomes_full_proof(self) -> None:
        plan = ci.event_plan({
            "EVENT_NAME": "push",
            "PUSH_BEFORE_SHA": "0" * 40,
            "HEAD_SHA": "1" * 40,
        })
        self.assertTrue(plan["run_checks"])
        self.assertTrue(plan["run_all"])
        self.assertIn("base", plan["reason"])

    def test_required_ci_context_names_and_matrix_remain_load_bearing(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("\n  test:\n", workflow)
        self.assertIn("python-version: ['3.10', '3.12', '3.14']", workflow)
        self.assertIn("\n  browser-and-docs:\n", workflow)
        self.assertIn("\n  visual-proof:\n", workflow)
        self.assertNotIn("paths-ignore:", workflow)
        self.assertNotIn("\n    paths:", workflow)


if __name__ == "__main__":
    unittest.main()
