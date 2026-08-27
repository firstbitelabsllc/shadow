"""shadow accept --row: the clean-checkout proof rerun is the only flip path."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.plan_tree_fixture import install_plan_tree


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-accept.py"
CLI = ROOT / "bin" / "shadow"

import importlib.util
_SPEC = importlib.util.spec_from_file_location("shadow_accept", SCRIPT)
accept = importlib.util.module_from_spec(_SPEC)
sys.modules["shadow_accept"] = accept
_SPEC.loader.exec_module(accept)


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
    home = repo.parent / "home"
    home.mkdir(exist_ok=True)
    plan = repo / "PLAN.md"
    state = accept._board.entity_state(plan, home=home)
    if state is None or state["entity"] is None:
        accept._board.reconcile(
            [
                {
                    "plan": str(plan),
                    "project": "demo",
                    "priority": 3,
                    "candidates": [row],
                }
            ],
            [],
            home=home,
        )
        state = accept._board.entity_state(plan, home=home)
    if not any(item["row"] == row for item in state["claims"]):
        accept._board.claim(
            plan,
            row,
            "seat-a",
            project="demo",
            priority=3,
            home=home,
        )
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--row",
            row,
            "--by",
            "seat-a",
        ],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


def run_shadow(repo: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args],
        cwd=repo,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


def fail_after_project_commit(*args, **kwargs):
    raise accept._board.BoardError("receipt unavailable")


class ShadowAcceptTests(unittest.TestCase):
    def test_git_backed_partitioned_plan_commits_root_and_objects_together(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            source = (repo / "PLAN.md").read_bytes()
            install_plan_tree(repo, source)
            git(repo, "add", "PLAN.md", "PLAN.d")
            git(repo, "commit", "-qm", "partition plan")

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 0, result.stderr)
            logical = accept._board.read_plan_text(repo / "PLAN.md")
            self.assertIn("[completed] x.txt says hello ~ab12", logical)
            self.assertIn("~ab12 PROOF", logical)
            self.assertTrue(accept._board.open_plan(repo / "PLAN.md").is_tree)
            self.assertEqual(git(repo, "status", "--porcelain"), "")
            committed = git(repo, "show", "--name-only", "--format=", "HEAD")
            self.assertIn("PLAN.md", committed)
            self.assertIn("PLAN.d/objects/sha256/", committed)

    def test_interrupted_tree_accept_is_recovered_through_the_object_store(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            plan = repo / "PLAN.md"
            install_plan_tree(repo, plan.read_bytes())
            git(repo, "add", "PLAN.md", "PLAN.d")
            git(repo, "commit", "-qm", "partition plan")
            claimed = run_shadow(
                repo, home, "throw", "--repo", str(repo), "--task", "~ab12", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            committed_root = plan.read_bytes()
            original_atomic_write = accept.atomic_write_text

            def crash_after_real_replace(path: Path, text: str):
                receipt = original_atomic_write(path, text)
                if path.resolve() == plan.resolve() and "- [completed] x.txt" in text:
                    raise SystemExit(75)
                return receipt

            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept,
                "atomic_write_text",
                side_effect=crash_after_real_replace,
            ), redirect_stdout(output), redirect_stderr(output):
                with self.assertRaises(SystemExit) as crashed:
                    accept.main(
                        ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a", "--no-push"]
                    )

            self.assertEqual(crashed.exception.code, 75)
            # The interrupted write left a newer tree generation whose root is a
            # manifest, not plan text: recovery has to read through the objects.
            self.assertNotEqual(plan.read_bytes(), committed_root)
            self.assertIn(
                "- [completed] x.txt says hello ~ab12",
                accept._board.read_plan_text(plan),
            )

            retry, retry_output = self._accept_main(repo, home)

            self.assertEqual(retry, 0, retry_output)
            logical = accept._board.read_plan_text(plan)
            self.assertIn("- [completed] x.txt says hello ~ab12", logical)
            self.assertEqual(logical.count("~ab12 PROOF"), 1)
            self.assertTrue(accept._board.open_plan(plan).is_tree)
            self.assertEqual(git(repo, "status", "--porcelain", "--untracked-files=all"), "")
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "3")
            self.assertEqual(
                json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))["claims"],
                [],
            )

    def _accept_main(self, repo: Path, home: Path) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(home)}), redirect_stdout(
            output
        ), redirect_stderr(output):
            result = accept.main(
                [
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                    "--no-push",
                ]
            )
        return result, output.getvalue()

    def _leave_completed_plan_after_atomic_replace(
        self,
        repo: Path,
        home: Path,
    ) -> bytes:
        claimed = run_shadow(
            repo,
            home,
            "throw",
            "--repo",
            str(repo),
            "--task",
            "~ab12",
            "--by",
            "seat-a",
        )
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        plan = repo / "PLAN.md"
        before_head = git(repo, "rev-parse", "HEAD")
        before_index = git(repo, "rev-parse", ":PLAN.md")
        claimed_at = json.loads(
            (home / ".shadow" / "board.json").read_text(encoding="utf-8")
        )["claims"][0]["claimed_at"]
        original_atomic_write = accept.atomic_write_text
        candidates: list[bytes] = []

        def crash_after_real_replace(path: Path, text: str) -> None:
            original_atomic_write(path, text)
            if path.resolve() == plan.resolve() and "- [completed] x.txt" in text:
                candidates.append(text.encode("utf-8"))
                raise SystemExit(75)

        output = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
            accept,
            "atomic_write_text",
            side_effect=crash_after_real_replace,
        ), redirect_stdout(output), redirect_stderr(output):
            with self.assertRaises(SystemExit) as crashed:
                accept.main(
                    [
                        "--repo",
                        str(repo),
                        "--row",
                        "~ab12",
                        "--by",
                        "seat-a",
                        "--no-push",
                    ]
                )

        self.assertEqual(crashed.exception.code, 75)
        self.assertEqual(len(candidates), 1, output.getvalue())
        self.assertEqual(plan.read_bytes(), candidates[0])
        self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
        self.assertEqual(git(repo, "rev-parse", ":PLAN.md"), before_index)
        claim = json.loads(
            (home / ".shadow" / "board.json").read_text(encoding="utf-8")
        )["claims"]
        self.assertEqual(
            [(item["row"], item["owner"]) for item in claim],
            [("~ab12", "seat-a")],
        )
        self.assertEqual(claim[0]["claimed_at"], claimed_at)
        return candidates[0]

    def test_review_worktree_cleanup_refuses_all_dirt_and_never_uses_force(self) -> None:
        for dirty_kind in ("tracked", "staged", "untracked", "ignored"):
            with self.subTest(dirty_kind=dirty_kind), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname).resolve()
                repo = make_repo(root)
                (repo / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
                git(repo, "add", ".gitignore")
                git(repo, "commit", "-qm", "ignore generated review artifact")
                review = root / "review"
                git(repo, "worktree", "add", "--detach", str(review), "HEAD")
                if dirty_kind == "tracked":
                    artifact = review / "x.txt"
                    artifact.write_text("changed\n", encoding="utf-8")
                elif dirty_kind == "staged":
                    artifact = review / "staged.txt"
                    artifact.write_text("staged\n", encoding="utf-8")
                    git(review, "add", "staged.txt")
                elif dirty_kind == "untracked":
                    artifact = review / "untracked.txt"
                    artifact.write_text("untracked\n", encoding="utf-8")
                else:
                    artifact = review / "ignored.tmp"
                    artifact.write_text("ignored\n", encoding="utf-8")
                artifact_bytes = artifact.read_bytes()

                with self.assertRaises(accept.AcceptError):
                    accept.remove_review_worktree(repo, review)

                self.assertTrue(review.is_dir())
                self.assertEqual(artifact.read_bytes(), artifact_bytes)
                self.assertIn(str(review), git(repo, "worktree", "list", "--porcelain"))

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            review = root / "clean-review"
            git(repo, "worktree", "add", "--detach", str(review), "HEAD")
            original = accept.git_completed
            calls: list[tuple[str, ...]] = []

            def observe(target: Path, *args: str, **kwargs):
                calls.append(args)
                return original(target, *args, **kwargs)

            with mock.patch.object(accept, "git_completed", side_effect=observe):
                accept.remove_review_worktree(repo, review)

            removal = next(args for args in calls if args[:2] == ("worktree", "remove"))
            self.assertEqual(removal, ("worktree", "remove", "--", str(review)))
            self.assertNotIn("--force", removal)
            self.assertFalse(review.exists())

    def test_python_review_proof_suppresses_bytecode_and_stays_clean(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            (repo / "proof_module.py").write_text("VALUE = 1\n", encoding="utf-8")
            git(repo, "add", "proof_module.py")
            git(repo, "commit", "-qm", "add proof module")

            self.assertTrue(
                accept.lead_review_passes(
                    repo,
                    [sys.executable, "-c", "import proof_module; assert proof_module.VALUE == 1"],
                    10,
                )
            )
            self.assertFalse((repo / "__pycache__").exists())

    def test_crash_after_completed_plan_replace_is_recovered_by_retry(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            with mock.patch.object(
                accept,
                "lead_review_passes",
                wraps=accept.lead_review_passes,
            ) as proof_runs:
                self._leave_completed_plan_after_atomic_replace(repo, home)
                retry, retry_output = self._accept_main(repo, home)

            self.assertEqual(retry, 0, retry_output)
            self.assertEqual(
                proof_runs.call_count,
                2,
                "retry did not rerun the committed proof",
            )
            completed = (repo / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("- [completed] x.txt says hello ~ab12", completed)
            self.assertEqual(completed.count("~ab12 PROOF"), 1)
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")
            self.assertEqual(git(repo, "status", "--porcelain", "--", "PLAN.md"), "")
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board["claims"], [])

    def test_crash_after_plan_is_staged_is_recovered_by_retry(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            plan = repo / "PLAN.md"
            before_head = git(repo, "rev-parse", "HEAD")
            claimed_at = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )["claims"][0]["claimed_at"]
            original_git_completed = accept.git_completed
            candidates: list[bytes] = []

            def crash_after_real_add(target: Path, *args: str, **kwargs):
                result = original_git_completed(target, *args, **kwargs)
                if result.returncode == 0 and args[:2] == ("add", "--"):
                    candidates.append(plan.read_bytes())
                    raise SystemExit(76)
                return result

            with mock.patch.object(
                accept,
                "lead_review_passes",
                wraps=accept.lead_review_passes,
            ) as proof_runs:
                output = io.StringIO()
                with mock.patch.dict(
                    os.environ,
                    {"HOME": str(home)},
                ), mock.patch.object(
                    accept,
                    "git_completed",
                    side_effect=crash_after_real_add,
                ), redirect_stdout(output), redirect_stderr(output):
                    with self.assertRaises(SystemExit) as crashed:
                        accept.main(
                            [
                                "--repo",
                                str(repo),
                                "--row",
                                "~ab12",
                                "--by",
                                "seat-a",
                                "--no-push",
                            ]
                        )

                self.assertEqual(crashed.exception.code, 76)
                self.assertEqual(len(candidates), 1, output.getvalue())
                self.assertEqual(plan.read_bytes(), candidates[0])
                staged = subprocess.run(
                    ["git", "-C", str(repo), "show", ":PLAN.md"],
                    capture_output=True,
                    check=True,
                ).stdout
                self.assertEqual(staged, candidates[0])
                self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
                claim = json.loads(
                    (home / ".shadow" / "board.json").read_text(encoding="utf-8")
                )["claims"]
                self.assertEqual(
                    [(item["row"], item["owner"]) for item in claim],
                    [("~ab12", "seat-a")],
                )
                self.assertEqual(claim[0]["claimed_at"], claimed_at)
                retry, retry_output = self._accept_main(repo, home)

            self.assertEqual(retry, 0, retry_output)
            self.assertEqual(
                proof_runs.call_count,
                2,
                "staged recovery did not rerun the committed proof",
            )
            completed = plan.read_text(encoding="utf-8")
            self.assertIn("- [completed] x.txt says hello ~ab12", completed)
            self.assertEqual(completed.count("~ab12 PROOF"), 1)
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")
            self.assertEqual(git(repo, "status", "--porcelain", "--", "PLAN.md"), "")
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board["claims"], [])

    def test_crash_candidate_with_an_extra_user_edit_is_preserved_and_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            with mock.patch.object(
                accept,
                "lead_review_passes",
                wraps=accept.lead_review_passes,
            ) as proof_runs:
                self._leave_completed_plan_after_atomic_replace(repo, home)
                plan = repo / "PLAN.md"
                plan.write_text(
                    plan.read_text(encoding="utf-8") + "- owner edit after crash\n",
                    encoding="utf-8",
                )
                before_plan = plan.read_bytes()
                before_index = git(repo, "rev-parse", ":PLAN.md")
                before_head = git(repo, "rev-parse", "HEAD")
                before_board = (home / ".shadow" / "board.json").read_bytes()
                retry, retry_output = self._accept_main(repo, home)

            self.assertEqual(retry, 1, retry_output)
            self.assertEqual(proof_runs.call_count, 1, "a user-edited candidate reran proof")
            self.assertEqual(plan.read_bytes(), before_plan)
            self.assertEqual(git(repo, "rev-parse", ":PLAN.md"), before_index)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before_board)

    def test_project_commit_boundary_does_not_hold_the_board_flock_needed_by_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            original_git_completed = accept.git_completed
            lock_probes: list[subprocess.CompletedProcess[str]] = []

            def git_with_hook_lock_probe(
                target: Path, *args: str, **kwargs
            ) -> subprocess.CompletedProcess[str]:
                if "commit" in args and not lock_probes:
                    # A project hook is allowed to consult Shadow. Probe the
                    # same OS flock it would need without wedging the test if
                    # accept accidentally holds that lock across `git commit`.
                    lock_probes.append(
                        subprocess.run(
                            [
                                sys.executable,
                                "-c",
                                (
                                    "import fcntl, os, sys; "
                                    "fd=os.open(sys.argv[1], os.O_RDWR); "
                                    "\ntry: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)"
                                    "\nexcept BlockingIOError: sys.exit(23)"
                                    "\nos.close(fd)"
                                ),
                                str(home / ".shadow" / ".board.lock"),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    )
                return original_git_completed(target, *args, **kwargs)

            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept,
                "git_completed",
                side_effect=git_with_hook_lock_probe,
            ), redirect_stdout(output), redirect_stderr(output):
                result = accept.main(
                    [
                        "--repo",
                        str(repo),
                        "--row",
                        "~ab12",
                        "--by",
                        "seat-a",
                        "--no-push",
                    ]
                )

            self.assertEqual(result, 0, output.getvalue())
            self.assertEqual(len(lock_probes), 1, "project commit boundary was not observed")
            self.assertEqual(
                lock_probes[0].returncode,
                0,
                "the computer-board flock was held while the project commit/hook ran",
            )

    def test_claim_token_changed_after_project_commit_refuses_the_board_close(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            original_git_completed = accept.git_completed
            replacement: dict[str, str] = {}

            def git_with_claim_replacement(
                target: Path, *args: str, **kwargs
            ) -> subprocess.CompletedProcess[str]:
                result = original_git_completed(target, *args, **kwargs)
                if result.returncode == 0 and "commit" in args and not replacement:
                    board_path = home / ".shadow" / "board.json"
                    board = json.loads(board_path.read_text(encoding="utf-8"))
                    claim = board["claims"][0]
                    claimed_at = datetime.fromisoformat(
                        claim["claimed_at"].replace("Z", "+00:00")
                    ) + timedelta(seconds=1)
                    return_by = datetime.fromisoformat(
                        claim["return_by"].replace("Z", "+00:00")
                    ) + timedelta(seconds=1)
                    claim["claimed_at"] = claimed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                    claim["return_by"] = return_by.strftime("%Y-%m-%dT%H:%M:%SZ")
                    board["revision"] += 1
                    board_path.write_text(
                        json.dumps(board, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    replacement.update(
                        claimed_at=claim["claimed_at"], return_by=claim["return_by"]
                    )
                return result

            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept,
                "git_completed",
                side_effect=git_with_claim_replacement,
            ), redirect_stdout(output), redirect_stderr(output):
                result = accept.main(
                    [
                        "--repo",
                        str(repo),
                        "--row",
                        "~ab12",
                        "--by",
                        "seat-a",
                        "--no-push",
                    ]
                )

            self.assertTrue(replacement, "project commit boundary was not observed")
            self.assertEqual(result, 1, output.getvalue())
            self.assertIn("root claim could not close", output.getvalue())
            self.assertIn("[completed] x.txt says hello ~ab12", (repo / "PLAN.md").read_text())
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")
            board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertEqual(len(board["claims"]), 1)
            self.assertEqual(board["claims"][0]["owner"], "seat-a")
            self.assertEqual(board["claims"][0]["claimed_at"], replacement["claimed_at"])

    def test_completed_retry_rejects_an_exact_receipt_outside_progress(self) -> None:
        _, _, _, proof, _ = accept.find_row(PLAN, "~ab12")
        exact_argv = shlex.join(shlex.split(proof.removeprefix("cmd ")))
        completed = PLAN.replace("- [in_progress] x.txt", "- [completed] x.txt", 1)
        completed += (
            "\n## Appendix\n\n"
            f"- 2026-08-10T01:00:00Z ~ab12 PROOF {exact_argv} -> pass (accept)\n"
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            (repo / "PLAN.md").write_text(completed, encoding="utf-8")
            git(repo, "commit", "-qam", "forge receipt outside Progress")
            result = run_accept(repo, "~ab12")
            board = json.loads((root / "home" / ".shadow" / "board.json").read_text())

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("proof", result.stderr.lower())
        self.assertEqual(board["claims"][0]["row"], "~ab12")

    def test_completed_retry_rejects_a_different_proof_inside_progress(self) -> None:
        completed = PLAN.replace("- [in_progress] x.txt", "- [completed] x.txt", 1)
        completed = completed.rstrip() + (
            "\n- 2026-08-10T01:00:00Z ~ab12 PROOF true -> pass (accept)\n"
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            (repo / "PLAN.md").write_text(completed, encoding="utf-8")
            git(repo, "commit", "-qam", "forge wrong accept proof")
            result = run_accept(repo, "~ab12")
            board = json.loads((root / "home" / ".shadow" / "board.json").read_text())

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("proof", result.stderr.lower())
        self.assertEqual(board["claims"][0]["row"], "~ab12")

    def test_staged_plan_data_is_refused_and_preserved_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            plan = repo / "PLAN.md"
            plan.write_text(PLAN + "\n- staged owner data\n", encoding="utf-8")
            git(repo, "add", "--", "PLAN.md")
            before_plan = plan.read_bytes()
            before_index = git(repo, "rev-parse", ":PLAN.md")
            before_head = git(repo, "rev-parse", "HEAD")
            before_board = (home / ".shadow" / "board.json").read_bytes()

            result = run_shadow(
                repo,
                home,
                "accept",
                "--repo",
                str(repo),
                "--row",
                "~ab12",
                "--by",
                "seat-a",
                "--no-push",
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("staged index changed", result.stderr)
            self.assertEqual(plan.read_bytes(), before_plan)
            self.assertEqual(git(repo, "rev-parse", ":PLAN.md"), before_index)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before_board)

    def test_uncommitted_proof_change_cannot_authorize_completion(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            plan = repo / "PLAN.md"
            plan.write_text(PLAN.replace("proof: cmd python3", "proof: cmd false # python3"), encoding="utf-8")
            git(repo, "commit", "-qam", "committed red proof")
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            committed = plan.read_text(encoding="utf-8")
            plan.write_text(committed.replace("proof: cmd false # python3", "proof: cmd true # python3"), encoding="utf-8")
            before_head = git(repo, "rev-parse", "HEAD")

            refused = run_shadow(
                repo,
                home,
                "accept",
                "--repo",
                str(repo),
                "--row",
                "~ab12",
                "--by",
                "seat-a",
                "--no-push",
            )

            self.assertEqual(refused.returncode, 1)
            self.assertIn("committed authority", refused.stderr)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
            self.assertNotIn("[completed]", plan.read_text(encoding="utf-8"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")

    def test_only_the_claim_owner_can_accept_the_row(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            before_plan = (repo / "PLAN.md").read_bytes()
            before_head = git(repo, "rev-parse", "HEAD")
            before_board = (home / ".shadow" / "board.json").read_bytes()

            refused = run_shadow(
                repo,
                home,
                "accept",
                "--repo",
                str(repo),
                "--row",
                "~ab12",
                "--by",
                "seat-b",
                "--no-push",
            )

            self.assertEqual(refused.returncode, 1)
            self.assertIn("claimed by seat-a, not seat-b", refused.stderr)
            self.assertEqual((repo / "PLAN.md").read_bytes(), before_plan)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before_board)

    def test_owner_adopted_during_proof_cannot_be_completed_by_the_old_seat(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            plan = repo / "PLAN.md"
            accept._board.reconcile(
                [{"plan": str(plan), "project": "demo", "priority": 3, "candidates": ["~ab12"]}],
                [],
                home=home,
            )
            accept._board.claim(
                plan,
                "~ab12",
                "seat-a",
                project="demo",
                priority=3,
                now=datetime.now(timezone.utc) - timedelta(hours=9),
                home=home,
            )
            before_plan = plan.read_bytes()
            before_head = git(repo, "rev-parse", "HEAD")

            def adopt_after_proof(*args, **kwargs) -> bool:
                accept._board.claim(
                    plan,
                    "~ab12",
                    "seat-b",
                    project="demo",
                    priority=3,
                    adopt_expired=True,
                    home=home,
                )
                return True

            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept,
                "lead_review_passes",
                side_effect=adopt_after_proof,
            ), redirect_stdout(output), redirect_stderr(output):
                result = accept.main(
                    [
                        "--repo",
                        str(repo),
                        "--row",
                        "~ab12",
                        "--by",
                        "seat-a",
                        "--no-push",
                    ]
                )

            self.assertEqual(result, 1, output.getvalue())
            self.assertIn("claim is owned by seat-b", output.getvalue())
            self.assertEqual(plan.read_bytes(), before_plan)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-b")

    def test_accepting_one_row_preserves_the_other_owner_as_resume(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            plan = repo / "PLAN.md"
            plan.write_text(
                PLAN.replace(
                    "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut",
                    "- [pending] second cmd row ~cd34 (DoD) | proof: cmd true",
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "two accept rows")
            for row, owner in (("~ab12", "seat-a"), ("~cd34", "seat-b")):
                claimed = run_shadow(
                    repo,
                    home,
                    "throw",
                    "--repo",
                    str(repo),
                    "--task",
                    row,
                    "--by",
                    owner,
                )
                self.assertEqual(claimed.returncode, 0, claimed.stderr)

            accepted = run_shadow(
                repo,
                home,
                "accept",
                "--repo",
                str(repo),
                "--row",
                "~ab12",
                "--by",
                "seat-a",
                "--no-push",
            )

            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(
                [(item["row"], item["owner"]) for item in payload["claims"]],
                [("~cd34", "seat-b")],
            )
            self.assertEqual(payload["entities"][0]["resume"], "~cd34")

    def test_existing_board_refuses_accept_for_an_unregistered_entity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            (root / "registered").mkdir()
            (root / "unregistered").mkdir()
            registered = make_repo(root / "registered")
            unregistered = make_repo(root / "unregistered")
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                registered,
                home,
                "throw",
                "--repo",
                str(registered),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            before_plan = (unregistered / "PLAN.md").read_bytes()
            before_head = git(unregistered, "rev-parse", "HEAD")
            before_board = (home / ".shadow" / "board.json").read_bytes()

            refused = run_shadow(
                unregistered,
                home,
                "accept",
                "--repo",
                str(unregistered),
                "--row",
                "~ab12",
                "--by",
                "seat-a",
                "--no-push",
            )

            self.assertEqual(refused.returncode, 1)
            self.assertIn("not registered on the computer board", refused.stderr)
            self.assertEqual((unregistered / "PLAN.md").read_bytes(), before_plan)
            self.assertEqual(git(unregistered, "rev-parse", "HEAD"), before_head)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before_board)

    def test_declared_nested_entity_runs_proof_in_its_directory_and_commits_only_its_plan(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = root / "repo"
            nested = repo / "plans" / "widget"
            home = root / "home"
            nested.mkdir(parents=True)
            home.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "t@example.invalid")
            git(repo, "config", "user.name", "T")
            root_plan = PLAN.replace(
                "- Mode: ship\n",
                "- Mode: ship\n- Plans: plans/*/PLAN.md\n",
            ).replace("- Project: demo", "- Project: demo-root")
            nested_plan = PLAN.replace(
                "pathlib.Path('x.txt').read_text()=='hello'",
                "pathlib.Path('entity-only.txt').read_text()=='nested'",
            )
            (repo / "PLAN.md").write_text(root_plan, encoding="utf-8")
            (nested / "PLAN.md").write_text(nested_plan, encoding="utf-8")
            (nested / "entity-only.txt").write_text("nested", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "nested fixture")
            root_before = (repo / "PLAN.md").read_bytes()
            env = {
                **os.environ,
                "HOME": str(home),
                "SHADOW_PORTFOLIO_ROOT": str(repo),
            }

            claimed = subprocess.run(
                [str(CLI), "throw", "--repo", str(nested), "--task", "~ab12", "--by", "seat-a"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            accepted = subprocess.run(
                [
                    str(CLI),
                    "accept",
                    "--repo",
                    str(nested),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            self.assertEqual((repo / "PLAN.md").read_bytes(), root_before)
            self.assertIn(
                "- [completed] x.txt says hello ~ab12",
                (nested / "PLAN.md").read_text(encoding="utf-8"),
            )
            changed = git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines()
            self.assertEqual(changed, ["plans/widget/PLAN.md"])
            payload = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["claims"], [])

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
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            before_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            original_git_completed = accept.git_completed
            commit_invocations: list[tuple[str, ...]] = []

            def refuse_project_commit(target: Path, *args: str, **kwargs):
                if "commit" in args:
                    commit_invocations.append(args)
                    return subprocess.CompletedProcess(args, 1, "", "commit refused")
                return original_git_completed(target, *args, **kwargs)

            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept,
                "git_completed",
                side_effect=refuse_project_commit,
            ), redirect_stdout(output), redirect_stderr(output):
                result = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a", "--no-push"]
                )
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
            staged = git(repo, "diff", "--cached", "--name-only").split()
        self.assertEqual(result, 1, output.getvalue())
        self.assertEqual(before_plan, after_plan)
        self.assertEqual(commits, "1")
        self.assertEqual(staged, [])
        self.assertEqual(
            commit_invocations[0][:9],
            (
                "-c", "core.hooksPath=/dev/null",
                "-c", "commit.gpgSign=false",
                "-c", "maintenance.autoDetach=false",
                "-c", "gc.autoDetach=false",
                "commit",
            ),
        )

    def test_a_failed_tree_commit_restores_root_index_and_objects(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            source = (repo / "PLAN.md").read_bytes()
            install_plan_tree(repo, source)
            git(repo, "add", "PLAN.md", "PLAN.d")
            git(repo, "commit", "-qm", "partition plan")
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo, home, "throw", "--repo", str(repo), "--task", "~ab12", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            root_before = (repo / "PLAN.md").read_bytes()
            objects_before = {
                path.relative_to(repo).as_posix(): path.read_bytes()
                for path in (repo / "PLAN.d" / "objects" / "sha256").glob("*/*")
            }
            original_git_completed = accept.git_completed

            def refuse_project_commit(target: Path, *args: str, **kwargs):
                if "commit" in args:
                    return subprocess.CompletedProcess(args, 1, "", "commit refused")
                return original_git_completed(target, *args, **kwargs)

            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept, "git_completed", side_effect=refuse_project_commit,
            ), redirect_stdout(output), redirect_stderr(output):
                result = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a", "--no-push"]
                )

            objects_after = {
                path.relative_to(repo).as_posix(): path.read_bytes()
                for path in (repo / "PLAN.d" / "objects" / "sha256").glob("*/*")
            }
            self.assertEqual(result, 1, output.getvalue())
            self.assertEqual((repo / "PLAN.md").read_bytes(), root_before)
            self.assertEqual(objects_after, objects_before)
            self.assertEqual(git(repo, "status", "--porcelain"), "")
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")

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
        self.assertIn("staged index changed", result.stderr)
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
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cannot be frozen after the proof", result.stderr)
        self.assertIn("- concurrent note", after_plan)
        self.assertIn("- [in_progress] x.txt says hello ~ab12", after_plan)
        self.assertNotIn("~ab12 PROOF", after_plan)

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
        self.assertIn("cannot be frozen after the proof", result.stderr)
        self.assertIn("- [blocked] x.txt says hello ~ab12", after_plan)
        self.assertNotIn("~ab12 PROOF", after_plan)
        self.assertEqual(commits, "2")

    def test_a_release_failure_after_commit_is_repaired_by_retrying_accept(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            remote = root / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            git(repo, "remote", "add", "origin", str(remote))
            git(repo, "push", "-qu", "origin", "HEAD:main")
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            first_output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                accept._board,
                "release",
                side_effect=fail_after_project_commit,
            ), redirect_stdout(first_output), redirect_stderr(first_output):
                first = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )

            self.assertEqual(first, 1, first_output.getvalue())
            self.assertIn("proof landed", first_output.getvalue())
            self.assertIn("[completed] x.txt says hello ~ab12", (repo / "PLAN.md").read_text())
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")
            self.assertIn("[completed] x.txt says hello", git(remote, "show", "main:PLAN.md"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["row"], "~ab12")

            retry_output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(home)}), redirect_stdout(
                retry_output
            ), redirect_stderr(retry_output):
                retry = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )

            self.assertEqual(retry, 0, retry_output.getvalue())
            self.assertIn("already proven", retry_output.getvalue())
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")
            self.assertIn("[completed] x.txt says hello", git(remote, "show", "main:PLAN.md"))
            self.assertIn("~ab12 PROOF", git(remote, "show", "main:PLAN.md"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_accept_from_a_sibling_worktree_mutates_only_the_stored_plan_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            sibling = root / "sibling"
            git(repo, "worktree", "add", "-q", "-b", "sibling", str(sibling), "HEAD")
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            accepted = run_accept(sibling, "~ab12")

            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            self.assertIn("[completed] x.txt says hello", (repo / "PLAN.md").read_text())
            self.assertNotIn("[completed] x.txt says hello", (sibling / "PLAN.md").read_text())
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_accepting_the_last_row_clears_the_project_resume_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            plan_path = repo / "PLAN.md"
            plan_path.write_text(
                PLAN.replace(
                    "- [in_progress] x.txt says hello ~ab12 | proof: cmd python3 -c \"import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\"\n"
                    "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
                    "- [completed] prerequisite is proven ~cd34 | proof: cmd true\n"
                    "- [in_progress] x.txt says hello ~ab12 (DoD) | proof: cmd python3 -c \"import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\" | needs: ~cd34\n",
                ).replace(
                    "## Progress\n",
                    "## Progress\n\n"
                    "- 2026-08-06T09:59:00Z ~cd34 PROOF true -> pass (fixture)\n",
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "keep one final unresolved row")
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo,
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~ab12",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            accepted = run_accept(repo, "~ab12")

            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])
            self.assertIsNone(payload["entities"][0]["resume"])

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


class ARejectedPushLeavesTheFlipReachable(unittest.TestCase):
    """The rejection message must make its own advice followable: the flip
    commit stays on the checkout's branch, and the message NAMES that
    repository and branch. Accept commits at the STORED plan pointer, which
    can differ from the --repo argument the operator typed — an unnamed
    location reads as a destroyed commit, and the operator duplicates the
    flip by hand (measured 2026-08-11 on this very plan).
    """

    def test_the_rejection_names_the_repo_and_branch_bearing_the_flip(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            remote = root / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            git(repo, "remote", "add", "origin", str(remote))
            git(repo, "push", "-qu", "origin", "HEAD:main")
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo, home, "throw", "--repo", str(repo), "--task", "~ab12",
                "--by", "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            claim_receipt = next(
                json.loads(line) for line in claimed.stderr.splitlines()
                if line.startswith("{")
            )
            hook = remote / "hooks" / "pre-receive"
            hook.write_text("#!/bin/sh\necho protected >&2\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)
            result = run_accept(repo, "~ab12")
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            branch = git(repo, "symbolic-ref", "--short", "HEAD")
            self.assertIn(str(repo), result.stderr, "the rejection must name the repository holding the flip")
            self.assertIn(f"(branch {branch})", result.stderr, "the rejection must name the branch holding the flip")
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2",
                             "the flip commit must remain reachable on the named branch")
            self.assertIn("[completed] x.txt says hello ~ab12",
                          git(repo, "show", "HEAD:PLAN.md"))
            stored = json.loads(git(remote, "show", f"{claim_receipt['ref']}:claim.json"))
            self.assertEqual(stored["state"], "acquired")
            board_payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(board_payload["claims"][0]["owner"], "seat-a")


class ARemoteManagedAcceptClosesOnlyAfterPublication(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path, dict]:
        repo = make_repo(root)
        remote = root / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "-qu", "origin", "HEAD:main")
        git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
        home = root / "home"
        home.mkdir()
        claimed = run_shadow(
            repo, home, "throw", "--repo", str(repo), "--task", "~ab12",
            "--by", "seat-a",
        )
        if claimed.returncode:
            self.fail(claimed.stderr)
        receipt = next(
            json.loads(line) for line in claimed.stderr.splitlines()
            if line.startswith("{")
        )
        return repo, remote, home, receipt

    def test_publish_then_completed_cas_then_local_release(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, receipt = self.fixture(Path(dirname).resolve())
            acquired_tip = git(remote, "rev-parse", receipt["ref"])

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("remote claim completed", result.stdout)
            completed_tip = git(remote, "rev-parse", receipt["ref"])
            stored = json.loads(git(remote, "show", f"{completed_tip}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("completed", "completed"))
            main = git(remote, "rev-parse", "refs/heads/main")
            parents = git(remote, "rev-list", "--parents", "-n", "1", completed_tip).split()
            self.assertIn(acquired_tip, parents[1:])
            self.assertIn(main, parents[1:])
            self.assertEqual(stored["plan"]["head"], main)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_local_completion_reservation_can_outlive_the_matching_remote_lease(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, receipt = self.fixture(Path(dirname).resolve())
            original = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"HOME": str(home)}),
                mock.patch.object(
                    accept._board,
                    "COMPLETION_RESERVATION_MINUTES",
                    24 * 60,
                ),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                result = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )

            self.assertEqual(result, 0, output.getvalue())
            completed_tip = git(remote, "rev-parse", receipt["ref"])
            stored = json.loads(git(remote, "show", f"{completed_tip}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("completed", "completed"))
            self.assertEqual(stored["claim"], original["claim"])
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_completed_retry_authenticates_origin_before_pushing_a_behind_branch(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, remote, home, receipt = self.fixture(root)
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"HOME": str(home)}),
                mock.patch.object(
                    accept._board,
                    "COMPLETION_RESERVATION_MINUTES",
                    24 * 60,
                ),
                mock.patch.object(
                    accept._remote_claim,
                    "transition",
                    return_value={"status": "error", "failure": "ambiguous_remote"},
                ),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                first = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )
            self.assertEqual(first, 1, output.getvalue())
            completed_head = git(repo, "rev-parse", "HEAD")
            self.assertEqual(git(remote, "rev-parse", "main"), completed_head)

            advanced = root / "advanced"
            subprocess.run(["git", "clone", "-q", str(remote), str(advanced)], check=True)
            git(advanced, "config", "user.email", "t@example.invalid")
            git(advanced, "config", "user.name", "T")
            (advanced / "AFTER.txt").write_text("after completion\n", encoding="utf-8")
            git(advanced, "add", "AFTER.txt")
            git(advanced, "commit", "-qm", "advance published authority")
            git(advanced, "push", "-q", "origin", "HEAD:main")
            self.assertNotEqual(git(remote, "rev-parse", "main"), completed_head)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), completed_head)

            retry = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            self.assertIn("remote claim completed", retry.stdout)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), completed_head)
            completed_tip = git(remote, "rev-parse", receipt["ref"])
            stored = json.loads(git(remote, "show", f"{completed_tip}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("completed", "completed"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_completed_retry_authenticates_a_current_lifecycle_archive(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, remote, home, receipt = self.fixture(root)
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"HOME": str(home)}),
                mock.patch.object(
                    accept._remote_claim,
                    "transition",
                    return_value={"status": "error", "failure": "ambiguous_remote"},
                ),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                first = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )
            self.assertEqual(first, 1, output.getvalue())

            completed_head = git(remote, "rev-parse", "main")
            completed_blob = git(remote, "rev-parse", f"{completed_head}:PLAN.md")
            completed_plan = git(remote, "show", "main:PLAN.md") + "\n"
            row_line = next(
                line for line in completed_plan.splitlines()
                if "[completed]" in line and "~ab12" in line
            )
            receipt_line = next(
                line for line in completed_plan.splitlines()
                if "~ab12 PROOF" in line and "pass (accept)" in line
            )
            archive_body = (
                "# Archived milestone: demo\n\n"
                "Source: `PLAN.md`\n\n"
                "## Exact milestone block\n\n"
                f"{row_line}\n"
                "## Exact Progress receipts\n\n"
                f"{receipt_line}\n"
            )
            digest = hashlib.sha256(archive_body.encode("utf-8")).hexdigest()
            cas = "1" * 64
            marker = (
                "- Archived milestone: [demo](docs/plan-archive/demo.md) "
                f"<!-- shadow:lifecycle:demo:sha256:{digest}:cas:{cas}:"
                f"head:{completed_head}:blob:{completed_blob}:successor:~cd34 -->"
            )
            archive = (
                f"<!-- shadow:archive:v1:demo:sha256:{digest}:cas:{cas}:"
                f"head:{completed_head}:blob:{completed_blob}:successor:~cd34 -->\n"
                f"{archive_body}"
            )
            compacted = "\n".join(
                line for line in completed_plan.splitlines()
                if line not in {row_line, receipt_line}
            ).replace("## Tasks\n", f"## Tasks\n\n{marker}\n", 1) + "\n"

            advanced = root / "advanced"
            subprocess.run(["git", "clone", "-q", str(remote), str(advanced)], check=True)
            git(advanced, "config", "user.email", "t@example.invalid")
            git(advanced, "config", "user.name", "T")
            (advanced / "PLAN.md").write_text(compacted, encoding="utf-8")
            archived = advanced / "docs" / "plan-archive" / "demo.md"
            archived.parent.mkdir(parents=True)
            archived.write_text(archive, encoding="utf-8")
            git(advanced, "add", "PLAN.md", "docs/plan-archive/demo.md")
            git(advanced, "commit", "-qm", "shadow: archive milestone demo")
            git(advanced, "push", "-q", "origin", "HEAD:main")

            snapshot = accept._remote_claim.published_plan_snapshot(repo, receipt["plan"])
            self.assertIsNotNone(snapshot)
            published_bytes, default_tip = snapshot
            self.assertIn(marker, published_bytes.decode("utf-8"))
            _, _, _, local_proof, _ = accept.find_row(
                (repo / "PLAN.md").read_text(encoding="utf-8"), "~ab12"
            )
            self.assertTrue(
                accept.completion_matches_lifecycle_archive(
                    repo,
                    published_bytes.decode("utf-8"),
                    receipt["plan"],
                    default_tip,
                    "~ab12",
                    local_proof,
                )
            )

            retry = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            self.assertIn("remote claim completed", retry.stdout)
            stored = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("completed", "completed"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_completion_reservation_refuses_identity_drift_or_an_earlier_local_lease(self) -> None:
        remote = {
            "entity": "a" * 64,
            "row": "~ab12",
            "owner": "seat-a",
            "claimed_at": "2026-08-22T02:55:23Z",
            "return_by": "2026-08-22T10:55:23Z",
            "recovery": "probe-proof-then-adopt-park-or-close",
        }
        local = {**remote, "return_by": "2026-08-22T14:17:10Z"}

        self.assertTrue(accept.completion_reservation_matches(local, remote))
        self.assertTrue(accept.completion_reservation_matches(remote, remote))
        self.assertFalse(
            accept.completion_reservation_matches(
                {key: value for key, value in local.items() if key != "return_by"},
                remote,
            )
        )
        for key, changed in (
            ("entity", "b" * 64),
            ("row", "~cd34"),
            ("owner", "seat-b"),
            ("claimed_at", "2026-08-22T02:55:24Z"),
            ("recovery", "changed"),
            ("return_by", "2026-08-22T10:55:22Z"),
        ):
            with self.subTest(key=key):
                self.assertFalse(
                    accept.completion_reservation_matches({**local, key: changed}, remote)
                )

    def test_no_push_keeps_both_remote_and_local_claim_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, receipt = self.fixture(Path(dirname).resolve())
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--repo", str(repo), "--row", "~ab12",
                    "--by", "seat-a", "--no-push",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            stored = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
            self.assertEqual(stored["state"], "acquired")
            self.assertNotIn("[completed] x.txt says hello", git(remote, "show", "main:PLAN.md"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")

    def test_ambiguous_completed_cas_after_publish_retains_claim_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, _ = self.fixture(Path(dirname).resolve())
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"HOME": str(home)}),
                mock.patch.object(
                    accept._remote_claim,
                    "transition",
                    return_value={"status": "error", "failure": "ambiguous_remote"},
                ),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                result = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )
            self.assertEqual(result, 1, output.getvalue())
            self.assertNotIn("accepted ~ab12", output.getvalue())
            self.assertIn("[completed] x.txt says hello", git(remote, "show", "main:PLAN.md"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")

    def test_completed_retry_closes_remote_claim_after_local_claim_was_released(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, receipt = self.fixture(Path(dirname).resolve())
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"HOME": str(home)}),
                mock.patch.object(
                    accept._remote_claim,
                    "transition",
                    return_value={"status": "error", "failure": "ambiguous_remote"},
                ),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                first = accept.main(
                    ["--repo", str(repo), "--row", "~ab12", "--by", "seat-a"]
                )
            self.assertEqual(first, 1, output.getvalue())
            plan = repo / "PLAN.md"
            plan_token, plan_bytes = accept._board.committed_plan_snapshot(plan)
            plan_text = plan_bytes.decode("utf-8")
            state = accept._board.entity_state(plan, home=home)
            claim = state["claims"][0]
            accept._board.release(
                plan,
                "~ab12",
                owner="seat-a",
                reason="completed",
                resumes=["~cd34"],
                expected_plan=plan_token,
                expected_text=plan_text,
                expected_claim=claim,
                home=home,
            )
            git(repo, "checkout", "--detach", plan_token["head"])

            retry = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            stored = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("completed", "completed"))
            self.assertEqual(stored["plan"]["head"], git(remote, "rev-parse", "main"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_status_command_recovers_a_published_remote_only_completion_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, remote, home_a, receipt = self.fixture(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                    "--no-push",
                ],
                env={**os.environ, "HOME": str(home_a)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            git(repo, "push", "-qu", "origin", "HEAD:main")

            second = root / "second"
            subprocess.run(
                ["git", "clone", "-q", str(remote), str(second)],
                check=True,
            )
            git(second, "config", "user.email", "t@example.invalid")
            git(second, "config", "user.name", "T")
            home_b = root / "home-b"
            home_b.mkdir()

            observed = run_shadow(
                second,
                home_b,
                "status",
                "--root",
                str(second),
                "--by",
                "seat-a",
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            board = json.loads((home_b / ".shadow" / "board.json").read_text())
            entity = board["entities"][0]["id"]
            recovery_line = next(
                line.strip()
                for line in observed.stdout.splitlines()
                if line.strip().startswith("Recover:")
            )
            self.assertEqual(
                recovery_line,
                f"Recover: shadow accept --entity {entity} --row '~ab12' --by seat-a",
            )
            recovery_argv = shlex.split(recovery_line.removeprefix("Recover: "))

            recovered = subprocess.run(
                [str(CLI), *recovery_argv[1:]],
                cwd=second,
                env={**os.environ, "HOME": str(home_b)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)
            self.assertIn("remote claim completed", recovered.stdout)
            completed_tip = git(remote, "rev-parse", receipt["ref"])
            stored = json.loads(git(remote, "show", f"{completed_tip}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("completed", "completed"))
            self.assertEqual(stored["entity"], entity)
            self.assertEqual(stored["project"], "demo")
            self.assertEqual(stored["owner"], "seat-a")
            self.assertEqual(stored["row"], "~ab12")
            self.assertEqual(
                json.loads((home_b / ".shadow" / "board.json").read_text())["claims"],
                [],
            )

            repeated = subprocess.run(
                [str(CLI), *recovery_argv[1:]],
                cwd=second,
                env={**os.environ, "HOME": str(home_b)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            self.assertEqual(git(remote, "rev-parse", receipt["ref"]), completed_tip)
            after = run_shadow(
                second,
                home_b,
                "status",
                "--root",
                str(second),
                "--by",
                "seat-a",
            )
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertNotIn("Recover:", after.stdout)

    def test_detached_unpublished_completion_keeps_both_claims_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, receipt = self.fixture(Path(dirname).resolve())
            first = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                    "--no-push",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            git(repo, "push", "-qu", "origin", "HEAD:feature")
            git(repo, "config", "branch.feature.remote", "origin")
            git(repo, "config", "branch.feature.merge", "refs/heads/feature")
            git(repo, "checkout", "--detach", "HEAD")

            retry = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            self.assertIn("not published", retry.stdout + retry.stderr)
            stored = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("acquired", "acquire"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")

    def test_detached_reverted_completion_keeps_both_claims_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, remote, home, receipt = self.fixture(Path(dirname).resolve())
            first = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                    "--no-push",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            completed = git(repo, "rev-parse", "HEAD")
            git(repo, "push", "-qu", "origin", "HEAD:main")
            git(repo, "revert", "--no-edit", completed)
            git(repo, "push", "-qu", "origin", "HEAD:main")
            git(repo, "checkout", "--detach", completed)

            retry = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            self.assertIn("no longer carries", retry.stdout + retry.stderr)
            self.assertIn("[in_progress] x.txt says hello", git(remote, "show", "main:PLAN.md"))
            stored = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
            self.assertEqual((stored["state"], stored["reason"]), ("acquired", "acquire"))
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")


class AChallengedFoundationDoesNotFlipSilently(unittest.TestCase):
    """The contradiction triangle: challenger, owner, dependent. A written
    challenge against a row — or anything in its needs-ancestry — must hold
    the flip until a person resolves it; nothing gated this before, so a
    dependent could accept work whose basis was under an undelivered
    challenge. The one coordination behavior that takes three roles.
    """

    HELLO_PROOF = (
        "cmd python3 -c \"import pathlib,sys; "
        "sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\""
    )

    def _plan(self, tasks: str, contradictions: str) -> str:
        return (
            "# Demo\n\n## Brief\n\n- Project: demo\n- Mode: ship\n\n## Tasks\n\n"
            "### M — file speaks\n" + tasks +
            "\n## Contradictions\n\n" + contradictions +
            "\n## Progress\n\n- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command\n"
        )

    def _run(self, plan: str, row: str):
        context = tempfile.TemporaryDirectory()
        root = Path(context.name).resolve()
        repo = make_repo(root)
        (repo / "PLAN.md").write_text(plan, encoding="utf-8")
        git(repo, "commit", "-qam", "scenario plan")
        result = run_accept(repo, row)
        return context, repo, result

    def test_a_challenge_naming_the_row_holds_its_flip(self) -> None:
        plan = self._plan(
            f"- [in_progress] x.txt says hello ~ab12 | proof: {self.HELLO_PROOF}\n"
            "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
            "- ~ab12 asserts hello but the file contract under review says goodbye\n",
        )
        context, repo, result = self._run(plan, "~ab12")
        with context:
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("written challenge", result.stderr)
            self.assertIn("file contract under review", result.stderr)
            self.assertIn("- [in_progress] x.txt says hello ~ab12", (repo / "PLAN.md").read_text())

    def test_a_challenge_on_a_needs_ancestor_holds_the_dependent(self) -> None:
        plan = self._plan(
            f"- [completed] foundation holds ~aa00 | proof: {self.HELLO_PROOF}\n"
            f"- [in_progress] x.txt says hello ~ab12 | proof: {self.HELLO_PROOF} | needs: ~aa00\n"
            "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
            "- ~aa00 was accepted against a fixture that no longer matches production\n",
        )
        context, repo, result = self._run(plan, "~ab12")
        with context:
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("needs-ancestry", result.stderr)
            self.assertIn("~aa00", result.stderr)

    def test_an_unrelated_or_empty_contradiction_does_not_hold_the_flip(self) -> None:
        plan = self._plan(
            f"- [in_progress] x.txt says hello ~ab12 | proof: {self.HELLO_PROOF}\n"
            "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
            "- None recorded yet.\n- ~zz99 an unrelated surface disagrees with its docs\n",
        )
        context, repo, result = self._run(plan, "~ab12")
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("- [completed] x.txt says hello ~ab12", (repo / "PLAN.md").read_text())

    def test_only_an_explicitly_resolved_challenge_releases_the_flip(self) -> None:
        plan = self._plan(
            f"- [in_progress] x.txt says hello ~ab12 | proof: {self.HELLO_PROOF}\n"
            "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
            "- RESOLVED 2026-08-26: ~ab12 keeps hello | winner: hello\n",
        )
        context, repo, result = self._run(plan, "~ab12")
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_winner_language_without_resolved_remains_an_acceptance_challenge(self) -> None:
        plan = self._plan(
            f"- [in_progress] x.txt says hello ~ab12 | proof: {self.HELLO_PROOF}\n"
            "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
            "- ~ab12 hello vs goodbye | winner: hello\n",
        )
        context, repo, result = self._run(plan, "~ab12")
        with context:
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("acceptance challenge", result.stderr)
            self.assertIn("needs-ancestry", result.stderr)


class AForgedCompletionCannotBeLaunderedByTheFastPath(unittest.TestCase):
    """The other end of the backdated-receipt chain (~lgrf). accept's
    completed fast path republishes an already-completed row after checking a
    matching receipt TEXT line — so a hand-fabricated commit (flip + typed
    pre-cutover receipt) could be laundered to other seats instead of proven.
    The lint gate that fast path already calls is the chokepoint: with
    grandfathering bound to a frozen id set, a forged receipt makes the plan
    lint-blocked, and the fast path refuses.
    """

    def test_the_fast_path_refuses_a_backdated_forged_receipt(self) -> None:
        forged = PLAN.replace(
            "- [in_progress] x.txt says hello ~ab12",
            "- [completed] x.txt says hello ~ab12",
        ).replace(
            "## Progress\n",
            "## Progress\n\n- 2000-01-01T00:00:00Z ~ab12 PROOF i pinky promise it passed\n",
        )
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            (repo / "PLAN.md").write_text(forged, encoding="utf-8")
            git(repo, "commit", "-qam", "forged completion")
            result = run_accept(repo, "~ab12")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            # Measured refusal reason: the receipt must match the row's actual
            # proof argv, which prose cannot. The lint gate behind it is the
            # second layer, not the first.
            self.assertIn("without a matching accept proof", result.stderr)
            # The forgery is never republished as proven.
            self.assertNotIn("already proven", result.stdout)
            self.assertIn("- [completed] x.txt says hello ~ab12",
                          (repo / "PLAN.md").read_text(encoding="utf-8"))


class NeedsIsAReadinessGate(unittest.TestCase):
    """grammar.md: "a task is ready when it is pending and every needs-target
    is completed". throw enforced that; accept did not, so a row could be
    flipped over a dependency still at pending and lint called it clean."""

    def test_unmet_needs_are_found_in_a_multi_id_value(self) -> None:
        plan = (
            "- [completed] one ~aa11 | proof: cmd true\n"
            "- [pending] two ~bb22 | proof: cmd true\n"
        )
        self.assertEqual(accept.unmet_needs(plan, "~aa11, ~bb22"), ["~bb22"])
        self.assertEqual(accept.unmet_needs(plan, "~aa11"), [])
        self.assertEqual(accept.unmet_needs(plan, ""), [])

    def test_the_scan_pattern_is_unanchored(self) -> None:
        # The first version of this check reused ROW_ID_RE, whose ^...$ anchors
        # make findall return nothing on a multi-id value -- the check existed
        # and enforced nothing. Keep the two patterns distinct.
        self.assertEqual(accept.NEEDS_REF_RE.findall("~aa11, ~bb22"), ["~aa11", "~bb22"])
        self.assertEqual(accept.ROW_ID_RE.findall("~aa11, ~bb22"), [])

    def test_a_need_reopened_during_the_proof_run_stops_the_flip(self) -> None:
        # Readiness was decided only from the pre-run snapshot: the re-read
        # after the proof compared state and proof and threw the fresh `needs`
        # away, so a dependency reopened while the proof ran still flipped.
        proof = (
            "cmd python3 -c \"import pathlib; p=pathlib.Path('../../repo/PLAN.md'); "
            # The needle is split so the command cannot match its own text and
            # rewrite the proof field instead of the dependency row.
            "p.write_text(p.read_text().replace('[comp'+'leted] dep', '[pending] dep'))\""
        )
        plan = PLAN.replace(
            "- [in_progress] x.txt says hello ~ab12 | proof: cmd python3 -c "
            "\"import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\"",
            "- [completed] dep ~ee55 | proof: cmd true\n"
            f"- [in_progress] x.txt says hello ~ab12 | needs: ~ee55 | proof: {proof}",
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            git(repo, "commit", "-qam", "need reopened mid-run")
            result = run_accept(repo, "~ab12")
            after_plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            commits = git(repo, "rev-list", "--count", "HEAD")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cannot be frozen after the proof", result.stderr)
        self.assertIn("- [in_progress] x.txt says hello ~ab12", after_plan)
        self.assertNotIn("~ab12 PROOF", after_plan)
        self.assertEqual(commits, "2")

    def test_accept_refuses_a_row_whose_need_is_not_completed(self) -> None:
        # ~cd34 is [pending], so ~ab12 is not ready even though its proof passes.
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "~ab12 | proof: cmd", "~ab12 | needs: ~cd34 | proof: cmd", 1
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "unmet accept dependency")
            result = run_accept(repo, "~ab12")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("still needs ~cd34", result.stdout + result.stderr)
            self.assertIn("[in_progress] x.txt", plan.read_text(encoding="utf-8"))


class ProofScriptArgumentsAreValidatedIdentically(unittest.TestCase):
    ORIGINAL = """cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\""""

    def test_a_missing_interpreter_script_is_refused_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    self.ORIGINAL, "cmd node scripts/definitely-missing.mjs"
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "missing proof script")

            result = run_accept(repo, "~ab12")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("interpreter script", result.stdout + result.stderr)
            self.assertNotIn("[completed] x.txt says hello", plan.read_text(encoding="utf-8"))

    def test_a_committed_relative_interpreter_script_can_be_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            script = repo / "scripts" / "proof.py"
            script.parent.mkdir()
            script.write_text("raise SystemExit(0)\n", encoding="utf-8")
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    self.ORIGINAL, "cmd python3 scripts/proof.py"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md", "scripts/proof.py")
            git(repo, "commit", "-m", "relative proof script")

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[completed] x.txt says hello", plan.read_text(encoding="utf-8"))

    def test_env_chdir_cannot_redirect_a_relative_script_outside_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            outside = root / "outside"
            outside.mkdir()
            (outside / "proof.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    self.ORIGINAL, f"cmd env -C {outside} python3 proof.py"
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "redirected proof script")

            result = run_accept(repo, "~ab12")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("working directory", result.stdout + result.stderr)
            self.assertNotIn("[completed] x.txt says hello", plan.read_text(encoding="utf-8"))


class ShellOperatorsInAProofAreRefused(unittest.TestCase):
    """The false green, end to end, at the only path that flips a row.

    `accept` runs a cmd proof through `shlex.split` with NO shell, so `&&`
    reaches argv[0] as a literal argument. `cmd echo done && shadow --version`
    ran `echo`, exited 0, flipped the row to `[completed]` and wrote
    `-> pass (accept)` — while `shadow --version` never executed. The tell was
    already in the receipt (`shlex.join` quotes the `'&&'`) and nothing read it.

    Lint refuses it too, but the refusal lives here as well on purpose: a plan
    can reach accept without lint having run, and two gates that disagree are
    how this got shipped in the first place.
    """

    PROOFED = PLAN.replace(
        """cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\"""",
        "cmd echo done && python3 -c \"import sys; sys.exit(1)\"",
    )

    def test_the_row_is_not_flipped_and_the_reason_names_the_operator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            (repo / "PLAN.md").write_text(self.PROOFED, encoding="utf-8")
            git(repo, "commit", "-qam", "proof with an operator")

            result = run_accept(repo, "~ab12")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("&&", result.stdout + result.stderr)
            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            self.assertNotIn("[completed] x.txt says hello", plan,
                             "the row flipped on a proof whose command never ran")
            self.assertNotIn("-> pass (accept)", plan)

    def test_a_deliberate_shell_still_runs(self) -> None:
        # A guard that refuses the sanctioned form too would just push people
        # back to lying in the proof.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            (repo / "PLAN.md").write_text(
                PLAN.replace(
                    """cmd python3 -c "import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='hello' else 1)\"""",
                    "cmd bash -c 'set -e; test -f x.txt && grep -q hello x.txt'",
                ), encoding="utf-8")
            git(repo, "commit", "-qam", "proof wrapped in a shell")

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[completed] x.txt says hello",
                          (repo / "PLAN.md").read_text(encoding="utf-8"))

    def test_the_shell_exemption_covers_the_script_only(self) -> None:
        # Bugbot (PR #282, High): exempting the whole argv once `-c` appeared
        # rebuilt the false green inside the sanctioned form. bash runs `true`
        # and takes `&&`, `grep`, ... as positional arguments it never runs.
        self.assertEqual(["&&"], accept._shell_operators("bash -c 'true' && grep -q nope x.txt"))
        self.assertEqual([], accept._shell_operators("bash -c 'set -e; true && true'"))

    def test_an_operator_glued_to_its_neighbour_is_still_an_operator(self) -> None:
        # Codex (PR #282, P1): `shlex.split` returns `done&&`, so comparing
        # whole tokens saw no offender while accept still ran `echo` alone.
        self.assertEqual(["&&"], accept._shell_operators("echo done&& false"))
        self.assertEqual([">"], accept._shell_operators("echo done>/missing"))
        self.assertEqual([">&"], accept._shell_operators("true 2>&1"))

    def test_a_quoted_metacharacter_is_a_literal_the_proof_meant_to_pass(self) -> None:
        self.assertEqual([], accept._shell_operators("grep -q 'a&&b' x.txt"))
        self.assertEqual([], accept._shell_operators("echo 'done > here'"))


