"""Tests for the native Shadow host adapters."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
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
import subprocess
import sys

if "--version" in sys.argv:
    print("fake-native-host 1.0")
    raise SystemExit(0)

mode = pathlib.Path(__file__).with_suffix(".mode").read_text().strip() if pathlib.Path(__file__).with_suffix(".mode").exists() else "ok"
proposal_path = pathlib.Path(__file__).with_suffix(".proposal.json")
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
    elif mode in {"proposal", "oversized-proposal"}:
        receipt["changed_paths"] = []
        receipt["authority_proposal"] = json.loads(proposal_path.read_text()) if proposal_path.exists() else {
            "schema": "shadow.authority-proposal.v1",
            "entity_id": "a" * 64,
            "row_id": "~a502",
            "owner": "codexdk",
            "base": {
                "plan_root_sha256": "b" * 64,
                "source_head": "c" * 40,
            },
            "request": {"transition": "complete"},
        }
        if mode == "oversized-proposal":
            receipt["tests"] = [
                {"name": f"bounded-test-{index:04d}", "status": "pass"}
                for index in range(1100)
            ]
    elif mode == "proposal-commit":
        repo = pathlib.Path(sys.argv[sys.argv.index("-C") + 1])
        (repo / "proof.py").write_text("print('compromised')\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "proof.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-qm", "rewrite proof"],
            check=True,
            capture_output=True,
        )
        receipt["changed_paths"] = []
        receipt["authority_proposal"] = json.loads(proposal_path.read_text())
    elif mode == "proposal-config":
        repo = pathlib.Path(sys.argv[sys.argv.index("-C") + 1])
        subprocess.run(
            ["git", "-C", str(repo), "config", "shadow.proposal-mutant", "true"],
            check=True,
            capture_output=True,
        )
        receipt["changed_paths"] = []
        receipt["authority_proposal"] = json.loads(proposal_path.read_text())
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


def make_host(
    root: Path,
    mode: str = "ok",
    *,
    proposal: dict[str, object] | None = None,
) -> Path:
    path = root / "fake-host"
    path.write_text(FAKE_HOST, encoding="utf-8")
    path.chmod(0o755)
    path.with_suffix(".mode").write_text(mode, encoding="utf-8")
    if proposal is not None:
        path.with_suffix(".proposal.json").write_text(
            json.dumps(proposal, sort_keys=True),
            encoding="utf-8",
        )
    return path





def run_host(
    repo: Path,
    binary: Path,
    task: Path,
    output: Path,
    *,
    host: str = "cursor",
    force: bool = False,
    authority_proposal: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "run",
        "--host",
        host,
        "--work-class",
        "coding",
        "--delegation",
        "direct",
        "--repo",
        str(repo),
        "--task-file",
        str(task),
        "--task-id",
        "add-proof",
        "--out",
        str(output),
        "--json",
    ]
    environment = os.environ.copy()
    if authority_proposal:
        bin_dir = binary.parent / ".proposal-bin"
        bin_dir.mkdir(exist_ok=True)
        codex = bin_dir / "codex"
        codex.unlink(missing_ok=True)
        codex.symlink_to(binary)
        for suffix in (".mode", ".proposal.json"):
            source = binary.with_suffix(suffix)
            destination = codex.with_suffix(suffix)
            destination.unlink(missing_ok=True)
            if source.exists():
                destination.symlink_to(source)
        environment["PATH"] = f"{bin_dir}{os.pathsep}{environment.get('PATH', '')}"
        command.append("--authority-proposal")
    else:
        command.extend(
            [
                "--binary",
                str(binary),
                "--allowed-path",
                "result.txt",
            ]
        )
    if force:
        command.append("--force")
    return subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


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

    def test_cursor_command_shape_uses_agent_stdin_and_coding_selector(self) -> None:
        repo = Path("/workspace/repo")
        final_message = Path("/tmp/final-message.txt")
        command = shadow_host.command_shape(
            "cursor",
            "cursor-agent",
            repo,
            final_message,
            work_class="coding",
            delegation="direct",
        )
        self.assertEqual(command[-1], "agent")
        self.assertEqual(
            command[command.index("--model") + 1],
            "claude-opus-5-thinking-high",
        )
        self.assertNotIn("frozen task", command)

    def test_sealed_host_set_includes_grok_and_refuses_unknown(self) -> None:
        # Regression: the old three-host-only set silently dropped grok from
        # probe/run argparse and launch. A host set without grok must fail here.
        self.assertGreaterEqual(
            set(shadow_host.HOSTS),
            {"codex", "claude-code", "cursor", "grok"},
        )
        with self.assertRaises(SystemExit):
            shadow_host.parser().parse_args(["probe", "--host", "not-a-host"])

    def test_documented_delegation_door_requires_class_and_execution_shape(self) -> None:
        # Shadow's entire delegation surface is `shadow host run --host X`.
        # The SKILL handoff and the CLI help are the caller contract. If either
        # omits a cheaper/alternate host, a seat cannot dispatch there.
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        help_text = subprocess.run(
            [str(SKILL_DIR / "bin" / "shadow"), "help", "host"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for host in ("codex", "claude-code", "cursor", "grok"):
            self.assertIn(host, skill, f"SKILL.md handoff lost {host}")
            self.assertIn(host, help_text, f"shadow help host lost {host}")
            with self.assertRaises(SystemExit):
                shadow_host.parser().parse_args(
                    ["run", "--host", host, "--task-file", "t", "--task-id", "add-proof"]
                )
            args = shadow_host.parser().parse_args(
                [
                    "run",
                    "--host",
                    host,
                    "--work-class",
                    "coding",
                    "--delegation",
                    "direct",
                    "--task-file",
                    "t",
                    "--task-id",
                    "add-proof",
                ]
            )
            self.assertEqual(args.host, host)
            self.assertEqual(args.work_class, "coding")
            self.assertEqual(args.delegation, "direct")
            shape = shadow_host.public_command_shape(host, delegation="direct")
            self.assertIn("--model", shape)
        self.assertIn("shadow host run --host", skill)
        self.assertIn("--delegation direct|required", skill)
        self.assertIn("--delegation MODE", help_text)
        self.assertIn("--authority-proposal", help_text)
        self.assertNotIn("shadow route", skill)

    def test_grok_command_shape_uses_prompt_file_and_coding_selector(self) -> None:
        repo = Path("/workspace/repo")
        final_message = Path("/tmp/final-message.txt")
        prompt_file = Path("/tmp/prompt.txt")
        command = shadow_host.command_shape(
            "grok",
            "grok",
            repo,
            final_message,
            prompt_file,
            work_class="coding",
            delegation="direct",
        )
        self.assertEqual(
            command,
            [
                "grok",
                "--no-subagents",
                "--model",
                "grok-4.6",
                "--cwd",
                str(repo),
                "--output-format",
                "json",
                "--permission-mode",
                "acceptEdits",
                "--prompt-file",
                str(prompt_file),
            ],
        )
        self.assertEqual(
            shadow_host.public_command_shape("grok", delegation="direct"),
            [
                "--no-subagents",
                "--model",
                "--cwd",
                "--output-format",
                "json",
                "--permission-mode",
                "acceptEdits",
                "--prompt-file",
            ],
        )
        self.assertIn(
            "--model",
            shadow_host.public_command_shape("grok", delegation="direct"),
        )

    def test_required_delegation_enables_only_verified_native_capabilities(self) -> None:
        repo = Path("/workspace/repo")
        final_message = Path("/tmp/final-message.txt")
        prompt_file = Path("/tmp/prompt.txt")
        commands = {
            host: shadow_host.command_shape(
                host,
                {"claude-code": "claude", "codex": "codex", "grok": "grok"}[host],
                repo,
                final_message,
                prompt_file,
                work_class="planning",
                delegation="required",
            )
            for host in ("claude-code", "codex", "grok")
        }
        self.assertIn("--agents", commands["claude-code"])
        self.assertEqual(
            commands["codex"][1:4],
            ["exec", "--enable", "multi_agent"],
        )
        self.assertEqual(commands["grok"][1:3], ["--max-turns", "20"])
        with self.assertRaises(shadow_host.HostError) as raised:
            shadow_host.command_shape(
                "cursor",
                "cursor-agent",
                repo,
                final_message,
                work_class="planning",
                delegation="required",
            )
        self.assertEqual(raised.exception.kind, "execution_policy_invalid")
        self.assertIn("observable child lineage", raised.exception.detail)

    def test_missing_grok_binary_fail_closes_without_launching_another_host(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            empty = Path(dirname)
            with mock.patch.dict(os.environ, {"PATH": str(empty)}, clear=False):
                with self.assertRaises(shadow_host.HostError) as raised:
                    shadow_host.resolve_binary("grok", None)
        self.assertEqual(raised.exception.kind, "host_unavailable")
        self.assertIn("grok", raised.exception.detail)

    def test_grok_json_envelope_parses_receipt_from_text_field(self) -> None:
        receipt = {
            "schema": "shadow.host-receipt.v1",
            "task_id": "grok-native-probe",
            "status": "ok",
            "summary": "marker created",
            "changed_paths": ["result.txt"],
            "tests": [{"name": "marker", "status": "pass"}],
            "proof_ref": "grok-native-probe",
        }
        envelope = json.dumps(
            {
                "text": "Working on the bounded file.\n```json\n"
                + json.dumps(receipt)
                + "\n```\n",
                "stopReason": "end_turn",
                "sessionId": "abc",
            }
        )
        receipts = shadow_host.json_objects(envelope)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["task_id"], "grok-native-probe")

    def test_host_prompt_supplies_the_receipt_contract(self) -> None:
        task = "Change the bounded file."
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
        prompt = shadow_host.host_prompt(
            task, "bounded-task", ["result.txt"], digest, "direct"
        )
        self.assertIn(task, prompt)
        self.assertIn(digest, prompt)
        self.assertIn("result.txt", prompt)
        self.assertIn("shadow.host-receipt.v1", prompt)
        self.assertIn('"task_id":"example-task-id"', prompt)
        self.assertIn('"proof_ref":"bounded-proof"', prompt)
        self.assertIn("Do not use spaces or prose for proof_ref.", prompt)
        self.assertIn("with status `blocked`", prompt)
        self.assertIn("`proof_ref`: null", prompt)
        self.assertIn("Do not invoke a child agent", prompt)
        self.assertNotIn("shadow.authority-proposal.v1", prompt)

        required = shadow_host.host_prompt(
            task, "bounded-task", ["result.txt"], digest, "required"
        )
        self.assertIn("Invoke one native child agent", required)
        self.assertIn("Do not merely claim", required)
        self.assertNotIn("shadow.authority-proposal.v1", required)

        proposal = shadow_host.host_prompt(
            task,
            "bounded-task",
            [],
            digest,
            "direct",
            authority_proposal=True,
        )
        self.assertIn("shadow.authority-proposal.v1", proposal)
        self.assertIn("second, no-change pass", proposal)
        self.assertIn('"changed_paths":[]', proposal)
        self.assertIn("none; this proposal pass", proposal)

    def test_echoing_the_prompt_example_cannot_satisfy_the_real_receipt(self) -> None:
        task = "Change the bounded file."
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
        prompt = shadow_host.host_prompt(
            task, "bounded-task", ["result.txt"], digest, "direct"
        )

        example = shadow_host.extract_host_receipt([prompt])
        with self.assertRaises(shadow_host.HostError) as raised:
            shadow_host.validate_host_receipt(
                example,
                "bounded-task",
                ["result.txt"],
                "codex",
            )
        self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_attempt_receipt_fsyncs_its_file_and_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            destination = Path(dirname) / "evidence" / "attempt.json"
            kinds = {"file": False, "dir": False}
            real_fsync = os.fsync

            def spy(fd: int) -> None:
                kinds["dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"] = True
                real_fsync(fd)

            with mock.patch.object(shadow_host.os, "fsync", side_effect=spy):
                shadow_host.write_json(str(destination), {"schema": "test"})
        self.assertEqual(kinds, {"file": True, "dir": True})

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
                    shadow_host.validate_host_receipt(
                        raw,
                        "audit-task",
                        ["result.txt"],
                        "cursor",
                    )
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
                    shadow_host.validate_host_receipt(
                        raw,
                        "audit-task",
                        ["result.txt"],
                        "cursor",
                    )
                self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_oversized_successful_proposal_becomes_a_bounded_failure(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root, ignore_evidence=False)
            binary = make_host(root, mode="oversized-proposal")
            task = root / "task.txt"
            task.write_text("Return the bounded proposal.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "attempt.json"

            result = run_host(
                repo,
                binary,
                task,
                output,
                host="codex",
                authority_proposal=True,
            )
            raw = output.read_bytes()
            payload = json.loads(raw)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertLessEqual(len(raw), shadow_host.MAX_ATTEMPT_BYTES)
        self.assertEqual(payload["status"], "failed")
        self.assertIsNone(payload["proof_ref"])
        self.assertEqual(payload["tests"], [])
        self.assertNotIn("authority_proposal", payload)
        self.assertEqual(
            payload["blocked"],
            {
                "kind": "attempt_too_large",
                "detail": (
                    "successful authority proposal exceeded the "
                    f"{shadow_host.MAX_ATTEMPT_BYTES}-byte attempt limit"
                ),
            },
        )

    def test_authority_proposal_mode_refuses_custom_binary_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = make_repo(root, ignore_evidence=False)
            binary = make_host(root, mode="proposal")
            task = root / "task.txt"
            task.write_text("Return the bounded proposal.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "attempt.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "run",
                    "--host",
                    "codex",
                    "--work-class",
                    "coding",
                    "--delegation",
                    "direct",
                    "--binary",
                    str(binary),
                    "--authority-proposal",
                    "--repo",
                    str(repo),
                    "--task-file",
                    str(task),
                    "--task-id",
                    "add-proof",
                    "--out",
                    str(output),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(binary.with_suffix(".argv.json").exists())
            self.assertEqual(
                json.loads(result.stdout)["blocked"]["kind"],
                "proposal_binary_override",
            )

    def test_authority_proposal_mode_seals_head_and_git_control_state(self) -> None:
        cases = (
            ("proposal-commit", "source_head_changed"),
            ("proposal-config", "git_control_changed"),
        )
        for mode, expected_kind in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = make_repo(root, ignore_evidence=False)
                proposal = {
                    "schema": "shadow.authority-proposal.v1",
                    "entity_id": "a" * 64,
                    "row_id": "~a502",
                    "owner": "codexdk",
                    "base": {
                        "plan_root_sha256": "b" * 64,
                        "source_head": shadow_host.git_value(
                            repo,
                            "rev-parse",
                            "--verify",
                            "HEAD^{commit}",
                        ),
                    },
                    "request": {"transition": "complete"},
                }
                binary = make_host(root, mode=mode, proposal=proposal)
                task = root / "task.txt"
                task.write_text("Return the bounded proposal.\n", encoding="utf-8")
                output = repo / ".shadow" / "evidence" / "attempt.json"

                result = run_host(
                    repo,
                    binary,
                    task,
                    output,
                    host="codex",
                    authority_proposal=True,
                )
                payload = json.loads(output.read_text(encoding="utf-8"))

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(payload["status"], "blocked")
                self.assertEqual(payload["blocked"]["kind"], expected_kind)
                self.assertNotIn("authority_proposal", payload)

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

    def test_same_packet_contract_runs_through_all_four_hosts(self) -> None:
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
                        "--work-class",
                        "coding",
                        "--delegation",
                        "direct",
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
                route = shadow_host.resolve_route(host, "coding")
                self.assertEqual(
                    payload["execution_policy"],
                    {
                        "schema": shadow_host.POLICY_VERSION,
                        "work_class": "coding",
                        "requested_model": route.model,
                        "observed_model": None,
                        "delegation": "direct",
                        "requested_child_capability": None,
                        "observed_child_spans": None,
                        "observation": "owner-local-gauntlet-required",
                    },
                )
                # Pin the exact per-host argv: a silently dropped sandbox or
                # output flag would still pass every other assertion here.
                argv = json.loads(binary.with_suffix(".argv.json").read_text(encoding="utf-8"))
                resolved = str(repo.resolve())
                if host == "codex":
                    self.assertEqual(argv[1:12], [
                        "exec", "--disable", "multi_agent", "--model", "gpt-5.6-sol",
                        "--json", "--ephemeral", "--sandbox", "workspace-write", "-C", resolved,
                    ])
                    self.assertEqual(argv[12], "--output-last-message")
                elif host == "claude-code":
                    self.assertEqual(argv[1:], [
                        "--disallowedTools", "Agent", "--model", "opus", "--print",
                        "--output-format", "json", "--no-session-persistence",
                        "--permission-mode", "acceptEdits", "--add-dir", resolved,
                    ])
                elif host == "grok":
                    self.assertEqual(argv[1:11], [
                        "--no-subagents", "--model", "grok-4.6", "--cwd", resolved,
                        "--output-format", "json",
                        "--permission-mode", "acceptEdits", "--prompt-file",
                    ])
                    self.assertTrue(argv[11].endswith("prompt.txt"), argv[11])
                else:
                    self.assertEqual(argv[1:], [
                        "--model", "claude-opus-5-thinking-high", "--print",
                        "--output-format", "json", "--workspace", resolved,
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
                    "--work-class",
                    "coding",
                    "--delegation",
                    "direct",
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
                    "--work-class",
                    "coding",
                    "--delegation",
                    "direct",
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
                    "--work-class",
                    "coding",
                    "--delegation",
                    "direct",
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
                    "--work-class",
                    "coding",
                    "--delegation",
                    "direct",
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

    def test_pre_rename_evidence_is_ordinary_dirt_with_no_exemption(self) -> None:
        # The compatibility path is gone, and no exemption replaces it. An
        # untracked pre-rename directory is ordinary dirt (worktree not
        # clean); a gitignored one is a pre-existing ignored file outside the
        # packet, which the seal refuses too. Both refuse — the host no
        # longer recognizes the old name at all.
        for ignored, expected_kind in ((False, "worktree_dirty"), (True, "worktree_unsealed")):
            with self.subTest(ignored=ignored), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = make_repo(root)
                if ignored:
                    ignore_file = repo / ".gitignore"
                    ignore_file.write_text(
                        ignore_file.read_text(encoding="utf-8") + ".pilot-puppy/\n", encoding="utf-8"
                    )
                    git(repo, "add", ".gitignore")
                    git(repo, "commit", "-qm", "ignore the pre-rename directory")
                legacy = repo / ".pilot-puppy" / "evidence"
                legacy.mkdir(parents=True)
                (legacy / "old-attempt.json").write_text("{}\n", encoding="utf-8")
                binary = make_host(root)
                task = root / "task.txt"
                task.write_text("Add the proof marker and run the bounded test.\n", encoding="utf-8")
                output = repo / ".shadow" / "evidence" / "attempt.json"
                result = run_host(repo, binary, task, output, host="codex")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(
                    json.loads(result.stdout)["blocked"]["kind"], expected_kind)

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

    def test_failure_before_the_run_is_scrubbed_and_classified_like_any_block(self) -> None:
        # A git subprocess timeout raised before run_attempt's inner handler
        # stringifies the full argv, including the absolute worktree path. That
        # detail reaches main()'s handler, so main() must scrub it too.
        timeout = subprocess.TimeoutExpired(
            cmd=["git", "-C", "/Users/person/secret-worktree", "rev-parse", "--show-toplevel"],
            timeout=5,
        )
        self.assertIn("/Users/", str(timeout), "the induced detail must carry an absolute home path")
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            task = root / "task.txt"
            task.write_text("Do the bounded thing.\n", encoding="utf-8")
            stream = io.StringIO()
            with mock.patch.object(shadow_host.subprocess, "run", side_effect=timeout):
                with contextlib.redirect_stdout(stream):
                    code = shadow_host.main(
                        [
                            "run",
                            "--host",
                            "cursor",
                            "--work-class",
                            "coding",
                            "--delegation",
                            "direct",
                            "--binary",
                            str(root / "fake-host"),
                            "--repo",
                            str(root),
                            "--task-file",
                            str(task),
                            "--task-id",
                            "add-proof",
                            "--allowed-path",
                            "result.txt",
                            "--out",
                            "-",
                            "--json",
                        ]
                    )
            emitted = stream.getvalue()

        payload = json.loads(emitted)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["blocked"]["kind"], "git_unavailable")
        self.assertIn("<redacted-path>", payload["blocked"]["detail"])
        self.assertNotIn("/Users/", emitted)

    def test_refusal_status_separates_environmental_failures_from_blocks(self) -> None:
        for kind in ("host_failed", "host_launch_failed", "host_timeout"):
            with self.subTest(kind=kind):
                self.assertEqual(shadow_host._refusal_status(kind), "failed")
        for kind in ("git_unavailable", "worktree_dirty", "scope_violation"):
            with self.subTest(kind=kind):
                self.assertEqual(shadow_host._refusal_status(kind), "blocked")

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
