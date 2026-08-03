"""Tests for the three native Pilot Puppy host adapters."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "pilot-puppy-host.py"
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


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "pilot-puppy-test@example.invalid")
    git(repo, "config", "user.name", "Pilot Puppy Test")
    (repo / "result.txt").write_text("base\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".env\n.pilot-puppy/\n", encoding="utf-8")
    git(repo, "add", "result.txt", ".gitignore")
    git(repo, "commit", "-qm", "base")
    return repo


def make_host(root: Path, mode: str = "ok") -> Path:
    path = root / "fake-host"
    path.write_text(FAKE_HOST, encoding="utf-8")
    path.chmod(0o755)
    path.with_suffix(".mode").write_text(mode, encoding="utf-8")
    return path


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
