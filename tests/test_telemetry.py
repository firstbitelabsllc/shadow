"""Privacy and ordering tests for optional Shadow Langfuse observation."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ROUTE_SCRIPT = SCRIPTS / "shadow-route.py"
HOST_SCRIPT = SCRIPTS / "shadow-host.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import shadow_telemetry as telemetry
from shadow_roster_lib import initialize_roster


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load_module("shadow_route_for_telemetry", ROUTE_SCRIPT)
host = load_module("shadow_host_for_telemetry", HOST_SCRIPT)


FAKE_HOST = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

if "--version" in sys.argv:
    print("fake-native-host 1.0")
    raise SystemExit(0)

pathlib.Path.cwd().joinpath("result.txt").write_text("changed\n", encoding="utf-8")
print("```json")
print(json.dumps({
    "schema": "shadow.host-receipt.v1",
    "task_id": "add-proof",
    "status": "ok",
    "summary": "bounded fake host completed the task",
    "proof_ref": "tests-green",
    "changed_paths": ["result.txt"],
    "tests": [{"name": "fake-test", "status": "pass"}],
}))
print("```")
'''


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "shadow-test@example.invalid")
    git(repo, "config", "user.name", "Shadow Test")
    (repo / "result.txt").write_text("base\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".shadow/\n", encoding="utf-8")
    git(repo, "add", "result.txt", ".gitignore")
    git(repo, "commit", "-qm", "base")
    return repo


def make_roster(root: Path) -> Path:
    path = root / "config" / "roster.json"
    initialize_roster(path)
    return path


class FakeSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeLangfuse:
    init_calls: list[dict[str, str]] = []
    observation_calls: list[dict[str, object]] = []
    flush_calls = 0

    def __init__(self, **kwargs: str) -> None:
        type(self).init_calls.append(kwargs)

    def start_as_current_observation(self, **kwargs: object) -> FakeSpan:
        type(self).observation_calls.append(kwargs)
        return FakeSpan()

    def flush(self) -> None:
        type(self).flush_calls += 1


class FakeLangfuseModule:
    Langfuse = FakeLangfuse


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeLangfuse.init_calls.clear()
        FakeLangfuse.observation_calls.clear()
        FakeLangfuse.flush_calls = 0

    def enabled_environment(self) -> dict[str, str]:
        return {
            "SHADOW_TELEMETRY": "langfuse",
            "LANGFUSE_BASE_URL": "https://langfuse.example.invalid",
            "LANGFUSE_PUBLIC_KEY": "public-test-key",
            "LANGFUSE_SECRET_KEY": "secret-test-key",
        }

    def test_default_mode_never_imports_or_contacts_the_optional_sdk(self) -> None:
        document = {"status": "ready", "selection": {"role": "dev", "host": "cursor"}}
        with mock.patch.object(telemetry.importlib, "import_module") as imported:
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(telemetry.record_route(document))
        imported.assert_not_called()

    def test_enabled_export_has_only_closed_metadata_and_null_io(self) -> None:
        payload = {
            "host": "cursor",
            "status": "ok",
            "duration_s": 61,
            "task_id": "private-task-marker",
            "summary": "private summary marker",
            "changed_paths": ["/Users/example/private-file.txt"],
            "route": {"role": "dev", "task_sha256": "private-route-marker"},
        }
        with mock.patch.dict(os.environ, self.enabled_environment(), clear=True):
            with mock.patch.object(telemetry.importlib, "import_module", return_value=FakeLangfuseModule):
                self.assertTrue(telemetry.record_host(payload, allowed_path_count=2))

        self.assertEqual(len(FakeLangfuse.init_calls), 1)
        self.assertEqual(FakeLangfuse.flush_calls, 1)
        self.assertEqual(len(FakeLangfuse.observation_calls), 1)
        observation = FakeLangfuse.observation_calls[0]
        self.assertEqual(observation["name"], "shadow.host_finished")
        self.assertIsNone(observation["input"])
        self.assertIsNone(observation["output"])
        self.assertEqual(
            observation["metadata"],
            {
                "schema": "shadow.telemetry.v1",
                "event": "host_finished",
                "session_id": None,
                "lane_id": None,
                "role": "dev",
                "host": "cursor",
                "state": "ok",
                "duration_bucket": "1_5m",
                "lane_count": 1,
                "path_count": 2,
                "scope_ok": True,
                "proof_ok": True,
                "merge_ok": None,
            },
        )
        rendered = json.dumps(observation, sort_keys=True).lower()
        for forbidden in ("private-task-marker", "private summary", "/users", "private-route-marker"):
            self.assertNotIn(forbidden, rendered)

    def test_invalid_metadata_or_sdk_failure_stays_local_and_quiet(self) -> None:
        unsafe = {
            "schema": telemetry.SCHEMA,
            "event": "route_prepared",
            "session_id": None,
            "lane_id": None,
            "role": "dev",
            "host": "cursor",
            "state": "ready",
            "duration_bucket": None,
            "lane_count": 1,
            "path_count": 0,
            "scope_ok": None,
            "proof_ok": None,
            "merge_ok": None,
            "task_text": "must never leave",
        }
        with self.assertRaises(ValueError):
            telemetry.validate_metadata(unsafe)
        valid = {key: value for key, value in unsafe.items() if key != "task_text"}
        with mock.patch.dict(os.environ, self.enabled_environment(), clear=True):
            with mock.patch.object(telemetry.importlib, "import_module", side_effect=RuntimeError("offline")):
                self.assertFalse(telemetry.emit(valid))

    def test_route_observation_occurs_only_after_the_local_packet_exists(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            roster_file = make_roster(root)
            task = root / "task.md"
            task.write_text("Change the bounded file.\n", encoding="utf-8")
            output = repo / ".shadow" / "evidence" / "route.json"

            def observed(document: dict[str, object]) -> bool:
                self.assertTrue(output.is_file())
                self.assertEqual(json.loads(output.read_text(encoding="utf-8")), document)
                return True

            with mock.patch.object(route.telemetry, "record_route", side_effect=observed) as recorder:
                with contextlib.redirect_stdout(io.StringIO()):
                    code = route.main(
                        [
                            "--repo",
                            str(repo),
                            "--task-id",
                            "fix-file",
                            "--task-file",
                            str(task),
                            "--task-kind",
                            "dev",
                            "--roster-file",
                            str(roster_file),
                            "--availability",
                            "assume",
                            "--out",
                            ".shadow/evidence/route.json",
                        ]
                    )

        self.assertEqual(code, 0)
        recorder.assert_called_once()

    def test_host_observation_occurs_only_after_the_local_receipt_exists(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            task = root / "task.md"
            task.write_text("Change the bounded file.\n", encoding="utf-8")
            binary = root / "fake-host"
            binary.write_text(FAKE_HOST, encoding="utf-8")
            binary.chmod(0o755)
            output = repo / ".shadow" / "evidence" / "attempt.json"
            args = type(
                "Args",
                (),
                {
                    "host": "cursor",
                    "binary": str(binary),
                    "repo": str(repo),
                    "task_file": str(task),
                    "task_id": "add-proof",
                    "allowed_path": ["result.txt"],
                    "route_file": None,
                    "roster_file": None,
                    "use_seat": False,
                    "seat_file": None,
                    "out": str(output),
                    "force": False,
                    "timeout_seconds": 10,
                },
            )()

            def observed(payload: dict[str, object], *, allowed_path_count: int) -> bool:
                self.assertTrue(output.is_file())
                self.assertEqual(json.loads(output.read_text(encoding="utf-8")), payload)
                self.assertEqual(allowed_path_count, 1)
                return True

            with mock.patch.object(host.telemetry, "record_host", side_effect=observed) as recorder:
                payload, code = host.run_attempt(args)

        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        recorder.assert_called_once()


if __name__ == "__main__":
    unittest.main()
