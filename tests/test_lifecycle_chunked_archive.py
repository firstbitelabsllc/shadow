"""A fully completed milestone archives whatever its row count.

The 2-7 band is Milestone law for authoring an OPEN milestone; lint already
demoted the upper bound to a warning (PR #538) because real plans carry
9-19-row milestones. Lifecycle mirrored the band as an archive gate, which
meant a fully completed, fully proven 8+-row milestone could never leave the
hot plan. Measured 2026-09-21 on this computer: two plans (trysnowcubes-web,
cabinet) sat within 1 KB of the 262,144-byte hot-plan cap with exactly one
such milestone each.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.proc_fixture import git
from tests.test_lifecycle import (
    LINT,
    PLAN,
    apply_with_cas,
    make_repo,
    preview_cas,
    run,
)


def wide_plan(rows: int = 8, open_row: int | None = None) -> str:
    """One completed milestone with `rows` task rows, then a pending successor.

    `open_row` leaves that sibling `[pending]` (with no receipt) so the
    completion guard, not the row count, is what refuses.
    """
    tasks: list[str] = []
    receipts: list[str] = []
    for index in range(rows - 1):
        row_id = f"~a{index:03d}"
        state = "pending" if index == open_row else "completed"
        tasks.append(f"- [{state}] wide result {index} exists {row_id} | proof: cmd true\n")
        if state == "completed":
            receipts.append(f"- 2026-08-10T00:{index:02d}:00Z {row_id} PROOF true -> pass\n")
    tasks.append(
        "- [completed] wide result is accepted ~b000 (DoD) | proof: cmd true | needs: ~a000\n"
    )
    receipts.append("- 2026-08-10T00:59:00Z ~b000 PROOF true -> pass\n")
    return (
        "# Demo\n\n"
        "## Brief\n\n"
        "- Project: demo\n"
        "- Mode: ship\n\n"
        "## Tasks\n\n"
        "### Wide finished work\n"
        + "".join(tasks)
        + "\n### Next work\n"
        "- [pending] next result starts ~cc33 | proof: cmd true | needs: ~b000\n"
        "- [pending] next result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~cc33\n"
        "\n## Progress\n\n"
        + "".join(receipts)
        + "- 2026-08-10T01:00:00Z NOTE unrelated history remains live\n"
    )


def lint_returncode(repo: Path) -> tuple[int, str]:
    lint = subprocess.run(
        [sys.executable, str(LINT), str(repo / "PLAN.md")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return lint.returncode, lint.stdout + lint.stderr


class AWideCompletedMilestoneArchivesWhole(unittest.TestCase):
    def test_eight_completed_rows_archive_losslessly(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve(), wide_plan(8))
            original = (repo / "PLAN.md").read_text(encoding="utf-8")
            block = original[
                original.index("### Wide finished work") : original.index("### Next work")
            ]
            head = git(repo, "rev-parse", "HEAD")

            _, preview, cas = preview_cas(repo, "--milestone", "Wide finished work")
            self.assertEqual(preview["action"], "would_archive", preview)
            self.assertFalse(preview["changed"])
            self.assertEqual(preview["receipt_count"], 8, preview)
            self.assertEqual((repo / "PLAN.md").read_text(encoding="utf-8"), original)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)

            result, report, _ = apply_with_cas(
                repo, "--milestone", "Wide finished work", cas=cas,
            )
            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "archived", report)
            self.assertEqual(report["successor"], "Next work")

            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            archive = (repo / "docs" / "plan-archive" / "wide-finished-work.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(block, archive)
            for index in range(7):
                self.assertIn(f"~a{index:03d} PROOF true -> pass", archive)
                self.assertNotIn(f"~a{index:03d}", plan)
            self.assertNotIn("~b000", plan)
            self.assertIn("shadow:lifecycle:wide-finished-work", plan)
            self.assertIn("unrelated history remains live", plan)
            self.assertIn(
                "STRUCT archived milestone wide-finished-work | successor: Next work", plan,
            )
            code, output = lint_returncode(repo)
            self.assertEqual(code, 0, output)

    def test_a_wide_milestone_with_one_open_row_still_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve(), wide_plan(8, open_row=3))
            before = (repo / "PLAN.md").read_bytes()
            result, report = run(repo, "--milestone", "Wide finished work")
            self.assertNotEqual(result.returncode, 0, report)
            message = result.stderr + str(report)
            self.assertIn("not fully completed", message)
            self.assertNotIn("2-7", message)
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertFalse((repo / "docs" / "plan-archive").exists())


class TheNarrowBandStillBehavesAsBefore(unittest.TestCase):
    def test_a_two_row_milestone_still_archives(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve(), PLAN)
            result, report, _ = apply_with_cas(repo, "--milestone", "Finished work")
            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "archived", report)
            self.assertIn("shadow:lifecycle:finished-work", (repo / "PLAN.md").read_text())

    def test_a_one_row_milestone_still_refuses(self) -> None:
        plan = PLAN.replace("- [completed] first result exists ~aa11 | proof: cmd true\n", "")
        plan = plan.replace(" | needs: ~aa11", "")
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve(), plan)
            result, report = run(repo, "--milestone", "Finished work")
            self.assertNotEqual(result.returncode, 0, report)
            self.assertIn("at least 2", result.stderr + str(report))
            self.assertFalse((repo / "docs" / "plan-archive").exists())


if __name__ == "__main__":
    unittest.main()
