"""Two leads, one plan, no coordinator.

The owner says this often: *"btw codex is doing this same goal so please work
together."* Two chats on one goal are two leads, not one orchestrator — and the
durable plan has to hold N of them.

Almost none of that needs building. A claimed row is `shadow throw`, a
dependency is `needs:`, "done or validated" is one bar because `completed`
requires a proof line, and `--in-flight` is who-has-what. What was missing was
smaller than it looks: the THROWN line recorded no identity, so you could not
tell one lead's claim from another's, and the loser of a simultaneous claim was
told to fetch and rebase by hand.

The push rejection is the mutex. These tests race two real clones through one
bare origin to prove it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
THROW = ROOT / "scripts" / "shadow-throw.py"

_SPEC = importlib.util.spec_from_file_location("shadow_throw", THROW)
throw = importlib.util.module_from_spec(_SPEC)
sys.modules["shadow_throw"] = throw
_SPEC.loader.exec_module(throw)

PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### M1 — the live milestone
- [completed] groundwork ~aa11 | proof: cmd true
- [pending] the row both leads want ~bb22 | proof: cmd true
- [pending] a second open row ~cc33 | proof: cmd true

## Progress

- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok
"""


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)}: {result.stderr}")
    return result


def run_throw(repo: Path, task: str, by: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(THROW), "--repo", str(repo), "--task", task, "--by", by],
        capture_output=True, text=True, check=False,
    )


