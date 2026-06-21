import importlib.util
import http.client
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "vidux_browser_server", ROOT / "browser" / "server.py"
)
browser_server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(browser_server)


class BrowserLocalPlanNoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.plan_dir = self.dev_root / "repo" / "projects" / "demo"
        self.plan_dir.mkdir(parents=True)
        self.plan_path = self.plan_dir / "PLAN.md"
        self.plan_path.write_text(
            "# Demo\n\n## Purpose\nLocal test plan.\n",
            encoding="utf-8",
        )
        browser_server.DEV_ROOT = self.dev_root

    def tearDown(self):
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def test_write_plan_note_creates_inbox_under_open(self):
        ok, path = browser_server.write_plan_note(
            self.plan_path,
            "capture this local-only note",
            source="codex/test",
            agent="codex/moussey",
        )

        self.assertTrue(ok, path)
        inbox = Path(path)
        text = inbox.read_text(encoding="utf-8")
        self.assertIn("## Open", text)
        self.assertIn("## Processed", text)
        self.assertIn("- Source: codex/test", text)
        self.assertIn("- Agent: codex/moussey", text)
        self.assertIn("> capture this local-only note", text)
        self.assertLess(text.index("capture this"), text.index("## Processed"))

    def test_write_plan_note_preserves_existing_processed_section(self):
        inbox = self.plan_dir / "INBOX.md"
        inbox.write_text(
            "## Open\n\n## Processed\n\n### Old\n",
            encoding="utf-8",
        )

        ok, msg = browser_server.write_plan_note(self.plan_path, "new note")

        self.assertTrue(ok, msg)
        text = inbox.read_text(encoding="utf-8")
        self.assertEqual(text.count("## Open"), 1)
        self.assertIn("> new note", text)
        self.assertLess(text.index("> new note"), text.index("## Processed"))
        self.assertIn("### Old", text)

    def test_resolve_plan_note_target_requires_plan_md_under_dev_root(self):
        evidence = self.plan_dir / "evidence.md"
        evidence.write_text("nope", encoding="utf-8")
        outside = Path(self.tmp.name).parent / "outside-plan.md"
        outside.write_text("# Outside", encoding="utf-8")

        self.assertEqual(
            browser_server.resolve_plan_note_target(str(self.plan_path)),
            self.plan_path.resolve(),
        )
        self.assertIsNone(browser_server.resolve_plan_note_target(str(evidence)))
        self.assertIsNone(browser_server.resolve_plan_note_target(str(outside)))

    def test_loopback_guard(self):
        self.assertTrue(browser_server.is_loopback_host("127.0.0.1"))
        self.assertTrue(browser_server.is_loopback_host("::1"))
        self.assertFalse(browser_server.is_loopback_host("192.0.2.55"))


class BrowserWriteEndpointHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.artifacts_dir = self.dev_root / ".artifacts"
        self.comments_file = self.dev_root / ".vidux-browser-comments.jsonl"
        self.original_dev_root = browser_server.DEV_ROOT
        self.original_artifacts_dir = browser_server.ARTIFACTS_DIR
        self.original_comments_file = browser_server.COMMENTS_FILE
        browser_server.DEV_ROOT = self.dev_root
        browser_server.ARTIFACTS_DIR = self.artifacts_dir
        browser_server.COMMENTS_FILE = self.comments_file

        self.plan_dir = self.dev_root / "repo" / "projects" / "demo"
        self.plan_dir.mkdir(parents=True)
        self.plan_path = self.plan_dir / "PLAN.md"
        self.plan_path.write_text("# Demo\n\n## Purpose\nTest.\n", encoding="utf-8")

        self.httpd = browser_server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            browser_server.Handler,
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()
        browser_server.DEV_ROOT = self.original_dev_root
        browser_server.ARTIFACTS_DIR = self.original_artifacts_dir
        browser_server.COMMENTS_FILE = self.original_comments_file
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def post(self, path: str, payload: dict | str, headers: dict[str, str]):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", path, body=body.encode("utf-8"), headers=headers)
        res = conn.getresponse()
        text = res.read().decode("utf-8", errors="replace")
        conn.close()
        return res.status, text

    def get(self, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        res = conn.getresponse()
        text = res.read().decode("utf-8", errors="replace")
        conn.close()
        return res.status, text

    def head(self, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("HEAD", path)
        res = conn.getresponse()
        body = res.read()
        headers = dict(res.getheaders())
        status = res.status
        conn.close()
        return status, headers, body

    def json_headers(self, **extra: str) -> dict[str, str]:
        return {"Content-Type": "application/json", **extra}

    def test_head_health_returns_headers_without_body(self):
        status, headers, body = self.head("/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_head_static_returns_headers_without_body(self):
        status, headers, body = self.head("/")

        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_head_missing_route_keeps_status_without_body(self):
        status, headers, body = self.head("/nope")

        self.assertEqual(status, 404)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_artifact_post_accepts_same_origin_json(self):
        status, text = self.post(
            "/api/artifact",
            {"slug": "safe-artifact", "html": "<h1>Safe</h1>"},
            self.json_headers(Origin=self.origin()),
        )

        self.assertEqual(status, 200, text)
        self.assertTrue((self.artifacts_dir / "safe-artifact.html").is_file())

    def test_artifact_post_rejects_lan_client(self):
        sent = []
        handler = object.__new__(browser_server.Handler)
        handler.client_address = ("192.0.2.55", 49152)
        handler.headers = {
            "Content-Type": "application/json",
            "Host": f"127.0.0.1:{self.port}",
            "Origin": self.origin(),
        }
        handler._send = lambda code, msg: sent.append((code, msg))

        self.assertFalse(browser_server.Handler._require_json_write(handler))
        self.assertEqual(sent, [(403, "write endpoints require loopback client")])

    def test_artifact_post_rejects_simple_content_type(self):
        status, text = self.post(
            "/api/artifact",
            json.dumps({"slug": "simple-body", "html": "<h1>Nope</h1>"}),
            {"Content-Type": "text/plain", "Origin": self.origin()},
        )

        self.assertEqual(status, 415, text)
        self.assertFalse((self.artifacts_dir / "simple-body.html").exists())

    def test_artifact_post_rejects_cross_origin(self):
        status, text = self.post(
            "/api/artifact",
            {"slug": "evil-origin", "html": "<h1>Nope</h1>"},
            self.json_headers(Origin="http://evil.example"),
        )

        self.assertEqual(status, 403, text)
        self.assertFalse((self.artifacts_dir / "evil-origin.html").exists())

    def test_plan_note_post_accepts_same_origin_json(self):
        status, text = self.post(
            "/api/local-plan-note",
            {"plan_path": str(self.plan_path), "note": "safe note"},
            self.json_headers(Origin=self.origin()),
        )

        self.assertEqual(status, 200, text)
        self.assertIn("safe note", (self.plan_dir / "INBOX.md").read_text(encoding="utf-8"))

    def test_plan_note_post_rejects_cross_origin(self):
        status, text = self.post(
            "/api/local-plan-note",
            {"plan_path": str(self.plan_path), "note": "evil note"},
            self.json_headers(Origin="http://evil.example"),
        )

        self.assertEqual(status, 403, text)
        self.assertFalse((self.plan_dir / "INBOX.md").exists())

    def test_comments_post_accepts_same_origin_json_for_plan_without_inbox_write(self):
        status, text = self.post(
            "/api/comments",
            {
                "target_path": str(self.plan_path),
                "author": "Viewer",
                "body": "This needs a quick annotation.",
            },
            self.json_headers(Origin=self.origin()),
        )

        self.assertEqual(status, 200, text)
        self.assertFalse((self.plan_dir / "INBOX.md").exists())
        status, text = self.get(f"/api/comments?path={self.plan_path}")
        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        self.assertEqual(payload["target_kind"], "plan")
        self.assertEqual(payload["comments"][0]["author"], "Viewer")
        self.assertEqual(payload["comments"][0]["body"], "This needs a quick annotation.")

    def test_comments_post_persists_clean_anchor_metadata(self):
        status, text = self.post(
            "/api/comments",
            {
                "target_path": str(self.plan_path),
                "author": "Viewer",
                "body": "Anchored note.",
                "anchor": {
                    "selector": '[data-vidux-anchor="a3"]',
                    "label": "Tasks / - [pending] Demo task",
                    "excerpt": "- [pending] Demo task",
                    "tag": "li",
                    "kind": "rendered",
                    "index": 3,
                    "ignored": "nope",
                },
            },
            self.json_headers(Origin=self.origin()),
        )

        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        anchor = payload["comment"]["anchor"]
        self.assertEqual(anchor["version"], 1)
        self.assertEqual(anchor["selector"], '[data-vidux-anchor="a3"]')
        self.assertEqual(anchor["label"], "Tasks / - [pending] Demo task")
        self.assertEqual(anchor["excerpt"], "- [pending] Demo task")
        self.assertEqual(anchor["tag"], "li")
        self.assertEqual(anchor["kind"], "rendered")
        self.assertEqual(anchor["index"], 3)
        self.assertNotIn("ignored", anchor)

    def test_comments_post_accepts_artifact_target(self):
        self.artifacts_dir.mkdir(parents=True)
        artifact = self.artifacts_dir / "demo.html"
        artifact.write_text("<h1>Demo</h1>", encoding="utf-8")

        status, text = self.post(
            "/api/comments",
            {
                "target_path": str(artifact),
                "author": "viewer/lan",
                "body": "Artifact comment.",
            },
            self.json_headers(Origin=self.origin()),
        )

        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        self.assertEqual(payload["comment"]["target_kind"], "artifact")
        status, text = self.get(f"/api/comments?path={artifact}")
        self.assertEqual(status, 200, text)
        self.assertIn("Artifact comment.", text)

    def test_comments_post_accepts_evidence_markdown_target(self):
        evidence_dir = self.plan_dir / "evidence"
        evidence_dir.mkdir()
        evidence = evidence_dir / "2026-05-24-browser-proof.md"
        evidence.write_text("# Browser proof\n\nLooks good.\n", encoding="utf-8")

        status, text = self.post(
            "/api/comments",
            {
                "target_path": str(evidence),
                "author": "Viewer",
                "body": "Evidence annotation.",
                "anchor": {"selector": '[data-vidux-anchor="a1"]', "label": "Content / Browser proof"},
            },
            self.json_headers(Origin=self.origin()),
        )

        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        self.assertEqual(payload["comment"]["target_kind"], "plan")
        self.assertEqual(payload["comment"]["target_path"], str(evidence.resolve()))
        status, text = self.get(f"/api/comments?path={evidence}")
        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        self.assertEqual(payload["comments"][0]["body"], "Evidence annotation.")
        self.assertEqual(payload["comments"][0]["anchor"]["label"], "Content / Browser proof")

    def test_comments_post_rejects_cross_origin(self):
        status, text = self.post(
            "/api/comments",
            {"target_path": str(self.plan_path), "author": "bad", "body": "evil note"},
            self.json_headers(Origin="http://evil.example"),
        )

        self.assertEqual(status, 403, text)
        self.assertFalse(self.comments_file.exists())

    def test_comments_post_rejects_simple_content_type(self):
        status, text = self.post(
            "/api/comments",
            json.dumps({"target_path": str(self.plan_path), "author": "bad", "body": "evil note"}),
            {"Content-Type": "text/plain", "Origin": self.origin()},
        )

        self.assertEqual(status, 415, text)
        self.assertFalse(self.comments_file.exists())

    def test_comments_post_requires_origin_or_referer(self):
        status, text = self.post(
            "/api/comments",
            {"target_path": str(self.plan_path), "author": "bad", "body": "no origin"},
            self.json_headers(),
        )

        self.assertEqual(status, 403, text)
        self.assertFalse(self.comments_file.exists())

    def test_comments_browser_json_guard_allows_lan_same_origin(self):
        sent = []
        handler = object.__new__(browser_server.Handler)
        handler.client_address = ("192.0.2.55", 49152)
        handler.headers = {
            "Content-Type": "application/json",
            "Host": f"127.0.0.1:{self.port}",
            "Origin": self.origin(),
        }
        handler._send = lambda code, msg: sent.append((code, msg))

        self.assertTrue(browser_server.Handler._require_browser_json(handler, require_origin=True))
        self.assertEqual(sent, [])

    def test_api_file_returns_404_for_allowed_missing_file(self):
        missing = self.plan_dir / "INBOX.md"

        status, text = self.get(f"/api/file?path={quote(str(missing), safe='')}")

        self.assertEqual(status, 404, text)
        self.assertEqual(text, "file missing: INBOX.md")

    def test_api_file_still_rejects_forbidden_missing_file(self):
        forbidden = self.plan_dir / ".env"

        status, text = self.get(f"/api/file?path={quote(str(forbidden), safe='')}")

        self.assertEqual(status, 403, text)
        self.assertEqual(text, "forbidden")


class BrowserArtifactBaseCssTests(unittest.TestCase):
    def test_shared_artifact_base_css_contract(self):
        css_path = ROOT / "browser" / "static" / "artifact-base.css"

        self.assertTrue(css_path.is_file())
        css = css_path.read_text(encoding="utf-8")

        self.assertIn("@media (prefers-color-scheme: dark)", css)
        self.assertIn("color-scheme: light dark", css)
        self.assertIn("--paper:", css)
        self.assertIn("--bg:", css)
        self.assertIn("--ink:", css)
        self.assertIn("--shadow:", css)
        self.assertIn(".hero", css)

    def test_local_snowcubes_artifacts_use_shared_base_when_present(self):
        artifacts = sorted((ROOT / "browser" / "artifacts").glob("snowcubes-*.html"))
        if not artifacts:
            self.skipTest("Snowcubes artifacts are ignored local runtime artifacts")

        for artifact in artifacts:
            html = artifact.read_text(encoding="utf-8")
            self.assertEqual(
                html.count("artifact-base.css"),
                1,
                f"{artifact.name} should link the shared artifact stylesheet once",
            )
            self.assertIn(
                'href="../static/artifact-base.css"',
                html,
                f"{artifact.name} should use the offline-friendly relative stylesheet link",
            )
            self.assertNotIn(
                "prefers-color-scheme",
                html,
                f"{artifact.name} should not carry a copied dark-mode block",
            )


class BrowserViduxTruthTests(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.original_runner = browser_server.run_truth_command

        def fake_runner(args, *, timeout):
            self.commands.append(list(args))
            joined = " ".join(str(part) for part in args)
            if "vidux-config.py" in joined:
                stdout = json.dumps({
                    "status": "ok",
                    "source": "example",
                    "path": "/repo/vidux.config.example.json",
                    "live_config_present": False,
                    "using_example": True,
                    "issues": [],
                    "plan_store": {"mode": "local", "path_exists": True},
                })
            elif "vidux-doctor.sh" in joined:
                stdout = json.dumps({
                    "pass": 13,
                    "total": 14,
                    "checks": [
                        {"id": "worktree_count", "status": "pass"},
                        {"id": "orphan_automations", "status": "warn"},
                        {
                            "id": "system_memory_pressure",
                            "status": "pass",
                            "available": True,
                            "memory_pressure_free_pct": 64,
                            "memory_free_pct": 64,
                            "min_memory_free_pct": 15,
                            "memory_pct_source": "memory_pressure -Q",
                            "vm_free_mb": 91.0,
                            "vm_speculative_mb": 41.5,
                            "free_mb": 91.0,
                            "speculative_mb": 41.5,
                            "vm_pages_source": "vm_stat",
                            "total_bytes": 68719476736,
                        },
                    ],
                })
            elif "vidux_signpost.py" in joined and "trace" in joined:
                stdout = json.dumps({
                    "total_events": 4,
                    "events": [
                        {
                            "run_id": "run-browser-truth",
                            "feature": "hook",
                            "action": "beforeTask",
                            "runtime": "codex",
                            "called": "scripts/vidux-doctor.sh --json",
                            "metadata": {"phase": "pre"},
                        },
                        {
                            "run_id": "run-browser-truth",
                            "feature": "subagent",
                            "action": "spawn",
                            "runtime": "claude",
                            "called": "claude spawned-worker",
                            "metadata": {"phase": "during"},
                        },
                        {
                            "run_id": "run-browser-truth",
                            "feature": "task",
                            "action": "verify",
                            "runtime": "cursor",
                            "called": "cursor worker verify",
                            "metadata": {"phase": "during"},
                        },
                        {
                            "run_id": "run-browser-truth",
                            "feature": "hook",
                            "action": "afterTask",
                            "runtime": "codex",
                            "called": "vidux checkpoint",
                            "metadata": {"phase": "post"},
                        },
                    ],
                    "log_path": "/Users/test/.vidux/signposts.jsonl",
                })
            elif "vidux_signpost.py" in joined:
                stdout = json.dumps({
                    "total_events": 4,
                    "features": {"hook.beforeTask": {"count": 1}},
                    "log_path": "/Users/test/.vidux/signposts.jsonl",
                })
            else:
                stdout = "{}"
            return subprocess.CompletedProcess(args, 0, stdout, "")

        browser_server.run_truth_command = fake_runner
        browser_server.clear_vidux_truth_cache()
        self.httpd = browser_server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            browser_server.Handler,
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()
        browser_server.run_truth_command = self.original_runner
        browser_server.clear_vidux_truth_cache()

    def get(self, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        res = conn.getresponse()
        text = res.read().decode("utf-8", errors="replace")
        conn.close()
        return res.status, text

    def test_vidux_truth_cached_payload_can_warm_without_blocking(self):
        payload = browser_server.vidux_truth_cached_payload(background=False)

        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["browser_runs_install_doctor"])
        self.assertFalse(payload["browser_runs_runtime_fix"])
        self.assertEqual(payload["cache"]["status"], "warming")
        self.assertFalse(payload["cache"]["refreshing"])
        self.assertEqual(payload["config"]["status"], "warming")
        self.assertEqual(payload["runtime_doctor"]["status"], "warming")
        self.assertEqual(self.commands, [])

    def test_vidux_truth_endpoint_is_read_only_and_splits_doctors(self):
        status, text = self.get("/api/vidux/truth?refresh=sync")

        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["browser_runs_install_doctor"])
        self.assertFalse(payload["browser_runs_runtime_fix"])
        self.assertEqual(payload["cache"]["status"], "fresh")
        self.assertEqual(payload["config"]["source"], "example")
        self.assertEqual(payload["install_doctor"]["browser_status"], "not_run")
        self.assertFalse(payload["install_doctor"]["pre_hook_safe"])
        self.assertEqual(payload["runtime_doctor"]["command"], "scripts/vidux-doctor.sh --json")
        self.assertTrue(payload["runtime_doctor"]["pre_hook_safe"])
        self.assertEqual(payload["runtime_doctor"]["status"], "warn")
        self.assertEqual(payload["runtime_doctor"]["warnings"], ["orphan_automations"])
        self.assertEqual(payload["runtime_doctor"]["system_memory"]["memory_pressure_free_pct"], 64)
        self.assertEqual(payload["runtime_doctor"]["system_memory"]["memory_pct_source"], "memory_pressure -Q")
        self.assertEqual(payload["runtime_doctor"]["system_memory"]["vm_pages_source"], "vm_stat")
        self.assertEqual(payload["runtime_doctor"]["system_memory"]["free_mb"], 91.0)
        self.assertEqual(payload["signposts"]["total_events"], 4)
        self.assertEqual(payload["signposts"]["latest_run"]["run_id"], "run-browser-truth")
        self.assertEqual(
            payload["signposts"]["latest_run"]["call_stack"],
            "codex > claude > cursor > codex",
        )
        self.assertTrue(payload["signposts"]["latest_run"]["complete_lifecycle"])

        command_text = "\n".join(" ".join(str(part) for part in cmd) for cmd in self.commands)
        self.assertIn("vidux-config.py check --json", command_text)
        self.assertIn("vidux-doctor.sh --json", command_text)
        self.assertIn("vidux_signpost.py summary --json", command_text)
        self.assertIn("vidux_signpost.py trace --limit 12 --json", command_text)
        self.assertNotIn("vidux-doctor-cli.sh", command_text)
        self.assertNotIn("vidux doctor", command_text)
        self.assertNotIn("--fix", command_text)

    def test_health_payload_identifies_repo_root_for_launcher_reuse(self):
        status, text = self.get("/api/health")

        self.assertEqual(status, 200, text)
        payload = json.loads(text)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["repo_root"], str(browser_server.VIDUX_ROOT))
        self.assertEqual(payload["dev_root"], str(browser_server.DEV_ROOT))
        self.assertEqual(payload["server_path"], str(browser_server.SERVER_FILE))
        self.assertEqual(payload["server_mtime_ns"], browser_server.SERVER_MTIME_NS)
        self.assertIn("port", payload)

    def test_vidux_truth_static_contract(self):
        server = (ROOT / "browser" / "server.py").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('route == "/api/vidux/truth"', server)
        self.assertIn("vidux_truth_cached_payload", server)
        self.assertIn('refresh == "sync"', server)
        self.assertIn("browser_runs_install_doctor", server)
        self.assertIn("browser_runs_runtime_fix", server)
        self.assertIn('"vidux-doctor.sh"), "--json"', server)
        self.assertIn('fetch("/api/vidux/truth")', app)
        self.assertIn("function renderOpsTruth", app)
        self.assertIn("cache.refreshing", app)
        self.assertIn("install doctor not run here", app)
        self.assertIn("scripts/vidux-doctor.sh --json", app)
        self.assertIn("runtime.system_memory", app)
        self.assertIn("memory_pressure", app)
        self.assertIn("vm_stat", app)
        self.assertIn("signposts.latest_run", app)
        self.assertIn("function renderMarkdownBody", app)
        self.assertIn("markdown render failed", app)
        self.assertIn("markdown-source-fallback", style)
        self.assertIn('const SESSION_TAB = "Sessions"', app)
        self.assertIn("function renderSessionPanel", app)
        self.assertIn("No Claude session found", app)
        self.assertIn(".session-panel", style)
        self.assertIn(".session-turn", style)
        self.assertIn("complete_lifecycle", app)
        self.assertIn("function refreshOpsTruth", app)
        for klass in [
            "ops-truth",
            "ops-truth-grid",
            "ops-truth-item",
            "ops-chip",
            "ops-chip.is-warn",
        ]:
            self.assertIn(klass, style)


class BrowserResponseWriteTests(unittest.TestCase):
    def test_response_helpers_swallow_client_disconnect_writes(self):
        class BrokenWriter:
            def write(self, body):
                raise BrokenPipeError("client closed")

        handler = object.__new__(browser_server.Handler)
        handler.wfile = BrokenWriter()
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None

        self.assertFalse(browser_server.Handler._write_body(handler, b"hello"))
        browser_server.Handler._json(handler, {"ok": True})
        browser_server.Handler._send_with_type(handler, b"body", "text/plain")
        browser_server.Handler._send_text(handler, "markdown")
        browser_server.Handler._send(handler, 404, "missing")

    def test_head_only_response_helpers_skip_body_write(self):
        writes = []
        handler = object.__new__(browser_server.Handler)
        handler._head_only = True
        handler.wfile = type("Writer", (), {"write": lambda _self, body: writes.append(body)})()
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None

        self.assertTrue(browser_server.Handler._write_body(handler, b"hello"))
        browser_server.Handler._json(handler, {"ok": True})
        browser_server.Handler._send_with_type(handler, b"body", "text/plain")
        browser_server.Handler._send_text(handler, "markdown")
        browser_server.Handler._send(handler, 404, "missing")

        self.assertEqual(writes, [])


class BrowserPlanDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.original_claude_projects_dir = browser_server.CLAUDE_PROJECTS_DIR
        browser_server.DEV_ROOT = self.dev_root
        browser_server.CLAUDE_PROJECTS_DIR = self.dev_root / ".claude" / "projects"

    def tearDown(self):
        browser_server.CLAUDE_PROJECTS_DIR = self.original_claude_projects_dir
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def write_plan(self, repo: str, rel: str, title: str = "Demo") -> Path:
        path = self.dev_root / repo / rel / "PLAN.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            f"# {title}\n\n## Purpose\nLocal test plan.\n",
            encoding="utf-8",
        )
        return path

    def test_repo_aliases_dedup_prefers_canonical_checkout(self):
        """When env `VIDUX_REPO_ALIASES` maps an old checkout name to a
        canonical one, discover_plans() should keep only the canonical copy
        when the same plan path exists in both. This used to be hardcoded
        to `{"mobiledevcombine-web": "strongyes-web"}` per Leo's fleet;
        it's now generic — the test injects its own alias map to validate
        the dedup mechanism."""
        canonical = self.write_plan("strongyes-web", "vidux/game-plan", "Game Plan")
        self.write_plan("mobiledevcombine-web", "vidux/game-plan", "Old Game Plan")

        original = browser_server.LEGACY_REPO_ALIASES
        browser_server.LEGACY_REPO_ALIASES = {"mobiledevcombine-web": "strongyes-web"}
        try:
            plans = browser_server.discover_plans()
        finally:
            browser_server.LEGACY_REPO_ALIASES = original

        game_plans = [
            plan
            for plan in plans
            if Path(plan["rel"]).parts[1:] == ("vidux", "game-plan", "PLAN.md")
        ]

        self.assertEqual(len(game_plans), 1)
        self.assertEqual(game_plans[0]["repo"], "strongyes-web")
        self.assertEqual(Path(game_plans[0]["path"]), canonical.resolve())

    def test_discover_plans_handles_missing_evidence_directory(self):
        plan_path = self.write_plan("demo-repo", "projects/no-evidence", "No Evidence")

        plans = browser_server.discover_plans()
        plan = next(p for p in plans if Path(p["path"]) == plan_path.resolve())

        self.assertEqual(plan["evidence"], [])

    def test_discover_evidence_sorts_dated_files_and_keeps_odd_markdown_names(self):
        plan_path = self.write_plan("demo-repo", "projects/receipts", "Receipts")
        evidence_dir = plan_path.parent / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "notes without date.md").write_text("# Notes\n", encoding="utf-8")
        (evidence_dir / "2026-05-24-browser-proof.md").write_text("# Latest\n", encoding="utf-8")
        (evidence_dir / "2026-05-01-research.md").write_text("# Research\n", encoding="utf-8")
        (evidence_dir / "2026-05-02-screenshot.png").write_text("not markdown", encoding="utf-8")
        (evidence_dir / "nested.md").mkdir()

        plans = browser_server.discover_plans()
        plan = next(p for p in plans if Path(p["path"]) == plan_path.resolve())

        names = [item["name"] for item in plan["evidence"]]
        self.assertEqual(
            names,
            [
                "2026-05-01-research.md",
                "2026-05-24-browser-proof.md",
                "notes without date.md",
            ],
        )
        labels = [item["label"] for item in plan["evidence"]]
        self.assertEqual(labels[0], "2026-05-01 - research")
        self.assertEqual(labels[1], "2026-05-24 - browser proof")
        self.assertEqual(labels[2], "notes without date")
        self.assertTrue(plan["evidence"][0]["is_dated"])
        self.assertFalse(plan["evidence"][2]["is_dated"])

    def test_plan_list_payload_uses_child_rels_without_nested_children(self):
        parent = self.write_plan("demo-repo", "projects/parent", "Parent")
        child_dir = parent.parent / "child"
        child_dir.mkdir()
        child_rel = "demo-repo/projects/parent/child/PLAN.md"
        (child_dir / "PLAN.md").write_text(
            "# Child\n\n"
            "> Parent: ../PLAN.md\n\n"
            "## Purpose\nChild plan.\n\n"
            "## Tasks\n- [completed] child task\n",
            encoding="utf-8",
        )

        plans = browser_server.discover_plans()
        payload = browser_server.plan_list_payload(plans)
        parent_item = next(item for item in payload if item["rel"] == "demo-repo/projects/parent/PLAN.md")

        self.assertNotIn("children", parent_item)
        self.assertEqual(parent_item["child_rels"], [child_rel])

    def test_build_fleet_summary_sums_completion_and_active_eta(self):
        plan_a = self.write_plan("demo-repo", "projects/eta-a", "ETA A")
        plan_a.write_text(
            "# ETA A\n\n"
            "## Tasks\n"
            "- [completed] done already [ETA: 99h]\n"
            "- [pending] next up [ETA: 1.25h]\n"
            "- [in_progress] active now [ETA: 2h]\n"
            "- [in_review] review lane [ETA: 0.75h]\n"
            "- [blocked] blocked elsewhere [ETA: 6h]\n",
            encoding="utf-8",
        )
        plan_b = self.write_plan("other-repo", "projects/eta-b", "ETA B")
        plan_b.write_text(
            "# ETA B\n\n"
            "## Tasks\n"
            "- [pending] untagged active row\n"
            "- [completed] shipped row\n",
            encoding="utf-8",
        )

        summary = browser_server.build_fleet_summary(browser_server.discover_plans())

        self.assertEqual(summary["plans"], 2)
        self.assertEqual(summary["repos"], 2)
        self.assertEqual(summary["tasks_completed"], 2)
        self.assertEqual(summary["tasks_total"], 7)
        self.assertEqual(summary["completion_pct"], 29)
        self.assertEqual(summary["eta_remaining_hours"], 4.0)
        self.assertEqual(summary["eta_remaining_label"], "4h remaining")
        self.assertEqual(summary["eta_tagged"], 3)
        self.assertEqual(summary["eta_eligible"], 4)

    def test_plan_payload_includes_latest_claude_session_summary(self):
        plan_path = self.write_plan("demo-repo", "projects/session", "Session")
        session_dir = (
            browser_server.CLAUDE_PROJECTS_DIR
            / browser_server.claude_project_slug(self.dev_root / "demo-repo")
        )
        session_dir.mkdir(parents=True)
        old_session = session_dir / "old.jsonl"
        old_session.write_text(
            json.dumps({
                "type": "user",
                "sessionId": "old-session",
                "message": {"role": "user", "content": "old session text"},
            }) + "\n",
            encoding="utf-8",
        )
        latest_session = session_dir / "latest.jsonl"
        rows = [
            {"type": "last-prompt", "sessionId": "latest-session"},
            {
                "type": "user",
                "timestamp": "2026-06-03T08:00:00Z",
                "sessionId": "latest-session",
                "message": {"role": "user", "content": [{"type": "text", "text": "first should drop"}]},
            },
            {
                "type": "assistant",
                "timestamp": "2026-06-03T08:01:00Z",
                "sessionId": "latest-session",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "second kept"}]},
            },
            {
                "type": "user",
                "timestamp": "2026-06-03T08:02:00Z",
                "sessionId": "latest-session",
                "message": {"role": "user", "content": "third kept"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-06-03T08:03:00Z",
                "sessionId": "latest-session",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "name": "ignored"}, {"type": "text", "text": "fourth kept"}],
                },
            },
            {
                "type": "user",
                "timestamp": "2026-06-03T08:04:00Z",
                "sessionId": "latest-session",
                "message": {"role": "user", "content": [{"type": "text", "text": "fifth kept"}]},
            },
            "{not-json",
            {
                "type": "assistant",
                "timestamp": "2026-06-03T08:05:00Z",
                "sessionId": "latest-session",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "sixth kept"}]},
            },
        ]
        latest_session.write_text(
            "\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        os.utime(old_session, (1_000, 1_000))
        os.utime(latest_session, (2_000, 2_000))

        plans = browser_server.plan_list_payload(browser_server.discover_plans())
        plan = next(p for p in plans if Path(p["path"]) == plan_path.resolve())
        session = plan["session"]

        self.assertTrue(session["available"])
        self.assertEqual(session["status"], "ok")
        self.assertEqual(session["file"], "latest.jsonl")
        self.assertEqual(session["session_id"], "latest-session")
        self.assertEqual(session["turns_seen"], 6)
        self.assertEqual(session["invalid_lines"], 1)
        self.assertEqual(len(session["turns"]), 5)
        self.assertEqual([turn["role"] for turn in session["turns"]], [
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
        ])
        joined = " ".join(turn["text"] for turn in session["turns"])
        self.assertNotIn("first should drop", joined)
        self.assertNotIn("old session text", joined)
        self.assertIn("sixth kept", joined)

    def test_plan_payload_reports_missing_claude_session(self):
        plan_path = self.write_plan("demo-repo", "projects/no-session", "No Session")

        plans = browser_server.plan_list_payload(browser_server.discover_plans())
        plan = next(p for p in plans if Path(p["path"]) == plan_path.resolve())
        session = plan["session"]

        self.assertFalse(session["available"])
        self.assertEqual(session["status"], "missing")
        self.assertEqual(session["turns"], [])
        self.assertIn(".claude/projects", session["project_dir"])

    def test_discover_plans_cached_reuses_recent_scan(self):
        self.write_plan("demo-repo", "projects/cache", "Cache")
        original_discover = browser_server.discover_plans
        original_ttl = browser_server.PLANS_CACHE_TTL_SECONDS
        calls = []

        def fake_discover():
            calls.append("scan")
            return original_discover()

        browser_server.PLANS_CACHE_TTL_SECONDS = 60
        browser_server.discover_plans = fake_discover
        browser_server.clear_plans_cache()
        try:
            first = browser_server.discover_plans_cached()
            second = browser_server.discover_plans_cached()
        finally:
            browser_server.discover_plans = original_discover
            browser_server.PLANS_CACHE_TTL_SECONDS = original_ttl
            browser_server.clear_plans_cache()

        self.assertEqual(first, second)
        self.assertEqual(calls, ["scan"])


class BrowserDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.original_dev_root = browser_server.DEV_ROOT
        self.original_claude_projects_dir = browser_server.CLAUDE_PROJECTS_DIR
        browser_server.DEV_ROOT = self.dev_root
        browser_server.CLAUDE_PROJECTS_DIR = self.dev_root / ".claude" / "projects"

    def tearDown(self):
        browser_server.DEV_ROOT = self.original_dev_root
        browser_server.CLAUDE_PROJECTS_DIR = self.original_claude_projects_dir
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def test_dashboard_extracts_bounded_tasks_and_open_sibling_entries(self):
        plan_dir = self.dev_root / "repo" / "projects" / "dashboard"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "PLAN.md"
        plan_path.write_text(
            "# Dashboard\n\n"
            "## Purpose\nFleet queue.\n\n"
            "## Tasks\n"
            "- [in_progress] Ship cross-plan dashboard [ETA: 1h]\n"
            "- [blocked] Wait for external proof [Blocker: real thing]\n"
            "- [pending] Ignore pending row\n",
            encoding="utf-8",
        )
        (plan_dir / "INBOX.md").write_text(
            "# Inbox\n\n"
            "## Open\n\n"
            "### First open inbox item\n"
            "- Second open inbox item\n\n"
            "## Processed\n\n"
            "- Old processed item\n",
            encoding="utf-8",
        )
        (plan_dir / "ASK-LEO.md").write_text(
            "# Ask Leo\n\n"
            "- Decide whether dashboard ships as default pane\n",
            encoding="utf-8",
        )

        plans = browser_server.discover_plans()
        payload = browser_server.plan_list_payload(plans)
        plan_payload = next(item for item in payload if item["rel"] == "repo/projects/dashboard/PLAN.md")
        dashboard = browser_server.build_dashboard(plans)

        self.assertNotIn("dashboard_tasks", plan_payload)
        self.assertNotIn("dashboard_inbox_entries", plan_payload)
        self.assertNotIn("dashboard_ask_leo_entries", plan_payload)
        self.assertEqual(dashboard["plans_scanned"], 1)
        self.assertEqual(dashboard["repos"], 1)

        in_progress = dashboard["categories"]["in_progress"]
        blocked = dashboard["categories"]["blocked"]
        inbox = dashboard["categories"]["inbox"]
        ask_leo = dashboard["categories"]["ask_leo"]

        self.assertEqual(in_progress["total"], 1)
        self.assertEqual(blocked["total"], 1)
        self.assertEqual(inbox["total"], 2)
        self.assertEqual(ask_leo["total"], 1)
        self.assertFalse(inbox["truncated"])

        task_item = in_progress["items"][0]
        self.assertEqual(task_item["kind"], "task")
        self.assertEqual(task_item["tab"], "PLAN.md")
        self.assertEqual(task_item["status"], "in_progress")
        self.assertEqual(task_item["source_rel"], "repo/projects/dashboard/PLAN.md")
        self.assertGreater(task_item["line"], 0)
        self.assertIn("Ship cross-plan dashboard", task_item["label"])
        self.assertNotIn("[ETA:", task_item["label"])

        inbox_labels = [item["label"] for item in inbox["items"]]
        self.assertEqual(inbox_labels, ["First open inbox item", "Second open inbox item"])
        self.assertNotIn("Old processed item", " ".join(inbox_labels))
        self.assertEqual(inbox["items"][0]["tab"], "INBOX.md")
        self.assertEqual(ask_leo["items"][0]["tab"], "ASK-LEO.md")

    def test_dashboard_parses_open_ask_leo_question_blocks(self):
        plan_dir = self.dev_root / "repo" / "projects" / "asks"
        plan_dir.mkdir(parents=True)
        (plan_dir / "PLAN.md").write_text("# Asks\n\n## Tasks\n", encoding="utf-8")
        (plan_dir / "ASK-LEO.md").write_text(
            "# ASK-LEO\n\n"
            "## Q1 — resolved question\n"
            "Opened: 2026-06-03\n"
            "Resolved: Leo decided no.\n"
            "Status: resolved\n\n"
            "## Q2 — open explicit question\n"
            "Opened: 2026-06-03\n"
            "Status: open\n\n"
            "## Q3 — implicit open question\n"
            "Opened: 2026-06-03\n",
            encoding="utf-8",
        )

        dashboard = browser_server.build_dashboard(browser_server.discover_plans())
        ask_leo = dashboard["categories"]["ask_leo"]
        labels = [item["label"] for item in ask_leo["items"]]

        self.assertEqual(ask_leo["total"], 2)
        self.assertEqual(labels, ["Q2 — open explicit question", "Q3 — implicit open question"])
        self.assertTrue(all(item["tab"] == "ASK-LEO.md" for item in ask_leo["items"]))

    def test_dashboard_limit_marks_truncated_categories(self):
        plan_dir = self.dev_root / "repo" / "projects" / "many"
        plan_dir.mkdir(parents=True)
        (plan_dir / "PLAN.md").write_text(
            "# Many\n\n"
            "## Tasks\n"
            "- [in_progress] first task\n"
            "- [in_progress] second task\n",
            encoding="utf-8",
        )

        dashboard = browser_server.build_dashboard(browser_server.discover_plans(), limit=1)
        bucket = dashboard["categories"]["in_progress"]

        self.assertEqual(bucket["total"], 2)
        self.assertEqual(len(bucket["items"]), 1)
        self.assertTrue(bucket["truncated"])
        self.assertEqual(bucket["limit"], 1)

    def test_dashboard_static_contract(self):
        server = (ROOT / "browser" / "server.py").read_text(encoding="utf-8")
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        sidebar_sort = (ROOT / "browser" / "static" / "sidebar-sort.js").read_text(encoding="utf-8")
        sidebar_filters = (ROOT / "browser" / "static" / "sidebar-filters.js").read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('"summary": build_fleet_summary(plans)', server)
        self.assertIn("def build_fleet_summary", server)
        self.assertIn('"dashboard": build_dashboard(plans)', server)
        self.assertIn("def build_dashboard", server)
        self.assertIn("extract_dashboard_tasks", server)
        self.assertIn("extract_open_entries", server)
        self.assertIn("fleetSummary", app)
        self.assertIn("function topbarFleetSummary", app)
        self.assertIn("remaining", app)
        self.assertIn("function renderDashboardPane", app)
        self.assertIn("function selectDashboard", app)
        self.assertIn('data-kind="dashboard"', app)
        self.assertIn("Cross-plan queue", app)
        self.assertIn('id="sort"', index)
        self.assertIn('/static/sidebar-sort.js', index)
        self.assertIn('/static/sidebar-filters.js', index)
        self.assertIn('/static/annotation-state.js', index)
        self.assertLess(index.index('/static/sidebar-sort.js'), index.index('/static/app.js'))
        self.assertLess(index.index('/static/sidebar-filters.js'), index.index('/static/app.js'))
        self.assertLess(index.index('/static/annotation-state.js'), index.index('/static/app.js'))
        self.assertIn('data-filter-chip="hot"', index)
        self.assertIn('data-filter-chip="tasks"', index)
        self.assertIn('data-filter-chip="eta"', index)
        self.assertIn("ViduxSidebarSort", app)
        self.assertIn("ViduxSidebarFilters", app)
        self.assertIn("function planComparator", sidebar_sort)
        self.assertIn("function repoComparator", sidebar_sort)
        self.assertIn("vidux:sidebar-sort", sidebar_sort)
        self.assertIn("vidux:sidebar-filter-chips", sidebar_filters)
        self.assertIn("function matches", sidebar_filters)
        self.assertIn("function syncButtons", sidebar_filters)
        self.assertIn(".sidebar-controls", style)
        self.assertIn(".sidebar-filter-chips", style)
        self.assertIn(".filter-chip.is-active", style)
        self.assertIn(".progress-row .progress-bar", style)
        self.assertIn(".dashboard-panel", style)
        self.assertIn(".dashboard-item", style)


class BrowserLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.ledger_file = self.dev_root / "activity.jsonl"
        self.original_dev_root = browser_server.DEV_ROOT
        self.original_ledger_file = browser_server.LEDGER_FILE
        self.original_item_limit = browser_server.LEDGER_ITEM_LIMIT
        self.original_scan_limit = browser_server.LEDGER_SCAN_LIMIT
        browser_server.DEV_ROOT = self.dev_root
        browser_server.LEDGER_FILE = self.ledger_file
        browser_server.LEDGER_ITEM_LIMIT = 2
        browser_server.LEDGER_SCAN_LIMIT = 20
        self.plan_dir = self.dev_root / "demo-repo" / "projects" / "ledger"
        self.plan_dir.mkdir(parents=True)
        self.plan_path = self.plan_dir / "PLAN.md"
        self.plan_path.write_text("# Ledger\n\n## Tasks\n", encoding="utf-8")

    def tearDown(self):
        browser_server.DEV_ROOT = self.original_dev_root
        browser_server.LEDGER_FILE = self.original_ledger_file
        browser_server.LEDGER_ITEM_LIMIT = self.original_item_limit
        browser_server.LEDGER_SCAN_LIMIT = self.original_scan_limit
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def write_ledger_rows(self, rows):
        self.ledger_file.write_text(
            "\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

    def test_ledger_payload_matches_plan_rows_first_then_repo_rows(self):
        self.write_ledger_rows([
            "{bad json",
            {
                "ts": "2026-06-03T08:00:00Z",
                "eid": "evt_other",
                "event": "publish",
                "repo": "other-repo",
                "summary": "ignored other repo",
                "plan_path": "projects/ledger/PLAN.md",
            },
            {
                "ts": "2026-06-03T08:01:00Z",
                "eid": "evt_repo",
                "event": "publish",
                "repo": "demo-repo",
                "lane": "demo-lane",
                "task_id": "R1",
                "summary": "repo level proof",
                "plan_path": "PLAN.md",
                "files": ["README.md"],
                "files_claimed": ["README.md"],
            },
            {
                "ts": "2026-06-03T08:02:00Z",
                "eid": "evt_checkpoint",
                "event": "vidux_checkpoint",
                "repo": "demo-repo",
                "lane": "demo-lane",
                "task_id": "T4b",
                "summary": "absolute checkpoint",
                "plan_path": str(self.plan_path),
                "proof": "checkpoint proof",
                "handoff_status": "done",
                "next_agent_resume": "resume from the plan",
                "files": [str(self.plan_path)],
                "files_claimed": [str(self.plan_path)],
            },
            {
                "ts": "2026-06-03T08:03:00Z",
                "eid": "evt_plan",
                "event": "publish",
                "repo": "demo-repo",
                "lane": "demo-lane",
                "task_id": "T4b",
                "summary": "relative plan publish",
                "plan_path": "projects/ledger/PLAN.md",
                "proof": "plan proof",
                "handoff_status": "done",
                "next_agent_resume": "resume again",
                "files": ["projects/ledger/PLAN.md"],
                "files_claimed": ["projects/ledger/PLAN.md"],
            },
            {
                "ts": "2026-06-03T08:04:00Z",
                "event": "vidux_loop_start",
                "repo": "demo-repo",
                "summary": "ignored noisy loop row",
                "files": ["projects/ledger/PLAN.md"],
            },
        ])

        payload = browser_server.ledger_payload_for_plan(self.plan_path)

        self.assertTrue(payload["available"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["invalid_rows"], 1)
        self.assertEqual(payload["plan_total"], 2)
        self.assertEqual(payload["repo_total"], 1)
        self.assertEqual(payload["returned"], 2)
        self.assertTrue(payload["truncated"])
        self.assertEqual([item["scope"] for item in payload["items"]], ["plan", "plan"])
        self.assertEqual([item["eid"] for item in payload["items"]], ["evt_plan", "evt_checkpoint"])
        self.assertEqual(payload["items"][0]["files_claimed_count"], 1)
        self.assertIn("plan proof", payload["items"][0]["proof"])
        self.assertIn("resume again", payload["items"][0]["next_agent_resume"])

    def test_ledger_endpoint_accepts_plan_and_rejects_non_plan_targets(self):
        self.write_ledger_rows([
            {
                "ts": "2026-06-03T08:03:00Z",
                "eid": "evt_plan",
                "event": "publish",
                "repo": "demo-repo",
                "summary": "relative plan publish",
                "plan_path": "projects/ledger/PLAN.md",
            },
        ])
        inbox = self.plan_dir / "INBOX.md"
        inbox.write_text("# Inbox\n", encoding="utf-8")
        httpd = browser_server.ThreadingHTTPServer(("127.0.0.1", 0), browser_server.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", f"/api/ledger?path={quote(str(self.plan_path))}")
            res = conn.getresponse()
            ok_text = res.read().decode("utf-8", errors="replace")
            conn.close()
            self.assertEqual(res.status, 200, ok_text)
            self.assertEqual(json.loads(ok_text)["items"][0]["eid"], "evt_plan")

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", f"/api/ledger?path={quote(str(inbox))}")
            res = conn.getresponse()
            forbidden_text = res.read().decode("utf-8", errors="replace")
            conn.close()
            self.assertEqual(res.status, 403, forbidden_text)
        finally:
            httpd.shutdown()
            thread.join(timeout=2)
            httpd.server_close()

    def test_ledger_static_contract(self):
        server = (ROOT / "browser" / "server.py").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('route == "/api/ledger"', server)
        self.assertIn("ledger_payload_for_plan", server)
        self.assertIn('const LEDGER_TAB = "Ledger"', app)
        self.assertIn("function renderLedgerPanel", app)
        self.assertIn("/api/ledger?path=", app)
        self.assertIn(".ledger-panel", style)
        self.assertIn(".ledger-entry", style)


class BrowserDecisionLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.original_dev_root = browser_server.DEV_ROOT
        browser_server.DEV_ROOT = self.dev_root

    def tearDown(self):
        browser_server.DEV_ROOT = self.original_dev_root
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def test_parse_decision_log_zero_when_section_is_missing(self):
        result = browser_server.parse_decision_log(
            "# Demo\n\n## Purpose\nNo decisions yet.\n\n## Tasks\n- [pending] one\n"
        )

        self.assertFalse(result["present"])
        self.assertIsNone(result["heading_line"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["recent_directions"], [])

    def test_parse_decision_log_handles_messy_markdown_and_wrapped_bullets(self):
        result = browser_server.parse_decision_log(
            "# Demo\n\n"
            "### Decision Log\n"
            "Intro text should not become an entry.\n"
            "- [DIRECTION] [2026-05-01] Keep browser read-only.\n"
            "  Reason: PLAN.md remains canonical.\n"
            "* [REFRAME] 2026-05-02 Promote decisions instead of scanning full markdown.\n"
            "1. Plain note without a tag still renders.\n"
            "#### Nested notes\n"
            "- [PIVOT] [2026-05-03 app chrome] Keep large modes out of the topbar.\n"
            "## Tasks\n"
            "- [pending] next task\n"
        )

        self.assertTrue(result["present"])
        self.assertEqual(result["heading_line"], 3)
        self.assertEqual(result["count"], 4)
        first = result["entries"][0]
        self.assertEqual(first["kind"], "DIRECTION")
        self.assertEqual(first["date"], "2026-05-01")
        self.assertIn("Reason: PLAN.md remains canonical.", first["body"])
        self.assertFalse(first["is_recent"])
        self.assertTrue(result["entries"][1]["is_recent"])
        self.assertEqual(result["entries"][2]["kind"], "NOTE")
        self.assertEqual(result["entries"][3]["date"], "2026-05-03 app chrome")
        self.assertEqual(
            [entry["kind"] for entry in result["recent_directions"]],
            ["DIRECTION", "REFRAME", "PIVOT"],
        )

    def test_discover_plans_exposes_decision_log_metadata(self):
        plan_dir = self.dev_root / "repo" / "projects" / "demo"
        plan_dir.mkdir(parents=True)
        (plan_dir / "PLAN.md").write_text(
            "# Demo\n\n"
            "## Decision Log\n"
            "- [DIRECTION] [2026-05-01] Keep it visible.\n\n"
            "## Tasks\n"
            "- [pending] ship pane\n",
            encoding="utf-8",
        )

        plans = browser_server.discover_plans()

        self.assertEqual(len(plans), 1)
        decision_log = plans[0]["decision_log"]
        self.assertTrue(decision_log["present"])
        self.assertEqual(decision_log["count"], 1)
        self.assertEqual(decision_log["entries"][0]["kind"], "DIRECTION")

    def test_decision_log_pane_static_contract(self):
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('const DECISION_LOG_TAB = "Decision Log"', app)
        self.assertIn("function renderDecisionLogPane", app)
        self.assertIn("recent_directions", app)
        self.assertIn("No Decision Log section", app)
        for klass in [
            "decision-log-summary",
            "decision-log-recent",
            "decision-entry",
            "decision-recent",
        ]:
            self.assertIn(klass, style)


class BrowserPlanBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        self.original_dev_root = browser_server.DEV_ROOT
        browser_server.DEV_ROOT = self.dev_root

    def tearDown(self):
        browser_server.DEV_ROOT = self.original_dev_root
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def test_plan_meta_includes_deterministic_brief_for_cockpit_view(self):
        plan_dir = self.dev_root / "repo" / "projects" / "pm"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "PLAN.md"
        plan_path.write_text(
            "# PM\n\n"
            "## Purpose\n"
            "Replace external PM surfaces with Vidux-native steering.\n\n"
            "## Tasks\n"
            "- [pending] PM-2 Later thing [ETA: 1h]\n"
            "- [completed] PM-0 Done thing\n"
            "- [in_progress] PM-1 Build `Now` strip [Evidence: user asked]\n"
            "- [blocked] PM-3 Waiting on browser proof [Blocker: screenshot]\n\n"
            "## Decision Log\n"
            "- [DIRECTION] [2026-05-24] Keep PLAN.md canonical and use comments for steering.\n\n"
            "## Progress\n"
            "- [completed] malformed task-shaped bullet should not win\n"
            "- [2026-05-24] Shipped the first cockpit slice.\n",
            encoding="utf-8",
        )

        plan = browser_server.plan_meta(plan_path)
        brief = plan["brief"]

        self.assertEqual(brief["state"], "blocked")
        self.assertEqual(brief["open_count"], 3)
        self.assertEqual(brief["summary"], "Replace external PM surfaces with Vidux-native steering.")
        self.assertEqual(
            [item["status"] for item in brief["focus_tasks"]],
            ["in_progress", "blocked", "pending"],
        )
        self.assertIn("Build Now strip", brief["focus_tasks"][0]["label"])
        self.assertEqual(brief["latest_progress"], "[2026-05-24] Shipped the first cockpit slice.")
        self.assertIn("Keep PLAN.md canonical", brief["latest_decision"])

    def test_plan_brief_and_steering_static_contract(self):
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        comment_rail = (
            ROOT / "browser" / "static" / "comment-rail.js"
        ).read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn("function renderPlanBrief", app)
        self.assertIn("function setupPlanSteering", app)
        self.assertIn("Steer this plan", app)
        self.assertIn("function codingWorkbenchUrl", app)
        self.assertIn("viduxPlan", app)
        self.assertIn("Code lane", app)
        self.assertIn("@pm", app)
        self.assertIn("plan-steering", app)
        self.assertIn("is-steering", comment_rail)
        for klass in [
            "plan-brief",
            "plan-brief-task",
            "plan-brief-code-link",
            "plan-steering",
            "comment-item.is-steering",
        ]:
            self.assertIn(klass, style)


class BrowserSubplanRollupTests(unittest.TestCase):
    """Recursive parent→child task-stat rollup via `> Parent:` backlinks.

    Sets up a parent plan with 5 completed + 5 pending tasks, then two child
    plans pointing back at the parent (3/3 + 2/2). Asserts:
      * `task_stats` stays scoped to the file's own ## Tasks (5/10).
      * `aggregate_stats` rolls in descendants (10/15, 2 descendants).
      * `parent_rel` parsing handles the `> Parent: <relpath>` form.
      * `children` are wired as a list of plan-dicts on the parent.
    Without this, the sidebar progress bar lies about parent completion.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        browser_server.DEV_ROOT = self.dev_root

        # Parent plan: 5 completed + 5 pending = 5/10 own tasks.
        parent_dir = self.dev_root / "demo-repo" / "vidux" / "design-overhaul"
        parent_dir.mkdir(parents=True)
        parent_path = parent_dir / "PLAN.md"
        parent_tasks = (
            "\n".join(f"- [completed] task done {i}" for i in range(5))
            + "\n"
            + "\n".join(f"- [pending] task pending {i}" for i in range(5))
        )
        parent_path.write_text(
            "# Parent\n\n## Purpose\nParent plan.\n\n## Tasks\n" + parent_tasks + "\n",
            encoding="utf-8",
        )
        self.parent_rel = "demo-repo/vidux/design-overhaul/PLAN.md"

        # Child A: 3/3 — every task completed.
        child_a_dir = parent_dir / "alpha"
        child_a_dir.mkdir(parents=True)
        (child_a_dir / "PLAN.md").write_text(
            "# Child A\n\n"
            f"> Parent: {self.parent_rel} task D2\n\n"
            "## Tasks\n"
            "- [completed] a1\n- [completed] a2\n- [completed] a3\n",
            encoding="utf-8",
        )

        # Child B: 0/2 — nothing done.
        child_b_dir = parent_dir / "beta"
        child_b_dir.mkdir(parents=True)
        (child_b_dir / "PLAN.md").write_text(
            "# Child B\n\n"
            f"**Parent:** {self.parent_rel}\n\n"
            "## Tasks\n"
            "- [pending] b1\n- [pending] b2\n",
            encoding="utf-8",
        )

    def tearDown(self):
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def _find(self, plans, rel: str) -> dict:
        for plan in plans:
            if plan["rel"] == rel:
                return plan
        raise AssertionError(f"plan {rel} not in {[p['rel'] for p in plans]}")

    def test_extract_parent_rel_handles_both_forms(self):
        self.assertEqual(
            browser_server.extract_parent_rel(
                "# T\n\n> Parent: vidux/x/PLAN.md task D2\n"
            ),
            "vidux/x/PLAN.md",
        )
        self.assertEqual(
            browser_server.extract_parent_rel("# T\n\n**Parent:** vidux/y/PLAN.md\n"),
            "vidux/y/PLAN.md",
        )
        self.assertIsNone(browser_server.extract_parent_rel("# T\n\nno parent\n"))

    def test_parent_task_stats_count_only_own_tasks(self):
        plans = browser_server.discover_plans()
        parent = self._find(plans, self.parent_rel)
        self.assertEqual(parent["task_stats"]["total"], 10)
        self.assertEqual(parent["task_stats"]["counts"]["completed"], 5)
        self.assertEqual(parent["task_stats"]["counts"]["pending"], 5)

    def test_aggregate_stats_rolls_up_children(self):
        plans = browser_server.discover_plans()
        parent = self._find(plans, self.parent_rel)
        agg = parent["aggregate_stats"]
        # 10 own + 3 child-A + 2 child-B = 15 total tasks under this branch.
        self.assertEqual(agg["total"], 15)
        # 5 own completed + 3 child-A completed + 0 child-B completed = 8.
        self.assertEqual(agg["counts"]["completed"], 8)
        # 5 own pending + 0 child-A pending + 2 child-B pending = 7.
        self.assertEqual(agg["counts"]["pending"], 7)
        self.assertEqual(agg["descendants"], 2)

    def test_children_attached_to_parent(self):
        plans = browser_server.discover_plans()
        parent = self._find(plans, self.parent_rel)
        rels = sorted(child["rel"] for child in parent["children"])
        self.assertEqual(
            rels,
            [
                "demo-repo/vidux/design-overhaul/alpha/PLAN.md",
                "demo-repo/vidux/design-overhaul/beta/PLAN.md",
            ],
        )

    def test_child_keeps_own_task_stats_independent(self):
        plans = browser_server.discover_plans()
        child_a = self._find(plans, "demo-repo/vidux/design-overhaul/alpha/PLAN.md")
        # Children should get their own aggregate_stats too — no descendants
        # for a leaf, so it equals the own task_stats.
        self.assertEqual(child_a["task_stats"]["total"], 3)
        self.assertEqual(child_a["aggregate_stats"]["total"], 3)
        self.assertEqual(child_a["aggregate_stats"]["descendants"], 0)
        self.assertEqual(child_a["parent_rel"], self.parent_rel)


class BrowserReadaloudStaticContractTests(unittest.TestCase):
    def test_readaloud_visual_fixture_covers_player_states(self):
        fixture = (ROOT / "browser" / "static" / "readaloud-fixture.html").read_text(
            encoding="utf-8",
        )
        manifest = json.loads(
            (
                ROOT / "browser" / "static" / "readaloud-fixture-manifest.json"
            ).read_text(encoding="utf-8")
        )
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn("/static/style.css", fixture)
        self.assertIn("/static/readaloud-fixture-manifest.json", fixture)
        self.assertEqual(manifest["decision"], "keep-vanilla-fixture-snapshots")
        self.assertEqual(manifest["storyRunner"], "browser/static/readaloud-fixture.html")
        self.assertIn("plain HTML", manifest["renderer"])
        self.assertIn("no React/Storybook for PR #87", fixture)
        self.assertIn("readaloud-player-fixture", fixture)
        self.assertIn('role="region" aria-label="Read-aloud player"', fixture)
        self.assertIn('role="status" aria-live="polite" aria-atomic="true"', fixture)
        self.assertIn('aria-label="Read-aloud position"', fixture)
        self.assertIn('aria-label="Play or pause read-aloud" aria-pressed="false"', fixture)
        states = [state["id"] for state in manifest["states"]]
        self.assertEqual(len(states), 16)
        self.assertEqual(len(states), len(set(states)))
        for state in states:
            self.assertIn(f'data-fixture-state="{state}"', fixture)

        self.assertIn("Server offline. Start Voxtral MLX script server", fixture)
        self.assertIn("Waiting for local server", fixture)
        self.assertIn("browser/scripts/start-voxtral-mlx-server.sh", fixture)
        self.assertIn("Copied server command", fixture)
        self.assertIn("readaloud-server-command", fixture)
        self.assertIn('aria-label="Copy local Voxtral MLX server command"', fixture)
        self.assertIn("Playing cached audio", fixture)
        self.assertIn("Playing cached/generated segments", fixture)
        self.assertIn("Cleared 3 cached segments", fixture)
        self.assertIn("Pruned 6 old cached segments", fixture)
        self.assertIn("readaloud-cache-clear", fixture)
        self.assertIn("Voxtral synthesis failed: segment 3", fixture)
        self.assertIn("readaloud-fixture-mobile", fixture)
        self.assertIn("readaloud-fixture-fab", fixture)

        for klass in [
            "readaloud-fixture-page",
            "readaloud-fixture-case",
            "readaloud-player-fixture",
            "readaloud-fixture-seek-hover",
            "readaloud-fixture-mobile",
            "readaloud-fixture-coexistence",
        ]:
            self.assertIn(klass, style)

    def test_readaloud_storybook_decision_does_not_add_browser_build_stack(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        deps = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }
        scripts = package.get("scripts", {})

        self.assertNotIn("react", deps)
        self.assertNotIn("react-dom", deps)
        self.assertFalse(any(key.startswith("@storybook/") for key in deps))
        self.assertNotIn("storybook", scripts)

    def test_readaloud_footer_controls_and_annotation_fab_are_annotation_safe(self):
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        topbar_meta = index.split('<div class="topbar-meta">', 1)[1].split("</div>", 1)[0]
        self.assertIn('id="meta-count"', topbar_meta)
        self.assertIn('id="refresh"', topbar_meta)
        self.assertNotIn("root-readaloud", topbar_meta)
        self.assertNotIn("root-annotation-toggle", topbar_meta)

        player_idx = index.index('id="readaloud-player" class="readaloud-player"')
        self.assertNotIn('id="readaloud-player" class="readaloud-player" hidden', index)
        self.assertIn('role="region" aria-label="Read-aloud player"', index)
        self.assertIn('aria-describedby="readaloud-player-status"', index)
        self.assertIn('role="status" aria-live="polite" aria-atomic="true"', index)
        self.assertIn('aria-label="Read current selection or pane aloud"', index)
        self.assertIn('aria-label="Play read-aloud" aria-pressed="false"', index)
        self.assertIn('aria-label="Read-aloud speed: 1.12x. Click to cycle."', index)
        self.assertIn('id="root-readaloud-engine" class="root-readaloud-engine" type="button"', index)
        self.assertIn("Click to copy the server command", index)
        self.assertIn('id="readaloud-server-command"', index)
        self.assertIn('hidden>browser/scripts/start-voxtral-mlx-server.sh</button>', index)
        self.assertIn('id="readaloud-cache-clear"', index)
        self.assertIn('aria-label="No cached read-aloud segments to clear"', index)
        self.assertGreater(index.index('id="root-readaloud-toggle"'), player_idx)
        self.assertGreater(index.index('id="root-readaloud-engine"'), player_idx)
        self.assertGreater(index.index('id="readaloud-cache-clear"'), player_idx)
        self.assertGreater(index.index('id="root-readaloud-speed"'), player_idx)
        self.assertIn('class="annotation-fab"', index)

        ids = [
            "root-annotation-toggle",
            "root-readaloud-toggle",
            "root-readaloud-engine",
            "readaloud-server-command",
            "readaloud-cache-clear",
            "root-readaloud-speed",
            "readaloud-player",
            "readaloud-player-toggle",
            "readaloud-player-seek",
            "readaloud-player-status",
            "readaloud-player-time",
        ]
        for control_id in ids:
            self.assertIn(f'id="{control_id}"', index)
            self.assertIn(f'"#{control_id}"', app)

        for klass in [
            "annotation-fab",
            "readaloud-player-read",
            "root-readaloud-engine",
            "readaloud-server-command",
            "readaloud-cache-clear",
            "root-readaloud-speed",
            "ra-section-play",
            "ra-section-play-host",
            "readaloud-player",
            "readaloud-player-toggle",
            "readaloud-player-seek",
            "readaloud-player-status",
            "readaloud-player-time",
        ]:
            self.assertIn(klass, style)

    def test_app_action_zoning_contract_names_chrome_layers(self):
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        topbar_meta = index.split('<div class="topbar-meta">', 1)[1].split("</div>", 1)[0]
        self.assertIn('data-vidux-zone="status-header"', index)
        self.assertIn('data-vidux-zone="app-shell"', index)
        self.assertIn('data-vidux-zone="navigation-sidebar"', index)
        self.assertIn('data-vidux-zone="content-pane"', index)
        self.assertIn('data-vidux-zone="floating-action"', index)
        self.assertIn('data-vidux-zone="footer-player"', index)
        self.assertIn('data-vidux-zone", "mode-popover"', app)
        self.assertNotIn("root-annotation-toggle", topbar_meta)
        self.assertNotIn("readaloud-player", topbar_meta)

        for token in [
            "--z-mobile-sidebar:",
            "--z-header:",
            "--z-footer-player:",
            "--z-floating-action:",
            "--z-mode-popover:",
            "--z-skip-link:",
            "--footer-player-bottom:",
            "--footer-player-block-size:",
            "--floating-action-footer-gap:",
            "--pane-footer-reserve:",
        ]:
            self.assertIn(token, style)

        self.assertIn("z-index: var(--z-header)", style)
        self.assertIn("z-index: var(--z-mobile-sidebar)", style)
        self.assertIn("z-index: var(--z-footer-player)", style)
        self.assertIn("z-index: var(--z-floating-action)", style)
        self.assertIn("z-index: var(--z-mode-popover)", style)

    def test_annotation_fab_state_machine_contract_is_named(self):
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        annotation_helper = (
            ROOT / "browser" / "static" / "annotation-state.js"
        ).read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('/static/annotation-state.js', index)
        self.assertLess(index.index('/static/annotation-state.js'), index.index('/static/app.js'))
        self.assertIn('data-annotation-state="unavailable"', index)
        self.assertIn('aria-label="Select a plan or artifact to annotate"', index)
        self.assertIn('aria-pressed="false"', index)
        self.assertIn("ViduxAnnotationState", app)
        self.assertIn("ANNOTATION_STATES", app)
        for state_name in [
            "unavailable",
            "idle",
            "capture-active",
            "target-picked",
            "composer-open",
            "saving",
            "saved",
            "error",
        ]:
            self.assertIn(state_name, annotation_helper)

        self.assertIn("dataset.annotationState", annotation_helper)
        self.assertIn("paintButton", annotation_helper)
        self.assertIn("derive", annotation_helper)
        self.assertIn("annotationUiState", app)
        self.assertIn("status.dataset.state", app)
        self.assertIn("setPopoverStatus(AS.SAVING", app)
        self.assertIn("setPopoverStatus(AS.SAVED", app)
        self.assertIn("setPopoverStatus(AS.ERROR", app)
        self.assertIn("aria-pressed", annotation_helper)
        self.assertIn("is-saving", style)
        self.assertIn("is-saved", style)
        self.assertIn("is-error", style)
        self.assertIn("z-index: var(--z-skip-link)", style)
        self.assertIn(
            "bottom: calc(var(--footer-player-bottom) + var(--footer-player-block-size) + var(--floating-action-footer-gap))",
            style,
        )
        self.assertIn("padding: 24px clamp(20px, 3vw, 40px) var(--pane-footer-reserve)", style)
        self.assertIn("--footer-player-block-size: 118px", style)

    def test_annotation_review_rail_contract_is_named(self):
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        comment_rail = (
            ROOT / "browser" / "static" / "comment-rail.js"
        ).read_text(encoding="utf-8")
        markers = (
            ROOT / "browser" / "static" / "comment-markers.js"
        ).read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('/static/comment-rail.js', index)
        self.assertLess(index.index('/static/comment-rail.js'), index.index('/static/app.js'))
        self.assertIn("ViduxCommentRail", app)
        self.assertIn("commentRail.countLabel", app)
        self.assertIn("commentRail.renderList", app)
        self.assertIn('class="comments-panel annotation-review-rail"', markers)
        self.assertIn('data-comment-scope="current-view"', markers)
        self.assertIn('data-comment-state="loading"', markers)
        self.assertIn('data-comment-count="0"', markers)
        self.assertIn('data-comment-filter="all"', markers)
        self.assertIn('data-comment-filter="open"', markers)
        self.assertIn('data-comment-filter="mine"', markers)
        self.assertIn('data-comment-list', markers)
        self.assertIn("data-comment-empty", comment_rail)
        self.assertIn("data-comment-jump", comment_rail)
        self.assertIn("targetLabel", comment_rail)
        self.assertIn("data-comment-state", app)
        self.assertIn("data-comment-count", app)
        self.assertIn(".annotation-review-rail", style)
        self.assertIn(".comment-filter-row", style)
        self.assertIn(".comment-filter.is-active", style)
        self.assertIn(".comment-empty", style)

    def test_annotation_anchor_marker_contract_is_named(self):
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        markers = (
            ROOT / "browser" / "static" / "comment-markers.js"
        ).read_text(encoding="utf-8")
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('/static/comment-markers.js', index)
        self.assertLess(index.index('/static/comment-rail.js'), index.index('/static/comment-markers.js'))
        self.assertLess(index.index('/static/comment-markers.js'), index.index('/static/app.js'))
        self.assertIn("ViduxCommentMarkers", app)
        self.assertIn("commentMarkers.render", app)
        self.assertIn("commentMarkers.renderPanel", app)
        self.assertIn("commentMarkers.bindToggle", app)
        self.assertIn("commentMarkers.jumpToTarget", app)
        self.assertIn("commentMarkers.setPreview", app)
        self.assertIn("commentMarkers.resolveAnchorTarget", app)
        self.assertIn("resolveAnchorTarget", app)
        self.assertIn("renderCommentMarkers", app)
        self.assertIn("vidux:comment-markers-hidden", markers)
        self.assertIn('data-comment-markers-hidden', markers)
        self.assertIn('data-comment-marker-toggle', markers)
        self.assertIn("updateToggle", markers)
        self.assertIn("setStoredHidden", markers)
        self.assertIn("accessibleArtifactFrames", markers)
        self.assertIn("ensureFrameAnchorStyle", markers)
        self.assertIn("resolveAnchorTarget", markers)
        self.assertIn('data-comment-target-map', markers)
        self.assertIn("comment-marker-layer", markers)
        self.assertIn("data-comment-marker-count", markers)
        self.assertIn("comment-target-map", markers)
        self.assertIn(".comment-marker-layer", style)
        self.assertIn(".comment-marker", style)
        self.assertIn(".comment-marker-toggle", style)
        self.assertIn(".comment-target-map", style)
        self.assertIn(".comment-target-chip", style)
        self.assertIn(".is-anchor-preview", style)

    def test_readaloud_engine_status_is_health_only_loopback_probe(self):
        readaloud = (ROOT / "browser" / "static" / "readaloud.js").read_text(
            encoding="utf-8",
        )
        style = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('voxtralBaseUrl: "http://127.0.0.1:8765"', readaloud)
        self.assertIn("function readaloudSetEngineStatus", readaloud)
        self.assertIn("async function readaloudProbeEngine", readaloud)
        self.assertIn("MLX on", readaloud)
        self.assertIn("MLX off", readaloud)
        self.assertIn('READALOUD_SERVER_COMMAND = "browser/scripts/start-voxtral-mlx-server.sh"', readaloud)
        self.assertIn("READALOUD_OFFLINE_REPROBE_INTERVAL_MS = 3000", readaloud)
        self.assertIn("READALOUD_OFFLINE_REPROBE_WINDOW_MS = 90000", readaloud)
        self.assertIn("READALOUD_CACHE_MAX_BYTES = 160 * 1024 * 1024", readaloud)
        self.assertIn("READALOUD_CACHE_MAX_ENTRIES = 120", readaloud)
        self.assertIn("readaloudCopyServerCommand", readaloud)
        self.assertIn("readaloudStartOfflineReprobe", readaloud)
        self.assertIn("readaloudRunOfflineReprobe", readaloud)
        self.assertIn("readaloudStopOfflineReprobe", readaloud)
        self.assertIn("readaloudShouldReprobeOffline", readaloud)
        self.assertIn("engineProbeTimer: null", readaloud)
        self.assertIn("engineProbeDeadline: 0", readaloud)
        self.assertIn("readaloudShowServerCommand", readaloud)
        self.assertIn("Copied server command", readaloud)
        self.assertIn("Server offline. Start", readaloud)
        self.assertIn("Server still offline", readaloud)
        self.assertIn("Run from the vidux repo root", readaloud)
        self.assertIn("Start local Voxtral MLX server: ${readaloudOfflineServerLabel()}", readaloud)
        self.assertIn('probePath: "/health"', readaloud)
        self.assertIn("${engine.baseUrl}${engine.probePath}", readaloud)
        self.assertIn('${READALOUD.voxtralBaseUrl}/v1/audio/speech', readaloud)
        self.assertIn('defaultVoice: "cheerful_female"', readaloud)
        self.assertIn("voice: READALOUD.defaultVoice", readaloud)
        self.assertIn("indexedDB.open", readaloud)
        self.assertIn("readaloudCacheKey", readaloud)
        self.assertIn("readaloudGetSegmentAudio", readaloud)
        self.assertIn("readaloudSegmentCacheKey", readaloud)
        self.assertIn("readaloudCachePrune", readaloud)
        self.assertIn("readaloudCacheRecordPrunable", readaloud)
        self.assertIn("readaloudCacheRecordBytes", readaloud)
        self.assertIn("readaloudCacheRecordLastUsedMs", readaloud)
        self.assertIn("readaloudCachePruneMessage", readaloud)
        self.assertIn("readaloudFormatBytes", readaloud)
        self.assertIn("readaloudCacheDeleteMany", readaloud)
        self.assertIn("readaloudClearCurrentCache", readaloud)
        self.assertIn("readaloudUpdateCacheButton", readaloud)
        self.assertIn("readaloudSegmentsPlaybackKey", readaloud)
        self.assertIn("readaloudMergeSegmentAudio", readaloud)
        self.assertIn("Decoding and stitching segment audio", readaloud)
        self.assertIn("cached, ${misses.length} missing in ${batches.length}", readaloud)
        self.assertIn('type: "segment"', readaloud)
        self.assertIn("last_used_at", readaloud)
        self.assertIn("created_at", readaloud)
        self.assertIn("protectedKeys", readaloud)
        self.assertIn("Pruned ${result.deleted} old cached segment", readaloud)
        self.assertIn("metadata,", readaloud)
        self.assertIn("currentSegmentDurations: []", readaloud)
        self.assertIn("currentSegmentCacheKeys: []", readaloud)
        self.assertIn("segmentCacheKeys: result.segmentCacheKeys", readaloud)
        self.assertIn("readaloudSegmentTimeline", readaloud)
        self.assertIn("readaloudAssignWordSegments", readaloud)
        self.assertIn("readaloudTimeForWordSpan", readaloud)
        self.assertIn("readaloudTimelineTimeForProgress", readaloud)
        self.assertIn("dataset.raSegmentIndex", readaloud)
        self.assertIn("dataset.raSegmentWordIndex", readaloud)
        self.assertIn("dataset.raSegmentWordCount", readaloud)
        self.assertIn("READALOUD_SECTION_CONTROL_KINDS", readaloud)
        self.assertIn("readaloudInstallSectionObserver", readaloud)
        self.assertIn("readaloudRefreshSectionControls", readaloud)
        self.assertIn("readaloudPlaySection", readaloud)
        self.assertIn("readaloudPlaySource", readaloud)
        self.assertIn("readaloudSegmentRange", readaloud)
        self.assertIn("readaloudElementText", readaloud)
        self.assertIn('"code-block"', readaloud)
        self.assertIn(".ra-section-play", readaloud)
        self.assertIn("Playing cached audio", readaloud)
        self.assertIn("Playing cached/generated segments", readaloud)
        self.assertIn("readaloudSeekFromPlayer", readaloud)
        self.assertIn('"aria-valuetext"', readaloud)
        self.assertIn('setAttribute("aria-pressed"', readaloud)
        self.assertIn('setAttribute("aria-busy"', readaloud)
        self.assertIn('setAttribute("aria-label", `Read this section:', readaloud)
        self.assertIn("span.tabIndex = 0", readaloud)
        self.assertIn('span.setAttribute("role", "button")', readaloud)
        self.assertIn('span.setAttribute("aria-label", `Jump playback to word', readaloud)
        self.assertIn("readaloudSeekFromWordKeydown", readaloud)
        self.assertIn("export function readaloudCollectSegments", readaloud)
        self.assertIn("readaloudSegmentsToText(segments)", readaloud)
        self.assertIn("readaloudStableHash", readaloud)
        self.assertIn('return "heading"', readaloud)
        self.assertIn('return "list-item"', readaloud)
        self.assertIn('return "code-block"', readaloud)
        self.assertIn('return "artifact-block"', readaloud)
        self.assertIn('element.closest("li,pre,blockquote")', readaloud)
        self.assertIn(".readaloud-player,.annotation-fab,.topbar,.sidebar", readaloud)
        self.assertIn(".ra-section-play-host:focus-within", style)
        self.assertIn(".ra-word:focus-visible", style)
        self.assertIn(".readaloud-player-seek:focus-visible", style)
        self.assertIn("currentSegments: []", readaloud)
        self.assertIn("segments: playbackSource.segments", readaloud)
        self.assertIn("try {\n    await audio.play();", readaloud)
        self.assertIn("readaloudClearAudio();\n    throw err;", readaloud)

    def test_readaloud_project_a_acceptance_contract(self):
        index = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
        readaloud = (ROOT / "browser" / "static" / "readaloud.js").read_text(
            encoding="utf-8",
        )
        manifest = json.loads(
            (
                ROOT / "browser" / "static" / "readaloud-fixture-manifest.json"
            ).read_text(encoding="utf-8")
        )
        server = (ROOT / "browser" / "scripts" / "voxtral_mlx_server.py").read_text(
            encoding="utf-8",
        )
        launcher = (
            ROOT / "browser" / "scripts" / "start-voxtral-mlx-server.sh"
        ).read_text(encoding="utf-8")

        topbar_meta = index.split('<div class="topbar-meta">', 1)[1].split("</div>", 1)[0]
        self.assertIn('id="meta-count"', topbar_meta)
        self.assertIn('id="refresh"', topbar_meta)
        self.assertNotIn("readaloud", topbar_meta)
        self.assertNotIn("annotation", topbar_meta)

        for control_id in [
            "readaloud-player",
            "root-readaloud-toggle",
            "readaloud-player-toggle",
            "readaloud-player-seek",
            "readaloud-cache-clear",
            "root-readaloud-engine",
            "root-readaloud-speed",
            "root-annotation-toggle",
        ]:
            self.assertIn(f'id="{control_id}"', index)
            self.assertIn(f'"#{control_id}"', app)

        for fn in [
            "readaloudCollectSegments",
            "readaloudGetSegmentAudio",
            "readaloudMergeSegmentAudio",
            "readaloudSegmentTimeline",
            "readaloudTimeForWordSpan",
            "readaloudRefreshSectionControls",
            "readaloudCachePrune",
            "readaloudClearCurrentCache",
            "readaloudStartOfflineReprobe",
            "readaloudCopyServerCommand",
        ]:
            self.assertIn(fn, readaloud)

        for marker in [
            'READALOUD_CACHE_MAX_BYTES = 160 * 1024 * 1024',
            'READALOUD_SERVER_COMMAND = "browser/scripts/start-voxtral-mlx-server.sh"',
            'voxtralBaseUrl: "http://127.0.0.1:8765"',
            'defaultVoice: "cheerful_female"',
            'source === "mixed" ? "Playing cached/generated segments"',
            'span.setAttribute("role", "button")',
            'setAttribute("aria-busy"',
        ]:
            self.assertIn(marker, readaloud)

        states = {state["id"] for state in manifest["states"]}
        self.assertTrue(
            {
                "server-offline",
                "server-waiting",
                "first-load",
                "synth-queue",
                "cache-hit",
                "cache-clear",
                "cache-pruned",
                "playing",
                "paused",
                "seek-hover",
                "segment-failure",
                "mobile-width",
                "annotation-fab-coexistence",
            }.issubset(states)
        )

        self.assertIn("supports_word_timestamps", server)
        self.assertIn("supports_reference_audio", server)
        self.assertIn("redseaplume/Voxtral-4B-TTS-2603-MLX-4bit", server)
        self.assertIn("voxtral_mlx_server.py", launcher)

    def test_voxtral_server_sends_success_after_generation_try_block(self):
        server = (ROOT / "browser" / "scripts" / "voxtral_mlx_server.py").read_text(
            encoding="utf-8",
        )

        error_index = server.index("except Exception as exc")
        success_index = server.index("self.send_response(HTTPStatus.OK)")
        self.assertLess(error_index, success_index)
        self.assertIn('self.send_header("Content-Type", "audio/wav")', server)


if __name__ == "__main__":
    unittest.main()