class AcceptReadsAProgressHeadingTheWayLintDoes(unittest.TestCase):
    """Bugbot (PR #282, Medium): lint prefix-matches section headings.

    `## Progress — the receipts` is a Progress section to the enforcer, so an
    exact-string match here would fail the append AFTER the proof had already
    passed: a plan lint calls valid that accept cannot finish.
    """

    def test_a_suffixed_progress_heading_still_takes_the_proof_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            (repo / "PLAN.md").write_text(
                PLAN.replace("## Progress\n", "## Progress — the receipts\n"), encoding="utf-8")
            git(repo, "commit", "-qam", "a suffixed Progress heading")

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("[completed] x.txt says hello", plan)
            self.assertIn("~ab12 PROOF", plan)

    def test_a_different_word_starting_with_progress_is_not_a_progress_section(self) -> None:
        self.assertIsNone(accept.PROGRESS_HEADING_RE.search("## Progressive\n"))


class AcceptNeverCommitsAPlanLintBlocks(unittest.TestCase):
    def test_a_passing_proof_cannot_flip_the_dod_before_its_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            plan = repo / "PLAN.md"
            before = plan.read_text(encoding="utf-8").replace(
                "proof: gate leo resume: release cut",
                "proof: cmd python3 -c 'raise SystemExit(0)'",
            )
            plan.write_text(before, encoding="utf-8")
            git(repo, "commit", "-qam", "make the early DoD proof runnable")
            head = git(repo, "rev-parse", "HEAD")

            result = run_accept(repo, "~cd34")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("DOD-EARLY", result.stderr)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)
            self.assertEqual(plan.read_text(encoding="utf-8"), before)
            state = accept._board.entity_state(plan, home=repo.parent / "home")
            self.assertEqual(["~cd34"], [claim["row"] for claim in state["claims"]])

    def test_a_locally_deleted_committed_proof_binary_does_not_veto_another_row(self) -> None:
        # Codex (PR #359, P2): the gate must read the checkout accept proves
        # and commits against. Judging argv[0] from the dirty working tree let
        # an unrelated local deletion emit blocking PROOF-ARGV0 and refuse a
        # flip the committed HEAD — whose clean worktree ran the proof — runs.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp))
            plan = repo / "PLAN.md"
            tool = repo / "tools" / "proof.sh"
            tool.parent.mkdir()
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "proof: gate leo resume: release cut", "proof: cmd tools/proof.sh"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "a committed proof executable")
            tool.unlink()

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[completed] x.txt says hello", plan.read_text(encoding="utf-8"))
            self.assertFalse(tool.exists(), "accept must not resurrect unrelated local state")

    def test_a_completed_retry_cannot_reconcile_a_claim_for_a_lint_blocked_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            plan = repo / "PLAN.md"
            _, _, _, proof, _ = accept.find_row(PLAN, "~ab12")
            argv = accept.proof_argv(proof.removeprefix("cmd "))
            completed = accept.completed_plan_text(
                PLAN, "~ab12", argv, "2026-08-11T00:00:00Z"
            ).replace("- Mode: ship", "- Mode: turbo")
            plan.write_text(completed, encoding="utf-8")
            git(repo, "commit", "-qam", "completed but lint blocked")

            home = root / "home"
            home.mkdir()
            accept._board.reconcile(
                [{"plan": str(plan), "project": "demo", "priority": 3, "candidates": ["~ab12"]}],
                [],
                home=home,
            )
            accept._board.claim(plan, "~ab12", "seat-a", project="demo", priority=3, home=home)
            board_path = home / ".shadow" / "board.json"
            board_before = board_path.read_bytes()
            head = git(repo, "rev-parse", "HEAD")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--row", "~ab12", "--by", "seat-a"],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("MODE-ILLEGAL", result.stderr)
            self.assertEqual(board_path.read_bytes(), board_before)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)
            self.assertEqual(plan.read_text(encoding="utf-8"), completed)


