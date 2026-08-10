"""Claim return and recovery are explicit, owner-safe lifecycle moves."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"

PLAN = """# Return fixture

## Brief

- Project: return-fixture
- Mode: ship
- Priority: 2

## Tasks

### The useful outcome
- [pending] inspect the result ~aa11 | proof: read artifact -> correct
- [pending] the outcome is proven ~bb22 (DoD) | proof: cmd true | needs: ~aa11

## Progress

- 2026-08-10T00:00:00Z NOTE seeded
"""


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)


def fixture(root: Path, *, remote: bool = False) -> tuple[Path, Path, dict[str, str]]:
    home = root / "home"
    portfolio = root / "portfolio"
    repo = portfolio / "project"
    home.mkdir()
    portfolio.mkdir()
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "user.email", "shadow-test@example.invalid")
    git(repo, "config", "user.name", "Shadow Test")
    if remote:
        git(repo, "remote", "add", "origin", "git@example.invalid:team/return-fixture.git")
    (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
    git(repo, "add", "PLAN.md")
    git(repo, "commit", "--quiet", "-m", "seed")
    env = {
        **os.environ,
        "HOME": str(home),
        "SHADOW_PORTFOLIO_ROOT": str(portfolio),
    }
    return repo, home, env


def run(env: dict[str, str], *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def payload(home: Path) -> dict:
    return json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))


class ReturnRequiresTheClaimOwner(unittest.TestCase):
    def test_legacy_selector_returns_its_canonical_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "inspect the result ~aa11",
                    "P9a~formats inspect the result ~3549",
                ).replace("needs: ~aa11", "needs: ~3549"),
                encoding="utf-8",
            )
            git(repo, "commit", "--quiet", "-am", "retain legacy selector")
            claimed = run(
                env, "throw", "--repo", str(repo), "--task", "~3549", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            returned = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "P9a~formats",
                "--by",
                "seat-a",
            )

            self.assertEqual(returned.returncode, 0, returned.stderr)
            self.assertIn("P9a~formats -> ~3549", returned.stdout)
            self.assertEqual(payload(home)["claims"], [])
            self.assertNotIn(
                "P9a~formats",
                (home / ".shadow" / "board.json").read_text(encoding="utf-8"),
            )

    def test_wrong_owner_cannot_close_and_right_owner_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            claimed = run(
                env,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            wrong = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-b",
            )
            self.assertEqual(wrong.returncode, 1, wrong.stderr)
            self.assertIn("seat-a", wrong.stderr)
            self.assertEqual(payload(home)["claims"][0]["owner"], "seat-a")

            right = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(right.returncode, 0, right.stderr)
            after = payload(home)
            self.assertEqual(after["claims"], [])
            revision = after["revision"]

            repeated = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertIn("already absent", repeated.stdout)
            self.assertEqual(payload(home)["revision"], revision)

    def test_never_claimed_row_is_reported_as_unchanged_not_returned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            registered = run(env, "status", "--json", cwd=repo)
            self.assertEqual(registered.returncode, 0, registered.stderr)

            result = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("already absent", result.stdout)
            self.assertNotIn("returned", result.stdout)

    def test_return_preserves_another_live_claim_as_resume_without_a_read_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(" | needs: ~aa11", ""),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "independent rows")
            for row, owner in (("~aa11", "seat-a"), ("~bb22", "seat-b")):
                claimed = run(
                    env, "throw", "--repo", str(repo), "--task", row, "--by", owner
                )
                self.assertEqual(claimed.returncode, 0, claimed.stderr)

            returned = run(
                env, "return", "--repo", str(repo), "--row", "~bb22", "--by", "seat-b"
            )

            self.assertEqual(returned.returncode, 0, returned.stderr)
            after = payload(home)
            self.assertEqual(after["entities"][0]["resume"], "~aa11")
            self.assertEqual(after["claims"][0]["owner"], "seat-a")
            revision = after["revision"]
            observed = run(env, "status", "--json", cwd=repo)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertEqual(payload(home)["revision"], revision)

    def test_duplicate_row_cannot_false_close_a_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            claimed = run(
                env, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            plan = repo / "PLAN.md"
            text = plan.read_text(encoding="utf-8")
            plan.write_text(
                text.replace(
                    "- [pending] inspect the result ~aa11",
                    "- [completed] inspect the result ~aa11",
                ).replace(
                    "## Progress",
                    "- [pending] duplicate target ~aa11 | proof: read artifact -> correct\n\n"
                    "## Progress",
                )
                + "- 2026-08-10T01:00:00Z ~aa11 PROOF observed -> pass\n",
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "introduce duplicate row")
            before = (home / ".shadow" / "board.json").read_bytes()

            refused = run(
                env, "return", "--repo", str(repo), "--row", "~aa11", "--by", "seat-a"
            )

            self.assertEqual(refused.returncode, 1)
            self.assertIn("duplicated", refused.stderr)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before)

    def test_completed_orphan_is_released_by_entity_instead_of_reworked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            claimed = run(
                env, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            entity = payload(home)["entities"][0]["id"]
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "- [pending] inspect the result ~aa11",
                    "- [completed] inspect the result ~aa11",
                )
                + "\n- 2026-08-10T01:00:00Z ~aa11 PROOF artifact -> pass\n",
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "complete before root release")

            observed = run(env, "status", "--by", "seat-a", cwd=home)
            projected = run(
                env,
                "amp",
                "--entity",
                entity,
                "--task",
                "~aa11",
                "--by",
                "seat-a",
                cwd=home,
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertIn(
                f"Recover: shadow return --entity {entity} --row '~aa11' --by seat-a",
                observed.stdout,
            )
            self.assertNotIn("Continue:", observed.stdout)
            self.assertEqual(projected.returncode, 1, projected.stderr)
            self.assertNotIn("/goal", projected.stdout)
            self.assertIn("not executable work", projected.stderr)
            self.assertIn("shadow return --entity", projected.stderr)

            recovered = run(
                env,
                "return",
                "--entity",
                entity,
                "--row",
                "~aa11",
                "--by",
                "seat-a",
                cwd=home,
            )

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertIn("returned ~aa11 (completed)", recovered.stdout)
            self.assertEqual(payload(home)["claims"], [])


class BlockedReturnsNeedOneDurableWake(unittest.TestCase):
    def test_deferred_wake_for_another_row_cannot_close_this_claim_by_substring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            claimed = run(
                env,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            plan_path = repo / "PLAN.md"
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8")
                .replace(
                    "- [pending] inspect the result ~aa11",
                    "- [blocked] inspect the result ~aa11",
                )
                .replace(
                    "## Progress",
                    "## Deferred\n\n"
                    "- ~bb22 waits on ~aa11 | artifact unavailable | wake: artifact exists\n\n"
                    "## Progress",
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "record another row's wake")
            before = (home / ".shadow" / "board.json").read_bytes()

            refused = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )

            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("Deferred entry naming the row", refused.stderr)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before)

    def test_blocked_row_cannot_be_parked_until_its_wake_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            claimed = run(
                env,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            plan_path = repo / "PLAN.md"
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8").replace(
                    "- [pending] inspect the result", "- [blocked] inspect the result"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "record blocked state")

            no_wake = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(no_wake.returncode, 1, no_wake.stderr)
            self.assertIn("wake", no_wake.stderr.lower())
            self.assertEqual(len(payload(home)["claims"]), 1)

            plan_path.write_text(
                plan_path.read_text(encoding="utf-8").replace(
                    "## Progress",
                    "## Deferred\n\n"
                    "- ~aa11 inspection | artifact unavailable | wake: artifact exists\n\n"
                    "## Progress",
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "record exact wake")

            parked = run(
                env,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(parked.returncode, 0, parked.stderr)
            self.assertEqual(payload(home)["claims"], [])


class BrokenPointersRecoverThroughAValidLogicalCheckout(unittest.TestCase):
    def test_owner_return_repoints_a_missing_plan_before_closing_the_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home, env = fixture(root, remote=True)
            sibling = root / "healthy-worktree"
            git(repo, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")
            claimed = run(
                env,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            (repo / "PLAN.md").unlink()

            recovered = run(
                env,
                "return",
                "--repo",
                str(sibling),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            after = payload(home)
            self.assertEqual(after["claims"], [])
            self.assertEqual(
                after["entities"][0]["plan"], str((sibling / "PLAN.md").resolve())
            )
            observed = run(env, "status", "--json", cwd=root)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertFalse(json.loads(observed.stdout)["v4_plans"][0].get("broken", False))


if __name__ == "__main__":
    unittest.main()
