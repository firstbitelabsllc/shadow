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
                mock.patch.object(server, "run_drive_subprocess", return_value=completed) as run,
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
                mock.patch.object(server, "run_drive_subprocess", return_value=completed),
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
                mock.patch.object(server, "run_drive_subprocess", return_value=completed) as run,
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

    def test_drive_budgets_nest_and_the_cli_owns_the_deadline(self) -> None:
        worst_case = 3 * 2 * server.DRIVE_STEP_TIMEOUT_SECONDS
        self.assertGreaterEqual(server.DRIVE_LAUNCH_TIMEOUT_SECONDS, worst_case)
        self.assertGreaterEqual(server.DRIVE_ACCEPT_TIMEOUT_SECONDS, worst_case)
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            completed = subprocess.CompletedProcess([], 0, "{}", "")
            with (
                mock.patch.object(server, "repository_root", return_value=repo),
                mock.patch.object(server, "run_drive_subprocess", return_value=completed) as run,
            ):
                with self.assertRaises(server.BrowserError):
                    server.run_drive_action(plan, action="launch", session_id="f" * 32)
            command = run.call_args.args[0]
            self.assertIn("--timeout-seconds", command)
            self.assertIn(str(server.DRIVE_STEP_TIMEOUT_SECONDS), command)
            self.assertEqual(run.call_args.args[2], server.DRIVE_LAUNCH_TIMEOUT_SECONDS)

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

    def test_post_errors_never_reflect_exception_text(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, _ = self.make_repo(Path(dirname))
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                failure = PermissionError(
                    f"[Errno 13] Permission denied: '{repo}/.pilot-puppy/evidence'"
                )
                body = json.dumps({"plan": "project/PLAN.md"})
                with mock.patch.object(server, "run_drive_action", side_effect=failure):
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
                self.assertEqual(response.status, 400)
                self.assertNotIn(str(repo), payload["error"])
                self.assertNotIn("Errno", payload["error"])
                self.assertNotIn("evidence", payload["error"])
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)


BOARD_PLAN = """# Gift flow live

## Operator Brief

- Entity: snowcubes
- Mode: Close
- Milestone: Gift flow live on storefront

## Checkpoints

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
        self.assertEqual(record["entity"], "snowcubes")
        self.assertEqual(record["mode"], "close")
        self.assertEqual(record["milestone"], "Gift flow live on storefront")
        self.assertEqual(
            record["checkpoints"],
            {"pending": 1, "in_progress": 1, "blocked": 0, "completed": 1},
        )

    def test_board_fields_fall_back_safely(self) -> None:
        bare = "# Plain plan\n\n## Operator Brief\n\n- Outcome: something\n"
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), bare)
            record = server.plan_record(plan, repo)
        self.assertEqual(record["entity"], "gift-flow")
        self.assertIsNone(record["mode"])
        self.assertIsNone(record["milestone"])
        self.assertIsNone(record["checkpoints"])

    def test_board_fields_reject_unsafe_or_invalid_values(self) -> None:
        unsafe = (
            "# Unsafe\n\n## Operator Brief\n\n"
            "- Entity: Not A Slug!!\n"
            "- Mode: turbo\n"
            "- Milestone: Fix ~/Development/secret-client build\n"
        )
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_board_repo(Path(dirname), unsafe)
            record = server.plan_record(plan, repo)
        self.assertEqual(record["entity"], "gift-flow")
        self.assertIsNone(record["mode"])
        self.assertIsNone(record["milestone"])


if __name__ == "__main__":
    unittest.main()
