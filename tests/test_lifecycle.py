"""Dry-run-first, provenance-safe hot-plan compaction."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-lifecycle.py"
CLI = ROOT / "bin" / "shadow"
LINT = ROOT / "scripts" / "shadow-lint.py"
SPEC = importlib.util.spec_from_file_location("shadow_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lifecycle
SPEC.loader.exec_module(lifecycle)


PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### Finished work
- [completed] first result exists ~aa11 | proof: cmd true
- [completed] finished result is accepted ~bb22 (DoD) | proof: cmd true | needs: ~aa11

### Next work
- [pending] next result starts ~cc33 | proof: cmd true | needs: ~bb22
- [pending] next result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~cc33

## Progress

- 2026-08-10T00:00:00Z ~aa11 PROOF true -> pass
  exact first-result detail remains attached
- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass
- 2026-08-10T00:02:00Z NOTE unrelated history remains live
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_repo(root: Path, plan: str = PLAN) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Lifecycle Test")
    git(repo, "config", "user.email", "lifecycle@example.invalid")
    (repo / "PLAN.md").write_text(plan, encoding="utf-8")
    git(repo, "add", "PLAN.md")
    git(repo, "commit", "--quiet", "-m", "seed")
    return repo


def make_nested_repo(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    entity = repo / "entities" / "alpha"
    entity.mkdir(parents=True)
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Lifecycle Test")
    git(repo, "config", "user.email", "lifecycle@example.invalid")
    (entity / "PLAN.md").write_text(PLAN, encoding="utf-8")
    git(repo, "add", "entities/alpha/PLAN.md")
    git(repo, "commit", "--quiet", "-m", "seed nested entity")
    return repo, entity


def run(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args, "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, json.loads(result.stdout)


def run_command(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [str(CLI), "lifecycle", "--repo", str(repo), *args, "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, json.loads(result.stdout)


class BudgetsAreEnforced(unittest.TestCase):
    def test_all_three_checked_in_limits_have_teeth(self) -> None:
        too_many_rows = "\n".join(
            f"- [pending] result {index} ~aa11 | proof: cmd true"
            for index in range(lifecycle.MAX_TASK_ROWS + 1)
        )
        too_many_milestones = "\n".join(
            f"### milestone {index}" for index in range(lifecycle.MAX_MILESTONES + 1)
        )
        self.assertIn(
            "bytes",
            lifecycle.measure("x" * (lifecycle.MAX_PLAN_BYTES + 1))["exceeded"],
        )
        self.assertIn("task_rows", lifecycle.measure(too_many_rows)["exceeded"])
        structured = f"## Tasks\n\n{too_many_milestones}\n\n## Progress\n"
        self.assertIn("milestones", lifecycle.measure(structured)["exceeded"])

    def test_over_budget_dry_run_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            oversized = PLAN + "\n<!-- " + ("x" * lifecycle.MAX_PLAN_BYTES) + " -->\n"
            (repo / "PLAN.md").write_text(oversized, encoding="utf-8")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "oversized")
            before = (repo / "PLAN.md").read_bytes()
            head = git(repo, "rev-parse", "HEAD")

            result, report = run_command(repo)

            self.assertEqual(result.returncode, 1, report)
            self.assertIn("bytes", report["budget"]["before"]["exceeded"])
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)


class CleanupIsDryRunFirstAndIdempotent(unittest.TestCase):
    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            before = (repo / "PLAN.md").read_bytes()
            head = git(repo, "rev-parse", "HEAD")

            result, report = run(repo, "--milestone", "Finished work")

            self.assertEqual(result.returncode, 0, report)
            self.assertEqual(report["action"], "would_archive")
            self.assertFalse(report["changed"])
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertFalse((repo / "docs" / "plan-archive").exists())
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)

    def test_apply_preserves_receipts_commits_once_and_repeats_as_noop(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            original = (repo / "PLAN.md").read_text(encoding="utf-8")
            block = original[
                original.index("### Finished work") : original.index("### Next work")
            ]
            hook = repo / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\nexit 91\n", encoding="utf-8")
            hook.chmod(0o755)
            before_head = git(repo, "rev-parse", "HEAD")

            result, report = run(repo, "--apply", "--milestone", "Finished work")

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "archived")
            self.assertTrue(report["changed"])
            self.assertNotEqual(report["commit"], before_head)
            self.assertEqual(git(repo, "rev-list", "--count", f"{before_head}..HEAD"), "1")
            changed = set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines())
            self.assertEqual(changed, {"PLAN.md", "docs/plan-archive/finished-work.md"})

            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            archive = (repo / "docs" / "plan-archive" / "finished-work.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(block, archive)
            self.assertIn("~aa11 PROOF true -> pass\n  exact first-result detail", archive)
            self.assertNotIn("~aa11", plan)
            self.assertNotIn("~bb22", plan)
            self.assertIn("shadow:lifecycle:finished-work", plan)
            self.assertIn("unrelated history remains live", plan)
            self.assertNotIn("needs: ~bb22", plan)
            self.assertIn(
                "STRUCT archived milestone finished-work | successor: Next work",
                plan,
            )
            self.assertEqual(report["successor"], "Next work")
            lint = subprocess.run(
                [sys.executable, str(LINT), str(repo / "PLAN.md")],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

            archived_head = git(repo, "rev-parse", "HEAD")
            repeated, repeated_report = run(
                repo, "--apply", "--milestone", "Finished work"
            )
            self.assertEqual(repeated.returncode, 0, repeated_report)
            self.assertEqual(repeated_report["action"], "already_archived")
            self.assertFalse(repeated_report["changed"])
            self.assertEqual(git(repo, "rev-parse", "HEAD"), archived_head)

    def test_dispatcher_documents_and_runs_the_dry_run(self) -> None:
        help_result = subprocess.run(
            [str(CLI), "help", "lifecycle"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--apply --repo PATH", help_result.stdout)

    def test_nested_entity_archives_adjacent_and_commits_only_its_two_paths(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, entity = make_nested_repo(Path(dirname))
            before_head = git(repo, "rev-parse", "HEAD")

            result, report = run(
                entity, "--apply", "--milestone", "Finished work"
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            expected_archive = entity / "docs" / "plan-archive" / "finished-work.md"
            self.assertEqual(Path(report["plan"]).resolve(), (entity / "PLAN.md").resolve())
            self.assertEqual(Path(report["archive"]).resolve(), expected_archive.resolve())
            changed = set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines())
            self.assertEqual(
                changed,
                {
                    "entities/alpha/PLAN.md",
                    "entities/alpha/docs/plan-archive/finished-work.md",
                },
            )
            self.assertEqual(git(repo, "rev-list", "--count", f"{before_head}..HEAD"), "1")
            plan = (entity / "PLAN.md").read_text(encoding="utf-8")
            link = re.search(r"\[finished-work\]\(([^)]+)\)", plan)
            self.assertIsNotNone(link)
            self.assertEqual((entity / link.group(1)).resolve(), expected_archive.resolve())
            self.assertTrue(expected_archive.is_file())

            archived_head = git(repo, "rev-parse", "HEAD")
            repeated, repeated_report = run(
                entity, "--apply", "--milestone", "Finished work"
            )
            self.assertEqual(repeated.returncode, 0, repeated_report)
            self.assertEqual(repeated_report["action"], "already_archived")
            self.assertEqual(git(repo, "rev-parse", "HEAD"), archived_head)


class DirtyOrProvenanceBearingStateIsRefused(unittest.TestCase):
    def test_dirty_plan_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            with (repo / "PLAN.md").open("a", encoding="utf-8") as stream:
                stream.write("\n")
            result, report = run(repo, "--milestone", "Finished work")
            self.assertEqual(result.returncode, 1, report)
            self.assertEqual(report["action"], "refused")
            self.assertIn("changed", report["error"])

    def test_clean_archive_collision_is_refused_as_existing_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            target = repo / "docs" / "plan-archive" / "finished-work.md"
            target.parent.mkdir(parents=True)
            target.write_text("independent archive\n", encoding="utf-8")
            git(repo, "add", target.relative_to(repo).as_posix())
            git(repo, "commit", "--quiet", "-m", "independent archive")

            result, report = run(repo, "--milestone", "Finished work")

            self.assertEqual(result.returncode, 1, report)
            self.assertIn("different provenance", report["error"])
            self.assertEqual(target.read_text(encoding="utf-8"), "independent archive\n")

    def test_unproven_milestone_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            text = PLAN.replace(
                "- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass\n", ""
            )
            repo = make_repo(Path(dirname), text)
            result, report = run(repo, "--milestone", "Finished work")
            self.assertEqual(result.returncode, 1, report)
            self.assertIn("lacks PROOF", report["error"])

    def test_non_git_and_symlinked_plans_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            plain = root / "plain"
            plain.mkdir()
            (plain / "PLAN.md").write_text(PLAN, encoding="utf-8")
            plain_result, plain_report = run(plain)
            self.assertEqual(plain_result.returncode, 1, plain_report)

            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "--quiet")
            git(repo, "config", "user.name", "Lifecycle Test")
            git(repo, "config", "user.email", "lifecycle@example.invalid")
            (repo / "REAL.md").write_text(PLAN, encoding="utf-8")
            os.symlink("REAL.md", repo / "PLAN.md")
            git(repo, "add", "PLAN.md", "REAL.md")
            git(repo, "commit", "--quiet", "-m", "symlink plan")
            linked_result, linked_report = run(repo)
            self.assertEqual(linked_result.returncode, 1, linked_report)
            self.assertIn("non-symlink", linked_report["error"])

    def test_retirement_refuses_to_invent_deletion_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            result, report = run(repo)
            self.assertEqual(result.returncode, 0, report)
            self.assertFalse(report["retirement"]["supported"])
            self.assertEqual(report["retirement"]["action"], "none")
            self.assertIn("never guesses", report["retirement"]["reason"])


if __name__ == "__main__":
    unittest.main()
