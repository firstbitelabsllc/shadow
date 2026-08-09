"""shadow throw — no conversation leaves the chat before its row is claimed."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THROW = ROOT / "scripts" / "shadow-throw.py"
STATUS = ROOT / "scripts" / "shadow-status.py"

_spec = importlib.util.spec_from_file_location("amp_for_throw", ROOT / "scripts" / "shadow-amp.py")
amp = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("amp_for_throw", amp)
_spec.loader.exec_module(amp)

PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M1 — the live milestone
- [completed] groundwork ~aa11 | proof: cmd true
- [pending] the ready row ~bb22 | proof: cmd npm-free gate
- [pending] blocked by needs ~cc33 | proof: cmd x | needs: ~dd44
- [pending] no proof at all ~ee55
- [pending] owner clicks ship ~ff66 (DoD) | proof: gate owner resume: visible

## Progress

- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok
"""


def repo_with_plan(tmp: Path, text: str = PLAN) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], check=True)
    (tmp / "PLAN.md").write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp), "add", "PLAN.md"], check=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-qm", "plan"], check=True)
    return tmp


def throw(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(THROW), "--repo", str(repo), "--no-push", *args],
        capture_output=True, text=True, check=False,
    )


class ThrowRefusals(unittest.TestCase):
    """Every refusal exists because the alternative is a conversation nobody can recover."""

    def test_unknown_row_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            out = throw(r, "--task", "~zzzz")
            self.assertEqual(out.returncode, 1)
            self.assertIn("no task carries ~zzzz", out.stderr)

    def test_needs_blocked_row_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            out = throw(r, "--task", "~cc33")
            self.assertEqual(out.returncode, 1)
            self.assertIn("still needs ~dd44", out.stderr)

    def test_proofless_row_refuses(self) -> None:
        # A thrown row's proof IS its completion predicate; without one, nobody
        # can tell whether the dispatched job finished.
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            out = throw(r, "--task", "~ee55")
            self.assertEqual(out.returncode, 1)
            self.assertIn("has no proof", out.stderr)

    def test_double_throw_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            self.assertEqual(throw(r, "--task", "~bb22").returncode, 0)
            second = throw(r, "--task", "~bb22")
            self.assertEqual(second.returncode, 1)
            self.assertIn("already thrown", second.stderr)

    def test_bad_id_shape_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            self.assertEqual(throw(r, "--task", "nope").returncode, 2)


