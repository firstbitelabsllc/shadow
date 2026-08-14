from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from browser.server import plan_record


ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "scripts" / "shadow-init.py"
SPEC = importlib.util.spec_from_file_location("shadow_init", INIT)
assert SPEC and SPEC.loader
shadow_init = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow_init)


def run(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INIT), *args],
        cwd=cwd,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


class InitTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "useful-project"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def test_creates_one_typed_local_plan_for_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
            result = run("--here", cwd=repo, home=home)
            record = plan_record(destination, home)
            plan = destination.read_text(encoding="utf-8")
            board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"created local PLAN.md: {destination}\n")
        self.assertIsNone(record["contract_error"])
        self.assertEqual(record["briefing"]["state"], "needs_you")
        self.assertEqual(len(record["briefing"]["choices"]), 3)
        self.assertEqual(board["entities"][0]["plan"], str(destination.resolve()))
        self.assertNotIn(dirname, json.dumps(record))
        self.assertIn("Complete the full declared outcome", plan)
        self.assertIn("every safe reachable lane", plan)
        self.assertIn("- Option A ID: derive-and-execute", plan)
        self.assertNotIn("smallest", plan.lower())
        self.assertNotIn(" ".join(("one", "bounded")), plan.lower())

    def test_exclusive_plan_write_fsyncs_its_file_and_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            destination = Path(dirname) / "nested" / "PLAN.md"
            destination.parent.mkdir()
            kinds = {"file": False, "dir": False}
            real_fsync = os.fsync

            def spy(fd: int) -> None:
                kinds["dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"] = True
                real_fsync(fd)

            with mock.patch.object(shadow_init.os, "fsync", side_effect=spy):
                shadow_init.write_exclusive(destination, "# Plan\n")
        self.assertEqual(kinds, {"file": True, "dir": True})

    def test_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
            destination.parent.mkdir(parents=True)
            destination.write_text("keep me\n", encoding="utf-8")
            result = run("--here", cwd=repo, home=home)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep me\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_requires_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            outside = root / "outside"
            outside.mkdir()
            result = run("--here", cwd=outside, home=root / "home")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not inside a Git worktree", result.stderr)

    def test_rejects_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            nested = repo / "nested"
            nested.mkdir()
            result = run("--here", cwd=nested, home=Path(dirname) / "home")
        self.assertEqual(result.returncode, 2)
        self.assertIn("project root", result.stderr)


if __name__ == "__main__":
    unittest.main()
