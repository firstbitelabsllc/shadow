"""Shadow's mechanical enforcer: every check refuses, deterministically."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
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

ACCEPT_SCRIPT = ROOT / "scripts" / "shadow-accept.py"
ACCEPT_SPEC = importlib.util.spec_from_file_location("shadow_accept", ACCEPT_SCRIPT)
assert ACCEPT_SPEC and ACCEPT_SPEC.loader
accept = importlib.util.module_from_spec(ACCEPT_SPEC)
ACCEPT_SPEC.loader.exec_module(accept)


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


def commit_fixture(root: Path, *paths: str) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Shadow Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "shadow@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "--", *paths], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "proof fixture"], check=True)


class ShadowLintTests(unittest.TestCase):
    def test_clean_v2_plan_has_no_blocking_findings(self) -> None:
        self.assertEqual(blocking(CLEAN_PLAN), set())

    def test_findings_are_deterministic_across_reruns(self) -> None:
        first = lint.lint_plan(CLEAN_PLAN)
        second = lint.lint_plan(CLEAN_PLAN)
        self.assertEqual(first, second)

    def test_completed_receipt_shape_matches_claim_return(self) -> None:
        malformed = CLEAN_PLAN.replace(
            "2026-08-05T10:00:00Z ~ab12 PROOF npm run test:pdp -> pass",
            "2026-08-10T22:39:12Z ~ab12 PROOF npm run test:pdp",
        )

        self.assertEqual(
            lint._board.progress_proof_receipts(malformed, "~ab12"),
            [],
        )
        self.assertIn("PROOF-RECEIPT-SHAPE", blocking(malformed))
        self.assertIn("COMPLETED-NO-PROOF", blocking(malformed))
        self.assertNotIn("COMPLETED-NO-PROOF", blocking(CLEAN_PLAN))

    def test_pre_cutover_receipt_prose_remains_accepted(self) -> None:
        legacy = CLEAN_PLAN.replace("npm run test:pdp -> pass", "npm run test:pdp")

        self.assertNotIn("PROOF-RECEIPT-SHAPE", blocking(legacy))
        self.assertNotIn("COMPLETED-NO-PROOF", blocking(legacy))

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

    def test_hot_plan_byte_row_and_milestone_budgets_are_blocking(self) -> None:
        oversized = CLEAN_PLAN + "\n<!-- " + "x" * lint._board.HOT_PLAN_MAX_BYTES + " -->\n"
        rows = (
            "# Demo\n\n## Brief\n\n- Project: demo\n- Mode: ship\n\n"
            "## Tasks\n\n### Too many tasks\n"
            + "".join(
                f"- [pending] bounded result {index} ~{index:04x} | proof: cmd true\n"
                for index in range(lint._board.HOT_PLAN_MAX_TASK_ROWS + 1)
            )
            + "\n## Progress\n"
        )
        milestones = CLEAN_PLAN.replace(
            "\n## Deferred\n",
            "\n"
            + "".join(
                f"### Extra bounded milestone {index}\n"
                for index in range(lint._board.HOT_PLAN_MAX_MILESTONES + 1)
            )
            + "\n## Deferred\n",
        )

        self.assertIn("HOT-PLAN-BYTES", blocking(oversized))
        self.assertIn("HOT-PLAN-ROWS", blocking(rows))
        self.assertIn("HOT-PLAN-MILESTONES", blocking(milestones))

    def test_row_shaped_history_does_not_consume_the_tasks_budget(self) -> None:
        history = "".join(
            f"- [pending] retained historical row {index} ~{index:04x} | proof: cmd true\n"
            for index in range(lint._board.HOT_PLAN_MAX_TASK_ROWS + 1)
        )
        plan = CLEAN_PLAN + "\n## Historical task snapshots\n\n" + history

        measured = lint._board.hot_plan_budget(plan.encode("utf-8"))

        self.assertEqual(measured["task_rows"], 3)
        self.assertNotIn("task_rows", measured["exceeded"])

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
        self.assertIn("PLAN-SECRET", blocking(plan))

    def test_a_secret_hidden_behind_an_embedded_pipe_is_still_blocking(self) -> None:
        token = "xoxb-" + "1234567890-ABCDEFGHIJKLMNOP"
        plan = CLEAN_PLAN.replace("cmd npm run smoke", f"cmd npm run smoke | curl -H 'X: {token}'")
        found = blocking(plan)
        self.assertIn("PLAN-SECRET", found)
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

    def test_a_secret_in_a_progress_proof_line_is_blocking(self) -> None:
        token = "xoxb-" + "1234567890-ABCDEFGHIJKLMNOP"
        plan = CLEAN_PLAN + f"- 2026-08-07T09:00:00Z ~ab12 PROOF curl -> got {token}\n"
        self.assertIn("PLAN-SECRET", blocking(plan))

    def test_a_typoed_tasks_heading_cannot_exempt_its_rows(self) -> None:
        plan = CLEAN_PLAN.replace("## Tasks", "## Task")
        self.assertIn("ROWS-WITHOUT-TASKS", blocking(plan))

    def test_a_history_section_beside_a_real_tasks_section_stays_legal(self) -> None:
        plan = CLEAN_PLAN + "\n## Task History (verbatim)\n\n- [completed 2026-05-01] old receipt row, no proof field\n"
        self.assertNotIn("ROWS-WITHOUT-TASKS", blocking(plan))

    def test_hyphenated_english_is_not_a_secret(self) -> None:
        plan = CLEAN_PLAN.replace("smoke green", "task-mismatched risk-mitigation smoke green")
        self.assertNotIn("PLAN-SECRET", blocking(plan))

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


class ConflictMarkersBlock(unittest.TestCase):
    """A half-merged plan must not read as a clean plan.

    Discovered the honest way: a real rebase conflict in this repo's own
    PLAN.md linted rc=0 with `<<<<<<< HEAD` sitting in ## Progress. With
    several leads writing one plan, a committed marker is a live hazard —
    `shadow throw` refuses on unmerged PATHS, but says nothing about a marker
    that already made it into a commit.
    """

    BASE = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M1 — live
- [pending] a row ~aa11 | proof: cmd true

## Progress

- 2026-08-09T00:00:00Z NOTE seeded
"""

    def test_a_clean_plan_has_no_conflict_finding(self) -> None:
        codes = [f["check"] for f in lint.lint_plan(self.BASE)]
        self.assertNotIn("CONFLICT-MARKER", codes)

    def test_each_marker_shape_blocks(self) -> None:
        for marker in ("<<<<<<< HEAD", "=======", ">>>>>>> abc123 (their commit)"):
            found = [
                f for f in lint.lint_plan(self.BASE + marker + "\n")
                if f["check"] == "CONFLICT-MARKER"
            ]
            self.assertEqual(len(found), 1, f"missed {marker!r}")
            self.assertEqual(found[0]["severity"], "blocking")

    def test_a_divider_inside_prose_is_not_a_marker(self) -> None:
        # "=======" only counts on its own line; a row that merely contains it
        # is somebody's text, not a conflict.
        text = self.BASE + "- 2026-08-09T00:01:00Z NOTE see the ======= divider above\n"
        codes = [f["check"] for f in lint.lint_plan(text)]
        self.assertNotIn("CONFLICT-MARKER", codes)


