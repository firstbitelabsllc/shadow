"""Shadow's shipped contract: AGENT.md and the file grammar stay coherent."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "AGENT.md"
GRAMMAR = ROOT / "docs" / "reference" / "grammar.md"
SKILL = ROOT / "SKILL.md"
AMPLIFY_SKILL = ROOT / "plugins" / "shadow" / "skills" / "amplify" / "SKILL.md"


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
        amplify_skill = AMPLIFY_SKILL.read_text(encoding="utf-8")
        normalized_goal = " ".join(amplify_skill.split())

        self.assertIn("`plugins/shadow/skills/amplify/SKILL.md` owns goal shaping", root_skill)
        self.assertNotIn("Outcome: <plain result>", root_skill)
        for anchor in (
            "A goal is a pointer, not a plan",
            "at most 80 words",
            "Stop after planning only when explicitly asked",
            "one standing Shadow goal",
            "unchanged and skill-free",
            "Skills:",
            "one to four canonical invocation names",
            "current session's available skill catalog",
            "plugin-qualified",
            "filesystem/cache path",
            "never add a fifth line",
            "brevity must not narrow it to one task",
            "Quantify only when a number changes a decision",
            "proof that would fail a plausible shallow result",
            "without mistaking activity for completion",
        ):
            self.assertIn(anchor, normalized_goal, anchor)
        self.assertNotIn("100-200 word", root_skill + amplify_skill)
        self.assertNotIn("60-100 word", root_skill + amplify_skill)
        self.assertNotIn("do not touch <prohibited paths>", amplify_skill)
        self.assertNotIn("Authority: <refreshed computer board>", amplify_skill)

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

    def test_task_consumers_import_one_executable_grammar(self) -> None:
        """A task row means the same thing to lint, accept, projection, and recovery."""
        scripts = ROOT / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import shadow_plan_grammar as grammar
            import shadow_root_board as board

            def load(name: str, filename: str):
                spec = importlib.util.spec_from_file_location(name, scripts / filename)
                assert spec and spec.loader
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module

            lint = load("grammar_contract_lint", "shadow-lint.py")
            accept = load("grammar_contract_accept", "shadow-accept.py")
            amp = load("grammar_contract_amp", "shadow-amp.py")
            lifecycle = load("grammar_contract_lifecycle", "shadow-lifecycle.py")
        finally:
            sys.path.pop(0)

        self.assertIs(lint.ROW_RE, grammar.ROW_RE)
        self.assertIs(accept.ROW_LINE_RE, grammar.ROW_RE)
        self.assertIs(amp.ROW_RE, grammar.ROW_RE)
        self.assertIs(lifecycle.ROW_RE, grammar.ROW_RE)
        self.assertIs(board.HOT_TASK_ROW_RE, grammar.HOT_TASK_ROW_RE)
        self.assertIs(lint.FIELD_RE, grammar.FIELD_RE)
        self.assertIs(accept.FIELD_RE, grammar.FIELD_RE)
        self.assertIs(amp.FIELD_RE, grammar.FIELD_RE)
        self.assertIs(lifecycle.FIELD_RE, grammar.FIELD_RE)
        self.assertIs(lint.NEEDS_VALUE_RE, grammar.NEEDS_VALUE_RE)
        self.assertIs(accept.NEEDS_REF_RE, grammar.NEEDS_REF_RE)
        self.assertIs(lint.PROOF_CLASS_RE, grammar.PROOF_CLASS_RE)
        self.assertIs(lifecycle.PROOF_CLASS_RE, grammar.PROOF_CLASS_RE)
        self.assertIs(board.ROW_ID, grammar.ROW_ID_RE)
        self.assertIs(board.PROGRESS_PROOF_RECEIPT_RE, grammar.PROOF_RECEIPT_RE)
        self.assertIs(lint._shell_operators, grammar.shell_operators)
        self.assertIs(accept._shell_operators, grammar.shell_operators)


if __name__ == "__main__":
    unittest.main()
