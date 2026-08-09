"""Where a plan lives, and what the board is therefore allowed to read.

Measured on the reference machine 2026-08-09, before this landed: 7,250
`PLAN.md` files under the portfolio root, 777 reachable by the recursive walk,
665 of those byte-identical copies of 196 originals. The walk filled its
250-slot cap alphabetically and stopped at `resplit-`, so **Shadow's own plan
was invisible on its own board**, and 83 of the 250 cards were duplicates of
each other — one plan appeared 42 times.

It also had no boundary. Only the fact that `Development` sorts before
`Documents` kept it from rendering session directories whose names are prompt
text.

So: enumerate project roots, never walk directories.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from browser.server import (  # noqa: E402
    declared_plan_globs, discover_plans, is_plan_root, repo_plans,
)

PLAN = """# {name}

## Brief

- Project: {slug}
- Mode: ship
{extra}
## Tasks

### M1 — live
- [pending] a row ~aa11 | proof: cmd true

## Progress

- 2026-08-09T00:00:00Z NOTE seeded
"""


def brief(plans_line: str) -> str:
    """A plan whose Brief declares `plans_line` — the only place it counts."""
    return PLAN.format(name="app", slug="app", extra=f"- Plans: {plans_line}\n")


def make(root: Path, name: str, *, plans_line: str = "", nested: tuple[str, ...] = ()) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    extra = f"- Plans: {plans_line}\n" if plans_line else ""
    (repo / "PLAN.md").write_text(
        PLAN.format(name=name, slug=name.replace("_", "-"), extra=extra), encoding="utf-8")
    for relative in nested:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(PLAN.format(name=relative, slug="nested", extra=""), encoding="utf-8")
    return repo


class TheRule(unittest.TestCase):
    def test_a_directory_owning_a_plan_is_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make(Path(tmp), "alpha")
            self.assertTrue(is_plan_root(repo))
            self.assertFalse(is_plan_root(Path(tmp)))

    def test_git_is_not_required(self) -> None:
        # Boundedness was the goal, not a version-control test. A plan in a
        # plain directory is still a plan; requiring .git would make it vanish.
        with tempfile.TemporaryDirectory() as tmp:
            make(Path(tmp), "plain")
            self.assertEqual([r["path"] for r in discover_plans(Path(tmp))], ["plain/PLAN.md"])

    def test_only_immediate_children_are_enumerated(self) -> None:
        # The recursion is the whole bug. A plan three levels down is not this
        # root's to show, however real it is.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make(root, "visible")
            make(root / "one" / "two", "buried")
            self.assertEqual([r["path"] for r in discover_plans(root)], ["visible/PLAN.md"])

    def test_a_root_that_is_itself_a_plan_root_shows_only_its_own(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make(Path(tmp), "solo", nested=("sub/PLAN.md",))
            self.assertEqual([r["path"] for r in discover_plans(repo)], ["PLAN.md"])


class DeclaredGlobs(unittest.TestCase):
    def test_a_declared_glob_makes_nested_plans_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make(root, "app", plans_line="plans/*/PLAN.md",
                 nested=("plans/one/PLAN.md", "plans/two/PLAN.md", "hidden/PLAN.md"))
            paths = sorted(r["path"] for r in discover_plans(root))
            self.assertEqual(paths, ["app/PLAN.md", "app/plans/one/PLAN.md", "app/plans/two/PLAN.md"])

    def test_at_most_three_globs_are_honored(self) -> None:
        self.assertEqual(len(declared_plan_globs(brief("a/*, b/*, c/*, d/*"))), 3)

    def test_an_escaping_glob_is_dropped(self) -> None:
        # A repo-relative declaration must not reach outside its own repo. This
        # is the same reach a central index would have, arriving one line at a
        # time — so it is refused at parse, not at read.
        globs = declared_plan_globs(brief("../elsewhere/*/PLAN.md, /etc/*, ok/*/PLAN.md"))
        self.assertEqual(globs, ["ok/*/PLAN.md"])

    def test_only_the_brief_can_declare(self) -> None:
        # The grammar calls this one Brief line. A `- Plans:` line quoted in
        # Progress — a note about what some other repo declares, a fenced
        # example — is prose, and prose must not widen what the board reads.
        text = PLAN.format(name="app", slug="app", extra="") + "- Plans: sneaky/*/PLAN.md\n"
        self.assertEqual(declared_plan_globs(text), [])

    def test_a_declaration_quoted_in_progress_reads_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make(root, "app", nested=("plans/one/PLAN.md",))
            with (repo / "PLAN.md").open("a", encoding="utf-8") as handle:
                handle.write("- 2026-08-09T00:00:01Z NOTE it declares\n- Plans: plans/*/PLAN.md\n")
            self.assertEqual([r["path"] for r in discover_plans(root)], ["app/PLAN.md"])

    def test_a_symlinked_glob_cannot_escape_either(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "PLAN.md").write_text(PLAN.format(name="x", slug="x", extra=""), encoding="utf-8")
            repo = make(root, "app", plans_line="linked/*/PLAN.md")
            (repo / "linked").mkdir()
            (repo / "linked" / "away").symlink_to(outside, target_is_directory=True)
            self.assertEqual([p.name for p in repo_plans(repo)], ["PLAN.md"])

    def test_no_declaration_means_only_the_root_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make(root, "app", nested=("plans/one/PLAN.md",))
            self.assertEqual([r["path"] for r in discover_plans(root)], ["app/PLAN.md"])


class OneLogicalPlan(unittest.TestCase):
    def test_two_checkouts_of_one_origin_render_once(self) -> None:
        # 665 of 777 files the old walk reached were byte-identical copies, and
        # 83 of 250 board cards were duplicates. A worktree is not a second
        # project.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("thing", "thing-worktree"):
                repo = make(root, name)
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin",
                     "git@example.invalid:acme/thing.git"], check=True)
            paths = [r["path"] for r in discover_plans(root)]
            self.assertEqual(len(paths), 1, paths)

    def test_the_canonical_checkout_wins_over_a_rename_era_clone(self) -> None:
        # Observed against this very repository: a clone keeping its old
        # directory name sorted first and replaced the real plan with a stale
        # copy. The directory whose name matches the origin's repo name wins.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("aaa-old-name", "thing"):
                repo = make(root, name)
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin",
                     "git@example.invalid:acme/thing.git"], check=True)
            paths = [r["path"] for r in discover_plans(root)]
            self.assertEqual(paths, ["thing/PLAN.md"])

    def test_an_scp_origin_without_a_path_still_names_its_repo(self) -> None:
        # `git@host:thing.git` carries no slash before the repository name, so
        # splitting on `/` alone returns the whole URL, no directory ever
        # matches, and the stale clone wins on mtime instead.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("aaa-old-name", "thing"):
                repo = make(root, name)
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin",
                     "git@example.invalid:thing.git"], check=True)
            # The stale clone touched most recently: only the name match can
            # save the canonical checkout here.
            os.utime(root / "aaa-old-name" / "PLAN.md", (2_000_000_000, 2_000_000_000))
            paths = [r["path"] for r in discover_plans(root)]
            self.assertEqual(paths, ["thing/PLAN.md"])

    def test_unrelated_roots_without_git_are_not_merged(self) -> None:
        # No origin means the path stands in as identity. Two plain
        # directories are two plans, not one.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make(root, "one")
            make(root, "two")
            self.assertEqual(len(discover_plans(root)), 2)


class Boundedness(unittest.TestCase):
    def test_a_symlinked_child_cannot_smuggle_a_plan_in(self) -> None:
        # A symlink is a directory that owns a PLAN.md by every test the
        # enumeration makes, while living anywhere on the filesystem. Following
        # one reads outside the portfolio, which is the whole boundary.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "portfolio"
            root.mkdir()
            elsewhere = make(Path(tmp) / "elsewhere", "external")
            (root / "external").symlink_to(elsewhere, target_is_directory=True)
            make(root, "inside")
            self.assertEqual([r["path"] for r in discover_plans(root)], ["inside/PLAN.md"])


    def test_a_deep_tree_costs_nothing_and_returns_nothing(self) -> None:
        # The old walk ran past a 300-second window on a large tree and only
        # terminated because the cap stopped it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deep = root / "noise"
            for depth in range(30):
                deep = deep / f"level{depth}"
            deep.mkdir(parents=True)
            (deep / "PLAN.md").write_text(PLAN.format(name="deep", slug="deep", extra=""),
                                          encoding="utf-8")
            make(root, "real")
            self.assertEqual([r["path"] for r in discover_plans(root)], ["real/PLAN.md"])

    def test_no_output_carries_an_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make(root, "app", plans_line="plans/*/PLAN.md", nested=("plans/one/PLAN.md",))
            for record in discover_plans(root):
                self.assertFalse(record["path"].startswith("/"), record["path"])
                self.assertNotIn(str(Path.home()), record["path"])


if __name__ == "__main__":
    unittest.main()
