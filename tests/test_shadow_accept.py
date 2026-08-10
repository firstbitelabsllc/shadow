"""shadow accept --row: the clean-checkout proof rerun is the only flip path."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
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

    def test_legacy_selector_accepts_and_records_only_the_canonical_id(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "x.txt says hello ~ab12", "P9a~formats x.txt says hello ~3549"
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "retain legacy selector")
            home = root / "home"
            home.mkdir()
            accept._board.reconcile(
                [{
                    "plan": str(plan),
                    "project": "demo",
                    "priority": 3,
                    "candidates": ["~3549"],
                }],
                [],
                home=home,
            )
            accept._board.claim(
                plan, "~3549", "seat-a", project="demo", priority=3, home=home
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--row",
                    "P9a~formats",
                    "--by",
                    "seat-a",
                    "--no-push",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            landed = plan.read_text(encoding="utf-8")
            self.assertIn("[completed] P9a~formats x.txt says hello ~3549", landed)
            self.assertEqual(landed.count("~3549 PROOF"), 1)
            self.assertNotIn("P9a~formats PROOF", landed)
            board_text = (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            self.assertNotIn("P9a~formats", board_text)
            self.assertEqual(json.loads(board_text)["claims"], [])

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
            self.assertNotIn("[completed] x.txt says hello", git(remote, "show", "main:PLAN.md"))
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
                    "- [pending] shipped ~cd34 (DoD) | proof: gate leo resume: release cut\n",
                    "",
                ),
                encoding="utf-8",
            )
            git(repo, "commit", "-qam", "keep one final row")
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
        ).replace(
            "- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command\n",
            "- 2026-08-06T10:00:00Z POSTURE Broad->Close | harness: the proof command\n"
            "- 2026-08-06T10:00:01Z ~ee55 PROOF true -> completed dependency\n",
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


class AcceptUsesTheEnforcersRowGrammar(unittest.TestCase):
    """The only flip path must not accept a plan its row enforcer refuses."""

    def test_an_unrelated_malformed_row_blocks_the_selected_flip(self) -> None:
        # `find_row` can still locate ~ab12, and its proof would pass.  Before
        # this check accept ignored the second row entirely while lint blocked
        # it, so the only completion path could commit a plan its own grammar
        # had already rejected.
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            plan = repo / "PLAN.md"
            malformed = plan.read_text(encoding="utf-8").replace(
                "## Progress\n",
                "## Worklane boundary\n\n"
                "- [pending] malformed unrelated row ~zz99 | proof: prose only\n\n"
                "## Progress\n",
            )
            plan.write_text(malformed, encoding="utf-8")
            git(repo, "commit", "-qam", "add malformed row outside tasks")

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("row grammar blocks acceptance", result.stderr)
            after = plan.read_text(encoding="utf-8")
            self.assertIn("- [in_progress] x.txt says hello ~ab12", after)
            self.assertNotIn("~ab12 PROOF", after)
            self.assertEqual(git(repo, "rev-list", "--count", "HEAD"), "2")


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
    """The flip path cannot turn a grammar-invalid plan into a commit.

    The proof is deliberately valid.  The unrelated illegal mode is the
    existing blocker that lint reports, and accept used to ignore it, append
    its receipt, and commit the whole invalid PLAN.md.
    """

    def test_a_blocking_plan_finding_refuses_the_flip_before_the_commit(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve())
            plan = repo / "PLAN.md"
            invalid = plan.read_text(encoding="utf-8").replace(
                "- Mode: ship", "- Mode: not-a-mode"
            )
            plan.write_text(invalid, encoding="utf-8")
            git(repo, "commit", "-qam", "plan lint blocker")
            before_head = git(repo, "rev-parse", "HEAD")

            result = run_accept(repo, "~ab12")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("shadow lint", result.stderr)
            self.assertIn("MODE-ILLEGAL", result.stderr)
            self.assertEqual(plan.read_text(encoding="utf-8"), invalid)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), before_head)
            self.assertNotIn("~ab12 PROOF", invalid)
