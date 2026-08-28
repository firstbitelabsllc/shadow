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
    def make_repo(self, root: Path, name: str = "useful-project") -> Path:
        repo = root / name
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
        self.assertNotIn("- Origin:", plan)

    def test_long_repo_name_separates_plan_storage_from_project_identity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            name = "shadow-pex-root-isolation-20260828-long-checkout-name"
            repo = self.make_repo(root, name)
            home = root / "home"
            storage_slug = shadow_init.board.local_plan_slug(name)
            project_id = storage_slug[:32]
            destination = home / ".shadow" / "plans" / storage_slug / "PLAN.md"
            result = run("--here", cwd=repo, home=home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, f"created local PLAN.md: {destination}\n")
            plan = destination.read_text(encoding="utf-8")
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            resolved = shadow_init.board.local_plan_for_repo(repo, home=home)
        self.assertGreater(len(name), 48)
        self.assertEqual(
            storage_slug, "shadow-pex-root-isolation-20260828-long-checkout"
        )
        self.assertEqual(project_id, "shadow-pex-root-isolation-202608")
        self.assertEqual(len(storage_slug), 48)
        self.assertEqual(len(project_id), 32)
        self.assertIn(f"- Project: {project_id}\n", plan)
        self.assertEqual(board["entities"][0]["project"], project_id)
        self.assertEqual(board["entities"][0]["plan"], str(destination.resolve()))
        self.assertEqual(resolved, destination.resolve())

    def test_writes_normalized_origin_from_ssh_or_https(self) -> None:
        urls = (
            "git@github.com:example/widget.git",
            "https://github.com/example/widget.git",
            "ssh://git@github.com/example/widget.git",
        )
        for url in urls:
            with self.subTest(url=url):
                with tempfile.TemporaryDirectory() as dirname:
                    root = Path(dirname)
                    repo = self.make_repo(root)
                    subprocess.run(
                        ["git", "-C", str(repo), "remote", "add", "origin", url],
                        check=True,
                    )
                    home = root / "home"
                    destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
                    result = run("--here", cwd=repo, home=home)
                    plan = destination.read_text(encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("- Origin: github.com/example/widget\n", plan)
                self.assertNotIn("git@github.com", plan)
                self.assertNotIn("https://", plan)
                self.assertNotIn(dirname, plan)

    def test_omits_origin_when_the_remote_is_a_filesystem_path(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            cases = (("relative-repo", "../forge.git"), ("absolute-repo", str(root / "forge.git")))
            for name, url in cases:
                with self.subTest(url=url):
                    repo = root / name
                    repo.mkdir()
                    subprocess.run(["git", "init", "-q", str(repo)], check=True)
                    subprocess.run(
                        ["git", "-C", str(repo), "remote", "add", "origin", url],
                        check=True,
                    )
                    home = root / f"home-{name}"
                    destination = home / ".shadow" / "plans" / name / "PLAN.md"
                    result = run("--here", cwd=repo, home=home)
                    plan = destination.read_text(encoding="utf-8")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("- Origin:", plan)
                    self.assertNotIn(dirname, plan)
                    self.assertNotIn("/Users/", plan)

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
