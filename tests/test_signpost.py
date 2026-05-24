"""Tests for scripts/vidux_signpost.py."""

from __future__ import annotations

import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
