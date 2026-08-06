from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)


class CheckpointTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        (repo / "PLAN.md").write_text(
            "# Demo\n\n## Work\n\n- [in_progress] Prove the result\n\n## Progress\n",
            encoding="utf-8",
        )
        git(repo, "add", "PLAN.md")
        git(repo, "commit", "-qm", "base")
        return repo

    def run_checkpoint(self, repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(CLI),
                "checkpoint",
                str(repo / "PLAN.md"),
                "Prove the result",
                "The focused check passed",
                "--proof",
                "tests/test_checkpoint.py",
                "--json",
                *extra,
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_updates_exact_row_and_writes_bounded_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            result = self.run_checkpoint(repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            receipt = repo / payload["evidence"]
            self.assertIn("- [completed] Prove the result", plan)
            self.assertIn(f"[receipt:{payload['receipt_id']}]", plan)
            self.assertTrue(receipt.is_file())
            encoded = receipt.read_text(encoding="utf-8")
            self.assertNotIn(dirname, encoded)
            self.assertEqual(payload["plan"], "PLAN.md")

    def test_same_checkpoint_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            first = self.run_checkpoint(repo)
            second = self.run_checkpoint(repo)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(first.stdout)["receipt_id"], json.loads(second.stdout)["receipt_id"])
            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            self.assertEqual(plan.count("[receipt:"), 1)
            self.assertEqual(len(list((repo / ".shadow" / "evidence").glob("*.json"))), 1)

    def test_blocked_checkpoint_records_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            result = self.run_checkpoint(repo, "--status", "blocked", "--blocker", "Waiting for fixture")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- [blocked] Prove the result", (repo / "PLAN.md").read_text(encoding="utf-8"))
            self.assertEqual(json.loads(result.stdout)["blocker"], "Waiting for fixture")

    def test_rejects_private_paths_and_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            for proof in ("/Users/person/proof.txt", "token=super-secret-value"):
                result = subprocess.run(
                    [str(CLI), "checkpoint", str(repo / "PLAN.md"), "Prove the result", "summary", "--proof", proof],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
            self.assertFalse((repo / ".shadow").exists())

    def test_requires_one_exact_plan_row(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            result = subprocess.run(
                [str(CLI), "checkpoint", str(repo / "PLAN.md"), "Unknown task", "summary", "--proof", "test"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("exactly one", result.stderr)

    def test_rejects_symlinked_evidence_parent(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            outside = root / "outside"
            outside.mkdir()
            (repo / ".shadow").symlink_to(outside, target_is_directory=True)
            result = self.run_checkpoint(repo)
            self.assertEqual(result.returncode, 1)
            self.assertIn("must not contain symlinks", result.stderr)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
