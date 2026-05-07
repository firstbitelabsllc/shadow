"""Tests for scripts/vidux-gh-merge-when-ready.py."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-gh-merge-when-ready.py"

spec = importlib.util.spec_from_file_location("vidux_gh_merge_when_ready", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


SHA_LATEST = "abc123def456"
SHA_OLDER = "0000000000aa"


def _ci_check(name: str, conclusion: str = "SUCCESS", status: str = "COMPLETED") -> dict:
    return {
        "__typename": "CheckRun",
        "name": name,
        "conclusion": conclusion,
        "status": status,
        "workflowName": "CI",
    }


def _review(login: str, state: str, oid: str) -> dict:
    return {
        "id": f"PRR_{login}_{state}_{oid[:6]}",
        "author": {"login": login},
        "state": state,
        "commit": {"oid": oid},
    }


def _view(*, checks: list[dict], reviews: list[dict], sha: str = SHA_LATEST) -> dict:
    return {
        "headRefOid": sha,
        "statusCheckRollup": checks,
        "reviews": reviews,
    }


class AssessTests(unittest.TestCase):
    def test_all_green_with_graphite_review_on_latest(self):
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("ShellCheck"),
                _ci_check("Graphite / AI Reviews", conclusion="SKIPPED"),
            ],
            reviews=[
                _review("graphite-app", "COMMENTED", SHA_LATEST),
            ],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertTrue(report.ready)
        self.assertEqual(report.reason, "all gates green")

    def test_pending_when_ci_still_running(self):
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("ShellCheck", conclusion="", status="IN_PROGRESS"),
            ],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertIn("ShellCheck", report.pending_checks)
        self.assertEqual(report.blockers, [])

    def test_pending_when_required_bot_has_not_reviewed_latest_sha(self):
        view = _view(
            checks=[_ci_check("Contract tests")],
            reviews=[
                _review("graphite-app", "COMMENTED", SHA_OLDER),
                _review("leojkwan", "COMMENTED", SHA_LATEST),
            ],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertIn("graphite-app", report.pending_bots)

    def test_blocked_on_failed_check(self):
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("ShellCheck", conclusion="FAILURE"),
            ],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertTrue(any("ShellCheck" in b for b in report.blockers))

    def test_blocked_on_changes_requested(self):
        view = _view(
            checks=[_ci_check("Contract tests")],
            reviews=[
                _review("graphite-app", "COMMENTED", SHA_LATEST),
                _review("leojkwan", "CHANGES_REQUESTED", SHA_LATEST),
            ],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertTrue(any("changes-requested" in b for b in report.blockers))

    def test_skipped_check_counts_as_green(self):
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("Optional macos build", conclusion="SKIPPED"),
            ],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        view["__required_bots"] = ["graphite-app"]
        self.assertTrue(mod.assess(view).ready)

    def test_multiple_required_bots(self):
        view = _view(
            checks=[_ci_check("Contract tests")],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        view["__required_bots"] = ["graphite-app", "seer-by-sentry"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertIn("seer-by-sentry", report.pending_bots)

    def test_missing_head_ref_oid_is_blocker(self):
        view = {"statusCheckRollup": [], "reviews": []}
        view["__required_bots"] = []
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertIn("headRefOid", report.blockers)

    def test_graphite_silent_pass_via_checkrun_acks_bot(self):
        # Graphite passes silently via the AI Reviews CheckRun when it has
        # no concerns — no review entry is submitted. The helper must accept
        # that signal as ack for graphite-app.
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("Graphite / AI Reviews", conclusion="SUCCESS"),
            ],
            reviews=[],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertTrue(report.ready, msg=f"expected ready, got: {report.reason}")
        self.assertEqual(report.pending_bots, [])

    def test_graphite_checkrun_failure_is_blocker(self):
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("Graphite / AI Reviews", conclusion="FAILURE"),
            ],
            reviews=[],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("Graphite" in b for b in report.blockers),
            msg=f"expected Graphite blocker, got: {report.blockers}",
        )

    def test_graphite_checkrun_pending_keeps_bot_pending(self):
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("Graphite / AI Reviews", conclusion="", status="IN_PROGRESS"),
            ],
            reviews=[],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertFalse(report.ready)
        self.assertEqual(report.blockers, [])
        self.assertIn("graphite-app", report.pending_bots)

    def test_graphite_review_overrides_checkrun_failure(self):
        # If Graphite explicitly approved/commented on the latest SHA, that
        # weighs more than a CheckRun failure that may have been a transient
        # infra issue. Reviews are the binding signal when present.
        view = _view(
            checks=[
                _ci_check("Contract tests"),
                _ci_check("Graphite / AI Reviews", conclusion="FAILURE"),
            ],
            reviews=[_review("graphite-app", "APPROVED", SHA_LATEST)],
        )
        view["__required_bots"] = ["graphite-app"]
        report = mod.assess(view)
        self.assertTrue(report.ready, msg=f"expected ready, got: {report.reason}")


class PollLoopTests(unittest.TestCase):
    def test_returns_zero_when_first_view_is_ready(self):
        view = _view(
            checks=[_ci_check("Contract tests")],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        sleeps: list[float] = []
        code, report = mod.poll_until_ready(
            42,
            repo="leojkwan/vidux",
            max_wait_s=900,
            poll_interval_s=30,
            required_bots=["graphite-app"],
            fetch=lambda pr, repo: dict(view),
            sleep=sleeps.append,
            clock=lambda: 0.0,
        )
        self.assertEqual(code, 0)
        self.assertTrue(report.ready)
        self.assertEqual(sleeps, [])

    def test_polls_then_succeeds(self):
        pending = _view(
            checks=[_ci_check("Contract tests", conclusion="", status="IN_PROGRESS")],
            reviews=[],
        )
        ready = _view(
            checks=[_ci_check("Contract tests")],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        seq = iter([pending, pending, ready])
        sleeps: list[float] = []
        clock_t = [0.0]

        def fake_clock() -> float:
            return clock_t[0]

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock_t[0] += seconds

        code, _ = mod.poll_until_ready(
            42,
            repo=None,
            max_wait_s=900,
            poll_interval_s=30,
            required_bots=["graphite-app"],
            fetch=lambda pr, repo: dict(next(seq)),
            sleep=fake_sleep,
            clock=fake_clock,
        )
        self.assertEqual(code, 0)
        self.assertEqual(sleeps, [30, 30])

    def test_returns_one_when_cap_reached_pending(self):
        pending = _view(
            checks=[_ci_check("Contract tests", conclusion="", status="IN_PROGRESS")],
            reviews=[],
        )
        clock_t = [0.0]

        def fake_clock() -> float:
            return clock_t[0]

        def fake_sleep(seconds: float) -> None:
            clock_t[0] += seconds

        code, report = mod.poll_until_ready(
            42,
            repo=None,
            max_wait_s=60,
            poll_interval_s=30,
            required_bots=["graphite-app"],
            fetch=lambda pr, repo: dict(pending),
            sleep=fake_sleep,
            clock=fake_clock,
        )
        self.assertEqual(code, 1)
        self.assertFalse(report.ready)
        self.assertEqual(report.blockers, [])

    def test_returns_two_immediately_on_blocker(self):
        blocked = _view(
            checks=[_ci_check("Contract tests", conclusion="FAILURE")],
            reviews=[_review("graphite-app", "COMMENTED", SHA_LATEST)],
        )
        sleeps: list[float] = []
        code, report = mod.poll_until_ready(
            42,
            repo=None,
            max_wait_s=900,
            poll_interval_s=30,
            required_bots=["graphite-app"],
            fetch=lambda pr, repo: dict(blocked),
            sleep=sleeps.append,
            clock=lambda: 0.0,
        )
        self.assertEqual(code, 2)
        self.assertTrue(report.blockers)
        self.assertEqual(sleeps, [])


if __name__ == "__main__":
    unittest.main()
