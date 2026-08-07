"""Shadow's shipped contract: AGENT.md and the file grammar stay coherent."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "AGENT.md"
GRAMMAR = ROOT / "docs" / "reference" / "grammar.md"
SKILL = ROOT / "SKILL.md"


class GrammarContractTests(unittest.TestCase):
    def test_law_files_exist_and_are_linked(self) -> None:
        self.assertTrue(AGENT.is_file(), "AGENT.md must ship at the skill root")
        self.assertTrue(GRAMMAR.is_file(), "docs/reference/grammar.md must ship")
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("AGENT.md", skill)
        self.assertIn("docs/reference/grammar.md", skill)
        index = (ROOT / "docs" / "reference" / "index.md").read_text(encoding="utf-8")
        self.assertIn("(grammar.md)", index)

    def test_agent_md_ships_in_the_npm_package(self) -> None:
        import json

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("AGENT.md", package.get("files", []),
                      "the standing-behavior file must ship in the package")

    def test_agent_md_carries_the_standing_behaviors(self) -> None:
        text = AGENT.read_text(encoding="utf-8")
        for anchor in (
            "plan file",
            "task",
            "explore",
            "ship",
            "Defer is a write",
            "two questions",
            "shadow lint",
            "lesson",
            "read-only",
        ):
            self.assertIn(anchor, text, anchor)

    def test_only_shadow_is_an_invented_name(self) -> None:
        # Standard vocabulary only: the old fun terms must not resurface in law.
        agent = AGENT.read_text(encoding="utf-8")
        grammar = GRAMMAR.read_text(encoding="utf-8")
        for banned in ("the Method", "Operator Brief", "checkpoint row", "gate pair", "posture", "Entity:", "BOX ", "VERDICT "):
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