class SectionOrderIsChecked(unittest.TestCase):
    """Order drifted unnoticed because sections are read into a dict.

    Nothing compared their positions, so this repo's own plan ended up with
    Progress in the middle — and Progress is append-only, which makes it the
    worst one to leave there: every cycle buried the open deferrals a little
    deeper, and a cold reader scrolled past a thousand lines of receipts to
    reach them.
    """

    ROWS = ("### M1\n- [pending] r ~aa11 | proof: cmd true\n")

    def _plan(self, *sections: str) -> str:
        return "# x\n\n## Brief\n\n- Project: x\n- Mode: ship\n\n" + "\n".join(sections)

    def test_progress_before_deferred_warns(self) -> None:
        text = self._plan(
            "## Tasks\n\n" + self.ROWS,
            "## Progress\n\n- 2026-08-09T00:00:00Z NOTE x\n",
            "## Deferred\n\n- a | b | wake: c\n",
        )
        found = [f for f in lint.lint_plan(text) if f["check"] == "SECTION-ORDER"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "warning")
        self.assertIn("append-only", found[0]["detail"])

    def test_the_canonical_order_is_silent(self) -> None:
        text = self._plan(
            "## Tasks\n\n" + self.ROWS,
            "## Deferred\n\n- a | b | wake: c\n",
            "## Contradictions\n\n- x vs y | winner x | opened 2026-08-09T00:00:00Z\n",
            "## Progress\n\n- 2026-08-09T00:00:00Z NOTE x\n",
        )
        self.assertEqual([f for f in lint.lint_plan(text) if f["check"] == "SECTION-ORDER"], [])

    def test_a_missing_section_does_not_trip_it(self) -> None:
        # Deferred and Contradictions are optional. Their absence is not disorder.
        text = self._plan("## Tasks\n\n" + self.ROWS, "## Progress\n\n- 2026-08-09T00:00:00Z NOTE x\n")
        self.assertEqual([f for f in lint.lint_plan(text) if f["check"] == "SECTION-ORDER"], [])

    def test_a_suffixed_heading_still_counts_as_its_section(self) -> None:
        # "## Deferred proof (not a global blocker)" is a legal heading, and
        # matching it exactly is what silently disabled DEFER-NO-WAKE for the
        # life of this file.
        text = self._plan(
            "## Tasks\n\n" + self.ROWS,
            "## Progress\n\n- 2026-08-09T00:00:00Z NOTE x\n",
            "## Deferred proof (not a global blocker)\n\n- a | b | wake: c\n",
        )
        self.assertTrue([f for f in lint.lint_plan(text) if f["check"] == "SECTION-ORDER"])


