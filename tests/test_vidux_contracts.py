"""
Contract tests for Vidux documentation and tooling.

Inspired by Jeffrey Lee-Chan's /harness plugin contract tests.
The tests ARE the spec. If they fail, fix the docs — not the tests.

Expanded for v1: covers docs, scripts, commands, hooks, enforcement, ingredients.
Runs on stdlib unittest — zero-bootstrap, no pip install needed.
"""

import http.client
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import textwrap
import time
import unittest
from datetime import datetime, timedelta, timezone
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
AMP_SKILL = Path.home() / "Development" / "ai-leo" / "skills" / "amp" / "SKILL.md"
PRIVATE_AUTO_SKILL = Path.home() / "Development" / "ai-leo" / "skills" / "auto" / "SKILL.md"
SHARED_AUTO_SKILL = Path.home() / "Development" / "ai" / "skills" / "auto" / "SKILL.md"
ACTIVE_AUTO_SKILL = Path.home() / ".ai" / "skills-active" / "auto" / "SKILL.md"
FLOW_SKILL = Path.home() / "Development" / "ai" / "skills" / "leo-flow" / "SKILL.md"
FLOW_YAML = Path.home() / "Development" / "ai" / "skills" / "leo-flow" / "flow.yaml"
FLOW_CLI = Path.home() / "Development" / "ai" / "skills" / "leo-flow" / "scripts" / "leo-flow"
SKILLBOX_SKILL = Path.home() / "Development" / "ai" / "skills" / "skillbox" / "SKILL.md"
GLM_SKILL = Path.home() / "Development" / "ai-leo" / "skills" / "glm" / "SKILL.md"
GROK_SKILL = Path.home() / "Development" / "ai-leo" / "skills" / "grok" / "SKILL.md"
CODEX_SKILL = Path.home() / "Development" / "ai-leo" / "skills" / "codex" / "SKILL.md"
GOAL_NAV_PROMPT = ROOT / "prompts" / "goal-navigation-control-plane.prompt.md"


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
        internal_terms = ["Phantom", "Bazel", "internal-bridge-tool", "COF"]
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

    def test_plan_rolls_up_current_goal_navigation_receipts(self):
        """PLAN.md must expose the current goal-navigation worker contract."""
        text = _read(PLAN)
        for phrase in [
            "5.3.0fr Model-worker selector bug/docs audit",
            "5.3.0fs Model-worker intent gate",
            "5.3.0ft Bounded model-worker writes",
            "5.3.0fv Parent-backed writable model-worker foldback",
            "5.3.0fw Codex high-fast model-worker skill",
            "bounded writable GLM/Grok/Codex workers",
            "parent/lead foldback",
            "Phase 5.3.0fn-fw",
            "`/auto` is intentionally deleted",
            "5.3.1 stays parked until Resplit PR-overlap ownership is re-proven",
        ]:
            self.assertIn(phrase, text)

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

    def test_phase5_goal_names_publish_propagation_fields(self):
        """The active PR architecture goal must route recovery through plan plus ledger."""
        text = _read(PLAN)
        phase5 = text[text.index("### Phase 5: Ready-PR architecture") : text.index("### Phase 6:")]
        for stale_phrase in [
            "Each PR carries: automation id, plan task id, last pushed diff, and the resume point.",
            "PRs are the **durable source-of-truth for in-flight work**",
            "`gh pr list` is the recovery manifest",
        ]:
            self.assertNotIn(stale_phrase, phase5)
        for phrase in [
            "PRs are transport/review handles for branch-backed in-flight work",
            "durable recovery starts from the owning PLAN.md plus matching publish ledger row",
            "`gh pr list` to find work that still needs review or nursing",
            "Each PR body carries: automation id, plan path, plan task id, proof, publish ledger eid",
            "handoff status",
            "files claimed",
            "last pushed diff",
            "resume point",
        ]:
            self.assertIn(phrase, phase5)

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

    def test_enforcement_uses_plan_ledger_checkpoint_and_crash_recovery(self):
        """ENFORCEMENT.md must not teach commit-first checkpoint or crash recovery."""
        text = _read(ENFORCEMENT)

        for stale_phrase in [
            "Every session must leave behind a structured progress entry",
            "Committed all changes with message format: vidux: [summary]",
            "Committed all changes.",
            "If uncommitted work exists from a crashed session, commit it first.",
            "The plan is truth. Code is derived from it.",
        ]:
            self.assertNotIn(stale_phrase, text)

        for phrase in [
            "structured plan/ledger packet",
            "publish ledger row for shipped work with summary, task id, plan path, proof, handoff_status, files claimed, claims, and resume",
            "Committed only after the plan/ledger packet exists, and only if code changed",
            "files and matching ledger row",
            "record recovery path in owning plan plus ledger handoff before any commit, push, cleanup, or overwrite",
            "PLAN.md is the queue/planning authority",
            "matching publish ledger rows prove shipped work",
        ]:
            self.assertIn(phrase, text)

    # -----------------------------------------------------------------------
    # INGREDIENTS.md contracts
    # -----------------------------------------------------------------------

    def test_ingredients_has_ten_patterns(self):
        """INGREDIENTS.md must list 10 adopted patterns."""
        text = _read(INGREDIENTS)
        pattern_rows = re.findall(r"^\|\s*\d+\s*\|", text, re.MULTILINE)
        self.assertGreaterEqual(len(pattern_rows), 10)

    def test_ingredients_has_adoption_details(self):
        """The patterns table must carry Adopt and Skip columns."""
        text = _read(INGREDIENTS)
        self.assertIn("| Adopt | Skip |", text)

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
        self.assertEqual(data.get("mode"), "reduce")
        self.assertEqual(data.get("type"), "missing_plan")
        self.assertEqual(data.get("action"), "create_plan")
        self.assertEqual(data.get("hot_tasks"), 0)
        self.assertEqual(data.get("runnable_tasks"), 0)
        self.assertIn("handoff_contract", data)
        self.assertFalse(data["handoff_contract"]["handoff_required"])
        self.assertEqual(data["handoff_contract"]["required_fields"], ["plan_path"])
        self.assertIn("reduce_contract", data)
        self.assertTrue(data["reduce_contract"]["read_only"])
        self.assertIn("file_writes", data["reduce_contract"]["forbidden"])

    def test_vidux_loop_exposes_reduce_mode_contract(self):
        """vidux-loop.sh must expose explicit quick-check routing metadata."""
        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(PLAN)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data.get("mode"), "reduce")
        self.assertIn(data.get("next_action"), {"dispatch", "none", "find_work", "refresh_proof", "surface_switch"})

    def test_vidux_status_keeps_blocked_plans_visible(self):
        """Default status must not classify blocked work as shipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mixed = root / "mixed"
            shipped = root / "shipped"
            mixed.mkdir()
            shipped.mkdir()
            (mixed / "PLAN.md").write_text(textwrap.dedent("""\
                # Mixed Plan
                ## Tasks
                - [completed] Done: shipped part
                - [blocked] Gate: waiting on external proof
                ## Progress
            """), encoding="utf-8")
            (shipped / "PLAN.md").write_text(textwrap.dedent("""\
                # Shipped Plan
                ## Tasks
                - [completed] Done: shipped all work
                ## Progress
            """), encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--json"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-status.py failed: {result.stderr}")
            data = json.loads(result.stdout)
            rows = data["tied"] + data["other"]
            names = {row["short"] for row in rows}
            self.assertIn("mixed", names)
            self.assertNotIn("shipped", names)
            mixed_row = next(row for row in rows if row["short"] == "mixed")
            self.assertEqual(mixed_row["completed"], 1)
            self.assertEqual(mixed_row["blocked"], 1)

            rendered = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--focus", "mixed"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(rendered.returncode, 0, f"vidux-status.py failed: {rendered.stderr}")
            self.assertIn("mixed", rendered.stdout)
            self.assertIn(" 50%", rendered.stdout)
            self.assertIn("[1b]", rendered.stdout)

    def test_vidux_status_recognizes_fsm_extension_tags_as_not_shipped(self):
        """Round-3 panel finding (code-quality-scripts lens): [in_review]/
        [verify]/[merged] -- SKILL.md's own documented status FSM extension
        tags -- didn't match TASK_LINE_RE at all, so tasks carrying them were
        silently excluded from every count. A plan with all its live work
        sitting in [in_review] reported pending=0/in_progress=0/blocked=0 and
        misreported as 100% shipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_dir = root / "fsm-extension"
            plan_dir.mkdir()
            (plan_dir / "PLAN.md").write_text(textwrap.dedent("""\
                # FSM Extension Plan
                ## Tasks
                - [completed] Task A: shipped part
                - [in_review] Task B: PR open, awaiting CI + review acks
                - [verify] Task C: generator finished, awaiting evaluator verdict
                - [merged] Task D: merged to trunk, not yet Findable
                ## Progress
            """), encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--json"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-status.py failed: {result.stderr}")
            data = json.loads(result.stdout)
            rows = data["tied"] + data["other"]
            row = next(row for row in rows if row["short"] == "fsm-extension")
            self.assertEqual(row["completed"], 1)
            # All three FSM extension tags fold into in_progress -- none of
            # them are terminal, so none may silently vanish from the count.
            self.assertEqual(row["in_progress"], 3)
            self.assertEqual(row["pending"], 0)
            self.assertEqual(row["blocked"], 0)
            self.assertEqual(row["completed"] + row["in_progress"], 4)
            names = {row["short"] for row in rows}
            self.assertIn("fsm-extension", names)

    def test_vidux_status_counts_prose_blocked_pending_rows(self):
        """Status counts must match reducer-visible explicit blocker prose."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_dir = root / "prose-blocked"
            plan_dir.mkdir()
            (plan_dir / "PLAN.md").write_text(textwrap.dedent("""\
                # Prose Blocked Plan
                ## Tasks
                - [completed] Wave 2 complete [Evidence: fixture]
                - [pending] 5.3.1 Remaining automations. [Depends: Wave 2 complete - but resplit gh pr create overlap issue must be solved first]
                - [pending] 5.3.2 Validate PR manifest [Depends: 5.3.1]
                - [pending] Negative wording row [Evidence: fixture] [Depends: review complete; not blocked by review bots] [ETA: 1h]
                ## Progress
            """), encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--json"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-status.py failed: {result.stderr}")
            data = json.loads(result.stdout)
            rows = data["tied"] + data["other"]
            row = next(row for row in rows if row["short"] == "prose-blocked")
            self.assertEqual(row["completed"], 1)
            self.assertEqual(row["blocked"], 1)
            self.assertEqual(row["pending"], 2)
            self.assertEqual(row["eta_hours"], 1.0)
            self.assertIn("blocked", row["flags"])
            self.assertIn("Remaining automations", " ".join(row["blocked_tasks"]))
            self.assertIn("Validate PR manifest", " ".join(row["pending_tasks"]))

            rendered = subprocess.run(
                [
                    "python3",
                    str(self.SCRIPTS_DIR / "vidux-status.py"),
                    "--root",
                    str(root),
                    "--focus",
                    "prose-blocked",
                ],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(rendered.returncode, 0, f"vidux-status.py failed: {rendered.stderr}")
            self.assertIn("prose-blocked", rendered.stdout)
            self.assertIn("[2p/1b]", rendered.stdout)

    def test_vidux_status_skips_fixture_and_example_plans(self):
        """Status board must not route agents into docs examples or test fixtures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_paths = {
                "real-project/PLAN.md": "- [pending] R1: real work [Evidence: fixture]",
                "examples/drift-smoke/PLAN.md": "- [pending] E1: example work [Evidence: fixture]",
                "browser/tests/fixtures/fake-dev-root/proj-alpha/PLAN.md": (
                    "- [in_progress] F1: fixture work [Evidence: fixture]"
                ),
            }
            for relative, task in plan_paths.items():
                plan = root / relative
                plan.parent.mkdir(parents=True, exist_ok=True)
                plan.write_text(textwrap.dedent(f"""\
                    # Test Plan
                    ## Tasks
                    {task}
                    ## Progress
                """), encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--json"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-status.py failed: {result.stderr}")
            data = json.loads(result.stdout)
            rows = data["tied"] + data["other"]
            names = {row["short"] for row in rows}

            self.assertIn("real-project", names)
            self.assertNotIn("examples/drift-smoke", names)
            self.assertNotIn("browser/tests/fixtures/fake-dev-root/proj-alpha", names)

    def test_vidux_status_prefers_task_claims_board_over_stale_task_stubs(self):
        """Status board must use the live task Claims board when old stubs linger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stale = root / "stale-child"
            mega = root / "mega-summary"
            stale.mkdir()
            mega.mkdir()
            (stale / "PLAN.md").write_text(textwrap.dedent("""\
                # Stale Child Plan
                ## Tasks
                - [pending] T1: stale stub
                - [pending] T2: stale stub
                - [pending] T3: stale stub

                ## Claims board
                | Task | Status | Owner | Updated |
                |---|---|---|---|
                | T1: shipped slice | [completed] | codex | 2026-06-02 |
                | T2: live remaining slice [ETA: 2h] | [pending] | — | 2026-06-02 |
                | T3: parked slice | [blocked] | — | 2026-06-02 |

                ## Progress
            """), encoding="utf-8")
            (mega / "PLAN.md").write_text(textwrap.dedent("""\
                # Mega Summary
                ## Claims board
                | Sub-project | Status | Owner | Updated |
                |---|---|---|---|
                | child-a | [pending] | — | 2026-06-02 |

                ## Progress
            """), encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--json"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-status.py failed: {result.stderr}")
            data = json.loads(result.stdout)
            rows = data["tied"] + data["other"]
            names = {row["short"] for row in rows}
            self.assertIn("stale-child", names)
            self.assertNotIn("mega-summary", names)

            stale_row = next(row for row in rows if row["short"] == "stale-child")
            self.assertEqual(stale_row["pending"], 1)
            self.assertEqual(stale_row["completed"], 1)
            self.assertEqual(stale_row["blocked"], 1)
            self.assertEqual(stale_row["eta_hours"], 2.0)
            self.assertIn("blocked", stale_row["flags"])
            self.assertIn("live remaining slice", " ".join(stale_row["pending_tasks"]))
            self.assertIn("parked slice", " ".join(stale_row["blocked_tasks"]))

    def test_vidux_status_labels_scan_root_plan_as_repo_name(self):
        """Repo-root scans must keep the root PLAN.md in the focus bucket."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "vidux"
            root.mkdir()
            (root / "PLAN.md").write_text(textwrap.dedent("""\
                # Vidux Plan
                ## Tasks
                - [pending] Root task: keep working [Evidence: fixture]
                ## Progress
            """), encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(self.SCRIPTS_DIR / "vidux-status.py"),
                    "--root",
                    str(root),
                    "--focus",
                    "vidux",
                    "--json",
                ],
                capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 0, f"vidux-status.py failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertEqual([row["short"] for row in data["tied"]], ["vidux"])
            self.assertEqual(data["other"], [])

    def test_vidux_status_all_labels_tracked_not_active_count(self):
        """Rendered --all output must not call shipped rows active work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            active = root / "active"
            shipped = root / "shipped"
            active.mkdir()
            shipped.mkdir()
            (active / "PLAN.md").write_text(textwrap.dedent("""\
                # Active Plan
                ## Tasks
                - [pending] A1: keep working [Evidence: fixture]
                ## Progress
            """), encoding="utf-8")
            (shipped / "PLAN.md").write_text(textwrap.dedent("""\
                # Shipped Plan
                ## Tasks
                - [completed] S1: done [Evidence: fixture]
                ## Progress
            """), encoding="utf-8")

            default = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(default.returncode, 0, f"vidux-status.py failed: {default.stderr}")
            self.assertIn("Other tracked plans  (1 active)", default.stdout)

            all_rows = subprocess.run(
                ["python3", str(self.SCRIPTS_DIR / "vidux-status.py"), "--root", str(root), "--all"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(all_rows.returncode, 0, f"vidux-status.py failed: {all_rows.stderr}")
            self.assertIn("Other tracked plans  (2 tracked)", all_rows.stdout)
            self.assertNotIn("Other tracked plans  (2 active)", all_rows.stdout)

    def test_vidux_status_help_matches_current_scan_scope(self):
        """CLI help must not describe status as only projects/* plans."""
        current_scope = "Print plan status across operational PLAN.md files"
        top = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(top.returncode, 0, top.stderr)
        self.assertIn(current_scope, top.stdout)
        self.assertNotIn("projects/*/PLAN.md", top.stdout)

        status = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "help", "status"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("usage: vidux status", status.stdout)
        self.assertIn("--root <path>", status.stdout)
        self.assertIn("--focus <repo>...", status.stdout)
        self.assertIn("--all includes tracked rows", status.stdout)
        self.assertIn("--json prints the", status.stdout)
        self.assertNotIn("projects/*/PLAN.md", status.stdout)

        completion = _read(ROOT / "scripts" / "vidux-completion.sh")
        self.assertIn(current_scope, completion)
        self.assertNotIn("Print active-plan status across projects/*/PLAN.md", completion)
        completion_flag_needles = {
            "bash": ("--root", "--focus", "--all", "--json"),
            "zsh": ("--root", "--focus", "--all", "--json"),
            "fish": ("-l root", "-l focus", "-l all", "-l json"),
        }
        for shell, flag_needles in completion_flag_needles.items():
            rendered_completion = subprocess.run(
                [str(ROOT / "scripts" / "vidux-completion.sh"), shell],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(
                rendered_completion.returncode,
                0,
                f"{shell} completion failed: {rendered_completion.stderr}",
            )
            for flag in flag_needles:
                self.assertIn(
                    flag,
                    rendered_completion.stdout,
                    f"{shell} completion missing status flag {flag}",
                )

        status_spec = _read(ROOT / "commands" / "vidux-status.md")
        self.assertIn("Find operational `PLAN.md` files under the selected root", status_spec)
        self.assertIn("Default output hides empty and fully shipped plans", status_spec)
        self.assertIn("vidux status --json", status_spec)
        self.assertNotIn("~/Development/vidux/projects/*/PLAN.md", status_spec)
        self.assertNotIn("No other arguments", status_spec)

    def test_vidux_cli_gives_authored_error_for_broken_vidux_root(self):
        """Round-3 panel finding (error-messages-ux lens): every subcommand
        exec's straight into python3/bash/awk against VIDUX_ROOT with no
        preflight, so a broken/misdirected VIDUX_ROOT leaked a raw
        interpreter error ("python3: can't open file ...", "awk: can't open
        file ...") instead of a vidux-authored message naming the actual
        problem."""
        with tempfile.TemporaryDirectory() as tmpdir:
            broken_root = Path(tmpdir) / "not-a-vidux-checkout"
            broken_root.mkdir()
            env = os.environ.copy()
            env["VIDUX_ROOT"] = str(broken_root)

            for args in (["status"], ["--version"], ["init", "demo"]):
                result = subprocess.run(
                    [str(ROOT / "bin" / "vidux"), *args],
                    capture_output=True, text=True, timeout=10, env=env,
                )
                self.assertEqual(result.returncode, 127, result.stderr)
                self.assertIn("does not look like a vidux checkout", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("can't open file", result.stderr)

            # help/-h stay exempt -- pure static text, no filesystem access,
            # must still work even from a broken VIDUX_ROOT.
            help_result = subprocess.run(
                [str(ROOT / "bin" / "vidux"), "--help"],
                capture_output=True, text=True, timeout=10, env=env,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("vidux — plan-first control plane", help_result.stdout)

    def test_doctor_passes_resolved_vidux_root_through_to_doctor_cli(self):
        """Round-1 open-source panel finding: `bin/vidux doctor` exec'd
        vidux-doctor-cli.sh without exporting the VIDUX_ROOT it had already
        resolved. vidux-doctor-cli.sh falls back to a hardcoded
        $HOME/Development/vidux when VIDUX_ROOT isn't in its environment, so
        running `vidux doctor` from any other checkout (a worktree, a
        differently-named clone, CI) silently validated the WRONG checkout.
        Proven here by running a copy of bin/vidux from a fake checkout that
        deliberately omits scripts/vidux-config.py: if VIDUX_ROOT isn't
        passed through, the config check falls back to the real dev
        checkout (which has vidux-config.py) and passes instead of naming
        the fake root as broken."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_root = Path(tmpdir) / "fake-checkout"
            (fake_root / "bin").mkdir(parents=True)
            (fake_root / "scripts").mkdir()
            (fake_root / "VERSION").write_text("0.0.0-test\n", encoding="utf-8")
            shutil.copy2(ROOT / "bin" / "vidux", fake_root / "bin" / "vidux")
            (fake_root / "bin" / "vidux").chmod(0o755)
            shutil.copy2(
                ROOT / "scripts" / "vidux-doctor-cli.sh",
                fake_root / "scripts" / "vidux-doctor-cli.sh",
            )
            # scripts/vidux-config.py is deliberately NOT copied in.

            env = os.environ.copy()
            env.pop("VIDUX_ROOT", None)
            env["VIDUX_DOCTOR_SKIP_NPM_TEST"] = "1"

            result = subprocess.run(
                [str(fake_root / "bin" / "vidux"), "doctor"],
                capture_output=True, text=True, timeout=30, env=env,
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                f"{fake_root}/scripts/vidux-config.py missing",
                result.stdout,
                "doctor-cli.sh did not validate the checkout bin/vidux resolved "
                "-- VIDUX_ROOT was not passed through to the exec'd subprocess",
            )

    def test_vidux_cli_gives_authored_error_when_python3_missing(self):
        """Same finding, the python3-on-PATH half: a python3-dispatching
        subcommand (status/drift/config/signpost/http-smoke/dev) used to
        leak "bash: exec: python3: not found" instead of a vidux-authored
        message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fakebin = Path(tmpdir) / "fakebin"
            fakebin.mkdir()
            # Symlink every tool bin/vidux's preamble + require_python3 need,
            # except python3 itself.
            for tool in ("bash", "sh", "dirname", "readlink", "cat", "awk", "cut"):
                real = shutil.which(tool)
                if real:
                    (fakebin / tool).symlink_to(real)
            env = os.environ.copy()
            env["PATH"] = str(fakebin)

            result = subprocess.run(
                [str(ROOT / "bin" / "vidux"), "status"],
                capture_output=True, text=True, timeout=10, env=env,
            )
            self.assertEqual(result.returncode, 127, result.stderr)
            self.assertIn("python3 not found on PATH", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_vidux_completion_command_completes_shell_targets(self):
        """The completion subcommand should complete target shells, not Vidux commands."""
        completion_source = _read(ROOT / "scripts" / "vidux-completion.sh")
        self.assertNotIn("help|completion)", completion_source)

        bash_completion = subprocess.run(
            [str(ROOT / "scripts" / "vidux-completion.sh"), "bash"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(bash_completion.returncode, 0, bash_completion.stderr)
        self.assertIn('compgen -W "bash zsh fish --help -h"', bash_completion.stdout)

        zsh_completion = subprocess.run(
            [str(ROOT / "scripts" / "vidux-completion.sh"), "zsh"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(zsh_completion.returncode, 0, zsh_completion.stderr)
        self.assertIn("completion)", zsh_completion.stdout)
        self.assertIn("'bash[Emit bash completion]'", zsh_completion.stdout)
        self.assertIn("'zsh[Emit zsh completion]'", zsh_completion.stdout)
        self.assertIn("'fish[Emit fish completion]'", zsh_completion.stdout)

        fish_completion = subprocess.run(
            [str(ROOT / "scripts" / "vidux-completion.sh"), "fish"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(fish_completion.returncode, 0, fish_completion.stderr)
        self.assertIn("-a 'bash zsh fish'", fish_completion.stdout)
        self.assertIn("__fish_seen_subcommand_from completion", fish_completion.stdout)

    def test_vidux_fish_help_completion_includes_help_subcommand(self):
        """Fish should complete the same help targets as the canonical subcommand list."""
        fish_completion = subprocess.run(
            [str(ROOT / "scripts" / "vidux-completion.sh"), "fish"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(fish_completion.returncode, 0, fish_completion.stderr)
        self.assertIn(
            "__fish_seen_subcommand_from help' -a 'dev browse status init drift config signpost http-smoke doctor build release completion help'",
            fish_completion.stdout,
        )

    def test_vidux_fish_config_and_signpost_options_match_user_cli(self):
        """Fish completion must expose config and signpost flags, not just subcommands."""
        fish_completion = subprocess.run(
            [str(ROOT / "scripts" / "vidux-completion.sh"), "fish"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(fish_completion.returncode, 0, fish_completion.stderr)
        for flag in ("config", "json", "strict", "path", "source", "force"):
            self.assertIn(
                f"__fish_seen_subcommand_from config' -l {flag}",
                fish_completion.stdout,
                f"fish config completion missing --{flag}",
            )
        for flag in (
            "feature",
            "action",
            "status",
            "duration-ms",
            "exit-code",
            "called",
            "emitter",
            "meta",
            "log",
            "run-id",
            "runtime",
            "limit",
            "json",
        ):
            self.assertIn(
                f"__fish_seen_subcommand_from signpost' -l {flag}",
                fish_completion.stdout,
                f"fish signpost completion missing --{flag}",
            )
        self.assertIn("__fish_seen_subcommand_from config' -l help -s h", fish_completion.stdout)
        self.assertIn("__fish_seen_subcommand_from signpost' -l help -s h", fish_completion.stdout)

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

    def test_vidux_loop_exposes_long_horizon_handoff_contract(self):
        """Reduce mode must surface week-long handoff and stale-proof gates."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task P2: Run week-long multi-agent durable loop with proof from 2020-01-01 [Evidence: prior run]
            ## Progress
        """)

        contract = data["handoff_contract"]
        self.assertTrue(contract["long_horizon"])
        self.assertTrue(contract["handoff_required"])
        self.assertTrue(contract["meter_checkpoint_required"])
        self.assertTrue(contract["stale_proof_gate"])
        self.assertEqual(contract["stale_proof_dates"][0]["date"], "2020-01-01")
        self.assertEqual(data["action"], "refresh_proof")
        self.assertEqual(data["next_action"], "refresh_proof")
        self.assertIn("Stale dated proof", data["context"])
        for field in [
            "plan_row_moved",
            "task_id",
            "ledger",
            "proof",
            "files_claimed",
            "handoff_status",
            "next_agent_resume",
        ]:
            self.assertIn(field, contract["required_fields"])

        fresh = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task P2: Run week-long multi-agent durable loop with current proof [Evidence: current run]
            ## Progress
        """)
        self.assertTrue(fresh["handoff_contract"]["long_horizon"])
        self.assertFalse(fresh["handoff_contract"]["stale_proof_gate"])
        self.assertEqual(fresh["action"], "execute")
        self.assertEqual(fresh["next_action"], "dispatch")

        stale_with_circuit_breaker = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task P2: Run week-long multi-agent durable loop with proof from 2020-01-01 [Evidence: prior run]
            ## Progress
            - [2026-04-07] Cycle 3: Assessed state. No changes needed.
            - [2026-04-07] Cycle 2: Reviewed plan. Nothing to do.
            - [2026-04-07] Cycle 1: Read plan. All good.
        """)
        self.assertEqual(stale_with_circuit_breaker["circuit_breaker"], "open")
        self.assertEqual(stale_with_circuit_breaker["action"], "refresh_proof")
        self.assertEqual(stale_with_circuit_breaker["next_action"], "refresh_proof")

    def test_vidux_loop_uses_latest_observed_date_for_stale_proof(self):
        """Historical proof dates must not keep a freshly refreshed row stale."""
        today = datetime.now(timezone.utc).date()
        fresh_date = today.isoformat()
        old_date = (today - timedelta(days=8)).isoformat()
        future_date = (today + timedelta(days=8)).isoformat()

        refreshed = self._run_loop_on(f"""\
            # Test Plan
            ## Tasks
            - [in_progress] Task T2: Refresh week-long LaunchAgent proof. Old evidence {old_date}; refreshed evidence {fresh_date}. [Evidence: current run]
            ## Progress
        """)
        self.assertFalse(refreshed["handoff_contract"]["stale_proof_gate"])
        self.assertEqual(refreshed["handoff_contract"]["stale_proof_dates"], [])
        self.assertEqual(refreshed["action"], "execute")
        self.assertEqual(refreshed["next_action"], "dispatch")

        future_deadline_does_not_clear_old_proof = self._run_loop_on(f"""\
            # Test Plan
            ## Tasks
            - [in_progress] Task T2: Refresh week-long LaunchAgent proof. Old evidence {old_date}; next review {future_date}. [Evidence: prior run]
            ## Progress
        """)
        self.assertTrue(future_deadline_does_not_clear_old_proof["handoff_contract"]["stale_proof_gate"])
        self.assertEqual(
            future_deadline_does_not_clear_old_proof["handoff_contract"]["stale_proof_dates"][0]["date"],
            old_date,
        )
        self.assertEqual(future_deadline_does_not_clear_old_proof["action"], "refresh_proof")

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
        expected_version = (ROOT / "VERSION").read_text().splitlines()[0].strip()
        self.assertEqual(data["version"], expected_version)

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

    def test_prompt_template_has_long_horizon_contract(self):
        """The canonical lane prompt template must make week-long handoff state explicit."""
        text = _read(ROOT / "docs" / "reference" / "prompt-template.md")
        commit_push = text[text.index("### Commit + push") : text.index("### Merge", text.index("### Commit + push"))]
        checkpoint_rules = text[text.index("### No-noise rule") : text.index("## Full Example")]
        required = [
            "Long-horizon / multi-agent contract",
            "one canonical PLAN.md",
            "claims-bus.sh check",
            "files_claimed",
            "stale-proof",
            "meter checkpoint",
            "handoff_status",
            "next-agent resume",
            "invariant audit",
            "regression runner",
            "adversarial reviewer",
            "scripts/vidux-publish-scrutiny.py",
            "--summary",
            "--review-pass invariant-audit:pass",
        ]
        for phrase in required:
            self.assertIn(phrase, text)
        self.assertNotIn("plan, proof, handoff,\n  resume, and claimed-file fields", commit_push)
        for phrase in [
            "plan path",
            "concise summary",
            "proof",
            "`handoff_status`",
            "files claimed",
            "next-agent resume",
            "changed files",
            "claims",
        ]:
            self.assertIn(phrase, commit_push)

        self.assertNotIn("The diff tells the story", checkpoint_rules)
        self.assertNotIn("memory.md orients", checkpoint_rules)
        for phrase in [
            "owning plan plus matching publish ledger row carries the shipped-cycle story",
            "memory.md only orients the lane-local cycle note",
        ]:
            self.assertIn(phrase, checkpoint_rules)

    def test_scripts_reference_describes_publish_claim_path_resolution(self):
        """Publish scrutiny docs must require real claimed paths, not only path-shaped text."""
        scripts = _read(ROOT / "docs" / "reference" / "scripts.md")
        row_start = scripts.index("`scripts/vidux-publish-scrutiny.py`")
        row_end = scripts.index("\n", row_start)
        row = scripts[row_start:row_end]

        for phrase in [
            "summary/plan path/checkbox-FSM task row/proof/publish ledger eid/handoff",
            "path-like file+claim/resume metadata exists",
            "claims cover every file-claimed entry",
            "claimed paths resolve to existing paths or git-known deletions",
            "invariant + regression + adversarial review passes",
        ]:
            self.assertIn(phrase, row)

    def test_scripts_reference_describes_pr_body_claim_path_resolution(self):
        """PR-body docs must require real claimed paths, not only path-shaped text."""
        scripts = _read(ROOT / "docs" / "reference" / "scripts.md")
        row_start = scripts.index("`scripts/vidux-pr-body.py`")
        row_end = scripts.index("\n", row_start)
        row = scripts[row_start:row_end]

        for phrase in [
            "lane, existing plan path/checkbox-FSM task row, summary, proof, a matching publish ledger eid",
            "must exist as a publish event in the hot/archive ledger",
            "same lane/task/summary/plan/proof/handoff/changed-files/file-claims/resume packet",
            "claimed files resolving to existing paths or git-known deletions",
            "self-scrutiny review-pass",
            "resume",
            "change fields",
        ]:
            self.assertIn(phrase, row)

    def test_core_push_authorization_requires_publish_propagation(self):
        """Core push/trunk doctrine must bind allowed publishes to plan+ledger state."""
        text = _read(SKILL)
        push = text[text.index("**Push authorization:**") : text.index("### Trunk-First Rule")]
        trunk = text[text.index("### Trunk-First Rule") : text.index("**Worktree lifecycle:**")]

        self.assertLess(
            push.index("ledger-emit.sh --event publish"),
            push.index("Open PRs ready-for-review"),
        )
        for phrase in [
            "Operational PR-branch pushes are safe without asking only after",
            "owning PLAN.md row/Progress/Drift Log is updated",
            "ledger-emit.sh --event publish",
            "records the publish packet",
            "Direct-to-main requires explicit authorization + the same publish propagation",
            "normal publish-propagated PR-branch push",
        ]:
            self.assertIn(phrase, push)

        for phrase in [
            "publish propagation recorded in the owning plan row + publish packet",
            "final proof",
            "release gates",
            "If they publish externally, record the plan + ledger propagation",
        ]:
            self.assertIn(phrase, trunk)

    def test_core_checkpoint_breadcrumbs_require_plan_then_ledger_then_git(self):
        """Loop/checkpoint docs must not teach raw commit/push as the publish checkpoint."""
        text = _read(SKILL)
        setup = _read(ROOT / "SETUP_NEW_MACHINE.md")
        cycle = text[text.index("## The Cycle") : text.index("### Read the Room")]
        loop = text[text.index("Loop body:") : text.index("Persistent loop mode is")]
        breadcrumbs = text[
            text.index("## Checkpoint Breadcrumbs") : text.index("## Replaces /superpowers")
        ]

        for stale_phrase in [
            "Checkpoint with commit + push.",
            "Commit as `vidux: [what you did]` + Progress entry.",
            "**Git** — commit and push the owned slice.",
            "Keep pushing that same lane",
        ]:
            self.assertNotIn(stale_phrase, text)
            self.assertNotIn(stale_phrase, setup)

        for phrase in [
            "CHECKPOINT -> Update the plan/queue note, emit the publish packet",
            "commit/push only after those breadcrumbs exist",
            "use `vidux drift` if they diverge",
        ]:
            self.assertIn(phrase, cycle)

        self.assertLess(
            loop.index("update the owning plan/queue note"),
            loop.index("emit the publish packet"),
        )
        self.assertLess(
            loop.index("emit the publish packet"),
            loop.index("commit + push the owned branch/PR path"),
        )
        for phrase in [
            "Checkpoint: update the owning plan/queue note",
            "emit the publish packet",
            "commit + push the owned branch/PR path",
        ]:
            self.assertIn(phrase, loop)

        self.assertLess(breadcrumbs.index("**Plan / queue**"), breadcrumbs.index("**Ledger**"))
        self.assertLess(breadcrumbs.index("**Ledger**"), breadcrumbs.index("**Git**"))
        for phrase in [
            "carrying the publish packet fields",
            "ledger-emit.sh --event publish",
            "branch/PR handoff",
            "after the plan + ledger breadcrumbs exist",
        ]:
            self.assertIn(phrase, breadcrumbs)

        for phrase in [
            "Keep driving that same lane",
            "Before any branch/PR/release publish leaves the machine",
            "update the owning plan",
            "emit a publish ledger row with concise summary, plan task id, proof, handoff status, files claimed, and next-agent resume",
            "carry the ledger eid into the handoff",
        ]:
            self.assertIn(phrase, setup)

    def test_store_doc_makes_plan_and_publish_ledger_cycle_truth(self):
        """Store docs must not let git history outrank plan and publish proof."""
        store = _read(ROOT / "docs" / "concepts" / "store.md")
        intro = store[: store.index("### evidence/")]
        git_history = store[store.index("### Git History") : store.index("## INBOX.md")]
        intro_normalized = " ".join(intro.split())
        git_history_normalized = " ".join(git_history.split())

        for stale_phrase in [
            "The commit message is the single source of truth for what happened in a cycle.",
            "if they diverge, the git log wins",
            "Every fact Vidux needs to survive an interrupted session lives in one of four durable locations",
            "One per project. The single source of truth for what needs to happen, what has been decided, and what actually happened.",
            "When code changed, a checkpoint commit records the local diff",
            "plan/ledger checkpoint",
        ]:
            self.assertNotIn(stale_phrase, store)

        for phrase in [
            "repo files",
            "append-only publish ledger rows that prove shipped cycles",
            "Publish ledger rows live outside the repo in the append-only ledger",
            "ledger row carrying task id, proof, handoff status, claimed files, resume point",
            "Planning authority for queue, decisions, constraints, Progress/Drift record",
            "publish packet is the proof of what shipped and how the next agent resumes",
        ]:
            self.assertIn(phrase, intro_normalized)

        for phrase in [
            "Cycle truth lives in the owning `PLAN.md` Progress, Tasks, or Drift Log entry",
            "publish packet",
            "Git history is evidence that transport happened",
            "does not outrank a missing or stale plan/ledger packet",
        ]:
            self.assertIn(phrase, git_history_normalized)

    def test_public_docs_scope_plan_authority_and_publish_ledger_truth(self):
        """Public onboarding/concept docs must not teach plan-only or commit-only truth."""
        files = {
            "home": ROOT / "docs" / "index.md",
            "readme": ROOT / "README.md",
            "quickstart": ROOT / "docs" / "guide" / "quickstart.md",
            "installation": ROOT / "docs" / "guide" / "installation.md",
            "cycle": ROOT / "docs" / "concepts" / "cycle.md",
            "principles": ROOT / "docs" / "concepts" / "principles.md",
            "store": ROOT / "docs" / "concepts" / "store.md",
        }
        docs = {name: _read(path) for name, path in files.items()}
        combined = "\n".join(docs.values())
        normalized = {name: " ".join(text.split()) for name, text in docs.items()}

        for stale_phrase in [
            "One source of truth",
            "State lives in markdown files in a git branch",
            "structured commit,<br/>progress entry",
            "**CHECKPOINT**: structured commit",
            "Every cycle ends with a checkpoint commit",
            "Operational PRs are always safe to push without asking",
            "checkpoint committed",
            "PLAN.md is the source of truth",
            "PLAN.md stays the source of truth",
            "source-of-truth claim",
            "PLAN.md                    ← source of truth",
            "block session exit without a structured commit",
            "Every cycle ends with a structured commit",
            "state lives in files committed to git",
            "The agent commits the in-progress work, then continues from the last checkpoint.",
            "When code changed, a checkpoint commit records the local diff",
            "plan/ledger checkpoint",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "one owning PLAN.md for queue, decisions, and progress",
            "Publish ledger rows carry shipped-cycle proof and resume metadata",
            "durable recovery lives in repo files plus append-only ledger rows",
        ]:
            self.assertIn(phrase, normalized["home"])

        for phrase in [
            "One planning authority",
            "Proof travels with the handoff",
            "`PLAN.md` + publish ledger rows",
        ]:
            self.assertIn(phrase, normalized["readme"])

        for phrase in [
            "emits the publish ledger row before any branch/PR/release publish",
            "durable handoff is the owning `PLAN.md` update plus the matching publish ledger row",
            "preserves in-progress work first",
            "records a plan/ledger handoff",
            "commits only after the plan/ledger packet exists and only if code changed",
        ]:
            self.assertIn(phrase, normalized["quickstart"])

        self.assertIn(
            "plan/progress update and publish-ledger packet",
            normalized["installation"],
        )

        for phrase in [
            "queue/planning authority: tasks, decisions, constraints, progress",
            "Latest publish ledger rows",
            "plan/progress checkpoint",
            "ledger-emit.sh --event publish",
            "plan/proof checkpoint recorded",
        ]:
            self.assertIn(phrase, normalized["cycle"])

        for phrase in [
            "planning authority for queue, decisions, constraints, progress",
            "State lives in repo files plus append-only ledger rows",
            "ledger row carrying task id, proof, handoff status, files claimed, next-agent resume",
        ]:
            self.assertIn(phrase, normalized["principles"])

        for phrase in [
            "append-only publish ledger rows that prove shipped cycles",
            "PLAN.md ← queue/planning authority",
            "Planning authority for queue, decisions, constraints",
            "When code changed, a commit records the local diff",
        ]:
            self.assertIn(phrase, normalized["store"])

    def test_plan_fields_progress_entries_reference_publish_ledger_truth(self):
        """Progress field docs must not make diff/git log the full cycle story."""
        text = _read(ROOT / "docs" / "reference" / "plan-fields.md")
        normalized = " ".join(text.split())

        for stale_phrase in [
            "Leaner than a checkpoint commit",
            "the diff tells the story",
            "that's what `git log` is for",
        ]:
            self.assertNotIn(stale_phrase, text)

        for phrase in [
            "Progress line orients future agents to the owning plan state",
            "matching publish ledger row carries shipped-cycle proof",
            "handoff status",
            "claimed files",
            "next-agent resume",
            "does not replace the plan plus ledger packet",
            "Treat the diff or git log as the whole handoff",
            "cite the task, proof, resume point",
        ]:
            self.assertIn(phrase, normalized)

    def test_core_skill_scopes_plan_authority_and_publish_ledger_truth(self):
        """Active core state-source wording must separate plans from proof packets."""
        text = _read(SKILL)
        intro = text[text.index("# Vidux") : text.index("## First-Time Setup")]
        principle_one = text[text.index("### 1. Plan first, code second") : text.index("### 2. Design for interruption")]
        browser = text[text.index("## Browser") : text.index("### Ad-hoc artifacts")]
        read_room = text[text.index("### Read the Room") : text.index("Ad hoc scratch files")]
        compaction = text[text.index("5. **Compaction survival.") : text.index("### Cron + interactive interleave")]
        nursing_state = text[
            text.index("**Repo-level state rule:**") : text.index(
                "For any timed or repeated supervision"
            )
        ]

        for stale_phrase in [
            "the plan file is the only state that matters",
            "plan file is the only state",
            "PLAN.md is the source of truth",
            "PLAN.md stays the source of truth",
            "the source of truth is still the markdown file in git",
            "resume from disk truth",
            "write iteration state to repo files (PLAN.md progress, RALPH.md queue, `.agent-ledger/`)",
            "Read PLAN.md, RALPH.md, CLAUDE.md, and the last ledger entry",
            "**The ledger** (`.agent-ledger/activity.jsonl`)",
            "Preferred sources: `RALPH.md`, repo plan docs, repo nurse logs, and `.agent-ledger/activity.jsonl`",
        ]:
            self.assertNotIn(stale_phrase, text)

        for phrase in [
            "owning plan records queue, decisions, constraints, progress",
            "matching ledger rows carry shipped-cycle proof",
            "handoff_status",
            "files claimed",
            "path-like claims",
            "next-agent resume",
        ]:
            self.assertIn(phrase, intro)

        for phrase in [
            "planning authority for queue, decisions, constraints, Progress/Drift record",
            "publish packet",
        ]:
            self.assertIn(phrase, principle_one)

        for phrase in [
            "queue/planning authority",
            "publish packet remains the shipped-cycle proof",
        ]:
            self.assertIn(phrase, browser)

        for phrase in [
            "~/.agent-ledger/activity.jsonl",
            "Repo-local `.agent-ledger/` is optional companion state only when documented",
        ]:
            self.assertIn(phrase, read_room)

        for phrase in [
            "emit the publish packet when work shipped",
            "repo-local `.agent-ledger/` only for configured companion state",
            "Repo files + append-only ledger rows survive compaction",
            "latest matching ledger entry",
        ]:
            self.assertIn(phrase, compaction)

        for phrase in [
            "centralized `~/.agent-ledger/activity.jsonl` stream",
            "repo-local `.agent-ledger/` only when documented",
        ]:
            self.assertIn(phrase, nursing_state)

    def test_loop_and_guide_scope_plan_authority_and_publish_ledger_truth(self):
        """Loop/public guide docs must not teach plan-only or commit-centric truth."""
        loop = _read(ROOT / "LOOP.md")
        guide = _read(ROOT / "docs" / "guide" / "index.md")
        combined = "\n".join([loop, guide])
        loop_normalized = " ".join(loop.split())
        guide_normalized = " ".join(guide.split())

        for stale_phrase in [
            "`PLAN.md` — the source of truth",
            "PLAN.md — the only source of truth",
            "State lives in markdown files in a git branch",
            "Structured commit, progress entry in PLAN.md",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "append-only ledger",
            "queue/decisions/constraints/Progress authority",
            "`ledger-emit.sh --event publish`",
            "CHECKPOINT plan + ledger",
        ]:
            self.assertIn(phrase, loop_normalized)

        for phrase in [
            "repo-local plan/proof files the recovery packet",
            "owning `PLAN.md`",
            "Matching publish ledger rows carry the shipped-cycle proof packet",
            "handoff status",
            "claimed files",
            "resume metadata",
            "PLAN.md - queue/planning authority",
            "publish ledger rows - shipped-cycle proof packet",
            "Plan/progress update plus publish ledger row",
            "owning plan plus publish ledger row persists across sessions",
        ]:
            self.assertIn(phrase, guide_normalized)

    def test_root_architecture_doctrine_ingredients_use_plan_ledger_recovery(self):
        """Root doctrine docs must not teach plan-only truth or commit-first recovery."""
        architecture = _read(ROOT / "ARCHITECTURE.md")
        doctrine = _read(ROOT / "DOCTRINE.md")
        ingredients = _read(ROOT / "INGREDIENTS.md")
        combined = "\n".join([architecture, doctrine, ingredients])
        normalized = " ".join(combined.split())

        for stale_phrase in [
            "PLAN.md<br/>source of truth",
            "git history<br/>checkpoint commits",
            "CHECKPOINT<br/>structured commit",
            "Structured commit message. Update Progress log in PLAN.md.",
            "State lives in markdown files in git. No databases. No daemons. No chat history.",
            "They share state through PLAN.md and git, never through memory or message passing.",
            "One file, one truth.",
            "The only reliable thing is what's committed to git.",
            "## 1. Plan is truth",
            "PLAN.md is the single source of truth.",
            "State lives in files, not memory. Every cycle reads fresh. Checkpoints are structured.",
            'If uncommitted work exists from a crash, commit it first',
            "git as the persistence layer",
            "PLAN.md's Progress section (timestamped cycle logs) serves the same handoff function",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "PLAN.md + publish ledger + evidence + git",
            "CHECKPOINT<br/>plan update + publish ledger",
            "PLAN.md<br/>queue/planning authority",
            "publish ledger rows<br/>shipped-cycle proof",
            "git history<br/>transport + diff evidence",
            "**one PLAN.md** as its queue/planning authority",
            "Matching publish ledger rows prove shipped cycles",
            "queue state through PLAN.md",
            "shipped-cycle proof through publish ledger rows",
            "owning PLAN.md update plus the matching publish ledger row",
            "Plan is authority",
            "shipped-cycle proof/resume lives in the matching publish ledger row",
            "Checkpoints are structured plan/ledger packets",
            "preserves dirty WIP",
        ]:
            self.assertIn(phrase, normalized)

    def test_interruption_and_fleet_docs_use_plan_ledger_recovery(self):
        """Interruption docs must not teach raw commit or prompt-only recovery truth."""
        skill = _read(SKILL)
        loop = _read(ROOT / "LOOP.md")
        claude = _read(ROOT / "docs" / "fleet" / "claude-lifecycle.md")
        codex = _read(ROOT / "docs" / "fleet" / "codex-lifecycle.md")
        fleet_index = _read(ROOT / "docs" / "fleet" / "index.md")
        platforms = _read(ROOT / "docs" / "fleet" / "platforms.md")
        combined = "\n".join([skill, loop, claude, codex, fleet_index, platforms])
        normalized = " ".join(combined.split())

        for stale_phrase in [
            "State lives in files, never in memory. Checkpoints are structured",
            "If `git diff` shows uncommitted work from a dead session, commit it first",
            "If uncommitted work exists from a crash, commit it first",
            "prompt.md      ← source of truth (read every cycle)",
            "Append one line to memory.md. Update PLAN.md status. Commit if code changed.",
            "`prompt.md` and `memory.md` hold the actual lane state",
            "`prompt.md` + `memory.md` live in the shared lane directory and are the durable lane state",
            "State can live on disk in files such as `PLAN.md`, `memory.md`, and ledger data.",
            "state lives on disk under the shared lane directory (`prompt.md` + `memory.md`), not in the cron",
            "picks up where it left off",
            "The actual lane instructions and memory live under a shared",
            "prompt.md` + `memory.md` are the hot-editable lane state",
            "append-only checkpoint log",
            "checkpoint history durable across restarts",
            "Session cycling + memory.md handoff works across accounts",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "Durable recovery lives in repo files + append-only ledger rows",
            "structured plan/ledger packets",
            "matching ledger row",
            "preserve it first",
            "record the recovery path in the owning plan plus a ledger handoff",
            "NEVER commit, overwrite, or discard unknown WIP",
            "record the recovery path in the owning plan plus a ledger handoff before any commit, push, cleanup, or overwrite",
            "commit unknown WIP",
            "prompt.md ← lane instructions (read every cycle)",
            "owning `PLAN.md` plus matching publish ledger row carrying the durable proof/resume packet",
            "Update the owning PLAN.md status/Progress and emit the matching publish ledger row",
            "task id, proof, handoff status, files claimed, and next-agent resume",
            "lane-local cycle log",
            "Shipped-cycle state lives in the owning `PLAN.md` plus matching publish ledger rows",
            "commit/push only after the plan/ledger packet exists",
            "State orientation can live on disk",
            "instructions and local cycle notes live under the shared lane directory",
            "shipped-work proof lives in the owning plan plus publish ledger rows",
            "reads its own `memory.md` for local cycle orientation",
            "owning plan plus publish ledger proof",
            "actual lane instructions and local cycle notes",
            "owning plan plus publish ledger rows carry shipped-work proof",
            "lane-local memory notes plus plan/ledger handoff",
        ]:
            self.assertIn(phrase, normalized)

    def test_amp_harness_goal_mode_uses_plan_ledger_state(self):
        """Loaded /amp must not mint harness or goal prompts with plan/memory-only state."""
        if not AMP_SKILL.exists():
            self.skipTest("Leo amp skill is not present")

        text = _read(AMP_SKILL)
        template_text = re.sub(r"[│┌┐└┘─]+", " ", text)
        normalized = " ".join(template_text.split())

        for stale_phrase in [
            "State lives in PLAN.md, evidence files, and `memory.md`",
            "state lives in files, never in memory",
            "state lives in the PLAN.md it points at",
            "+ commit SHA",
            "[Evidence: <proof/SHA>]",
        ]:
            self.assertNotIn(stale_phrase, text)

        for phrase in [
            "State orientation lives in the owning PLAN.md, evidence files, matching publish ledger rows, and lane-local memory notes",
            "Shipped-work proof/resume belongs to the plan plus publish ledger packet",
            "`memory.md` is local cycle orientation only",
            "durable recovery lives in repo files plus append-only ledger rows",
            "state orientation comes from the owning PLAN.md plus matching publish ledger rows",
            "publish ledger eid",
            "Emit the publish ledger row for shipped work with proof, handoff_status, files claimed, claims, and resume",
            "Emit publish ledger row before git transport",
        ]:
            self.assertIn(phrase, normalized)

    def test_deleted_auto_publish_rules_are_rehomed_without_skip(self):
        """Deleting /auto must not skip the live publish/decision contracts."""
        required = [AMP_SKILL, FLOW_SKILL, FLOW_YAML, SKILLBOX_SKILL]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            self.skipTest("Leo active control-plane skills are not present: " + ", ".join(missing))

        test_source = _read(Path(__file__))
        combined = "\n".join(
            [_read(SKILL), _read(AMP_SKILL), _read(FLOW_SKILL), _read(FLOW_YAML), _read(SKILLBOX_SKILL)]
        )
        normalized = " ".join(combined.split())

        self.assertFalse(PRIVATE_AUTO_SKILL.exists(), "private /auto skill should stay deleted")
        self.assertFalse(SHARED_AUTO_SKILL.exists(), "shared /auto skill should stay deleted")
        stale_skip = "Leo " + "auto skill is not present"
        self.assertNotIn(stale_skip, test_source)

        for stale_phrase in [
            "Commit to the tooling repo IN THE SAME TURN. Stage the file in repo B",
            "STOP, commit + push the tool repo, THEN report",
            "The local edit IS the bug; the commit IS the fix.",
            "Commit + push the ai repo per `/captain` rules.",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "Decision Layer (Auto Removed)",
            "Migration rule: reusable decision rules land in Flow core",
            "Do not add `/auto`; it is intentionally deleted",
            "State orientation lives in the owning PLAN.md, evidence files, matching publish ledger rows, and lane-local memory notes",
            "Shipped-work proof/resume belongs to the plan plus publish ledger packet",
            "Emit publish ledger row before git transport",
            "Skillbox vs Captain",
        ]:
            self.assertIn(phrase, normalized)

    def test_goal_navigation_and_deleted_auto_contract(self):
        """Goal prompts must navigate work while Flow owns the live decision layer."""
        required = [AMP_SKILL, FLOW_SKILL, FLOW_YAML, SKILLBOX_SKILL, GOAL_NAV_PROMPT]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            self.skipTest("Leo active control-plane skills are not present: " + ", ".join(missing))

        vidux = _read(SKILL)
        prompt = _read(GOAL_NAV_PROMPT)
        amp = _read(AMP_SKILL)
        flow = _read(FLOW_SKILL)
        flow_yaml = _read(FLOW_YAML)
        skillbox = _read(SKILLBOX_SKILL)
        combined = "\n".join([vidux, prompt, amp, flow, flow_yaml, skillbox])
        normalized = " ".join(combined.split())

        # Phrases must exist in the *live* thin-token corpus (SKILL + goal-nav
        # prompt + Amp + Flow + Flow YAML + Skillbox). Do not re-bloat doctrine
        # just to satisfy obsolete string matches after the kernel-cut.
        for phrase in [
            "## Goal Navigation Plans",
            "navigation contract, not a frozen task list",
            "The prompt file is also a pointer/control contract, not the goal",
            "`PLAN.md` owns the actual goal",
            "real work rows, exit criteria, and the next action",
            "how to rank work when state changes, not the exact future task list",
            "completion rule: `/goal` and `/loop` keep appending and executing real work rows",
            "N-agents-one-PLAN concurrency contract",
            "Vidux core does not choose model-specific leader/follower hierarchies",
            "leader/follower orchestration",
            "Codex/Claude/GLM/Grok runner selection",
            "headless Codex control",
            "hard-blocker move-on rule",
            "primitive readiness and proof floors",
            "worktree convergence rule",
            "Decision Layer (Auto Removed)",
            "`/auto` was deleted on 2026-06-26",
            "Hard blocker move-on",
            "Primitive registry for broad Leo work",
            "Graphite/repo review discipline",
            "do not use GitHub Actions as expensive FirstBite test proof",
            # Amp FIRE path still exists; goal-nav forbids pre-planning exact tasks
            "GATHER → SYNTHESIZE → PRESENT → STEER → FIRE",
            "Do not plan the exact future implementation tasks",
            "Primitive Readiness Matrix",
            "Nia-first indexed/source lookup before web fetch",
            "Worktree Lifecycle Contract",
            "append real work rows when discovery creates new reachable work",
            "keep going until the PLAN says the goal is complete",
            "do not load or restore it",
            "stale live pointers are repaired at their owning artifact",
            "skills: [<your-private-dispatcher>, vidux]",
            "skills: [amp, <your-private-dispatcher>, vidux]",
            "Skillbox vs Captain",
            "Captain decides placement, Skillbox executes the mount",
            "Flow owns leader/follower orchestration",
            "The host's private router owns model/runner selection and leader/follower foldback",
        ]:
            self.assertIn(phrase, normalized)

        for stale_phrase in [
            "Vidux is the kernel",
            "planner-executor kernel",
            "Vidux owns the full nursing loop",
            "Vidux owns model-specific leader/follower hierarchies",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "Vidux is the thin plan/proof control plane",
            "Vidux owns the schema and lifecycle for plan state",
            "The host's private router owns model/runner selection and leader/follower foldback",
            "Runner selection and model-worker foldback stay with Flow",
        ]:
            self.assertIn(phrase, normalized)

        prompt_path = "prompts/goal-navigation-control-plane.prompt.md"
        self.assertIn(prompt_path, vidux)
        self.assertIn(prompt_path, amp)
        self.assertFalse(PRIVATE_AUTO_SKILL.exists(), "private /auto skill should be deleted, not archived")
        self.assertFalse(SHARED_AUTO_SKILL.exists(), "shared /auto skill should be deleted, not shadowed")
        self.assertFalse(ACTIVE_AUTO_SKILL.exists(), "active skill farm should not expose /auto")

        for stale_phrase in [
            "Fleet/review policy lives in `/auto` and `references/fleet-policy.md`",
            "Full boilerplate only on explicit ask, a runner that can't load `/vidux + /auto`",
            "Use /vidux + /auto; resume in-progress work first",
            "project strategy, go-with-flow decisions, PR shape policy | `/auto`",
            "Goal prompts, living prompt files, prompt-to-plan entrypoints | `/amp` plus `/auto`",
            "load `/auto` only when",
            "Add `/auto` only when",
            "[auto](../auto/SKILL.md)",
            "skills: [auto, vidux]",
            "skills: [amp, auto, vidux]",
        ]:
            self.assertNotIn(stale_phrase, combined)

    def test_kernel_cut_public_docs_scope_vidux_to_plan_proof_control_plane(self):
        """Public/core docs must not reintroduce Vidux as the orchestration kernel."""
        public = "\n".join([
            _read(ROOT / "README.md"),
            _read(ROOT / "docs" / "index.md"),
            _read(ROOT / "docs" / "guide" / "index.md"),
            _read(SKILL),
            _read(ROOT / "bin" / "vidux"),
            _read(ROOT / "package.json"),
        ])
        normalized = " ".join(public.split())

        for stale_phrase in [
            "lightweight orchestration system",
            "Vidux orchestrates AI coding work",
            "Documentation is the control plane",
            "Fleet Intelligence (opt-in)",
            "ORCHESTRATED",
            "Orchestration Mode",
            "Default Discipline Swarm",
            "Release Swarm",
            "Vidux orchestrates — decompose, delegate, track",
            # Round-3 panel finding: README explicitly says vidux is
            # "meaningfully less than an orchestration platform" (line 159),
            # while bin/vidux's own --help banner and package.json's own
            # description both self-described using the exact word the
            # README positions vidux against -- a reader typing
            # `vidux --help` saw language directly undercutting the README's
            # own differentiation claim.
            "expedition orchestration",
            "Plan-first orchestration for long-running AI coding loops",
        ]:
            self.assertNotIn(stale_phrase, public)

        for phrase in [
            "thin plan/proof control plane",
            "Plan/proof files are the control plane",
            "repo-local plan/proof files the recovery packet",
            "routing boundaries",
            "Vidux coordinates state; host tools or Flow dispatch workers",
            "host runtime or Flow",
            "core Vidux only preserves plan, proof, decision, and resume truth",
        ]:
            self.assertIn(phrase, normalized)

        automation_boundary = "\n".join([
            _read(ROOT / "guides" / "automation.md"),
            _read(ROOT / "references" / "automation.md"),
            _read(ROOT / "docs" / "fleet" / "index.md"),
            _read(ROOT / "docs" / "fleet" / "operations.md"),
        ])
        boundary_normalized = " ".join(automation_boundary.split())
        for phrase in [
            "this guide is operator reference, not a second control plane",
            "this file is historical/operator detail, not core authority",
            "Runtime dispatch is owned by the host tool or Flow",
            "Boundary: these operations are optional scheduling mechanics",
        ]:
            self.assertIn(phrase, boundary_normalized)

    def test_model_worker_delegation_contract_covers_glm_grok_and_codex(self):
        """Flow must project max GLM, max Grok, and high-fast Codex as bounded sidecar workers."""
        required = [FLOW_SKILL, FLOW_YAML, FLOW_CLI, GLM_SKILL, GROK_SKILL, CODEX_SKILL, SKILLBOX_SKILL]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            self.skipTest("Leo model-worker skills are not present: " + ", ".join(missing))

        flow = _read(FLOW_SKILL)
        flow_yaml = _read(FLOW_YAML)
        glm = _read(GLM_SKILL)
        grok = _read(GROK_SKILL)
        codex = _read(CODEX_SKILL)
        skillbox = _read(SKILLBOX_SKILL)
        combined = "\n".join([flow, flow_yaml, glm, grok, codex, skillbox])
        normalized = " ".join(combined.split())

        for phrase in [
            "## Model-Worker Delegation",
            "`glm_max_worker`",
            "`grok_max_worker`",
            "`codex_high_fast_worker`",
            "Flow owns routing and foldback",
            "## Leader/Follower Orchestration",
            "Flow owns leader/follower orchestration",
            "Vidux core supports N concurrent agents working on one PLAN",
            "Codex can run headless as the lead controller",
            "Claude Code can lead",
            "Flow writes leader/follower assignments into",
            "single_plan_rule",
            "assignment_sink",
            "lead owns plan/proof/diff",
            "opencode run --agent build --model zai/glm-5.2 --variant max",
            "codex exec",
            "service_tier",
            "high-fast Codex",
            "high reasoning and fast service tier",
            "one file/spec",
            "write_scope: lead_assigned_paths",
            "explicit allowed paths",
            "writable followers",
            "drive the assigned implementation slice",
            "grok -p",
            "`/loop`",
            "scheduler_create",
            "--best-of-n",
            "`Stop` hook is passive",
            "The lead owns plan/proof/diff application",
            "Skillbox only proves the runtime package surface",
            "Skillbox visibility is not write permission",
            "Do not put provider credentials, balances, or account-specific auth inside Skillbox docs",
            "writable workers edit only allowed_paths",
        ]:
            self.assertIn(phrase, normalized)

        result = subprocess.run(
            [
                "python3",
                str(FLOW_CLI),
                "subagents",
                "delegate max glm, max grok, and high fast /codex model-worker codegen to subagents for a build proof audit",
                "--repo",
                str(ROOT),
                "--json",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("leo-flow", payload["leader_follower"]["owner"], payload["leader_follower"])
        self.assertIn(
            "Vidux core supports N concurrent agents working on one PLAN",
            payload["leader_follower"]["authority_boundary"],
        )
        self.assertIn("Codex can run headless", payload["leader_follower"]["codex_headless"])
        self.assertIn("shadow queue", payload["delegation_policy"]["single_plan_rule"])
        self.assertIn("FLOW.md", payload["delegation_policy"]["assignment_sink"])
        sidecars = {item["id"]: item for item in payload["sidecars"]}
        for sidecar_id, skill_name in [
            ("glm_max_worker", "glm"),
            ("grok_max_worker", "grok"),
            ("codex_high_fast_worker", "codex"),
        ]:
            self.assertIn(sidecar_id, sidecars, sidecars)
            self.assertEqual(skill_name, sidecars[sidecar_id]["skill"], sidecars[sidecar_id])
            self.assertEqual("lead_assigned_paths", sidecars[sidecar_id]["write_scope"], sidecars[sidecar_id])
            self.assertEqual(["<lead-assigned>"], sidecars[sidecar_id]["allowed_paths"], sidecars[sidecar_id])
            self.assertEqual("constrained_isolated_lane_only", sidecars[sidecar_id]["lead_eligible"], sidecars[sidecar_id])
            self.assertTrue(sidecars[sidecar_id]["follower_default"], sidecars[sidecar_id])
            if sidecar_id == "codex_high_fast_worker":
                self.assertIn("high-fast", sidecars[sidecar_id]["model_tier"].lower(), sidecars[sidecar_id])
                self.assertIn("service_tier", sidecars[sidecar_id]["command_hint"], sidecars[sidecar_id])
            else:
                self.assertIn("max", sidecars[sidecar_id]["model_tier"].lower(), sidecars[sidecar_id])
            self.assertTrue(sidecars[sidecar_id]["command_hint"], sidecars[sidecar_id])
            self.assertIn("lead owns plan/proof/diff", sidecars[sidecar_id]["prompt"], sidecars[sidecar_id])
            self.assertIn("Only write inside the declared write scope", sidecars[sidecar_id]["prompt"], sidecars[sidecar_id])
            self.assertIn("fold back to the parent/lead", sidecars[sidecar_id]["prompt"], sidecars[sidecar_id])
        self.assertEqual(3, payload["delegation_policy"]["max_sidecars"], payload["delegation_policy"])
        self.assertIn("writable workers edit only allowed_paths", payload["delegation_policy"]["no_overlap_rule"])
        self.assertIn("writable followers may drive", payload["lead"]["rule"])
        self.assertIn("write-scoped worker slices", payload["lead"]["task"])

    def test_goal_navigation_prompt_file_is_concrete_goal_pointer(self):
        """The goal-navigation doctrine must have a pasteable prompt artifact."""
        self.assertTrue(GOAL_NAV_PROMPT.exists(), "missing canonical goal-navigation prompt file")
        text = _read(GOAL_NAV_PROMPT)
        normalized = " ".join(text.split())

        for phrase in [
            "Authority Store: `PLAN.md` (this repo's root)",
            "Use `/amp + /vidux + /<your-private-dispatcher> + /nia + /glm + /grok + /skillbox`",
            "Authority layering: this prompt's Authority Store is the Vidux meta/doctrine lane",
            "Per-project prompts inherit this contract, but own their own product PLAN",
            "Do not write product state into the Vidux core PLAN",
            "This file is a pointer, not the goal",
            "The Vidux PLAN owns the actual goal",
            "fixed `## Current State (resume here)` header",
            "Improve the goal before improving the work",
            "Goal-First Thinking Pass",
            "append-real-work rule",
            "Primitive Readiness Matrix",
            "Worker orchestration",
            "Your dispatcher owns leader/follower orchestration",
            "headless model-worker control",
            "Goal navigation inference:",
            "Hard Stops",
            "Mutation Rule",
            "`/auto` was deleted on 2026-06-26",
            "do not load or restore it",
            "Compact `/goal` Pointer",
            "This is a pointer; the goal lives in this repo's PLAN.md",
            "read this repo's prompts/goal-navigation-control-plane.prompt.md",
            "starting with ## Current State (resume here)",
            "let /<your-private-dispatcher> choose Codex/Claude/GLM/Grok leader/follower roles",
            "append/update real PLAN rows when discovery changes what complete means",
            "continue until the PLAN exit criteria are satisfied or every remaining row is parked with exact hard-blocker resume",
            "[METER ▓░N] [ETA Xh/gated] [N pending, M in_progress, K done]",
        ]:
            self.assertIn(phrase, normalized)

        for stale_phrase in [
            "TODO",
            "TBD",
            "[PLAN-APPEND-NEEDED]",
        ]:
            self.assertNotIn(stale_phrase, text)

    def test_release_cli_help_describes_plan_ledger_gated_publish(self):
        """Release-facing help/completion text must not advertise raw tag+push."""
        cli = _read(ROOT / "bin" / "vidux")
        completion = _read(ROOT / "scripts" / "vidux-completion.sh")
        release = _read(ROOT / "scripts" / "vidux-release.sh")
        combined = "\n".join([cli, completion, release])

        self.assertNotIn("Bump VERSION + cut CHANGELOG + tag + push", cli)
        self.assertNotIn("bump VERSION, cut CHANGELOG, tag, push", cli)
        self.assertNotIn("Bump VERSION, tag, push", completion)
        self.assertNotIn("CHANGELOG cut + tag + push", release)

        for phrase in [
            "plan/ledger-gated tag + push",
            "release publish requires --plan-path, --task-id, --proof, and --resume",
            "owning plan task row and publish ledger row are updated",
            "--plan-path <PLAN.md>",
            "--task-id <task-id>",
            "--proof <text>",
            "--resume <text>",
            "--handoff-status <s>",
            "Plan/ledger-gated release tag + push",
            "semver bump + CHANGELOG cut + plan/ledger-gated tag + push",
        ]:
            self.assertIn(phrase, combined)

    def test_team_coordination_skill_push_constraint_is_publish_propagated(self):
        """Authority-plan skill push constraints must not be raw command-only publishes."""
        plan_path = ROOT / "projects" / "team-agent-coordination" / "PLAN.md"
        if not plan_path.exists():
            self.skipTest("team-agent-coordination private plan is not present")
        plan = _read(plan_path)
        self.assertNotIn("committed + pushed via `cd ~/Development/ai && git add -A && git commit && git push`", plan)
        for phrase in [
            "every change to a skill in `~/Development/ai/skills/` is a publish action",
            "update the owning PLAN.md Progress/Tasks or Drift Log",
            "ledger-emit.sh --event publish",
            "concise summary, plan task id, plan path, proof, handoff status, resume, file, and claim fields",
            "commit + push from `~/Development/ai`",
            "ledger eid carried into the handoff",
        ]:
            self.assertIn(phrase, plan)

    def test_project_atomic_claim_protocols_are_publish_propagated(self):
        """Active project claim instructions must not teach plan-silent claim pushes."""
        required_paths = [
            ROOT / "projects" / "agentic-command-center" / "PLAN.md",
            ROOT / "projects" / "moussey-voice-agent" / "PLAN.md",
            ROOT / "projects" / "moussey-voice-agent" / "INBOX.md",
        ]
        if not all(path.exists() for path in required_paths):
            self.skipTest("private project claim plans are not present")
        command_center = _read(required_paths[0])
        voice_plan = _read(required_paths[1])
        voice_inbox = _read(required_paths[2])
        combined = "\n".join([command_center, voice_plan, voice_inbox])

        for stale_phrase in [
            "Pull → claim → push → ship → mark completed.",
            'git add PLAN.md && git commit -m "voice-agent: claim <V#>" && git push',
            "commit + push (`cd ~/Development/vidux && git add projects/moussey-voice-agent/PLAN.md",
            "repo commit",
            "repo commit + push",
            "the plan file is the only state",
            "Claims board (live — claim atomically and push)",
            "Atomic\nclaim: edit [pending] → [in_progress] [owner: <claude|codex>] and push.",
            "First-pusher wins.",
        ]:
            self.assertNotIn(stale_phrase, combined)

        goal_prompt = command_center[
            command_center.index("## The Goal Prompt") :
            command_center.index("## Five layers of the stack")
        ]
        for phrase in [
            "ledger-emit.sh --event publish",
            "plan task id",
            "plan path",
            "proof",
            "handoff_status=in_progress",
            "changed/claimed plan path",
            "next-agent resume",
            "First publish-propagated claimer wins",
            "publish ledger row",
            "repo diff/PR transport after owning-plan plus",
            "publish-ledger propagation",
        ]:
            self.assertIn(phrase, goal_prompt)

        output_stack = command_center[
            command_center.index("│ OUTPUT") :
            command_center.index("│ COORDINATION")
        ]
        self.assertIn("repo diff/PR transport after plan + publish ledger", output_stack)

        parent_protocol = command_center[
            command_center.index("## Two-agent coordination (across all sub-projects)") :
            command_center.index("**Strength alignment, fleet-wide:**")
        ]
        for phrase in [
            "Same atomic-claim protocol everywhere",
            "ledger-emit.sh --event publish",
            "plan task id",
            "plan path",
            "proof",
            "`handoff_status=in_progress`",
            "changed/claimed plan path",
            "next-agent resume point",
            "First publish-propagated claimer wins",
            "matching publish ledger row",
        ]:
            self.assertIn(phrase, parent_protocol)

        for text in [voice_plan, voice_inbox]:
            for phrase in [
                "ledger-emit.sh --event publish",
                "plan task id",
                "plan path",
                "proof",
                "`handoff_status=in_progress`",
                "changed/claimed plan path",
                "next-agent resume point",
                "publish ledger row",
            ]:
                self.assertIn(phrase, text)

    def test_ready_pr_flow_emits_publish_before_push(self):
        """Branch-push recipes must update plan and emit publish ledger before push."""
        flow = _read(ROOT / "guides" / "draft-pr-flow.md")
        first_ledger_emit = flow.index("ledger-emit.sh")
        first_push = flow.index("git push origin HEAD")
        self.assertLess(first_ledger_emit, first_push)
        for stale_phrase in [
            "Pull requests on GitHub are the durable manifest",
            "Each open PR is a recoverable unit of work",
            "record the failed PR creation in PLAN.md/memory.md",
        ]:
            self.assertNotIn(stale_phrase, flow)
        for phrase in [
            "Update the owning PLAN.md",
            "owning PLAN.md plus matching publish ledger row is the durable shipped-work recovery packet",
            "Pull requests on GitHub are transport/review handles",
            "`gh pr list` shows which branch-backed work needs review or nursing",
            "--event publish",
            "--summary",
            "--task-id",
            "--plan-path",
            "--handoff-status",
            "--resume",
            "--claim",
            "path-like files claimed/claims",
            "--claim \"<path-like-claimed-file>\"",
            "--file-claimed \"<path-like-claimed-file>\"",
            "$LEDGER_EID",
            "--review-pass \"invariant-audit:pass",
            "--review-pass \"regression-runner:pass",
            "--review-pass \"adversarial-reviewer:pass",
            "gh pr create` fails",
            "Each open PR is a transport/review handle",
            "Before checkout, read the PR body for its plan path and ledger eid",
            "then re-read the owning plan plus matching publish ledger row",
            "record the failed PR creation in the owning PLAN.md",
            "memory.md` only as a lane-local note",
        ]:
            self.assertIn(phrase, flow)

    def test_hook_install_docs_require_publish_ledger(self):
        """Hook installs must be plan+ledger propagated before copying hooks."""
        docs = "\n".join(
            [
                _read(ROOT / "docs" / "guide" / "installation.md"),
                _read(ROOT / "docs" / "reference" / "hooks.md"),
            ]
        )
        first_emit = docs.index("ledger-emit.sh")
        first_copy = docs.index("cp hooks/pre-commit-plan-check.sh")
        self.assertLess(first_emit, first_copy)
        for phrase in [
            "Before copying or enabling hooks",
            "summary, task id that matches the plan row, existing owning `PLAN.md` path, proof, handoff status, next-agent resume, path-like existing/git-known changed file, and matching claim coverage",
            "updated `PLAN.md` as both `--file` and `--claim`",
            "emit the final `done` row with copied hook paths once they exist",
            "--event publish",
            "--summary \"Planned Vidux planning hook install\"",
            "--repo-path /path/to/your/project",
            "--task-id hook-install",
            "--plan-path /path/to/your/project/PLAN.md",
            "--proof",
            "--handoff-status needs_review",
            "--resume",
            "--file /path/to/your/project/PLAN.md",
            "--claim /path/to/your/project/PLAN.md",
            "--skills vidux",
        ]:
            self.assertIn(phrase, docs)

    def test_team_coordination_release_gate_names_resume_packet(self):
        """Team-agent release gate summary must match the current release packet."""
        plan_path = ROOT / "projects" / "team-agent-coordination" / "PLAN.md"
        if not plan_path.exists():
            self.skipTest("team-agent-coordination private plan is not present")
        plan = _read(plan_path)
        row_start = plan.index("T10: **Vidux release publish gate**")
        row_end = plan.index("- [completed] T11:", row_start)
        row = plan[row_start:row_end]
        for phrase in [
            "owning plan, proof, and next-agent resume",
            "proof, handoff status, files claimed, and resume",
            "before `git push origin main --tags`",
            "final publish ledger row after push success",
            "root task 5.3.0u",
        ]:
            self.assertIn(phrase, row)

    def test_secondary_publish_recipes_require_publish_before_push(self):
        """Secondary fleet recipes must not drift from the ready-PR publish invariant."""
        fleet = _read(ROOT / "guides" / "fleet-ops.md")
        recipe = _read(ROOT / "guides" / "recipes" / "lane-prompt-patterns.md")

        for stale_phrase in [
            "leave durable state as a branch + PR",
            "`gh pr list` is the durable recovery manifest",
            "open PRs are the durable recovery manifest",
            "The durable state is the branch + PR, not the local worktree.",
            "rely on `gh pr list` for recovery",
        ]:
            self.assertNotIn(stale_phrase, fleet)

        self.assertLess(
            fleet.index("ledger-emit.sh --event publish"),
            fleet.index("If work is complete and tests pass: push branch"),
        )
        for phrase in [
            "update the owning PLAN.md",
            "ledger-emit.sh --event publish",
            "--summary",
            "--task-id",
            "--plan-path",
            "--handoff-status",
            "--resume",
            "--file",
            "--claim",
            "$LEDGER_EID",
            "three `--review-pass` self-scrutiny entries",
            "handoff_status=in_progress",
            "needs_review",
        ]:
            self.assertIn(phrase, fleet)
        pr_body_sentence = (
            "build the PR body with `scripts/vidux-pr-body.py` including "
            "`--summary`, `--plan-path`, `--proof`, `--handoff-status`, "
            '`--ledger "$LEDGER_EID"`, `--file-claimed`, `--resume`'
        )
        self.assertIn(pr_body_sentence, fleet)

        self.assertLess(
            recipe.index("Before pushing a branch"),
            recipe.index("Before `gh pr create`"),
        )
        for phrase in [
            "update the owning PLAN.md",
            "ledger-emit.sh --event publish",
            "--summary",
            "--task-id",
            "--plan-path",
            "--handoff-status",
            "--resume",
            "--file",
            "--claim",
            "$LEDGER_EID",
            '--ledger "$LEDGER_EID"',
            "three `--review-pass` entries",
            "Self-Scrutiny",
        ]:
            self.assertIn(phrase, recipe)

    def test_harness_and_fleet_ops_use_plan_ledger_recovery(self):
        """Harness/fleet ops docs must not collapse recovery to plan-only or PR-only state."""
        harness = _read(ROOT / "guides" / "harness.md")
        fleet = _read(ROOT / "guides" / "fleet-ops.md")
        operations = _read(ROOT / "docs" / "fleet" / "operations.md")
        combined = "\n".join([harness, fleet, operations])
        normalized = " ".join(combined.split())

        for stale_phrase in [
            "PLAN.md is the STATE.",
            "state lives in PLAN.md.",
            "leave durable state as a branch + PR",
            "`gh pr list` is the durable recovery manifest",
            "open PRs are the durable recovery manifest",
            "Open automation PRs are the durable recovery manifest",
            "The durable state is the branch + PR, not the local worktree.",
            "rely on `gh pr list` for recovery",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "The owning PLAN.md is the queue/planning authority",
            "matching publish ledger rows carry shipped-work proof/resume",
            "state orientation lives in the owning PLAN.md plus matching publish ledger rows",
            "durable handoff packet before the local worktree is discarded",
            "owning PLAN.md update plus publish ledger row first",
            "transport/review recovery index",
            "owning PLAN.md plus matching publish ledger row remains the durable shipped-work recovery packet",
            "branch + PR are the transport and review handles",
            "plan/ledger packet plus `gh pr list` for transport recovery",
            "open automation PRs are transport/review handles",
        ]:
            self.assertIn(phrase, normalized)

    def test_codex_runtime_recipes_scope_memory_to_lane_log(self):
        """Codex-native recipes must not make memory.md the shipped-work checkpoint."""
        runtime = _read(ROOT / "guides" / "recipes" / "codex-runtime.md")
        setup = _read(ROOT / "docs" / "fleet" / "codex-setup.md")
        patterns = _read(ROOT / "guides" / "recipes" / "lane-prompt-patterns.md")
        combined = "\n".join([runtime, setup, patterns])
        normalized = " ".join(combined.split())

        for stale_phrase in [
            "checkpoints to memory.md",
            "Append one line to memory.md at the end.",
            "Write prompt.md + memory.md → disk (lane state",
            "Write prompt.md + memory.md → disk (shared lane state)",
            "Lane state (prompt.md + memory.md) lives under a shared",
            "After the first fire, `tail -1 $LANE_DIR/memory.md` shows a cycle checkpoint",
            "8. Checkpoint   — one-line memory.md format with valid tags.",
            "**Signal-only checkpoint vs full checkpoint.**",
            "Lanes pick up from `memory.md` on the next fire.",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "records a lane-local memory note",
            "updates the owning plan plus matching publish ledger row before any commit/push transport",
            "lane-local cycle log",
            "Shipped-cycle proof and resume metadata still live in the owning `PLAN.md` plus matching publish ledger row",
            "Record the lane-local memory note, and for shipped work update the owning PLAN.md plus matching publish ledger row before any commit/push.",
            "After the first fire, `tail -1 $LANE_DIR/memory.md` shows a lane-local cycle note",
            "owning `PLAN.md` plus publish ledger row carries the proof/resume packet",
            "lane-local memory format plus plan/ledger publish packet for shipped work",
            "owning PLAN.md update plus matching `ledger-emit.sh --event publish` row carries the durable proof",
            "Signal-only lane note vs full publish checkpoint",
            "shipped work still needs the owning PLAN.md plus publish ledger packet",
        ]:
            self.assertIn(phrase, normalized)

    def test_fleet_lifecycle_docs_share_config_doctor_signpost_contract(self):
        """Fleet docs must describe one config/doctor/signpost lifecycle spine."""
        docs = {
            "index": _read(ROOT / "docs" / "fleet" / "index.md"),
            "platforms": _read(ROOT / "docs" / "fleet" / "platforms.md"),
            "claude": _read(ROOT / "docs" / "fleet" / "claude-lifecycle.md"),
            "codex": _read(ROOT / "docs" / "fleet" / "codex-lifecycle.md"),
            "setup": _read(ROOT / "docs" / "fleet" / "codex-setup.md"),
            "operations": _read(ROOT / "docs" / "fleet" / "operations.md"),
            "readme": _read(ROOT / "README.md"),
        }
        combined = "\n".join(docs.values())
        normalized = " ".join(combined.split())

        self.assertNotIn("Never both at once", docs["readme"])
        for phrase in [
            "Shared lifecycle spine",
            "Shared lifecycle contract",
            "Lifecycle observability",
            "vidux config check --json",
            "scripts/vidux-doctor.sh --json",
            "VIDUX_SIGNPOST_RUN_ID",
            "hook.beforeTask",
            "subagent.spawn",
            "task.verify",
            "hook.afterTask",
            "VIDUX_RUNTIME=claude",
            "VIDUX_RUNTIME=codex",
            "VIDUX_RUNTIME=cursor",
            "vidux signpost lifecycle-smoke --json",
            "vidux signpost spawned-subagent-smoke --json",
            "vidux signpost trace --run-id",
            "publish ledger row",
            "not proof that Claude, Codex, or Cursor actually launched",
        ]:
            self.assertIn(phrase, normalized)

    def test_docs_bug_sweep_matches_current_command_setup_browser_surfaces(self):
        """Reference docs must match current command, setup, browser, and helper surfaces."""
        command = _read(ROOT / "commands" / "vidux.md")
        command_ref = _read(ROOT / "docs" / "reference" / "commands.md")
        setup = _read(ROOT / "SETUP_NEW_MACHINE.md")
        readme = _read(ROOT / "README.md")
        browser = _read(ROOT / "docs" / "reference" / "browser.md")
        checkpoint = _read(ROOT / "scripts" / "vidux-checkpoint.sh")
        normalized_command = " ".join(command.split())
        normalized_command_ref = " ".join(command_ref.split())
        normalized_readme = " ".join(readme.split())

        for stale_phrase in [
            "The plan is truth",
            "commit cleanly",
            "Commit the plan/doc/code delta",
            "vidux-checkpoint.sh --status done|done_with_concerns|blocked",
        ]:
            self.assertNotIn(stale_phrase, command)

        for phrase in [
            "owning `PLAN.md` is queue and planning authority",
            "matching publish ledger rows carry shipped-cycle proof",
            "vidux config check --json",
            "missing live config distinct from the checked-in example fallback",
            "task id, proof, handoff status, files claimed, path-like claims, and next-agent resume",
            "[--outcome <useful|busy|blocked_clarified>]",
            "Commit or push only after the plan/ledger packet exists",
        ]:
            self.assertIn(phrase, normalized_command)

        for phrase in [
            "redacted inbox-source metadata",
            "Resolve config with `vidux config check --json`",
            "vidux http-smoke --json --timeout 3",
            "`warn_partial`",
            "`fail_budget`",
            "JSON `ok` follows the hard-fail exit status",
            "`strict_ok` is false when",
        ]:
            self.assertIn(phrase, normalized_command_ref)

        for phrase in [
            "vidux http-smoke --json --timeout 3",
            "observe-only route budget checks",
            "`warn_partial`",
            "`fail_budget`",
        ]:
            self.assertIn(phrase, normalized_readme)

        self.assertIn("owning PLAN.md plus matching publish ledger rows", setup)
        self.assertIn("~/.agent-ledger/activity.jsonl", setup)
        self.assertIn("repo-local .agent-ledger/ is companion state only when documented", setup)
        self.assertNotIn("PLAN.md, CLAUDE.md, .agent-ledger/activity.jsonl", setup)
        self.assertNotIn("Use Codex CLI for Vidux work, not the desktop app", setup)

        for route in [
            "GET /receipts",
            "GET /api/receipts/list",
            "GET /api/receipts/<id>/image",
            "POST /api/upload-ref-audio",
            "POST /api/receipts/upload",
            "POST /api/receipts/<id>/tag",
            "POST /api/receipts/<id>/ocr",
            "POST /api/receipts/<id>/expected",
            "POST /api/receipts/<id>/delete",
            "POST /api/receipts/<id>/analyze",
            "Receipt writes, receipt OCR/analyze mutations, and read-aloud reference-audio upload are loopback-only JSON writes",
        ]:
            self.assertIn(route, browser)

        self.assertIn("[--outcome <useful|busy|blocked_clarified>]", checkpoint)

    def test_loop_checkpoint_wording_requires_publish_propagation(self):
        """The loop guide must not describe raw git commit as the checkpoint."""
        loop = _read(ROOT / "LOOP.md")
        normalized = " ".join(loop.split())
        self.assertNotIn("Git commit is the checkpoint", loop)
        self.assertNotIn("not git push", loop)
        self.assertNotIn("CHECKPOINT commit", loop)
        self.assertNotIn("Commit + push", loop)
        self.assertNotIn('Commit: "vidux:', loop)
        self.assertNotIn("plan and ledger checkpoint", loop)
        for phrase in [
            "CHECKPOINT plan + ledger",
            "publish branch/PR when propagated",
            "A commit is a local code snapshot",
            "PLAN.md update plus `ledger-emit.sh --event publish`",
            "Ledger: publish row carries proof, handoff_status",
            "Git: commit/push branch only after the plan/ledger packet exists.",
            "Plan update + publish ledger row + resume",
            "`handoff_status`",
            "summary",
            "files claimed",
            "next-agent resume",
            "ledger eid",
            "branch/PR/release handoff",
        ]:
            self.assertIn(phrase, normalized)

    def test_top_level_recipes_require_publish_propagation(self):
        """The top-level recipes guide must not teach plan-silent publish paths."""
        recipes = _read(ROOT / "guides" / "recipes.md")
        self.assertNotIn("commit directly to main", recipes)
        self.assertLess(
            recipes.index("ledger-emit.sh --event publish"),
            recipes.index("git push -u origin claude/skill-refine-<name>"),
        )
        self.assertLess(
            recipes.index("ledger-emit.sh --event publish"),
            recipes.index("gh pr create --title \"skill(<name>): <improvement>\""),
        )
        for phrase in [
            "Identify the owning PLAN.md row before editing",
            "Update the owning PLAN.md Progress/Tasks or Drift Log",
            "--plan-path",
            "--task-id",
            "--summary",
            "--proof",
            "--handoff-status done",
            "--resume",
            "--file",
            "--claim",
            "--skills vidux,ledger",
            "self-scrutiny",
            "three `--review-pass` entries",
            "--body-file /tmp/vidux-pr-body.md",
            "any commit, push, or PR is a publish",
            "Keep the publish ledger eid with the branch/PR handoff",
        ]:
            self.assertIn(phrase, recipes)

    def test_claude_md_rules_keep_publish_propagation(self):
        """Copyable CLAUDE.md rules must not make trunk merge the only done signal."""
        recipe = _read(ROOT / "guides" / "recipes" / "claude-md-rules.md")
        self.assertNotIn(
            "Tier 2 (direct-to-main, merge to trunk): session-scope authorization required.",
            recipe,
        )
        self.assertNotIn("A change isn't\ndone until it's merged back to trunk.", recipe)
        self.assertNotIn(
            "A change isn't done until merged to trunk.",
            recipe,
        )
        self.assertLess(
            recipe.index("ledger-emit.sh --event publish"),
            recipe.index("Never use --no-verify"),
        )
        for phrase in [
            "same publish propagation before the push/merge",
            "Every commit, push, PR, direct-to-main update, or trunk merge is a publish",
            "update the owning PLAN.md Progress/Tasks or Drift Log first",
            "--plan-path <PLAN.md>",
            "--task-id <task-id>",
            "--summary \"<summary>\"",
            "--proof",
            "--handoff-status <done|in_progress|blocked|needs_review>",
            "--resume \"<resume point>\"",
            "--file <changed-file>",
            "--claim <claimed-file>",
            "Carry the ledger eid",
            "--resume",
            "A merge back to\ntrunk is not enough by itself",
            "publish ledger row with proof, handoff status, files claimed, and next-agent resume",
        ]:
            self.assertIn(phrase, recipe)

    def test_checkpoint_residue_recipes_scope_memory_to_lane_notes(self):
        """Copyable checkpoint snippets must not make memory.md the shipped-work truth."""
        prompt_template = _read(ROOT / "docs" / "reference" / "prompt-template.md")
        recipes = _read(ROOT / "guides" / "recipes.md")
        claude_rules = _read(ROOT / "guides" / "recipes" / "claude-md-rules.md")
        combined = "\n".join([prompt_template, recipes, claude_rules])
        normalized = " ".join(combined.split())

        for stale_phrase in [
            "Append one line to memory.md:",
            "checkpoint failure reason to memory.md",
            "State lives on disk (PLAN.md, memory.md), not in context.",
        ]:
            self.assertNotIn(stale_phrase, combined)

        for phrase in [
            "lane-local memory note plus publish packet fields for shipped work",
            "Append one lane-local line to memory.md:",
            "record lane-local failure reason in memory.md",
            "update the owning PLAN.md plus ledger handoff",
            "State orientation lives on disk: PLAN.md plus publish ledger rows carry shipped-work truth",
            "memory.md is the lane-local cycle log",
        ]:
            self.assertIn(phrase, normalized)

    def test_automation_guide_scopes_memory_to_lane_notes(self):
        """Automation guide must keep memory.md lane-local, not shipped-work truth."""
        guide = _read(ROOT / "guides" / "automation.md")
        normalized = " ".join(guide.split())

        for stale_phrase in [
            "State can live on disk (PLAN.md, memory.md, ledger) between fires",
            "memory.md   (durable state)",
            "the lane resumes from memory.md tail",
            "| **Cold** (durable) | PLAN.md, evidence/, investigations/, memory.md per lane, `.agent-ledger/activity.jsonl`",
            "CHECKPOINT   — Format for the memory.md entry on exit.",
        ]:
            self.assertNotIn(stale_phrase, guide)

        for phrase in [
            "State orientation can live on disk",
            "memory.md (lane-local cycle log)",
            "shipped-work proof never lives here alone",
            "reads memory.md for lane-local orientation",
            "owning PLAN.md plus publish ledger rows for shipped-work proof",
            "publish ledger rows, lane-local memory.md notes",
            "lane-local memory.md note, plus publish packet when work ships",
            "owning PLAN.md plus publish ledger row carries proof and resume metadata",
        ]:
            self.assertIn(phrase, normalized)

    def test_placeholder_draft_prs_are_publish_actions(self):
        """Core placeholder draft PR doctrine must keep plan and ledger propagation."""
        text = _read(SKILL)
        section = text[text.index("### Placeholder draft PRs over blocked exits") :]
        self.assertLess(
            section.index("owning PLAN.md Progress/Tasks or Drift Log"),
            section.index("gh pr create --draft"),
        )
        self.assertLess(
            section.index("ledger-emit.sh --event publish"),
            section.index("gh pr create --draft"),
        )
        for phrase in [
            "A placeholder draft PR is still a publish action",
            "handoff_status=needs_review",
            "--summary",
            "--task-id",
            "--plan-path",
            "--proof",
            "--handoff-status needs_review",
            "--resume",
            "--file",
            "--claim",
            "carry that ledger eid into the PR body",
        ]:
            self.assertIn(phrase, section)

    # -----------------------------------------------------------------------
    # Cross-doc consistency
    # -----------------------------------------------------------------------

    # test_skill_has_fifty_thirty_twenty — removed in v3 (50/30/20 split removed)

    def test_doctrine_principles_match_skill(self):
        """SKILL.md principles must cover plan-first and process-fix concepts."""
        skill = _read(SKILL)
        s_p1 = re.search(r"###\s+1\.\s+Plan.*?(?=^###\s+2\.)", skill, re.DOTALL | re.MULTILINE)
        self.assertIsNotNone(s_p1, "SKILL.md missing principle 1 (Plan first)")
        self.assertIn("planning authority", s_p1.group())
        self.assertIn("publish packet", s_p1.group())
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
        internal_terms = ["Phantom", "Bazel", "internal-bridge-tool", "COF", "CameraMusicFeature"]
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
        """vidux.config.example.json must exist and have required keys.

        Test migrated from vidux.config.json to vidux.config.example.json on
        2026-05-14 — the live config file is now gitignored (user-local, not
        source). The example file is the durable schema artifact.
        """
        config_path = ROOT / "vidux.config.example.json"
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
        for key in ("hot_tasks", "runnable_tasks", "cold_tasks", "context_warning", "context_note"):
            self.assertIn(key, data)
        self.assertIsInstance(data["hot_tasks"], int)
        self.assertIsInstance(data["runnable_tasks"], int)
        self.assertIsInstance(data["cold_tasks"], int)
        self.assertIsInstance(data["context_warning"], bool)
        self.assertIsInstance(data["context_note"], str)

    def test_vidux_loop_early_exits_expose_handoff_contract(self):
        """No-task reduce paths must still tell next agents how to checkpoint."""
        cases = {
            "empty": """\
                # Empty Plan
                ## Purpose
                Needs task creation.
                ## Progress
            """,
            "done": """\
                # Done Plan
                ## Purpose
                Needs idle scan.
                ## Tasks
                - [completed] Task 1: Done already. [Evidence: test]
                ## Progress
            """,
            "all_blocked": """\
                # Blocked Plan
                ## Tasks
                - [blocked] Task 1: Waiting on human input. [Evidence: test]
                ## Progress
            """,
            "exit_criteria_pending": """\
                # Criteria Plan
                ## Tasks
                - [completed] Task 1: Done already. [Evidence: test]
                ## Exit Criteria
                - [ ] Proof artifact attached
                ## Progress
            """,
        }

        for expected_type, plan_text in cases.items():
            with self.subTest(expected_type=expected_type):
                data = self._run_loop_on(plan_text)
                self.assertEqual(data["type"], expected_type)
                self.assertIn("handoff_contract", data)
                self.assertIn("reduce_contract", data)
                self.assertTrue(data["handoff_contract"]["handoff_required"])
                self.assertTrue(data["handoff_contract"]["meter_checkpoint_required"])
                self.assertIn("next_agent_resume", data["handoff_contract"]["required_fields"])
                self.assertTrue(data["reduce_contract"]["read_only"])

    def test_vidux_loop_archive_pressure_is_read_only(self):
        """Reduce mode must warn about archive pressure without mutating plan files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "PLAN.md"
            completed = "\n".join(
                f"- [completed] Task C{i}: Done already. [Evidence: test]"
                for i in range(220)
            )
            plan.write_text(
                textwrap.dedent(
                    f"""\
                    # Test Plan
                    ## Tasks
                    {completed}
                    - [pending] Task P1: Keep working. [Evidence: source]
                    ## Progress
                    """
                ),
                encoding="utf-8",
            )
            before = plan.read_text(encoding="utf-8")

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(plan)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data["context_warning"])
            self.assertIn("read-only", data["context_note"])
            self.assertIn("archive explicitly", data["context_note"])
            self.assertNotIn("Auto-archived", data["context_note"])
            self.assertEqual(plan.read_text(encoding="utf-8"), before)
            self.assertFalse((Path(tmpdir) / "ARCHIVE.md").exists())

    def test_vidux_loop_read_mode_does_not_emit_loop_start_ledger(self):
        """Reduce mode must not append telemetry rows unless explicitly opted in."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "PLAN.md"
            ledger = Path(tmpdir) / "activity.jsonl"
            ledger.write_text("", encoding="utf-8")
            plan.write_text(
                textwrap.dedent(
                    """\
                    # Test Plan
                    ## Tasks
                    - [pending] Task P1: Read the plan. [Evidence: fixture]
                    ## Progress
                    """
                ),
                encoding="utf-8",
            )
            before = ledger.read_text(encoding="utf-8")
            env = os.environ.copy()
            env["VIDUX_LEDGER_FILE"] = str(ledger)
            env.pop("VIDUX_LOOP_EMIT_READ_LEDGER", None)

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(plan)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data["reduce_contract"]["read_only"])
            self.assertTrue(data["ledger_available"])
            self.assertEqual(ledger.read_text(encoding="utf-8"), before)

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
        import tempfile
        import os
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
        import tempfile
        import os
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
        import tempfile
        import os
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

    def test_vidux_loop_stuck_counts_task_id_mentions(self):
        """Compact task IDs in Progress must count toward stuck detection."""
        import tempfile
        import os
        plan_stuck = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            ## Progress
            - [2026-01-01] T2/T8 refresh checked the current LaunchAgent state. Next: wait for scheduled proof.
            - [2026-01-02] T2 live-status remained deferred. Next: inspect cron output.
            - [2026-01-03] T2 scheduled proof still did not satisfy acceptance. Next: surface switch.
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_stuck)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data["stuck"], "Expected stuck=true for compact task ID references")
            self.assertEqual(data["action"], "stuck")
            self.assertIn("3", data["context"])
        finally:
            os.unlink(tmp)

    def test_vidux_loop_task_id_stuck_uses_token_boundaries(self):
        """T2 must not count T20/T21/T22 as Progress mentions."""
        import tempfile
        import os
        plan_not_stuck = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            ## Progress
            - [2026-01-01] T20 reviewed an unrelated lane. Next: keep going.
            - [2026-01-02] T21 reviewed an unrelated lane. Next: keep going.
            - [2026-01-03] T22 reviewed an unrelated lane. Next: keep going.
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_not_stuck)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertFalse(data["stuck"], "Expected stuck=false when only longer task IDs match")
        finally:
            os.unlink(tmp)

    def test_vidux_loop_read_mode_reports_stuck_without_auto_blocking(self):
        """Read-only reduce mode must not rewrite stuck in-progress tasks."""
        task = "Task S1: keep trying the same path [Evidence: fixture]"
        plan_stuck = textwrap.dedent(f"""\
            # Test Plan
            ## Tasks
            - [in_progress] {task}
            ## Progress
            - [2026-01-01] Cycle 1: Done: {task}. Next: check plan.
            - [2026-01-02] Cycle 2: Done: {task}. Next: check plan.
            - [2026-01-03] Cycle 3: Done: {task}. Next: check plan.
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "PLAN.md"
            plan.write_text(plan_stuck, encoding="utf-8")
            before = plan.read_text(encoding="utf-8")

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(plan)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data["stuck"], "Expected stuck=true for task with 3+ Progress entries")
            self.assertFalse(data["auto_blocked"])
            self.assertEqual(data["action"], "stuck")
            self.assertEqual(plan.read_text(encoding="utf-8"), before)
            self.assertNotIn("[blocked]", before)
            self.assertNotIn("[STUCK]", plan.read_text(encoding="utf-8"))

    def test_vidux_loop_stuck_surfaces_next_unblocked_task(self):
        """A stuck row must expose the next runnable surface without mutating the plan."""
        plan_stuck = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            - [in_progress] T8: Disk-pressure cleanup [Evidence: source]
            - [pending] T9: Later cleanup audit [Evidence: source]
            ## Progress
            - [2026-01-01] T2/T8 refresh checked the current LaunchAgent state. Next: wait for scheduled proof.
            - [2026-01-02] T2 live-status remained deferred. Next: inspect cron output.
            - [2026-01-03] T2 scheduled proof still did not satisfy acceptance. Next: surface switch.
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "PLAN.md"
            plan.write_text(plan_stuck, encoding="utf-8")
            before = plan.read_text(encoding="utf-8")

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(plan)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data["stuck"])
            self.assertEqual(data["action"], "stuck")
            self.assertEqual(data["next_action"], "surface_switch")
            self.assertTrue(data["surface_switch"]["available"])
            self.assertIn("T8", data["surface_switch"]["task"])
            self.assertGreater(data["surface_switch"]["line"], 0)
            self.assertEqual(data["runnable_tasks"], 2)
            self.assertEqual(plan.read_text(encoding="utf-8"), before)

    def test_vidux_loop_stuck_surface_switch_skips_owner_gated_task(self):
        """A stuck row must not surface-switch to an owner-gated cleanup row."""
        plan_stuck = textwrap.dedent("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            - [in_progress] T8: Disk-pressure cleanup before broad builds. [Partial Evidence: ownership review records current read-only classifications and non-removable worktrees. Non-claim: no deletion, no branch removal, no process kill.] [Evidence: source]
            - [pending] T9: Later cleanup audit [Evidence: source]
            ## Progress
            - [2026-01-01] T2/T8 refresh checked the current LaunchAgent state. Next: wait for scheduled proof.
            - [2026-01-02] T2 live-status remained deferred. Next: inspect cron output.
            - [2026-01-03] T2 scheduled proof still did not satisfy acceptance. Next: surface switch.
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "PLAN.md"
            plan.write_text(plan_stuck, encoding="utf-8")
            before = plan.read_text(encoding="utf-8")

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), str(plan)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, f"vidux-loop.sh failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data["stuck"])
            self.assertEqual(data["next_action"], "surface_switch")
            self.assertTrue(data["surface_switch"]["available"])
            self.assertIn("T9", data["surface_switch"]["task"])
            self.assertNotIn("T8", data["surface_switch"]["task"])
            self.assertEqual(plan.read_text(encoding="utf-8"), before)

    def test_vidux_loop_stuck_surface_switch_skips_dependency_gated_task(self):
        """A stuck row must not surface-switch to a dependency-gated alternate row."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            - [pending] T8: Build cleanup packet after upstream proof [Evidence: source] [Depends: T7]
            - [pending] T7: Upstream proof blocked until scheduled launch-loop evidence [Evidence: source]
            - [pending] T9: Independent audit [Evidence: source]
            ## Progress
            - [2026-01-01] T2 refresh checked the current LaunchAgent state. Next: wait for scheduled proof.
            - [2026-01-02] T2 live-status remained deferred. Next: inspect cron output.
            - [2026-01-03] T2 scheduled proof still did not satisfy acceptance. Next: surface switch.
        """)
        self.assertTrue(data["stuck"])
        self.assertEqual(data["next_action"], "surface_switch")
        self.assertTrue(data["surface_switch"]["available"])
        self.assertIn("T9", data["surface_switch"]["task"])
        self.assertNotIn("T8", data["surface_switch"]["task"])
        self.assertNotIn("T7", data["surface_switch"]["task"])

    def test_vidux_loop_stuck_surface_switch_none_without_candidate(self):
        """A stuck row with no alternate runnable task must not invent a route."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            ## Progress
            - [2026-01-01] T2 refresh checked the current LaunchAgent state. Next: wait for scheduled proof.
            - [2026-01-02] T2 live-status remained deferred. Next: inspect cron output.
            - [2026-01-03] T2 scheduled proof still did not satisfy acceptance. Next: surface switch.
        """)
        self.assertTrue(data["stuck"])
        self.assertEqual(data["action"], "stuck")
        self.assertEqual(data["next_action"], "none")
        self.assertFalse(data["surface_switch"]["available"])
        self.assertEqual(data["surface_switch"]["task"], "")
        self.assertEqual(data["surface_switch"]["line"], 0)
        self.assertEqual(data["hot_tasks"], 1)
        self.assertEqual(data["runnable_tasks"], 0)

    def test_vidux_loop_runnable_tasks_excludes_stuck_row_but_counts_candidate(self):
        """Runnable count must exclude stuck rows and keep independent alternates."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [in_progress] T2: Phase-shift LaunchAgents [Evidence: source]
            - [pending] T9: Independent audit [Evidence: source]
            ## Progress
            - [2026-01-01] T2 refresh checked the current LaunchAgent state. Next: wait for scheduled proof.
            - [2026-01-02] T2 live-status remained deferred. Next: inspect cron output.
            - [2026-01-03] T2 scheduled proof still did not satisfy acceptance. Next: surface switch.
        """)
        self.assertTrue(data["stuck"])
        self.assertEqual(data["next_action"], "surface_switch")
        self.assertTrue(data["surface_switch"]["available"])
        self.assertIn("T9", data["surface_switch"]["task"])
        self.assertEqual(data["hot_tasks"], 2)
        self.assertEqual(data["runnable_tasks"], 1)

    def test_vidux_loop_not_stuck_when_progress_has_2_entries(self):
        """stuck must be false when Progress section has only 2 entries for the task."""
        import tempfile
        import os
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
        import tempfile
        import os
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

    def test_checkpoint_emits_publish_ready_ledger_row(self):
        """checkpoint.sh commits must emit enough ledger data before git transport."""
        import tempfile
        task = "Task 1: publish propagation [Evidence: contract test]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [in_progress] {task}
                ## Progress
            """))
            ledger_path = Path(tmpdir) / "activity.jsonl"
            ledger_path.write_text("", encoding="utf-8")
            env = os.environ.copy()
            env["VIDUX_LEDGER_FILE"] = str(ledger_path)

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task,
                 "publish propagation proof"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir, env=env,
            )

            self.assertEqual(result.returncode, 0, f"checkpoint failed: {result.stderr}")
            lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1, f"expected one ledger row, got: {lines!r}")
            entry = json.loads(lines[0])
            plan_path = str(Path(plan).resolve())

            self.assertEqual(entry["event"], "vidux_checkpoint")
            self.assertEqual(entry["task_id"], "Task 1")
            # Harness Contract block 8 (convergence ladder): a checkpoint with no
            # merge SHA cannot certify a merge, so a legacy "done" demotes to the
            # honest rung `pr_open`. "done" is no longer a status word.
            self.assertEqual(entry["handoff_status"], "pr_open")
            self.assertEqual(entry["plan_path"], plan_path)
            self.assertEqual(
                entry["next_agent_resume"],
                f"Resume from {plan_path}; next: all tasks complete",
            )
            self.assertIn(plan_path, entry["files"])
            self.assertIn(plan_path, entry["files_claimed"])
            self.assertEqual(entry["lane"], "vidux-checkpoint")
            self.assertEqual(entry["publish_kind"], "checkpoint")
            self.assertNotIn("commit", entry)
            self.assertNotIn("commit=", entry["proof"])
            self.assertIn("plan=", entry["proof"])
            self.assertIn("task_id=Task 1", entry["proof"])
            commit_count = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(commit_count.stdout.strip(), "2")

    def test_handoff_status_convergence_ladder(self):
        """Harness Contract block 8: ledger handoff status is a convergence ladder
        (branch_pushed < pr_open < merged < findable); 'done' is not a status word
        and never overclaims a merge without a SHA."""
        emit = self.SCRIPTS_DIR / "lib" / "ledger-emit.sh"
        self.assertTrue(emit.exists(), f"missing {emit}")

        def status_for(arg: str, merge_sha: str = "") -> str:
            sha_clause = f"VIDUX_MERGE_SHA={merge_sha} " if merge_sha else ""
            script = f'source "{emit}"; {sha_clause}_vidux_handoff_status "{arg}"'
            res = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(res.returncode, 0, f"bash failed: {res.stderr}")
            return res.stdout.strip()

        # Ladder rungs pass through unchanged.
        self.assertEqual(status_for("branch_pushed"), "branch_pushed")
        self.assertEqual(status_for("pr_open"), "pr_open")
        self.assertEqual(status_for("merged"), "merged")
        self.assertEqual(status_for("findable"), "findable")
        # Legacy "done"/"completed" cannot certify a merge without a SHA -> honest rung.
        self.assertEqual(status_for("done"), "pr_open")
        self.assertEqual(status_for("completed"), "pr_open")
        # With a real merge SHA proving it, legacy "done" stamps the merged rung.
        self.assertEqual(status_for("done", merge_sha="abc1234"), "merged")
        # Non-ladder operational states are preserved.
        self.assertEqual(status_for("blocked"), "blocked")
        self.assertEqual(status_for("in_progress"), "in_progress")
        self.assertEqual(status_for("needs_review"), "needs_review")
        # Unknown input fails safe to needs_review (never to a convergence rung).
        self.assertEqual(status_for("garbage"), "needs_review")

    def test_checkpoint_ledger_failure_blocks_commit(self):
        """checkpoint.sh must not commit if the checkpoint ledger row cannot be written."""
        import tempfile
        task = "Task 1: publish propagation [Evidence: contract test]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [in_progress] {task}
                ## Progress
            """))
            ledger_path = Path(tmpdir) / "activity.jsonl"
            ledger_path.write_text("", encoding="utf-8")
            ledger_path.chmod(0o400)
            env = os.environ.copy()
            env["VIDUX_LEDGER_FILE"] = str(ledger_path)

            try:
                result = subprocess.run(
                    ["bash", str(self.SCRIPTS_DIR / "vidux-checkpoint.sh"), plan, task,
                     "publish propagation proof"],
                    capture_output=True, text=True, timeout=10, cwd=tmpdir, env=env,
                )
            finally:
                ledger_path.chmod(0o600)

            self.assertNotEqual(result.returncode, 0, "checkpoint should fail before commit")
            self.assertIn("ledger checkpoint emit failed", result.stderr)
            self.assertIn("git transport not attempted", result.stderr)
            self.assertNotIn("checkpoint not committed", result.stderr)
            commit_count = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertEqual(commit_count.stdout.strip(), "1")

    def test_checkpoint_helper_names_git_transport_failures_precisely(self):
        """Checkpoint helper stderr should not describe git failure as missing proof."""
        script = _read(ROOT / "scripts" / "vidux-checkpoint.sh")

        self.assertNotIn("checkpoint not committed", script)
        self.assertNotIn("checkpoint not saved", script)
        self.assertNotIn("failed commit means the checkpoint did not land", script)
        self.assertIn("ledger checkpoint emit failed - git transport not attempted", script)
        self.assertIn("git commit failed - git transport did not land", script)

    def test_loop_checkpoint_does_not_emit_stale_commit_proof(self):
        """vidux-loop.sh --checkpoint mutates PLAN.md but must not claim HEAD proof."""
        import tempfile
        task = "Task 1: loop checkpoint without commit [Evidence: contract test]"
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._make_git_plan(tmpdir, textwrap.dedent(f"""\
                # Test Plan
                ## Tasks
                - [in_progress] {task}
                ## Progress
            """))
            ledger_path = Path(tmpdir) / "activity.jsonl"
            ledger_path.write_text("", encoding="utf-8")
            env = os.environ.copy()
            env["VIDUX_LEDGER_FILE"] = str(ledger_path)

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-loop.sh"), plan, "--checkpoint"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir, env=env,
            )

            self.assertEqual(result.returncode, 0, f"loop checkpoint failed: {result.stderr}")
            self.assertIn("[completed]", Path(plan).read_text(encoding="utf-8"))

            status = subprocess.run(
                ["git", "status", "--short", "PLAN.md"],
                capture_output=True, text=True, timeout=10, cwd=tmpdir,
            )
            self.assertIn("M PLAN.md", status.stdout)

            entries = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            checkpoints = [entry for entry in entries if entry.get("event") == "vidux_checkpoint"]
            self.assertEqual(len(checkpoints), 1, f"expected one checkpoint row, got: {entries!r}")
            entry = checkpoints[0]
            plan_path = str(Path(plan).resolve())

            self.assertEqual(entry["task_id"], "Task 1")
            # Harness Contract block 8 (convergence ladder): no merge SHA in env ->
            # legacy "done" demotes to the honest rung `pr_open`, never overclaiming
            # a merge the checkpoint cannot prove.
            self.assertEqual(entry["handoff_status"], "pr_open")
            self.assertEqual(entry["plan_path"], plan_path)
            self.assertEqual(entry["next_agent_resume"], f"Resume from {plan_path}; next: check plan")
            self.assertIn(plan_path, entry["files"])
            self.assertIn(plan_path, entry["files_claimed"])
            self.assertEqual(entry["lane"], "vidux-checkpoint")
            self.assertEqual(entry["publish_kind"], "checkpoint")
            self.assertNotIn("commit", entry)
            self.assertNotIn("commit=", entry["proof"])
            self.assertIn("plan=", entry["proof"])
            self.assertIn("task_id=Task 1", entry["proof"])

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
        import tempfile
        import os
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
        import tempfile
        import os
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
        import tempfile
        import os
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
        import tempfile
        import shutil
        import os
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
        import tempfile
        import os
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
        import tempfile
        import os
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
        import tempfile
        import os
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

    def test_dep_prose_must_be_solved_first_blocks(self):
        """Explicit blocker prose in a [Depends:] row must route as blocked."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 2: Continue rollout [Evidence: src] [Depends: Wave 2 complete - but resplit gh pr create overlap issue must be solved first]
            ## Progress
        """)
        self.assertTrue(data["blocked"])
        self.assertEqual(data["action"], "blocked")
        self.assertEqual(data["context"], "Waiting on: resplit gh pr create overlap issue")
        self.assertTrue(data["handoff_contract"]["handoff_required"])
        self.assertTrue(data["handoff_contract"]["meter_checkpoint_required"])

    def test_dep_prose_blocker_beats_repeated_task_id_progress(self):
        """Repeated compact IDs must not override explicit dependency blockers."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] 5.3.1 Remaining automations. [Evidence: src] [Depends: Wave 2 complete - but resplit gh pr create overlap issue must be solved first]
            ## Progress
            - [2026-01-01] 5.3.1 remains parked on resplit overlap. Next: wait.
            - [2026-01-02] 5.3.1 remains parked on resplit overlap. Next: wait.
            - [2026-01-03] 5.3.1 remains parked on resplit overlap. Next: wait.
        """)
        self.assertTrue(data["blocked"])
        self.assertFalse(data["stuck"])
        self.assertEqual(data["action"], "blocked")
        self.assertEqual(data["context"], "Waiting on: resplit gh pr create overlap issue")
        self.assertEqual(data["hot_tasks"], 1)
        self.assertEqual(data["runnable_tasks"], 0)

    def test_runnable_tasks_excludes_dependency_and_section_gated_rows(self):
        """Runnable count must distinguish a hot-but-parked root queue from executable work."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            #### Wave 3 - Full fleet
            - [pending] 5.3.1 Remaining automations. [Evidence: src] [Depends: Wave 2 complete - but resplit gh pr create overlap issue must be solved first]
            - [pending] 5.3.2 Validate PR list [Evidence: src] [Depends: 5.3.1]
            #### Wave 4 - Lock the gate
            - [pending] 5.4.1 Branch protection [Evidence: src] [Depends: Wave 3 complete]
            - [pending] 5.4.2 Smoke test [Evidence: src] [Depends: 5.4.1]
            ## Progress
        """)
        self.assertTrue(data["blocked"])
        self.assertEqual(data["action"], "blocked")
        self.assertEqual(data["hot_tasks"], 4)
        self.assertEqual(data["runnable_tasks"], 0)

    def test_dep_negative_prose_not_blocked_by_does_not_block(self):
        """Negative prose must not trigger the explicit blocker classifier."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] Task 2: Continue rollout [Evidence: src] [Depends: Wave 2 complete; not blocked by review bots]
            ## Progress
        """)
        self.assertFalse(data["blocked"])

    def test_owner_gated_in_progress_task_blocks_resume(self):
        """Ownership-review prose must beat blind in_progress resume routing."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [in_progress] T8: Disk-pressure cleanup pending ownership review of non-removable worktrees. Next owner must review named PR/no-PR/dirty buckets before any cleanup class exists. [Evidence: src]
            ## Progress
        """)
        self.assertTrue(data["blocked"])
        self.assertEqual(data["action"], "blocked")
        self.assertEqual(data["next_action"], "none")
        self.assertIn("owner review", data["context"])
        self.assertTrue(data["handoff_contract"]["handoff_required"])
        self.assertTrue(data["handoff_contract"]["meter_checkpoint_required"])

    def test_owner_review_packet_work_is_not_owner_gated(self):
        """Executable owner-review tooling rows must not be blocked by the noun alone."""
        data = self._run_loop_on("""\
            # Test Plan
            ## Tasks
            - [pending] T8c: Worktree owner-review packet export [Evidence: src]
            ## Progress
        """)
        self.assertFalse(data["blocked"])
        self.assertEqual(data["action"], "execute")
        self.assertEqual(data["next_action"], "dispatch")

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

    def test_doctor_split_is_documented_for_cli_and_runtime_hooks(self):
        """Install doctor and runtime doctor must stay visibly separate."""
        help_result = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "help", "doctor"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("install/readiness doctor", help_result.stdout)
        self.assertIn("scripts/vidux-doctor.sh --json", help_result.stdout)
        self.assertIn("beforeTask/pre-hook probe", help_result.stdout)
        self.assertIn("2 for invalid usage", help_result.stdout)
        self.assertIn("N/TOTAL summary", help_result.stdout)

        runtime_doctor = _read(self.SCRIPTS_DIR / "vidux-doctor.sh")
        self.assertIn("Complements `vidux doctor`", runtime_doctor)
        self.assertIn("JSON-friendly runtime doctor", runtime_doctor)
        self.assertNotIn("vidux-install.sh doctor", runtime_doctor)

        install_doctor = _read(self.SCRIPTS_DIR / "vidux-doctor-cli.sh")
        self.assertIn("install/readiness doctor", install_doctor)
        self.assertIn("scripts/vidux-doctor.sh --json", install_doctor)
        self.assertIn("can be slow", install_doctor)

        scripts_ref = _read(ROOT / "docs" / "reference" / "scripts.md")
        self.assertIn("### Doctor split", scripts_ref)
        self.assertIn("beforeTask/pre-hook probe", scripts_ref)
        self.assertIn("VIDUX_DOCTOR_SKIP_NPM_TEST=1", scripts_ref)
        self.assertIn("`2` for invalid usage", scripts_ref)

        hooks_ref = _read(ROOT / "docs" / "reference" / "hooks.md")
        self.assertIn("not `vidux doctor`", hooks_ref)
        self.assertIn("may be slow when it runs `npm test`", hooks_ref)
        self.assertIn('called "scripts/vidux-doctor.sh --json"', hooks_ref)

    def test_install_doctor_skip_npm_fixture_is_machine_independent(self):
        """vidux doctor must be testable without real gh auth or npm test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            home = tmp / "home"
            fakebin = tmp / "bin"
            root = tmp / "vidux"
            scripts = root / "scripts"
            config_dir = home / ".config" / "vidux"
            for directory in (home / "Development", fakebin, scripts, config_dir):
                directory.mkdir(parents=True, exist_ok=True)

            token = config_dir / "fixture.token"
            token.write_text("redacted\n", encoding="utf-8")
            token.chmod(0o600)

            gh = fakebin / "gh"
            gh.write_text("#!/usr/bin/env bash\necho 'Logged in to github.com as fixture'\n", encoding="utf-8")
            gh.chmod(0o755)

            config = scripts / "vidux-config.py"
            config.write_text(textwrap.dedent("""\
                import json

                print(json.dumps({
                    "status": "ok",
                    "source": "fixture",
                    "live_config_present": True,
                    "using_example": False
                }))
            """), encoding="utf-8")

            env = os.environ.copy()
            env.update({
                "HOME": str(home),
                "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
                "TMPDIR": str(tmp / "tmp"),
                "VIDUX_ROOT": str(root),
                "VIDUX_DOCTOR_SKIP_NPM_TEST": "1",
            })
            (tmp / "tmp").mkdir()

            result = subprocess.run(
                ["bash", str(self.SCRIPTS_DIR / "vidux-doctor-cli.sh")],
                capture_output=True, text=True, timeout=15, env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("7/7 checks passed", result.stdout)
            self.assertIn("~/.config/vidux/*.token chmod 600 (1 token file(s) verified)", result.stdout)
            self.assertIn("vidux config check (source=fixture live=yes example=no)", result.stdout)
            self.assertIn("npm test (contract suite) (skipped via VIDUX_DOCTOR_SKIP_NPM_TEST=1)", result.stdout)

    def test_vidux_browse_launcher_reuses_only_matching_health(self):
        """vidux-browse must not treat any listener on :7191 as the current UI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fakebin = tmp / "bin"
            home = tmp / "home"
            dev_root = home / "Development"
            fakebin.mkdir()
            dev_root.mkdir(parents=True)

            (fakebin / "lsof").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fakebin / "open").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            for executable in fakebin.iterdir():
                executable.chmod(0o755)

            env = os.environ.copy()
            env.update({
                "HOME": str(home),
                "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
                "VIDUX_ROOT": str(ROOT),
                "VIDUX_DEV_ROOT": str(dev_root),
                "VIDUX_BROWSER_PORT": "7191",
            })

            matching_health = json.dumps({
                "ok": True,
                "dev_root": str(dev_root.resolve()),
                "repo_root": str(ROOT.resolve()),
                "server_mtime_ns": (ROOT / "browser" / "server.py").stat().st_mtime_ns,
                "port": 7191,
            })
            (fakebin / "curl").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' " + json.dumps(matching_health) + "\n",
                encoding="utf-8",
            )
            (fakebin / "curl").chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "bin" / "vidux-browse"), "--no-open"],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("vidux browser already on http://127.0.0.1:7191", result.stdout)

            stale_health = json.dumps({
                "ok": True,
                "dev_root": str(dev_root.resolve()),
                "port": 7191,
            })
            (fakebin / "curl").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' " + json.dumps(stale_health) + "\n",
                encoding="utf-8",
            )
            (fakebin / "curl").chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "bin" / "vidux-browse"), "--no-open"],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match this Vidux checkout/root", result.stderr)

    def test_vidux_browse_self_locates_when_invoked_via_symlink_outside_checkout(self):
        """Round-1 open-source panel finding: bin/vidux-browse hardcoded ROOT to
        $HOME/Development/vidux with no BASH_SOURCE self-location (unlike
        bin/vidux, which resolves correctly). README.md's own "Vidux Browse"
        section documents running this script directly -- for any stranger not
        physically cloned to ~/Development/vidux, that crashed with a raw
        FileNotFoundError trying to stat a browser/server.py that doesn't exist
        at the wrong, hardcoded path. Reproduced here via a symlink into the
        real checkout from a HOME with no Development/vidux at all -- the same
        deployment shape bin/vidux itself is normally used in (globally
        symlinked into PATH)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            scratch_home = tmp / "home"
            scratch_bin = tmp / "elsewhere" / "bin"
            scratch_dev_root = scratch_home / "Development"
            scratch_bin.mkdir(parents=True)
            scratch_dev_root.mkdir(parents=True)
            (scratch_bin / "vidux-browse").symlink_to(ROOT / "bin" / "vidux-browse")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                free_port = s.getsockname()[1]

            env = os.environ.copy()
            env.update({
                "HOME": str(scratch_home),
                "VIDUX_DEV_ROOT": str(scratch_dev_root),
                "VIDUX_BROWSER_PORT": str(free_port),
            })
            env.pop("VIDUX_ROOT", None)

            proc = subprocess.Popen(
                ["bash", str(scratch_bin / "vidux-browse"), "--no-open", "--foreground"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
            )
            health_payload = None
            try:
                stdout, stderr = proc.communicate(timeout=5)
                self.fail(f"vidux-browse exited early (rc={proc.returncode}): stdout={stdout!r} stderr={stderr!r}")
            except subprocess.TimeoutExpired:
                # Still running after 5s == the server actually started and is
                # serving (matches --foreground's exec into a blocking server).
                conn = http.client.HTTPConnection("127.0.0.1", free_port, timeout=5)
                try:
                    conn.request("GET", "/api/health")
                    health_payload = json.loads(conn.getresponse().read())
                finally:
                    conn.close()
                proc.terminate()
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()

            self.assertNotIn("Traceback", stderr)
            self.assertNotIn("FileNotFoundError", stderr)
            self.assertIn("vidux browser", stderr)
            self.assertIsNotNone(health_payload)
            self.assertEqual(health_payload["repo_root"], str(ROOT.resolve()))

    def test_vidux_browse_launcher_parses_flags_instead_of_silently_ignoring(self):
        """browse flags should affect launcher behavior or fail loudly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fakebin = tmp / "bin"
            home = tmp / "home"
            dev_root = home / "Development"
            custom_root = tmp / "scan-root"
            fakebin.mkdir()
            dev_root.mkdir(parents=True)
            custom_root.mkdir()

            (fakebin / "lsof").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fakebin / "open").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            custom_health = json.dumps({
                "ok": True,
                "dev_root": str(custom_root.resolve()),
                "repo_root": str(ROOT.resolve()),
                "server_mtime_ns": (ROOT / "browser" / "server.py").stat().st_mtime_ns,
                "port": 7292,
            })
            (fakebin / "curl").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' " + json.dumps(custom_health) + "\n",
                encoding="utf-8",
            )
            for executable in fakebin.iterdir():
                executable.chmod(0o755)

            env = os.environ.copy()
            env.update({
                "HOME": str(home),
                "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
                "VIDUX_ROOT": str(ROOT),
            })

            result = subprocess.run(
                [
                    "bash",
                    str(ROOT / "bin" / "vidux-browse"),
                    "--port",
                    "7292",
                    "--root",
                    str(custom_root),
                    "--no-open",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("vidux browser already on http://127.0.0.1:7292", result.stdout)

            unknown = subprocess.run(
                ["bash", str(ROOT / "bin" / "vidux-browse"), "--definitely-not-real", "--no-open"],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(unknown.returncode, 2)
            self.assertIn("unknown flag: --definitely-not-real", unknown.stderr)

            missing = subprocess.run(
                ["bash", str(ROOT / "bin" / "vidux-browse"), "--port"],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn("--port requires a value", missing.stderr)

    def test_vidux_wrapper_exports_resolved_root_to_browse_launcher(self):
        """vidux browse must launch from the checkout that owns bin/vidux."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fakebin = tmp / "bin"
            home = tmp / "home"
            dev_root = tmp / "scan-root"
            fakebin.mkdir()
            home.mkdir()
            dev_root.mkdir()

            (fakebin / "lsof").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fakebin / "open").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            matching_health = json.dumps({
                "ok": True,
                "dev_root": str(dev_root.resolve()),
                "repo_root": str(ROOT.resolve()),
                "server_mtime_ns": (ROOT / "browser" / "server.py").stat().st_mtime_ns,
                "port": 7293,
            })
            (fakebin / "curl").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' " + json.dumps(matching_health) + "\n",
                encoding="utf-8",
            )
            for executable in fakebin.iterdir():
                executable.chmod(0o755)

            env = os.environ.copy()
            env.update({
                "HOME": str(home),
                "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
            })
            env.pop("VIDUX_ROOT", None)

            result = subprocess.run(
                [
                    str(ROOT / "bin" / "vidux"),
                    "browse",
                    "--port",
                    "7293",
                    "--root",
                    str(dev_root),
                    "--no-open",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("vidux browser already on http://127.0.0.1:7293", result.stdout)

    def test_vidux_browse_help_and_completions_include_launcher_flags(self):
        """User-facing help and completions must match vidux-browse flags."""
        help_result = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "help", "browse"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for token in (
            "--no-open",
            "--foreground",
            "--port N",
            "--host HOST",
            "--root PATH",
            "--open-host HOST",
            "--comments-path PATH",
        ):
            self.assertIn(token, help_result.stdout)
        self.assertIn("refuses to reuse an existing port", help_result.stdout)
        self.assertIn("/api/health matches", help_result.stdout)

        browse_help = subprocess.run(
            [str(ROOT / "bin" / "vidux-browse"), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(browse_help.returncode, 0, browse_help.stderr)
        self.assertIn("--port N", browse_help.stdout)
        self.assertIn("--comments-path PATH", browse_help.stdout)

        completion_expectations = {
            "bash": ("--no-open", "--foreground", "--port", "--host", "--root", "--open-host", "--comments-path"),
            "zsh": ("--no-open[Do not open a browser]", "--port[Bind or reuse port]", "--comments-path[Comments JSONL path]"),
            "fish": ("-l no-open", "-l port", "-l comments-path"),
        }
        for shell, tokens in completion_expectations.items():
            completion = subprocess.run(
                [str(ROOT / "scripts" / "vidux-completion.sh"), shell],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(completion.returncode, 0, completion.stderr)
            for token in tokens:
                self.assertIn(token, completion.stdout)

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

    def test_runtime_doctor_memory_fields_name_their_sources(self):
        """Memory-pressure JSON must not imply memory_pressure and vm_stat are one metric."""
        runtime_doctor = _read(self.SCRIPTS_DIR / "vidux-doctor.sh")
        for token in (
            "memory_pressure_free_pct",
            "memory_free_pct",
            "memory_pct_source",
            "vm_free_mb",
            "vm_speculative_mb",
            "vm_pages_source",
            "free_mb",
            "speculative_mb",
        ):
            self.assertIn(token, runtime_doctor)

        result = subprocess.run(
            ["bash", str(self.SCRIPTS_DIR / "vidux-doctor.sh"), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        system_memory = next(
            check for check in data["checks"] if check["id"] == "system_memory_pressure"
        )
        if system_memory.get("available"):
            self.assertIn("memory_pressure_free_pct", system_memory)
            self.assertEqual(
                system_memory["memory_free_pct"],
                system_memory["memory_pressure_free_pct"],
            )
            self.assertEqual(system_memory["memory_pct_source"], "memory_pressure -Q")
            self.assertIn("vm_free_mb", system_memory)
            self.assertIn("vm_speculative_mb", system_memory)
            self.assertEqual(system_memory["free_mb"], system_memory["vm_free_mb"])
            self.assertEqual(system_memory["vm_pages_source"], "vm_stat")

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

    def test_doctor_orphan_fix_does_not_false_green_retained_dirs(self):
        """Runtime doctor --fix must stay warn when safety rules retain an orphan directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / "projects").mkdir()
            auto_root = repo / "automations"
            removable = auto_root / "short-orphan"
            retained = auto_root / "long-orphan"
            removable.mkdir(parents=True)
            retained.mkdir(parents=True)
            (removable / "memory.md").write_text("short\n", encoding="utf-8")
            (retained / "memory.md").write_text(
                "\n".join(f"line {i}" for i in range(8)) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "bash",
                    str(self.SCRIPTS_DIR / "vidux-doctor.sh"),
                    "--json",
                    "--fix",
                    "--repo",
                    str(repo),
                    "--automations-dir",
                    str(auto_root),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
            check = next(
                check for check in data["checks"] if check["id"] == "orphan_automations"
            )

            self.assertFalse(removable.exists())
            self.assertTrue(retained.exists())
            self.assertEqual(check["status"], "warn")
            self.assertFalse(check["fixed"])
            self.assertEqual(check["fixed_count"], 1)
            self.assertEqual(check["retained_count"], 1)
            self.assertEqual(check["count"], 1)
            self.assertEqual(check["details"], ["long-orphan"])
            self.assertEqual(check["removed"], ["short-orphan"])

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

    def test_ledger_fleet_health_marks_zero_run_repo_unknown(self):
        """Fleet health must not report healthy when the ledger has no automation runs."""
        data = self._run_ledger_fleet_health([
            {
                "ts": "2026-04-07T00:00:00Z",
                "repo": "vidux",
                "agent_id": "codex/noise",
                "event": "live",
                "summary": "noise without automation id",
            }
        ])

        self.assertEqual(data["summary"]["total_runs"], 0)
        self.assertEqual(data["summary"]["bimodal_score"], 100)
        self.assertEqual(data["summary"]["bimodal_status"], "unknown")

    def _run_ledger_fleet_health(self, entries):
        """Helper: run ledger_fleet_health against a temp ledger fixture."""
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
                        "&& ledger_fleet_health vidux 168"
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
        """vidux.config.example.json must have backpressure section with bimodal thresholds.

        Migrated from vidux.config.json on 2026-05-14 (config is now gitignored).
        """
        config = json.loads((ROOT / "vidux.config.example.json").read_text())
        self.assertIn("backpressure", config)
        bp = config["backpressure"]
        self.assertIn("bimodal_critical_threshold", bp)
        self.assertIn("bimodal_warning_threshold", bp)
        self.assertGreater(bp["bimodal_warning_threshold"], bp["bimodal_critical_threshold"])

    def test_config_has_pruning_section(self):
        """vidux.config.example.json must have pruning section.

        Migrated from vidux.config.json on 2026-05-14 (config is now gitignored).
        """
        config = json.loads((ROOT / "vidux.config.example.json").read_text())
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
        """SKILL.md must document the two nesting modes (investigation + sub-plan rollup).

        Section evolved through three names:
        - 2.10.0: 'Compound tasks and sub-plans'
        - 2.11.0: 'When a task needs an investigation (the only nesting vidux allows)'
        - 2.17.0: 'Two nesting modes' (investigation + sub-plan rollup)

        The contract is the SEMANTIC presence of compound-task / investigation
        nesting documentation, not any specific section header. We assert the
        terms and the two-mode structure rather than the literal header text.
        """
        text = _read(ROOT / "SKILL.md")
        self.assertIn("Two nesting modes", text, "SKILL.md missing 'Two nesting modes' section header")
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
            "context will be lost" in text.lower() or "context is lost" in text.lower(),
            "SKILL.md missing context-loss guidance in principle 2",
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
        import tempfile
        import os
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
        import tempfile
        import os
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

    def test_midzone_deep_work_in_doctrine(self):
        """DOCTRINE.md must tie mid-zone guidance to deep work."""
        text = _read(DOCTRINE)
        self.assertIn("mid-zone", text.lower())
        self.assertIn("deep work", text.lower())


if __name__ == "__main__":
    unittest.main()
