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


if __name__ == "__main__":
    unittest.main()
