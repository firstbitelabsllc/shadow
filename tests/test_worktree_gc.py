import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vidux-worktree-gc.py"


def run(command, cwd=None, env=None, check=True):
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"{command} failed with {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def git(repo, *args, check=True):
    return run(["git", "-C", str(repo), *args], check=check)


class WorktreeGcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.worktrees_dir = self.root / "worktrees"
        self.worktrees_dir.mkdir()

        run(["git", "init", "-b", "main", str(self.repo)])
        git(self.repo, "config", "user.email", "vidux@example.com")
        git(self.repo, "config", "user.name", "Vidux Test")
        (self.repo / "README.md").write_text("vidux\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "initial")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")

        self.add_worktree("merged-clean")
        self.add_worktree("open-pr")
        dirty = self.add_worktree("dirty-branch")
        (dirty / "dirty.txt").write_text("local-only\n", encoding="utf-8")
        self.add_unmerged_worktree("closed-unmerged")
        self.add_unmerged_worktree("unmerged-no-pr")

        self.env = os.environ.copy()
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        self.write_fake_gh(fake_bin / "gh")
        self.env["PATH"] = f"{fake_bin}{os.pathsep}{self.env['PATH']}"

    def tearDown(self):
        self.tmp.cleanup()

    def add_worktree(self, branch):
        path = self.worktrees_dir / branch
        git(self.repo, "worktree", "add", "-b", branch, str(path), "HEAD")
        return path

    def add_unmerged_worktree(self, branch):
        path = self.add_worktree(branch)
        filename = f"{branch}.txt"
        (path / filename).write_text(branch + "\n", encoding="utf-8")
        git(path, "add", filename)
        git(path, "commit", "-m", f"change {branch}")
        return path

    def write_fake_gh(self, path):
        payload = [
            {
                "number": 12,
                "state": "OPEN",
                "title": "open work",
                "headRefName": "open-pr",
                "isDraft": False,
                "url": "https://example.test/pull/12",
                "mergedAt": None,
                "closedAt": None,
            },
            {
                "number": 13,
                "state": "CLOSED",
                "title": "closed work",
                "headRefName": "closed-unmerged",
                "isDraft": False,
                "url": "https://example.test/pull/13",
                "mergedAt": None,
                "closedAt": "2026-04-26T00:00:00Z",
            },
        ]
        path.write_text(
            "#!/bin/sh\ncat <<'JSON'\n" + json.dumps(payload) + "\nJSON\n",
            encoding="utf-8",
        )
        path.chmod(0o755)

    def run_gc(self, *args, check=True):
        return run(
            [sys.executable, str(SCRIPT), "--base", "origin/main", "--json", *args, str(self.repo)],
            env=self.env,
            check=check,
        )

    def test_classifies_worktree_lifecycle_buckets(self):
        result = self.run_gc()
        payload = json.loads(result.stdout)
        by_branch = {item["branch"]: item for item in payload["worktrees"]}

        self.assertEqual("primary", by_branch["main"]["bucket"])
        self.assertEqual("merged_clean", by_branch["merged-clean"]["bucket"])
        self.assertTrue(by_branch["merged-clean"]["removable"])
        self.assertEqual("open_pr", by_branch["open-pr"]["bucket"])
        self.assertEqual(12, by_branch["open-pr"]["pr_number"])
        self.assertEqual("dirty", by_branch["dirty-branch"]["bucket"])
        self.assertEqual("closed_unmerged", by_branch["closed-unmerged"]["bucket"])
        self.assertEqual(13, by_branch["closed-unmerged"]["pr_number"])
        self.assertEqual("unmerged_no_pr", by_branch["unmerged-no-pr"]["bucket"])
        self.assertEqual(1, payload["summary"]["removable"])
        self.assertEqual(6, payload["summary"]["total"])

    def test_apply_requires_yes(self):
        result = run(
            [sys.executable, str(SCRIPT), "--base", "origin/main", "--apply", str(self.repo)],
            env=self.env,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("--apply requires --yes", result.stderr)

    def test_apply_removes_only_merged_clean_worktrees(self):
        result = self.run_gc("--apply", "--yes")
        payload = json.loads(result.stdout)

        self.assertEqual([str((self.worktrees_dir / "merged-clean").resolve())], payload["removed"])
        self.assertEqual(5, payload["summary"]["total"])
        self.assertEqual(0, payload["summary"]["removable"])
        self.assertFalse((self.worktrees_dir / "merged-clean").exists())
        self.assertTrue((self.worktrees_dir / "open-pr").exists())
        self.assertTrue((self.worktrees_dir / "dirty-branch").exists())
        self.assertTrue((self.worktrees_dir / "closed-unmerged").exists())
        self.assertTrue((self.worktrees_dir / "unmerged-no-pr").exists())

    def test_invocation_worktree_is_never_removed(self):
        linked = self.worktrees_dir / "merged-clean"
        result = run(
            [
                sys.executable,
                str(SCRIPT),
                "--base",
                "origin/main",
                "--json",
                "--apply",
                "--yes",
                str(linked),
            ],
            env=self.env,
        )
        payload = json.loads(result.stdout)
        by_branch = {item["branch"]: item for item in payload["worktrees"]}

        self.assertEqual("primary", by_branch["merged-clean"]["bucket"])
        self.assertFalse(by_branch["merged-clean"]["removable"])
        self.assertTrue(linked.exists())


if __name__ == "__main__":
    unittest.main()