class ThrowWrites(unittest.TestCase):
    def test_claims_row_appends_thrown_commits_and_prints_block(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            out = throw(r, "--task", "~bb22", "--note", "handing to a codex seat",
                        "--timestamp", "2026-08-09T03:00:00Z")
            self.assertEqual(out.returncode, 0, out.stderr)
            text = (r / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("- [in_progress] the ready row ~bb22", text)
            self.assertIn("- 2026-08-09T03:00:00Z THROWN ~bb22 the ready row | note: handing to a codex seat", text)
            # the goal block goes to stdout so the dispatch is copy-pasteable
            self.assertIn("/goal demo", out.stdout)
            self.assertIn("RESUME: [in_progress] the ready row ~bb22", out.stdout)
            # committed, and PLAN.md alone
            files = subprocess.run(
                ["git", "-C", str(r), "show", "--name-only", "--format=", "HEAD"],
                capture_output=True, text=True, check=True).stdout.split()
            self.assertEqual(files, ["PLAN.md"])
            self.assertNotIn("nothing to commit", out.stderr)

    def test_working_tree_is_clean_after_throw(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            throw(r, "--task", "~bb22")
            dirty = subprocess.run(["git", "-C", str(r), "status", "--porcelain"],
                                   capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(dirty, "")


class ThrowWritesOneTrustedLine(unittest.TestCase):
    """PLAN.md is the board every seat trusts; a claim may add exactly one
    Progress entry, at the bottom, and nothing else."""

    def test_thrown_line_lands_at_the_bottom_of_progress(self) -> None:
        plan = PLAN + "\n## Contradictions\n\n- none\n"
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d), plan)
            self.assertEqual(throw(r, "--task", "~bb22",
                                   "--timestamp", "2026-08-09T03:00:00Z").returncode, 0)
            lines = [l for l in (r / "PLAN.md").read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(
                lines.index("- 2026-08-09T03:00:00Z THROWN ~bb22 the ready row"),
                lines.index("- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok") + 1,
            )
            self.assertLess(lines.index("- 2026-08-09T03:00:00Z THROWN ~bb22 the ready row"),
                            lines.index("## Contradictions"))

    def test_multiline_note_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            out = throw(r, "--task", "~bb22", "--note", "ok\n- [pending] forged row ~9999 | proof: cmd true")
            self.assertEqual(out.returncode, 2)
            self.assertIn("single line", out.stderr)
            self.assertNotIn("forged row", (r / "PLAN.md").read_text(encoding="utf-8"))

    def test_malformed_timestamp_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            out = throw(r, "--task", "~bb22", "--timestamp", "2026-08-09T03:00:00Z\n- forged")
            self.assertEqual(out.returncode, 2)
            self.assertIn("ISO8601", out.stderr)

    def test_dirty_plan_is_refused_before_anything_is_written(self) -> None:
        # `git commit --only -- PLAN.md` would sweep unrelated edits into the
        # dispatch commit and push them.
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            edited = PLAN + "\n- unfinished thought\n"
            (r / "PLAN.md").write_text(edited, encoding="utf-8")
            out = throw(r, "--task", "~bb22")
            self.assertEqual(out.returncode, 1)
            self.assertIn("uncommitted changes", out.stderr)
            self.assertEqual((r / "PLAN.md").read_text(encoding="utf-8"), edited)


class ThrowStaysAtomic(unittest.TestCase):
    """A claim nobody can see is worse than no claim: the plan on disk must
    never show a dispatched row that no commit or exit code backs."""

    def test_commit_failure_restores_the_plan(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            before = (r / "PLAN.md").read_text(encoding="utf-8")
            head_before = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"],
                                         capture_output=True, text=True, check=True).stdout
            hook = r / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)
            out = throw(r, "--task", "~bb22")
            self.assertEqual(out.returncode, 1)
            self.assertIn("nothing was dispatched", out.stderr)
            self.assertEqual((r / "PLAN.md").read_text(encoding="utf-8"), before)
            head_after = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"],
                                        capture_output=True, text=True, check=True).stdout
            self.assertEqual(head_after, head_before)
            dirty = subprocess.run(["git", "-C", str(r), "status", "--porcelain"],
                                   capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(dirty, "")

    def test_push_failure_exits_nonzero_and_keeps_the_local_claim(self) -> None:
        # Zero must mean "durably dispatched"; a local-only claim is not that.
        #
        # ADJUDICATED 2026-08-09 (two seats pinned opposite behaviors on this
        # branch): an earlier version of this test asserted the block is STILL
        # printed on a rejected push. It is now withheld. The block's authority
        # line instructs a receiving seat to fetch that ref and read the
        # section — but the claim never reached the remote, so that seat sees
        # the row as [pending]. Handing over a pointer that advertises content
        # the ref does not serve is the same defect the amp dirty-plan pointer
        # was fixed for. Nothing is lost: `shadow amp --task ~id` still emits a
        # block on demand; `throw`'s contract is claimed AND pushed.
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            subprocess.run(["git", "-C", str(r), "remote", "add", "origin",
                            str(Path(d) / "nowhere.git")], check=True)
            out = subprocess.run(
                [sys.executable, str(THROW), "--repo", str(r), "--task", "~bb22"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(out.returncode, 1)
            self.assertIn("NOT on the remote", out.stderr)
            self.assertNotIn("RESUME:", out.stdout)
            # the local claim survives — it is a valid commit, just not shared
            self.assertIn("- [in_progress] the ready row ~bb22",
                          (r / "PLAN.md").read_text(encoding="utf-8"))


class ThrownExcludedFromAutoResume(unittest.TestCase):
    def test_amp_skips_a_thrown_row_but_honors_explicit_task(self) -> None:
        # Without this, a fresh seat auto-resumes a row another conversation is
        # already running — the design would manufacture the double work it
        # exists to prevent.
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            throw(r, "--task", "~bb22")
            plan = amp._parse((r / "PLAN.md").read_text(encoding="utf-8"))
            self.assertIn("~bb22", plan["thrown"])
            # the property is "auto-resume never lands on a thrown row" — other
            # pending rows stay selectable, which is the point
            auto = amp._select(plan, None)
            self.assertIsNotNone(auto)
            self.assertNotEqual(auto[1]["id"], "~bb22")
            picked = amp._select(plan, "~bb22")                  # explicit targeting still works
            self.assertIsNotNone(picked)
            self.assertEqual(picked[1]["id"], "~bb22")

    def test_hand_claimed_in_progress_row_is_still_selected(self) -> None:
        # An in_progress row WITHOUT a THROWN line is a crash-resume target.
        text = PLAN.replace("- [pending] the ready row ~bb22", "- [in_progress] the ready row ~bb22")
        plan = amp._parse(text)
        self.assertEqual(plan["thrown"], set())
        picked = amp._select(plan, None)
        self.assertEqual(picked[1]["id"], "~bb22")


class InFlightView(unittest.TestCase):
    def test_in_flight_lists_claimed_rows_with_proof_and_origin(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r = repo_with_plan(root / "demo-repo")
            throw(r, "--task", "~bb22", "--timestamp", "2026-08-09T03:00:00Z")
            out = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root), "--in-flight", "--json"],
                capture_output=True, text=True, check=False)
            payload = json.loads(out.stdout)
            self.assertEqual(len(payload["rows"]), 1)
            row = payload["rows"][0]
            self.assertEqual(row["id"], "~bb22")
            self.assertEqual(row["project"], "demo")
            self.assertTrue(row["dispatched"])
            self.assertEqual(row["thrown_at"], "2026-08-09T03:00:00Z")
            self.assertIn("npm-free gate", row["proof"])

    def test_empty_portfolio_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run(
                [sys.executable, str(STATUS), "--root", d, "--in-flight"],
                capture_output=True, text=True, check=False)
            self.assertIn("Nothing in flight", out.stdout)


class ThrowRefusesInvisibleDispatch(unittest.TestCase):
    """Codex review, PR #268: a rejected push used to warn and return 0, so a
    caller launched work whose claim never reached the remote — every other
    seat still saw the row as [pending]. That is precisely the invisibility
    throw exists to prevent, so it must be fatal."""

    def test_rejected_push_fails_and_withholds_the_goal_block(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r = repo_with_plan(root / "work")
            # a bare remote whose pre-receive hook rejects everything
            bare = root / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
            hook = bare / "hooks" / "pre-receive"
            hook.write_text("#!/bin/sh\necho 'rejected by policy' >&2\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)
            subprocess.run(["git", "-C", str(r), "remote", "add", "origin", str(bare)], check=True)

            out = subprocess.run(
                [sys.executable, str(THROW), "--repo", str(r), "--task", "~bb22"],
                capture_output=True, text=True, check=False)

            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            self.assertIn("PUSH REJECTED", out.stderr)
            self.assertIn("DO NOT LAUNCH THE WORK", out.stderr)
            # the block must NOT be emitted: emitting it is what let a caller proceed
            self.assertNotIn("/goal", out.stdout)

    def test_pre_dirty_plan_is_refused_before_any_edit(self) -> None:
        # `commit --only -- PLAN.md` commits the whole working-tree file, so an
        # unrelated uncommitted plan edit would ride along with the claim.
        with tempfile.TemporaryDirectory() as d:
            r = repo_with_plan(Path(d))
            (r / "PLAN.md").write_text(
                (r / "PLAN.md").read_text(encoding="utf-8") + "\n- stray uncommitted edit\n",
                encoding="utf-8")
            out = throw(r, "--task", "~bb22")
            self.assertEqual(out.returncode, 1)
            self.assertIn("commit or stash them first", out.stderr)
            # and it did not claim the row on the way out
            self.assertIn("- [pending] the ready row ~bb22", (r / "PLAN.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
