"""shadow accept --row: the clean-checkout proof rerun is the only flip path."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-accept.py"


PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M — file speaks
- [in_progress] x.txt says hello ~ab12 | proof: cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)"
- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut

## Progress

- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_repo(root: Path, content: str = "hello") -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "T")
    (repo / "x.txt").write_text(content, encoding="utf-8")
    (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    return repo


def run_accept(repo: Path, row: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--row", row],
        capture_output=True,
        text=True,
        check=False,
    )


class ShadowAcceptTests(unittest.TestCase):
    def test_green_proof_flips_the_row_with_a_paired_proof_line_in_one_commit(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            before = git(repo, "rev-parse", "HEAD")
            result = run_accept(repo, "~ab12")
            text = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
            subject = git(repo, "log", "-1", "--pretty=%s")
            status = git(repo, "status", "--porcelain")
            pools = list(Path(dirname).resolve().glob("**/*shadow-accept*"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- [completed] x.txt says hello ~ab12", text)
        self.assertIn("~ab12 PROOF", text)
        self.assertIn("-> pass (accept)", text)
        self.assertEqual(commits, "2")
        self.assertIn("~ab12", subject)
        self.assertEqual(status, "")
        self.assertEqual(pools, [])

    def test_red_proof_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve(), content="goodbye")
            before_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before_plan, after_plan)
        self.assertEqual(commits, "1")

    def test_gate_class_proof_is_refused_plainly(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            result = run_accept(repo, "~cd34")
        self.assertEqual(result.returncode, 1)
        self.assertIn("gate", result.stderr.lower() + result.stdout.lower())

    def test_unrelated_staged_files_stay_out_of_the_acceptance_commit(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "other.txt").write_text("staged elsewhere\n", encoding="utf-8")
            git(repo, "add", "--", "other.txt")
            result = run_accept(repo, "~ab12")
            files = git(repo, "show", "--name-only", "--pretty=format:", "HEAD").split()
            staged = git(repo, "diff", "--cached", "--name-only").split()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(files, ["PLAN.md"])
        self.assertEqual(staged, ["other.txt"])

    def test_a_failed_commit_restores_the_plan(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            before_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            # Refuse the commit itself: the proof still passes, so this exercises
            # the write-then-commit window.
            git(repo, "config", "commit.gpgsign", "true")
            git(repo, "config", "gpg.program", str(repo / "no-such-gpg"))
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
            staged = git(repo, "diff", "--cached", "--name-only").split()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before_plan, after_plan)
        self.assertEqual(commits, "1")
        self.assertEqual(staged, [])

    def test_a_failed_commit_restores_a_staged_plan_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            # Index and working tree disagree before accept runs: the staged
            # snapshot carries a note the working tree does not.
            (repo / "PLAN.md").write_text(PLAN + "\n- staged only\n", encoding="utf-8")
            git(repo, "add", "--", "PLAN.md")
            staged_blob = git(repo, "rev-parse", ":PLAN.md")
            (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
            git(repo, "config", "commit.gpgsign", "true")
            git(repo, "config", "gpg.program", str(repo / "no-such-gpg"))
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            after_blob = git(repo, "rev-parse", ":PLAN.md")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(after_plan, PLAN)
        self.assertEqual(after_blob, staged_blob)
        self.assertEqual(commits, "1")

    def test_unknown_row_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            result = run_accept(repo, "~zz99")
        self.assertEqual(result.returncode, 1)

    def test_decoy_proof_in_row_prose_cannot_override_the_gate_class(self) -> None:
        # Prose before the ~id may legally contain "| proof: cmd ..."; the real
        # proof lives in the parsed tail and here it is gate-classed — refuse.
        plan = PLAN.replace(
            '- [in_progress] x.txt says hello ~ab12 | proof: cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'x.txt\').read_text()==\'hello\' else 1)"',
            "- [in_progress] ship it (was | proof: cmd true earlier) ~ab12 | proof: gate leo decides",
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "decoy prose proof")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("gate", result.stdout.lower() + result.stderr.lower())
        self.assertEqual(after_plan, plan)

    def test_a_plan_edit_during_the_proof_run_is_not_reverted(self) -> None:
        # The proof appends a Progress note to PLAN.md while it runs (simulating
        # a concurrent writer); the accepted plan must keep that note.
        proof = (
            "cmd python3 -c \"import pathlib; p=pathlib.Path('../../repo/PLAN.md'); "
            "p.write_text(p.read_text() + '- concurrent note\\n')\""
        )
        plan = PLAN.replace(
            'cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'x.txt\').read_text()==\'hello\' else 1)"',
            proof,
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "concurrent-writer proof")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- concurrent note", after_plan)
        self.assertIn("- [completed]", after_plan)

    def test_proof_line_lands_inside_progress_not_after_a_later_section(self) -> None:
        plan = PLAN + "\n## Lessons\n\n- keep sections after Progress\n"
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "section after progress")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(after_plan.find("~ab12 PROOF"), after_plan.find("## Lessons"))

    def test_leftover_pool_directory_refuses_without_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            leftover = repo.parent / "repo-shadow-accept" / "ab12"
            leftover.mkdir(parents=True)
            before_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before_plan, after_plan)
        self.assertEqual(commits, "1")

    def test_a_crashed_runs_registered_worktree_is_pruned_not_wedged(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            pool = repo.parent / "repo-shadow-accept"
            stale = pool / "ab12"
            git(repo, "worktree", "add", "--detach", str(stale), "HEAD")
            import shutil

            shutil.rmtree(stale)
            result = run_accept(repo, "~ab12")
            text = (repo / "PLAN.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- [completed] x.txt says hello ~ab12", text)

    def test_conflicted_plan_is_refused_before_any_work(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            git(repo, "checkout", "-qb", "side")
            (repo / "PLAN.md").write_text(PLAN + "- side note\n", encoding="utf-8")
            git(repo, "commit", "-qam", "side")
            git(repo, "checkout", "-q", "-")
            (repo / "PLAN.md").write_text(PLAN + "- main note\n", encoding="utf-8")
            git(repo, "commit", "-qam", "main")
            merge = subprocess.run(
                ["git", "-C", str(repo), "merge", "side"], capture_output=True, text=True, check=False
            )
            result = run_accept(repo, "~ab12")
        self.assertNotEqual(merge.returncode, 0)
        self.assertEqual(result.returncode, 1)
        self.assertIn("conflict", result.stdout.lower() + result.stderr.lower())

    def test_a_pipe_truncated_proof_is_refused_instead_of_rerun_shortened(self) -> None:
        # The tail residue would leave `cmd true` as the parsed proof — green,
        # and the rest of the operator's command silently dropped.
        plan = PLAN.replace(
            'cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'x.txt\').read_text()==\'hello\' else 1)"',
            "cmd true | echo also-ran",
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "pipe-truncated proof")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertIn("residue", result.stderr)
        self.assertEqual(after_plan, plan)
        self.assertEqual(commits, "2")

    def test_a_repeated_tail_key_cannot_shadow_the_first_proof(self) -> None:
        plan = PLAN.replace(
            'cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'x.txt\').read_text()==\'hello\' else 1)"',
            "cmd false | proof: cmd true",
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "repeated proof key")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertIn("repeats a tail field key", result.stderr)
        self.assertEqual(after_plan, plan)
        self.assertEqual(commits, "2")

    def test_a_row_blocked_during_the_proof_run_is_not_flipped(self) -> None:
        # The proof passes, but somebody marks the row blocked while it runs;
        # that judgment outranks a green rerun.
        proof = (
            "cmd python3 -c \"import pathlib; p=pathlib.Path('../../repo/PLAN.md'); "
            "p.write_text(p.read_text().replace('- [in_progress] x.txt', '- [blocked] x.txt'))\""
        )
        plan = PLAN.replace(
            'cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'x.txt\').read_text()==\'hello\' else 1)"',
            proof,
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "row blocked mid-run")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertIn("in_progress to blocked", result.stderr)
        self.assertIn("- [blocked] x.txt says hello ~ab12", after_plan)
        self.assertNotIn("~ab12 PROOF", after_plan)
        self.assertEqual(commits, "2")

    def test_a_row_mentioning_another_id_cannot_stand_in_for_it(self) -> None:
        # An earlier row that references ~ef56 in its needs field must not be
        # selected — its own proof would run and its own state would flip.
        plan = PLAN.replace(
            "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut",
            "- [in_progress] decoy ~ab13 | proof: cmd true | needs: ~ef56\n"
            "- [pending] shipped ~ef56 (DoD) | proof: gate leo resume: release cut",
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "decoy row")
            result = run_accept(repo, "~ef56")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertIn("gate", result.stdout.lower() + result.stderr.lower())
        self.assertEqual(after_plan, plan)
        self.assertEqual(commits, "2")


if __name__ == "__main__":
    unittest.main()
