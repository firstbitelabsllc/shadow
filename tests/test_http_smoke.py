import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "vidux_http_smoke", ROOT / "scripts" / "vidux-http-smoke.py"
)
http_smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(http_smoke)


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: N802
        return

    def write_body(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self):  # noqa: N802
        if self.path == "/fast":
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.write_body(body)
            return
        if self.path == "/partial":
            body = b"x" * 8192
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.write_body(body)
            self.wfile.flush()
            time.sleep(0.5)
            return
        if self.path == "/slow-empty":
            time.sleep(0.5)
            self.send_response(200)
            self.end_headers()
            self.write_body(b"late")
            return
        self.send_response(404)
        self.end_headers()


class HttpSmokeTests(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_fast_route_passes(self):
        result = http_smoke.smoke_url(self.url("/fast"), timeout=0.3)

        self.assertEqual(result["verdict"], "pass")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertGreater(result["bytes_read"], 0)
        self.assertFalse(result["timed_out"])

    def test_control_characters_in_url_fail_cleanly_instead_of_raising(self):
        url = self.url("/fast") + "\x01\x02"

        result = http_smoke.smoke_url(url, timeout=0.3)

        self.assertEqual(result["verdict"], "fail_transport")
        self.assertFalse(result["ok"])
        self.assertTrue(result["error"])

    def test_partial_timeout_is_warning(self):
        result = http_smoke.smoke_url(self.url("/partial"), timeout=0.2)

        self.assertEqual(result["verdict"], "warn_partial")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertGreater(result["bytes_read"], 0)
        self.assertTrue(result["timed_out"])
        self.assertTrue(result["partial"])

    def test_zero_byte_timeout_is_budget_failure(self):
        result = http_smoke.smoke_url(self.url("/slow-empty"), timeout=0.2)

        self.assertEqual(result["verdict"], "fail_budget")
        self.assertFalse(result["ok"])
        self.assertEqual(result["bytes_read"], 0)
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["partial"])

    def test_main_json_reports_warn_and_fail_counts(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = http_smoke.main([
                "--json",
                "--timeout",
                "0.2",
                self.url("/fast"),
                self.url("/partial"),
                self.url("/slow-empty"),
            ])

        payload = json.loads(buf.getvalue())
        self.assertEqual(rc, 1)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["strict_ok"])
        self.assertFalse(payload["warning_only"])
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["warn_count"], 1)
        self.assertEqual(payload["fail_count"], 1)
        self.assertEqual([item["verdict"] for item in payload["results"]], [
            "pass",
            "warn_partial",
            "fail_budget",
        ])

    def test_warning_only_json_ok_matches_exit_status(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = http_smoke.main([
                "--json",
                "--timeout",
                "0.2",
                self.url("/fast"),
                self.url("/partial"),
            ])

        payload = json.loads(buf.getvalue())
        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["strict_ok"])
        self.assertTrue(payload["warning_only"])
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["warn_count"], 1)
        self.assertEqual(payload["fail_count"], 0)

    def test_invalid_numeric_options_fail_without_traceback(self):
        for args, expected in [
            (["--timeout", "0", self.url("/fast")], "--timeout must be greater than 0"),
            (["--timeout", "-1", self.url("/fast")], "--timeout must be greater than 0"),
            (["--max-sample-bytes", "-1", self.url("/fast")], "--max-sample-bytes must be 0 or greater"),
        ]:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    http_smoke.main(args)

            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn(expected, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_empty_argv_does_not_read_process_argv(self):
        original_argv = sys.argv[:]
        stderr = io.StringIO()
        try:
            sys.argv = ["pytest", self.url("/fast")]
            with contextlib.redirect_stderr(stderr):
                rc = http_smoke.main([])
        finally:
            sys.argv = original_argv

        self.assertEqual(rc, 2)
        self.assertIn("at least one URL is required", stderr.getvalue())

    def test_bin_vidux_dispatches_http_smoke(self):
        result = subprocess.run(
            [
                str(ROOT / "bin" / "vidux"),
                "http-smoke",
                "--json",
                "--timeout",
                "0.3",
                self.url("/fast"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["results"][0]["verdict"], "pass")

    def test_bin_vidux_help_documents_http_smoke(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "vidux"), "help", "http-smoke"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warn_partial", result.stdout)
        self.assertIn("fail_budget", result.stdout)
        self.assertIn("top-level ok follows hard-fail exit status", result.stdout)
        self.assertIn("strict_ok is false", result.stdout)
        self.assertIn("warning_only", result.stdout)
        self.assertIn("--timeout must be greater than 0", result.stdout)
        self.assertIn("--max-sample-bytes must be 0 or greater", result.stdout)

    def test_completion_scripts_document_http_smoke(self):
        outputs = {}
        for shell in ("bash", "zsh", "fish"):
            result = subprocess.run(
                [str(ROOT / "bin" / "vidux"), "completion", shell],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs[shell] = result.stdout
            self.assertIn("http-smoke", result.stdout)

        combined = "\n".join(outputs.values())
        for phrase in ["--url", "--timeout", "--max-sample-bytes", "--json"]:
            self.assertIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
