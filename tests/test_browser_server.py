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
        self.assertEqual(len(states), 15)
        self.assertEqual(len(states), len(set(states)))
        for state in states:
            self.assertIn(f'data-fixture-state="{state}"', fixture)

        self.assertIn("Server offline. Run from the vidux repo root", fixture)
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
        self.assertIn("Waiting for local server", readaloud)
        self.assertIn("Server still offline", readaloud)
        self.assertIn("Server offline. Run from the vidux repo root", readaloud)
        self.assertIn("Start local Voxtral MLX server: ${READALOUD_SERVER_COMMAND}", readaloud)
        self.assertIn('${READALOUD.voxtralBaseUrl}/health', readaloud)
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
        self.assertIn("Merging segment audio", readaloud)
        self.assertIn("cached, ${misses.length} synthesizing", readaloud)
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
