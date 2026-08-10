"""Shadow's shipped contract: AGENT.md and the file grammar stay coherent."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "AGENT.md"
GRAMMAR = ROOT / "docs" / "reference" / "grammar.md"
SKILL = ROOT / "SKILL.md"
GOAL_SKILL = ROOT / "skills" / "goal" / "SKILL.md"


class GrammarContractTests(unittest.TestCase):
    def test_law_files_exist_and_are_linked(self) -> None:
        self.assertTrue(AGENT.is_file(), "AGENT.md must ship at the skill root")
        self.assertTrue(GRAMMAR.is_file(), "docs/reference/grammar.md must ship")
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("AGENT.md", skill)
        self.assertIn("docs/reference/grammar.md", skill)
        index = (ROOT / "docs" / "reference" / "index.md").read_text(encoding="utf-8")
        self.assertIn("(grammar.md)", index)

    def test_agent_md_ships_in_the_release_artifact(self) -> None:
        # npm removed 2026-08-09: the artifact is `git archive`, and the
        # allowlist is .gitattributes export-ignore. AGENT.md must not be
        # export-ignored, and must be in the release script's required set.
        import importlib.util

        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for line in attrs.splitlines():
            if line.strip().startswith("AGENT.md"):
                self.fail("AGENT.md must not be export-ignored from the release artifact")
        spec = importlib.util.spec_from_file_location(
            "relpkg", ROOT / "scripts" / "shadow-release-package.py")
        rel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rel)
        self.assertIn("AGENT.md", rel.REQUIRED_FILES,
                      "the standing-behavior file must ship in the release artifact")

    def test_agent_md_carries_the_standing_behaviors(self) -> None:
        text = AGENT.read_text(encoding="utf-8")
        for anchor in (
            "plan file",
            "computer board",
            "project",
            "entity",
            "milestone",
            "checkpoint",
            "explore",
            "ship",
            "Defer is a write",
            "two questions",
            "shadow lint",
            "lesson",
            "read-only",
        ):
            self.assertIn(anchor, text, anchor)

    def test_goal_compiler_keeps_launchers_bounded_and_plan_owned(self) -> None:
        root_skill = SKILL.read_text(encoding="utf-8")
        goal_skill = GOAL_SKILL.read_text(encoding="utf-8")
        normalized_goal = " ".join(goal_skill.split())

        self.assertIn("`skills/goal/SKILL.md` owns goal shaping", root_skill)
        self.assertNotIn("Outcome: <plain result>", root_skill)
        for anchor in (
            "A goal is a pointer, not a plan",
            "60-100 words",
            "Stop after planning only when explicitly asked",
            "details stay in PLAN.md",
            "one relevant human boundary or none",
        ):
            self.assertIn(anchor, normalized_goal, anchor)
        self.assertNotIn("100-200 word", root_skill + goal_skill)
        self.assertNotIn("do not touch <prohibited paths>", goal_skill)

    def test_only_shadow_is_an_invented_name(self) -> None:
        # Standard vocabulary only: the old fun terms must not resurface in law.
        agent = AGENT.read_text(encoding="utf-8")
        grammar = GRAMMAR.read_text(encoding="utf-8")
        for banned in ("Operator Brief", "gate pair", "posture", "BOX ", "VERDICT "):
            self.assertNotIn(banned, agent, banned)
            self.assertNotIn(banned, grammar, banned)

    def test_grammar_is_pinned(self) -> None:
        text = GRAMMAR.read_text(encoding="utf-8")
        for anchor in (
            "- Project:",
            "explore | ship",
            "(DoD)",
            "| proof:",
            "needs:",
            "PROOF",
            "MODE",
            "SPIKE",
            "DECISION",
            "LESSON none",
            "shadow-lint.py",
            "ARCHIVE",
        ):
            self.assertIn(anchor, text, anchor)
        self.assertRegex(text, r"~[0-9a-z]{4}")
        self.assertIn("^[a-z][a-z0-9-]{1,31}$", text)

    def test_grammar_matches_the_shipped_board_scanner(self) -> None:
        server = (ROOT / "browser" / "server.py").read_text(encoding="utf-8")
        grammar = GRAMMAR.read_text(encoding="utf-8")
        project_re = re.search(r'PROJECT_VALUE_RE = re\.compile\(r"([^"]+)"\)', server)
        self.assertIsNotNone(project_re)
        self.assertIn(project_re.group(1), grammar)
        mode_re = re.search(r'MODE_VALUE_RE = re\.compile\(r"([^"]+)"\)', server)
        self.assertIsNotNone(mode_re)
        # Two modes, and the board's vocabulary is exactly the grammar's.
        for mode in ("explore", "ship"):
            self.assertIn(mode, mode_re.group(1))
            self.assertIn(f"Mode: {mode}", grammar.replace("explore | ship", f"Mode: {mode}"))
        for legacy in ("spike-mode", "defer-mode", "broad", "close"):
            self.assertNotIn(legacy, mode_re.group(1))


if __name__ == "__main__":
    unittest.main()
