#!/usr/bin/env python3
"""The optional local ledger path has a producer reachable from the CLI.

Vidux ships local ledger readers in `vidux status`, `GET /api/ledger`, and the
browser Ledger tab. When a user configures that optional store, the public
checkpoint command must be able to append the corresponding proof/resume row.
The repository plan remains authority even when no ledger is configured.

These tests assert the end-to-end path a user actually walks, not the presence
of a verb: run the CLI, then read the ledger file back and check a row landed
with the right shape. A test that only asserted the dispatcher mentions
"checkpoint" would pass against a verb that emits nothing, which is the exact
failure this file exists to prevent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vidux"

PLAN_TEMPLATE = """# Test Plan

## Tasks

- [in_progress] {task}
- [pending] a second task so the plan is not empty

## Progress
"""


class CheckpointTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name)
        for args in (
            ["git", "init", "-q", "-b", "main", str(self.repo)],
            ["git", "-C", str(self.repo), "config", "user.email", "t@example.com"],
            ["git", "-C", str(self.repo), "config", "user.name", "T"],
        ):
            subprocess.run(args, check=True, capture_output=True)
        self.plan = self.repo / "PLAN.md"
        self.plan.write_text(PLAN_TEMPLATE.format(task="wire the emitter"))
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "PLAN.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "seed"],
            check=True,
            capture_output=True,
        )
        # The ledger must pre-exist: the config discovers a FILE, and an absent
        # path means "ledger unavailable", which turns every emitter into a
        # silent no-op. That silence is what hid this defect.
        self.ledger = self.repo / "activity.jsonl"
        self.ledger.write_text("")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["VIDUX_LEDGER_FILE"] = str(self.ledger)
        env.pop("VIDUX_LEDGER_APPEND", None)
        return subprocess.run(
            [str(CLI), *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(self.repo),
            env=env,
        )

    def _rows(self) -> list[dict]:
        return [
            json.loads(line)
            for line in self.ledger.read_text().splitlines()
            if line.strip()
        ]

    def test_checkpoint_is_a_dispatched_command(self) -> None:
        """Not sufficient on its own -- see the emit test -- but a verb that
        does not dispatch cannot emit, so this failing localises the cause."""
        result = self._run("checkpoint")
        self.assertNotIn("unknown command", result.stderr)
        self.assertNotEqual(
            result.returncode,
            2,
            f"checkpoint should reach its script, not the unknown-command branch: {result.stderr}",
        )

    def test_checkpoint_appears_in_top_level_help(self) -> None:
        result = self._run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("checkpoint", result.stdout)

    def test_checkpoint_help_discloses_proof_and_opt_in_commit(self) -> None:
        result = self._run("help", "checkpoint")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--proof", result.stdout)
        self.assertIn("--commit", result.stdout)
        self.assertIn("remain uncommitted", result.stdout)

    def test_completion_without_proof_does_not_mutate_or_commit(self) -> None:
        before_plan = self.plan.read_text()
        before_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        result = self._run(
            "checkpoint",
            str(self.plan),
            "wire the emitter",
            "unproved completion",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--proof is required", result.stderr)
        self.assertEqual(self.plan.read_text(), before_plan)
        self.assertEqual(self._rows(), [])
        after_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(after_head, before_head)

    def test_running_the_cli_actually_lands_a_ledger_row(self) -> None:
        """The assertion that matters.

        Mutant this must kill: adding the dispatch but pointing it at a script
        that does not source the emitter. The verb would exist, help would list
        it, exit status would be 0 -- and the ledger would stay empty, which is
        precisely the state this repo shipped in.
        """
        before = len(self._rows())
        result = self._run(
            "checkpoint",
            str(self.plan),
            "wire the emitter",
            "emitter reachable from the CLI",
            "--proof",
            "unit gate passed",
        )
        self.assertEqual(result.returncode, 0, f"{result.stdout}\n{result.stderr}")
        rows = self._rows()
        self.assertGreater(
            len(rows),
            before,
            "checkpoint ran but emitted no ledger row -- the producer is still orphaned",
        )
        checkpoint_rows = [
            row
            for row in rows
            if "checkpoint" in json.dumps(row).lower()
        ]
        self.assertTrue(
            checkpoint_rows,
            f"a row landed but none of them is a checkpoint event: {rows}",
        )
        self.assertTrue(
            all(row.get("handoff_status") == "needs_review" for row in checkpoint_rows),
            checkpoint_rows,
        )
        self.assertTrue(
            all("commit" not in row for row in checkpoint_rows),
            checkpoint_rows,
        )
        self.assertTrue(
            all("unit gate passed" in row.get("proof", "") for row in checkpoint_rows),
            checkpoint_rows,
        )

    def test_emitted_row_carries_the_plan_it_checkpointed(self) -> None:
        """A row that cannot be traced to a plan is ledger volume, not proof."""
        self._run(
            "checkpoint",
            str(self.plan),
            "wire the emitter",
            "emitter reachable from the CLI",
            "--proof",
            "unit gate passed",
        )
        rows = self._rows()
        self.assertTrue(rows, "no rows emitted")
        blob = json.dumps(rows)
        self.assertIn(
            "PLAN.md",
            blob,
            f"emitted rows do not reference the plan path: {rows}",
        )
        self.assertIn("unit gate passed", blob)

    def test_checkpoint_leaves_plan_uncommitted_by_default(self) -> None:
        before_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        result = self._run(
            "checkpoint",
            str(self.plan),
            "wire the emitter",
            "safe local checkpoint",
            "--proof",
            "unit gate passed",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("left uncommitted", result.stdout)
        after_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(after_head, before_head)
        self.assertIn("PLAN.md", subprocess.run(
            ["git", "status", "--short"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout)

    def test_blocked_checkpoint_requires_a_concrete_blocker_before_mutation(self) -> None:
        before_plan = self.plan.read_text()
        result = self._run(
            "checkpoint",
            str(self.plan),
            "wire the emitter",
            "blocked without a reason",
            "--status",
            "blocked",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--blocker is required", result.stderr)
        self.assertEqual(self.plan.read_text(), before_plan)
        self.assertEqual(self._rows(), [])

    def test_commit_requires_explicit_flag(self) -> None:
        before_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        result = self._run(
            "checkpoint",
            str(self.plan),
            "wire the emitter",
            "explicit local commit",
            "--proof",
            "unit gate passed",
            "--commit",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        after_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertNotEqual(after_head, before_head)

    def test_explicit_commit_uses_the_target_repo_outside_caller_cwd(self) -> None:
        before_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        env = dict(os.environ)
        env["VIDUX_LEDGER_FILE"] = str(self.ledger)
        env.pop("VIDUX_LEDGER_APPEND", None)
        with tempfile.TemporaryDirectory() as outside:
            result = subprocess.run(
                [
                    str(CLI),
                    "checkpoint",
                    str(self.plan),
                    "wire the emitter",
                    "explicit outside-cwd commit",
                    "--proof",
                    "unit gate passed",
                    "--commit",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=outside,
                env=env,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        after_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertNotEqual(after_head, before_head)


if __name__ == "__main__":
    unittest.main(verbosity=1)
