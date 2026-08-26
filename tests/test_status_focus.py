from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.plan_tree_fixture import install_plan_tree


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "shadow-status.py"

PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2
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

## Tasks

### Demo release
- [pending] Choose the review depth ~aa11 | proof: read tests/test_status_focus.py -> passes
- [pending] Demo is released ~bb22 (DoD) | proof: read demo -> visible
"""


class StatusTests(unittest.TestCase):
    def run_status(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        home = root / ".test-home" if root.is_dir() else Path("/tmp")
        home.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [sys.executable, str(STATUS), "--root", str(root), *args],
            cwd=ROOT,
            env={**os.environ, "HOME": str(home)},
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
        self.assertIn("demo —", result.stdout)
        self.assertIn("Mode: ship", result.stdout)
        self.assertIn("Choose the review depth", result.stdout)
        self.assertNotIn("A. Focused check", result.stdout)
        self.assertNotIn(dirname, result.stdout)

    def test_status_names_unresolved_plan_entries_not_acceptance_challenges(self) -> None:
        text = PLAN + (
            "\n## Contradictions\n\n"
            "- one open plan conflict | provisional winner: measure\n"
            "- a decided-looking plan conflict | winner: smaller\n"
            "- RESOLVED 2026-08-26: retired conflict | winner: smaller\n"
            "\n## Progress\n"
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(text, encoding="utf-8")
            result = self.run_status(root)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plan contradictions unresolved: 2", result.stdout)
        self.assertNotIn("acceptance challenge", result.stdout.lower())
        self.assertNotIn("blocker", result.stdout.lower())
        self.assertNotIn("bug", result.stdout.lower())

    def test_json_is_bounded_and_path_relative(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = self.run_status(root, "--json")
            payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.status.v1")
        self.assertEqual(payload["plans"], [])
        self.assertEqual(payload["v4_plans"][0]["project"], "demo")
        self.assertEqual(len(payload["root_board"]["entities"]), 1)
        self.assertNotIn(dirname, result.stdout)

    def test_in_flight_json_does_not_repeat_the_portfolio_index(self) -> None:
        """The footer surface carries claim authority, not every board pointer."""
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = self.run_status(root, "--in-flight", "--json")
            payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            set(payload["root_board"]),
            {"schema", "revision", "claims"},
            payload["root_board"],
        )
        self.assertEqual(payload["root_board"]["claims"], [])
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


OMISSION_PLAN = """# Demo omissions

## Brief

- Project: demo
- Mode: ship

## Tasks

### Finished long ago
- [completed] first result exists ~aa11 | proof: cmd true
- [completed] finished result is accepted ~bb22 (DoD) | proof: cmd true

### Also finished
- [completed] second result exists ~ee55 | proof: cmd true
- [completed] second result is accepted ~ff66 (DoD) | proof: cmd true

### Current work
- [pending] next result starts ~cc33 | proof: cmd true
- [pending] next result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~cc33

## Progress

