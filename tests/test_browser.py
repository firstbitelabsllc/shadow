from __future__ import annotations

import json
import http.client
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from browser import server


PLAN = """# Release notes

## Operator Brief

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
            receipt = repo / ".pilot-puppy" / "evidence" / f"decision-{first['receipt_id']}.json"
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
            hidden = repo / ".pilot-puppy" / "PLAN.md"
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


if __name__ == "__main__":
    unittest.main()
