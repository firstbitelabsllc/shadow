"""Keep shipped Shadow instructions aligned with shipped executable targets."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "SKILL.md",
    ROOT / "AGENT.md",
    ROOT / "CONTRIBUTING.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "guides").rglob("*.md")),
)
TARGET = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"((?:assets|bin|browser|docs|examples|guides|hooks|references|schemas|scripts|tests)"
    r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?)"
)
# The plan archive names paths that USED to exist and were deliberately
# removed; requiring them back would forbid ever deleting a file.
PROPOSAL_PREFIXES = (
    "docs/plan-archive/",
)


class DocumentedTargetTests(unittest.TestCase):
    def test_documented_repository_targets_exist(self):
        missing: list[str] = []
        documented: set[str] = set()

        for document in DOCUMENTS:
            relative = document.relative_to(ROOT).as_posix()
            proposal = relative.startswith(PROPOSAL_PREFIXES)
            text = document.read_text(encoding="utf-8")
            for match in TARGET.finditer(text):
                target = match.group(1)
                documented.add(target)
                if proposal or (ROOT / target).exists():
                    continue
                line = text.count("\n", 0, match.start()) + 1
                missing.append(f"{relative}:{line}: {target}")

        self.assertTrue(documented, "expected at least one documented target")
        self.assertEqual([], missing, "documented targets must exist in this checkout")

    def test_public_help_matches_the_ownership_and_entity_flags(self):
        shadow = ROOT / "bin" / "shadow"
        expected = {
            "status": ("--by OWNER", "--in-flight"),
            "amp": ("--entity ID", "--by OWNER"),
            "throw": ("--entity ID", "--by OWNER"),
            "return": ("--entity ID", "--by OWNER"),
            "accept": ("--by OWNER", "--row '~hash'"),
        }
        for verb, clauses in expected.items():
            result = subprocess.run(
                [str(shadow), "help", verb], cwd=ROOT, capture_output=True,
                text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for clause in clauses:
                self.assertIn(clause, result.stdout, f"{verb}: {clause}")
        status = subprocess.run(
            [str(shadow), "help", "status"], cwd=ROOT, capture_output=True,
            text=True, check=False,
        ).stdout
        self.assertNotIn("--all", status)


class RetiredDesignRecordsDoNotShip(unittest.TestCase):
    def test_retired_superpowers_design_records_and_their_exceptions_are_gone(self) -> None:
        self.assertFalse((ROOT / "docs" / "superpowers").exists())
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertNotIn("docs/superpowers/", attributes)
        self.assertNotIn("docs/superpowers/specs/", PROPOSAL_PREFIXES)
        self.assertNotIn("docs/superpowers/plans/", PROPOSAL_PREFIXES)
        all_boats = (ROOT / "tests" / "test_all_boats_law.py").read_text(encoding="utf-8")
        self.assertNotIn('Path("docs/superpowers")', all_boats)

    def test_current_method_configuration_and_bucket_instructions_remain(self) -> None:
        expected = {
            "docs/reference/method.md": "Attack, then refute",
            "docs/reference/config.md": "shadow.yaml",
            "docs/reference/buckets.md": "Extension buckets",
        }
        for relative, expected_text in expected.items():
            with self.subTest(document=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(expected_text, text)


if __name__ == "__main__":
    unittest.main()