- 2026-08-10T00:00:00Z ~aa11 PROOF true -> pass
- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass
- 2026-08-10T00:02:00Z ~ee55 PROOF true -> pass
- 2026-08-10T00:03:00Z ~ff66 PROOF true -> pass
"""


class OmittedRowsAreCounted(StatusTests):
    """A surface that hides work must say how much it hid.

    `milestone_rotation` drops every completed row, and then drops a milestone
    entirely once nothing is left to show. That focus is correct — but it was
    silent, and silence reads as completeness.

    Measured 2026-08-17: on Shadow's own plan `shadow status` showed 6 of 18
    milestones with no count anywhere in the output. A seat looking for an
    archive target read the 6, concluded no milestone was eligible, and
    diagnosed the byte-budget gate as advertising an unreachable remedy. Five
    of the twelve hidden milestones were eligible the whole time. The report
    was not wrong about what it showed; it was wrong about what it implied.
    """

    def _payload(self, root: Path) -> dict:
        (root / "PLAN.md").write_text(OMISSION_PLAN, encoding="utf-8")
        result = self.run_status(root, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _plan(self, payload: dict) -> dict:
        plans = payload.get("v4_plans") or []
        self.assertTrue(plans, payload)
        return plans[0]

    def test_a_fully_completed_milestone_is_counted_where_it_is_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            plan = self._plan(self._payload(Path(dirname)))
        omitted = plan.get("omitted")
        self.assertIsNotNone(omitted, plan)
        # 2 hidden milestones vs 1 shown: the numbers must differ, or a
        # mutation reporting SHOWN instead of OMITTED would pass unnoticed.
        self.assertEqual(omitted.get("milestones"), 2, omitted)
        self.assertEqual(omitted.get("checkpoints"), 4, omitted)

    def test_the_shown_rotation_still_carries_only_live_work(self) -> None:
        """The count is additive: focus itself must not change."""
        with tempfile.TemporaryDirectory() as dirname:
            plan = self._plan(self._payload(Path(dirname)))
        titles = [m["title"] for m in plan["milestones"]]
        self.assertEqual(titles, ["Current work"], titles)

    def test_a_plan_hiding_nothing_reports_no_omissions(self) -> None:
        """No false alarm: a plan with nothing hidden must not claim omissions."""
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = self.run_status(root, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = self._plan(json.loads(result.stdout))
        # V4_PLAN's single milestone is live, so its completed row is the only
        # thing hidden and the milestone itself is not.
        omitted = plan.get("omitted") or {}
        self.assertEqual(omitted.get("milestones", 0), 0, omitted)

    def test_the_human_render_states_the_omission(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(OMISSION_PLAN, encoding="utf-8")
            result = self.run_status(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("omitted", result.stdout.lower(), result.stdout)


class StatusV4Tests(StatusTests):
    def test_by_focuses_the_human_view_on_the_seats_next_entity(self) -> None:
        # A cold seat needs every claim it owns or one exact next claim, not a
        # transcript-sized rendering of every open checkpoint on the machine.
        # The unscoped human view remains the full portfolio for inspection.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            alpha = root / "alpha"
            beta = root / "beta"
            alpha.mkdir()
            beta.mkdir()
            alpha.joinpath("PLAN.md").write_text(
                V4_PLAN.replace("# Demo v4", "# Alpha")
                .replace("Project: demo", "Project: alpha")
                .replace("the ready row", "the alpha cold-start row"),
                encoding="utf-8",
            )
            beta.joinpath("PLAN.md").write_text(
                V4_PLAN.replace("# Demo v4", "# Beta")
                .replace("Project: demo", "Project: beta")
                .replace("the ready row", "the beta portfolio-only row"),
                encoding="utf-8",
            )

            focused = self.run_status(root, "--by", "cold-seat")
            full = self.run_status(root)

        self.assertEqual(focused.returncode, 0, focused.stderr)
        self.assertIn("Portfolio: 2 entities", focused.stdout)
        self.assertIn("alpha —", focused.stdout)
        self.assertIn("the alpha cold-start row", focused.stdout)
        self.assertIn("--by cold-seat", focused.stdout)
        self.assertNotIn("Milestone rotation:", focused.stdout)
        self.assertNotIn("beta —", focused.stdout)
        self.assertNotIn("the beta portfolio-only row", focused.stdout)
        self.assertLess(len(focused.stdout), len(full.stdout))
        self.assertIn("beta —", full.stdout)
        self.assertIn("the beta portfolio-only row", full.stdout)

    def test_partitioned_plan_renders_the_same_v4_brief(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            plan = root / "PLAN.md"
            plan.write_text(V4_PLAN, encoding="utf-8")
            legacy = self.run_status(root, "--json")
            install_plan_tree(root, V4_PLAN.encode("utf-8"))
            partitioned = self.run_status(root, "--json")

        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual(partitioned.returncode, 0, partitioned.stderr)
        legacy_payload = json.loads(legacy.stdout)
        partitioned_payload = json.loads(partitioned.stdout)
        self.assertEqual(legacy_payload["v4_plans"], partitioned_payload["v4_plans"])

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
            self.assertIn("Current outcome: live milestone", result.stdout)
            self.assertIn("Resume: [pending] the ready row", result.stdout)
            self.assertIn("--task '~bb22'", result.stdout)
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
                env={**os.environ, "HOME": str(root / ".home")},
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
        self.assertTrue(payload["v4_plans"][0]["path"].endswith("/PLAN.md"))
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
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("portfolio import failed", result.stderr)
        self.assertIn("does not read clean", result.stderr)


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
            env["HOME"] = blank
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
            self.assertIn("Resume: [pending] the ready row", result.stdout)
            self.assertIn("--task '~bb22'", result.stdout)

    def test_explicit_root_changes_import_scope_but_never_hides_the_board(self) -> None:
        import os as _os

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            proj = Path(portfolio) / "demo-repo"
            proj.mkdir()
            (proj / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            env = dict(_os.environ)
            env["SHADOW_PORTFOLIO_ROOT"] = portfolio
            env["HOME"] = blank
            initialized = subprocess.run(
                [sys.executable, str(STATUS)],
                cwd=blank,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn("Mode: ship", initialized.stdout)
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", blank],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotIn("showing the portfolio", result.stderr)
            self.assertIn("Mode: ship", result.stdout)
            self.assertIn("root board revision", result.stdout)

    def test_a_symlinked_child_does_not_decide_the_fallback(self) -> None:
        # discover_plans refuses a symlinked child because it resolves outside
        # the scan root. Fallback detection asks the same question, so it must
        # refuse it too — otherwise an external PLAN.md reachable through a
        # symlink reports "exists but failed to load" and blocks the fallback
        # over a file this root does not own.
        import os as _os

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            outside = Path(blank) / "outside" / "external"
            outside.mkdir(parents=True)
            (outside / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            work = Path(blank) / "work"
            work.mkdir()
            (work / "external").symlink_to(outside, target_is_directory=True)
            proj = Path(portfolio) / "demo-repo"
            proj.mkdir()
            (proj / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            env = dict(_os.environ)
            env["SHADOW_PORTFOLIO_ROOT"] = portfolio
            env["HOME"] = blank
            env.pop("SHADOW_DEV_ROOT", None)
            result = subprocess.run(
                [sys.executable, str(STATUS)],
                cwd=str(work), env=env, capture_output=True, text=True, check=False,
            )
            self.assertNotIn("failed to load", result.stderr)
            self.assertIn("showing the portfolio", result.stderr)

    def test_retired_board_bypass_flag_is_rejected(self) -> None:
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
            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized arguments", result.stderr)


V4_TWO_MILESTONES = """# Demo v4 two

