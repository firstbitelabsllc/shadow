from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from browser.server import plan_record


ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "scripts" / "shadow-init.py"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INIT), *args],
        cwd=cwd,
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

    def test_creates_one_v4_plan_at_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            result = run("--here", cwd=repo)
            record = plan_record(repo / "PLAN.md", repo)
            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "created PLAN.md\n")
        self.assertTrue(record["lint"]["parse_ok"])
        self.assertEqual(record["lint"]["blocking"], 0)
        self.assertEqual(record["project"], "useful-project")
        self.assertEqual(record["mode"], "explore")
        self.assertEqual(record["board"]["priority"], "3")
        self.assertNotIn(dirname, str(record))
        self.assertIn("the full product outcome, scenario matrix", plan)
        self.assertIn("every reachable row is proven", plan)
        self.assertNotIn("Outcome ID:", plan)
        self.assertNotIn("Decision ID:", plan)
        self.assertNotIn("Option A:", plan)
        self.assertNotIn("smallest", plan.lower())
        self.assertNotIn(" ".join(("one", "bounded")), plan.lower())

    def test_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            (repo / "PLAN.md").write_text("keep me\n", encoding="utf-8")
            result = run("--here", cwd=repo)
            self.assertEqual((repo / "PLAN.md").read_text(encoding="utf-8"), "keep me\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_requires_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            outside = Path(dirname)
            result = run("--here", cwd=outside)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not inside a Git worktree", result.stderr)

    def test_rejects_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            nested = repo / "nested"
            nested.mkdir()
            result = run("--here", cwd=nested)
        self.assertEqual(result.returncode, 2)
        self.assertIn("project root", result.stderr)


if __name__ == "__main__":
    unittest.main()
