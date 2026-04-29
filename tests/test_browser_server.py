import importlib.util
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path


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
        self.assertFalse(browser_server.is_loopback_host("192.168.4.55"))


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

    def json_headers(self, **extra: str) -> dict[str, str]:
        return {"Content-Type": "application/json", **extra}

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
        handler.client_address = ("192.168.4.55", 49152)
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
        handler.client_address = ("192.168.4.55", 49152)
        handler.headers = {
            "Content-Type": "application/json",
            "Host": f"127.0.0.1:{self.port}",
            "Origin": self.origin(),
        }
        handler._send = lambda code, msg: sent.append((code, msg))

        self.assertTrue(browser_server.Handler._require_browser_json(handler, require_origin=True))
        self.assertEqual(sent, [])


class BrowserPlanDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev_root = Path(self.tmp.name).resolve()
        browser_server.DEV_ROOT = self.dev_root

    def tearDown(self):
        self.tmp.cleanup()

    def write_plan(self, repo: str, rel: str, title: str = "Demo") -> Path:
        path = self.dev_root / repo / rel / "PLAN.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            f"# {title}\n\n## Purpose\nLocal test plan.\n",
            encoding="utf-8",
        )
        return path

    def test_legacy_mobiledevcombine_duplicate_prefers_strongyes_checkout(self):
        canonical = self.write_plan("strongyes-web", "vidux/game-plan", "Game Plan")
        self.write_plan("mobiledevcombine-web", "vidux/game-plan", "Old Game Plan")

        plans = browser_server.discover_plans()
        game_plans = [
            plan
            for plan in plans
            if Path(plan["rel"]).parts[1:] == ("vidux", "game-plan", "PLAN.md")
        ]

        self.assertEqual(len(game_plans), 1)
        self.assertEqual(game_plans[0]["repo"], "strongyes-web")
        self.assertEqual(Path(game_plans[0]["path"]), canonical.resolve())


if __name__ == "__main__":
    unittest.main()
