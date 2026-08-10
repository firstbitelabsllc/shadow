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

- Project: release-notes
- Mode: ship
- Priority: 2

## Tasks

### Release notes

- [pending] Draft covers the shipped changes ~aa11 | proof: read tests/test_browser.py -> passes
- [pending] Release notes are published ~bb22 (DoD) | proof: read published notes -> visible

## Progress

- 2026-08-03: The bounded implementation is ready for review.
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

    def test_browser_reads_only_the_computer_board_entity(self) -> None:
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

                self.assertFalse((canonical / ".shadow" / "evidence").exists())
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
            2,
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


    def test_non_loopback_bind_is_rejected(self) -> None:
        self.assertEqual(server.main(["--host", "0.0.0.0", "--port", "7191", "--root", "."]), 2)


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
        self.assertNotIn("contract_error", record)
        self.assertNotIn("briefing", record)
        self.assertNotIn("outcome", record)
        board = record["board"]
        self.assertEqual(board["state"], "working")
        self.assertEqual(board["milestone"]["title"], "M1 — Gift flow live")
        self.assertEqual(board["milestone"]["counts"],
                         {"pending": 1, "in_progress": 1, "blocked": 0, "completed": 1})
        self.assertIn("Checkout smoke green", board["milestone"]["current"])
        self.assertEqual(board["milestone"]["dod"]["state"], "pending")


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
        self.assertNotIn("contract_error", record)

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


if __name__ == "__main__":
    unittest.main()
