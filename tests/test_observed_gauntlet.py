"""The observed gauntlet's readback gate: accepted-but-unverifiable is red."""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
from pathlib import Path
import sys
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

    def log_message(self, *args: object) -> None:
        return

    def do_POST(self) -> None:
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
        with mock.patch.dict(os.environ, self.env, clear=False), mock.patch.object(
            gauntlet, "JOBS", {"fake": fake_job}
        ):
            return gauntlet.main(["--jobs", "fake"])

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


if __name__ == "__main__":
    unittest.main()
