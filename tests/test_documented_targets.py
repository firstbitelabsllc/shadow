"""Keep shipped Shadow instructions aligned with shipped executable targets."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "SKILL.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "guides").rglob("*.md")),
)
TARGET = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"((?:assets|bin|browser|docs|examples|guides|hooks|references|schemas|scripts|tests)"
    r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?)"
)


class DocumentedTargetTests(unittest.TestCase):
    def test_documented_repository_targets_exist(self):
        missing: list[str] = []
        documented: set[str] = set()

        for document in DOCUMENTS:
            text = document.read_text(encoding="utf-8")
            for match in TARGET.finditer(text):
                target = match.group(1)
                documented.add(target)
                if not (ROOT / target).exists():
                    line = text.count("\n", 0, match.start()) + 1
                    missing.append(f"{document.relative_to(ROOT)}:{line}: {target}")

        self.assertTrue(documented, "expected at least one documented target")
        self.assertEqual([], missing, "documented targets must exist in this checkout")


if __name__ == "__main__":
    unittest.main()