FOREIGN_PROOF_PLAN = PLAN.replace(
    "### M — file speaks\n",
    "### M — file speaks\n"
    "- [completed] an older row named a source tool ~ef56 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_x\n",
).replace(
    "- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command\n",
    "- 2026-08-06T09:00:00Z ~ef56 PROOF scripts/shadow-python.sh -m unittest tests.test_x -> pass\n"
    "- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command\n",
)


class ProofRootIsResolvedOrNamed(unittest.TestCase):
    """A refusal must name the row it is about and the root it wants.

    `--repo` is where proofs RUN, not where the plan lives. For a machine-local
    plan under `~/.shadow/plans/<slug>/` whose proofs name a source checkout,
    passing the plan directory makes every such proof unresolvable.

    Measured 2026-08-17: `shadow accept --repo ~/.shadow/plans/shadow --row
    '~nx05'` refused with `PROOF-ARGV0 on line 26` — line 26 was `~gskl`, an
    unrelated row completed weeks earlier. The message was true and unusable:
    it named a line number in a row the seat was not touching, and never said
    that passing the source checkout as `--repo` was the fix. Re-running with
    the source checkout succeeded immediately.

    So the refusal must say three things: WHICH row is blocking, that it is not
    the row being accepted, and that `--repo` is the proof root.
    """

    def _refusal(self) -> str:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            (repo / "PLAN.md").write_text(FOREIGN_PROOF_PLAN, encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "foreign proof")
            result = run_accept(repo, "~ab12")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            return result.stdout + result.stderr

    def test_the_refusal_names_the_blocking_row(self) -> None:
        self.assertIn("~ef56", self._refusal())

    def test_the_refusal_says_the_blocking_row_is_not_the_one_being_accepted(self) -> None:
        text = self._refusal()
        self.assertIn("not the row", text.lower())

    def test_the_refusal_names_repo_as_the_proof_root(self) -> None:
        self.assertIn("--repo", self._refusal())


