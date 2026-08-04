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

DRIVE_PACKET = """

<!-- pilot-puppy-drive.v1
{
  "schema": "pilot-puppy.drive.v1",
  "revision": 1,
  "lanes": [
    {
      "id": "improve-copy",
      "state": "ready",
      "task_kind": "dev",
      "summary": "Make the release note easier to understand.",
      "task": "Clarify the release note and keep the focused check green.",
      "allowed_paths": ["README.md"],
      "proof": ["python3", "-m", "unittest", "tests.test_browser"],
      "merge": "manual"
    }
  ]
}
-->
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

    def test_ready_work_preview_hides_instructions_paths_and_checks(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            plan.write_text(PLAN + DRIVE_PACKET, encoding="utf-8")
            record = server.plan_record(plan, repo)
        rendered = json.dumps(record, sort_keys=True)
        self.assertEqual(record["drive"]["state"], "ready")
        self.assertEqual(record["drive"]["ready_count"], 1)
        self.assertIn("Make the release note easier", rendered)
        for hidden in ("Clarify the release note", "allowed_paths", "tests.test_browser", "task_kind"):
            self.assertNotIn(hidden, rendered)

    def test_drive_command_projection_has_no_task_or_provider_details(self) -> None:
        session = {
            "schema": "pilot-puppy.drive-session.v1",
            "revision": 1,
            "session_id": "a" * 32,
            "state": "prepared",
            "plan_sha256": "b" * 64,
            "base_sha256": "c" * 40,
            "lanes": [
                {
                    "id": "improve-copy",
                    "observation_id": "d" * 32,
                    "role": "dev",
                    "host": "cursor",
                    "route_sha256": "e" * 64,
                    "status": "prepared",
                    "scope_ok": None,
                    "proof_ok": None,
                    "merge_ok": None,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            completed = subprocess.CompletedProcess([], 0, json.dumps(session), "")
            with (
                mock.patch.object(server, "repository_root", return_value=repo),
                mock.patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                projection = server.run_drive_action(plan, action="prepare")
        self.assertEqual(projection, {
            "session": "a" * 32,
            "state": "prepared",
            "work_count": 1,
            "finished_count": 0,
            "needs_attention_count": 0,
        })
        rendered = json.dumps(projection, sort_keys=True)
        self.assertNotIn("cursor", rendered)
        self.assertNotIn("dev", rendered)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, str(server.SCRIPTS / "pilot-puppy-drive.py"), "prepare"])
        self.assertIn("--json", command)

    def test_drive_launch_returns_a_partial_local_work_update(self) -> None:
        session = {
            "schema": "pilot-puppy.drive-session.v1",
            "revision": 1,
            "session_id": "a" * 32,
            "state": "finished",
            "plan_sha256": "b" * 64,
            "base_sha256": "c" * 40,
            "lanes": [{"status": "needs_attention"}],
        }
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            completed = subprocess.CompletedProcess([], 1, json.dumps(session), "expected local work result")
            with (
                mock.patch.object(server, "repository_root", return_value=repo),
                mock.patch.object(server.subprocess, "run", return_value=completed),
            ):
                projection = server.run_drive_action(plan, action="launch", session_id="a" * 32)
        self.assertEqual(projection["state"], "finished")
        self.assertEqual(projection["finished_count"], 0)
        self.assertEqual(projection["needs_attention_count"], 1)

    def test_drive_accept_projects_only_fully_rechecked_local_work(self) -> None:
        session = {
            "schema": "pilot-puppy.drive-session.v1",
            "revision": 1,
            "session_id": "a" * 32,
            "state": "accepted",
            "plan_sha256": "b" * 64,
            "base_sha256": "c" * 40,
            "lanes": [{"status": "passed", "scope_ok": True, "proof_ok": True, "merge_ok": True}],
        }
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            completed = subprocess.CompletedProcess([], 0, json.dumps(session), "")
            with (
                mock.patch.object(server, "repository_root", return_value=repo),
                mock.patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                projection = server.run_drive_action(plan, action="accept", session_id="a" * 32)
        self.assertEqual(projection, {
            "session": "a" * 32,
            "state": "accepted",
            "work_count": 1,
            "finished_count": 1,
            "needs_attention_count": 0,
        })
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, str(server.SCRIPTS / "pilot-puppy-drive.py"), "accept"])
        self.assertIn("--session", command)

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

    def test_http_prepares_ready_work_only_from_the_loopback_page(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname))
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                response_value = {
                    "session": "f" * 32,
                    "state": "prepared",
                    "work_count": 1,
                    "finished_count": 0,
                    "needs_attention_count": 0,
                }
                body = json.dumps({"plan": "project/PLAN.md"})
                with mock.patch.object(server, "run_drive_action", return_value=response_value) as action:
                    connection = http.client.HTTPConnection("127.0.0.1", port)
                    connection.request(
                        "POST",
                        "/api/drive/prepare",
                        body=body,
                        headers={
                            "Content-Type": "application/json",
                            "Origin": f"http://127.0.0.1:{port}",
                        },
                    )
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    connection.close()
                self.assertEqual(response.status, 200)
                self.assertEqual(payload, {"drive": response_value, "ok": True})
                action.assert_called_once()
                self.assertEqual(action.call_args.kwargs, {"action": "prepare"})
                self.assertEqual(action.call_args.args[0], (repo / "project" / "PLAN.md").resolve())
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
