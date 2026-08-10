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
2.  projection: status and the browser dereference the same canonical
    computer-board entities;
3.  dispatch: two named seats atomically claim disjoint rows in different
    entities without mutating either project plan;
4.  reachability: a cold seat in another clone sees WHO claimed WHICH row from
    the same local computer board — the remote project plan never becomes a
    competing claim ledger;
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
                priority=n,
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
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            dev = root / "Development"
            shadow_env = {
                **os.environ,
                "HOME": str(home),
                "SHADOW_PORTFOLIO_ROOT": str(dev),
            }

            # --- the portfolio: two real repos, one ghost, one pre-grammar ---
            alpha, alpha_bare = self._mint_repo(root, "alpha", 1)
            beta, _ = self._mint_repo(root, "beta", 2)
            # The ghost must sit where discovery actually looks: a direct
            # child of the portfolio owning its own root PLAN.md. Buried a
            # level down it is never enumerated, and step 1 would pass even if
            # deduplication regressed entirely.
            ghost = dev / "alpha-stale-lane"
            git(root, "clone", "-q", str(alpha_bare), str(ghost))
            legacy = dev / "old-notes"
            legacy.mkdir(parents=True)
            (legacy / "PLAN.md").write_text(PRE_GRAMMAR, encoding="utf-8")
            git(legacy, "init", "-q")

            # --- 1. discovery/import: each repo once; the ghost collapses ---
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
            status = run(
                [str(SHADOW), "status", "--root", str(dev), "--json"],
                root,
                env=shadow_env,
            )
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertEqual(
                {item["project"] for item in status_payload["root_board"]["entities"]},
                {"alpha", "beta"},
            )
            self.assertEqual(status_payload["plans"], [])

            # --- 2. projection: browser and status share the board entities ---
            board_payload, cards, warning = server.board_plan_records(dev, home)
            self.assertIsNone(warning)
            self.assertEqual(board_payload["revision"], status_payload["root_board"]["revision"])
            self.assertEqual({card["project"] for card in cards}, {"alpha", "beta"})
            by_project = {card["project"]: card for card in cards}
            self.assertEqual(by_project["alpha"]["board"]["state"], "ready")
            self.assertEqual(by_project["beta"]["board"]["state"], "ready")
            self.assertEqual(
                next(plan for plan in plans if plan["project"] == "old-notes")["board"]["state"],
                "unmigrated",
            )

            # --- 3. dispatch: two seats claim disjoint entity rows ---
            thrown_a = run(
                [str(SHADOW), "throw", "--repo", str(alpha), "--task", "~aa12",
                 "--by", "seat-a"],
                alpha,
                env=shadow_env,
            )
            thrown_b = run(
                [str(SHADOW), "throw", "--repo", str(beta), "--task", "~aa22",
                 "--by", "seat-b"],
                beta,
                env=shadow_env,
            )
            self.assertEqual(thrown_a.returncode, 0, thrown_a.stdout + thrown_a.stderr)
            self.assertEqual(thrown_b.returncode, 0, thrown_b.stdout + thrown_b.stderr)
            board_payload, cards, warning = server.board_plan_records(dev, home)
            self.assertIsNone(warning)
            self.assertEqual(
                {(claim["row"], claim["owner"]) for claim in board_payload["claims"]},
                {("~aa12", "seat-a"), ("~aa22", "seat-b")},
            )
            by_project = {card["project"]: card for card in cards}
            self.assertEqual(by_project["alpha"]["owner"], "seat-a")
            self.assertEqual(by_project["beta"]["owner"], "seat-b")

            # --- 4. reachability: a cold clone sees claims through the board ---
            seat_b = root / "seat-b" / "alpha"
            seat_b.parent.mkdir(parents=True)
            git(root, "clone", "-q", str(alpha_bare), str(seat_b))
            b_plan = (seat_b / "PLAN.md").read_text(encoding="utf-8")
            self.assertNotIn("THROWN", b_plan)
            self.assertNotIn("seat-a", b_plan)
            in_flight = run(
                [str(SHADOW), "status", "--in-flight", "--json"],
                seat_b,
                env=shadow_env,
            )
            self.assertEqual(in_flight.returncode, 0, in_flight.stdout + in_flight.stderr)
            cold_rows = json.loads(in_flight.stdout)["rows"]
            self.assertEqual(
                {(row["id"], row["by"]) for row in cold_rows},
                {("~aa12", "seat-a"), ("~aa22", "seat-b")},
            )

            # --- 5. acceptance: the cmd proof reruns clean and flips ---
            accepted = run(
                [str(SHADOW), "accept", "--repo", str(alpha), "--row", "~aa12",
                 "--by", "seat-a"],
                alpha,
                env=shadow_env,
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
            remaining = json.loads(
                run(
                    [str(SHADOW), "status", "--in-flight", "--json"],
                    seat_b,
                    env=shadow_env,
                ).stdout
            )["rows"]
            self.assertEqual(
                [(row["id"], row["by"]) for row in remaining],
                [("~aa22", "seat-b")],
            )


if __name__ == "__main__":
    unittest.main()
