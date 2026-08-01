"""Tests for the bounded, local-only telemetry contract seed."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
from threading import Thread
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from browser.telemetry import (  # noqa: E402
    SCHEMA,
    TelemetryConfigError,
    TelemetryInputError,
    build_event,
    emit_local,
    to_otlp,
)


BASE = {
    "event": "outcome.finished",
    "outcome_id": "pilot-puppy-demo",
    "plan_revision": 4,
    "state": "finished_with_proof",
    "native_host": "codex",
    "model_label": "local",
    "proof_status": "delivered",
    "attempt": 1,
    "retries": 0,
    "compactions": 0,
    "time_to_first_progress_ms": 1200,
    "time_to_terminal_ms": 5400,
    "at": "2026-08-01T22:00:00Z",
}


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class TelemetryTests(unittest.TestCase):
    def test_build_event_is_allowlisted_and_normalizes_timestamp(self):
        event = build_event(BASE)

        self.assertEqual(event["schema"], SCHEMA)
        self.assertEqual(event["at"], "2026-08-01T22:00:00.000Z")
        self.assertEqual(event["state"], "finished_with_proof")
        self.assertNotIn("prompt", event)
        self.assertNotIn("transcript", event)

    def test_unknown_fields_and_private_values_fail_closed(self):
        with self.assertRaises(TelemetryInputError):
            build_event({**BASE, "prompt": "hidden"})
        private_path = "".join(("/", "Users", "/leo/private"))
        with self.assertRaises(TelemetryInputError):
            build_event({**BASE, "model_label": private_path})
        secret_word = "".join(("se", "cret"))
        with self.assertRaises(TelemetryInputError):
            build_event({**BASE, "model_label": secret_word})

    def test_otlp_envelope_contains_only_bounded_attributes(self):
        envelope = to_otlp(build_event(BASE))
        span = envelope["resourceSpans"][0]["scopeSpans"][0]["spans"][0]

        self.assertEqual(len(span["traceId"]), 32)
        self.assertEqual(len(span["spanId"]), 16)
        self.assertEqual(span["name"], "outcome.finished")
        self.assertTrue(all(item["key"].startswith("vidux.") for item in span["attributes"]))
        self.assertNotIn("prompt", json.dumps(envelope))

    def test_otlp_rejects_an_unvalidated_event_mapping(self):
        event = {"schema": SCHEMA, **BASE, "prompt": "hidden"}

        with self.assertRaises(TelemetryInputError):
            to_otlp(event)

    def test_export_is_disabled_without_an_explicit_endpoint(self):
        called = []

        def opener(*_args, **_kwargs):
            called.append(True)
            raise AssertionError("disabled export attempted a network call")

        result = emit_local(build_event(BASE), endpoint="", opener=opener)

        self.assertEqual(result, {"status": "disabled"})
        self.assertEqual(called, [])

    def test_export_rejects_non_loopback_endpoints(self):
        endpoint = "https://" + ".".join(("external", "invalid")) + "/otel"

        with self.assertRaises(TelemetryConfigError):
            emit_local(build_event(BASE), endpoint=endpoint)

        with self.assertRaises(TelemetryConfigError):
            emit_local(build_event(BASE), endpoint="http://localhost:4318/v1/traces?key=hidden")

    def test_export_posts_otlp_json_to_loopback(self):
        received = []

        def opener(request, timeout):
            received.append((request, timeout))
            return _Response()

        result = emit_local(
            build_event(BASE),
            endpoint="http://127.0.0.1:4318/v1/traces",
            opener=opener,
        )

        self.assertEqual(result, {"status": "sent", "status_code": 200})
        self.assertEqual(len(received), 1)
        request, timeout = received[0]
        self.assertEqual(timeout, 2)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertNotIn("Authorization", request.headers)
        body = json.loads(request.data.decode("utf-8"))
        self.assertIn("resourceSpans", body)

    def test_real_loopback_collector_receives_completion_and_failure_spans(self):
        received = []

        class Collector(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - stdlib handler hook
                length = int(self.headers["Content-Length"])
                received.append(json.loads(self.rfile.read(length).decode("utf-8")))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
        proxy_env = {
            "HTTP_PROXY": "http://127.0.0.1:9/",
            "http_proxy": "http://127.0.0.1:9/",
            "ALL_PROXY": "http://127.0.0.1:9/",
            "all_proxy": "http://127.0.0.1:9/",
        }
        try:
            for payload in (
                BASE,
                {
                    **BASE,
                    "event": "outcome.failed",
                    "state": "not_delivered",
                    "proof_status": "not_delivered",
                    "failure_class": "host_receipt_missing",
                },
            ):
                with mock.patch.dict(os.environ, proxy_env, clear=False):
                    os.environ.pop("NO_PROXY", None)
                    os.environ.pop("no_proxy", None)
                    result = emit_local(build_event(payload), endpoint=endpoint)
                self.assertEqual(result["status"], "sent")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(len(received), 2)
        names = [
            item["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"]
            for item in received
        ]
        self.assertEqual(names, ["outcome.finished", "outcome.failed"])


if __name__ == "__main__":
    unittest.main()
