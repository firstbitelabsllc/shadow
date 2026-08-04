"""Integration tests for foreground, non-executing Drive preparation."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "pilot-puppy-drive.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_drive():
    spec = importlib.util.spec_from_file_location("pilot_puppy_drive_prepare", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drive = load_drive()


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def packet() -> dict:
    return {
        "schema": "pilot-puppy.drive.v1",
        "revision": 1,
        "lanes": [
            {
                "id": "improve-copy",
                "state": "ready",
                "task_kind": "dev",
                "summary": "Make the welcome message easier to understand.",
                "task": "Improve the welcome message and keep the focused test green.",
                "allowed_paths": ["src/welcome.ts", "tests/welcome.test.ts"],
                "proof": ["python3", "-m", "unittest", "tests.test_welcome"],
                "merge": "ordinary",
            },
            {
                "id": "repair-parser",
                "state": "ready",
                "task_kind": "debug",
                "summary": "Fix the reproducible parser failure.",
                "task": "Fix the parser failure and run the declared proof.",
                "allowed_paths": ["src/parser.py", "tests/test_parser.py"],
                "proof": ["python3", "-m", "unittest", "tests.test_parser"],
                "merge": "manual",
            },
        ],
    }


def make_repo(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "pilot-puppy-test@example.invalid")
    git(repo, "config", "user.name", "Pilot Puppy Test")
    plan = repo / "PLAN.md"
    plan.write_text(
        "# Example\n\n## Pilot Puppy Drive\n\n<!-- pilot-puppy-drive.v1\n"
        + json.dumps(packet(), indent=2)
        + "\n-->\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text(".pilot-puppy/\n", encoding="utf-8")
    git(repo, "add", "PLAN.md", ".gitignore")
    git(repo, "commit", "-qm", "base")
    roster = root / "config" / "roster.json"
    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "pilot-puppy-roster.py"), "init", "--file", str(roster)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return repo, roster


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False, env=env
    )


class DrivePrepareTests(unittest.TestCase):
    def test_prepare_writes_only_bounded_routes_and_a_frozen_session(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_repo(root)
            result = run(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
            )
            session = json.loads(result.stdout)
            evidence = repo / ".pilot-puppy" / "evidence"
            persisted = json.loads((evidence / f"drive-{session['session_id']}.json").read_text(encoding="utf-8"))
            routes = sorted(evidence.glob(f"drive-{session['session_id']}-*.route.json"))
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in routes)
            plan_contents = (repo / "PLAN.md").read_text(encoding="utf-8")
            source_status = git(repo, "status", "--porcelain=v1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(persisted, session)
        self.assertEqual(session["schema"], "pilot-puppy.drive-session.v1")
        self.assertEqual(session["state"], "prepared")
        self.assertEqual([lane["id"] for lane in session["lanes"]], ["improve-copy", "repair-parser"])
        self.assertEqual([lane["host"] for lane in session["lanes"]], ["cursor", "codex"])
        self.assertEqual(len(routes), 2)
        for forbidden in ("welcome message and keep", "src/welcome.ts", "tests.test_welcome", "/Users"):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("pilot-puppy-drive.v1", plan_contents)
        self.assertEqual(source_status, "")

    def test_prepare_refuses_a_dirty_project_before_creating_any_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_repo(root)
            (repo / "unrelated.txt").write_text("leave this alone\n", encoding="utf-8")
            result = run(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
            )
            evidence_exists = (repo / ".pilot-puppy" / "evidence").exists()

        self.assertEqual(result.returncode, 1)
        self.assertIn("save or commit", result.stderr)
        self.assertFalse(evidence_exists)

    def test_prepare_output_is_plain_language_and_does_not_start_a_host(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_repo(root)
            result = run(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ready work", result.stdout)
        self.assertIn("Make the welcome message easier to understand.", result.stdout)
        self.assertIn("Nothing has started.", result.stdout)
        self.assertNotIn("python3 -m", result.stdout)
        self.assertNotIn("/Users", result.stdout)

    def test_explicit_launch_rechecks_the_plan_then_runs_and_keeps_a_review_branch(self) -> None:
        fake_host = r'''#!/usr/bin/env python3
import json
import pathlib
import sys
if "--version" in sys.argv:
    print("fake-host 1.0")
    raise SystemExit(0)
pathlib.Path.cwd().joinpath("result.txt").write_text("changed\n", encoding="utf-8")
print("```json")
print(json.dumps({
  "schema": "pilot-puppy.host-receipt.v1",
  "task_id": "write-result",
  "status": "ok",
  "summary": "bounded change completed",
  "proof_ref": "result-proof",
  "changed_paths": ["result.txt"],
  "tests": [{"name": "host receipt", "status": "pass"}],
}))
print("```")
'''
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_repo(root)
            payload = packet()
            payload["lanes"] = [
                {
                    "id": "write-result",
                    "state": "ready",
                    "task_kind": "dev",
                    "summary": "Write the bounded result file.",
                    "task": "Write the requested result file and report the focused proof.",
                    "allowed_paths": ["result.txt"],
                    "proof": ["python3", "-c", "import pathlib; assert pathlib.Path('result.txt').read_text() == 'changed\\n'"],
                    "merge": "manual",
                }
            ]
            (repo / "PLAN.md").write_text(
                "# Example\n\n## Pilot Puppy Drive\n\n<!-- pilot-puppy-drive.v1\n"
                + json.dumps(payload, indent=2)
                + "\n-->\n",
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "-qm", "add drive packet")
            prepared = run(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
            )
            prepared_session = json.loads(prepared.stdout)
            binary = root / "fake-cursor"
            binary.write_text(fake_host, encoding="utf-8")
            binary.chmod(0o755)
            environment = {**os.environ, "PILOT_PUPPY_CURSOR_BIN": str(binary)}
            launched = run(
                "launch",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--session",
                prepared_session["session_id"],
                "--timeout-seconds",
                "20",
                "--json",
                env=environment,
            )
            finished = json.loads(launched.stdout)
            worktree = repo.parent / f"{repo.name}-pilot-puppy-drive" / prepared_session["session_id"] / "write-result"
            result_text = (worktree / "result.txt").read_text(encoding="utf-8")
            branch = git(worktree, "branch", "--show-current")
            commit = git(worktree, "log", "-1", "--pretty=%s")
            source_status = git(repo, "status", "--porcelain=v1")

        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(launched.returncode, 0, launched.stderr + launched.stdout)
        self.assertEqual(finished["state"], "finished")
        self.assertEqual(finished["lanes"][0]["status"], "passed")
        self.assertTrue(finished["lanes"][0]["scope_ok"])
        self.assertTrue(finished["lanes"][0]["proof_ok"])
        self.assertIsNone(finished["lanes"][0]["merge_ok"])
        self.assertEqual(result_text, "changed\n")
        self.assertTrue(branch.startswith("pilot-puppy/drive-"))
        self.assertEqual(commit, "pilot-puppy drive: write-result")
        self.assertEqual(source_status, "")

    def test_launch_refuses_a_changed_plan_or_malformed_session_before_creating_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_repo(root)
            prepared = run(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
            )
            session = json.loads(prepared.stdout)
            (repo / "PLAN.md").write_text((repo / "PLAN.md").read_text(encoding="utf-8") + "\nChanged after prepare.\n", encoding="utf-8")
            changed_plan = run(
                "launch",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--session",
                session["session_id"],
            )
            worktree_root = repo.parent / f"{repo.name}-pilot-puppy-drive"
            (repo / "PLAN.md").write_text((repo / "PLAN.md").read_text(encoding="utf-8").replace("\nChanged after prepare.\n", "\n"), encoding="utf-8")
            session_file = repo / ".pilot-puppy" / "evidence" / f"drive-{session['session_id']}.json"
            malformed = json.loads(session_file.read_text(encoding="utf-8"))
            malformed["lanes"][0]["role"] = []
            session_file.write_text(json.dumps(malformed), encoding="utf-8")
            malformed_session = run(
                "launch",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--session",
                session["session_id"],
            )
            worktree_exists = worktree_root.exists()

        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(changed_plan.returncode, 1)
        self.assertIn("plan changed after preparation", changed_plan.stderr)
        self.assertEqual(malformed_session.returncode, 1)
        self.assertIn("prepared Drive session is invalid", malformed_session.stderr)
        self.assertNotIn("Traceback", malformed_session.stderr)
        self.assertFalse(worktree_exists)

    def test_explicit_accept_reproduces_and_brings_checked_work_into_the_source_project(self) -> None:
        fake_host = r'''#!/usr/bin/env python3
import json
import pathlib
import sys
if "--version" in sys.argv:
    print("fake-host 1.0")
    raise SystemExit(0)
pathlib.Path.cwd().joinpath("result.txt").write_text("changed\n", encoding="utf-8")
print("```json")
print(json.dumps({
  "schema": "pilot-puppy.host-receipt.v1",
  "task_id": "write-result",
  "status": "ok",
  "summary": "bounded change completed",
  "proof_ref": "result-proof",
  "changed_paths": ["result.txt"],
  "tests": [{"name": "host receipt", "status": "pass"}],
}))
print("```")
'''
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_repo(root)
            payload = packet()
            payload["lanes"] = [
                {
                    "id": "write-result",
                    "state": "ready",
                    "task_kind": "dev",
                    "summary": "Write the bounded result file.",
                    "task": "Write the requested result file and report the focused proof.",
                    "allowed_paths": ["result.txt"],
                    "proof": ["python3", "-c", "import pathlib; assert pathlib.Path('result.txt').read_text() == 'changed\\n'"],
                    "merge": "manual",
                }
            ]
            (repo / "PLAN.md").write_text(
                "# Example\n\n## Pilot Puppy Drive\n\n<!-- pilot-puppy-drive.v1\n"
                + json.dumps(payload, indent=2)
                + "\n-->\n",
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "-qm", "add drive packet")
            prepared = run(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
            )
            session = json.loads(prepared.stdout)
            binary = root / "fake-cursor"
            binary.write_text(fake_host, encoding="utf-8")
            binary.chmod(0o755)
            environment = {**os.environ, "PILOT_PUPPY_CURSOR_BIN": str(binary)}
            launched = run(
                "launch",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--session",
                session["session_id"],
                "--timeout-seconds",
                "20",
                "--json",
                env=environment,
            )
            (repo / "unrelated.txt").write_text("leave this alone\n", encoding="utf-8")
            blocked = run(
                "accept",
                "--repo",
                str(repo),
                "--session",
                session["session_id"],
                "--timeout-seconds",
                "20",
                "--json",
            )
            review_root = repo.parent / f"{repo.name}-pilot-puppy-lead-review"
            review_exists_before_accept = review_root.exists()
            (repo / "unrelated.txt").unlink()
            accepted = run(
                "accept",
                "--repo",
                str(repo),
                "--session",
                session["session_id"],
                "--timeout-seconds",
                "20",
                "--json",
            )
            result = json.loads(accepted.stdout)
            review = repo.parent / f"{repo.name}-pilot-puppy-lead-review" / session["session_id"] / "attempt-01" / "write-result"
            review_exists = review.is_dir()
            source_text = (repo / "result.txt").read_text(encoding="utf-8")
            source_status = git(repo, "status", "--porcelain=v1")
            accepted_commit = git(repo, "log", "-1", "--pretty=%s")
            changed = git(repo, "diff", "--name-only", session["base_sha256"], "HEAD")

        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(launched.returncode, 0, launched.stderr + launched.stdout)
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("save or commit project changes", blocked.stderr)
        self.assertFalse(review_exists_before_accept)
        self.assertEqual(accepted.returncode, 0, accepted.stderr + accepted.stdout)
        self.assertEqual(result["state"], "accepted")
        self.assertTrue(result["lanes"][0]["scope_ok"])
        self.assertTrue(result["lanes"][0]["proof_ok"])
        self.assertTrue(result["lanes"][0]["merge_ok"])
        self.assertTrue(review_exists)
        self.assertEqual(source_text, "changed\n")
        self.assertEqual(source_status, "")
        self.assertEqual(accepted_commit, f"pilot-puppy accept: {session['session_id']}")
        self.assertEqual(changed, "result.txt")


if __name__ == "__main__":
    unittest.main()
