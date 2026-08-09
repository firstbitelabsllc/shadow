from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "shadow-status.py"

PLAN = """# Demo

## Brief

- Outcome ID: ship-demo
- Outcome Revision: 1
- Outcome Updated At: 2026-08-03T03:00:00Z
- Outcome State: needs_input
- Outcome: Ship the demo.
- Next: Choose the review depth.
- Decision ID: choose-review
- Decision: How should we review it?
- Option A ID: focused-check
- Option A: Focused check
- Option A Consequence: Run only the direct regression.
- Option B ID: full-check
- Option B: Full check
- Option B Consequence: Run every local test.
- Option C ID: stop-now
- Option C: Stop now
- Option C Consequence: Leave the result unshipped.
"""


class StatusTests(unittest.TestCase):
    def run_status(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(STATUS), "--root", str(root), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_text_is_a_brief_with_abc(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = self.run_status(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Outcome: Ship the demo.", result.stdout)
        self.assertIn("A. Focused check", result.stdout)
        self.assertIn("C. Stop now", result.stdout)
        self.assertNotIn(dirname, result.stdout)

    def test_json_is_bounded_and_path_relative(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = self.run_status(root, "--json")
            payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.status.v1")
        self.assertEqual(payload["plans"][0]["path"], "PLAN.md")
        self.assertNotIn(dirname, result.stdout)

    def test_invalid_root_fails_cleanly(self) -> None:
        result = self.run_status(Path("/definitely/missing/shadow-root"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a directory", result.stderr)


if __name__ == "__main__":
    unittest.main()


V4_PLAN = """# Demo v4

## Brief

- Project: demo
- Mode: ship

## Tasks

### M1 — live milestone
- [completed] parser lands ~aa11 | proof: cmd true
- [pending] the ready row ~bb22 | proof: cmd npm run gate
- [pending] closes ~cc33 (DoD) | proof: read site -> renders | needs: ~bb22

## Progress

- 2026-08-08T00:00:00Z ~aa11 PROOF true -> ok
"""


class StatusV4Tests(StatusTests):
    def test_v4_plan_renders_brief_not_schema_error(self) -> None:
        # The regression this pins: status used to validate ONLY the retired v3
        # outcome schema, so a grammar-clean v4 plan reported "needs a valid
        # Brief / outcome must be a string" (250/250 plans on the reference
        # machine). A v4 plan must render its Brief and never the v3 error.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = self.run_status(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("demo", result.stdout)
            self.assertIn("Mode: ship", result.stdout)
            self.assertIn("M1 — live milestone (1/3 done)", result.stdout)
            self.assertIn("Resume: [pending] the ready row ~bb22", result.stdout)
            self.assertNotIn("outcome must be a string", result.stdout)
            self.assertNotIn("needs a valid Brief", result.stdout)

    def test_v4_plan_renders_from_any_cwd(self) -> None:
        # discover_plans emits root-relative paths; status must resolve them
        # against the scan root, not the process cwd.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                cwd=dirname if dirname != str(ROOT) else "/",
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn("Mode: ship", result.stdout)

    def test_stalled_plan_does_not_claim_every_task_complete(self) -> None:
        # Nothing selectable is not the same as nothing left: a plan whose only
        # open rows are person-gated or needs-blocked must say so, not tell the
        # reader to mint a successor over unfinished work.
        stalled = V4_PLAN.replace(
            "- [pending] the ready row ~bb22 | proof: cmd npm run gate",
            "- [pending] owner clicks release ~bb22 | proof: gate owner resume: live",
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(stalled, encoding="utf-8")
            result = self.run_status(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("every task complete", result.stdout)
        self.assertIn("1 person-gated", result.stdout)
        self.assertIn("1 waiting on needs", result.stdout)

    def test_v4_json_carries_v4_plans(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = self.run_status(root, "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["v4_plans"]), 1)
            self.assertEqual(payload["v4_plans"][0]["project"], "demo")

    def test_v4_paths_stay_relative_to_the_scan_root(self) -> None:
        # Codex (PR #263, P2): v4 records printed an absolute path while
        # legacy records stayed root-relative, leaking the operator's home
        # directory onto a portfolio board.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            text = self.run_status(root)
            payload = json.loads(self.run_status(root, "--json").stdout)
        self.assertEqual(payload["v4_plans"][0]["path"], "PLAN.md")
        self.assertNotIn(dirname, text.stdout)

    def test_unreadable_rows_are_surfaced_not_swallowed(self) -> None:
        # Codex (PR #263, P1): a v4 Brief alone made the plan "v4"; malformed
        # rows were dropped silently, so a plan with open work could render as
        # complete. The board must say the plan does not read clean.
        broken = V4_PLAN.replace(
            "- [pending] the ready row ~bb22 | proof: cmd npm run gate",
            "- [doing] the ready row ~bb22 proof cmd npm run gate",
        ).replace(
            "- [pending] closes ~cc33 (DoD) | proof: read site -> renders | needs: ~bb22",
            "- [completed] closes ~cc33 (DoD) | proof: read site -> renders",
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(broken, encoding="utf-8")
            result = self.run_status(root)
        self.assertNotIn("every task complete", result.stdout)
        self.assertIn("Plan health:", result.stdout)
        self.assertIn("shadow lint", result.stdout)


class StatusPortfolioFallbackTests(unittest.TestCase):
    def test_empty_workspace_falls_back_to_portfolio_root(self) -> None:
        # The car-session failure: shadow opened in a blank voice workspace
        # reported nothing and the wrapping agent asked "which project should I
        # attach to?". An empty cwd scan must fall back to the portfolio root
        # so every entry point shows the SAME durable plan list.
        import os as _os

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            proj = Path(portfolio) / "demo-repo"
            proj.mkdir()
            (proj / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            env = dict(_os.environ)
            env["SHADOW_PORTFOLIO_ROOT"] = portfolio
            env.pop("SHADOW_DEV_ROOT", None)
            result = subprocess.run(
                [sys.executable, str(STATUS)],
                cwd=blank,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            # The message no longer names the portfolio path: this line lands
            # in terminals and pasted issues, and Shadow's own privacy gate
            # flags an absolute home path anywhere in its output.
            self.assertIn("showing the portfolio", result.stderr)
            self.assertNotIn(str(Path.home()), result.stderr)
            self.assertIn("Mode: ship", result.stdout)
            self.assertIn("Resume: [pending] the ready row ~bb22", result.stdout)

    def test_explicit_root_never_falls_back(self) -> None:
        import os as _os

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            proj = Path(portfolio) / "demo-repo"
            proj.mkdir()
            (proj / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            env = dict(_os.environ)
            env["SHADOW_PORTFOLIO_ROOT"] = portfolio
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", blank],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotIn("showing the portfolio", result.stderr)
            self.assertNotIn("Mode: ship", result.stdout)

    def test_opt_out_flag_keeps_empty_empty(self) -> None:
        import os as _os

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            env = dict(_os.environ)
            env["SHADOW_PORTFOLIO_ROOT"] = portfolio
            result = subprocess.run(
                [sys.executable, str(STATUS), "--no-portfolio-fallback"],
                cwd=blank,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotIn("showing the portfolio", result.stderr)


V4_TWO_MILESTONES = """# Demo v4 two

## Brief

- Project: demo
- Mode: ship

## Tasks

### M1 — everything here is needs-blocked
- [pending] blocked row ~aa11 | proof: cmd true | needs: ~cc33
- [pending] blocked closer ~bb22 (DoD) | proof: read x -> y | needs: ~aa11

### M2 — where the live work actually is
- [in_progress] the live row ~cc33 | proof: cmd npm run gate
- [pending] closer ~dd44 (DoD) | proof: read site -> renders | needs: ~cc33

## Progress

- 2026-08-08T00:00:00Z STRUCT fixture | trigger: test
"""


class StatusMatchesAmpTests(unittest.TestCase):
    def test_milestone_line_names_the_resumed_rows_milestone(self) -> None:
        # Bugbot (PR #263, High): status labeled the plan with the FIRST open
        # milestone while amp resumed an in_progress row in a LATER one —
        # breaking the shared-parser guarantee. The Milestone line must name
        # the milestone the Resume row lives in.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_TWO_MILESTONES, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                capture_output=True, text=True, check=False,
            )
            self.assertIn("Resume: [in_progress] the live row ~cc33", result.stdout)
            self.assertIn("Milestone: M2 — where the live work actually is", result.stdout)
            self.assertNotIn("Milestone: M1", result.stdout)


class StatusBrokenPlanTests(unittest.TestCase):
    def test_broken_local_plan_blocks_fallback_and_says_why(self) -> None:
        # Bugbot (PR #263, Medium): discover_plans silently skips a PLAN.md
        # that raises during ingestion, so the fallback could mask a BROKEN
        # local plan behind a healthy portfolio board.
        import os as _os
        import stat as _stat

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            plan = Path(blank) / "PLAN.md"
            plan.write_text("# unreadable", encoding="utf-8")
            plan.chmod(0)
            try:
                env = dict(_os.environ)
                env["SHADOW_PORTFOLIO_ROOT"] = portfolio
                result = subprocess.run(
                    [sys.executable, str(STATUS)],
                    cwd=blank, env=env, capture_output=True, text=True, check=False,
                )
                self.assertIn("failed to load", result.stderr)
                self.assertNotIn("showing the portfolio", result.stderr)
            finally:
                plan.chmod(_stat.S_IRUSR | _stat.S_IWUSR)


class AmpRelativePlanTests(unittest.TestCase):
    def test_relative_plan_resolves_against_repo_not_cwd(self) -> None:
        # Bugbot (PR #263, High): a relative --plan resolved against the cwd,
        # so `shadow amp --repo /x --plan PLAN.md` run from a directory with
        # its OWN PLAN.md read the wrong file.
        AMP = ROOT / "scripts" / "shadow-amp.py"
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as cwd:
            (Path(repo) / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            decoy = V4_PLAN.replace("- Project: demo", "- Project: decoy")
            (Path(cwd) / "PLAN.md").write_text(decoy, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(AMP), "--repo", repo, "--plan", "PLAN.md"],
                cwd=cwd, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/goal demo", result.stdout)
            self.assertNotIn("decoy", result.stdout)


class StatusLintBlockingTests(unittest.TestCase):
    """Codex review, PR #263: a v4-SHAPED plan is not a v4-VALID plan. `_parse`
    skips rows it cannot match, so a plan whose only open work sits in a
    malformed row must never render as "nothing left to do"."""

    # Every PARSED row is completed; the open work is in a row the grammar
    # cannot read. Before the guard this briefed as a finished plan.
    HIDDEN_WORK = """# Broken

## Brief

- Project: broken
- Mode: ship

## Tasks

### M1 — the readable rows are all done
- [completed] groundwork ~aa11 | proof: cmd true
- [completed] closer ~cc33 (DoD) | proof: read x -> y
- [pending] THE REAL WORK, unreadable to the grammar

## Progress

- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok
"""

    def test_completion_is_never_claimed_while_lint_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(self.HIDDEN_WORK, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                capture_output=True, text=True, check=False)
            self.assertNotIn("mint the successor", result.stdout)
            self.assertIn("cannot be trusted", result.stdout)
            # and the operator is still told the plan is unhealthy
            self.assertIn("Plan health", result.stdout)

    def test_clean_complete_plan_still_mints_the_successor(self) -> None:
        # Flipping the states is not enough to make a plan complete: since
        # 0.1.0 lint blocks a [completed] row with no paired PROOF line, so a
        # genuinely clean finished plan has to carry a receipt per row. That is
        # the point of the rule — this fixture used to fake completion the same
        # way a careless operator would.
        done = (
            V4_PLAN.replace("[pending]", "[completed]").replace("[in_progress]", "[completed]")
            + "- 2026-08-08T01:00:00Z ~bb22 PROOF gate -> pass\n"
            + "- 2026-08-08T02:00:00Z ~cc33 PROOF site re-observed -> renders\n"
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(done, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                capture_output=True, text=True, check=False)
            self.assertNotIn("cannot be trusted", result.stdout)
