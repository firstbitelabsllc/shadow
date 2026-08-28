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

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from browser.server import (  # noqa: E402
    BrowserError, MAX_PLAN_BYTES, MAX_PLANS, declared_plan_globs, discover_plans,
    is_plan_root, live_plans, repo_plans,
)

STATUS = ROOT / "scripts" / "shadow-status.py"

PLAN = """# {name}

## Brief

- Project: {slug}
- Mode: ship
{extra}
## Tasks

### M1 — live
- [pending] a row ~aa11 | proof: cmd true
- [pending] live closes ~bb22 (DoD) | proof: cmd true | needs: ~aa11

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

    def test_a_fourth_valid_glob_is_refused(self) -> None:
        self.assertEqual(
            declared_plan_globs(brief("a/*, b/*, c/*")),
            ["a/*", "b/*", "c/*"],
        )
        with self.assertRaisesRegex(BrowserError, "more than 3 declared plan globs"):
            declared_plan_globs(brief("a/*, b/*, c/*, d/*"))

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

    def test_a_differently_cased_checkout_still_matches_its_origin(self) -> None:
        # The normalized origin is lowercased so one repository is one key, and
        # that same value names the canonical checkout. A `Thing` directory
        # cloned from `.../thing` must still win the tie-break; otherwise the
        # normalization that fixed the duplicate row hands the card to a stale
        # clone that merely sorts first and was touched last.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("aaa-old-name", "Thing"):
                repo = make(root, name)
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin",
                     "git@example.invalid:acme/thing.git"], check=True)
            os.utime(root / "aaa-old-name" / "PLAN.md", (2_000_000_000, 2_000_000_000))
            paths = [r["path"] for r in discover_plans(root)]
            self.assertEqual(paths, ["Thing/PLAN.md"])

    def test_two_paths_differing_only_in_case_are_two_repositories(self) -> None:
        # A hostname is case-insensitive; a path is not. `/srv/git/Foo.git` and
        # `/srv/git/foo.git` are two repositories, so folding the whole origin
        # would give them one key and drop a real project from the board — the
        # duplicate-row bug inverted, and worse, because it hides work.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, remote in (("upper", "/srv/git/Foo.git"), ("lower", "/srv/git/foo.git")):
                repo = make(root, name)
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
            paths = sorted(r["path"] for r in discover_plans(root))
            self.assertEqual(paths, ["lower/PLAN.md", "upper/PLAN.md"])

    def test_one_origin_spelled_two_ways_still_collapses(self) -> None:
        # Case-folding only the host must not cost the dedup this PR exists
        # for: SSH and HTTPS spellings of one GitHub repository stay one key.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remotes = ("git@Example.invalid:acme/thing.git", "https://example.invalid/acme/thing")
            for name, remote in zip(("thing", "thing-clone"), remotes):
                repo = make(root, name)
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
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
    def test_recursive_or_over_budget_declarations_fail_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recursive = make(root, "recursive", plans_line="**/PLAN.md")
            with self.assertRaisesRegex(BrowserError, "recursive plan globs"):
                repo_plans(recursive)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = tuple(f"plans/p{index:03d}/PLAN.md" for index in range(MAX_PLANS))
            crowded = make(
                root,
                "crowded",
                plans_line="plans/*/PLAN.md",
                nested=nested,
            )
            with self.assertRaisesRegex(BrowserError, f"more than {MAX_PLANS} plans"):
                repo_plans(crowded)

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


class StrictDiscoveryForBoardImport(unittest.TestCase):
    def _assert_default_omits_strict_refuses(self, plan_writer) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "broken"
            repo.mkdir()
            plan_writer(repo / "PLAN.md", root)

            self.assertEqual(discover_plans(root), [])
            with self.assertRaisesRegex(BrowserError, r"broken/PLAN\.md"):
                discover_plans(root, fail_on_skipped=True)

    def test_invalid_utf8_is_omitted_by_default_and_refused_by_strict_import(self) -> None:
        self._assert_default_omits_strict_refuses(
            lambda plan, _root: plan.write_bytes(b"\xff\xfe")
        )

    def test_oversized_plan_is_omitted_by_default_and_refused_by_strict_import(self) -> None:
        self._assert_default_omits_strict_refuses(
            lambda plan, _root: plan.write_bytes(b"#" * (MAX_PLAN_BYTES + 1))
        )

    def test_symlinked_plan_is_omitted_by_default_and_refused_by_strict_import(self) -> None:
        def symlink(plan: Path, root: Path) -> None:
            target = root / "outside-plan"
            target.write_text(
                PLAN.format(name="outside", slug="outside", extra=""),
                encoding="utf-8",
            )
            plan.symlink_to(target)

        self._assert_default_omits_strict_refuses(symlink)

    def test_non_regular_plan_is_omitted_by_default_and_refused_by_strict_import(self) -> None:
        self._assert_default_omits_strict_refuses(
            lambda plan, _root: plan.mkdir()
        )

    def test_broken_duplicate_is_ignored_after_the_canonical_checkout_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = make(root, "thing")
            duplicate = make(root, "thing-worktree")
            remote = "git@example.invalid:acme/thing.git"
            for repo in (canonical, duplicate):
                subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin", remote],
                    check=True,
                )
            (duplicate / "PLAN.md").write_bytes(b"\xff\xfe")

            records = discover_plans(root, fail_on_skipped=True)

            self.assertEqual([record["path"] for record in records], ["thing/PLAN.md"])

    def _status(self, home: Path, portfolio: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(STATUS), "--json"],
            cwd=cwd,
            env={
                **os.environ,
                "HOME": str(home),
                "SHADOW_PORTFOLIO_ROOT": str(portfolio),
            },
            capture_output=True,
            text=True,
            check=False,
        )

    def test_strict_import_failure_does_not_create_a_root_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            broken = portfolio / "broken"
            broken.mkdir()
            (broken / "PLAN.md").write_bytes(b"\xff\xfe")

            result = self._status(home, portfolio, root)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("portfolio import refused", result.stderr)
            self.assertFalse((home / ".shadow" / "board.json").exists())

    def test_strict_import_failure_does_not_advance_an_existing_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            make(portfolio, "healthy")
            first = self._status(home, portfolio, root)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            board = home / ".shadow" / "board.json"
            before = board.read_bytes()

            broken = portfolio / "broken"
            broken.mkdir()
            (broken / "PLAN.md").write_bytes(b"\xff\xfe")
            refused = self._status(home, portfolio, root)

            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("portfolio import refused", refused.stderr)
            self.assertEqual(board.read_bytes(), before)

    def test_blocking_plan_lint_does_not_advance_an_existing_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            make(portfolio, "healthy")
            first = self._status(home, portfolio, root)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            board = home / ".shadow" / "board.json"
            before = board.read_bytes()

            malformed = make(portfolio, "malformed") / "PLAN.md"
            malformed.write_text(
                malformed.read_text(encoding="utf-8").replace("~bb22", "~aa11"),
                encoding="utf-8",
            )
            refused = self._status(home, portfolio, root)

            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("cannot enter the computer board", refused.stderr)
            self.assertEqual(board.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()


class ADuplicateNeverBecomesASecondRow(unittest.TestCase):
    """Two spellings of one repository, and one repository's own copies.

    Both were red when this was written, on main, with no mutation needed.

    A clone addressed as `git@github.com:acme/thing.git` and one addressed as
    `https://github.com/acme/thing` are the same repository. The dedup key was
    the raw URL string, so they were two keys and both rendered — the board
    said two projects where one exists.

    Separately, `Path.glob` descends into dot-directories: a declared
    `**/PLAN.md` reached into `.worktrees/`, `node_modules/`, and any vendored
    copy. `SKIP_DIRS` named exactly those directories and had zero readers.
    """

    def _repo(self, root: Path, name: str, origin: str | None, plan: str) -> Path:
        repo = root / name
        (repo).mkdir(parents=True, exist_ok=True)
        (repo / "PLAN.md").write_text(plan, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        if origin:
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
        return repo

    PLAN = ("# T\n\n## Brief\n\n- Project: thing\n- Mode: ship\n\n## Tasks\n\n"
            "### M\n- [pending] a row ~aa11 | proof: cmd true\n"
            "- [pending] ships ~bb22 (DoD) | proof: read x -> y\n\n## Progress\n\n"
            "- 2026-08-09T00:00:00Z NOTE seeded\n")

    def test_two_url_spellings_of_one_repo_render_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git", self.PLAN)
            self._repo(root, "thing-clone", "https://github.com/acme/thing", self.PLAN)
            found = discover_plans(root)
            self.assertEqual(len(found), 1,
                             f"one repository rendered {len(found)} times: "
                             f"{[r['path'] for r in found]}")

    def test_two_different_repos_sharing_a_project_slug_both_render(self) -> None:
        # The opposite error. Brief law legalizes multi-repo projects, so
        # grouping by `- Project:` would hide a real repository.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "web", "git@github.com:acme/web.git", self.PLAN)
            self._repo(root, "api", "git@github.com:acme/api.git", self.PLAN)
            self.assertEqual(len(discover_plans(root)), 2)

    def test_a_declared_glob_never_descends_into_a_hidden_or_vendor_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaring = self.PLAN.replace("- Mode: ship", "- Mode: ship\n- Plans: */PLAN.md")
            repo = self._repo(root, "thing", "git@github.com:acme/thing.git", declaring)
            for buried in (".worktrees/pool", "node_modules/pkg", "dist", "sub"):
                (repo / buried).mkdir(parents=True, exist_ok=True)
                (repo / buried / "PLAN.md").write_text(self.PLAN, encoding="utf-8")

            paths = {str(p.relative_to(repo)) for p in repo_plans(repo)}

            self.assertIn("sub/PLAN.md", paths, "a real nested plan was pruned")
            for hidden in (".worktrees/pool/PLAN.md", "node_modules/pkg/PLAN.md", "dist/PLAN.md"):
                self.assertNotIn(hidden, paths,
                                 f"discovery read a copy under a pruned directory: {hidden}")


class AnArchiveShellNeverRendersAsAuthority(unittest.TestCase):
    """The demotion can live on the copy no rule elects.

    Measured on this machine: `resplit-ios/PLAN.md` wins election on every
    structural rule — its directory name matches its origin, `.git` is a real
    directory, it is a portfolio-root child. Its "non-executable archive
    shell ... do not revive" banner exists ONLY on the divergent copy at
    `resplit-ios-deploy-watcher`, which nothing elects:

        grep -c "non-executable" resplit-ios/PLAN.md                 -> 0
        grep -c "non-executable" resplit-ios-deploy-watcher/PLAN.md  -> 1

    So the board reads the undemoted twin as the project's authority while the
    verdict sits in a file it never opens. A check that reads only the elected
    file cannot see this; the verdict has to be sought across every instance
    of a dedup key, which the key already enumerates.
    """

    BANNER = ("**[verified 2026-07-29: HISTORICAL ROUTING CONFIRMED — this root plan remains a "
              "non-executable archive shell. do not revive or update the historical task rows "
              "below.]**")

    def _repo(self, root: Path, name: str, origin: str, banner: str = "") -> Path:
        repo = root / name
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "PLAN.md").write_text(
            f"# Demo\n\n{banner}\n\n## Brief\n\n- Project: demo\n- Mode: ship\n\n"
            "## Tasks\n\n### M\n- [pending] a row ~aa11 | proof: cmd true\n"
            "- [pending] ships ~bb22 (DoD) | proof: read x -> y\n\n"
            "## Progress\n\n- 2026-08-09T00:00:00Z NOTE seeded\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
        return repo

    def test_a_veto_on_an_unelected_copy_demotes_the_elected_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git")               # elected, no banner
            self._repo(root, "thing-watcher", "git@github.com:acme/thing.git", self.BANNER)

            found = discover_plans(root)
            self.assertEqual(len(found), 1, "dedup regressed")
            record = found[0]
            self.assertTrue(record.get("archived"),
                            "the elected plan renders as live authority while a copy of it "
                            "says 'non-executable archive shell, do not revive'")
            self.assertIn("non-executable", record.get("archive_veto", "").lower())

    def test_a_plan_with_no_veto_anywhere_stays_authority(self) -> None:
        # A guard that demotes everything is as useless as one that never fires.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git")
            self._repo(root, "thing-watcher", "git@github.com:acme/thing.git")
            record = discover_plans(root)[0]
            self.assertFalse(record.get("archived"), "a healthy plan was demoted")

    def test_the_veto_is_found_on_the_elected_file_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git", self.BANNER)
            self.assertTrue(discover_plans(root)[0].get("archived"))

    def test_the_word_archive_in_ordinary_prose_does_not_demote(self) -> None:
        # `docs/plan-archive/` and "archive the milestone" are everywhere in a
        # healthy plan. Only a self-demotion counts.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git",
                       "The shipping commit moves the block to docs/plan-archive/<slug>.md.")
            self.assertFalse(discover_plans(root)[0].get("archived"))

    def test_a_demotion_phrase_aimed_at_something_else_does_not_demote(self) -> None:
        # The phrases are true sentences about other things in a live plan: the
        # milestone retires a service, or names a component for what it is. A
        # verdict is a plan demoting ITSELF, so the phrase only counts when its
        # subject is this plan.
        for prose in (
            "Do not revive the old deploy service — the watcher replaced it.",
            "The deploy watcher is a historical shell we delete in M18.",
            "Cut over from the archive shell that fronts the legacy bucket.",
            # "this <thing> plan" is a plan of work, not this file: a row that
            # holds one back is scheduling, not a self-verdict.
            "Do not update this deployment plan until the watcher cuts over.",
            "This rollout plan is a historical shell of the M12 sequence.",
        ):
            with self.subTest(prose=prose), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._repo(root, "thing", "git@github.com:acme/thing.git", prose)
                record = discover_plans(root)[0]
                self.assertFalse(record.get("archived"),
                                 f"a live plan was demoted by prose about something else: "
                                 f"{record.get('archive_veto')!r}")

    def test_a_symlinked_copy_cannot_demote_from_outside_the_portfolio(self) -> None:
        # A root PLAN.md is admitted on is_file(), which a symlink satisfies,
        # so a sibling checkout could point its plan anywhere and have that
        # content decide authority. read_plan refuses a symlinked plan; the
        # veto reader has to refuse it too, or out-of-boundary text demotes a
        # plan the board would otherwise render.
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git")
            watcher = self._repo(root, "thing-watcher", "git@github.com:acme/thing.git")
            planted = Path(outside) / "PLAN.md"
            planted.write_text(f"# Demo\n\n{self.BANNER}\n", encoding="utf-8")
            (watcher / "PLAN.md").unlink()
            (watcher / "PLAN.md").symlink_to(planted)

            record = discover_plans(root)[0]
            self.assertFalse(record.get("archived"),
                             "a file outside the portfolio decided the plan's authority: "
                             f"{record.get('archive_veto')!r}")

    def test_a_vetoed_plan_never_reaches_the_browser(self) -> None:
        # Annotating the record is not a demotion: both projections iterate the
        # served list without reading `archived`, so a card the wire still
        # carries keeps its live briefing and its decision buttons.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git")
            self._repo(root, "thing-watcher", "git@github.com:acme/thing.git", self.BANNER)
            self._repo(root, "other", "git@github.com:acme/other.git")

            demoted = [record for record in discover_plans(root) if record.get("archived")]
            self.assertEqual([record["path"] for record in demoted], ["thing/PLAN.md"],
                             "veto regressed")
            served = live_plans(root)
            self.assertEqual([record["path"] for record in served], ["other/PLAN.md"],
                             "the board was served a plan a copy of it demotes")

    def test_a_healthy_portfolio_is_served_whole(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "thing", "git@github.com:acme/thing.git")
            self._repo(root, "other", "git@github.com:acme/other.git")
            self.assertEqual(len(live_plans(root)), 2)


class TheTerminalObeysTheVetoToo(unittest.TestCase):
    """`shadow status` is the other surface that answers "what is authority".

    Serving the browser from `live_plans` closed one path. The CLI kept reading
    `discover_plans`, so the same archive shell the wire refused to send was
    still printed at a terminal as a current plan, and `--in-flight` still
    handed out its claimed rows for recovery. That is the resplit-ios split
    re-created one surface over, which is worse than never having filtered: the
    two answers now disagree.
    """

    STATUS = ROOT / "scripts" / "shadow-status.py"
    BANNER = ("**[verified 2026-07-29: HISTORICAL ROUTING CONFIRMED — this root plan remains a "
              "non-executable archive shell. do not revive or update the historical task rows "
              "below.]**")

    def _repo(self, root: Path, name: str, origin: str, banner: str = "") -> Path:
        repo = root / name
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "PLAN.md").write_text(
            f"# {name}\n\n{banner}\n\n## Brief\n\n- Project: {name}\n- Mode: ship\n"
            "- Priority: 3\n\n"
            "## Tasks\n\n### M\n"
            f"- [in_progress] a claimed row in {name} ~aa11 | proof: cmd true\n"
            "- [pending] ships ~bb22 (DoD) | proof: read x -> y\n\n"
            "## Progress\n\n"
            "- 2026-08-09T00:00:00Z THROWN ~aa11 | by: archive-veto-test\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
        return repo

    def _status(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        home = root / ".home"
        home.mkdir(exist_ok=True)
        env = os.environ.copy()
        env.update({"HOME": str(home), "SHADOW_PORTFOLIO_ROOT": str(root)})
        return subprocess.run(
            [sys.executable, str(self.STATUS), "--root", str(root), *args],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )

    def _portfolio(self, root: Path) -> None:
        self._repo(root, "shell", "git@github.com:acme/shell.git", self.BANNER)
        self._repo(root, "live", "git@github.com:acme/live.git")

    def test_an_archive_shell_is_not_printed_as_a_current_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._portfolio(root)
            result = self._status(root, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            served = json.loads(result.stdout)
            projects = {row.get("project") for row in served["v4_plans"]}
            self.assertIn("live", projects, "the healthy plan stopped rendering")
            self.assertNotIn("shell", projects,
                             "the CLI quotes a plan the wire refuses to send")

    def test_a_claim_inside_an_archive_shell_is_not_handed_to_a_successor(self) -> None:
        # The worst form of the split: recovery reads `--in-flight` to find out
        # what to pick up, so a row from a file that says "do not revive" is
        # not merely noise: it is work actively dispatched against a verdict.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._portfolio(root)
            result = self._status(root, "--in-flight", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            projects = {row["project"] for row in json.loads(result.stdout)["rows"]}
            self.assertEqual(projects, {"live"})

    def test_a_registered_entity_is_retired_when_any_copy_self_demotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._repo(root, "live", "git@github.com:acme/live.git") / "PLAN.md"
            first = self._status(root, "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            before = json.loads(first.stdout)["root_board"]
            self.assertEqual(len(before["entities"]), 1)
            self.assertEqual(len(before["claims"]), 1)

            text = plan.read_text(encoding="utf-8")
            plan.write_text(text.replace("# live\n", f"# live\n\n{self.BANNER}\n", 1),
                            encoding="utf-8")
            second = self._status(root, "--json")
            self.assertEqual(second.returncode, 0, second.stderr)
            after = json.loads(second.stdout)["root_board"]
            self.assertEqual(after["entities"], [])
            self.assertEqual(after["claims"], [])
            self.assertGreater(after["revision"], before["revision"])

            ledger = root / ".home" / ".shadow"
            prior = subprocess.run(
                ["git", "-C", str(ledger), "show", "HEAD^:board.json"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(len(json.loads(prior.stdout)["claims"]), 1)

    def test_the_demotion_is_inspectable_rather_than_silent(self) -> None:
        # A plan that vanishes with no reason is the ambiguity `--shadowed`
        # exists to end. Its public receipt names an opaque copy and a fixed
        # reason without exposing the checkout directory that supplied either.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._portfolio(root)
            result = self._status(root, "--shadowed", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads(result.stdout)["rows"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), {"path", "shadowed_by", "reason"})
            self.assertRegex(rows[0]["path"], r"^copy@[0-9a-f]{12}/PLAN\.md$")
            self.assertIn("non-executable archive shell", rows[0]["reason"].lower())

    def test_a_directory_holding_only_a_shell_says_why_it_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root, "shell", "git@github.com:acme/shell.git", self.BANNER)
            result = self._status(root, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["v4_plans"], [])
            self.assertIn("non-executable archive shell", result.stderr.lower())


class ClassificationIsDeterministic(unittest.TestCase):
    """The same portfolio must classify the same way, twice and anywhere.

    Two things could make it drift, and both were measured on this machine
    rather than imagined:

    Filesystem iteration order. `pilot-puppy` sorts BEFORE `shadow` and shares
    its dedup key exactly — same origin, same repo-relative path — so a
    first-seen winner would elect a plan that contains the string "shadow"
    zero times and claims authority over the whole portfolio. The candidate
    sort's `repo.name != _origin_repo_name(...)` term is what stops that, and
    it is a set-membership test, so listing order cannot reach it.

    Modification time. `git checkout` and worktree creation rewrite mtimes
    wholesale — `resplit-ios/PLAN.md` reads 2026-06-28 while the file is
    unmodified on main — so mtime is a fact about the last checkout, never
    about liveness. It may break ties; it must never decide classification.
    """

    PLAN = ("# T\n\n## Brief\n\n- Project: t\n- Mode: ship\n\n## Tasks\n\n### M\n"
            "- [pending] a row ~aa11 | proof: cmd true\n"
            "- [pending] ships ~bb22 (DoD) | proof: read x -> y\n\n"
            "## Progress\n\n- 2026-08-09T00:00:00Z NOTE seeded\n")

    def _build(self, root: Path, order: list[str], mtimes: dict[str, int]) -> None:
        """One fixture, built in a caller-chosen order with chosen mtimes."""
        for name in order:
            repo = root / name
            repo.mkdir(parents=True)
            (repo / "PLAN.md").write_text(self.PLAN, encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                            "git@github.com:acme/thing.git"], check=True)
            stamp = mtimes[name]
            os.utime(repo / "PLAN.md", (stamp, stamp))

    def _observe(self, root: Path) -> list[tuple]:
        """Everything a reader could see, made root-relative."""
        return [
            (r["path"], r.get("shadowed_by"), r.get("shadow_reason"),
             bool(r.get("archived")))
            for r in discover_plans(root, include_shadowed=True)
        ]

    def test_listing_order_and_mtimes_cannot_change_the_answer(self) -> None:
        forward = ["thing", "thing-copy", "another-copy"]
        backward = list(reversed(forward))
        # Permuted so the mtime ranking is inverted between the two runs.
        early = {"thing": 1_600_000_000, "thing-copy": 1_700_000_000, "another-copy": 1_650_000_000}
        late = {"thing": 1_700_000_000, "thing-copy": 1_600_000_000, "another-copy": 1_650_000_000}

        observations = []
        for order, mtimes in ((forward, early), (backward, late),
                              (backward, early), (forward, late)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._build(root, order, mtimes)
                observations.append(self._observe(root))
                observations.append(self._observe(root))  # second run, same root

        first = observations[0]
        for index, observed in enumerate(observations[1:], start=1):
            self.assertEqual(observed, first,
                             f"run {index} classified differently — order or mtime reached the answer")

    def test_the_canonical_name_decides_and_not_the_newest_file(self) -> None:
        # The measured pilot-puppy case: the directory whose name matches the
        # origin wins even when a sibling's plan is newer. Deleting that term
        # from the sort is what turns this red.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build(root, ["thing", "zzz-newer-copy"],
                        {"thing": 1_600_000_000, "zzz-newer-copy": 1_900_000_000})
            rendered = [r for r in discover_plans(root, include_shadowed=True)
                        if not r.get("shadowed_by")]
            self.assertEqual(len(rendered), 1)
            self.assertTrue(rendered[0]["path"].startswith("thing/"),
                            f"the newer copy won: {rendered[0]['path']}")

    def test_every_suppressed_plan_is_reported_with_the_rule_that_suppressed_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build(root, ["thing", "thing-copy"],
                        {"thing": 1_600_000_000, "thing-copy": 1_600_000_000})
            shadowed = [r for r in discover_plans(root, include_shadowed=True)
                        if r.get("shadowed_by")]
            self.assertEqual(len(shadowed), 1)
            self.assertTrue(shadowed[0]["shadow_reason"],
                            "a plan was suppressed with no reason a reader could act on")
            self.assertTrue(shadowed[0]["shadowed_by"].startswith("thing/"))

    def test_the_flag_off_output_is_unchanged(self) -> None:
        # The migration must be a no-op for anyone not asking for the extra view.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build(root, ["thing", "thing-copy"],
                        {"thing": 1_600_000_000, "thing-copy": 1_600_000_000})
            self.assertEqual(discover_plans(root),
                             [r for r in discover_plans(root, include_shadowed=True)
                              if not r.get("shadowed_by")])

    def test_no_reason_string_leaks_an_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build(root, ["thing", "thing-copy"],
                        {"thing": 1_600_000_000, "thing-copy": 1_600_000_000})
            for record in discover_plans(root, include_shadowed=True):
                for field in ("path", "shadowed_by", "shadow_reason"):
                    value = record.get(field) or ""
                    self.assertNotIn(str(root), value,
                                     f"{field} leaked an absolute path, so the answer is machine-specific")
