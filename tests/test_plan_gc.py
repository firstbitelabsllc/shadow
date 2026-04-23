"""
Tests for scripts/vidux-plan-gc.py.

Style matches test_vidux_contracts.py: stdlib unittest, no pip.
Each test builds a disposable plan dir in a tempdir and asserts on outcomes.

Run:
    python3 -m unittest tests.test_plan_gc -v
    # or
    python3 tests/test_plan_gc.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-plan-gc.py"


def run_script(plan_dir, *args):
    """Run the GC script. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args, str(plan_dir)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def make_plan(plan_dir, completed=0, pending=0, in_progress=0, blocked=0,
              multi_line_task=False):
    """Write a PLAN.md fixture with the requested task counts."""
    plan_path = plan_dir / "PLAN.md"
    lines = [
        "# Test Plan",
        "",
        "## Purpose",
        "Test fixture.",
        "",
        "## Tasks",
    ]
    for i in range(1, completed + 1):
        lines.append(f"- [completed] T{i}: task {i} [Evidence: fixture] [Shipped: sha{i}]")
        if multi_line_task and i == 1:
            lines.append("  [Fix: src/foo.ts:42] [Tests: tests/foo.test.ts]")
            lines.append("  extra context for T1 preserved as indented continuation.")
    for i in range(1, pending + 1):
        lines.append(f"- [pending] P{i}: pending task {i} [Evidence: fixture] [ETA: 1h]")
    for i in range(1, in_progress + 1):
        lines.append(f"- [in_progress] IP{i}: working {i} [Evidence: fixture] [ETA: 2h]")
    for i in range(1, blocked + 1):
        lines.append(f"- [blocked] B{i}: blocked task {i} [Blocker: needs auth]")
    lines += [
        "",
        "## Decision Log",
        "- [DIRECTION] [2026-04-22] test fixture direction, must survive.",
        "",
        "## Progress",
        "- [2026-04-22] initial setup, must survive.",
        "",
    ]
    plan_path.write_text("\n".join(lines))


def make_inbox(plan_dir, entries=0):
    inbox = plan_dir / "INBOX.md"
    lines = ["# Inbox", ""]
    for i in range(1, entries + 1):
        lines.append(f"- entry {i}: triage item {i}")
    lines.append("")
    inbox.write_text("\n".join(lines))


def make_investigations(plan_dir, fresh=0, stale=0):
    inv = plan_dir / "investigations"
    inv.mkdir(exist_ok=True)
    # Fresh: current mtime
    for i in range(1, fresh + 1):
        (inv / f"fresh-{i}.md").write_text(f"# Fresh investigation {i}\n")
    # Stale: set mtime to 200 days ago
    stale_mtime = time.time() - (200 * 86400)
    for i in range(1, stale + 1):
        f = inv / f"stale-{i}.md"
        f.write_text(f"# Stale investigation {i}\n")
        os.utime(f, (stale_mtime, stale_mtime))


class PlanGCTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vidux-plan-gc-")
        self.plan_dir = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- completed-tasks target -------------------------------------------

    def test_under_soft_cap_is_noop(self):
        make_plan(self.plan_dir, completed=25, pending=1)
        before = (self.plan_dir / "PLAN.md").read_text()
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(before, (self.plan_dir / "PLAN.md").read_text(),
                         "Under soft cap should not modify PLAN.md")
        self.assertIn("under cap", out)
        self.assertFalse((self.plan_dir / "ARCHIVE.md").exists())

    def test_soft_cap_archives_down_to_target(self):
        make_plan(self.plan_dir, completed=35, pending=1, in_progress=1)
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0, f"exit=0 for soft cap; got {rc}; out={out}")
        plan_text = (self.plan_dir / "PLAN.md").read_text()
        completed_after = plan_text.count("\n- [completed]")
        self.assertEqual(completed_after, 20)
        # pending + in_progress survive
        self.assertIn("- [pending] P1:", plan_text)
        self.assertIn("- [in_progress] IP1:", plan_text)
        # Archive file created with 15 tasks + header
        self.assertTrue((self.plan_dir / "ARCHIVE.md").exists())
        archive_text = (self.plan_dir / "ARCHIVE.md").read_text()
        self.assertIn("# Archived Tasks", archive_text)
        self.assertEqual(archive_text.count("\n- [completed]"), 15)

    def test_hard_cap_exits_2(self):
        make_plan(self.plan_dir, completed=55, pending=1)
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 2, f"hard cap must exit 2; got {rc}")
        self.assertIn("HARD CAP EXCEEDED", out)
        # Still archives down to target
        plan_text = (self.plan_dir / "PLAN.md").read_text()
        self.assertEqual(plan_text.count("\n- [completed]"), 20)

    def test_no_tasks_section_is_graceful(self):
        (self.plan_dir / "PLAN.md").write_text(
            "# No Tasks Plan\n\n## Purpose\nFree-form plan.\n\n## Progress\n- done.\n"
        )
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        self.assertIn("no ## Tasks section", out)

    def test_no_plan_md_is_graceful(self):
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        self.assertIn("no PLAN.md", out)

    def test_oldest_tasks_archived_first(self):
        make_plan(self.plan_dir, completed=31)
        run_script(self.plan_dir)
        archive = (self.plan_dir / "ARCHIVE.md").read_text()
        plan = (self.plan_dir / "PLAN.md").read_text()
        # First 11 tasks (T1..T11) should be in archive; T12..T31 remain
        for i in range(1, 12):
            self.assertIn(f"- [completed] T{i}:", archive)
            self.assertNotIn(f"- [completed] T{i}:", plan)
        for i in range(12, 32):
            self.assertIn(f"- [completed] T{i}:", plan)

    def test_multi_line_task_continuation_preserved(self):
        """An archived task with indented continuation lines keeps them attached."""
        make_plan(self.plan_dir, completed=31, multi_line_task=True)
        run_script(self.plan_dir)
        archive = (self.plan_dir / "ARCHIVE.md").read_text()
        # T1 has continuation. It must be archived WITH its continuation lines.
        self.assertIn("- [completed] T1: task 1", archive)
        self.assertIn("[Fix: src/foo.ts:42]", archive)
        self.assertIn("extra context for T1 preserved", archive)

    def test_decision_log_and_progress_survive(self):
        """Archival must only touch ## Tasks section."""
        make_plan(self.plan_dir, completed=35)
        run_script(self.plan_dir)
        plan = (self.plan_dir / "PLAN.md").read_text()
        self.assertIn("## Decision Log", plan)
        self.assertIn("test fixture direction, must survive", plan)
        self.assertIn("## Progress", plan)
        self.assertIn("initial setup, must survive", plan)

    def test_idempotent_after_archive(self):
        """Second run under-cap must be a no-op (no double-archive)."""
        make_plan(self.plan_dir, completed=35)
        run_script(self.plan_dir)
        archive_first = (self.plan_dir / "ARCHIVE.md").read_text()
        plan_first = (self.plan_dir / "PLAN.md").read_text()
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(archive_first, (self.plan_dir / "ARCHIVE.md").read_text(),
                         "Second run must not append to archive")
        self.assertEqual(plan_first, (self.plan_dir / "PLAN.md").read_text(),
                         "Second run must not modify plan")

    # ---- investigations target --------------------------------------------

    def test_stale_investigations_moved_to_archive(self):
        make_plan(self.plan_dir, completed=1)
        make_investigations(self.plan_dir, fresh=2, stale=3)
        rc, _, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        inv = self.plan_dir / "investigations"
        archive = inv / "archive"
        self.assertTrue(archive.is_dir())
        # 3 stale moved, 2 fresh remain in place
        self.assertEqual(len(list(archive.glob("stale-*.md"))), 3)
        self.assertEqual(len(list(inv.glob("fresh-*.md"))), 2)
        self.assertEqual(len(list(inv.glob("stale-*.md"))), 0)

    def test_no_investigations_dir_is_graceful(self):
        make_plan(self.plan_dir, completed=1)
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        self.assertIn("no investigations/", out)

    # ---- inbox target -----------------------------------------------------

    def test_inbox_under_cap_is_noop(self):
        make_plan(self.plan_dir, completed=1)
        make_inbox(self.plan_dir, entries=15)
        before = (self.plan_dir / "INBOX.md").read_text()
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(before, (self.plan_dir / "INBOX.md").read_text())
        self.assertIn("under cap", out)

    def test_inbox_over_cap_trims_oldest(self):
        make_plan(self.plan_dir, completed=1)
        make_inbox(self.plan_dir, entries=25)
        rc, out, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        inbox_text = (self.plan_dir / "INBOX.md").read_text()
        # Kept newest 20 (entry 6..entry 25); oldest 5 archived
        self.assertEqual(inbox_text.count("\n- entry"), 20)
        self.assertNotIn("entry 1:", inbox_text)
        self.assertNotIn("entry 5:", inbox_text)
        self.assertIn("entry 6:", inbox_text)
        self.assertIn("entry 25:", inbox_text)
        # Archive created under evidence/
        archives = list((self.plan_dir / "evidence").glob("*-inbox-archive.md"))
        self.assertEqual(len(archives), 1)
        arch_text = archives[0].read_text()
        for i in range(1, 6):
            self.assertIn(f"- entry {i}:", arch_text)

    def test_inbox_preserves_preamble(self):
        make_plan(self.plan_dir, completed=1)
        inbox = self.plan_dir / "INBOX.md"
        header = (
            "# Inbox\n\n"
            "Triage drops here. Max 20 entries; oldest archive to evidence/.\n\n"
        )
        entries = "\n".join(f"- e{i}" for i in range(1, 30)) + "\n"
        inbox.write_text(header + entries)
        rc, _, _ = run_script(self.plan_dir)
        self.assertEqual(rc, 0)
        after = inbox.read_text()
        self.assertTrue(after.startswith("# Inbox"))
        self.assertIn("Triage drops here", after)
        self.assertEqual(after.count("\n- e"), 20)

    # ---- flags ------------------------------------------------------------

    def test_dry_run_writes_nothing(self):
        make_plan(self.plan_dir, completed=35)
        make_inbox(self.plan_dir, entries=25)
        make_investigations(self.plan_dir, stale=2)
        plan_before = (self.plan_dir / "PLAN.md").read_text()
        inbox_before = (self.plan_dir / "INBOX.md").read_text()
        inv_before = sorted(os.listdir(self.plan_dir / "investigations"))
        rc, out, _ = run_script(self.plan_dir, "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("DRY-RUN", out)
        self.assertEqual(plan_before, (self.plan_dir / "PLAN.md").read_text())
        self.assertEqual(inbox_before, (self.plan_dir / "INBOX.md").read_text())
        self.assertEqual(inv_before, sorted(os.listdir(self.plan_dir / "investigations")))
        self.assertFalse((self.plan_dir / "ARCHIVE.md").exists())

    def test_json_output_is_valid_json(self):
        make_plan(self.plan_dir, completed=35)
        rc, out, _ = run_script(self.plan_dir, "--dry-run", "--json")
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload["dry_run"], True)
        self.assertFalse(payload["hard_cap_exceeded"])
        targets = {t["target"] for t in payload["targets"]}
        self.assertEqual(targets, {"completed-tasks", "investigations", "inbox"})
        completed = next(t for t in payload["targets"] if t["target"] == "completed-tasks")
        self.assertEqual(completed["archived"], 15)
        self.assertEqual(completed["completed_before"], 35)
        self.assertEqual(completed["completed_after"], 20)

    def test_json_hard_cap_exit_2(self):
        make_plan(self.plan_dir, completed=55)
        rc, out, _ = run_script(self.plan_dir, "--json")
        self.assertEqual(rc, 2)
        payload = json.loads(out.strip())
        self.assertTrue(payload["hard_cap_exceeded"])


if __name__ == "__main__":
    unittest.main()
