"""
Contract tests for Vidux documentation and tooling.

Inspired by Jeffrey Lee-Chan's /harness plugin contract tests.
The tests ARE the spec. If they fail, fix the docs — not the tests.

Expanded for v1: covers docs, scripts, commands, hooks, enforcement, ingredients.
Runs on stdlib unittest — zero-bootstrap, no pip install needed.
"""

import json
import os
import re
import sqlite3
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

# Root = repo root (two levels up from this test file)
ROOT = Path(__file__).resolve().parent.parent

SKILL = ROOT / "SKILL.md"
DOCTRINE = ROOT / "DOCTRINE.md"
PLAN = ROOT / "PLAN.md"
LOOP = ROOT / "LOOP.md"
ENFORCEMENT = ROOT / "ENFORCEMENT.md"
INGREDIENTS = ROOT / "INGREDIENTS.md"
GITIGNORE = ROOT / ".gitignore"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Valid task line patterns (v1 checkbox + v2 FSM)
TASK_LINE_RE = re.compile(
    r"^- \[( |x|pending|in_progress|completed|blocked)\]"
)


class ViduxContractTests(unittest.TestCase):

    # -----------------------------------------------------------------------
    # SKILL.md contracts
    # -----------------------------------------------------------------------

    def test_skill_has_five_principles(self):
        """SKILL.md must contain all 5 numbered principles under Five Principles."""
        text = _read(SKILL)
        self.assertIn("## Five Principles", text, "SKILL.md missing '## Five Principles' heading")
        for n in range(1, 6):
            self.assertRegex(
                text, rf"###\s+{n}\.",
                f"SKILL.md missing principle #{n}",
            )

    # test_skill_has_two_data_structures — removed in v3 (framing replaced by Five Principles)
    # test_skill_has_advisors — removed in v3 (advisors concept removed)

    def test_skill_is_company_agnostic_layer1(self):
        """Doctrine + architecture sections must have zero company-specific terms."""
        text = _read(SKILL)
        internal_terms = ["Phantom", "Bazel", "snap-bridge", "COF"]
        sections = text.split("## Advisors")
        layer1 = sections[0] if sections else text
        for term in internal_terms:
            hits = [
                (i + 1, line)
                for i, line in enumerate(layer1.splitlines())
                if term in line
            ]
            self.assertEqual(
                len(hits), 0,
                f"Company-specific term '{term}' found in Layer 1: {hits}",
            )

    # test_skill_has_layer_separation — removed in v3 (layer separation removed)

    def test_skill_has_activation_criteria(self):
        """SKILL.md must define when Vidux activates and when it does NOT."""
        text = _read(SKILL)
        self.assertTrue(
            "activates when" in text.lower() or "## Activation" in text,
            "SKILL.md missing activation criteria",
        )
        self.assertTrue(
            "does NOT activate" in text or "does not activate" in text.lower(),
            "SKILL.md missing negative activation criteria",
        )

    def test_skill_cycle_has_worktree_lifecycle_gate(self):
        """SKILL.md core cycle must require worktree classification and closeout."""
        text = _read(SKILL)
        self.assertIn("vidux-worktree-gc.py", text)
        self.assertIn("Worktree lifecycle", text)
        for bucket in [
            "merged_clean",
            "open_pr",
            "dirty",
            "closed_unmerged",
            "unmerged_no_pr",
        ]:
            self.assertIn(bucket, text)

    def test_external_state_sidecars_are_ignored(self):
        """External board state sidecars must stay local even in tracked plan dirs."""
        text = _read(GITIGNORE)
        self.assertIn(".external-state.json", text)
        result = subprocess.run(
            ["git", "check-ignore", "-v", "projects/vidux-browser/.external-state.json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            0,
            result.returncode,
            f"external state sidecar is not ignored\nstdout={result.stdout}\nstderr={result.stderr}",
        )

    # test_skill_has_failure_protocol — removed in v3 (covered by principle 5: Prove it mechanically)

    # -----------------------------------------------------------------------
    # DOCTRINE.md contracts
    # -----------------------------------------------------------------------

    def test_doctrine_has_execution_model(self):
        """DOCTRINE.md must contain the execution model (quick check vs deep work)."""
        text = _read(DOCTRINE)
        self.assertIn("quick check", text.lower())
        self.assertIn("deep work", text.lower())
        self.assertIn("worker", text.lower())

    def test_doctrine_has_pilot_routing(self):
        """DOCTRINE.md must contain the Vidux vs Pilot decision table."""
        text = _read(DOCTRINE)
        self.assertIn("Pilot", text)
        self.assertTrue("Mode A" in text or "Mode B" in text)

    # -----------------------------------------------------------------------
    # PLAN.md contracts
    # -----------------------------------------------------------------------

    REQUIRED_PLAN_SECTIONS = [
        "Purpose", "Evidence", "Constraints", "Decisions",
        "Tasks", "Progress",
    ]

    def test_plan_has_required_sections(self):
        """PLAN.md must have all required sections.

        Open Questions and Surprises were removed from the required list in
        2.9.0 — Progress entries and Decision Log cover those findings. Plans
        may still include them as optional sections.
        """
        text = _read(PLAN)
        for section in self.REQUIRED_PLAN_SECTIONS:
            self.assertTrue(
                re.search(rf"^##\s+{re.escape(section)}", text, re.MULTILINE),
                f"PLAN.md missing required section: {section}",
            )

    def test_plan_evidence_has_citations(self):
        """Every Evidence bullet must contain a [Source: ...] marker."""
        text = _read(PLAN)
        in_evidence = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.match(r"^##\s+Evidence", line):
                in_evidence = True
                continue
            if in_evidence and re.match(r"^##\s+", line):
                break
            if in_evidence and line.startswith("- "):
                self.assertIn(
                    "[Source:", line,
                    f"PLAN.md Evidence line {lineno} missing [Source:] citation",
                )

    def test_plan_tasks_have_valid_status(self):
        """Every task line must use v1 checkboxes or v2 FSM states."""
        # Lines starting with - [Source: or - [DIRECTION] are evidence/metadata,
        # not tasks — skip them even when nested inside ## Tasks subsections.
        evidence_re = re.compile(r"^- \[(Source|DIRECTION)")
        text = _read(PLAN)
        in_tasks = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.match(r"^##\s+Tasks", line):
                in_tasks = True
                continue
            if in_tasks and re.match(r"^##\s+", line):
                break
            if in_tasks and line.startswith("- "):
                if evidence_re.match(line):
                    continue
                self.assertRegex(
                    line, TASK_LINE_RE,
                    f"PLAN.md Tasks line {lineno} not a valid task: {line!r}",
                )

    def test_plan_constraints_have_always_never(self):
        """PLAN.md Constraints must have at least one ALWAYS and one NEVER."""
        text = _read(PLAN)
        in_constraints = False
        has_always = has_never = False
        for line in text.splitlines():
            if re.match(r"^##\s+Constraints", line):
                in_constraints = True
                continue
            if in_constraints and re.match(r"^##\s+", line):
                break
            if in_constraints:
                if "ALWAYS" in line:
                    has_always = True
                if "NEVER" in line:
                    has_never = True
        self.assertTrue(has_always, "PLAN.md Constraints missing ALWAYS rule")
        self.assertTrue(has_never, "PLAN.md Constraints missing NEVER rule")

    # -----------------------------------------------------------------------
    # LOOP.md contracts
    # -----------------------------------------------------------------------

    def test_loop_has_five_steps(self):
        """LOOP.md must contain Step 1 through Step 5."""
        text = _read(LOOP)
        for n in range(1, 6):
            self.assertRegex(text, rf"##\s+Step\s+{n}", f"LOOP.md missing Step {n}")

    def test_loop_requires_worktree_lifecycle_closeout(self):
        """LOOP.md must make worktree classification part of read + complete."""
        text = _read(LOOP)
        self.assertIn("vidux-worktree-gc.py", text)
        self.assertIn("unclassified worktree", text)
        self.assertIn("not complete", text.lower())
        for bucket in [
            "merged_clean",
            "open_pr",
            "dirty",
            "closed_unmerged",
            "unmerged_no_pr",
        ]:
            self.assertIn(bucket, text)

    def test_loop_has_unify_step(self):
        """LOOP.md must mention UNIFY or 'planned vs actual'."""
        text = _read(LOOP)
        self.assertTrue(
            "UNIFY" in text.upper() or "planned vs actual" in text.lower(),
            "LOOP.md missing UNIFY step",
        )

    def test_loop_has_readiness_checklist(self):
        """LOOP.md must have the 10-point plan readiness checklist."""
        text = _read(LOOP)
        self.assertTrue(
            "7/10" in text or "7 to" in text or "Minimum 7" in text,
            "LOOP.md missing 7/10 readiness threshold",
        )
        readiness_match = re.search(r"###\s+Q1.*?(?=###\s+Q2)", text, re.DOTALL)
        self.assertIsNotNone(readiness_match, "LOOP.md missing Q1 readiness section")
        checkboxes = re.findall(r"^- \[ \]", readiness_match.group(), re.MULTILINE)
        self.assertGreaterEqual(len(checkboxes), 5)

    def test_loop_has_escalation_statuses(self):
        """LOOP.md must define all 4 escalation statuses."""
        text = _read(LOOP)
        for status in ["DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"]:
            self.assertIn(status, text, f"LOOP.md missing escalation status: {status}")

    def test_loop_has_stuck_detection(self):
        """LOOP.md must have stuck-loop detection with a 3-cycle threshold."""
        text = _read(LOOP)
        self.assertTrue("stuck" in text.lower() or "Stuck" in text)
        has_three = bool(
            re.search(r"3.*(?:stuck|consecutive)", text, re.IGNORECASE)
            or re.search(r"(?:stuck|consecutive).*3", text, re.IGNORECASE)
        )
        self.assertTrue(has_three, "LOOP.md stuck detection missing '3' threshold")

    # -----------------------------------------------------------------------
    # ENFORCEMENT.md contracts
    # -----------------------------------------------------------------------

    def test_enforcement_has_four_hooks(self):
        """ENFORCEMENT.md must define all 4 lifecycle hooks."""
        text = _read(ENFORCEMENT)
        for hook in ["PreToolUse", "PostToolUse", "Stop", "SessionStart"]:
            self.assertIn(hook, text, f"ENFORCEMENT.md missing hook: {hook}")

    def test_enforcement_hooks_are_prompt_type(self):
        """All Vidux hooks must be type: prompt (nudge, not block)."""
        text = _read(ENFORCEMENT)
        type_matches = re.findall(r'"type":\s*"(\w+)"', text)
        self.assertGreaterEqual(len(type_matches), 4)
        for t in type_matches:
            self.assertIn(t, ("prompt", "command"), f"Unexpected hook type: {t}")

    def test_enforcement_has_gradient(self):
        """ENFORCEMENT.md must describe the enforcement gradient."""
        text = _read(ENFORCEMENT)
        for label in ["Orientation", "Friction", "Reflection", "Obligation"]:
            self.assertIn(label, text, f"Missing gradient label: {label}")

    # -----------------------------------------------------------------------
    # INGREDIENTS.md contracts
    # -----------------------------------------------------------------------

    def test_ingredients_has_ten_patterns(self):
        """INGREDIENTS.md must list 10 adopted patterns."""
        text = _read(INGREDIENTS)
        pattern_headers = re.findall(r"^##\s+\d+\.", text, re.MULTILINE)
        self.assertGreaterEqual(len(pattern_headers), 10)

    def test_ingredients_has_adoption_details(self):
        """Each ingredient must explain what Vidux adopts AND what it does not."""
        text = _read(INGREDIENTS)
        adopt_count = text.lower().count("how vidux adopts")
        not_adopt_count = text.lower().count("what we do not adopt")
        self.assertGreaterEqual(adopt_count, 10)
        self.assertGreaterEqual(not_adopt_count, 10)

    def test_ingredients_has_summary_table(self):
        """INGREDIENTS.md must have a summary table."""
        text = _read(INGREDIENTS)
        self.assertTrue("Summary Table" in text or "| # |" in text)

    # -----------------------------------------------------------------------
    # Scripts contracts
    # -----------------------------------------------------------------------

    SCRIPTS_DIR = ROOT / "scripts"

    def test_scripts_exist_and_executable(self):
        """All vidux scripts must exist and be executable."""
        expected = [
            "vidux-loop.sh", "vidux-checkpoint.sh",
            "vidux-doctor.sh", "vidux-test-all.sh",
        ]
        for name in expected:
            script = self.SCRIPTS_DIR / name
            self.assertTrue(script.exists(), f"Script missing: {name}")
            self.assertTrue(os.access(script, os.X_OK), f"Script not executable: {name}")

    def test_vidux_loop_produces_json(self):
        """vidux-loop.sh must produce valid JSON output."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(PLAN)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue("cycle" in data or "error" in data)

    def test_vidux_loop_no_plan_produces_json(self):
        """vidux-loop.sh with nonexistent plan must produce valid JSON."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), "/tmp/nonexistent-plan.md"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data.get("action") == "create_plan" or "error" in data)

    def test_vidux_loop_exposes_reduce_mode_contract(self):
        """vidux-loop.sh must expose explicit quick-check routing metadata."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(PLAN)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data.get("mode"), "reduce")
        self.assertIn(data.get("next_action"), {"dispatch", "none", "find_work"})

    def test_vidux_loop_routes_pending_work_to_dispatch(self):
        """Reduce mode must recommend dispatch when a runnable task exists."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Build feature [Evidence: src]
            ## Progress
        """)
        self.assertEqual(data["mode"], "reduce")
        self.assertEqual(data["action"], "execute")
        self.assertEqual(data["next_action"], "dispatch")

    def test_vidux_loop_routes_done_plan_to_none(self):
        """Reduce mode must return next_action=none when the queue is empty."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Build feature [Done: 2026-04-07]
            ## Progress
        """)
        self.assertEqual(data["mode"], "reduce")
        self.assertEqual(data["action"], "complete")
        self.assertEqual(data["next_action"], "none")

    def test_vidux_loop_exposes_process_fix_declared(self):
        """Reduce mode must surface [ProcessFix: ...] declarations for the current task."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Fix replay bug [ProcessFix: test] [Evidence: src]
            ## Progress
        """)
        self.assertEqual(data["process_fix_declared"], "test")

    # Tests for vidux-dispatch.sh and vidux-gather.sh removed — scripts deleted in v2.6.0 fleet cleanup

    # -----------------------------------------------------------------------
    # Commands contracts
    # -----------------------------------------------------------------------

    COMMANDS_DIR = ROOT / "commands"

    # Post-2026-04-22: explicit user direction removed the deprecated
    # breadcrumb command after active prompts and docs were migrated.
    # `/vidux` remains the single command entry point for both discipline and
    # automation guidance.
    CORE_COMMANDS = ["vidux.md"]

    def test_commands_exist(self):
        """All vidux commands must exist."""
        for name in self.CORE_COMMANDS:
            self.assertTrue((self.COMMANDS_DIR / name).exists(), f"Command missing: {name}")

    def test_commands_have_frontmatter(self):
        """Each command file must have YAML frontmatter with name and description."""
        for name in self.CORE_COMMANDS:
            text = _read(self.COMMANDS_DIR / name)
            self.assertTrue(text.startswith("---"), f"{name} missing frontmatter")
            end = text.index("---", 3)
            frontmatter = text[3:end]
            self.assertIn("name:", frontmatter, f"{name} frontmatter missing name")
            self.assertIn("description:", frontmatter, f"{name} frontmatter missing description")

    # -----------------------------------------------------------------------
    # Hooks contracts
    # -----------------------------------------------------------------------

    def test_hooks_json_valid(self):
        """hooks/hooks.json must be valid JSON with a hooks array."""
        hooks_file = ROOT / "hooks" / "hooks.json"
        self.assertTrue(hooks_file.exists(), "hooks/hooks.json missing")
        data = json.loads(hooks_file.read_text())
        self.assertIn("hooks", data)
        self.assertIsInstance(data["hooks"], list)
        self.assertGreaterEqual(len(data["hooks"]), 3)

    # -----------------------------------------------------------------------
    # Plugin manifest contracts
    # -----------------------------------------------------------------------

    def test_plugin_manifest_valid(self):
        """plugin.json must be valid JSON with required fields."""
        manifest = ROOT / ".claude-plugin" / "plugin.json"
        self.assertTrue(manifest.exists())
        data = json.loads(manifest.read_text())
        for field in ["name", "version", "description"]:
            self.assertIn(field, data)
        self.assertEqual(data["name"], "vidux")
        self.assertEqual(data["version"], "1.0.0")

    # -----------------------------------------------------------------------
    # Structural integrity
    # -----------------------------------------------------------------------

    def test_all_core_docs_exist(self):
        """All 6 core documentation files must exist."""
        for doc in [SKILL, DOCTRINE, PLAN, LOOP, ENFORCEMENT, INGREDIENTS]:
            self.assertTrue(doc.exists(), f"Core doc missing: {doc.name}")

    def test_skill_mentions_all_core_docs(self):
        """SKILL.md should reference key file artifacts."""
        text = _read(SKILL)
        self.assertIn("PLAN.md", text, "SKILL.md missing PLAN.md reference")
        self.assertIn("evidence/", text, "SKILL.md missing evidence/ reference")
        self.assertIn("investigations/", text, "SKILL.md missing investigations/ reference")

    # -----------------------------------------------------------------------
    # Cross-doc consistency
    # -----------------------------------------------------------------------

    # test_skill_has_fifty_thirty_twenty — removed in v3 (50/30/20 split removed)

    def test_doctrine_principles_match_skill(self):
        """SKILL.md principles must cover plan-first and process-fix concepts."""
        skill = _read(SKILL)
        s_p1 = re.search(r"###\s+1\.\s+Plan.*?(?=^###\s+2\.)", skill, re.DOTALL | re.MULTILINE)
        self.assertIsNotNone(s_p1, "SKILL.md missing principle 1 (Plan first)")
        self.assertIn("source of truth", s_p1.group())
        s_p5 = re.search(r"###\s+5\..*?(?=^---|^###|\Z)", skill, re.DOTALL | re.MULTILINE)
        self.assertIsNotNone(s_p5, "SKILL.md missing principle 5 (Prove it)")
        self.assertIn("process fix", s_p5.group())

    def test_hooks_scripts_exist(self):
        """Every script referenced in hooks/hooks.json must exist on disk."""
        hooks_file = ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_file.read_text())
        for hook in data["hooks"]:
            script_path = hook.get("script")
            self.assertTrue(script_path, f"Hook '{hook.get('name')}' missing 'script'")
            full_path = ROOT / script_path
            self.assertTrue(full_path.exists(), f"Hook script not found: {script_path}")

    def test_checkpoint_script_is_portable(self):
        """vidux-checkpoint.sh must use sedi() and never raw 'sed -i'."""
        text = _read(self.SCRIPTS_DIR / "vidux-checkpoint.sh")
        self.assertIn("sedi()", text)
        lines = text.splitlines()
        raw_sed_hits = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if "sedi()" in line or stripped.startswith("#"):
                continue
            if re.search(r"\bsed\s+-i\b", line):
                raw_sed_hits.append((i, line.strip()))
        self.assertEqual(len(raw_sed_hits), 0, f"Raw 'sed -i' found: {raw_sed_hits}")

    def test_no_internal_terms_in_layer1_docs(self):
        """Layer 1 docs must not contain company-specific terms."""
        internal_terms = ["Phantom", "Bazel", "snap-bridge", "COF", "CameraMusicFeature"]
        layer1_docs = {"LOOP.md": LOOP, "ENFORCEMENT.md": ENFORCEMENT, "DOCTRINE.md": DOCTRINE}
        for doc_name, doc_path in layer1_docs.items():
            text = _read(doc_path)
            for term in internal_terms:
                hits = [
                    (i + 1, line) for i, line in enumerate(text.splitlines()) if term in line
                ]
                self.assertEqual(len(hits), 0, f"'{term}' found in {doc_name}: {hits}")

    # -----------------------------------------------------------------------
    # Config, loop output, project structure, and handoff contracts
    # -----------------------------------------------------------------------

    REPO_ROOT = ROOT.parent.parent

    def test_config_exists_and_valid(self):
        """vidux.config.json must exist and have required keys."""
        config_path = ROOT / "vidux.config.json"
        self.assertTrue(config_path.exists())
        data = json.loads(config_path.read_text(encoding="utf-8"))
        for key in ("version", "plan_store", "defaults"):
            self.assertIn(key, data)
        defaults = data["defaults"]
        self.assertIn("archive_threshold", defaults)
        self.assertIn("context_warning_lines", defaults)
        self.assertIsInstance(defaults["archive_threshold"], int)
        self.assertIsInstance(defaults["context_warning_lines"], int)

    def test_vidux_loop_outputs_hot_cold_fields(self):
        """vidux-loop.sh JSON output must contain hot/cold and context fields."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(PLAN)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        for key in ("hot_tasks", "cold_tasks", "context_warning", "context_note"):
            self.assertIn(key, data)
        self.assertIsInstance(data["hot_tasks"], int)
        self.assertIsInstance(data["cold_tasks"], int)
        self.assertIsInstance(data["context_warning"], bool)
        self.assertIsInstance(data["context_note"], str)

    def test_vidux_loop_outputs_decision_log_fields(self):
        """vidux-loop.sh JSON output must contain decision_log_count, decision_log_warning, decision_log_entries."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(PLAN)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        for key in ("decision_log_count", "decision_log_warning", "decision_log_entries"):
            self.assertIn(key, data, f"Missing field: {key}")
        self.assertIsInstance(data["decision_log_count"], int)
        self.assertIsInstance(data["decision_log_warning"], bool)
        self.assertIsInstance(data["decision_log_entries"], str)

    def test_vidux_loop_decision_log_parsed_from_plan(self):
        """decision_log_count must equal the number of tagged entries when Decision Log section exists."""
        import tempfile, os
        plan_with_dl = textwrap.dedent("""\
            # Test Plan
            ## Decision Log
            - [DIRECTION] [2026-01-01] Do X not Y.
            - [DELETION] [2026-01-02] Removed Z. Reason: no longer needed.
            - [RATE-LIMIT] [2026-01-03] Limit to 3/day.
            ## Tasks
            - [pending] Task 1: do something [Evidence: source]
            ## Progress
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_with_dl)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["decision_log_count"], 3)
            self.assertTrue(data["decision_log_warning"])
            self.assertIn("DIRECTION", data["decision_log_entries"])
            self.assertIn("DELETION", data["decision_log_entries"])
            self.assertIn("RATE-LIMIT", data["decision_log_entries"])
        finally:
            os.unlink(tmp)

    def test_vidux_loop_decision_log_zero_when_absent(self):
        """decision_log_count must be 0 and warning false when no Decision Log section exists."""
        import tempfile, os
        plan_no_dl = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: do something [Evidence: source]
            ## Progress
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_no_dl)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["decision_log_count"], 0)
            self.assertFalse(data["decision_log_warning"])
            self.assertEqual(data["decision_log_entries"], "")
        finally:
            os.unlink(tmp)

    def test_vidux_loop_stuck_when_progress_has_3_entries(self):
        """stuck must be true when Progress section has 3+ entries for the task."""
        import tempfile, os
        # Progress entries must include the full TASK_DESC (with [Evidence:]) because
        # the checkpoint script writes TASK_DESC verbatim — that's what TASK_SHORT matches.
        plan_stuck = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: do something specific here [Evidence: source]
            ## Progress
            - [2026-01-01] Cycle 1: Done: Task 1: do something specific here [Evidence: source]. Next: check plan.
            - [2026-01-02] Cycle 2: Done: Task 1: do something specific here [Evidence: source]. Next: check plan.
            - [2026-01-03] Cycle 3: Done: Task 1: do something specific here [Evidence: source]. Next: check plan.
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_stuck)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertTrue(data["stuck"], "Expected stuck=true for task with 3+ Progress entries")
            self.assertEqual(data["action"], "stuck")
            self.assertIn("3", data["context"])
        finally:
            os.unlink(tmp)

    def test_vidux_loop_not_stuck_when_progress_has_2_entries(self):
        """stuck must be false when Progress section has only 2 entries for the task."""
        import tempfile, os
        plan_two = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: do something specific here [Evidence: source]
            ## Progress
            - [2026-01-01] Cycle 1: Done: Task 1: do something specific here [Evidence: source]. Next: check plan.
            - [2026-01-02] Cycle 2: Done: Task 1: do something specific here [Evidence: source]. Next: check plan.
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_two)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertFalse(data["stuck"], "Expected stuck=false for task with only 2 Progress entries")
        finally:
            os.unlink(tmp)

    def test_vidux_loop_not_stuck_when_no_progress_section(self):
        """stuck must be false when plan has no Progress section."""
        import tempfile, os
        plan_no_prog = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: do something specific here [Evidence: source]
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_no_prog)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertFalse(data["stuck"], "Expected stuck=false when no Progress section")
        finally:
            os.unlink(tmp)

    # -----------------------------------------------------------------------
    # vidux-checkpoint.sh FSM + status contracts
    # -----------------------------------------------------------------------

    def _make_git_plan(self, tmpdir: str, content: str) -> str:
        """Create a minimal git repo with PLAN.md committed; return plan path."""
        import os
        plan = os.path.join(tmpdir, "PLAN.md")
        Path(plan).write_text(content, encoding="utf-8")
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "add", "PLAN.md"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)
        return plan

    def test_checkpoint_handles_v2_pending_task(self):
        """checkpoint.sh must mark [pending] tasks [completed], not just v1 [ ]."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [pending] {task}
                ## Progress
            """))
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task, "done the thing"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            content = Path(plan).read_text(encoding="utf-8")
            self.assertIn("[completed]", content)
            self.assertNotIn("- [pending]", content)

    def test_checkpoint_handles_v2_in_progress_task(self):
        """checkpoint.sh must mark [in_progress] tasks [completed]."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [in_progress] {task}
                ## Progress
            """))
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task, "done the thing"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            content = Path(plan).read_text(encoding="utf-8")
            self.assertIn("[completed]", content)
            self.assertNotIn("- [in_progress]", content)

    def test_checkpoint_status_blocked_marks_task_blocked(self):
        """checkpoint.sh --status blocked must set task to [blocked], not [completed]."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [in_progress] {task}
                ## Progress
            """))
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task,
                 "blocked on external dep", "--status", "blocked", "--blocker", "waiting for API"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            content = Path(plan).read_text(encoding="utf-8")
            self.assertIn("- [blocked]", content)
            self.assertNotIn("[completed]", content)
            self.assertIn("[BLOCKED]", content)

    def test_checkpoint_status_done_with_concerns_adds_progress_note(self):
        """checkpoint.sh --status done_with_concerns must add [concerns noted] to Progress."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [pending] {task}
                ## Progress
            """))
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task,
                 "done but concern", "--status", "done_with_concerns"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            content = Path(plan).read_text(encoding="utf-8")
            self.assertIn("[completed]", content)
            self.assertIn("[concerns noted]", content)

    def test_checkpoint_next_task_detects_v2_pending(self):
        """checkpoint.sh output must identify the next [pending] task (v2 FSM format)."""
        import tempfile
        task1 = "Task 1: first task [Evidence: source]"
        task2 = "Task 2: second task [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [pending] {task1}
                - [pending] {task2}
                ## Progress
            """))
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task1, "done task 1"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            self.assertIn("Task 2", result.stdout)

    def test_checkpoint_idempotent_for_v2_completed(self):
        """checkpoint.sh must skip silently if task is already [completed] (v2)."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [completed] {task} [Done: 2026-01-01]
                ## Progress
            """))
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task, "already done"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("terminal state", result.stdout)

    def test_checkpoint_warns_when_process_fix_artifact_missing(self):
        """Checkpoint must warn when a tagged process fix has no matching repo artifact."""
        import tempfile
        task = "Task 1: Fix replay bug [ProcessFix: test] [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [pending] {task}
                ## Progress
            """))
            Path(tmpdir, "src.py").write_text("print('bugfix')\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task, "fixed replay bug"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            self.assertIn("PROCESS-FIX WARNING", result.stderr)

    def test_checkpoint_accepts_untracked_matching_process_fix_artifact(self):
        """Checkpoint must treat matching untracked files as valid process-fix artifacts."""
        import tempfile
        task = "Task 1: Fix replay bug [ProcessFix: test] [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [pending] {task}
                ## Progress
            """))
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_replay_regression.py").write_text("def test_replay():\n    assert True\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task, "fixed replay bug"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            self.assertNotIn("PROCESS-FIX WARNING", result.stderr)

    # -----------------------------------------------------------------------
    # Task 12: FSM parsing, Q-gating, malformed config, archive idempotency
    # -----------------------------------------------------------------------

    def test_vidux_loop_is_resuming_true_for_in_progress(self):
        """vidux-loop.sh must set is_resuming=true when an [in_progress] task exists."""
        import tempfile, os
        plan_ip = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [in_progress] Task 1: do something specific [Evidence: source]
            ## Progress
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_ip)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data.get("is_resuming"), "Expected is_resuming=true for [in_progress] task")
            self.assertEqual(data.get("action"), "execute")
        finally:
            os.unlink(tmp)

    def test_vidux_loop_q_gating_blocks_task_with_open_qref(self):
        """action must be 'refine' when task desc cites an open Q-ref."""
        import tempfile, os
        plan_q = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: implement something, see Q1 [Evidence: source.md:1]
            ## Open Questions
            - [ ] Q1: Which API version should we target?
            ## Progress
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_q)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertEqual(data.get("action"), "refine",
                             f"Expected action=refine but got {data.get('action')}")
            self.assertGreater(data.get("task_open_questions", 0), 0)
        finally:
            os.unlink(tmp)

    def test_vidux_loop_q_gating_does_not_block_unrelated_qs(self):
        """action must be 'execute' when open Qs exist but are NOT cited in the task desc."""
        import tempfile, os
        plan_unrelated = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: implement the feature [Evidence: source.md:1]
            ## Open Questions
            - [ ] Q1: Some global question not referenced in tasks
            ## Progress
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_unrelated)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertEqual(data.get("action"), "execute",
                             f"Unrelated open Q should not gate task; got action={data.get('action')}")
            self.assertEqual(data.get("task_open_questions", 0), 0)
        finally:
            os.unlink(tmp)

    def test_vidux_loop_malformed_config_uses_defaults(self):
        """vidux-loop.sh must produce valid JSON and warn on stderr when config is malformed."""
        import tempfile, shutil, os
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_subdir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_subdir)
            script_copy = os.path.join(scripts_subdir, "vidux-loop.sh")
            shutil.copy(str(self.SCRIPTS_DIR / "vidux-loop.sh"), script_copy)
            os.chmod(script_copy, 0o755)
            # Malformed config at ../vidux.config.json relative to scripts/
            config_path = os.path.join(tmpdir, "vidux.config.json")
            with open(config_path, "w") as f:
                f.write("{ not valid json !!!")
            plan_path = os.path.join(tmpdir, "PLAN.md")
            with open(plan_path, "w") as f:
                f.write("# Test\n## Tasks\n- [pending] Task 1: do something [Evidence: s]\n## Progress\n")
            result = subprocess.run(
                ["bash", script_copy, plan_path],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"script failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertIn("cycle", data, "Must still produce valid cycle output with defaults")
            self.assertIn("WARNING", result.stderr, "Must emit WARNING to stderr on malformed config")

    def test_checkpoint_archive_idempotent(self):
        """Running --archive twice must not double-archive or corrupt PLAN.md."""
        import tempfile, os
        tasks = "\n".join([
            f"- [completed] Task {i}: something [Done: 2026-01-{i:02d}]"
            for i in range(1, 36)
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, f"# Test Plan\n## Tasks\n{tasks}\n## Progress\n")
            archive = os.path.join(tmpdir, "ARCHIVE.md")
            # First run
            r1 = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, "--archive"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(r1.returncode, 0, f"First archive failed: {r1.stderr}")
            content_after_first = Path(plan).read_text(encoding="utf-8")
            archive_size_after_first = Path(archive).stat().st_size if os.path.exists(archive) else 0
            # Second run
            r2 = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, "--archive"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(r2.returncode, 0, f"Second archive failed: {r2.stderr}")
            content_after_second = Path(plan).read_text(encoding="utf-8")
            archive_size_after_second = Path(archive).stat().st_size if os.path.exists(archive) else 0
            self.assertEqual(content_after_first, content_after_second,
                             "PLAN.md changed on second --archive run (not idempotent)")
            self.assertEqual(archive_size_after_first, archive_size_after_second,
                             "ARCHIVE.md grew on second --archive run (double-archived)")
            idempotent_signals = ["Already archived", "Nothing to archive"]
            self.assertTrue(
                any(sig in r2.stdout for sig in idempotent_signals),
                f"Expected idempotent message in second run, got: {r2.stdout!r}"
            )

    def test_checkpoint_archive_counts_v2_completed_tasks(self):
        """archive mode must include [completed] (v2) tasks in archive count, not just [x] (v1)."""
        import tempfile, os
        tasks = "\n".join([
            f"- [completed] Task {i}: something [Done: 2026-01-{i:02d}]"
            for i in range(1, 36)
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, f"# Test Plan\n## Tasks\n{tasks}\n## Progress\n")
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, "--archive"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"archive failed: {result.stderr}")
            self.assertIn("Archived 5", result.stdout)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "ARCHIVE.md")))

    # test_skill_has_configuration_section — removed in v3 (configuration section removed)

    def test_plan_store_resolvable(self):
        """resolve-plan-store.sh must exist and resolve_plan_store must return a path."""
        resolver = self.SCRIPTS_DIR / "lib" / "resolve-plan-store.sh"
        self.assertTrue(resolver.exists(), "scripts/lib/resolve-plan-store.sh missing")
        result = subprocess.run(
            ["bash", "-c", f'VIDUX_ROOT="{ROOT}" source "{resolver}" && resolve_plan_store'],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, f"resolve_plan_store failed: {result.stderr}")
        self.assertTrue(len(result.stdout.strip()) > 0, "resolve_plan_store returned empty")

    def test_checkpoint_outcome_useful_appears_in_progress(self):
        """checkpoint.sh --outcome useful must write 'outcome=useful' into the Progress entry."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, f"# Test Plan\n## Tasks\n- [pending] {task}\n## Progress\n")
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task,
                 "task done", "--outcome", "useful"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            with open(plan) as f:
                content = f.read()
            self.assertIn("outcome=useful", content)

    def test_checkpoint_outcome_invalid_rejects_with_nonzero_exit(self):
        """checkpoint.sh --outcome <invalid> must exit non-zero."""
        import tempfile
        task = "Task 1: do something specific [Evidence: source]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, f"# Test Plan\n## Tasks\n- [pending] {task}\n## Progress\n")
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task,
                 "task done", "--outcome", "invalid_value"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertNotEqual(result.returncode, 0, "expected non-zero exit for invalid --outcome")


    # ===== v2.3.0 NEW TESTS: Dependency Matcher Fixes ===== #

    def _run_loop_on(self, plan_text):
        """Helper: write plan_text to a temp file, run vidux-loop.sh, return parsed JSON."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(textwrap.dedent(plan_text))
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            return json.loads(result.stdout)
        finally:
            os.unlink(tmp)

    def test_dep_none_does_not_block(self):
        """[Depends: none] must not block — fixes false-positive on 'none' sentinel."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Build feature X [Evidence: src] [Depends: none]
            - [pending] Task 2: Build feature Y [Evidence: src] [Depends: none]
            ## Progress
        """)
        self.assertFalse(data["blocked"])

    def test_dep_none_case_insensitive(self):
        """[Depends: None] and [Depends: NONE] must not block."""
        for variant in ["None", "NONE"]:
            data = self._run_loop_on(f"""\
                # Test Plan
                ## Tasks
                - [pending] Task 1: Build feature [Evidence: src] [Depends: {variant}]
                ## Progress
            """)
            self.assertFalse(data["blocked"], f"[Depends: {variant}] incorrectly blocked")

    def test_dep_self_match_excluded(self):
        """Task must not self-match on its own [Depends:] text."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Setup infrastructure
            - [pending] Task 2: Build widget [Evidence: src] [Depends: Task 1]
            ## Progress
        """)
        self.assertFalse(data["blocked"])

    def test_dep_numeric_partial_match_safe(self):
        """[Depends: 1.4] must not match Task 14 or text containing '2.4'."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1.4: Build payment gateway
            - [pending] Task 2: Scale to 2.4x [Evidence: src] [Depends: 1.4]
            - [pending] Task 14: Unrelated work
            ## Progress
        """)
        self.assertFalse(data["blocked"])

    def test_dep_legitimate_blocking(self):
        """Task with pending dependency must be blocked."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Setup infrastructure
            - [pending] Task 2: Build on infra [Evidence: src] [Depends: 1]
            ## Progress
        """)
        # Task 1 is first pending, so it gets selected (not Task 2)
        self.assertIn("Task 1", data["task"])

    def test_dep_dotted_id_blocking(self):
        """[Depends: 0.3] must correctly block when Task 0.3 is pending."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 0.7: Review all designs [Evidence: src] [Depends: 0.3]
            - [pending] Task 0.3: Design the matcher [Evidence: src]
            ## Progress
        """)
        self.assertTrue(data["blocked"])
        self.assertIn("0.3", data["context"])

    def test_dep_multi_dep_partial_resolution(self):
        """Multi-dep list must block if any dep is unresolved."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 0.3: Design dep matcher
            - [completed] Task 0.5: Design hygiene
            - [completed] Task 0.6: Design D6
            - [pending] Task 0.7: Review all [Evidence: src] [Depends: 0.3, 0.4, 0.5, 0.6]
            - [pending] Task 0.4: Design contradiction
            ## Progress
        """)
        self.assertTrue(data["blocked"])
        self.assertIn("0.4", data["context"])

    def test_dep_unstructured_tasks_degrade_gracefully(self):
        """Tasks without 'Task N:' prefix must not false-block."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Fix the login bug
            - [pending] Add password reset [Evidence: src] [Depends: Fix the login bug]
            ## Progress
        """)
        self.assertFalse(data["blocked"])

    def test_dep_v1_checkbox_compat(self):
        """v1 [x] completed tasks must be excluded from pending set."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [x] Task 1: Setup infrastructure
            - [ ] Task 2: Build widget [Evidence: src] [Depends: 1]
            ## Progress
        """)
        self.assertFalse(data["blocked"])

    # ===== v2.3.0 NEW TESTS: DL-STUCK-TAG-BLIND Fix ===== #

    def test_dl_stuck_entries_parsed(self):
        """[STUCK] entries must appear in decision_log_count and decision_log_entries."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Decision Log
            - [STUCK] [2026-04-05] Task stuck for 3+ cycles. Auto-blocked.
            - [DIRECTION] [2026-04-05] Do not skip planning.
            ## Tasks
            - [pending] Task 1: Build feature [Evidence: src]
            ## Progress
        """)
        self.assertEqual(data["decision_log_count"], 2)
        self.assertTrue(data["decision_log_warning"])
        self.assertIn("STUCK", data["decision_log_entries"])
        self.assertIn("DIRECTION", data["decision_log_entries"])

    # ===== v2.3.0 NEW TESTS: Contradiction Detection ===== #

    def test_contradiction_fields_present(self):
        """JSON output must contain contradiction_warning, contradiction_matches, contradicts_tag."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Build feature [Evidence: src]
            ## Progress
        """)
        self.assertIn("contradiction_warning", data)
        self.assertIn("contradiction_matches", data)
        self.assertIn("contradicts_tag", data)

    def test_contradiction_keyword_overlap_fires(self):
        """Keyword overlap >=2 with DELETION entry must set contradiction_warning=true."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Decision Log
            - [DELETION] [2026-04-05] Removed legacy --verbose flag. Do not re-add.
            ## Tasks
            - [pending] Task 1: Re-add --verbose flag [Evidence: src]
            ## Progress
        """)
        self.assertTrue(data["contradiction_warning"])
        self.assertIn("verbose", data["contradiction_matches"].lower())
        self.assertIn("flag", data["contradiction_matches"].lower())

    def test_contradiction_no_overlap_below_threshold(self):
        """0-1 keyword overlap must not trigger contradiction_warning."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Decision Log
            - [DELETION] [2026-04-05] Removed payment retry logic.
            ## Tasks
            - [pending] Task 1: Add payment webhook handler [Evidence: src]
            ## Progress
        """)
        self.assertFalse(data["contradiction_warning"])

    def test_contradiction_explicit_tag(self):
        """Task with [Contradicts: DL-1] must set contradiction_warning=true."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Decision Log
            - [DIRECTION] [2026-04-05] Use SQLite.
            ## Tasks
            - [pending] Task 1: Migrate to Postgres [Contradicts: DL-1] [Evidence: src]
            ## Progress
        """)
        self.assertTrue(data["contradiction_warning"])
        self.assertIn("Contradicts", data["contradicts_tag"])

    def test_contradiction_rate_limit_skipped(self):
        """RATE-LIMIT entries must not trigger keyword overlap."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Decision Log
            - [RATE-LIMIT] [2026-04-05] Deploy limited to 3 per day.
            ## Tasks
            - [pending] Task 1: Deploy the new feature today [Evidence: src]
            ## Progress
        """)
        self.assertFalse(data["contradiction_warning"])

    def test_contradiction_no_dl_section(self):
        """Plans without Decision Log must have all contradiction fields false/empty."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Build feature [Evidence: src]
            ## Progress
        """)
        self.assertFalse(data["contradiction_warning"])
        self.assertEqual(data["contradiction_matches"], "")
        self.assertEqual(data["contradicts_tag"], "")

    def test_contradiction_direction_overlap(self):
        """DIRECTION entry overlap must trigger warning."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Decision Log
            - [DIRECTION] [2026-04-05] Chose SQLite over Postgres for storage.
            ## Tasks
            - [pending] Task 1: Migrate storage to Postgres [Evidence: src]
            ## Progress
        """)
        self.assertTrue(data["contradiction_warning"])

    # ===== v2.3.0 NEW TESTS: Doctor Script ===== #

    def test_doctor_script_exists_and_executable(self):
        """vidux-doctor.sh must exist and be executable."""
        script = self.SCRIPTS_DIR / "vidux-doctor.sh"
        self.assertTrue(script.exists(), "vidux-doctor.sh missing")
        self.assertTrue(os.access(script, os.X_OK), "vidux-doctor.sh not executable")

    def test_doctor_json_output_is_valid(self):
        """vidux-doctor.sh --json must produce valid JSON with required fields."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-doctor.sh"), "--json"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        for key in ("version", "pass", "total", "checks"):
            self.assertIn(key, data)
        self.assertIsInstance(data["checks"], list)
        self.assertGreaterEqual(len(data["checks"]), 7)

    def test_doctor_checks_have_required_fields(self):
        """Each check in doctor JSON output must have id, category, and status."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-doctor.sh"), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        for check in data["checks"]:
            self.assertIn("id", check)
            self.assertIn("category", check)
            self.assertIn("status", check)
            self.assertIn(check["status"], ("pass", "warn", "block"))

    def test_doctor_repo_flag_rescopes_project_scan(self):
        """--repo must scan the target repo's projects/, not the script checkout's projects/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            plan = repo / "projects" / "test-conflict" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(textwrap.dedent("""
                # Conflict Plan

                ## Tasks
                <<<<<<< HEAD
                - [pending] Task 1: A [Evidence: fixture]
                =======
                - [pending] Task 1: B [Evidence: fixture]
                >>>>>>> feature
            """).lstrip(), encoding="utf-8")

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-doctor.sh"), "--json", "--repo", str(repo)],
                capture_output=True, text=True, timeout=60,
            )
            data = json.loads(result.stdout)
            merge_check = next(
                check for check in data["checks"] if check["id"] == "plan_merge_conflicts"
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(merge_check["status"], "block")

    def test_doctor_reduce_harness_scope_warns_on_dispatch_cron_prompt(self):
        """Doctor must flag active cron prompts that schedule deep Vidux work without a reduce contract."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / "projects").mkdir()
            auto_dir = repo / "automations" / "vidux-v230-planner"
            auto_dir.mkdir(parents=True)
            (auto_dir / "automation.toml").write_text(textwrap.dedent("""
                version = 1
                id = "vidux-v230-planner"
                kind = "cron"
                status = "ACTIVE"
                prompt = "Use [$vidux](/tmp/vidux/SKILL.md) to continuously improve Vidux itself. Build new verification, write new contract tests, and implement the fix in the same scheduled run."
            """).lstrip(), encoding="utf-8")

            result = subprocess.run(
                [
                    "bash",
                    str(self.SCRIPTS_DIR / "vidux-doctor.sh"),
                    "--json",
                    "--repo",
                    str(repo),
                    "--automations-dir",
                    str(repo / "automations"),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
            check = next(
                check for check in data["checks"] if check["id"] == "reduce_harness_scope"
            )

            self.assertEqual(check["status"], "warn")
            self.assertEqual(check["count"], 1)
            self.assertEqual(check["details"][0]["automation_id"], "vidux-v230-planner")
            self.assertIn("missing_reduce_contract", check["details"][0]["issues"])

    def test_doctor_reduce_harness_scope_allows_explicit_reduce_prompt(self):
        """Doctor must pass when a cron prompt stays in reduce mode and hands deep work to dispatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / "projects").mkdir()
            auto_dir = repo / "automations" / "vidux-reduce"
            auto_dir.mkdir(parents=True)
            (auto_dir / "automation.toml").write_text(textwrap.dedent("""
                version = 1
                id = "vidux-reduce"
                kind = "cron"
                status = "ACTIVE"
                prompt = "Use [$vidux](/tmp/vidux/SKILL.md) in reduce mode. Keep this run brief, stay under 2 minutes, inspect the plan, and return next_action=dispatch when real work exists."
            """).lstrip(), encoding="utf-8")

            result = subprocess.run(
                [
                    "bash",
                    str(self.SCRIPTS_DIR / "vidux-doctor.sh"),
                    "--json",
                    "--repo",
                    str(repo),
                    "--automations-dir",
                    str(repo / "automations"),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
            check = next(
                check for check in data["checks"] if check["id"] == "reduce_harness_scope"
            )

            self.assertEqual(check["status"], "pass")
            self.assertEqual(check["count"], 0)

    def test_doctor_reduce_harness_scope_ignores_dispatch_body_after_reduce_gate(self):
        """Doctor must not flag valid REDUCE harnesses just because later sections mention implementation work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / "projects").mkdir()
            auto_dir = repo / "automations" / "acme-web"
            auto_dir.mkdir(parents=True)
            (auto_dir / "automation.toml").write_text(textwrap.dedent("""
                version = 1
                id = "acme-web"
                kind = "cron"
                status = "ACTIVE"
                prompt = "Use [$vidux](/tmp/vidux/SKILL.md), [$pilot](/tmp/pilot/SKILL.md), and [$figma-implement-design](/tmp/figma/SKILL.md) for the Acme web identity overhaul.\n\nREDUCE gate (run FIRST, before any other work):\n1. Run: bash /tmp/vidux-loop.sh /tmp/projects/acme-web/PLAN.md\n2. Read the JSON output. If next_action is \\\"none\\\", exit immediately.\n4. If next_action is \\\"dispatch\\\": proceed to full execution below.\nBudget: steps 1-3 must complete in under 60 seconds.\n\nAuthority\n- /tmp/projects/acme-web/PLAN.md\n\nExecution\n- Implement the next queued landing-page improvement after dispatch.\n- Use $figma-implement-design when a node is available.\n\nCheckpoint\n- Keep 3 notes max."
            """).lstrip(), encoding="utf-8")

            result = subprocess.run(
                [
                    "bash",
                    str(self.SCRIPTS_DIR / "vidux-doctor.sh"),
                    "--json",
                    "--repo",
                    str(repo),
                    "--automations-dir",
                    str(repo / "automations"),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
            check = next(
                check for check in data["checks"] if check["id"] == "reduce_harness_scope"
            )

            self.assertEqual(check["status"], "pass")
            self.assertEqual(check["count"], 0)

    def test_doctor_stalled_active_automation_rows_warns_on_overdue_zero_run_rows(self):
        """Doctor must flag active scheduler rows that are overdue and still have zero runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / "projects").mkdir()
            auto_dir = repo / "automations"
            auto_dir.mkdir()
            db = repo / "codex-dev.db"

            conn = sqlite3.connect(db)
            conn.execute(textwrap.dedent("""
                CREATE TABLE automations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    next_run_at INTEGER,
                    last_run_at INTEGER,
                    cwds TEXT NOT NULL DEFAULT '[]',
                    rrule TEXT NOT NULL DEFAULT 'FREQ=HOURLY;INTERVAL=24;BYMINUTE=0',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    model TEXT,
                    reasoning_effort TEXT
                )
            """))
            conn.execute(textwrap.dedent("""
                CREATE TABLE automation_runs (
                    automation_id TEXT,
                    created_at INTEGER
                )
            """))

            now_ms = int(time.time() * 1000)
            overdue_ms = now_ms - (20 * 60 * 1000)
            conn.execute(
                """
                INSERT INTO automations (
                    id, name, prompt, status, next_run_at, last_run_at,
                    cwds, rrule, created_at, updated_at, model, reasoning_effort
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "stalled-auto",
                    "Stalled Automation",
                    "Keep the loop healthy.",
                    "ACTIVE",
                    overdue_ms,
                    None,
                    "[]",
                    "FREQ=HOURLY;INTERVAL=1;BYMINUTE=0,30",
                    now_ms,
                    now_ms,
                    "gpt-5.4",
                    "xhigh",
                ),
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [
                    "bash",
                    str(self.SCRIPTS_DIR / "vidux-doctor.sh"),
                    "--json",
                    "--repo",
                    str(repo),
                    "--automations-dir",
                    str(auto_dir),
                    "--automation-db",
                    str(db),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
            check = next(
                check for check in data["checks"] if check["id"] == "stalled_active_automation_rows"
            )

            self.assertEqual(check["status"], "warn")
            self.assertEqual(check["count"], 1)
            self.assertEqual(check["details"][0]["id"], "stalled-auto")
            self.assertFalse(check["details"][0]["repo_backed"])

    def test_ledger_bimodal_distribution_ignores_non_automation_noise(self):
        """Repo-wide bimodal stats must ignore raw codex live/stop noise without automation IDs."""
        ledger_entries = [
            {
                "ts": "2026-04-07T00:00:00Z",
                "repo": "vidux",
                "automation_id": "vidux-v230-planner",
                "automation_name": "Vidux v2.3.0 Planner",
                "agent_id": "codex/run-good",
                "event": "live",
                "summary": "run start",
            },
            {
                "ts": "2026-04-07T00:01:00Z",
                "repo": "vidux",
                "automation_id": "vidux-v230-planner",
                "automation_name": "Vidux v2.3.0 Planner",
                "agent_id": "codex/run-good",
                "event": "stop",
                "summary": "run end",
            },
            {
                "ts": "2026-04-07T00:02:00Z",
                "repo": "vidux",
                "agent_id": "codex/noise",
                "event": "live",
                "summary": "noise start",
            },
            {
                "ts": "2026-04-07T00:06:00Z",
                "repo": "vidux",
                "agent_id": "codex/noise",
                "event": "stop",
                "summary": "noise end",
            },
        ]

        data = self._run_ledger_bimodal_distribution(ledger_entries)
        self.assertEqual(data["totals"]["total_runs"], 1)
        self.assertEqual(data["totals"]["mid"], 0)
        self.assertEqual(data["bimodal_score"], 100)
        self.assertEqual(len(data["per_automation"]), 1)
        self.assertEqual(data["per_automation"][0]["automation_id"], "vidux-v230-planner")

    def test_ledger_bimodal_distribution_collapses_live_snapshots_into_one_run(self):
        """Multiple live snapshots from one automation agent must classify as one run."""
        ledger_entries = [
            {
                "ts": "2026-04-07T00:00:00Z",
                "repo": "vidux",
                "automation_id": "vidux-v230-planner",
                "automation_name": "Vidux v2.3.0 Planner",
                "agent_id": "codex/run-mid",
                "event": "live",
                "summary": "snapshot 1",
            },
            {
                "ts": "2026-04-07T00:03:00Z",
                "repo": "vidux",
                "automation_id": "vidux-v230-planner",
                "automation_name": "Vidux v2.3.0 Planner",
                "agent_id": "codex/run-mid",
                "event": "live",
                "summary": "snapshot 2",
            },
            {
                "ts": "2026-04-07T00:06:00Z",
                "repo": "vidux",
                "automation_id": "vidux-v230-planner",
                "automation_name": "Vidux v2.3.0 Planner",
                "agent_id": "codex/run-mid",
                "event": "stop",
                "summary": "snapshot 3",
            },
            {
                "ts": "2026-04-07T00:10:00Z",
                "repo": "vidux",
                "automation_id": "vidux-endurance",
                "automation_name": "vidux-endurance",
                "agent_id": "codex/run-quick",
                "event": "live",
                "summary": "quick 1",
            },
            {
                "ts": "2026-04-07T00:11:00Z",
                "repo": "vidux",
                "automation_id": "vidux-endurance",
                "automation_name": "vidux-endurance",
                "agent_id": "codex/run-quick",
                "event": "stop",
                "summary": "quick 2",
            },
        ]

        data = self._run_ledger_bimodal_distribution(ledger_entries)
        planner = next(
            item for item in data["per_automation"] if item["automation_id"] == "vidux-v230-planner"
        )
        self.assertEqual(planner["total"], 1)
        self.assertEqual(planner["mid"], 1)
        self.assertEqual(data["totals"]["total_runs"], 2)
        self.assertEqual(data["totals"]["mid"], 1)
        self.assertEqual(data["totals"]["quick"], 1)

    def _run_ledger_bimodal_distribution(self, entries):
        """Helper: run ledger_bimodal_distribution against a temp ledger fixture."""
        with tempfile.NamedTemporaryFile("w", delete=False) as ledger_file:
            for entry in entries:
                ledger_file.write(json.dumps(entry) + "\n")
            ledger_path = ledger_file.name

        env = os.environ.copy()
        env["VIDUX_LEDGER_FILE"] = ledger_path
        try:
            result = subprocess.run(
                [
                    "bash",
                    "-lc",
                    (
                        f"source {self.SCRIPTS_DIR / 'lib' / 'ledger-query.sh'} "
                        "&& ledger_bimodal_distribution vidux 168"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        finally:
            os.unlink(ledger_path)


    # ===== v2.4.0: Exit Criteria Hook (Task 11.4) ===== #

    def test_exit_criteria_fields_present_in_loop_output(self):
        """vidux-loop.sh must include exit_criteria_met and exit_criteria_pending in JSON output."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 1: Build feature [Evidence: src]
            ## Progress
        """)
        self.assertIn("exit_criteria_met", data)
        self.assertIn("exit_criteria_pending", data)

    def test_exit_criteria_met_when_no_section(self):
        """Plans without ## Exit Criteria must default to exit_criteria_met=true, pending=0."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Done [Evidence: src]
            ## Progress
        """)
        self.assertTrue(data["exit_criteria_met"])
        self.assertEqual(data["exit_criteria_pending"], 0)

    def test_exit_criteria_met_when_all_checked(self):
        """All checked exit criteria must yield exit_criteria_met=true."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Done [Evidence: src]
            ## Exit Criteria
            - [x] All tests pass
            - [x] No TODOs in src/
            ## Progress
        """)
        self.assertTrue(data["exit_criteria_met"])
        self.assertEqual(data["exit_criteria_pending"], 0)

    def test_exit_criteria_pending_when_unchecked(self):
        """Unchecked exit criteria must yield exit_criteria_met=false and correct pending count."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Done [Evidence: src]
            ## Exit Criteria
            - [x] All tests pass
            - [ ] No TODOs in src/
            - [ ] Coverage > 80%
            ## Progress
        """)
        self.assertFalse(data["exit_criteria_met"])
        self.assertEqual(data["exit_criteria_pending"], 2)

    def test_exit_criteria_blocks_done_signal(self):
        """When all tasks are done but exit criteria unmet, action must NOT be 'complete'."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Done [Evidence: src]
            ## Exit Criteria
            - [ ] All tests pass
            ## Progress
        """)
        self.assertNotEqual(data["action"], "complete")
        self.assertEqual(data["type"], "exit_criteria_pending")
        self.assertEqual(data["next_action"], "dispatch")

    def test_exit_criteria_allows_done_when_all_met(self):
        """When all tasks done AND all exit criteria checked, action must be 'complete'."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [completed] Task 1: Done [Evidence: src]
            ## Exit Criteria
            - [x] All tests pass
            - [x] No TODOs in src/
            ## Progress
        """)
        self.assertEqual(data["action"], "complete")
        self.assertEqual(data["type"], "done")
        self.assertEqual(data["next_action"], "none")

    # Tests for vidux-dispatch.sh exit criteria removed — script deleted in v2.6.0

    # test_skill_has_exit_criteria_in_plan_template — removed in v3 (plan template simplified)

    # ===================================================================== #
    # Phase 10-12 contract tests
    # ===================================================================== #

    # -----------------------------------------------------------------------
    # DOCTRINE.md: 12 principles
    # -----------------------------------------------------------------------

    def test_doctrine_has_twelve_principles(self):
        """DOCTRINE.md must contain all 12 numbered principles."""
        text = _read(DOCTRINE)
        for n in range(1, 13):
            self.assertTrue(
                re.search(rf"^## {n}\.", text, re.MULTILINE),
                f"DOCTRINE.md missing principle #{n}",
            )

    def test_doctrine_has_loop_discipline_section(self):
        """DOCTRINE.md must contain the Loop Discipline section covering principles 10-12."""
        text = _read(DOCTRINE)
        self.assertIn("Loop Discipline", text)
        self.assertIn("Principles 10-12", text)

    def test_doctrine_has_quick_check_deep_work_section(self):
        """DOCTRINE.md must contain the Quick Check / Deep Work section."""
        text = _read(DOCTRINE)
        self.assertIn("Quick Check / Deep Work", text)
        self.assertIn("quick check", text.lower())
        self.assertIn("deep work", text.lower())

    # -----------------------------------------------------------------------
    # Ledger library contracts (sourced, not executed)
    # -----------------------------------------------------------------------

    LEDGER_LIB_DIR = ROOT / "scripts" / "lib"

    def test_ledger_lib_scripts_exist(self):
        """All 3 ledger library scripts must exist."""
        for name in ["ledger-config.sh", "ledger-emit.sh", "ledger-query.sh"]:
            lib = self.LEDGER_LIB_DIR / name
            self.assertTrue(lib.exists(), f"Ledger lib script missing: {name}")

    def test_ledger_lib_scripts_are_sourceable(self):
        """Ledger library scripts must be sourceable (not directly executable)."""
        for name in ["ledger-config.sh", "ledger-emit.sh", "ledger-query.sh"]:
            lib = self.LEDGER_LIB_DIR / name
            text = _read(lib)
            self.assertIn(
                "Source this file; do not execute directly",
                text,
                f"{name} missing source-only guard comment",
            )

    def test_ledger_config_exports_expected_vars(self):
        """ledger-config.sh must export LEDGER_FILE, LEDGER_DIR, LEDGER_AVAILABLE."""
        text = _read(self.LEDGER_LIB_DIR / "ledger-config.sh")
        for var in ["LEDGER_FILE", "LEDGER_DIR", "LEDGER_AVAILABLE"]:
            self.assertIn(var, text, f"ledger-config.sh missing export: {var}")

    def test_ledger_config_has_double_source_guard(self):
        """ledger-config.sh must guard against double-sourcing."""
        text = _read(self.LEDGER_LIB_DIR / "ledger-config.sh")
        self.assertIn("_VIDUX_LEDGER_CONFIG_LOADED", text)

    def test_ledger_emit_provides_expected_functions(self):
        """ledger-emit.sh must define the expected emitter functions."""
        text = _read(self.LEDGER_LIB_DIR / "ledger-emit.sh")
        for func in [
            "vidux_emit",
            "vidux_emit_loop_start",
            "vidux_emit_loop_end",
            "vidux_emit_checkpoint",
            "vidux_emit_plan_modified",
            "vidux_emit_fleet_health",
        ]:
            self.assertIn(func, text, f"ledger-emit.sh missing function: {func}")

    def test_ledger_emit_has_double_source_guard(self):
        """ledger-emit.sh must guard against double-sourcing."""
        text = _read(self.LEDGER_LIB_DIR / "ledger-emit.sh")
        self.assertIn("_VIDUX_LEDGER_EMIT_LOADED", text)

    def test_ledger_query_provides_expected_functions(self):
        """ledger-query.sh must define the expected query functions."""
        text = _read(self.LEDGER_LIB_DIR / "ledger-query.sh")
        for func in [
            "ledger_bimodal_distribution",
            "ledger_automation_runs",
            "ledger_handoff_gaps",
            "ledger_fleet_health",
            "ledger_recent_activity",
            "ledger_conflict_check",
        ]:
            self.assertIn(func, text, f"ledger-query.sh missing function: {func}")

    def test_ledger_query_has_double_source_guard(self):
        """ledger-query.sh must guard against double-sourcing."""
        text = _read(self.LEDGER_LIB_DIR / "ledger-query.sh")
        self.assertIn("_VIDUX_LEDGER_QUERY_LOADED", text)

    def test_ledger_config_sources_without_error(self):
        """ledger-config.sh must source cleanly without producing errors."""
        result = subprocess.run(
            ["bash", "-lc", f"source {self.LEDGER_LIB_DIR / 'ledger-config.sh'}"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"ledger-config.sh source failed: {result.stderr}")

    def test_ledger_emit_sources_without_error(self):
        """ledger-emit.sh must source cleanly (it chains to ledger-config.sh)."""
        result = subprocess.run(
            ["bash", "-lc", f"source {self.LEDGER_LIB_DIR / 'ledger-emit.sh'}"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"ledger-emit.sh source failed: {result.stderr}")

    def test_ledger_query_sources_without_error(self):
        """ledger-query.sh must source cleanly (it chains to ledger-config.sh)."""
        result = subprocess.run(
            ["bash", "-lc", f"source {self.LEDGER_LIB_DIR / 'ledger-query.sh'}"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"ledger-query.sh source failed: {result.stderr}")

    # -----------------------------------------------------------------------
    # # vidux-prune.sh contracts — removed (script deleted in v2.6.0)
    # -----------------------------------------------------------------------

    # def test_prune_script_exits_with_usage_on_no_args(self): — removed (script deleted in v2.6.0)
    # def test_prune_pressure_produces_json(self): — removed (script deleted in v2.6.0)
    # def test_prune_pressure_simulate_is_safe(self): — removed (script deleted in v2.6.0)
    # def test_prune_has_five_subcommands(self): — removed (script deleted in v2.6.0)
    # -----------------------------------------------------------------------
    # # vidux-fleet-quality.sh contracts — removed (script deleted in v2.6.0)
    # -----------------------------------------------------------------------

    # Tests for vidux-fleet-quality.sh removed — script deleted in v2.6.0

    # -----------------------------------------------------------------------
    # Phase 10-12 commands: frontmatter + required sections
    #
    # REMOVED 2026-04-17 (commit 8c1f593, Phase 10 of PLAN.md):
    #   - test_dashboard_command_*  (vidux-dashboard.md deleted)
    #   - test_manager_command_*    (vidux-manager.md deleted)
    #   - test_fleet_command_*      (vidux-fleet.md deleted)
    # Former /vidux-dashboard, /vidux-fleet, /vidux-manager commands merged
    # into /vidux Part 2 + references/automation.md. See PLAN.md Phase 10
    # Decision Log [DELETION] 2026-04-17.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Cross-doc: SKILL.md must reference Phase 10-12 concepts
    # -----------------------------------------------------------------------

    # test_skill_has_quick_check_terminology — removed in v3 (quick check/deep work simplified)

    # test_skill_has_bimodal_concept — removed in v3 (moved to fleet ops guide)

    def test_skill_has_self_extend_with_brake(self):
        """SKILL.md principle 4 must describe self-extension with a stopping rule."""
        text = _read(SKILL)
        self.assertTrue(
            "brake" in text.lower() or "stop polishing" in text.lower(),
            "SKILL.md missing 'brake' or 'stop polishing' in principle 4",
        )

    # ===================================================================== #
    # Phase 12: Continuous Feedback Loop contracts                          #
    # ===================================================================== #

    # test_dispatch_merge_gate_mode removed — vidux-dispatch.sh deleted in v2.6.0

    def test_loop_auto_pause_fields(self):
        """vidux-loop.sh JSON must include auto_pause_recommended and unproductive_streak."""
        data = self._run_loop_on("""\
            # Test Plan

            ## Tasks
            - [pending] Task 1: test [Evidence: fixture]

            ## Progress
            - [2026-04-07] Cycle 1: Done: something. Next: check plan.
        """)
        self.assertIn("auto_pause_recommended", data)
        self.assertIn("unproductive_streak", data)
        self.assertIsInstance(data["auto_pause_recommended"], bool)
        self.assertIsInstance(data["unproductive_streak"], int)

    def test_loop_bimodal_gate_fields(self):
        """vidux-loop.sh JSON must include bimodal_score and bimodal_gate."""
        data = self._run_loop_on("""\
            # Test Plan

            ## Tasks
            - [pending] Task 1: test [Evidence: fixture]

            ## Progress
        """)
        self.assertIn("bimodal_score", data)
        self.assertIn("bimodal_gate", data)
        self.assertIn(data["bimodal_gate"], ["pass", "blocked"])

    def test_loop_reduce_contract_fields(self):
        """vidux-loop.sh JSON must include reduce_contract with read_only and budget."""
        data = self._run_loop_on("""\
            # Test Plan

            ## Tasks
            - [pending] Task 1: test [Evidence: fixture]

            ## Progress
        """)
        self.assertIn("reduce_contract", data)
        contract = data["reduce_contract"]
        self.assertTrue(contract["read_only"])
        self.assertEqual(contract["max_budget_seconds"], 120)
        self.assertIn("code_changes", contract["forbidden"])

    def test_codex_db_lib_exists(self):
        """scripts/lib/codex-db.sh must exist and be sourceable."""
        lib = ROOT / "scripts" / "lib" / "codex-db.sh"
        self.assertTrue(lib.exists(), "codex-db.sh missing")
        # Verify it sources without error (double-source guard)
        result = subprocess.run(
            ["bash", "-c", f"source '{lib}' && source '{lib}' && echo ok"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertIn("ok", result.stdout)

    def test_queue_jsonl_lib_exists(self):
        """scripts/lib/queue-jsonl.sh must exist and be sourceable."""
        lib = ROOT / "scripts" / "lib" / "queue-jsonl.sh"
        self.assertTrue(lib.exists(), "queue-jsonl.sh missing")
        result = subprocess.run(
            ["bash", "-c", f"source '{lib}' && source '{lib}' && echo ok"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertIn("ok", result.stdout)

    # def test_witness_script_exists_and_executable(self): — removed (script deleted in v2.6.0)
    def test_hooks_include_lifecycle_hooks(self):
        """hooks.json must include beforeTask and afterTask lifecycle hooks."""
        hooks_file = ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_file.read_text())
        events = [h["event"] for h in data["hooks"]]
        self.assertIn("beforeTask", events, "Missing beforeTask hook")
        self.assertIn("afterTask", events, "Missing afterTask hook")

    def test_config_has_backpressure_section(self):
        """vidux.config.json must have backpressure section with bimodal thresholds."""
        config = json.loads((ROOT / "vidux.config.json").read_text())
        self.assertIn("backpressure", config)
        bp = config["backpressure"]
        self.assertIn("bimodal_critical_threshold", bp)
        self.assertIn("bimodal_warning_threshold", bp)
        self.assertGreater(bp["bimodal_warning_threshold"], bp["bimodal_critical_threshold"])

    def test_config_has_pruning_section(self):
        """vidux.config.json must have pruning section."""
        config = json.loads((ROOT / "vidux.config.json").read_text())
        self.assertIn("pruning", config)
        self.assertIn("stale_blocked_days", config["pruning"])
        self.assertIn("max_concurrent_worktrees", config["pruning"])

    # test_manager_has_self_extension_metric REMOVED 2026-04-17 (Phase 10).
    # vidux-manager.md was deleted; self-extension/recursive-overload concept
    # preserved in /vidux Part 2 as "self-extend with a brake" (Principle 4).


    # --- Phase 13.6-13.10: Coverage gap tests -------------------------------- #

    # def test_witness_produces_valid_json(self): — removed (script deleted in v2.6.0)
    # def test_witness_fleet_grade_is_letter(self): — removed (script deleted in v2.6.0)
    def test_skill_has_compound_tasks_section(self):
        """SKILL.md must document compound tasks (nesting model) and investigations.

        Section was renamed in 2.10.0 from 'Compound tasks and sub-plans' to
        'When a task needs an investigation (the only nesting vidux allows)'.
        """
        text = _read(ROOT / "SKILL.md")
        self.assertIn("task needs an investigation", text, "SKILL.md missing nesting/investigation subsection")
        self.assertIn("compound task", text.lower(), "SKILL.md missing compound-task reference")
        self.assertIn("Investigation", text, "SKILL.md missing 'Investigation' reference")
        self.assertIn("Impact Map", text, "SKILL.md missing 'Impact Map'")
        self.assertIn("Fix Spec", text, "SKILL.md missing 'Fix Spec'")

    def test_skill_investigation_template_has_required_sections(self):
        """SKILL.md investigation template must have all required sections."""
        text = _read(ROOT / "SKILL.md")
        for section in ["Reporter Says", "Root Cause", "Impact Map", "Fix Spec", "Gate"]:
            self.assertIn(section, text, f"Investigation template missing: {section}")

    def test_skill_principle2_mentions_context_loss(self):
        """SKILL.md Principle 2 must address context loss and disk-based re-read."""
        text = _read(ROOT / "SKILL.md")
        self.assertTrue(
            "context will be lost" in text.lower(),
            "SKILL.md missing 'Context will be lost' in principle 2",
        )
        self.assertTrue(
            "re-read plan" in text.lower() or "re-read PLAN.md" in text,
            "SKILL.md missing re-read guidance in principle 2",
        )
        self.assertTrue(
            "never trust summaries" in text.lower() or "never trust summaries or memory" in text.lower(),
            "SKILL.md missing 'Never trust summaries' in principle 2",
        )

    def test_doctrine_principle7_mentions_investigation(self):
        """DOCTRINE.md Principle 7 must mention investigation and nested."""
        text = _read(ROOT / "DOCTRINE.md")
        self.assertIn("investigation", text.lower())
        self.assertIn("nested", text.lower())

    def test_doctrine_principle8_mentions_harness(self):
        """DOCTRINE.md Principle 8 must mention harness and stateless."""
        text = _read(ROOT / "DOCTRINE.md")
        self.assertIn("harness", text.lower())
        self.assertIn("stateless", text.lower())

    def test_doctrine_principle9_mentions_subagent(self):
        """DOCTRINE.md Principle 9 must mention subagent and coordinator."""
        text = _read(ROOT / "DOCTRINE.md")
        self.assertIn("subagent", text.lower())
        self.assertIn("coordinator", text.lower())

    def test_loop_empty_tasks_produces_valid_json(self):
        """vidux-loop.sh with empty Tasks section must produce valid JSON."""
        import tempfile, os
        plan_text = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            ## Decision Log
            ## Progress
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_text)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(result.stdout)
            self.assertIn("mode", data)
            self.assertIn("hot_tasks", data)
            self.assertEqual(data["hot_tasks"], 0)
        finally:
            os.unlink(tmp)

    @unittest.skipIf(os.environ.get("VIDUX_TEST_ALL_RUNNING"), "skip when called from vidux-test-all.sh to avoid infinite recursion")
    def test_test_all_json_output(self):
        """vidux-test-all.sh --json must produce valid JSON with sections array."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-test-all.sh"), "--json"],
            capture_output=True, text=True, timeout=900,
        )
        data = json.loads(result.stdout)
        self.assertIn("overall", data)
        self.assertIn("sections", data)
        self.assertIsInstance(data["sections"], list)
        self.assertGreater(len(data["sections"]), 0)


    # === Phase 14: Fleet Restructuring Contract Tests ===

    def test_doctor_cadence_runtime_check_exists(self):
        """vidux-doctor.sh must have a cadence_runtime check (CHECK 12)."""
        content = (self.SCRIPTS_DIR / "vidux-doctor.sh").read_text()
        self.assertIn("cadence_runtime", content)
        self.assertIn("_check_cadence_runtime", content)

    def test_doctor_total_checks_at_least_14(self):
        """vidux-doctor.sh --json must report at least 14 total checks."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-doctor.sh"), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        self.assertGreaterEqual(data["total"], 14)

    def test_quick_check_gate_in_doctrine(self):
        """DOCTRINE.md must document the quick check gate pattern."""
        content = (ROOT / "DOCTRINE.md").read_text()
        self.assertIn("quick check", content.lower())
        self.assertIn("gate", content.lower())

    def test_quick_check_gate_in_best_practices(self):
        """best-practices.md must have the Quick check gate pattern section."""
        bp = ROOT / "guides" / "vidux" / "best-practices.md"
        if bp.exists():
            content = bp.read_text()
            self.assertIn("Quick Check Gate", content)

    def test_compat_lib_exists(self):
        """scripts/lib/compat.sh must exist for OS portability."""
        self.assertTrue((self.SCRIPTS_DIR / "lib" / "compat.sh").exists())

    def test_compat_lib_has_required_functions(self):
        """compat.sh must define file_mtime_epoch, dir_newest_mtime, parse_iso_epoch."""
        content = (self.SCRIPTS_DIR / "lib" / "compat.sh").read_text()
        for fn in ["file_mtime_epoch", "dir_newest_mtime", "parse_date_epoch", "parse_iso_epoch"]:
            self.assertIn(fn, content, f"Missing function: {fn}")

    # def test_prune_uses_compat(self): — removed (script deleted in v2.6.0)
    # def test_witness_uses_compat(self): — removed (script deleted in v2.6.0)
    # === Phase 15: Fleet Intelligence Contract Tests ===

    def test_loop_has_circuit_breaker_fields(self):
        """vidux-loop.sh JSON output must include circuit_breaker fields."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(ROOT / "PLAN.md")],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertIn("circuit_breaker", data)
        self.assertIn("circuit_breaker_streak", data)
        self.assertIn(data["circuit_breaker"], ["open", "closed"])

    def test_loop_circuit_breaker_blocks_dispatch_when_open(self):
        """vidux-loop.sh must block dispatch when circuit breaker is open."""
        import tempfile, os
        # Plan with idle progress entries (no shipping signals)
        plan_text = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [pending] Do something [Evidence: test]
            ## Decision Log
            ## Progress
            - [2026-04-07] Cycle 3: Assessed state. No changes needed.
            - [2026-04-07] Cycle 2: Reviewed plan. Nothing to do.
            - [2026-04-07] Cycle 1: Read plan. All good.
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_text)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)
            self.assertEqual(data["circuit_breaker"], "open")
            self.assertEqual(data["next_action"], "none")
        finally:
            os.unlink(tmp)


    def test_gate_pattern_documented(self):
        """Gate pattern must be documented in harness guide or doctrine."""
        harness = _read(ROOT / "guides" / "harness.md")
        doctrine = _read(DOCTRINE)
        combined = harness + doctrine
        self.assertIn("gate", combined.lower())
        self.assertIn("worker", combined.lower())


    def test_midzone_kill_in_doctrine(self):
        """DOCTRINE.md Principle 10 must include dispatch-side mid-zone kill."""
        text = _read(ROOT / "DOCTRINE.md")
        self.assertIn("mid-zone kill", text.lower())
        self.assertIn("3+ minutes", text)

    def test_midzone_kill_in_doctrine(self):
        """DOCTRINE.md must include mid-zone kill guidance."""
        text = _read(DOCTRINE)
        self.assertIn("mid-zone", text.lower())
        self.assertIn("deep work", text.lower())


if __name__ == "__main__":
    unittest.main()
