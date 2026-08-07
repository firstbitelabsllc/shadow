"""Tests for the three native Shadow host adapters."""

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
SCRIPT = SKILL_DIR / "scripts" / "shadow-host.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

SPEC = importlib.util.spec_from_file_location("shadow_host", SCRIPT)
assert SPEC and SPEC.loader
shadow_host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow_host)


FAKE_HOST = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

if "--version" in sys.argv:
    print("fake-native-host 1.0")
    raise SystemExit(0)

mode = pathlib.Path(__file__).with_suffix(".mode").read_text().strip() if pathlib.Path(__file__).with_suffix(".mode").exists() else "ok"
capture = pathlib.Path(__file__).with_suffix(".argv.json")
capture.write_text(json.dumps(sys.argv), encoding="utf-8")
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
    receipt = {
        "schema": "shadow.host-receipt.v1",
        "task_id": "add-proof",
        "status": "ok",
        "summary": "bounded fake host completed the task",
        "proof_ref": "tests-green",
        "changed_paths": changed,
        "tests": [{"name": "fake-test", "status": "pass"}],
    }
    if mode == "private-summary":
        receipt["summary"] = "private-model-marker was used"
    elif mode == "private-test":
        receipt["tests"] = [{"name": "private-model-marker", "status": "pass"}]
    elif mode == "unsafe-test":
        receipt["tests"] = [{"name": "fake-test", "status": "pass", "extra": "private-model-marker"}]
    print(json.dumps(receipt))
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
    git(repo, "config", "user.email", "shadow-test@example.invalid")
    git(repo, "config", "user.name", "Shadow Test")
    (repo / "result.txt").write_text("base\n", encoding="utf-8")
    ignored = ".env\n" + (".shadow/\n" if ignore_evidence else "")
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





