"""Tests for scripts/vidux_signpost.py."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux_signpost.py"

spec = importlib.util.spec_from_file_location("vidux_signpost", SCRIPT)
assert spec is not None
signpost = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = signpost
spec.loader.exec_module(signpost)


class SignpostTests(unittest.TestCase):
    def test_emit_event_appends_jsonl_and_summary_counts_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "signposts.jsonl"

            signpost.emit_event(
                "drift",
                "record",
                status="ok",
                duration_ms=12,
                metadata={"drift_id": "D-1"},
                log_path=log,
                now="2026-05-22T23:59:00Z",
            )
            signpost.emit_event(
                "drift",
                "record",
                status="error",
                duration_ms=24,
                metadata={"error": "bad plan"},
                log_path=log,
                now="2026-05-22T23:59:01Z",
            )

            rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["schema_version"], 1)
            self.assertTrue(rows[0]["event_id"].startswith("sp_"))
            self.assertTrue(rows[0]["run_id"].startswith("run_"))
            self.assertEqual(rows[0]["feature"], "drift")
            self.assertEqual(rows[0]["action"], "record")
            self.assertEqual(rows[0]["status"], "ok")
            self.assertEqual(rows[0]["duration_ms"], 12)
            self.assertEqual(rows[0]["exit_code"], 0)
            self.assertIn("pid", rows[0]["attribution"])
            self.assertEqual(rows[0]["metadata"], {"drift_id": "D-1"})

            summary = signpost.summarize_events(log)
            self.assertEqual(summary["total_events"], 2)
            self.assertEqual(summary["features"]["drift.record"]["count"], 2)
            self.assertEqual(summary["features"]["drift.record"]["statuses"]["ok"], 1)
            self.assertEqual(summary["features"]["drift.record"]["statuses"]["error"], 1)
            self.assertEqual(summary["features"]["drift.record"]["avg_duration_ms"], 18.0)
            self.assertEqual(summary["features"]["drift.record"]["min_duration_ms"], 12.0)
            self.assertEqual(summary["features"]["drift.record"]["max_duration_ms"], 24.0)
            self.assertEqual(summary["features"]["drift.record"]["p50_duration_ms"], 18.0)

    def test_cli_emit_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "signposts.jsonl"

            emit = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "emit",
                    "--feature",
                    "cache",
                    "--action",
                    "suggest",
                    "--status",
                    "ok",
                    "--duration-ms",
                    "7",
                    "--log",
                    str(log),
                    "--meta",
                    "plan=PLAN.md",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(emit.returncode, 0, emit.stderr)
            self.assertIn("signposted cache.suggest ok", emit.stdout)

            summary = subprocess.run(
                [sys.executable, str(SCRIPT), "summary", "--log", str(log), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(summary.returncode, 0, summary.stderr)
            payload = json.loads(summary.stdout)
            self.assertEqual(payload["features"]["cache.suggest"]["count"], 1)

    def test_cli_wrap_preserves_exit_code_and_signposts(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "signposts.jsonl"

            ok = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "wrap",
                    "--feature",
                    "build",
                    "--action",
                    "unit",
                    "--log",
                    str(log),
                    "--",
                    sys.executable,
                    "-c",
                    "print('wrapped-ok')",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("wrapped-ok", ok.stdout)

            bad = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "wrap",
                    "--feature",
                    "build",
                    "--action",
                    "unit",
                    "--log",
                    str(log),
                    "--",
                    sys.executable,
                    "-c",
                    "import sys; sys.exit(3)",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(bad.returncode, 3)
            rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["status"], "ok")
            self.assertEqual(rows[0]["exit_code"], 0)
            self.assertEqual(rows[1]["status"], "error")
            self.assertEqual(rows[1]["exit_code"], 3)

    def test_trace_orders_hook_and_subagent_events_by_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "signposts.jsonl"
            env_keys = [
                "VIDUX_SIGNPOST_RUN_ID",
                "VIDUX_RUNTIME",
                "CODEX_SESSION_ID",
                "CODEX_THREAD_ID",
                "CLAUDE_SESSION_ID",
                "CLAUDE_AUTOMATION_ID",
                "CURSOR_SESSION_ID",
            ]
            saved = {key: os.environ.get(key) for key in env_keys}
            try:
                for key in env_keys:
                    os.environ.pop(key, None)
                os.environ["VIDUX_SIGNPOST_RUN_ID"] = "run-call-stack"
                os.environ["CODEX_SESSION_ID"] = "codex-1"
                signpost.emit_event(
                    "hook",
                    "beforeTask",
                    status="ok",
                    called="doctor",
                    log_path=log,
                    now="2026-06-03T10:00:00Z",
                )
                os.environ.pop("CODEX_SESSION_ID", None)
                os.environ["CODEX_THREAD_ID"] = "ambient-codex-thread"
                os.environ["CLAUDE_SESSION_ID"] = "claude-1"
                signpost.emit_event(
                    "subagent",
                    "spawn",
                    status="ok",
                    called="worker-plan",
                    log_path=log,
                    now="2026-06-03T10:00:01Z",
                )
                os.environ.pop("CLAUDE_SESSION_ID", None)
                os.environ["CODEX_SESSION_ID"] = "ambient-codex-session"
                os.environ["VIDUX_RUNTIME"] = "cursor"
                os.environ["CURSOR_SESSION_ID"] = "cursor-1"
                signpost.emit_event(
                    "hook",
                    "afterTask",
                    status="ok",
                    called="checkpoint",
                    log_path=log,
                    now="2026-06-03T10:00:02Z",
                )
            finally:
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

            trace = signpost.trace_events(log, run_id="run-call-stack")
            self.assertEqual(trace["total_events"], 3)
            self.assertEqual([event["action"] for event in trace["events"]], ["beforeTask", "spawn", "afterTask"])
            self.assertEqual([event["runtime"] for event in trace["events"]], ["codex", "claude", "cursor"])

            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "trace",
                    "--log",
                    str(log),
                    "--run-id",
                    "run-call-stack",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(cli.returncode, 0, cli.stderr)
            payload = json.loads(cli.stdout)
            self.assertEqual(payload["events"][1]["feature"], "subagent")

    def test_lifecycle_smoke_emits_standard_hook_subagent_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "signposts.jsonl"

            trace = signpost.emit_lifecycle_smoke(log_path=log, run_id="run-lifecycle")

            self.assertEqual(trace["total_events"], 4)
            self.assertEqual(
                [(event["feature"], event["action"]) for event in trace["events"]],
                [
                    ("hook", "beforeTask"),
                    ("subagent", "spawn"),
                    ("task", "verify"),
                    ("hook", "afterTask"),
                ],
            )
            self.assertEqual(
                [event["runtime"] for event in trace["events"]],
                ["codex", "claude", "cursor", "codex"],
            )
            self.assertEqual(trace["events"][0]["called"], "scripts/vidux-doctor.sh --json")

            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "lifecycle-smoke",
                    "--log",
                    str(log),
                    "--run-id",
                    "run-lifecycle-cli",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(cli.returncode, 0, cli.stderr)
            payload = json.loads(cli.stdout)
            self.assertEqual(payload["run_id"], "run-lifecycle-cli")
            self.assertEqual(payload["events"][2]["runtime"], "cursor")

    def test_spawned_subagent_smoke_simulates_inherited_parent_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "signposts.jsonl"
            env_keys = [
                "VIDUX_SIGNPOST_RUN_ID",
                "VIDUX_RUNTIME",
                "VIDUX_AGENT_ID",
                "CODEX_SESSION_ID",
                "CODEX_THREAD_ID",
                "CLAUDE_SESSION_ID",
                "CURSOR_SESSION_ID",
            ]
            saved = {key: os.environ.get(key) for key in env_keys}
            try:
                os.environ["VIDUX_RUNTIME"] = "ambient-runtime"
                os.environ["CODEX_SESSION_ID"] = "ambient-codex-session"

                trace = signpost.emit_spawned_subagent_smoke(log_path=log, run_id="run-spawned")

                self.assertEqual(os.environ.get("VIDUX_RUNTIME"), "ambient-runtime")
                self.assertEqual(os.environ.get("CODEX_SESSION_ID"), "ambient-codex-session")
            finally:
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

            self.assertEqual(trace["total_events"], 4)
            self.assertEqual(
                [(event["feature"], event["action"]) for event in trace["events"]],
                [
                    ("hook", "beforeTask"),
                    ("subagent", "spawn"),
                    ("task", "verify"),
                    ("hook", "afterTask"),
                ],
            )
            self.assertEqual(
                [event["runtime"] for event in trace["events"]],
                ["codex", "claude", "cursor", "codex"],
            )
            self.assertEqual(
                [event["agent_id"] for event in trace["events"]],
                [
                    "smoke-codex-parent",
                    "smoke-claude-worker",
                    "smoke-cursor-worker",
                    "smoke-codex-parent",
                ],
            )
            self.assertEqual({event["run_id"] for event in trace["events"]}, {"run-spawned"})
            self.assertEqual(trace["events"][1]["thread_id"], "smoke-codex-thread")
            self.assertEqual(trace["events"][2]["thread_id"], "smoke-codex-thread")
            self.assertTrue(trace["events"][1]["metadata"]["inherited_codex_thread"])
            self.assertTrue(trace["events"][2]["metadata"]["inherited_codex_thread"])
            self.assertEqual(trace["events"][1]["metadata"]["worker_runtime"], "claude")
            self.assertEqual(trace["events"][2]["metadata"]["worker_runtime"], "cursor")

            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "spawned-subagent-smoke",
                    "--log",
                    str(log),
                    "--run-id",
                    "run-spawned-cli",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(cli.returncode, 0, cli.stderr)
            payload = json.loads(cli.stdout)
            self.assertEqual(payload["run_id"], "run-spawned-cli")
            self.assertEqual(payload["total_events"], 4)
            self.assertEqual(payload["events"][1]["runtime"], "claude")
            self.assertEqual(payload["events"][2]["thread_id"], "smoke-codex-thread")

    def test_main_empty_argv_does_not_read_process_argv(self):
        """Programmatic main([]) must not emit from ambient sys.argv."""
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "ambient-signposts.jsonl"
            original_argv = sys.argv[:]
            sys.argv = [
                "probe",
                "emit",
                "--feature",
                "ambient",
                "--action",
                "leak",
                "--status",
                "ok",
                "--log",
                str(log),
            ]
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with (
                    self.assertRaises(SystemExit) as raised,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    signpost.main([])
            finally:
                sys.argv = original_argv

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("the following arguments are required", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
