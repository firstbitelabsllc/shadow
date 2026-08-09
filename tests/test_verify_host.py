"""The host verifier must be able to fail.

`shadow doctor` answers "is it installed". Every one of its host checks is an
existence check, and the failure this milestone cares about slips past all of
them: a host that has the files and still opens cold, without the skill, asking
which project to attach to.

So every check here is proven by breaking the thing it guards. A verifier that
cannot go red is the same class of defect as the three false greens this repo
shipped and later found: a promise nothing checks.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-verify-host.sh"


PLAN = """# Fixture

## Brief

- Project: fixture
- Mode: ship

## Tasks

### M1 — live
- [pending] a row ~aa11 | proof: cmd true

## Progress

- 2026-08-09T00:00:00Z NOTE seeded
"""


def run(home: Path, host: str = "claude-code",
        path: str | None = None) -> subprocess.CompletedProcess[str]:
    # A scratch HOME has no ~/Development, so the board check would fail for a
    # reason that has nothing to do with the host's wiring. Point the portfolio
    # at a directory that owns one plan; the verifier is what is under test.
    portfolio = home / "portfolio" / "project"
    if not portfolio.exists():
        portfolio.mkdir(parents=True)
        (portfolio / "PLAN.md").write_text(PLAN, encoding="utf-8")
    # A cold session types `shadow`, so a wired host has this checkout's bin on
    # PATH. The fixture has to say so, or the verifier is right to go red.
    if path is None:
        path = f"{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(SCRIPT), "--host", host],
        capture_output=True, text=True, check=False,
        env={**os.environ, "HOME": str(home), "PATH": path,
             "SHADOW_PORTFOLIO_ROOT": str(home / "portfolio")},
    )


def wired(home: Path, host: str = "claude-code") -> None:
    """A correctly wired host: mount plus a current standing goal."""
    mount = {"claude-code": ".claude/skills", "codex": ".agents/skills",
             "cursor": ".cursor/skills"}[host]
    (home / mount).mkdir(parents=True, exist_ok=True)
    (home / mount / "shadow").symlink_to(ROOT, target_is_directory=True)
    directive = {"claude-code": ".claude/CLAUDE.md", "codex": ".codex/AGENTS.md"}.get(host)
    if directive:
        path = home / directive
        path.parent.mkdir(parents=True, exist_ok=True)
        block = subprocess.run([str(ROOT / "bin" / "shadow"), "goal"],
                               capture_output=True, text=True, check=True).stdout.strip()
        path.write_text(f"# my rules\n\nkeep these\n\n{block}\n", encoding="utf-8")


class AWiredHostPasses(unittest.TestCase):
    def test_the_happy_path_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            result = run(home)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("wiring verified", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)

    def test_the_session_check_is_skipped_not_silently_passed(self) -> None:
        # It costs the owner's quota, so it must never run by default — and it
        # must say so, rather than leaving a green run implying it happened.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            self.assertIn("[SKIP] session check", run(home).stdout)


class EveryCheckCanFail(unittest.TestCase):
    def _broken(self, mutate) -> subprocess.CompletedProcess[str]:
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            mutate(home)
            return run(home)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_mount_fails(self) -> None:
        result = self._broken(lambda home: (home / ".claude/skills/shadow").unlink())
        self.assertEqual(result.returncode, 1)
        self.assertIn("no skill mount", result.stdout)

    def test_a_mount_pointing_at_another_checkout_fails(self) -> None:
        def mutate(home: Path) -> None:
            (home / ".claude/skills/shadow").unlink()
            other = home / "another-clone"
            other.mkdir()
            (other / "SKILL.md").write_text("# not this one\n", encoding="utf-8")
            (home / ".claude/skills/shadow").symlink_to(other, target_is_directory=True)

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("another checkout is serving this host", result.stdout)

    def test_a_competing_skill_in_another_root_fails(self) -> None:
        # Host loaders take the first match, so a same-named skill in another
        # root wins silently and forever.
        def mutate(home: Path) -> None:
            other = home / ".agents" / "skills"
            other.mkdir(parents=True)
            impostor = home / "impostor"
            impostor.mkdir()
            (other / "shadow").symlink_to(impostor, target_is_directory=True)

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("one of them is stale", result.stdout)

    def test_a_skill_whose_frontmatter_a_loader_cannot_use_fails(self) -> None:
        # Opening with `---` is not the same as parsing. A block that closes
        # without a description is dropped by the loader without a word, and
        # "SKILL.md exists" reports nothing about that.
        def mutate(home: Path) -> None:
            (home / ".claude/skills/shadow").unlink()
            damaged = home / "damaged"
            damaged.mkdir()
            (damaged / "SKILL.md").write_text("---\nname: shadow\n---\n\n# Shadow\n",
                                              encoding="utf-8")
            (home / ".claude/skills/shadow").symlink_to(damaged, target_is_directory=True)

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("a loader would drop the skill", result.stdout)

    def test_shadow_missing_from_path_fails(self) -> None:
        # The installer can link into a directory the host never sees. Every
        # file is in place and the session's first command is not found.
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            empty = home / "empty-bin"
            empty.mkdir()
            result = run(home, path=f"{empty}{os.pathsep}/usr/bin{os.pathsep}/bin")
            self.assertEqual(result.returncode, 1)
            self.assertIn("first command is not found", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_path_shadow_from_another_checkout_fails(self) -> None:
        # Mount and directive can both point here while `shadow` earlier on
        # PATH belongs to another clone — the session reads one version's law
        # and runs another's board.
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            other = home / "other-bin"
            other.mkdir()
            shim = other / "shadow"
            shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            shim.chmod(0o755)
            result = run(home, path=f"{other}{os.pathsep}{ROOT / 'bin'}"
                                    f"{os.pathsep}{os.environ.get('PATH', '')}")
            self.assertEqual(result.returncode, 1)
            self.assertIn("another checkout", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_directive_fails_with_the_command_that_fixes_it(self) -> None:
        result = self._broken(lambda home: (home / ".claude/CLAUDE.md").unlink())
        self.assertEqual(result.returncode, 1)
        self.assertIn("shadow goal --install", result.stdout)

    def test_two_copies_of_the_standing_goal_fail(self) -> None:
        # The exact false green the doctor check had: append twice, and a
        # substring test says "current" while the host reads the stale one.
        def mutate(home: Path) -> None:
            path = home / ".claude/CLAUDE.md"
            block = subprocess.run([str(ROOT / "bin" / "shadow"), "goal"],
                                   capture_output=True, text=True, check=True).stdout.strip()
            path.write_text(path.read_text(encoding="utf-8") + "\n" + block + "\n", encoding="utf-8")

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("reads the first one", result.stdout)

    def test_an_empty_board_fails(self) -> None:
        # THE POINT of the whole milestone. Files can all be in place and the
        # session still opens cold with nothing to take — which is when a host
        # asks "which project?", the one question this exists to prevent.
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            (home / "nothing").mkdir()
            result = subprocess.run(
                ["bash", str(SCRIPT), "--host", "claude-code"],
                capture_output=True, text=True, check=False,
                env={**os.environ, "HOME": str(home),
                     "PATH": f"{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
                     "SHADOW_PORTFOLIO_ROOT": str(home / "nothing")},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("a session would have nothing to take", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_stale_standing_goal_fails(self) -> None:
        def mutate(home: Path) -> None:
            path = home / ".claude/CLAUDE.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("shadow accept", "shadow flip"),
                encoding="utf-8")

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout)


class CursorIsHonestAboutWhatItCannotCheck(unittest.TestCase):
    def test_cursor_skips_the_directive_instead_of_inventing_a_path(self) -> None:
        # Its user rules live in application settings, not a file. Asserting
        # ~/.cursor/rules/shadow.md would invent a convention and then report
        # success for wiring that does nothing.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home, "cursor")
            result = run(home, "cursor")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("no file-backed directive", result.stdout)
            self.assertNotIn(".cursor/rules", result.stdout)


class TheScriptItself(unittest.TestCase):
    def test_an_unknown_host_is_refused(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT), "--host", "emacs"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)

    def test_help_names_both_tiers(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT), "--help"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("offline", result.stdout)
        self.assertIn("--live", result.stdout)


if __name__ == "__main__":
    unittest.main()
