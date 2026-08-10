"""The gauntlet: Shadow run END TO END against a disposable mock portfolio.

The owner's bar, recorded in the universal-system register (entry 22): the
system is done when the loop makes the owner's calls in their absence, and
confidence comes only from repeated end-to-end runs against mock portfolios —
fake repositories with a local bare remote standing in for the forge, plans in
every state, ghost copies, a pre-grammar document — driven through the REAL
verbs as subprocesses, with proof asserted at every step.  One passing run is
a demo; this file exists so the run can be repeated until it is boringly
green.

What one gauntlet run proves, in order:
1.  discovery: `shadow status` sees each real plan once — a second checkout of
    a repo, sitting in the portfolio beside it, collapses into it, and the
    pre-grammar essay does not crash it;
2.  projection: the browser's plan API renders every mock plan with its true
    board state;
3.  dispatch: seat A claims a row with `shadow throw`; the claim commit
    reaches the bare remote;
4.  reachability: seat B — a separate clone, told nothing but the remote —
    fetches and sees WHO claimed WHICH row;
5.  acceptance: `shadow accept` reruns the row's cmd proof in a clean
    checkout and flips it with its paired PROOF line, pushed;
6.  honesty: the flip is visible to seat B only after the push, and the
    completed row carries its receipt.

Nothing here touches the machine's real portfolio: every path lives under a
TemporaryDirectory, and the remote is a local bare repository.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SHADOW = ROOT / "bin" / "shadow"

sys.path.insert(0, str(ROOT))
from browser import server  # noqa: E402


PLAN_TEMPLATE = """# {title}

## Brief

- Project: {project}
- Mode: ship
- Priority: {priority}

## Tasks

### M1 — {milestone}
- [completed] the groundwork landed ~aa{n}1 | proof: cmd true
- [pending] the feature is being built ~aa{n}2 | proof: cmd true
- [pending] the owner re-observes the result ~aa{n}3 (DoD) | proof: gate owner re-observes | needs: ~aa{n}2

## Progress

- 2026-08-09T12:00:00Z ~aa{n}1 PROOF cmd true — green.
"""

PRE_GRAMMAR = """# Old campaign notes

## Goal

Ship the spring campaign.

## Steps

1. Draft the landing page.
2. Review with the team.
3. Publish.

## Notes

