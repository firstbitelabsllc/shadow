"""The observed gauntlet's readback gate: accepted-but-unverifiable is red."""

from __future__ import annotations

from datetime import datetime, timezone
import http.server
import importlib.util
import contextlib
import io
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
    otel_spans: list[dict] = []
    huddle_rows_override: object | None = None
    huddle_project = "huddle-test"

    def log_message(self, *args: object) -> None:
        return

    def do_POST(self) -> None:
        if self.path == "/":
            length = int(self.headers.get("Content-Length", 0))
            query = self.rfile.read(length).decode()
            self.clickhouse_queries.append(query)
            if "name = 'huddle.lifecycle'" in query:
                trace_id = query.split("trace_id = '")[1].split("'")[0] if "trace_id = '" in query else ""
                project_id = query.split("project_id = '")[1].split("'")[0] if "project_id = '" in query else ""
                response = self.huddle_rows_override
                if project_id != self.huddle_project or trace_id not in self.traces:
                    response = ""
                elif response is None:
                    rows = []
                    for span in self.otel_spans:
                        if span.get("name") != "huddle.lifecycle" or span.get("traceId") != trace_id:
                            continue
                        values = {}
                        for attribute in span.get("attributes", []):
                            value = attribute.get("value", {})
                            raw = next(iter(value.values()), None)
                            if "intValue" in value:
                                raw = int(raw)
                            values[attribute["key"].removeprefix("shadow.")] = raw
                        rows.append(values)
                    response = "".join(json.dumps(row) + "\n" for row in rows)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response.encode() if isinstance(response, str) else response)
                return
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
                    self.otel_spans.append(span)
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
        FakeLangfuse.otel_spans = []
        FakeLangfuse.huddle_rows_override = None
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

    def test_failed_job_tail_lands_in_the_local_log(self) -> None:
        failing_job = ["-c", "import sys; print('boom-tail-marker'); sys.exit(3)"]
        scrubbed = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SHADOW_LANGFUSE")
        }
        out = io.StringIO()
        with (
            mock.patch.dict(os.environ, {**scrubbed, **self.env}, clear=True),
            mock.patch.object(gauntlet, "JOBS", {"failing": failing_job}),
            contextlib.redirect_stdout(out),
        ):
            rc = gauntlet.main(["--jobs", "failing"])
        self.assertEqual(rc, 1)
        self.assertIn("boom-tail-marker", out.getvalue())

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


