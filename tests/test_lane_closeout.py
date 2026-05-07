"""Tests for scripts/vidux-lane-closeout.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-lane-closeout.py"

spec = importlib.util.spec_from_file_location("vidux_lane_closeout", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# parse_plan_tasks
# ---------------------------------------------------------------------------


class ParsePlanTasksTests(unittest.TestCase):
    def test_extracts_only_tasks_section_lines(self):
        text = (
            "# Plan\n"
            "## Evidence\n"
            "- [completed] FAKE-99: not a real task — outside ## Tasks\n"
            "## Tasks\n"
            "- [completed] LI-1: shipped thing\n"
            "- [in_progress] LI-2: working\n"
            "- [pending] LI-3: queued\n"
            "## Decision Log\n"
            "- [completed] FAKE-100: also outside\n"
        )
        tasks = mod.parse_plan_tasks(text)
        self.assertEqual([t.id for t in tasks], ["LI-1", "LI-2", "LI-3"])
        self.assertEqual(
            [t.status for t in tasks],
            ["completed", "in_progress", "pending"],
        )

    def test_returns_empty_when_no_tasks_section(self):
        text = "# Plan\n## Evidence\n- [completed] LI-1: ignored\n"
        self.assertEqual(mod.parse_plan_tasks(text), [])

    def test_handles_blocked_and_cancelled_states(self):
        text = (
            "## Tasks\n"
            "- [blocked] LI-1: stuck\n"
            "- [cancelled] LI-2: dropped\n"
        )
        tasks = mod.parse_plan_tasks(text)
        self.assertEqual([t.status for t in tasks], ["blocked", "cancelled"])

    def test_indented_task_line_still_parsed(self):
        text = "## Tasks\n  - [pending] LI-9: indented\n"
        tasks = mod.parse_plan_tasks(text)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "LI-9")


# ---------------------------------------------------------------------------
# assess_tasks_terminal
# ---------------------------------------------------------------------------


class TasksTerminalTests(unittest.TestCase):
    def test_ok_when_all_completed(self):
        tasks = [mod.Task("LI-1", "completed"), mod.Task("LI-2", "completed")]
        gate = mod.assess_tasks_terminal(tasks)
        self.assertTrue(gate.ok)
        self.assertEqual(gate.detail["blockers"], [])

    def test_completed_or_cancelled_both_terminal(self):
        tasks = [mod.Task("LI-1", "completed"), mod.Task("LI-2", "cancelled")]
        gate = mod.assess_tasks_terminal(tasks)
        self.assertTrue(gate.ok)

    def test_blocks_on_pending_task(self):
        tasks = [mod.Task("LI-1", "completed"), mod.Task("LI-7", "pending")]
        gate = mod.assess_tasks_terminal(tasks)
        self.assertFalse(gate.ok)
        self.assertEqual(gate.detail["blockers"],
                         [{"id": "LI-7", "status": "pending"}])

    def test_blocks_on_in_progress_or_blocked(self):
        tasks = [
            mod.Task("LI-1", "in_progress"),
            mod.Task("LI-2", "blocked"),
        ]
        gate = mod.assess_tasks_terminal(tasks)
        self.assertFalse(gate.ok)
        self.assertEqual(len(gate.detail["blockers"]), 2)

    def test_self_task_id_excluded_from_block(self):
        tasks = [
            mod.Task("LI-1", "completed"),
            mod.Task("LI-7", "pending"),
        ]
        gate = mod.assess_tasks_terminal(tasks, self_task_id="LI-7")
        self.assertTrue(gate.ok)
        self.assertEqual(gate.detail["blockers"], [])

    def test_self_task_does_not_mask_other_pending(self):
        tasks = [
            mod.Task("LI-1", "pending"),
            mod.Task("LI-7", "pending"),
        ]
        gate = mod.assess_tasks_terminal(tasks, self_task_id="LI-7")
        self.assertFalse(gate.ok)
        self.assertEqual(gate.detail["blockers"],
                         [{"id": "LI-1", "status": "pending"}])


# ---------------------------------------------------------------------------
# assess_audit
# ---------------------------------------------------------------------------


class AuditGateTests(unittest.TestCase):
    def test_ok_on_green(self):
        gate = mod.assess_audit({"overall": "green"})
        self.assertTrue(gate.ok)
        self.assertEqual(gate.detail["overall"], "green")

    def test_ok_on_yellow(self):
        gate = mod.assess_audit({"overall": "yellow"})
        self.assertTrue(gate.ok)

    def test_blocks_on_red(self):
        gate = mod.assess_audit({"overall": "red"})
        self.assertFalse(gate.ok)
        self.assertEqual(gate.detail["overall"], "red")

    def test_skipped_when_envelope_none(self):
        gate = mod.assess_audit(None)
        self.assertTrue(gate.ok)
        self.assertEqual(gate.detail["overall"], "skipped")


# ---------------------------------------------------------------------------
# assess_sync
# ---------------------------------------------------------------------------


class SyncGateTests(unittest.TestCase):
    def test_ok_when_all_zero(self):
        per_repo = [
            {"repo": "vidux", "results": [
                {"plan": "p1", "pushed": 0, "inbox_appended": 0, "errors": []},
            ]},
            {"repo": "strongyes-web", "results": [
                {"plan": "p2", "pushed": 0, "inbox_appended": 0, "errors": []},
            ]},
        ]
        gate = mod.assess_sync(per_repo)
        self.assertTrue(gate.ok)
        self.assertEqual(gate.detail["drift"], [])
        self.assertEqual(gate.detail["errors"], [])

    def test_drift_blocks(self):
        per_repo = [
            {"repo": "vidux", "results": [
                {"plan": "p1", "pushed": 3, "inbox_appended": 0, "errors": []},
            ]},
        ]
        gate = mod.assess_sync(per_repo)
        self.assertFalse(gate.ok)
        self.assertEqual(gate.detail["drift"],
                         [{"repo": "vidux", "pushed": 3, "inbox_appended": 0}])

    def test_inbox_appended_drift_blocks(self):
        per_repo = [
            {"repo": "x", "results": [
                {"plan": "p", "pushed": 0, "inbox_appended": 5, "errors": []},
            ]},
        ]
        gate = mod.assess_sync(per_repo)
        self.assertFalse(gate.ok)

    def test_errors_block(self):
        per_repo = [
            {"repo": "x", "results": [
                {"plan": "p", "pushed": 0, "inbox_appended": 0, "errors": ["boom"]},
            ]},
        ]
        gate = mod.assess_sync(per_repo)
        self.assertFalse(gate.ok)
        self.assertEqual(gate.detail["errors"],
                         [{"repo": "x", "errors": ["boom"]}])

    def test_auto_promote_blocks_skipped(self):
        per_repo = [
            {"repo": "x", "results": [
                {"plan": "p", "pushed": 0, "inbox_appended": 0, "errors": []},
                {"_kind": "auto_promote", "promoted": 4, "errors": []},
            ]},
        ]
        gate = mod.assess_sync(per_repo)
        self.assertTrue(gate.ok)

    def test_skipped_when_per_repo_none(self):
        gate = mod.assess_sync(None)
        self.assertTrue(gate.ok)
        self.assertTrue(gate.detail["skipped"])


# ---------------------------------------------------------------------------
# closeout_status orchestration
# ---------------------------------------------------------------------------


class CloseoutStatusTests(unittest.TestCase):
    def test_closed_when_all_gates_ok(self):
        out = mod.closeout_status(
            tasks=[mod.Task("LI-1", "completed")],
            audit={"overall": "green"},
            sync=[],
            self_task_id=None,
        )
        self.assertEqual(out["status"], "CLOSED")
        self.assertTrue(out["gates"]["tasks_terminal"]["ok"])
        self.assertTrue(out["gates"]["audit_overall"]["ok"])
        self.assertTrue(out["gates"]["sync_drift"]["ok"])

    def test_open_when_audit_red(self):
        out = mod.closeout_status(
            tasks=[mod.Task("LI-1", "completed")],
            audit={"overall": "red"},
            sync=[],
            self_task_id=None,
        )
        self.assertEqual(out["status"], "OPEN")
        self.assertFalse(out["gates"]["audit_overall"]["ok"])

    def test_open_when_pending_task_outside_self(self):
        out = mod.closeout_status(
            tasks=[
                mod.Task("LI-1", "pending"),
                mod.Task("LI-7", "pending"),
            ],
            audit={"overall": "green"},
            sync=[],
            self_task_id="LI-7",
        )
        self.assertEqual(out["status"], "OPEN")
        self.assertFalse(out["gates"]["tasks_terminal"]["ok"])

    def test_closed_when_self_task_excused(self):
        out = mod.closeout_status(
            tasks=[
                mod.Task("LI-1", "completed"),
                mod.Task("LI-7", "pending"),
            ],
            audit={"overall": "yellow"},
            sync=[],
            self_task_id="LI-7",
        )
        self.assertEqual(out["status"], "CLOSED")

    def test_no_network_path_skipped_audit_and_sync_pass(self):
        # When audit/sync are None (skipped), gates pass; tasks_terminal still
        # evaluates honestly.  This matches the --no-network CLI path.
        out = mod.closeout_status(
            tasks=[mod.Task("LI-1", "completed")],
            audit=None,
            sync=None,
            self_task_id=None,
        )
        self.assertEqual(out["status"], "CLOSED")
        self.assertEqual(out["gates"]["audit_overall"]["overall"], "skipped")
        self.assertTrue(out["gates"]["sync_drift"]["skipped"])


# ---------------------------------------------------------------------------
# run_closeout — integration of plan parsing + injected runners
# ---------------------------------------------------------------------------


class RunCloseoutTests(unittest.TestCase):
    def _write_plan(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        )
        tmp.write(text)
        tmp.close()
        return Path(tmp.name)

    def test_runs_with_injected_runners(self):
        plan = self._write_plan(
            "## Tasks\n"
            "- [completed] LI-1: shipped\n"
            "- [pending] LI-7: closeout\n"
        )
        try:
            out = mod.run_closeout(
                plan_path=plan,
                self_task_id="LI-7",
                repos=["vidux"],
                no_network=False,
                audit_script=Path("/nonexistent"),
                inbox_sync=Path("/nonexistent"),
                runners={
                    "run_audit": lambda: {"overall": "green"},
                    "run_sync": lambda: [
                        {"repo": "vidux", "results": [
                            {"pushed": 0, "inbox_appended": 0, "errors": []},
                        ]},
                    ],
                },
            )
            self.assertEqual(out["status"], "CLOSED")
            self.assertEqual(out["self_task"], "LI-7")
            self.assertIn("closeout_at", out)
            self.assertEqual(out["plan"], str(plan))
        finally:
            plan.unlink()

    def test_no_network_skips_runners(self):
        plan = self._write_plan(
            "## Tasks\n- [completed] LI-1: only shipped task\n"
        )
        try:
            sentinel = {"audit_called": 0}

            def boom():  # pragma: no cover - should never be invoked
                sentinel["audit_called"] += 1
                raise AssertionError("audit should not be called under --no-network")

            out = mod.run_closeout(
                plan_path=plan,
                self_task_id=None,
                repos=["vidux"],
                no_network=True,
                audit_script=Path("/nonexistent"),
                inbox_sync=Path("/nonexistent"),
                runners={"run_audit": boom, "run_sync": boom},
            )
            self.assertEqual(out["status"], "CLOSED")
            self.assertEqual(sentinel["audit_called"], 0)
        finally:
            plan.unlink()

    def test_open_when_pending_task_unaccounted(self):
        plan = self._write_plan(
            "## Tasks\n"
            "- [pending] LI-1: still open\n"
            "- [pending] LI-7: closeout itself\n"
        )
        try:
            out = mod.run_closeout(
                plan_path=plan,
                self_task_id="LI-7",
                repos=["vidux"],
                no_network=True,
                audit_script=Path("/nonexistent"),
                inbox_sync=Path("/nonexistent"),
            )
            self.assertEqual(out["status"], "OPEN")
            blockers = out["gates"]["tasks_terminal"]["blockers"]
            self.assertEqual(blockers, [{"id": "LI-1", "status": "pending"}])
        finally:
            plan.unlink()


# ---------------------------------------------------------------------------
# CLI wrapping
# ---------------------------------------------------------------------------


class CLITests(unittest.TestCase):
    @staticmethod
    def _silent_main(argv):
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return mod.main(argv)

    def test_main_exits_2_when_plan_missing(self):
        rc = self._silent_main([
            "--plan", "/nonexistent/PLAN.md",
            "--no-network",
        ])
        self.assertEqual(rc, 2)

    def test_main_exits_0_on_closed_via_no_network(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("## Tasks\n- [completed] LI-1: done\n")
            path = f.name
        try:
            rc = self._silent_main([
                "--plan", path,
                "--no-network",
            ])
            self.assertEqual(rc, 0)
        finally:
            Path(path).unlink()

    def test_main_exits_1_when_pending_task_not_self(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "## Tasks\n"
                "- [completed] LI-1: done\n"
                "- [pending] LI-2: not self\n"
            )
            path = f.name
        try:
            rc = self._silent_main([
                "--plan", path,
                "--self", "LI-7",
                "--no-network",
            ])
            self.assertEqual(rc, 1)
        finally:
            Path(path).unlink()

    def test_default_repos_used_when_repo_flag_absent(self):
        # Direct sanity check on the constant; CLI path is exercised above.
        self.assertIn("vidux", mod.DEFAULT_REPOS)
        self.assertIn("strongyes-web", mod.DEFAULT_REPOS)
        self.assertIn("resplit-web", mod.DEFAULT_REPOS)
        self.assertIn("resplit-ios", mod.DEFAULT_REPOS)


if __name__ == "__main__":
    unittest.main()