The copy needs one more pass.
The hero image is picked.
Budget was approved in March.
Remember to loop in support.
Legal reviewed the claims.
Analytics events are named.
"""


def run(cmd, cwd, **kw):
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=120, **kw
    )


def git(cwd, *args):
    result = run(["git", *args], cwd)
    if result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result


class TheGauntlet(unittest.TestCase):
    """One full end-to-end pass over a disposable mock portfolio."""

    maxDiff = None

    def _mint_repo(self, home: Path, name: str, n: int) -> tuple[Path, Path]:
        """A working clone wired to a local bare remote, carrying one plan."""
        bare = home / "forge" / f"{name}.git"
        bare.parent.mkdir(parents=True, exist_ok=True)
        git(home, "init", "-q", "--bare", str(bare))
        clone = home / "Development" / name
        clone.parent.mkdir(parents=True, exist_ok=True)
        git(home, "clone", "-q", str(bare), str(clone))
        git(clone, "config", "user.email", "gauntlet@example.invalid")
        git(clone, "config", "user.name", "Gauntlet")
        plan = clone / "PLAN.md"
        plan.write_text(
            PLAN_TEMPLATE.format(
                title=f"{name} plan", project=name, n=n,
                priority=f"{name} ships its feature",
                milestone=f"{name} feature live",
            ),
            encoding="utf-8",
        )
        git(clone, "add", "PLAN.md")
        git(clone, "commit", "-qm", "plan")
        git(clone, "push", "-q", "origin", "HEAD:main")
        git(clone, "branch", "-q", "--set-upstream-to=origin/main")
        # The forge's HEAD must name the branch we pushed, or a cold clone
        # checks out an unborn default branch and sees an empty tree.
        git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
        return clone, bare

    def test_one_full_pass(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            home = Path(dirname)
            dev = home / "Development"

            # --- the portfolio: two real repos, one ghost, one pre-grammar ---
            alpha, alpha_bare = self._mint_repo(home, "alpha", 1)
            beta, _ = self._mint_repo(home, "beta", 2)
            # The ghost must sit where discovery actually looks: a direct
            # child of the portfolio owning its own root PLAN.md. Buried a
            # level down it is never enumerated, and step 1 would pass even if
            # deduplication regressed entirely.
            ghost = dev / "alpha-stale-lane"
            git(home, "clone", "-q", str(alpha_bare), str(ghost))
            legacy = dev / "old-notes"
            legacy.mkdir(parents=True)
            (legacy / "PLAN.md").write_text(PRE_GRAMMAR, encoding="utf-8")
            git(legacy, "init", "-q")

            # --- 1. discovery: each repo once; the ghost collapses ---
            plans = server.discover_plans(dev)
            self.assertTrue(
                (ghost / "PLAN.md").is_file(),
                "the ghost must own a plan discovery could have counted twice",
            )
            projects = sorted(p["project"] for p in plans)
            self.assertEqual(
                projects, ["alpha", "beta", "old-notes"],
                f"discovery must see each repo exactly once, got {projects}",
            )
            paths = {p["project"]: p["path"] for p in plans}
            self.assertEqual(
                paths["alpha"], "alpha/PLAN.md",
                "the canonical checkout must win over its stale twin",
            )

            # --- 2. projection: true states, pre-grammar named honestly ---
            by_project = {p["project"]: p for p in plans}
            self.assertEqual(by_project["alpha"]["board"]["state"], "ready")
            self.assertEqual(by_project["beta"]["board"]["state"], "ready")
            self.assertEqual(by_project["old-notes"]["board"]["state"], "unmigrated")
            self.assertIsNone(by_project["alpha"]["contract_error"])

            # --- 3. dispatch: seat A claims alpha's in_progress row ---
            thrown = run(
                [str(SHADOW), "throw", "--repo", str(alpha), "--task", "~aa12",
                 "--by", "seat-a", "--note", "gauntlet claim"],
                alpha,
            )
            self.assertEqual(thrown.returncode, 0, thrown.stdout + thrown.stderr)

            # The claim moved the board: alpha reads "working" on re-discovery.
            re_projected = {p["project"]: p for p in server.discover_plans(dev)}
            self.assertEqual(re_projected["alpha"]["board"]["state"], "working")

            # --- 4. reachability: seat B sees WHO claimed WHAT, cold ---
            seat_b = home / "seat-b" / "alpha"
            seat_b.parent.mkdir(parents=True)
            git(home, "clone", "-q", str(alpha_bare), str(seat_b))
            b_plan = (seat_b / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("THROWN", b_plan, "the claim did not reach the remote")
            self.assertIn("seat-a", b_plan, "the claim does not name its seat")
            self.assertIn("~aa12", b_plan, "the claim does not name its row")

            # --- 5. acceptance: the cmd proof reruns clean and flips ---
            accepted = run(
                [str(SHADOW), "accept", "--repo", str(alpha), "--row", "~aa12"],
                alpha,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            flipped = (alpha / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("- [completed] the feature is being built ~aa12", flipped)
            self.assertIn("~aa12 PROOF", flipped, "a flip without its receipt is a lie")

            # --- 6. honesty: seat B sees the flip only after the push ---
            git(seat_b, "fetch", "-q", "origin")
            git(seat_b, "reset", "-q", "--hard", "origin/main")
            b_after = (seat_b / "PLAN.md").read_text(encoding="utf-8")
            self.assertIn("- [completed] the feature is being built ~aa12", b_after)
            self.assertIn("~aa12 PROOF", b_after)


if __name__ == "__main__":
    unittest.main()
