"""Outcome completeness must never regress into a single-slice stop rule."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent

ARCHIVE_ROOTS = (ROOT / "docs" / "archive", ROOT / "docs" / "plan-archive")
TEXT_SUFFIXES = {".md", ".py", ".js", ".svg"}

BANNED_NARROWING = tuple(
    " ".join(words)
    for words in (
        ("one", "bounded", "task"),
        ("one", "bounded", "change"),
        ("one", "exact", "resume", "move"),
        ("one", "exact", "next", "move"),
        ("one", "bounded", "task", "per", "cycle"),
        ("ship", "one", "useful"),
        ("first", "bounded", "move"),
        ("smallest", "coherent", "scope"),
        ("smallest", "behavior"),
        ("smallest", "result"),
        ("smallest", "slice"),
    )
)


class AllBoatsLaw(unittest.TestCase):
    def test_live_instruction_surfaces_carry_no_single_slice_stop_law(self) -> None:
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if any(path.is_relative_to(archive) for archive in ARCHIVE_ROOTS):
                continue
            text = path.read_text(encoding="utf-8").lower()
            for phrase in BANNED_NARROWING:
                relative = path.relative_to(ROOT)
                self.assertNotIn(phrase, text, f"{relative} restored narrowing law: {phrase}")

    def test_runtime_entry_points_require_queue_drain_and_safe_fanout(self) -> None:
        standing = (ROOT / "docs/reference/host-integration.md").read_text(encoding="utf-8")
        amp = (ROOT / "scripts/shadow-amp.py").read_text(encoding="utf-8")
        for text in (standing, amp):
            self.assertIn("drain every reachable row", text.lower())
            self.assertIn("fan out safe disjoint", text.lower())
            self.assertIn("full acceptance", text.lower())


if __name__ == "__main__":
    unittest.main()