ORIGIN_NAMED_LOCAL_PLAN = """# Widget

## Brief

- Project: widget
- Mode: ship

## Tasks

### Origin-named sibling
- [in_progress] origin plan row ~cd34 | proof: cmd true
- [pending] origin plan done ~ef56 (DoD) | proof: cmd true | needs: ~cd34

## Progress

- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command
"""

SIDECAR_LOCAL_PLAN = """# Sidecar

## Brief

- Project: sidecar
- Mode: ship

## Tasks

### Non-origin-named plan
- [in_progress] sidecar-only row ~ab12 | proof: cmd true
- [pending] sidecar done ~aa11 (DoD) | proof: cmd true | needs: ~ab12

## Progress

- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command
"""


class ALocalEntityAndExplicitProofRepoSelectTheExactPlan(unittest.TestCase):
    """Two local plans can share one Git origin; --entity names the plan.

    `shadow accept --repo` guesses a registered local plan from checkout
    basename and origin. When the intended cmd-proof row lives only on the
    non-origin-named sibling, that guess cannot select it. Path-free local
    `--entity` stays refused. The public pairing is `--entity` for the exact
    local plan plus `--repo` for the proof checkout only.
    """

    def _world(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        home = root / "home"
        repo = root / "dev" / "widget"
        repo.mkdir(parents=True)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.invalid")
        git(repo, "config", "user.name", "T")
        git(repo, "remote", "add", "origin", "git@github.com:example/widget.git")
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        git(repo, "add", "README.md")
        git(repo, "commit", "-qm", "seed")

        origin_plan = home / ".shadow" / "plans" / "widget" / "PLAN.md"
        sidecar_plan = home / ".shadow" / "plans" / "sidecar" / "PLAN.md"
        origin_plan.parent.mkdir(parents=True)
        sidecar_plan.parent.mkdir(parents=True)
        origin_plan.write_text(ORIGIN_NAMED_LOCAL_PLAN, encoding="utf-8")
        sidecar_plan.write_text(SIDECAR_LOCAL_PLAN, encoding="utf-8")

        payload = accept._board.reconcile(
            [
                {
                    "plan": str(origin_plan),
                    "project": "widget",
                    "priority": 2,
                    "candidates": ["~cd34"],
                },
                {
                    "plan": str(sidecar_plan),
                    "project": "sidecar",
                    "priority": 3,
                    "candidates": ["~ab12"],
                },
            ],
            [],
            home=home,
        )
        by_plan = {Path(item["plan"]).resolve(): item["id"] for item in payload["entities"]}
        origin_entity = by_plan[origin_plan.resolve()]
        sidecar_entity = by_plan[sidecar_plan.resolve()]
        accept._board.claim(
            sidecar_plan, "~ab12", "seat-a", project="sidecar", priority=3, home=home
        )
        accept._board.claim(
            origin_plan, "~cd34", "seat-a", project="widget", priority=2, home=home
        )
        guessed = accept._board.local_plan_for_repo(repo, home=home)
        return {
            "home": home,
            "repo": repo,
            "origin_plan": origin_plan,
            "sidecar_plan": sidecar_plan,
            "origin_entity": origin_entity,
            "sidecar_entity": sidecar_entity,
            "guessed": guessed,
            "origin_text": origin_plan.read_text(encoding="utf-8"),
            "sidecar_text": sidecar_plan.read_text(encoding="utf-8"),
        }

    def _accept(self, world, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env={**os.environ, "HOME": str(world["home"])},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_entity_and_explicit_repo_accept_the_non_origin_named_plan(self) -> None:
        world = self._world()
        self.assertEqual(world["guessed"], world["origin_plan"].resolve())

        result = self._accept(
            world,
            "--entity",
            world["sidecar_entity"],
            "--repo",
            str(world["repo"]),
            "--row",
            "~ab12",
            "--by",
            "seat-a",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        sidecar = world["sidecar_plan"].read_text(encoding="utf-8")
        self.assertIn("[completed] sidecar-only row ~ab12", sidecar)
        self.assertIn("~ab12 PROOF true -> pass (accept)", sidecar)
        self.assertEqual(
            world["origin_plan"].read_text(encoding="utf-8"), world["origin_text"]
        )
        self.assertEqual(
            accept._board.entity_state(world["sidecar_plan"], home=world["home"])["claims"],
            [],
        )
        origin_claims = accept._board.entity_state(
            world["origin_plan"], home=world["home"]
        )["claims"]
        self.assertEqual([item["row"] for item in origin_claims], ["~cd34"])

    def test_basename_origin_guessing_cannot_select_the_sibling_plan(self) -> None:
        world = self._world()
        self.assertEqual(world["guessed"], world["origin_plan"].resolve())

        result = self._accept(
            world,
            "--repo",
            str(world["repo"]),
            "--row",
            "~ab12",
            "--by",
            "seat-a",
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no task carries ~ab12", result.stderr)
        self.assertEqual(
            world["sidecar_plan"].read_text(encoding="utf-8"), world["sidecar_text"]
        )
        self.assertEqual(
            world["origin_plan"].read_text(encoding="utf-8"), world["origin_text"]
        )

    def test_path_free_local_entity_remains_refused(self) -> None:
        world = self._world()

        result = self._accept(
            world,
            "--entity",
            world["sidecar_entity"],
            "--row",
            "~ab12",
            "--by",
            "seat-a",
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--entity recovery requires a Git-backed project plan", result.stderr)
        self.assertEqual(
            world["sidecar_plan"].read_text(encoding="utf-8"), world["sidecar_text"]
        )

    def test_mismatched_entity_repo_row_owner_fail_closed(self) -> None:
        world = self._world()
        other = world["home"].parent / "not-a-repo"
        other.mkdir()
        cases = (
            (
                [
                    "--entity",
                    world["sidecar_entity"],
                    "--repo",
                    str(world["repo"]),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-b",
                ],
                "claimed by seat-a, not seat-b",
            ),
            (
                [
                    "--entity",
                    world["origin_entity"],
                    "--repo",
                    str(world["repo"]),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                "no task carries ~ab12",
            ),
            (
                [
                    "--entity",
                    world["sidecar_entity"],
                    "--repo",
                    str(world["repo"]),
                    "--row",
                    "~cd34",
                    "--by",
                    "seat-a",
                ],
                "no task carries ~cd34",
            ),
            (
                [
                    "--entity",
                    "a" * 64,
                    "--repo",
                    str(world["repo"]),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                "not registered on the computer board",
            ),
            (
                [
                    "--entity",
                    world["sidecar_entity"],
                    "--repo",
                    str(other),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                ],
                "--repo must name a Git source checkout",
            ),
        )
        for argv, needle in cases:
            with self.subTest(needle=needle):
                result = self._accept(world, *argv)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(needle, result.stderr)
                self.assertEqual(
                    world["sidecar_plan"].read_text(encoding="utf-8"),
                    world["sidecar_text"],
                )
                self.assertEqual(
                    world["origin_plan"].read_text(encoding="utf-8"),
                    world["origin_text"],
                )

    def test_git_backed_entity_does_not_take_repo(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            home = root / "home"
            home.mkdir()
            claimed = run_shadow(
                repo, home, "throw", "--repo", str(repo), "--task", "~ab12", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            entity = json.loads((home / ".shadow" / "board.json").read_text())["entities"][0]["id"]
            before = (repo / "PLAN.md").read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--entity",
                    entity,
                    "--repo",
                    str(repo),
                    "--row",
                    "~ab12",
                    "--by",
                    "seat-a",
                    "--no-push",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Git-backed", result.stderr)
            self.assertIn("--repo", result.stderr)
            self.assertEqual((repo / "PLAN.md").read_text(encoding="utf-8"), before)
