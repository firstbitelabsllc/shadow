"""The observed gauntlet's readback gate: accepted-but-unverifiable is red."""

from __future__ import annotations

from datetime import datetime, timezone
import http.server
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dev" / "shadow-observed-gauntlet.py"
SPEC = importlib.util.spec_from_file_location("shadow_observed_gauntlet", SCRIPT)
assert SPEC and SPEC.loader
gauntlet = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gauntlet
SPEC.loader.exec_module(gauntlet)


class FakeLangfuse(http.server.BaseHTTPRequestHandler):
    traces: set[str] = set()
    accept_otel = True
    clickhouse_queries: list[str] = []

    def log_message(self, *args: object) -> None:
        return

    def do_POST(self) -> None:
        if self.path == "/":
            length = int(self.headers.get("Content-Length", 0))
            query = self.rfile.read(length).decode()
            self.clickhouse_queries.append(query)
            trace_id = query.split("trace_id = '")[1].split("'")[0] if "trace_id = '" in query else ""
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"1" if trace_id in self.traces else b"0")
            return
        if not self.path.startswith("/api/public/otel/v1/traces"):
            self.send_error(404)
            return
        if not self.accept_otel:
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        for resource in payload.get("resourceSpans", []):
            for scope in resource.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    self.traces.add(span["traceId"])
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_GET(self) -> None:
        prefix = "/api/public/traces/"
        if self.path.startswith(prefix) and self.path[len(prefix):] in self.traces:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id":"ok"}')
            return
        self.send_error(404)


class ReadbackGateTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeLangfuse.traces = set()
        FakeLangfuse.accept_otel = True
        FakeLangfuse.clickhouse_queries = []
        self.server = http.server.HTTPServer(("127.0.0.1", 0), FakeLangfuse)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = {
            "SHADOW_LANGFUSE_HOST": f"http://127.0.0.1:{self.server.server_port}",
            "SHADOW_LANGFUSE_PUBLIC_KEY": "pk-test",
            "SHADOW_LANGFUSE_SECRET_KEY": "sk-test",
        }

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def run_gauntlet(self) -> int:
        fake_job = ["-c", "print('ok')"]
        # Ambient SHADOW_LANGFUSE_* from the operator's real opt-in must never
        # leak into the fake harness: a leftover READBACK_URL/PROJECT_ID would
        # point readback at the real ClickHouse and turn every fake job red.
        scrubbed = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SHADOW_LANGFUSE")
        }
        with (
            mock.patch.dict(os.environ, {**scrubbed, **self.env}, clear=True),
            mock.patch.object(gauntlet, "JOBS", {"fake": fake_job}),
        ):
            return gauntlet.main(["--jobs", "fake"])

    def test_ambient_operator_env_cannot_leak_into_the_fake_harness(self) -> None:
        leaked = {
            "SHADOW_LANGFUSE_READBACK_URL": "http://localhost:8123",
            "SHADOW_LANGFUSE_PROJECT_ID": "shadow-observability",
            "SHADOW_LANGFUSE_READBACK_USER": "clickhouse",
            "SHADOW_LANGFUSE_READBACK_PASSWORD": "clickhouse",
        }
        with mock.patch.dict(os.environ, leaked, clear=False):
            self.assertEqual(self.run_gauntlet(), 0)

    def test_delivered_and_read_back_exits_zero(self) -> None:
        self.assertEqual(self.run_gauntlet(), 0)

    def test_accepted_but_never_readable_is_red(self) -> None:
        with mock.patch.object(gauntlet.Sink, "verify_trace", return_value=False):
            self.assertEqual(self.run_gauntlet(), 1)

    def test_rejected_delivery_is_red(self) -> None:
        FakeLangfuse.accept_otel = False
        self.assertEqual(self.run_gauntlet(), 1)

    def test_dead_endpoint_is_red(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.assertEqual(self.run_gauntlet(), 1)

    def test_clickhouse_readback_path_preferred_when_configured(self) -> None:
        self.env["SHADOW_LANGFUSE_READBACK_URL"] = self.env["SHADOW_LANGFUSE_HOST"]
        self.env["SHADOW_LANGFUSE_PROJECT_ID"] = "shadow-test"
        self.assertEqual(self.run_gauntlet(), 0)
        self.assertTrue(
            any("FROM default.events_core" in q for q in FakeLangfuse.clickhouse_queries),
            "the v4 events_core readback must be used when READBACK_URL + PROJECT_ID are set",
        )

    def test_a_failed_event_delivery_turns_the_round_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            events.write_text(
                json.dumps({"verb": "throw", "recorded_at": "2026-08-29T00:00:00Z", "duration_ms": 1}) + "\n",
                encoding="utf-8",
            )
            self.env["SHADOW_LANGFUSE_EVENTS"] = str(events)
            real_send = gauntlet.Sink.send_spans

            def fail_events(self, spans):
                if spans and str(spans[0].get("name", "")).startswith("event:"):
                    return False
                return real_send(self, spans)

            with mock.patch.object(gauntlet.Sink, "send_spans", fail_events):
                self.assertEqual(self.run_gauntlet(), 1)


class EventForwardingTests(unittest.TestCase):
    """Forwarded spans carry the event's own clock, not the upload instant."""

    def _sink(self, delivered: bool = True) -> mock.Mock:
        sink = mock.Mock()
        sink.send_spans.return_value = delivered
        return sink

    def _events(self, tmp: str, lines: list[str]) -> Path:
        path = Path(tmp) / "events.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_spans_carry_recorded_at_and_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._events(tmp, [json.dumps({
                "recorded_at": "2026-08-29T07:19:00.5Z",
                "verb": "throw",
                "duration_ms": 1500,
                "outcome": "claimed",
            })])
            sink = self._sink()
            count, ok = gauntlet.forward_events(sink, path, "0" * 32, "1" * 16)
            self.assertEqual((count, ok), (1, True))
            (span,) = sink.send_spans.call_args.args[0]
            start = int(span["startTimeUnixNano"])
            expected = int(
                datetime(2026, 8, 29, 7, 19, 0, 500000, tzinfo=timezone.utc).timestamp()
                * 1_000_000_000
            )
            self.assertEqual(start, expected)
            self.assertEqual(int(span["endTimeUnixNano"]) - start, 1_500_000_000)

    def test_a_malformed_clock_falls_back_to_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._events(tmp, [json.dumps({"recorded_at": "not a time", "verb": "throw"})])
            sink = self._sink()
            before = gauntlet._now_ns()
            count, ok = gauntlet.forward_events(sink, path, "0" * 32, "1" * 16)
            after = gauntlet._now_ns()
            self.assertEqual((count, ok), (1, True))
            (span,) = sink.send_spans.call_args.args[0]
            self.assertTrue(before <= int(span["startTimeUnixNano"]) <= after)
            self.assertEqual(span["startTimeUnixNano"], span["endTimeUnixNano"])

    def test_an_unreadable_events_file_is_red_not_silent(self) -> None:
        count, ok = gauntlet.forward_events(
            self._sink(), Path("/definitely/not/here.jsonl"), "0" * 32, "1" * 16
        )
        self.assertEqual((count, ok), (0, False))

    def test_a_failed_event_delivery_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._events(tmp, [json.dumps({"verb": "throw"})])
            count, ok = gauntlet.forward_events(self._sink(delivered=False), path, "0" * 32, "1" * 16)
            self.assertEqual((count, ok), (1, False))


if __name__ == "__main__":
    unittest.main()
