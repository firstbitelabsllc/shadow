from __future__ import annotations

import json
import http.client
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from browser import board_projection, server


PLAN = """# Release notes

## Brief

- Project: release-notes
- Mode: ship
- Priority: 2
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
- Option B Consequence: Apply independent judgment across every relevant surface.
- Option C ID: hold-release
- Option C: Hold the release
- Option C Consequence: Keep the Outcome open until new evidence exists.
- Proof ID: focused-tests
- Proof: tests/test_browser.py
- Proof Summary: Browser contract tests pass.
- Proof Delivery: delivered

## Tasks

### Release notes decision

- [pending] Choose the final review depth ~aa11 | proof: read tests/test_browser.py -> passes
- [pending] Decision receipt is durable ~bb22 (DoD) | proof: read .shadow/evidence -> recorded

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

    def test_decision_receipt_fsyncs_its_file_and_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, plan = self.make_repo(Path(dirname))
            document = server.plan_record(plan, repo)["outcome"]
            kinds = {"file": False, "dir": False}
            real_fsync = os.fsync

            def spy(fd: int) -> None:
                kinds["dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"] = True
                real_fsync(fd)

            with mock.patch.object(server.os, "fsync", side_effect=spy):
                server.write_decision_receipt(plan, document, "cold-review", 7)
        self.assertEqual(kinds, {"file": True, "dir": True})

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

    def test_browser_reads_and_writes_only_the_computer_board_entity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            portfolio = Path(dirname)
            home = portfolio / "home"
            home.mkdir()
            canonical = portfolio / "canonical"
            canonical.mkdir()
            plan = canonical / "PLAN.md"
            plan.write_text(PLAN, encoding="utf-8")
            git(canonical, "init", "-q")
            git(canonical, "config", "user.email", "test@example.invalid")
            git(canonical, "config", "user.name", "Test")
            git(canonical, "add", "PLAN.md")
            git(canonical, "commit", "-qm", "canonical")
            origin = "git@example.invalid:leo/sibling.git"
            git(canonical, "remote", "add", "origin", origin)

            first, _, warning = server.board_plan_records(canonical, home)
            self.assertIsNone(warning)
            identity = first["entities"][0]["id"]
            server._root_board.claim(
                plan,
                "~aa11",
                "seat-a",
                project="release-notes",
                priority=2,
                home=home,
            )
            server._root_board.set_priority(plan, 1, home=home)

            sibling = portfolio / "sibling"
            git(portfolio, "clone", "-q", str(canonical), str(sibling))
            git(sibling, "remote", "set-url", "origin", origin)
            (sibling / "PLAN.md").write_text(
                PLAN.replace("# Release notes", "# Wrong sibling bytes"),
                encoding="utf-8",
            )

            service = server.Server(("127.0.0.1", 0), portfolio, home=home)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("GET", "/api/plans")
                response = connection.getresponse()
                payload = json.loads(response.read())
                connection.close()
                self.assertEqual(response.status, 200, payload)
                self.assertEqual(payload["root_board_revision"], first["revision"] + 2)
                self.assertEqual(len(payload["plans"]), 1)
                record = payload["plans"][0]
                self.assertEqual(record["entity"], identity)
                self.assertEqual(record["title"], "Release notes")
                self.assertEqual(record["priority"], 1)
                self.assertEqual(record["resume"], "~aa11")
                self.assertEqual(record["owner"], "seat-a")
                self.assertEqual(record["board"]["state"], "working")

                body = json.dumps(
                    {
                        "entity": identity,
                        "root_board_revision": payload["root_board_revision"],
                        "option_id": "cold-review",
                        "revision": 7,
                    }
                )
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
                decided = connection.getresponse()
                receipt = json.loads(decided.read())
                connection.close()
                self.assertEqual(decided.status, 200, receipt)
                self.assertTrue((canonical / ".shadow" / "evidence").is_dir())
                self.assertFalse((sibling / ".shadow" / "evidence").exists())

                returned = server._root_board.release(
                    plan,
                    "~aa11",
                    resumes=["~aa11", "~bb22"],
                    owner="seat-a",
                    reason="handback",
                    home=home,
                )
                self.assertIsNotNone(returned)
                self.assertTrue(returned[1])
                _, records, warning = server.board_plan_records(portfolio, home)
                self.assertIsNone(warning)
                self.assertNotIn("owner", records[0])
                self.assertEqual(records[0]["resume"], "~aa11")
                self.assertEqual(records[0]["board"]["state"], "ready")
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)

    def test_browser_projects_every_open_milestone_with_checkpoint_owners(self) -> None:
        multi = """# m20 — Rotation

