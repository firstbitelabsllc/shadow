"""Shadow's mechanical enforcer: every check refuses, deterministically."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-lint.py"
SPEC = importlib.util.spec_from_file_location("shadow_lint", SCRIPT)
assert SPEC and SPEC.loader
lint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lint)


CLEAN_PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M — the thing ships
- [completed] wrapper renders ~ab12 | proof: cmd npm run test:pdp
- [in_progress] smoke green ~cd34 | proof: cmd npm run smoke | needs: ~ab12
- [pending] owner submits ~ef56 (DoD) | proof: gate leo resume: ASC verdict lands

## Deferred

- chaos sweep | flavor launch is the gate | wake: M DoD completed

## Contradictions

- None recorded yet.

## Progress

- 2026-08-05T10:00:00Z ~ab12 PROOF npm run test:pdp -> pass
- 2026-08-06T11:00:00Z SPIKE ~cd34 is checkout smoke worth owning | ends: 2026-08-07
- 2026-08-06T12:00:00Z DECISION ~cd34 keep -> smoke stays
"""


def checks(plan: str) -> set[str]:
    return {finding["check"] for finding in lint.lint_plan(plan)}


def blocking(plan: str) -> set[str]:
    return {f["check"] for f in lint.lint_plan(plan) if f["severity"] == "blocking"}


