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

    def test_argv0_is_not_guessed_when_the_root_is_unknown(self) -> None:
        # Guessing would turn an unknowable into a false accusation.
        self.assertNotIn("PROOF-ARGV0", _checks(self._plan("cmd scripts/shadow-lint.py PLAN.md")))

    def test_an_ordinary_proof_is_untouched(self) -> None:
        self.assertNotIn("PROOF-SHELL-OPERATOR", _checks(self._plan("cmd true")))
        self.assertNotIn("PROOF-UNPARSEABLE", _checks(self._plan("cmd true")))