def _checks(text: str, **kw) -> set[str]:
    return {f["check"] for f in lint.lint_plan(text, **kw)}


class RowGrammarRunsWhereverAcceptWouldFlip(unittest.TestCase):
    """The enforcer and the only flip path must agree on what a task is.

    Row checks used to run only under the exact heading `## Tasks`, while
    `shadow accept` builds its row list from `plan_text.splitlines()` — the
    whole file. Any second heading was therefore a lint-free zone whose rows
    accept would still flip to completed and still count for `needs`
    readiness. A row invisible to the enforcer and real to the flip path is
    the same defect class as a proof that proves nothing.
    """

    OUTSIDE = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M — the thing ships
- [pending] a real row ~aa11 | proof: cmd true
- [pending] it ships ~bb22 (DoD) | proof: read site -> renders

## Worklane boundary

- [pending] a duplicate id ~aa11 | proof: it totally works
- [bogus_state] not even a legal state ~zz9 | proof: cmd true
- [pending] no proof at all ~yy88
"""

    def test_a_row_under_another_heading_is_checked(self) -> None:
        found = _checks(self.OUTSIDE)
        self.assertIn("ID-DUP", found, "a duplicate id outside Tasks went unchecked")
        self.assertIn("PROOF-CLASS", found, "an unclassed proof outside Tasks went unchecked")

    def test_a_malformed_row_outside_tasks_is_checked(self) -> None:
        found = _checks(self.OUTSIDE)
        self.assertIn("ROW-SHAPE", found, "an illegal state outside Tasks went unchecked")
        self.assertIn("PROOF-MISSING", found, "a proofless row outside Tasks went unchecked")

    def test_milestone_grouping_stays_scoped_to_tasks(self) -> None:
        # DoD law is about milestones. A stray row under another heading must
        # not invent a milestone, or every plan with prose bullets goes red.
        self.assertNotIn("DOD-COUNT", _checks(self.OUTSIDE))

    def test_lint_checks_the_same_outside_row_accept_can_flip(self) -> None:
        plan = """# Demo

## Brief

- Project: demo
- Mode: ship

## Worklane boundary

- [pending] an outside row ~cc33 | proof: not-classed

## Progress