## Brief

- Project: demo
- Mode: ship

## Tasks

### m20 — everything here is needs-blocked
- [pending] blocked row ~aa11 | proof: cmd true | needs: ~cc33
- [pending] blocked closer ~bb22 (DoD) | proof: read x -> y | needs: ~aa11

### m21 — where the live work actually is
- [in_progress] the live row ~cc33 | proof: cmd npm run gate
- [pending] closer ~dd44 (DoD) | proof: read site -> renders | needs: ~cc33

## Progress

- 2026-08-08T00:00:00Z STRUCT fixture | trigger: test
"""


class StatusMatchesAmpTests(unittest.TestCase):
    def test_rotation_shows_every_open_milestone_and_marks_the_resume(self) -> None:
        # Bugbot (PR #263, High): status labeled the plan with the FIRST open
        # milestone while amp resumed an in_progress row in a LATER one —
        # breaking the shared-parser guarantee. The Milestone line must name
        # the milestone the Resume row lives in.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_TWO_MILESTONES, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                env={**os.environ, "HOME": str(root / ".home")},
                capture_output=True, text=True, check=False,
            )
            self.assertIn("Resume: [in_progress] the live row", result.stdout)
            self.assertIn("Current outcome: where the live work actually is", result.stdout)
            self.assertIn("open: everything here is needs-blocked", result.stdout)
            self.assertIn("current: where the live work actually is", result.stdout)
            self.assertIn("[pending/waiting] blocked row", result.stdout)
            self.assertIn("[in_progress/reachable] the live row", result.stdout)
            self.assertIn("--task '~cc33'", result.stdout)
            self.assertNotIn("m20", result.stdout)
            self.assertNotIn("m21", result.stdout)

            json_result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root), "--json"],
                env={**os.environ, "HOME": str(root / ".json-home")},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(json_result.returncode, 0, json_result.stderr)
            payload = json.loads(json_result.stdout)
            milestones = payload["v4_plans"][0]["milestones"]
            self.assertEqual(
                [milestone["title_human"] for milestone in milestones],
                [
                    "everything here is needs-blocked",
                    "where the live work actually is",
                ],
            )
            self.assertFalse(milestones[0]["current"])
            self.assertTrue(milestones[1]["current"])
            self.assertEqual(milestones[1]["resume"], "~cc33")
            self.assertEqual(
                [row["availability"] for row in milestones[0]["checkpoints"]],
                ["waiting", "waiting"],
            )

    def test_by_prints_continue_only_for_that_seats_claims(self) -> None:
        throw = ROOT / "scripts" / "shadow-throw.py"
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / ".home"
            home.mkdir()
            claimable = V4_TWO_MILESTONES.replace(" | needs: ~cc33", "")
            (root / "PLAN.md").write_text(claimable, encoding="utf-8")
            for command in (
                ("init", "-q"),
                ("config", "user.email", "test@example.invalid"),
                ("config", "user.name", "Test"),
                ("add", "PLAN.md"),
                ("commit", "-qm", "fixture"),
            ):
                subprocess.run(["git", "-C", str(root), *command], check=True)
            env = {**os.environ, "HOME": str(home)}
            registered = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(registered.returncode, 0, registered.stderr)
            for task, seat in (("~aa11", "seat-a"), ("~cc33", "seat-b")):
                claimed = subprocess.run(
                    [
                        sys.executable, str(throw), "--repo", str(root),
                        "--task", task, "--by", seat,
                    ],
                    env=env, capture_output=True, text=True, check=False,
                )
                self.assertEqual(claimed.returncode, 0, claimed.stderr)
            result = subprocess.run(
                [
                    sys.executable, str(STATUS), "--root", str(root),
                    "--by", "seat-a",
                ],
                env=env, capture_output=True, text=True, check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        continuations = [
            line for line in result.stdout.splitlines() if "Continue:" in line
        ]
        self.assertEqual(len(continuations), 1)
        self.assertIn("--by seat-a", continuations[0])
        self.assertNotIn("seat-b", continuations[0])
        for line in (line for line in result.stdout.splitlines() if "~" in line):
            self.assertRegex(line, r"shadow (?:amp|throw|return) ")


class StatusBrokenPlanTests(unittest.TestCase):
    def test_broken_cwd_plan_cannot_shadow_the_computer_board(self) -> None:
        import os as _os
        import stat as _stat

        with tempfile.TemporaryDirectory() as blank, tempfile.TemporaryDirectory() as portfolio:
            plan = Path(blank) / "PLAN.md"
            plan.write_text("# unreadable", encoding="utf-8")
            plan.chmod(0)
            try:
                env = dict(_os.environ)
                env["SHADOW_PORTFOLIO_ROOT"] = portfolio
                env["HOME"] = blank
                result = subprocess.run(
                    [sys.executable, str(STATUS)],
                    cwd=blank, env=env, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("showing the portfolio", result.stderr)
                self.assertNotIn("unreadable", result.stdout)
            finally:
                plan.chmod(_stat.S_IRUSR | _stat.S_IWUSR)


class AmpRelativePlanTests(unittest.TestCase):
    def test_relative_plan_resolves_against_repo_not_cwd(self) -> None:
        # Bugbot (PR #263, High): a relative --plan resolved against the cwd,
        # so `shadow amp --repo /x --plan PLAN.md` run from a directory with
        # its OWN PLAN.md read the wrong file.
        AMP = ROOT / "scripts" / "shadow-amp.py"
        THROW = ROOT / "scripts" / "shadow-throw.py"
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as cwd,
            tempfile.TemporaryDirectory() as home,
        ):
            (Path(repo) / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            decoy = V4_PLAN.replace("- Project: demo", "- Project: decoy")
            (Path(cwd) / "PLAN.md").write_text(decoy, encoding="utf-8")
            subprocess.run(["git", "init", "-q", repo], check=True)
            subprocess.run(["git", "-C", repo, "add", "PLAN.md"], check=True)
            subprocess.run(
                [
                    "git", "-C", repo,
                    "-c", "user.name=Shadow Test",
                    "-c", "user.email=shadow@example.invalid",
                    "commit", "-qm", "fixture",
                ],
                check=True,
            )
            env = {**os.environ, "HOME": home}
            registered = subprocess.run(
                [sys.executable, str(STATUS), "--root", repo],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(registered.returncode, 0, registered.stderr)
            claimed = subprocess.run(
                [
                    sys.executable, str(THROW), "--repo", repo,
                    "--task", "~bb22", "--by", "seat-a",
                ],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            result = subprocess.run(
                [
                    sys.executable, str(AMP), "--repo", repo,
                    "--plan", "PLAN.md", "--by", "seat-a",
                ],
                cwd=cwd, env=env, capture_output=True, text=True, check=False,
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
                env={**os.environ, "HOME": str(root / ".home")},
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("portfolio import failed", result.stderr)
            self.assertIn("does not read clean", result.stderr)

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
                env={**os.environ, "HOME": str(root / ".home")},
                capture_output=True, text=True, check=False)
            self.assertNotIn("cannot be trusted", result.stdout)
