"""Outcome completeness must never regress into a single-slice stop rule."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent.parent

# Archived provenance, not live instruction: these records are kept as written.
ARCHIVE_ROOTS = (
    Path("docs/archive"),
    Path("docs/plan-archive"),
    Path("docs/superpowers"),
)
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


def live_instruction_files() -> list[Path]:
    """Tracked, non-archived text surfaces.

    Tracked-only, because an untracked virtualenv, vendored dependency, or
    generated tree is not an instruction surface and must never fail this law.
    """

    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = []
    for entry in listing.stdout.split("\0"):
        if not entry:
            continue
        relative = Path(entry)
        if relative.suffix not in TEXT_SUFFIXES:
            continue
        if any(relative.is_relative_to(archive) for archive in ARCHIVE_ROOTS):
            continue
        absolute = ROOT / relative
        if absolute.is_file():
            paths.append(relative)
    return paths


class AllBoatsLaw(unittest.TestCase):
    def test_live_instruction_surfaces_carry_no_single_slice_stop_law(self) -> None:
        scanned = live_instruction_files()
        self.assertTrue(scanned, "no live instruction surface was scanned")
        for relative in scanned:
            path = ROOT / relative
            text = path.read_text(encoding="utf-8").lower()
            for phrase in BANNED_NARROWING:
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
