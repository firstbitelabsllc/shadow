from __future__ import annotations

import json
import http.client
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from browser import server


PLAN = """# Release notes

## Brief

- Outcome ID: ship-release-notes
- Outcome Revision: 7
- Outcome Updated At: 2026-08-03T02:00:00Z
- Outcome State: needs_input
- Outcome: Publish release notes people can trust.
- Next: Choose the final review depth.
- Decision ID: choose-review-depth
- Decision: How should we finish the review?
- Option A ID: ship-now
- Option A: Ship now
- Option A Consequence: Use the accepted proof and finish today.
- Option B ID: cold-review
- Option B: Run a cold review
- Option B Consequence: Spend one bounded pass on independent judgment.
- Option C ID: hold-release
- Option C: Hold the release
- Option C Consequence: Keep the Outcome open until new evidence exists.
- Proof ID: focused-tests
- Proof: tests/test_browser.py
- Proof Summary: Browser contract tests pass.
- Proof Delivery: delivered

## Work

- [in_progress] Choose the final review depth

## Progress

- 2026-08-03: The bounded implementation is ready for a decision.
"""


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)


class BrowserTests(unittest.TestCase):
    def make_repo(self, root: Path) -> tuple[Path, Path]:
        repo = root / "repo"
        plan = repo / "project" / "PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(PLAN, encoding="utf-8")
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        git(repo, "add", "project/PLAN.md")
        git(repo, "commit", "-qm", "fixture")
        return repo, plan

    def test_plan_projection_has_one_brief_and_three_choices(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            record = server.plan_record(plan, repo)
        self.assertIsNone(record["contract_error"])
        self.assertEqual(record["outcome"]["revision"], 7)
        self.assertEqual(record["briefing"]["state"], "needs_you")
        self.assertEqual(
            [item["id"] for item in record["briefing"]["choices"]],
            ["ship-now", "cold-review", "hold-release"],
        )
        self.assertEqual(record["briefing"]["proof"]["locator"], "tests/test_browser.py")
        self.assertNotIn(dirname, json.dumps(record))





    def test_decision_receipt_is_project_local_bounded_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            document = server.plan_record(plan, repo)["outcome"]
            first = server.write_decision_receipt(plan, document, "cold-review", 7)
            second = server.write_decision_receipt(plan, document, "cold-review", 7)
            receipt = repo / ".shadow" / "evidence" / f"decision-{first['receipt_id']}.json"
            self.assertEqual(first["receipt_id"], second["receipt_id"])
            self.assertTrue(receipt.is_file())
            self.assertEqual(first["state"], "received")
            self.assertNotIn(dirname, receipt.read_text(encoding="utf-8"))
            self.assertEqual(len(list(receipt.parent.glob("*.json"))), 1)

    def test_stale_revision_is_recorded_as_superseded(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            document = server.plan_record(plan, repo)["outcome"]
            receipt = server.write_decision_receipt(plan, document, "ship-now", 6)
        self.assertEqual(receipt["state"], "superseded")
        self.assertEqual(receipt["reason"], "stale_revision")

    def test_plan_resolution_rejects_escape_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            with self.assertRaises(server.BrowserError):
                server.resolve_plan(repo, "../PLAN.md")
            link = repo / "linked" / "PLAN.md"
            link.parent.mkdir()
            link.symlink_to(plan)
            with self.assertRaises(server.BrowserError):
                server.resolve_plan(repo, "linked/PLAN.md")

    def test_scan_skips_hidden_state_and_returns_no_absolute_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname))
            hidden = repo / ".shadow" / "PLAN.md"
            hidden.parent.mkdir(exist_ok=True)
            hidden.write_text(PLAN, encoding="utf-8")
            records = server.discover_plans(repo)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], "project/PLAN.md")
        self.assertNotIn(dirname, json.dumps(records))

    def test_non_loopback_bind_is_rejected(self) -> None:
        self.assertEqual(server.main(["--host", "0.0.0.0", "--port", "7191", "--root", "."]), 2)

    def test_http_rejects_foreign_host_and_missing_write_origin(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname))
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.putrequest("GET", "/", skip_host=True)
                connection.putheader("Host", "example.invalid")
                connection.endheaders()
                self.assertEqual(connection.getresponse().status, 403)
                connection.close()

                body = json.dumps({"plan": "project/PLAN.md", "option_id": "ship-now", "revision": 7})
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("POST", "/api/decision", body=body, headers={"Content-Type": "application/json"})
                self.assertEqual(connection.getresponse().status, 403)
                connection.close()
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)


    def test_stylesheet_uses_only_its_own_design_tokens(self) -> None:
        css = (Path(server.__file__).parent / "static" / "style.css").read_text(encoding="utf-8")
        for token in ("--card", "--paper"):
            self.assertNotIn(f"var({token}", css)

    def test_proxy_host_is_refused_without_the_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname))
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.putrequest("GET", "/api/health", skip_host=True)
                connection.putheader("Host", "studio.tailnet.example.ts.net")
                connection.endheaders()
                self.assertEqual(connection.getresponse().status, 403)
                connection.close()
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)

    def test_allow_listed_proxy_host_reads_and_decides(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname).resolve())
            service = server.Server(
                ("127.0.0.1", 0), repo, frozenset({"studio.tailnet.example.ts.net"})
            )
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.putrequest("GET", "/api/health", skip_host=True)
                # The proxy owns its own outer port; no port in the Host header.
                connection.putheader("Host", "Studio.Tailnet.Example.TS.NET")
                connection.endheaders()
                self.assertEqual(connection.getresponse().status, 200)
                connection.close()

                body = json.dumps({"plan": "project/PLAN.md", "option_id": "cold-review", "revision": 7})
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.putrequest("POST", "/api/decision", skip_host=True)
                connection.putheader("Host", "studio.tailnet.example.ts.net")
                connection.putheader("Origin", "https://studio.tailnet.example.ts.net")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(len(body)))
                connection.endheaders()
                connection.send(body.encode("utf-8"))
                self.assertEqual(connection.getresponse().status, 200)
                connection.close()

                # A hostname NOT on the allowlist still gets refused.
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.putrequest("GET", "/api/health", skip_host=True)
                connection.putheader("Host", "evil.example.net")
                connection.endheaders()
                self.assertEqual(connection.getresponse().status, 403)
                connection.close()
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)

    def test_non_loopback_bind_is_still_rejected_with_allow_host(self) -> None:
        self.assertEqual(
            server.main(["--host", "0.0.0.0", "--port", "7191", "--root", ".", "--allow-host", "x.ts.net"]),
            2,
        )

    def test_raw_plan_endpoint_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname))
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("GET", "/api/plan?path=project/PLAN.md")
                self.assertEqual(connection.getresponse().status, 404)
                connection.close()
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)


    def test_http_server_header_carries_the_product_name(self) -> None:
        self.assertTrue(server.Handler.server_version.startswith("Shadow/"))

    def test_post_errors_never_reflect_exception_text(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname).resolve())
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                failure = PermissionError(
                    f"[Errno 13] Permission denied: '{repo}/.shadow/evidence'"
                )
                body = json.dumps({"plan": "project/PLAN.md", "option_id": "ship-now", "revision": 7})
                with mock.patch.object(server, "write_decision_receipt", side_effect=failure):
                    connection = http.client.HTTPConnection("127.0.0.1", port)
                    connection.request(
                        "POST",
                        "/api/decision",
                        body=body,
                        headers={
                            "Content-Type": "application/json",
                            "Origin": f"http://127.0.0.1:{port}",
                        },
                    )
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    connection.close()
                self.assertEqual(response.status, 400)
                self.assertNotIn(str(repo), payload["error"])
                self.assertNotIn("Errno", payload["error"])
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)

    def test_titles_block_every_canonical_private_path_and_secret_shape(self) -> None:
        # Secret-shaped fixtures are assembled at runtime so the tracked
        # source itself stays clean for the public-ready grep gate.
        slack_token = "xoxb-" + "1234567890-ABCDEFGHIJKLMNOP"
        aws_key = "AKIA" + "IOSFODNN7EXAMPLE"
        github_token = "github_pat_" + "11ABCDEFGHIJKLMNOPQRSTUV"
        unsafe_titles = (
            "# Fix ~/Development/secret-client build",
            "# Clean /private/var/folders cache",
            "# Debug C:\\Users\\leo\\repo crash",
            f"# Rotate {slack_token} now",
            f"# Revoke {aws_key} key",
            f"# Move {github_token} creds",
        )
        for heading in unsafe_titles:
            self.assertEqual(server.title(heading + "\n", "client-repo"), "Client Repo", heading)
        self.assertEqual(server.title("# Ship the release notes\n", "client-repo"), "Ship the release notes")

    def test_brief_and_outcome_filters_block_secret_shapes(self) -> None:
        from browser import chief_of_staff, outcome_source

        secret_shaped = (
            "rotate " + "AKIA" + "IOSFODNN7EXAMPLE" + " today",
            "revoke " + "xoxb-" + "1234567890-ABCDEFGHIJKLMNOP",
            "replace " + "sk-ant-" + "api03-abcdefghijkl",
        )
        for value in secret_shaped:
            with self.assertRaises(chief_of_staff.DecisionInputError, msg=value):
                chief_of_staff._public_text(value, "changed")
            self.assertIsNotNone(outcome_source.SECRET_SHAPE_RE.search(value), value)
        self.assertEqual(
            chief_of_staff._public_text("shipped the release notes", "changed"),
            "shipped the release notes",
        )

    def test_browser_secret_shapes_carry_the_canonical_left_guard(self) -> None:
        # shadow-lint accepts hyphenated English because the canonical
        # SECRET_SHAPE_RE guards `sk-` on the left.  The browser transcriptions
        # must agree, or a plan passes lint and then fails board projection.
        from browser import chief_of_staff, outcome_source

        prose = "task-mismatched risk-mitigation smoke green"
        self.assertIsNone(outcome_source.SECRET_SHAPE_RE.search(prose), prose)
        self.assertIsNone(chief_of_staff.PRIVATE_TEXT_RE.search(prose), prose)
        self.assertEqual(chief_of_staff._public_text(prose, "changed"), prose)
        self.assertEqual(outcome_source._text(prose, "changed"), prose)