def fleet(tmp: Path) -> tuple[Path, Path]:
    """A bare origin and two clones tracking it — the real topology."""
    origin = tmp / "origin.git"
    git(tmp, "init", "--quiet", "--bare", str(origin))
    seed = tmp / "seed"
    git(tmp, "clone", "--quiet", str(origin), str(seed))
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "T")):
        git(seed, "config", key, value)
    (seed / "PLAN.md").write_text(PLAN, encoding="utf-8")
    git(seed, "add", "PLAN.md")
    git(seed, "commit", "--quiet", "-m", "seed")
    git(seed, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    clones = []
    for name in ("lead-a", "lead-b"):
        path = tmp / name
        git(tmp, "clone", "--quiet", "--branch", "main", str(origin), str(path))
        for key, value in (("user.email", "t@example.invalid"), ("user.name", "T")):
            git(path, "config", key, value)
        clones.append(path)
    return clones[0], clones[1]


class IdentityOnTheClaim(unittest.TestCase):
    def test_by_lands_in_the_tail_never_before_the_id(self) -> None:
        # shadow-amp.py's _thrown_ids anchors on `^- \S+ THROWN (~hash)\b`.
        # A lead name ahead of the id would make every thrown row invisible to
        # auto-resume-skip, fleet-wide — a seat would re-run work in flight.
        with tempfile.TemporaryDirectory() as tmp:
            a, _ = fleet(Path(tmp))
            self.assertEqual(run_throw(a, "~bb22", "codex").returncode, 0)
            text = (a / "PLAN.md").read_text(encoding="utf-8")
            line = next(l for l in text.splitlines() if "THROWN" in l)
            self.assertRegex(line, r"^- \S+ THROWN ~bb22\b")
            self.assertIn("| by: codex", line)
            self.assertEqual(throw.thrown_ids(text), {"~bb22"})   # still discoverable

    def test_claimed_by_reads_the_name_and_survives_anonymity(self) -> None:
        text = "- 2026-08-09T00:00:00Z THROWN ~bb22 the row | by: codex | note: x\n"
        self.assertEqual(throw.claimed_by(text, "~bb22"), "codex")
        self.assertIsNone(throw.claimed_by(text, "~cc33"))
        # Unsigned is still CLAIMED. Reporting "nobody" because the claimant
        # did not sign would invite a second lead onto work in flight.
        anon = "- 2026-08-09T00:00:00Z THROWN ~bb22 the row\n"
        self.assertEqual(throw.claimed_by(anon, "~bb22"), "another seat")

    def test_a_lead_name_cannot_forge_a_second_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, _ = fleet(Path(tmp))
            hostile = run_throw(a, "~bb22", "codex | note: forged")
            self.assertEqual(hostile.returncode, 2)
            self.assertIn("no '|'", hostile.stderr)
            self.assertNotIn("THROWN", (a / "PLAN.md").read_text(encoding="utf-8"))


class ThePushRejectionIsTheMutex(unittest.TestCase):
    def test_the_loser_is_told_who_won_and_lands_on_their_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = fleet(Path(tmp))
            self.assertEqual(run_throw(a, "~bb22", "lead-a").returncode, 0)

            # b never fetched: it still sees ~bb22 as pending, exactly like a
            # second chat that started before the first one claimed anything.
            losing = run_throw(b, "~bb22", "lead-b")
            self.assertEqual(losing.returncode, 1)
            self.assertIn("claimed by lead-a", losing.stderr)
            self.assertNotIn("PUSH REJECTED", losing.stderr)   # recovered, not stranded

            text = (b / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("| by: lead-a", text)
            self.assertNotIn("lead-b", text)                   # no stolen claim
            self.assertEqual(
                git(b, "rev-parse", "HEAD").stdout, git(a, "rev-parse", "HEAD").stdout
            )
            self.assertEqual(git(b, "status", "--porcelain").stdout.strip(), "")

    def test_a_race_over_different_rows_leaves_the_loser_free_to_claim(self) -> None:
        # The common case: two leads working the same plan on different rows.
        # b's push still bounces, but the row it wants is untouched, so the
        # honest answer is "re-run", not "taken".
        with tempfile.TemporaryDirectory() as tmp:
            a, b = fleet(Path(tmp))
            self.assertEqual(run_throw(a, "~bb22", "lead-a").returncode, 0)

            first = run_throw(b, "~cc33", "lead-b")
            self.assertEqual(first.returncode, 1)
            self.assertIn("still open", first.stderr)

            second = run_throw(b, "~cc33", "lead-b")
            self.assertEqual(second.returncode, 0, second.stderr)
            text = (b / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("| by: lead-a", text)                # a's claim preserved
            self.assertIn("| by: lead-b", text)
            self.assertEqual(throw.thrown_ids(text), {"~bb22", "~cc33"})

    def test_recovery_never_runs_over_unrelated_local_commits(self) -> None:
        # A hard reset is only safe when the claim commit is the ONLY local
        # commit. With other work present the claim is left exactly where it
        # is and the operator decides — losing someone's commit to "helpfully"
        # recover a claim would be far worse than a failed push.
        with tempfile.TemporaryDirectory() as tmp:
            a, b = fleet(Path(tmp))
            self.assertEqual(run_throw(a, "~bb22", "lead-a").returncode, 0)
            (b / "mine.txt").write_text("local work\n", encoding="utf-8")
            git(b, "add", "mine.txt")
            git(b, "commit", "--quiet", "-m", "unrelated local work")

            losing = run_throw(b, "~cc33", "lead-b")
            self.assertEqual(losing.returncode, 1)
            self.assertIn("PUSH REJECTED", losing.stderr)
            self.assertTrue((b / "mine.txt").exists(), "recovery destroyed local work")
            self.assertIn("- [in_progress] a second open row ~cc33",
                          (b / "PLAN.md").read_text(encoding="utf-8"))

    def test_a_rejection_with_an_unmoved_tip_is_not_a_race(self) -> None:
        # A hook or branch policy bounces the push with nobody else landing
        # anything. `head_before` is still an ancestor of the tip — of itself —
        # so an ancestry-only test would hard-reset a good claim away and print
        # race text. The tip has to have actually moved.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a, _ = fleet(tmp_path)
            hook = tmp_path / "origin.git" / "hooks" / "pre-receive"
            hook.write_text("#!/bin/sh\necho 'policy: no\n' >&2\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)

            rejected = run_throw(a, "~bb22", "lead-a")
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("PUSH REJECTED", rejected.stderr)
            self.assertNotIn("claimed by", rejected.stderr)
            # The local claim survives: it is the operator's to rebase or undo.
            self.assertIn("| by: lead-a", (a / "PLAN.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