def run_host(
    repo: Path,
    binary: Path,
    task: Path,
    output: Path,
    *,
    host: str = "cursor",
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
    if force:
        command.append("--force")
    return subprocess.run(command, capture_output=True, text=True, check=False)


class ShadowHostTests(unittest.TestCase):
    def test_cursor_json_envelope_parses_receipt_after_prose(self) -> None:
        envelope = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "result": (
                    "Creating the marker file, then verifying it exists."
                    "{\"schema\":\"shadow.host-receipt.v1\","
                    "\"task_id\":\"cursor-native-probe\","
                    "\"status\":\"ok\","
                    "\"summary\":\"marker created\","
                    "\"changed_paths\":[\"cursor-native-marker.txt\"],"
                    "\"tests\":[{\"name\":\"marker\",\"status\":\"pass\"}],"
                    "\"proof_ref\":\"cursor-native-probe\"}"
                ),
            }
        )
        receipts = shadow_host.json_objects(envelope)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["task_id"], "cursor-native-probe")

    def test_cursor_command_shape_uses_agent_stdin_without_receipt_leak(self) -> None:
        repo = Path("/workspace/repo")
        final_message = Path("/tmp/final-message.txt")
        command = shadow_host.command_shape("cursor", "cursor-agent", repo, final_message)
        self.assertEqual(command[-1], "agent")
        self.assertNotIn("frozen task", command)

    def test_host_prompt_supplies_the_receipt_contract(self) -> None:
        task = "Change the bounded file."
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
        prompt = shadow_host.host_prompt(task, "bounded-task", ["result.txt"], digest)
        self.assertIn(task, prompt)
        self.assertIn(digest, prompt)
        self.assertIn("result.txt", prompt)
        self.assertIn("shadow.host-receipt.v1", prompt)
        self.assertIn('"task_id":"bounded-task"', prompt)
        self.assertIn('"proof_ref":"bounded-proof"', prompt)
        self.assertIn("Do not use spaces or prose for proof_ref.", prompt)
        self.assertIn("with status `blocked`", prompt)
        self.assertIn("`proof_ref`: null", prompt)

    def test_receipt_rejects_private_paths_and_secret_shaped_text(self) -> None:
        for field, value in (
            ("summary", "completed " + chr(47) + "Users" + chr(47) + "exampleuser" + chr(47) + "private" + chr(47) + "project"),
            ("test", "token=" + "gh" + "p_12345678901234567890"),
        ):
            with self.subTest(field=field):
                raw = {
                    "schema": shadow_host.HOST_RECEIPT_SCHEMA,
                    "task_id": "audit-task",
                    "status": "ok",
                    "summary": "bounded task completed",
                    "proof_ref": "audit-proof",
                    "changed_paths": ["result.txt"],
                    "tests": [{"name": "bounded test", "status": "pass"}],
                }
                if field == "summary":
                    raw["summary"] = value
                else:
                    raw["tests"][0]["name"] = value
                with self.assertRaises(shadow_host.HostError) as raised:
                    shadow_host.validate_host_receipt(raw, "audit-task", ["result.txt"])
                self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_receipt_rejects_unknown_test_fields_and_status(self) -> None:
        base = {
            "schema": shadow_host.HOST_RECEIPT_SCHEMA,
            "task_id": "audit-task",
            "status": "ok",
            "summary": "bounded task completed",
            "proof_ref": "audit-proof",
            "changed_paths": ["result.txt"],
            "tests": [{"name": "bounded test", "status": "pass"}],
        }
        for test in (
            {"name": "bounded test", "status": "pass", "raw_output": "secret"},
            {"name": "bounded test", "status": "unknown"},
        ):
            with self.subTest(test=test):
                raw = {**base, "tests": [test]}
                with self.assertRaises(shadow_host.HostError) as raised:
                    shadow_host.validate_host_receipt(raw, "audit-task", ["result.txt"])
                self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_probe_is_projection_only_and_reports_available_host(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = make_host(root)
            args = type("Args", (), {"host": "codex", "binary": str(binary)})()
            payload, code = shadow_host.probe(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["schema"], "shadow.host-probe.v1")
        self.assertEqual(payload["execution"], {"performed": False, "projection_only": True})

    def test_cursor_without_explicit_binary_resolves_cursor_agent(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "cursor-agent"
            binary.write_text(FAKE_HOST, encoding="utf-8")
            binary.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(root)}, clear=False):
                resolved = shadow_host.resolve_binary("cursor", None)
        self.assertEqual(Path(resolved), binary.resolve())

    def test_same_packet_contract_runs_through_all_three_hosts(self) -> None:
        for host in sorted(shadow_host.HOSTS):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = make_repo(root)
                binary = make_host(root)
                task = root / "task.txt"
                task.write_text("Add the proof marker and run the bounded test.\n", encoding="utf-8")
                output = repo / ".shadow" / "evidence" / "attempt.json"
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
                self.assertEqual(payload["schema"], "shadow.host-attempt.v1")
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["host"], host)
                self.assertEqual(
                    payload["task_sha256"],
                    hashlib.sha256(task.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
                )
                self.assertEqual(payload["changed_paths"], ["result.txt"])
                self.assertEqual(payload["proof_ref"], "tests-green")
                # Pin the exact per-host argv: a silently dropped sandbox or
                # output flag would still pass every other assertion here.
                argv = json.loads(binary.with_suffix(".argv.json").read_text(encoding="utf-8"))
                resolved = str(repo.resolve())
                if host == "codex":
                    self.assertEqual(argv[1:8], [
                        "exec", "--json", "--ephemeral", "--sandbox", "workspace-write", "-C", resolved,
                    ])
                    self.assertEqual(argv[8], "--output-last-message")
                elif host == "claude-code":
                    self.assertEqual(argv[1:], [
                        "--print", "--output-format", "json", "--no-session-persistence",
                        "--permission-mode", "acceptEdits", "--add-dir", resolved,
                    ])
                else:
                    self.assertEqual(argv[1:], [
                        "--print", "--output-format", "json", "--workspace", resolved,
                        "--trust", "--force", "agent",
                    ])
                self.assertFalse(payload["accepted_by_lead"])
                self.assertTrue(payload["unreviewed_claim"])






    def test_missing_host_receipt_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root, mode="missing")
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "attempt.json"
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
            output = repo / ".shadow" / "evidence" / "attempt.json"
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

    def test_new_ignored_files_are_recorded_but_never_block_scope(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root, mode="ignored")
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "attempt.json"
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
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertIn(".env", payload["ignored_artifact_paths"])
            self.assertNotIn(".env", payload["changed_paths"])

    def test_pre_rename_evidence_directory_never_blocks_a_packet(self) -> None:
        for ignore_legacy in (False, True):
            with self.subTest(ignore_legacy=ignore_legacy), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = make_repo(root)
                if ignore_legacy:
                    ignore_file = repo / ".gitignore"
                    ignore_file.write_text(
                        ignore_file.read_text(encoding="utf-8") + ".pilot-puppy/\n", encoding="utf-8"
                    )
                    git(repo, "add", ".gitignore")
                    git(repo, "commit", "-qm", "ignore pre-rename evidence")
                legacy = repo / ".pilot-puppy" / "evidence"
                legacy.mkdir(parents=True)
                (legacy / "old-attempt.json").write_text("{}\n", encoding="utf-8")
                binary = make_host(root)
                task = root / "task.txt"
                task.write_text("Add the proof marker and run the bounded test.\n", encoding="utf-8")
                output = repo / ".shadow" / "evidence" / "attempt.json"
                result = run_host(repo, binary, task, output, host="codex")
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["changed_paths"], ["result.txt"])

    def test_symlinked_pre_rename_evidence_is_never_exempt_from_sealing(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            outside = root / "outside"
            outside.mkdir()
            (repo / ".pilot-puppy").symlink_to(outside, target_is_directory=True)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "attempt.json"
            result = run_host(repo, binary, task, output, host="codex")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(result.stdout)["blocked"]["kind"], "worktree_unsealed")



    def test_private_or_unbounded_host_receipt_data_blocks_without_persisting_it(self) -> None:
        cases = (
            ("unsafe-test", "host_receipt_invalid"),
        )
        for mode, expected in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname).resolve()
                repo = make_repo(root, ignore_evidence=False)
                binary = make_host(root, mode=mode)
                task = root / "task.txt"
                task.write_text("Do the bounded task.\n", encoding="utf-8")
                output = repo / ".shadow" / "evidence" / "attempt.json"
                result = run_host(repo, binary, task, output, host="cursor")
                payload = json.loads(output.read_text(encoding="utf-8"))

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(payload["status"], "blocked")
                self.assertEqual(payload["blocked"]["kind"], expected)
                self.assertEqual(payload["tests"], [])


class AuditBlockRegressionTests(unittest.TestCase):
    def test_existing_out_refuses_before_the_host_ever_runs(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root)
            binary = make_host(root)
            task = root / "task.txt"
            task.write_text("Do the bounded thing.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "attempt.json"
            output.parent.mkdir(parents=True)
            output.write_text("{}", encoding="utf-8")
            result = run_host(repo, binary, task, output)
            captured = binary.with_suffix(".argv.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("output_exists", result.stdout + result.stderr)
        self.assertFalse(captured.exists(), "the host must not run when the receipt would be clobbered")

    def test_nested_evidence_directories_do_not_unseal_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            nested = repo / ".shadow" / "evidence" / "archive"
            nested.mkdir(parents=True)
            (nested / "old.json").write_text("{}", encoding="utf-8")
            snapshot = shadow_host.local_state_snapshot(repo)
        self.assertIn(".shadow/evidence/archive/old.json", snapshot)


if __name__ == "__main__":
    unittest.main()