- None yet.
"""

        self.assertIn("PROOF-CLASS", _checks(plan))
        self.assertEqual(accept.find_row(plan, "~cc33")[2], "pending")
        completed = accept.completed_plan_text(
            plan,
            "~cc33",
            ["true"],
            "2026-08-10T00:00:00Z",
        )
        self.assertIn("- [completed] an outside row ~cc33", completed)

    def test_a_clean_plan_is_still_clean(self) -> None:
        self.assertEqual(_checks(CLEAN_PLAN) - {"SECTION-MISSING", "TS-ORDER"}, set())


class EverySectionLookupIsPrefixMatched(unittest.TestCase):
    """PR #272 prefix-fixed Deferred and left every sibling exact-string."""

    SUFFIXED = """# Demo

## Brief — the north star

- Project: demo
- Mode: turbo

## Tasks

### M — the thing ships
- [pending] a real row ~aa11 | proof: cmd true
- [pending] it ships ~bb22 (DoD) | proof: read site -> renders

## Progress

- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok
"""

    def test_a_suffixed_brief_still_blocks_an_illegal_mode(self) -> None:
        # The exact false green: with an exact-string lookup this returned
        # SECTION-MISSING (warning, rc=0) and MODE-ILLEGAL never fired.
        found = lint.lint_plan(self.SUFFIXED)
        self.assertIn("MODE-ILLEGAL", {f["check"] for f in found})
        self.assertTrue([f for f in found if f["severity"] == "blocking"])

    def test_a_suffixed_heading_is_not_reported_missing(self) -> None:
        details = {f["detail"] for f in lint.lint_plan(self.SUFFIXED)}
        self.assertNotIn("no `## Brief` heading", details)

    def test_every_canonical_section_accepts_a_suffix(self) -> None:
        for name in ("Brief", "Tasks", "Deferred", "Contradictions", "Progress"):
            sections = {f"{name} — with a suffix": [(1, "x")]}
            self.assertTrue(lint._has_section(sections, name), name)
            self.assertEqual(lint._section(sections, name), [(1, "x")], name)

    def test_suffixed_tasks_still_enforces_milestone_law(self) -> None:
        plan = self.SUFFIXED.replace(
            "## Tasks",
            "## Tasks — current work",
        ).replace(
            "- [pending] it ships ~bb22 (DoD) | proof: read site -> renders",
            "- [pending] first exit ~bb22 (DoD) | proof: read site -> renders\n"
            "- [pending] second exit ~cc33 (DoD) | proof: read site -> renders",
        )

        self.assertIn("DOD-COUNT", _checks(plan))

    def test_suffixed_deferred_still_requires_an_exact_wake(self) -> None:
        plan = self.SUFFIXED.replace(
            "## Progress",
            "## Deferred — later\n\n- parked without a wake\n\n## Progress",
        )

        self.assertIn("DEFER-NO-WAKE", _checks(plan))

    def test_a_different_word_starting_with_the_name_is_not_matched(self) -> None:
        # `## Briefing` is not `## Brief`. Prefix means "name plus a space".
        self.assertFalse(lint._has_section({"Briefing": [(1, "x")]}, "Brief"))