class ShadowLintTests(unittest.TestCase):
    def test_clean_v2_plan_has_no_blocking_findings(self) -> None:
        self.assertEqual(blocking(CLEAN_PLAN), set())

    def test_findings_are_deterministic_across_reruns(self) -> None:
        first = lint.lint_plan(CLEAN_PLAN)
        second = lint.lint_plan(CLEAN_PLAN)
        self.assertEqual(first, second)

    def test_duplicate_row_ids_are_blocking(self) -> None:
        plan = CLEAN_PLAN.replace("~cd34 |", "~ab12 |", 1)
        self.assertIn("ID-DUP", blocking(plan))

    def test_dangling_needs_target_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace("needs: ~ab12", "needs: ~zz99")
        self.assertIn("NEEDS-DANGLE", blocking(plan))

    def test_missing_or_prose_proof_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace("| proof: cmd npm run smoke ", "| proof: it works fine ")
        self.assertIn("PROOF-CLASS", blocking(plan))
        plan2 = CLEAN_PLAN.replace(" | proof: cmd npm run smoke", "")
        self.assertIn("PROOF-MISSING", blocking(plan2))

    def test_milestone_dod_shape_is_enforced(self) -> None:
        plan = CLEAN_PLAN.replace(" (DoD)", "")
        self.assertIn("DOD-COUNT", blocking(plan))
        plan2 = CLEAN_PLAN.replace("- [in_progress] smoke green", "- [pending] smoke green").replace(
            "- [pending] owner submits ~ef56 (DoD)", "- [completed] owner submits ~ef56 (DoD)"
        )
        self.assertIn("DOD-EARLY", blocking(plan2))

    def test_deferred_row_without_wake_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace(" | wake: M DoD completed", "")
        self.assertIn("DEFER-NO-WAKE", blocking(plan))

    def test_illegal_and_legacy_mode_values_are_blocking(self) -> None:
        self.assertIn("MODE-ILLEGAL", blocking(CLEAN_PLAN.replace("- Mode: ship", "- Mode: turbo")))
        self.assertIn("MODE-ILLEGAL", blocking(CLEAN_PLAN.replace("- Mode: ship", "- Mode: Challenge")))

    def test_non_monotonic_progress_timestamps_are_a_warning(self) -> None:
        plan = CLEAN_PLAN.replace("2026-08-06T12:00:00Z DECISION", "2026-08-04T12:00:00Z DECISION")
        hits = [f for f in lint.lint_plan(plan) if f["check"] == "TS-ORDER"]
        self.assertTrue(hits and all(f["severity"] == "warning" for f in hits))

    def test_overlong_line_is_a_warning(self) -> None:
        plan = CLEAN_PLAN + "\n- " + "x" * 2100 + "\n"
        findings = lint.lint_plan(plan)
        hits = [f for f in findings if f["check"] == "READ-FIT"]
        self.assertTrue(hits and all(f["severity"] == "warning" for f in hits))

    def test_box_lifecycle_checks(self) -> None:
        no_end = CLEAN_PLAN.replace(" | ends: 2026-08-07", "")
        self.assertIn("SPIKE-NO-END", blocking(no_end))
        expired = CLEAN_PLAN.replace("ends: 2026-08-07", "ends: 2026-08-05").replace(
            "- 2026-08-06T12:00:00Z DECISION ~cd34 keep -> smoke stays\n", ""
        )
        self.assertIn("SPIKE-EXPIRED-NO-DECISION", blocking(expired))
        self.assertIn("SHIP-OVER-OPEN-SPIKE", blocking(expired))
        orphan = CLEAN_PLAN.replace(
            "- 2026-08-06T11:00:00Z SPIKE ~cd34 is checkout smoke worth owning | ends: 2026-08-07\n", ""
        )
        findings = lint.lint_plan(orphan)
        self.assertIn("ORPHAN-DECISION", {f["check"] for f in findings if f["severity"] == "warning"})

    def test_secret_shaped_proof_is_blocking(self) -> None:
        token = "xoxb-" + "1234567890-ABCDEFGHIJKLMNOP"
        plan = CLEAN_PLAN.replace("cmd npm run smoke", f"cmd curl -H 'Authorization: {token}'")
        self.assertIn("PROOF-SECRET", blocking(plan))

    def test_a_secret_hidden_behind_an_embedded_pipe_is_still_blocking(self) -> None:
        token = "xoxb-" + "1234567890-ABCDEFGHIJKLMNOP"
        plan = CLEAN_PLAN.replace("cmd npm run smoke", f"cmd npm run smoke | curl -H 'X: {token}'")
        found = blocking(plan)
        self.assertIn("PROOF-SECRET", found)
        self.assertIn("ROW-SHAPE", found)

    def test_tail_residue_outside_fields_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace("cmd npm run smoke", "cmd true | tee log.txt")
        self.assertIn("ROW-SHAPE", blocking(plan))

    def test_a_repeated_tail_field_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace(
            "| proof: cmd npm run smoke ", "| proof: totally works | proof: cmd npm run smoke "
        )
        self.assertIn("ROW-SHAPE", blocking(plan))

    def test_state_typos_are_not_invisible(self) -> None:
        for bad_state in ("In_Progress", "in-progress", " ", "Completed"):
            plan = CLEAN_PLAN.replace("- [in_progress] smoke green", f"- [{bad_state}] smoke green")
            self.assertTrue(
                blocking(plan) & {"ROW-SHAPE", "PROOF-MISSING"},
                f"state [{bad_state}] produced no blocking finding",
            )

    def test_malformed_needs_value_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace("needs: ~ab12", "needs: tbd")
        self.assertIn("NEEDS-SHAPE", blocking(plan))

    def test_duplicate_box_id_is_blocking(self) -> None:
        plan = CLEAN_PLAN.replace(
            "- 2026-08-06T12:00:00Z DECISION ~cd34 keep -> smoke stays",
            "- 2026-08-06T12:00:00Z SPIKE ~cd34 re-boxed | ends: 2027-01-01",
        )
        self.assertIn("SPIKE-DUP", blocking(plan))

    def test_missing_canonical_section_is_a_warning(self) -> None:
        plan = CLEAN_PLAN.replace("## Tasks", "## Tasks:")
        hits = [f for f in lint.lint_plan(plan) if f["check"] == "SECTION-MISSING"]
        self.assertTrue(hits and all(f["severity"] == "warning" for f in hits))

    def test_wake_substring_lookalikes_do_not_satisfy_defer(self) -> None:
        plan = CLEAN_PLAN.replace("| wake: M DoD completed", "| awake: M DoD completed")
        self.assertIn("DEFER-NO-WAKE", blocking(plan))

    def test_cli_exits_nonzero_on_blocking_and_zero_on_clean(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            clean = Path(dirname) / "clean.md"
            clean.write_text(CLEAN_PLAN, encoding="utf-8")
            dirty = Path(dirname) / "dirty.md"
            dirty.write_text(CLEAN_PLAN.replace("- Mode: ship", "- Mode: turbo"), encoding="utf-8")
            ok = subprocess.run([sys.executable, str(SCRIPT), str(clean)], capture_output=True, text=True)
            bad = subprocess.run([sys.executable, str(SCRIPT), str(dirty)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("MODE-ILLEGAL", bad.stdout)

    def test_cli_lints_every_file_and_aggregates_worst_exit(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            clean = Path(dirname) / "clean.md"
            clean.write_text(CLEAN_PLAN, encoding="utf-8")
            dirty = Path(dirname) / "dirty.md"
            dirty.write_text(CLEAN_PLAN.replace("- Mode: ship", "- Mode: turbo"), encoding="utf-8")
            missing = Path(dirname) / "missing.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(clean), str(missing), str(dirty)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("clean.md: clean", result.stdout)
        self.assertIn("unreadable", result.stdout)
        self.assertIn("MODE-ILLEGAL", result.stdout)


if __name__ == "__main__":
    unittest.main()