## Brief

- Project: rotation
- Mode: ship
- Priority: 2

## Tasks

### M0 — retired history
- [completed] old work landed ~zz11 | proof: cmd true
- [completed] old work closed ~zz22 (DoD) | proof: read x -> y

### M1 — groundwork waits
- [completed] groundwork landed ~aa11 | proof: cmd true
- [pending] dependent work ~bb22 | proof: cmd true | needs: ~cc33
- [pending] groundwork closes ~bb23 (DoD) | proof: read x -> y | needs: ~bb22

### M2 — release is moving
- [in_progress] live release work ~cc33 | proof: cmd true
- [blocked] upstream is unavailable ~dd44 | proof: cmd true
- [pending] release closes ~ee55 (DoD) | proof: read x -> y | needs: ~cc33

## Progress

- 2026-08-09T22:00:00Z ~zz11 PROOF true -> ok
- 2026-08-09T23:00:00Z ~zz22 PROOF x -> y
- 2026-08-10T00:00:00Z ~aa11 PROOF true -> ok
"""
        with tempfile.TemporaryDirectory() as dirname:
            repo = Path(dirname) / "repo"
            home = Path(dirname) / "home"
            repo.mkdir()
            home.mkdir()
            plan = repo / "PLAN.md"
            plan.write_text(multi, encoding="utf-8")
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.invalid")
            git(repo, "config", "user.name", "Test")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "-qm", "fixture")
            _, _, warning = server.board_plan_records(repo, home)
            self.assertIsNone(warning)
            server._root_board.claim(
                plan,
                "~cc33",
                "seat-a",
                project="rotation",
                priority=2,
                home=home,
            )
            _, records, warning = server.board_plan_records(repo, home)

        self.assertIsNone(warning)
        self.assertEqual(records[0]["title"], "Rotation")
        milestones = records[0]["milestones"]
        self.assertEqual(
            [milestone["title"] for milestone in milestones],
            ["groundwork waits", "release is moving"],
        )
        self.assertFalse(milestones[0]["current"])
        self.assertTrue(milestones[1]["current"])
        checkpoints = {
            checkpoint["id"]: checkpoint
            for milestone in milestones
            for checkpoint in milestone["checkpoints"]
        }
        self.assertEqual(checkpoints["~bb22"]["availability"], "waiting")
        self.assertEqual(checkpoints["~cc33"]["availability"], "claimed")
        self.assertEqual(checkpoints["~cc33"]["owners"], ["seat-a"])
        self.assertEqual(checkpoints["~dd44"]["availability"], "blocked")

    def test_browser_renderer_iterates_the_rotation_in_brief_and_board_views(self) -> None:
        source = (Path(server.__file__).parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            source.count("for (const milestone of rotationOf(plan))"),
            3,
        )
        self.assertNotIn("const milestoneTitle = plan.board?.milestone", source)

    def test_symlinked_canonical_plan_cannot_import_external_milestones(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            repo = root / "repo"
            home.mkdir()
            repo.mkdir()
            plan = repo / "PLAN.md"
            plan.write_text(PLAN, encoding="utf-8")
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.invalid")
            git(repo, "config", "user.name", "Test")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "-qm", "fixture")
            server.board_plan_records(repo, home)
            outside = root / "outside-PLAN.md"
            outside.write_text(
                PLAN.replace("# Release notes", "# External authority"),
                encoding="utf-8",
            )
            plan.unlink()
            plan.symlink_to(outside)

            _, records, warning = server.board_plan_records(root / "empty", home)

        self.assertIsNotNone(warning)
        self.assertTrue(records[0]["broken"])
        self.assertEqual(records[0]["milestones"], [])
        self.assertNotIn("External authority", json.dumps(records[0]))

    def test_decision_post_refuses_a_last_good_board_when_refresh_warns(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo, _ = self.make_repo(root)
            payload, _, warning = server.board_plan_records(repo, home)
            self.assertIsNone(warning)
            identity = payload["entities"][0]["id"]
            broken = repo / "broken" / "PLAN.md"
            broken.parent.mkdir()
            broken.write_bytes(b"\xff\xfe")

            service = server.Server(("127.0.0.1", 0), repo, home=home)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("GET", "/api/plans")
                response = connection.getresponse()
                current = json.loads(response.read())
                connection.close()
                self.assertEqual(response.status, 200, current)
                self.assertIsNotNone(current["warning"])
                self.assertEqual(current["root_board_revision"], payload["revision"])

                body = json.dumps(
                    {
                        "entity": identity,
                        "root_board_revision": current["root_board_revision"],
                        "option_id": "cold-review",
                        "revision": 7,
                    }
                )
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
                refused = connection.getresponse()
                error = json.loads(refused.read())
                connection.close()

                self.assertEqual(refused.status, 400, error)
                self.assertIn("refresh failed", error["error"])
                self.assertFalse((repo / ".shadow" / "evidence").exists())
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)

    def test_decision_receipt_holds_board_cas_until_receipt_is_durable(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo, plan = self.make_repo(root)
            payload, _, warning = server.board_plan_records(repo, home)
            self.assertIsNone(warning)
            identity = payload["entities"][0]["id"]
            original_receipt = server.write_decision_receipt
            original_flock = server._root_board.fcntl.flock
            mutation_attempted = threading.Event()
            mutation_done = threading.Event()
            mutation_threads: list[threading.Thread] = []

            def observed_flock(descriptor: int, operation: int) -> None:
                if (
                    mutation_threads
                    and threading.current_thread() is mutation_threads[0]
                    and operation & server._root_board.fcntl.LOCK_EX
                ):
                    mutation_attempted.set()
                original_flock(descriptor, operation)

            def wrapped_receipt(*args, **kwargs):
                def mutate_priority() -> None:
                    server._root_board.set_priority(plan, 1, home=home)
                    mutation_done.set()

                worker = threading.Thread(target=mutate_priority)
                mutation_threads.append(worker)
                worker.start()
                self.assertTrue(mutation_attempted.wait(2), "mutator never reached the board CAS")
                self.assertFalse(mutation_done.is_set(), "board changed before receipt durability")
                return original_receipt(*args, **kwargs)

            service = server.Server(("127.0.0.1", 0), repo, home=home)
            service.RequestHandlerClass.log_message = lambda *args: None
            service_thread = threading.Thread(target=service.serve_forever, daemon=True)
            service_thread.start()
            port = service.server_address[1]
            try:
                body = json.dumps(
                    {
                        "entity": identity,
                        "root_board_revision": payload["revision"],
                        "option_id": "cold-review",
                        "revision": 7,
                    }
                )
                with mock.patch.object(
                    server._root_board.fcntl, "flock", side_effect=observed_flock
                ), mock.patch.object(
                    server, "write_decision_receipt", side_effect=wrapped_receipt
                ):
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
                    receipt = json.loads(response.read())
                    connection.close()
                self.assertEqual(response.status, 200, receipt)
                mutation_threads[0].join(timeout=2)
                self.assertTrue(mutation_done.is_set())
                self.assertEqual(
                    server._root_board.snapshot(home=home)["revision"],
                    payload["revision"] + 1,
                )
                self.assertTrue((repo / ".shadow" / "evidence").is_dir())
            finally:
                service.shutdown()
                service.server_close()
                service_thread.join(timeout=2)

    def test_deleted_claimed_row_is_a_loud_broken_board_not_a_working_card(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo, plan = self.make_repo(root)
            payload, _, warning = server.board_plan_records(repo, home)
            self.assertIsNone(warning)
            server._root_board.claim(
                plan,
                "~aa11",
                "seat-a",
                project="release-notes",
                priority=2,
                home=home,
            )
            plan.write_text(PLAN.replace("~aa11", "~cc33"), encoding="utf-8")
            git(repo, "add", "project/PLAN.md")
            git(repo, "commit", "-qm", "replace claimed row")

            _, records, warning = server.board_plan_records(repo, home)

            self.assertIsNotNone(warning)
            self.assertIn("broken", warning)
            self.assertTrue(records[0]["broken"])
            self.assertEqual(records[0]["board"]["state"], "broken")
            self.assertIn("~aa11", records[0]["contract_error"])

    def test_deleted_canonical_plan_is_a_loud_broken_board(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo, plan = self.make_repo(root)
            _, _, warning = server.board_plan_records(repo, home)
            self.assertIsNone(warning)
            plan.unlink()

            _, records, warning = server.board_plan_records(root / "empty", home)

            self.assertIsNotNone(warning)
            self.assertIn("broken", warning)
            self.assertTrue(records[0]["broken"])
            self.assertEqual(records[0]["board"]["state"], "broken")
            self.assertIn("missing or unreadable", records[0]["contract_error"])

    def test_decision_write_rejects_a_stale_board_revision_and_entity_id(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo, plan = self.make_repo(root)
            payload, _, warning = server.board_plan_records(repo, home)
            self.assertIsNone(warning)
            identity = payload["entities"][0]["id"]
            server._root_board.set_priority(plan, 1, home=home)
            with self.assertRaisesRegex(server.BrowserError, "changed"):
                server.board_entity_plan(identity, payload["revision"], home)

            current = server._root_board.snapshot(home=home)
            self.assertIsNotNone(current)
            git(repo, "remote", "add", "origin", "git@example.invalid:org/moved.git")
            with self.assertRaisesRegex(server.BrowserError, "stale"):
                server.board_entity_plan(identity, current["revision"], home)

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

                body = json.dumps({
                    "entity": "0" * 64,
                    "root_board_revision": 0,
                    "option_id": "ship-now",
                    "revision": 7,
                })
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
            payload, _, warning = server.board_plan_records(repo, repo)
            self.assertIsNone(warning)
            identity = payload["entities"][0]["id"]
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

                body = json.dumps({
                    "entity": identity,
                    "root_board_revision": payload["revision"],
                    "option_id": "cold-review",
                    "revision": 7,
                })
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
            board, _, warning = server.board_plan_records(repo, repo)
            self.assertIsNone(warning)
            identity = board["entities"][0]["id"]
            service = server.Server(("127.0.0.1", 0), repo)
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                failure = PermissionError(
                    f"[Errno 13] Permission denied: '{repo}/.shadow/evidence'"
                )
                body = json.dumps({
                    "entity": identity,
                    "root_board_revision": board["revision"],
                    "option_id": "ship-now",
                    "revision": 7,
                })
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


class AV4PlanGetsABoardBriefNotAnError(unittest.TestCase):
    """The board renders the v4 grammar; a missing v3 Outcome is not a defect.

    The v3 typed-Outcome block was retired from the grammar on 2026-08-09, but
    the browser kept demanding it — so EVERY current plan on a machine failed
    "outcome must be a string" and the board rendered a wall of dead cards.
    These tests pin the split: the v4 board brief is total, and the v3
    contract can only error for a plan that actually still carries its keys.
    """

    def _record(self, plan_text: str):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = root / "repo"
            plan = repo / "proj" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(plan_text, encoding="utf-8")
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.invalid")
            git(repo, "config", "user.name", "Test")
            git(repo, "add", "proj/PLAN.md")
            git(repo, "commit", "-qm", "fixture")
            return server.plan_record(plan, repo)

    def test_a_v4_plan_without_the_retired_outcome_key_is_not_an_error(self) -> None:
        record = self._record(BOARD_PLAN)
        self.assertIsNone(record["contract_error"],
                          "the retired v3 key's absence was reported as a defect")
        board = record["board"]
        self.assertEqual(board["state"], "working")
        self.assertEqual(board["milestone"]["title"], "Gift flow live")
        self.assertEqual(board["milestone"]["counts"],
                         {"pending": 1, "in_progress": 1, "blocked": 0, "completed": 1})
        self.assertIn("Checkout smoke green", board["milestone"]["current"])
        self.assertEqual(board["milestone"]["dod"]["state"], "pending")

    def test_a_v3_plan_still_gets_its_rich_briefing(self) -> None:
        record = self._record(PLAN)
        self.assertIsNone(record["contract_error"])
        self.assertIsNotNone(record["briefing"])
        self.assertIsNotNone(record["board"])

    def test_a_v3_plan_with_malformed_outcome_still_reports_its_error(self) -> None:
        broken = PLAN.replace("- Outcome State: needs_input", "- Outcome State: vibing")
        record = self._record(broken)
        self.assertIsNotNone(record["contract_error"],
                             "a malformed v3 contract must still be named")
        self.assertIsNotNone(record["board"], "the board brief is total even then")

    def test_states_ready_blocked_and_resting_derive_from_the_rows(self) -> None:
        ready = BOARD_PLAN.replace("- [in_progress]", "- [pending]")
        self.assertEqual(self._record(ready)["board"]["state"], "ready")
        blocked = BOARD_PLAN.replace("- [in_progress]", "- [blocked]").replace("- [pending]", "- [blocked]")
        self.assertEqual(self._record(blocked)["board"]["state"], "blocked")
        resting = (BOARD_PLAN.replace("- [in_progress]", "- [completed]")
                             .replace("- [pending]", "- [completed]"))
        self.assertEqual(self._record(resting)["board"]["state"], "resting")

    def test_a_plan_with_no_tasks_is_an_honest_empty_not_a_crash(self) -> None:
        record = self._record("# Just notes\n\nno sections at all\n")
        self.assertEqual(record["board"]["state"], "empty")
        self.assertIsNone(record["contract_error"])

    def test_a_pre_grammar_plan_reads_unmigrated_not_empty(self) -> None:
        essay = "# Old plan\n\n## Goal\n" + "\n".join(
            f"line {i} of a real pre-grammar document" for i in range(14)
        )
        self.assertEqual(self._record(essay)["board"]["state"], "unmigrated")

    def test_open_contradictions_are_counted_resolved_ones_are_not(self) -> None:
        with_contra = BOARD_PLAN + (
            "\n## Contradictions\n\n- one open thing | opened 2026-08-09\n"
            "- RESOLVED 2026-08-09 in favor of X | winner: X\n"
        )
        self.assertEqual(self._record(with_contra)["board"]["contradictions_open"], 1)


class TheGalleryShowsEveryStateHonestly(unittest.TestCase):
    """The gallery is the in-house component catalog: fixture plan TEXTS run
    through the production pipeline. Each fixture names the state it must
    project to, and this class holds that promise — the golden that stops the
    catalog from drifting into decoration."""

    def test_every_fixture_projects_to_its_named_state(self) -> None:
        for record in server.gallery_records():
            self.assertEqual(
                record["board"]["state"], record["expected_state"],
                f"fixture {record['gallery_name']} promises "
                f"{record['expected_state']!r} but projects {record['board']['state']!r}")

    def test_every_board_state_the_projection_can_produce_has_a_fixture(self) -> None:
        producible = {"working", "ready", "blocked", "resting", "unmigrated", "empty"}
        covered = {r["board"]["state"] for r in server.gallery_records()}
        self.assertEqual(producible - covered, set(),
                         "a state the board can show has no fixture — the catalog is incomplete")

    def test_normal_state_fixtures_lint_clean_so_cards_render_normally(self) -> None:
        # A blocking lint finding puts the red error treatment on the card, so
        # a "normal" state fixture that lints red is showing the WRONG state.
        # (Found by review: completed rows lacked their PROOF receipts.)
        for record in server.gallery_records():
            if record["expected_state"] in {"working", "ready", "blocked", "resting"}:
                # The card goes red on EITHER arm of the production condition
                # (`!parse_ok || blocking`), so the golden holds both.
                self.assertTrue(
                    record["lint"]["parse_ok"],
                    f"fixture {record['gallery_name']} fails to parse and would render as an error card")
                self.assertEqual(
                    record["lint"]["blocking"], 0,
                    f"fixture {record['gallery_name']} lints red and would render as an error card")

    def test_the_gallery_page_carries_no_inline_style_the_csp_would_discard(self) -> None:
        html = (server.STATIC / "gallery.html").read_text(encoding="utf-8")
        self.assertNotIn("<style", html,
                         "inline styles are discarded by style-src 'self'; use style.css")

    def test_the_v3_rich_brief_has_a_fixture_with_choices(self) -> None:
        rich = [r for r in server.gallery_records() if r["briefing"]]
        self.assertTrue(rich, "no fixture exercises the v3 rich brief card")
        self.assertTrue(any(r["briefing"]["choices"] for r in rich),
                        "no fixture shows a waiting decision")

    def test_the_gallery_page_and_api_are_served(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            service = server.Server(("127.0.0.1", 0), Path(dirname))
            service.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            port = service.server_address[1]
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("GET", "/gallery")
                page = connection.getresponse()
                self.assertEqual(page.status, 200)
                self.assertIn("gallery.js", page.read().decode("utf-8"))
                connection.request("GET", "/api/gallery")
                payload = json.loads(connection.getresponse().read().decode("utf-8"))
                self.assertGreaterEqual(len(payload["plans"]), 6)
                connection.close()
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)


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



class TheBoardSpeaksHumanNotMachine(unittest.TestCase):
    """The owner graded the board F for printing machine text on human cards.

    The projection is where the fix holds: no commit hash, no receipt
    grammar keyword, no milestone code number, and no mid-word cut ever
    reaches a card. The renderer can then trust every string it is handed.
    """

    PLAN = (
        "# T\n\n## Brief\n\n- Project: demo\n- Mode: ship\n\n## Tasks\n\n"
        "### M3 — Soft cloudy props for tables\n"
        "- [completed] groundwork ~aa11 | proof: cmd true\n"
        "- [blocked] the remembered soft cloudy direction is represented by an "
        "evidence-backed shortlist, every finalist has a photo and factual vendor "
        "receipt, the list is simple and image-first, and any unavailable route is "
        "named with its exact wake predicate so a cold reader can resume without "
        "asking anything of anyone ever again ~aa12 (DoD) | proof: gate owner\n\n"
        "## Progress\n\n"
        "- 2026-08-10T14:13:05Z STRUCT Final authority read — objective SHA "
        "`b30773705e835d97f9792ea81e3775fa19dbb238f7d5de13bc1e88160827f5fc`, "
        "Snowcubes `origin/main` and both clean authority checkouts agree ~aa11\n"
    )

    def _board(self):
        return board_projection.project_board_brief(self.PLAN)

    def test_a_milestone_title_carries_no_code_number(self) -> None:
        title = self._board()["milestone"]["title"]
        self.assertEqual(title, "Soft cloudy props for tables")
        self.assertNotRegex(title, r"^M\d+")

    def test_the_latest_change_is_structured_and_hash_free(self) -> None:
        change = self._board()["latest_change"]
        self.assertEqual(change["when"], "2026-08-10T14:13:05Z")
        self.assertEqual(change["kind"], "Plan structure changed")
        self.assertNotIn("STRUCT", change["summary"])
        self.assertNotRegex(change["summary"], r"[0-9a-f]{12}")
        self.assertNotIn("~aa11", change["summary"])
        self.assertIn("authority", change["summary"])

    def test_a_bounded_text_never_cuts_mid_word(self) -> None:
        dod = self._board()["milestone"]["dod"]["text"]
        self.assertTrue(dod.endswith("…"), "fixture must exercise the bound")
        # The last kept token must be a COMPLETE word from the source row —
        # "any unavailable r…" (half of "route") is the debug-dump tell the
        # owner photographed.
        source_words = set(self.PLAN.split())
        last = dod.rstrip("…").split()[-1]
        self.assertIn(
            last, source_words,
            f"the bound cut inside a word: …{last!r}",
        )
        self.assertLessEqual(len(dod), board_projection.MAX_ROW_TEXT)

    def test_a_plain_note_without_keyword_still_projects(self) -> None:
        plan = self.PLAN.replace(
            "- 2026-08-10T14:13:05Z STRUCT Final authority read",
            "- a hand-written note with no stamp and no keyword at all",
        )
        change = board_projection.project_board_brief(plan)["latest_change"]
        self.assertIsNone(change["when"])
        self.assertIsNone(change["kind"])
        self.assertIn("hand-written note", change["summary"])

    def test_a_private_path_in_a_progress_line_never_reaches_a_card(self) -> None:
        private_path = "/" + "Users" + "/someone/Development/private-client/PLAN.md"
        plan = self.PLAN.replace(
            "Final authority read — objective SHA "
            "`b30773705e835d97f9792ea81e3775fa19dbb238f7d5de13bc1e88160827f5fc`, "
            "Snowcubes `origin/main` and both clean authority checkouts agree ~aa11",
            f"read the canonical plan at {private_path} ~aa11",
        )
        change = board_projection.project_board_brief(plan)["latest_change"]
        # Assert over the WHOLE projected change, not just its summary: the
        # path must not survive in any field the renderer can print.
        self.assertNotIn(private_path, json.dumps(change))
        self.assertNotIn("private-client", json.dumps(change))
        self.assertIsNone(change["summary"])
        # The gate is surgical, not a blanket drop: when and kind still speak.
        self.assertEqual(change["when"], "2026-08-10T14:13:05Z")
        self.assertEqual(change["kind"], "Plan structure changed")

    def test_a_secret_shaped_progress_line_is_withheld_too(self) -> None:
        plan = self.PLAN.replace(
            "Snowcubes `origin/main`",
            "the token ghp_" + "a" * 30 + " rotated,",
        )
        change = board_projection.project_board_brief(plan)["latest_change"]
        self.assertIsNone(change["summary"])
        self.assertNotIn("ghp_", json.dumps(change))

    def test_a_brief_priority_carrying_a_path_is_withheld(self) -> None:
        private_path = "/" + "Users" + "/someone/Development/x"
        plan = self.PLAN.replace(
            "- Project: demo",
            f"- Project: demo\n- Priority: finish {private_path}",
        )
        self.assertIsNone(board_projection.project_board_brief(plan)["priority"])
        safe = self.PLAN.replace(
            "- Project: demo", "- Project: demo\n- Priority: finish the shortlist"
        )
        self.assertEqual(
            board_projection.project_board_brief(safe)["priority"],
            "finish the shortlist",
        )

    def test_the_gallery_record_never_prints_a_private_priority(self) -> None:
        """The gallery renders checked-in plan TEXT through record_from_text —
        the same path a fixture with a stray machine path would travel."""
        private_path = "/" + "Users" + "/someone/Development/x"
        plan = self.PLAN.replace(
            "- Project: demo",
            f"- Project: demo\n- Priority: ship {private_path}",
        )
        record = server.record_from_text(plan, "demo/PLAN.md", "demo")
        self.assertIsNone(record["board"]["priority"])
        self.assertNotIn(private_path, json.dumps(record["board"]))


if __name__ == "__main__":
    unittest.main()
