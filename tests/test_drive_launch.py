"""End-to-end Drive launch/accept behavior with a bounded fake native host."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-drive.py"


FAKE_CURSOR = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

if "--version" in sys.argv:
    print("fake-cursor 1.0")
    raise SystemExit(0)

cwd = pathlib.Path.cwd()
source = cwd / "src" / "greeting.py"
source.write_text(
    '"""Greeting module."""\n\n\ndef greeting() -> str:\n'
    '    """Return the user-facing greeting."""\n    return "hello world"\n',
    encoding="utf-8",
)
cache = cwd / "src" / "__pycache__"
cache.mkdir(exist_ok=True)
(cache / "greeting.cpython-000.pyc").write_bytes(b"\x00fake interpreter cache")
print("```json")
print(
    json.dumps(
        {
            "schema": "shadow.host-receipt.v1",
            "task_id": "fix-greeting",
            "status": "ok",
            "summary": "fixed the greeting spelling",
            "proof_ref": "bounded-proof",
            "changed_paths": ["src/greeting.py"],
            "tests": [{"name": "tests.test_greeting", "status": "pass"}],
        }
    )
)
print("```")
'''


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_project(
    root: Path, *, ignore: str = ".shadow/\n__pycache__/\n"
) -> tuple[Path, Path]:
    repo = root / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "shadow-test@example.invalid")
    git(repo, "config", "user.name", "Shadow Test")
    (repo / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "greeting.py").write_text(
        '"""Greeting module."""\n\n\ndef greeting() -> str:\n'
        '    """Return the user-facing greeting."""\n    return "helo wrld"\n',
        encoding="utf-8",
    )
    (repo / "tests" / "test_greeting.py").write_text(
        "import unittest\n\nfrom src.greeting import greeting\n\n\n"
        "class GreetingTests(unittest.TestCase):\n"
        "    def test_greeting_is_a_short_nonempty_string(self) -> None:\n"
        "        value = greeting()\n"
        "        self.assertIsInstance(value, str)\n"
        "        self.assertTrue(0 < len(value) < 80)\n",
        encoding="utf-8",
    )
    packet = {
        "schema": "shadow.drive.v1",
        "revision": 1,
        "lanes": [
            {
                "id": "fix-greeting",
                "state": "ready",
                "task_kind": "dev",
                "summary": "Fix the greeting spelling.",
                "task": "Fix the misspelled greeting string. Keep the focused test green.",
                "allowed_paths": ["src/greeting.py"],
                "proof": ["python3", "-m", "unittest", "tests.test_greeting"],
                "merge": "ordinary",
            }
        ],
    }
    (repo / "PLAN.md").write_text(
        "# Example\n\n## Shadow Drive\n\n<!-- shadow-drive.v1\n"
        + json.dumps(packet, indent=2)
        + "\n-->\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text(ignore, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    roster = root / "config" / "roster.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "shadow-roster.py"),
            "init",
            "--file",
            str(roster),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    binary = root / "fake-cursor"
    binary.write_text(FAKE_CURSOR, encoding="utf-8")
    binary.chmod(0o755)
    return repo, roster


def run_drive(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class DriveLaunchTests(unittest.TestCase):
    def test_lane_passes_and_accepts_when_the_proof_creates_ignored_caches(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_project(root)
            env = dict(os.environ)
            env["SHADOW_CURSOR_BIN"] = str(root / "fake-cursor")
            prepared = run_drive(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
                env=env,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            session_id = json.loads(prepared.stdout)["session_id"]
            launched = run_drive(
                "launch",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--roster-file",
                str(roster),
                "--json",
                env=env,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            session = json.loads(launched.stdout)
            lane = session["lanes"][0]
            self.assertEqual(lane["status"], "passed", session)
            self.assertTrue(lane["scope_ok"], session)
            self.assertTrue(lane["proof_ok"], session)
            accepted = run_drive(
                "accept",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--json",
                env=env,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            merged = git(repo, "show", "HEAD", "--stat", "--format=%s")
            self.assertIn("src/greeting.py", merged)
            content = (repo / "src" / "greeting.py").read_text(encoding="utf-8")
            self.assertIn("hello world", content)
            status = git(repo, "status", "--porcelain")
            self.assertEqual(status, "")

    def test_accept_and_reprepare_work_without_a_shadow_gitignore_entry(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_project(root, ignore="__pycache__/\n")
            env = dict(os.environ)
            env["SHADOW_CURSOR_BIN"] = str(root / "fake-cursor")
            prepared = run_drive(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
                env=env,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            session_id = json.loads(prepared.stdout)["session_id"]
            launched = run_drive(
                "launch",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--roster-file",
                str(roster),
                "--json",
                env=env,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            accepted = run_drive(
                "accept",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--json",
                env=env,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            content = (repo / "src" / "greeting.py").read_text(encoding="utf-8")
            self.assertIn("hello world", content)
            status = git(repo, "status", "--porcelain")
            outside_state = [
                line
                for line in status.splitlines()
                if not line[3:].startswith(".shadow/")
            ]
            self.assertEqual(outside_state, [], status)
            again = run_drive(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
                env=env,
            )
            self.assertEqual(again.returncode, 0, again.stderr)

    def test_interrupted_running_session_relaunches_and_completes(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_project(root)
            env = dict(os.environ)
            env["SHADOW_CURSOR_BIN"] = str(root / "fake-cursor")
            prepared = run_drive(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
                env=env,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            session_id = json.loads(prepared.stdout)["session_id"]
            session_path = repo / ".shadow" / "evidence" / f"drive-{session_id}.json"
            record = json.loads(session_path.read_text(encoding="utf-8"))
            record["state"] = "running"
            session_path.write_text(json.dumps(record), encoding="utf-8")
            relaunched = run_drive(
                "launch",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--roster-file",
                str(roster),
                "--json",
                env=env,
            )
            self.assertEqual(relaunched.returncode, 0, relaunched.stderr)
            lane = json.loads(relaunched.stdout)["lanes"][0]
            self.assertEqual(lane["status"], "passed")
            accepted = run_drive(
                "accept",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--json",
                env=env,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_a_live_lock_refuses_a_second_launch_and_a_dead_lock_is_replaced(self) -> None:
        import os
        import subprocess as sp

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_project(root)
            env = dict(os.environ)
            env["SHADOW_CURSOR_BIN"] = str(root / "fake-cursor")
            prepared = run_drive(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
                env=env,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            session_id = json.loads(prepared.stdout)["session_id"]
            lock = repo / ".shadow" / "evidence" / f"drive-{session_id}.lock"
            lock.write_text(str(os.getpid()), encoding="utf-8")
            refused = run_drive(
                "launch",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--roster-file",
                str(roster),
                env=env,
            )
            self.assertEqual(refused.returncode, 1)
            self.assertIn("already being worked on", refused.stderr)
            reaped = sp.Popen(["true"])
            reaped.wait()
            lock.write_text(str(reaped.pid), encoding="utf-8")
            launched = run_drive(
                "launch",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--roster-file",
                str(roster),
                "--json",
                env=env,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            self.assertFalse(lock.exists())

    def test_manual_merge_lane_is_checked_but_left_on_its_kept_branch(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo, roster = make_project(root)
            plan_text = (repo / "PLAN.md").read_text(encoding="utf-8")
            (repo / "PLAN.md").write_text(
                plan_text.replace('"merge": "ordinary"', '"merge": "manual"'), encoding="utf-8"
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "-qm", "declare manual merge")
            base = git(repo, "rev-parse", "HEAD")
            env = dict(os.environ)
            env["SHADOW_CURSOR_BIN"] = str(root / "fake-cursor")
            prepared = run_drive(
                "prepare",
                "--repo",
                str(repo),
                "--roster-file",
                str(roster),
                "--availability",
                "assume",
                "--json",
                env=env,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            session_id = json.loads(prepared.stdout)["session_id"]
            launched = run_drive(
                "launch",
                "--repo",
                str(repo),
                "--session",
                session_id,
                "--roster-file",
                str(roster),
                "--json",
                env=env,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            accepted = run_drive(
                "accept",
                "--repo",
                str(repo),
                "--session",
                session_id,
                env=env,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertIn("for your own merge", accepted.stdout)
            head = git(repo, "rev-parse", "HEAD")
            self.assertEqual(head, base)
            content = (repo / "src" / "greeting.py").read_text(encoding="utf-8")
            self.assertIn("helo wrld", content)
            branch = f"shadow/drive-{session_id[:12]}-fix-greeting"
            kept = git(repo, "rev-parse", "--verify", f"{branch}^{{commit}}")
            self.assertTrue(kept)


if __name__ == "__main__":
    unittest.main()