class HuddleLifecycleObservedTests(unittest.TestCase):
    """The owner-local Huddle journey is real; only its network boundary is fake."""

    def setUp(self) -> None:
        FakeLangfuse.traces = set()
        FakeLangfuse.accept_otel = True
        FakeLangfuse.clickhouse_queries = []
        FakeLangfuse.otel_spans = []
        FakeLangfuse.huddle_rows_override = None
        self.server = http.server.HTTPServer(("127.0.0.1", 0), FakeLangfuse)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = {
            "SHADOW_LANGFUSE_HOST": f"http://127.0.0.1:{self.server.server_port}",
            "SHADOW_LANGFUSE_PUBLIC_KEY": "pk-test",
            "SHADOW_LANGFUSE_SECRET_KEY": "sk-test",
        }
        self.env.update({
            "SHADOW_LANGFUSE_READBACK_URL": self.env["SHADOW_LANGFUSE_HOST"],
            "SHADOW_LANGFUSE_PROJECT_ID": "huddle-test",
        })

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @staticmethod
    def expected_rows() -> list[dict]:
        return [
            {"huddle_id": "hdl_00000001", "huddle_generation": 1,
             "lifecycle_step": "hold_observed", "huddle_state": "open_round_1",
             "opened_revision": 7, "settled_revision": 0, "compliance_revision": 0},
            {"huddle_id": "hdl_00000001", "huddle_generation": 1,
             "lifecycle_step": "bids_recorded", "huddle_state": "open_round_1",
             "opened_revision": 7, "settled_revision": 0, "compliance_revision": 0},
            {"huddle_id": "hdl_00000001", "huddle_generation": 2,
             "lifecycle_step": "settled", "huddle_state": "awaiting_compliance",
             "opened_revision": 7, "settled_revision": 10, "compliance_revision": 0},
            {"huddle_id": "hdl_00000001", "huddle_generation": 2,
             "lifecycle_step": "held_write_refused", "huddle_state": "awaiting_compliance",
             "opened_revision": 7, "settled_revision": 10, "compliance_revision": 0},
            {"huddle_id": "hdl_00000001", "huddle_generation": 3,
             "lifecycle_step": "compliance_satisfied", "huddle_state": "resolved",
             "opened_revision": 7, "settled_revision": 10, "compliance_revision": 11},
        ]

    def test_huddle_lifecycle_drives_real_disposable_board_and_reads_exact_spans(self) -> None:
        self.assertEqual(self.run_gauntlet_job("huddle-lifecycle"), 0)
        huddle_spans = [span for span in FakeLangfuse.otel_spans if span["name"] == "huddle.lifecycle"]
        self.assertEqual(len(huddle_spans), 5)
        observed = []
        for span in huddle_spans:
            self.assertEqual(
                {attribute["key"] for attribute in span["attributes"]},
                {
                    "shadow.huddle_id", "shadow.huddle_generation", "shadow.lifecycle_step",
                    "shadow.huddle_state", "shadow.opened_revision", "shadow.settled_revision",
                    "shadow.compliance_revision",
                },
            )
            values = {
                attribute["key"].removeprefix("shadow."): next(iter(attribute["value"].values()))
                for attribute in span["attributes"]
            }
            observed.append(values)
        self.assertEqual(
            [row["lifecycle_step"] for row in observed],
            ["hold_observed", "bids_recorded", "settled", "held_write_refused", "compliance_satisfied"],
        )
        self.assertEqual(
            [row["huddle_state"] for row in observed],
            ["open_round_1", "open_round_1", "awaiting_compliance", "awaiting_compliance", "resolved"],
        )
        self.assertEqual([row["huddle_generation"] for row in observed], ["1", "1", "2", "2", "3"])
        self.assertEqual([row["settled_revision"] for row in observed[:2]], ["0", "0"])
        self.assertEqual([row["compliance_revision"] for row in observed[:-1]], ["0", "0", "0", "0"])
        query = next(query for query in FakeLangfuse.clickhouse_queries if "huddle.lifecycle" in query)
        self.assertIn("project_id = 'huddle-test'", query)
        self.assertIn("name = 'huddle.lifecycle'", query)
        self.assertIn("output_format_json_quote_64bit_integers = 0", query)
        self.assertIn("FORMAT JSONEachRow", query)

    def test_huddle_readback_refuses_every_inexact_projection(self) -> None:
        trace_id = "a" * 32
        expected = self.expected_rows()
        cases = (
            ("missing", expected[:-1], trace_id, "huddle-test"),
            ("partial", [{"huddle_id": expected[0]["huddle_id"]}], trace_id, "huddle-test"),
            ("duplicate", [*expected, expected[-1]], trace_id, "huddle-test"),
            ("wrong scalar", [*expected[:-1], {**expected[-1], "compliance_revision": 12}], trace_id, "huddle-test"),
            ("wrong project", expected, trace_id, "other-test"),
            ("wrong trace", expected, "b" * 32, "huddle-test"),
            ("malformed", "not-json\n", trace_id, "huddle-test"),
        )
        scrubbed = {key: value for key, value in os.environ.items() if not key.startswith("SHADOW_LANGFUSE")}
        with mock.patch.dict(os.environ, {**scrubbed, **self.env}, clear=True):
            sink = gauntlet.Sink()
            FakeLangfuse.traces.add(trace_id)
            for name, response, checked_trace, project_id in cases:
                with self.subTest(name=name):
                    FakeLangfuse.huddle_rows_override = (
                        response if isinstance(response, str)
                        else "".join(json.dumps(row) + "\n" for row in response)
                    )
                    sink.project_id = project_id
                    self.assertFalse(sink.verify_huddle_trace(checked_trace, expected, attempts=1, delay_s=0))
        FakeLangfuse.huddle_rows_override = None

    def test_huddle_refuses_unsafe_or_ambiguous_selection_before_lifecycle_or_send(self) -> None:
        cases = (
            ("remote OTLP", {**self.env, "SHADOW_LANGFUSE_HOST": "https://example.invalid"}, ["--jobs", "huddle-lifecycle"]),
            ("credentialed OTLP", {**self.env, "SHADOW_LANGFUSE_HOST": "http://user:pass@127.0.0.1:4318"}, ["--jobs", "huddle-lifecycle"]),
            ("zero rounds", self.env, ["--jobs", "huddle-lifecycle", "--rounds", "0"]),
            ("mixed jobs", self.env, ["--jobs", "huddle-lifecycle,accept"]),
        )
        for name, env, argv in cases:
            with self.subTest(name=name), mock.patch.object(gauntlet, "huddle_lifecycle_rows") as lifecycle:
                with mock.patch.dict(os.environ, env, clear=True):
                    self.assertEqual(gauntlet.main(argv), 2)
                lifecycle.assert_not_called()
        self.assertEqual(FakeLangfuse.otel_spans, [])

    def test_huddle_spans_are_provisional_until_exact_readback(self) -> None:
        self.assertEqual(self.run_gauntlet_job("huddle-lifecycle"), 0)
        huddle_spans = [span for span in FakeLangfuse.otel_spans if span["name"] == "huddle.lifecycle"]
        self.assertEqual([span["status"] for span in huddle_spans], [{"code": 2}] * 5)

    def run_gauntlet_job(self, name: str) -> int:
        scrubbed = {key: value for key, value in os.environ.items() if not key.startswith("SHADOW_LANGFUSE")}
        with mock.patch.dict(os.environ, {**scrubbed, **self.env}, clear=True):
            return gauntlet.main(["--jobs", name])


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


class FailureTailTests(unittest.TestCase):
    def test_short_output_is_unchanged(self) -> None:
        self.assertEqual(gauntlet._failure_tail("one line\n"), "one line\n")

    def test_long_output_without_failure_header_keeps_the_closing_tail(self) -> None:
        output = "x" * 900
        self.assertEqual(gauntlet._failure_tail(output), output[-600:])

    def test_mass_failure_names_the_first_failure_and_the_close(self) -> None:
        output = (
            "noise\n" * 50
            + "FAIL: test_first_cause\nAssertionError: the real cause\n"
            + "middle\n" * 100
            + "FAIL: test_last_summary\nAssertionError: not the cause\n"
        )
        tail = gauntlet._failure_tail(output)
        self.assertIn("FAIL: test_first_cause", tail)
        self.assertIn("AssertionError: the real cause", tail)
        self.assertIn("FAIL: test_last_summary", tail)
        self.assertIn("[...]", tail)


if __name__ == "__main__":
    unittest.main()