class ACmdProofIsValidatedAsArgv(unittest.TestCase):
    """`accept` runs a cmd proof through shlex with NO shell.

    So `&&`, `|`, `;` and `$(...)` arrive as literal ARGUMENTS. The class-word
    check could not see that: `cmd echo done && shadow --version` linted clean,
    ran `echo`, exited 0, flipped the row to completed and wrote `-> pass`
    while `shadow` never ran.
    """

    def _plan(self, proof: str) -> str:
        return f"""# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M — the thing ships
- [pending] a real row ~aa11 | proof: {proof}
- [pending] it ships ~bb22 (DoD) | proof: read site -> renders

## Progress

- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok
"""

    def test_the_documented_false_green_is_refused(self) -> None:
        self.assertIn("PROOF-SHELL-OPERATOR", _checks(self._plan("cmd echo done && true")))

    def test_every_operator_that_reaches_argv_is_refused(self) -> None:
        for operator in ("&&", ";", ">", ">>", "<", "&"):
            with self.subTest(operator=operator):
                self.assertIn("PROOF-SHELL-OPERATOR",
                              _checks(self._plan(f"cmd true {operator} false")))

    def test_a_pipe_is_blocked_by_the_field_separator_before_it_reaches_argv(self) -> None:
        # `|` and `||` cannot survive to argv: the row tail is split on `|`, so
        # the row stops parsing first. Still refused, by an earlier gate — and
        # worth pinning, because "PROOF-SHELL-OPERATOR did not fire" reads as a
        # hole until you know which check caught it instead.
        for operator in ("|", "||"):
            with self.subTest(operator=operator):
                self.assertIn("ROW-SHAPE", _checks(self._plan(f"cmd true {operator} false")))

    def test_command_substitution_is_refused(self) -> None:
        self.assertIn("PROOF-SHELL-OPERATOR", _checks(self._plan("cmd true $(whoami)")))

    def test_a_deliberate_shell_is_allowed(self) -> None:
        # The sanctioned form: the script after -c really is handed to a shell,
        # so it means what it reads.
        self.assertNotIn("PROOF-SHELL-OPERATOR",
                         _checks(self._plan("cmd bash -c 'set -e; true && true'")))

    def test_the_shell_exemption_covers_the_script_only(self) -> None:
        # Bugbot (PR #282, High): exempting the whole argv once `-c` appeared
        # rebuilt the false green inside the sanctioned form — bash runs
        # `true` and takes `&&`, `false` as positional arguments it never runs.
        self.assertIn("PROOF-SHELL-OPERATOR",
                      _checks(self._plan("cmd bash -c 'true' && false")))

    def test_an_operator_glued_to_its_neighbour_is_still_an_operator(self) -> None:
        # Codex (PR #282, P1): `shlex.split` returns `done&&` as one token, so
        # comparing whole tokens saw no offender while accept ran `echo` alone.
        for proof in ("cmd echo done&& false", "cmd echo done>/missing", "cmd true 2>&1"):
            with self.subTest(proof=proof):
                self.assertIn("PROOF-SHELL-OPERATOR", _checks(self._plan(proof)))

    def test_a_quoted_metacharacter_is_a_literal_the_proof_meant_to_pass(self) -> None:
        # The refusal must not swallow arguments that only look like operators.
        self.assertNotIn("PROOF-SHELL-OPERATOR", _checks(self._plan("cmd grep -q 'a&&b' f")))

    def test_an_unparseable_command_line_is_its_own_finding(self) -> None:
        self.assertIn("PROOF-UNPARSEABLE", _checks(self._plan("cmd echo 'unbalanced")))

    def test_a_command_that_exists_nowhere_is_refused_when_the_root_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            found = _checks(self._plan("cmd definitely-not-a-real-binary-xyz"), root=Path(tmp))
            self.assertIn("PROOF-ARGV0", found)

    def test_severity_follows_the_evidence_the_finding_rests_on(self) -> None:
        # Codex (PR #282, P1): this file promises "same text, same findings".
        # A missing in-tree path is answered by the repository, so it blocks
        # anywhere. A bare name is answered by PATH, which is not the plan's
        # text — blocking on it would tie the gate's exit code to whatever the
        # runner happens to have installed.
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = lint.lint_plan(self._plan("cmd tools/gone.sh"), root=Path(tmp))
            missing_name = lint.lint_plan(
                self._plan("cmd definitely-not-a-real-binary-xyz"), root=Path(tmp))
        self.assertEqual(
            ["blocking"], [f["severity"] for f in missing_path if f["check"] == "PROOF-ARGV0"])
        self.assertEqual(
            ["warning"], [f["severity"] for f in missing_name if f["check"] == "PROOF-ARGV0"])

    def test_an_in_tree_path_resolves(self) -> None:
        found = _checks(self._plan("cmd scripts/shadow-lint.py PLAN.md"), root=ROOT)
        self.assertNotIn("PROOF-ARGV0", found)

    def test_a_committed_reading_answers_an_in_tree_path_from_head(self) -> None:
        # Codex (PR #359, P2): accept proves and commits against HEAD, so its
        # reading of argv[0] must come from HEAD too. A committed executable
        # the caller deleted locally is still there in the clean checkout that
        # runs the proof, and blocking on the dirty working tree refused a
        # plan the committed checkout runs fine.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "proof.sh").write_text("exit 0\n", encoding="utf-8")
            commit_fixture(root, "tools/proof.sh")
            (root / "tools" / "proof.sh").unlink()
            plan = self._plan("cmd tools/proof.sh")

            self.assertIn("PROOF-ARGV0", _checks(plan, root=root))
            self.assertNotIn("PROOF-ARGV0", _checks(plan, root=root, committed=True))

    def test_a_committed_reading_refuses_a_path_only_the_working_tree_has(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "kept.sh").write_text("exit 0\n", encoding="utf-8")
            commit_fixture(root, "tools/kept.sh")
            (root / "tools" / "uncommitted.sh").write_text("exit 0\n", encoding="utf-8")
            plan = self._plan("cmd tools/uncommitted.sh")

            self.assertNotIn("PROOF-ARGV0", _checks(plan, root=root))
            self.assertIn("PROOF-ARGV0", _checks(plan, root=root, committed=True))

    def test_a_committed_reading_never_follows_dirty_worktree_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / "tools"
            tools.mkdir()
            proof = tools / "proof.sh"
            kept = tools / "kept.sh"
            proof.write_text("exit 0\n", encoding="utf-8")
            kept.write_text("exit 0\n", encoding="utf-8")
            commit_fixture(root, "tools/proof.sh", "tools/kept.sh")

            proof.unlink()
            proof.symlink_to("/definitely/outside-shadow")
            redirected = tools / "uncommitted.sh"
            redirected.symlink_to("kept.sh")

            committed = self._plan("cmd tools/proof.sh")
            absent = self._plan("cmd tools/uncommitted.sh")
            self.assertNotIn("PROOF-ARGV0", _checks(committed, root=root, committed=True))
            self.assertIn("PROOF-ARGV0", _checks(absent, root=root, committed=True))

    def test_argv0_is_not_guessed_when_the_root_is_unknown(self) -> None:
        # Guessing would turn an unknowable into a false accusation.
        self.assertNotIn("PROOF-ARGV0", _checks(self._plan("cmd scripts/shadow-lint.py PLAN.md")))

    def test_an_interpreter_cannot_hide_a_missing_repository_script(self) -> None:
        # Regression: `node` resolved, so lint stopped there even though the
        # script accept would execute did not exist in the clean checkout.
        nested_split = "python3 scripts/missing.py"
        for _ in range(8):
            nested_split = shlex.join(["env", "-S", nested_split])
        commands = (
            "node scripts/operating-reset/missing.mjs",
            "node missing.mjs",
            "/usr/bin/python3 scripts/missing.py",
            "env MODE=test python3 scripts/missing.py",
            "env -uFOO python3 scripts/missing.py",
            "/usr/bin/env -i python3 scripts/missing.py",
            "env -S 'python3 scripts/missing.py'",
            "env -S 'MODE=x python3 scripts/missing.py'",
            "env -S '-i python3 scripts/missing.py'",
            "env -S 'env MODE=x python3 scripts/missing.py'",
            "env env MODE=x python3 scripts/missing.py",
            "env env env env env env env env python3 scripts/missing.py",
            nested_split,
            "python3 -W ignore scripts/missing.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            for command in commands:
                with self.subTest(command=command):
                    findings = lint.lint_plan(self._plan(f"cmd {command}"), root=Path(tmp))
                    matching = [
                        finding for finding in findings if finding["check"] == "PROOF-SCRIPT"
                    ]
                    self.assertEqual(
                        ["blocking"], [finding["severity"] for finding in matching]
                    )

    def test_an_existing_interpreter_script_and_non_script_modes_remain_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "scripts" / "proof.py"
            script.parent.mkdir()
            script.write_text("raise SystemExit(0)\n", encoding="utf-8")
            commit_fixture(root, "scripts/proof.py")
            self.assertNotIn(
                "PROOF-SCRIPT",
                _checks(self._plan("cmd python3 scripts/proof.py"), root=root),
            )
            self.assertNotIn(
                "PROOF-SCRIPT",
                _checks(self._plan("cmd python3 -m unittest discover"), root=root),
            )
            self.assertNotIn(
                "PROOF-SCRIPT",
                _checks(self._plan("cmd node --version"), root=root),
            )
            for command in (
                "python3 -c 'print(123/4)'",
                "python3 -cprint(1) scripts/missing.py",
                "python3 -munittest discover",
                "node -e 'console.log(123/4)'",
                "node --input-type module --eval 'console.log(1)'",
                "python3 -X pycache_prefix=build/cache scripts/proof.py",
                f"env -C {root} git status --short",
                "env -S 'git --version'",
                "env -S 'MODE=x git --version'",
                "env -S 'env MODE=x git --version'",
            ):
                with self.subTest(command=command):
                    self.assertNotIn(
                        "PROOF-SCRIPT",
                        _checks(self._plan(f"cmd {command}"), root=root),
                    )

            for command in (
                "env -C /tmp python3 scripts/proof.py",
                "env --chdir=/tmp python3 scripts/proof.py",
            ):
                with self.subTest(command=command):
                    self.assertIn(
                        "PROOF-SCRIPT",
                        _checks(self._plan(f"cmd {command}"), root=root),
                    )

    def test_an_interpreter_script_must_be_a_relative_regular_plan_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "check.py"
            script.write_text("raise SystemExit(0)\n", encoding="utf-8")
            commit_fixture(root, "check.py")
            self.assertNotIn(
                "PROOF-SCRIPT", _checks(self._plan("cmd python3 check.py"), root=root)
            )
            self.assertIn(
                "PROOF-SCRIPT", _checks(self._plan(f"cmd python3 {script}"), root=root)
            )
            self.assertIn(
                "PROOF-SCRIPT", _checks(self._plan("cmd python3 ../check.py"), root=root)
            )

    def test_only_a_script_present_as_a_regular_file_in_head_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            script = root / "proof.py"
            script.write_text("raise SystemExit(0)\n", encoding="utf-8")
            command = self._plan("cmd python3 proof.py")
            self.assertIn("PROOF-SCRIPT", _checks(command, root=root))
            subprocess.run(["git", "-C", str(root), "add", "proof.py"], check=True)
            self.assertIn("PROOF-SCRIPT", _checks(command, root=root))
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Shadow Test"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "shadow@example.invalid"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "committed proof"], check=True
            )
            self.assertNotIn("PROOF-SCRIPT", _checks(command, root=root))

    def test_output_paths_are_not_mistaken_for_interpreter_scripts(self) -> None:
        self.assertNotIn(
            "PROOF-SCRIPT",
            _checks(
                self._plan(
                    "cmd python3 scripts/shadow-lint.py --out build/not-created-yet.json"
                ),
                root=ROOT,
            ),
        )

    def test_an_ordinary_proof_is_untouched(self) -> None:
        self.assertNotIn("PROOF-SHELL-OPERATOR", _checks(self._plan("cmd true")))
        self.assertNotIn("PROOF-UNPARSEABLE", _checks(self._plan("cmd true")))