class WorktreePoolPruneTests(unittest.TestCase):
    def test_discover_skips_worktree_pool_directories(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            keep = root / "repo" / "PLAN.md"
            keep.parent.mkdir(parents=True)
            keep.write_text("# Keep me\n", encoding="utf-8")
            for pool in ("repo-worktrees", ".worktrees"):
                lane = root / pool / "lane-a"
                lane.mkdir(parents=True)
                (lane / "PLAN.md").write_text("# Lane copy\n", encoding="utf-8")
            records = server.discover_plans(root)
        titles = [record["title"] for record in records]
        self.assertEqual(titles, ["Keep me"])


BOARD_PLAN = """# Gift flow live

## Brief

- Project: snowcubes
- Mode: ship
- Milestone: Gift flow live on storefront

## Tasks

### M1 — Gift flow live
- [completed] C1 Gift wrap option renders on PDP | proof: npm run test:pdp | size: S
- [in_progress] C2 Checkout smoke green on preview theme | proof: npm run smoke | size: M
- [pending] C3 (DoD) Live-theme publish with pixel proof | proof: npm run publish:verify | size: S

## Progress

- 2026-08-05: board fixture ready.
"""


class BoardProjectionTests(unittest.TestCase):
    def make_board_repo(self, root: Path, plan_text: str) -> tuple[Path, Path]:
        repo = root / "repo"
        plan = repo / "gift-flow" / "PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(plan_text, encoding="utf-8")
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        git(repo, "add", "gift-flow/PLAN.md")
        git(repo, "commit", "-qm", "fixture")
        return repo, plan

    def test_plan_record_carries_gated_board_fields(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), BOARD_PLAN)
            record = server.plan_record(plan, repo)
        self.assertEqual(record["project"], "snowcubes")
        self.assertEqual(record["mode"], "ship")
        self.assertEqual(record["milestone"], "Gift flow live on storefront")
        self.assertEqual(
            record["tasks"],
            {"pending": 1, "in_progress": 1, "blocked": 0, "completed": 1},
        )

    def test_task_counts_ignore_checkboxes_outside_the_tasks_section(self) -> None:
        noisy = BOARD_PLAN.replace(
            "## Progress",
            "## Notes\n\n- [completed] a stray checkbox that is not a task\n\n## Progress",
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), noisy)
            record = server.plan_record(plan, repo)
        self.assertEqual(
            record["tasks"],
            {"pending": 1, "in_progress": 1, "blocked": 0, "completed": 1},
        )

    def test_plan_record_carries_a_lint_summary(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), BOARD_PLAN)
            record = server.plan_record(plan, repo)
        self.assertTrue(record["lint"]["parse_ok"])
        self.assertIsInstance(record["lint"]["blocking"], int)
        self.assertIsInstance(record["lint"]["warning"], int)

    def test_broad_posture_earns_a_chip(self) -> None:
        broad = BOARD_PLAN.replace("- Mode: ship", "- Mode: explore")
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), broad)
            record = server.plan_record(plan, repo)
        self.assertEqual(record["mode"], "explore")

    def test_legacy_modes_earn_no_chip(self) -> None:
        legacy = BOARD_PLAN.replace("- Mode: ship", "- Mode: Spike")
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), legacy)
            record = server.plan_record(plan, repo)
        self.assertIsNone(record["mode"])
        self.assertGreaterEqual(record["lint"]["blocking"], 1)

    def test_an_unreadable_plan_is_skipped_without_crashing_the_scan(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), BOARD_PLAN)
            bad = repo / "broken" / "PLAN.md"
            bad.parent.mkdir()
            bad.write_bytes(b"# \xff\xfe not utf-8")
            records = server.discover_plans(repo)
        paths = [record["path"] for record in records]
        self.assertIn("gift-flow/PLAN.md", paths)
        self.assertNotIn("broken/PLAN.md", paths)

    def test_lint_summary_reports_parse_ok_false_when_the_linter_raises(self) -> None:
        with mock.patch.object(server.shadow_lint, "lint_plan", side_effect=RuntimeError("boom")):
            summary = server.lint_summary("# anything")
        self.assertEqual(summary, {"parse_ok": False, "blocking": 0, "warning": 0})

    def test_lint_flags_a_bad_plan(self) -> None:
        bad = BOARD_PLAN.replace("- Mode: ship", "- Mode: turbo")
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), bad)
            record = server.plan_record(plan, repo)
        self.assertGreaterEqual(record["lint"]["blocking"], 1)

    def test_board_fields_fall_back_safely(self) -> None:
        bare = "# Plain plan\n\n## Brief\n\n- Outcome: something\n"
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), bare)
            record = server.plan_record(plan, repo)
        self.assertEqual(record["project"], "gift-flow")
        self.assertIsNone(record["mode"])
        self.assertIsNone(record["milestone"])
        self.assertIsNone(record["tasks"])

    def test_board_fields_reject_unsafe_or_invalid_values(self) -> None:
        unsafe = (
            "# Unsafe\n\n## Brief\n\n"
            "- Project: Not A Slug!!\n"
            "- Mode: turbo\n"
            "- Milestone: Fix ~/Development/secret-client build\n"
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), unsafe)
            record = server.plan_record(plan, repo)
        self.assertEqual(record["project"], "gift-flow")
        self.assertIsNone(record["mode"])
        self.assertIsNone(record["milestone"])


if __name__ == "__main__":
    unittest.main()
