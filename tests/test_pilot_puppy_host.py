"""Tests for the three native Pilot Puppy host adapters."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "pilot-puppy-host.py"
ROUTE_SCRIPT = SKILL_DIR / "scripts" / "pilot-puppy-route.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
from pilot_puppy_roster_lib import initialize_roster

SPEC = importlib.util.spec_from_file_location("pilot_puppy_host", SCRIPT)
assert SPEC and SPEC.loader
pilot_puppy_host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot_puppy_host)


FAKE_HOST = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

if "--version" in sys.argv:
    print("fake-native-host 1.0")
    raise SystemExit(0)

mode = pathlib.Path(__file__).with_suffix(".mode").read_text().strip() if pathlib.Path(__file__).with_suffix(".mode").exists() else "ok"
if mode == "ok":
    pathlib.Path.cwd().joinpath("result.txt").write_text("changed\n", encoding="utf-8")
    changed = ["result.txt"]
elif mode == "scope":
    pathlib.Path.cwd().joinpath("outside.txt").write_text("escape\n", encoding="utf-8")
    changed = ["outside.txt"]
elif mode == "ignored":
    pathlib.Path.cwd().joinpath(".env").write_text("ignored escape\n", encoding="utf-8")
    changed = []
else:
    changed = []

if mode != "missing":
    print("```json")
    print(json.dumps({
        "schema": "pilot-puppy.host-receipt.v1",
        "task_id": "add-proof",
        "status": "ok",
        "summary": "bounded fake host completed the task",
        "proof_ref": "tests-green",
        "changed_paths": changed,
        "tests": [{"name": "fake-test", "status": "pass"}],
    }))
    print("```")
'''


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)


def make_repo(root: Path, *, ignore_evidence: bool = True) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "pilot-puppy-test@example.invalid")
    git(repo, "config", "user.name", "Pilot Puppy Test")
    (repo / "result.txt").write_text("base\n", encoding="utf-8")
    ignored = ".env\n" + (".pilot-puppy/\n" if ignore_evidence else "")
    (repo / ".gitignore").write_text(ignored, encoding="utf-8")
    git(repo, "add", "result.txt", ".gitignore")
    git(repo, "commit", "-qm", "base")
    return repo


def make_host(root: Path, mode: str = "ok") -> Path:
    path = root / "fake-host"
    path.write_text(FAKE_HOST, encoding="utf-8")
    path.chmod(0o755)
    path.with_suffix(".mode").write_text(mode, encoding="utf-8")
    return path


def make_roster(root: Path) -> Path:
    path = root / "config" / "roster.json"
    initialize_roster(path)
    return path


def make_route(repo: Path, task: Path, roster_file: Path, *, task_kind: str = "dev") -> Path:
    output = ".pilot-puppy/evidence/route.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROUTE_SCRIPT),
            "--repo",
            str(repo),
            "--task-id",
            "add-proof",
            "--task-file",
            str(task),
            "--task-kind",
            task_kind,
            "--roster-file",
            str(roster_file),
            "--availability",
            "assume",
            "--out",
            output,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return repo / output


def run_host(
    repo: Path,
    binary: Path,
    task: Path,
    output: Path,
    *,
    host: str = "cursor",
    route_file: str | None = None,
    roster_file: Path | None = None,
    force: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "run",
        "--host",
        host,
        "--binary",
        str(binary),
        "--repo",
        str(repo),
        "--task-file",
        str(task),
        "--task-id",
        "add-proof",
        "--allowed-path",
        "result.txt",
        "--out",
        str(output),
        "--json",
    ]
    if route_file is not None:
        command.extend(["--route-file", route_file])
    if roster_file is not None:
        command.extend(["--roster-file", str(roster_file)])
    if force:
        command.append("--force")
    return subprocess.run(command, capture_output=True, text=True, check=False)


class PilotPuppyHostTests(unittest.TestCase):
    def test_cursor_json_envelope_parses_receipt_after_prose(self) -> None:
        envelope = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "result": (
                    "Creating the marker file, then verifying it exists."
                    "{\"schema\":\"pilot-puppy.host-receipt.v1\","
                    "\"task_id\":\"cursor-native-probe\","
                    "\"status\":\"ok\","
                    "\"summary\":\"marker created\","
                    "\"changed_paths\":[\"cursor-native-marker.txt\"],"
                    "\"tests\":[{\"name\":\"marker\",\"status\":\"pass\"}],"
                    "\"proof_ref\":\"cursor-native-probe\"}"
                ),
            }
        )
        receipts = pilot_puppy_host.json_objects(envelope)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["task_id"], "cursor-native-probe")

    def test_cursor_command_shape_uses_agent_stdin_without_receipt_leak(self) -> None:
        repo = Path("/workspace/repo")
        final_message = Path("/tmp/final-message.txt")
        command = pilot_puppy_host.command_shape("cursor", "cursor-agent", repo, final_message)
        self.assertEqual(command[-1], "agent")
        self.assertNotIn("frozen task", command)

    def test_host_prompt_supplies_the_receipt_contract(self) -> None:
        task = "Change the bounded file."
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
        prompt = pilot_puppy_host.host_prompt(task, "bounded-task", ["result.txt"], digest)
        self.assertIn(task, prompt)
        self.assertIn(digest, prompt)
        self.assertIn("result.txt", prompt)
        self.assertIn("pilot-puppy.host-receipt.v1", prompt)
        self.assertIn('"task_id":"bounded-task"', prompt)
        self.assertIn('"proof_ref":"bounded-proof"', prompt)
        self.assertIn("Do not use spaces or prose for proof_ref.", prompt)
        self.assertIn("with status `blocked`", prompt)
        self.assertIn("`proof_ref`: null", prompt)

    def test_probe_is_projection_only_and_reports_available_host(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = make_host(root)
            args = type("Args", (), {"host": "codex", "binary": str(binary)})()
            payload, code = pilot_puppy_host.probe(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["schema"], "pilot-puppy.host-probe.v1")
        self.assertEqual(payload["execution"], {"performed": False, "projection_only": True})

    def test_cursor_without_explicit_binary_resolves_cursor_agent(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "cursor-agent"
            binary.write_text(FAKE_HOST, encoding="utf-8")
            binary.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(root)}, clear=False):
                resolved = pilot_puppy_host.resolve_binary("cursor", None)
        self.assertEqual(Path(resolved), binary.resolve())

    def test_same_packet_contract_runs_through_all_three_hosts(self) -> None:
        for host in sorted(pilot_puppy_host.HOSTS):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = make_repo(root)
                binary = make_host(root)
                task = root / "task.txt"
                task.write_text("Add the proof marker and run the bounded test.\n", encoding="utf-8")
                output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
                result = subprocess.run(
                    [
                        "python3",
                        str(SCRIPT),
                        "run",
                        "--host",
                        host,
                        "--binary",
                        str(binary),
                        "--repo",
                        str(repo),
                        "--task-file",
                        str(task),
                        "--task-id",
                        "add-proof",
                        "--allowed-path",
                        "result.txt",
                        "--out",
                        str(output),
                        "--json",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(payload["schema"], "pilot-puppy.host-attempt.v1")
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["host"], host)
                self.assertEqual(
                    payload["task_sha256"],
                    hashlib.sha256(task.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
                )
                self.assertEqual(payload["changed_paths"], ["result.txt"])
                self.assertEqual(payload["proof_ref"], "tests-green")
                self.assertFalse(payload["accepted_by_lead"])
                self.assertTrue(payload["unreviewed_claim"])

    def test_ready_route_binds_one_host_run_without_leaking_private_roster_text(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root, ignore_evidence=False)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Add the proof marker and run the bounded test.\n", encoding="utf-8")
            roster_file = make_roster(root)
            route_file = make_route(repo, task, roster_file)
            output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
            result = run_host(
                repo,
                binary,
                task,
                output,
                route_file=".pilot-puppy/evidence/route.json",
                roster_file=roster_file,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["route"]["schema"], "pilot-puppy.route.v1")
        self.assertEqual(payload["route"]["role"], "bulk")
        self.assertEqual(payload["route"]["host"], "cursor")
        self.assertEqual(payload["route"]["priority"], 1)
        rendered = json.dumps(payload, sort_keys=True).lower()
        self.assertNotIn(str(root).lower(), rendered)
        self.assertNotIn("slot", rendered)
        self.assertNotIn("model", rendered)
        self.assertNotIn("credential", rendered)

    def test_forged_undeclared_route_selection_fails_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            roster_file = make_roster(root)
            route_file = make_route(repo, task, roster_file)
            packet = json.loads(route_file.read_text(encoding="utf-8"))
            packet["selection"]["host"] = "claude-code"
            route_file.write_text(json.dumps(packet), encoding="utf-8")
            output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
            result = run_host(
                repo,
                binary,
                task,
                output,
                host="claude-code",
                route_file=".pilot-puppy/evidence/route.json",
                roster_file=roster_file,
            )
            payload = json.loads(result.stdout)
            result_contents = (repo / "result.txt").read_text(encoding="utf-8")
            output_written = output.exists()

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(output_written)
        self.assertEqual(result_contents, "base\n")
        self.assertEqual(payload["blocked"]["kind"], "route_invalid")

    def test_force_cannot_replace_the_active_route_packet(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            roster_file = make_roster(root)
            route_file = make_route(repo, task, roster_file)
            original = route_file.read_bytes()
            result = run_host(
                repo,
                binary,
                task,
                route_file,
                route_file=".pilot-puppy/evidence/route.json",
                roster_file=roster_file,
                force=True,
            )
            payload = json.loads(result.stdout)
            preserved = route_file.read_bytes()

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(preserved, original)
        self.assertEqual(payload["blocked"]["kind"], "route_output_collision")

    def test_stale_or_mismatched_route_fails_before_launch(self) -> None:
        cases = ("task", "roster", "host", "manual")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname).resolve()
                repo = make_repo(root)
                binary = make_host(root)
                task = root / "task.txt"
                task.write_text("Do the bounded task.\n", encoding="utf-8")
                roster_file = make_roster(root)
                route_file = make_route(repo, task, roster_file, task_kind="plan" if case == "manual" else "dev")
                if case == "task":
                    task.write_text("A different frozen task.\n", encoding="utf-8")
                elif case == "roster":
                    roster_payload = json.loads(roster_file.read_text(encoding="utf-8"))
                    roster_payload["revision"] = 2
                    roster_file.write_text(json.dumps(roster_payload), encoding="utf-8")
                output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
                result = run_host(
                    repo,
                    binary,
                    task,
                    output,
                    host="codex" if case == "host" else "cursor",
                    route_file=".pilot-puppy/evidence/route.json",
                    roster_file=roster_file,
                )
                payload = json.loads(result.stdout)

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual((repo / "result.txt").read_text(encoding="utf-8"), "base\n")
                expected = {
                    "task": "route_task_mismatch",
                    "roster": "route_stale",
                    "host": "route_host_mismatch",
                    "manual": "route_manual",
                }[case]
                self.assertEqual(payload["blocked"]["kind"], expected)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes are unavailable on this platform")
    def test_named_pipe_route_fails_before_host_launch(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            evidence = repo / ".pilot-puppy" / "evidence"
            evidence.mkdir(parents=True)
            os.mkfifo(evidence / "route.json")
            output = evidence / "attempt.json"
            result = run_host(
                repo,
                binary,
                task,
                output,
                route_file=".pilot-puppy/evidence/route.json",
            )
            payload = json.loads(result.stdout)
            output_written = output.exists()

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(output_written)
        self.assertEqual(payload["blocked"]["kind"], "route_invalid")

    def test_missing_host_receipt_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root, mode="missing")
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "run",
                    "--host",
                    "codex",
                    "--binary",
                    str(binary),
                    "--repo",
                    str(repo),
                    "--task-file",
                    str(task),
                    "--task-id",
                    "add-proof",
                    "--allowed-path",
                    "result.txt",
                    "--out",
                    str(output),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["blocked"]["kind"], "host_receipt_missing")

    def test_scope_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root, mode="scope")
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "run",
                    "--host",
                    "cursor",
                    "--binary",
                    str(binary),
                    "--repo",
                    str(repo),
                    "--task-file",
                    str(task),
                    "--task-id",
                    "add-proof",
                    "--allowed-path",
                    "result.txt",
                    "--out",
                    str(output),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["blocked"]["kind"], "scope_violation")

    def test_output_must_stay_in_project_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = root / "outside.json"
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "run",
                    "--host",
                    "codex",
                    "--binary",
                    str(binary),
                    "--repo",
                    str(repo),
                    "--task-file",
                    str(task),
                    "--task-id",
                    "add-proof",
                    "--allowed-path",
                    "result.txt",
                    "--out",
                    str(output),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(result.stdout)["blocked"]["kind"], "output_unsafe")

    def test_ignored_scope_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root, mode="ignored")
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = repo / ".pilot-puppy" / "evidence" / "attempt.json"
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "run",
                    "--host",
                    "codex",
                    "--binary",
                    str(binary),
                    "--repo",
                    str(repo),
                    "--task-file",
                    str(task),
                    "--task-id",
                    "add-proof",
                    "--allowed-path",
                    "result.txt",
                    "--out",
                    str(output),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["blocked"]["kind"], "scope_violation")


if __name__ == "__main__":
    unittest.main()