class ThisRepositorysOwnPlanSurvivesTheGate(unittest.TestCase):
    """The regression that would have turned every CI matrix job red.

    argv0 resolution first consulted `shutil.which` and blocked on a miss.
    `PLAN.md` carries `proof: cmd shadow status ...`, and the workflow checks
    out the repository without installing `shadow` — so the gate would have
    failed on a plan that is fine, everywhere except a developer's laptop.

    Pinned against the real file the gate runs on, with a root supplied, which
    is how `main()` calls it. A synthetic fixture would not have caught it.
    """

    def test_the_real_plan_has_no_blocking_finding(self) -> None:
        findings = lint.lint_plan((ROOT / "PLAN.md").read_text(encoding="utf-8"), root=ROOT)
        blocking = [f for f in findings if f["severity"] == "blocking"]
        self.assertEqual(blocking, [], f"the gate would reject this repository's own plan: {blocking}")

    def test_no_finding_depends_on_what_is_installed(self) -> None:
        # An empty PATH is the CI runner at its most bare. Whatever lint says
        # about this plan, it must say the same thing there — otherwise the
        # verdict is about the machine, not the plan.
        import os
        plan = (ROOT / "PLAN.md").read_text(encoding="utf-8")
        before = {(f["check"], f["line"], f["severity"]) for f in lint.lint_plan(plan, root=ROOT)}
        saved = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        try:
            after = {(f["check"], f["line"], f["severity"]) for f in lint.lint_plan(plan, root=ROOT)}
        finally:
            os.environ["PATH"] = saved
        blocking_before = {f for f in before if f[2] == "blocking"}
        blocking_after = {f for f in after if f[2] == "blocking"}
        self.assertEqual(blocking_before, blocking_after,
                         "the gate's exit code changes with the machine's PATH")
