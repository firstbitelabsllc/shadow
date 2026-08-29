from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
BOARD_MODULE = ROOT / "scripts" / "shadow_root_board.py"
PLAN_MODULE = ROOT / "scripts" / "shadow-plan.py"
PROOF_SENTINEL = "PROOF-MUST-NOT-ENTER-THE-BOARD"
HOT_PLAN_LIMIT = 256 * 1024
sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as board_api  # noqa: E402
from tests.plan_tree_fixture import install_plan_tree  # noqa: E402
from tests.proc_fixture import git

_PLAN_SPEC = importlib.util.spec_from_file_location(
    "shadow_map_plan_test",
    PLAN_MODULE,
)
plan_api = importlib.util.module_from_spec(_PLAN_SPEC)
assert _PLAN_SPEC and _PLAN_SPEC.loader
sys.modules[_PLAN_SPEC.name] = plan_api
_PLAN_SPEC.loader.exec_module(plan_api)


def fresh_board_module(name: str):
    """One isolated board-module copy for tests that patch its internals."""
    spec = importlib.util.spec_from_file_location(name, BOARD_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Machine-local pex-based shims can keep writing their bootstrap cache into a
# fixture HOME after the test that spawned them returns; that races
# TemporaryDirectory cleanup. Pin PEX_ROOT outside every fixture so the
# background writer and the fixture never share a directory.
_PEX_ROOT = Path(tempfile.mkdtemp(prefix="shadow-test-pex-root-"))
os.environ.setdefault("PEX_ROOT", str(_PEX_ROOT))
atexit.register(lambda: shutil.rmtree(_PEX_ROOT, ignore_errors=True))


def project(
    root: Path,
    sentinel: str = "TASK-BODY-MUST-NOT-ENTER-THE-BOARD",
    *,
    name: str = "project",
    display_name: str | None = None,
    priority: int = 2,
    first_proof: str = f"cmd python3 -c \"print('{PROOF_SENTINEL}')\"",
    commit_date: str | None = None,
) -> Path:
    repo = root / name
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "user.email", "shadow-test@example.invalid")
    git(repo, "config", "user.name", "Shadow Test")
    (repo / "PLAN.md").write_text(
        "# Project\n\n"
        "## Brief\n\n"
        f"- Project: {display_name or name}\n"
        "- Mode: ship\n"
        f"- Priority: {priority}\n\n"
        "## Tasks\n\n"
        "### The useful outcome\n"
        f"- [pending] {sentinel} ~aa11 | proof: {first_proof}\n"
        "- [pending] the outcome is proven ~bb22 (DoD) | proof: cmd true | needs: ~aa11\n\n"
        "## Progress\n\n"
        "- 2026-08-10T00:00:00Z NOTE seeded\n",
        encoding="utf-8",
    )
    git(repo, "add", "PLAN.md")
    # `commit_date` pins the seed commit's date so a fixture that models two
    # checkouts of ONE repository can give them the equal commit dates a real
    # worktree or clone has. Left unset, the date is wall-clock and two
    # sequentially seeded checkouts straddle a second boundary at random.
    git(
        repo,
        "commit",
        "--quiet",
        "-m",
        "seed",
        env=(
            {"GIT_AUTHOR_DATE": commit_date, "GIT_COMMITTER_DATE": commit_date}
            if commit_date is not None
            else None
        ),
    )
    return repo


def run(
    home: Path,
    *args: str,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args],
        cwd=cwd or home,
        env={**os.environ, "HOME": str(home), **(extra_env or {})},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def board(home: Path) -> dict:
    return json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))


def make_plan_over_budget(repo: Path) -> None:
    plan = repo / "PLAN.md"
    with plan.open("a", encoding="utf-8") as stream:
        stream.write("\n<!-- " + ("x" * HOT_PLAN_LIMIT) + " -->\n")
    git(repo, "add", "PLAN.md")
    git(repo, "commit", "--quiet", "-m", "exceed the hot-plan byte budget")


class PartitionedPlansUseOneLogicalReadBoundary(unittest.TestCase):
    def test_committed_tree_materializes_the_same_authority_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            source = (repo / "PLAN.md").read_bytes()
            plan = install_plan_tree(repo, source)
            git(repo, "add", "PLAN.md", "PLAN.d")
            git(repo, "commit", "--quiet", "-m", "partition plan")

            snapshot = board_api.open_plan(plan)
            token, content = board_api.committed_plan_snapshot(plan)

            self.assertTrue(snapshot.is_tree)
            self.assertEqual(board_api.read_plan_bytes(plan), source)
            self.assertEqual(content, source)
            self.assertEqual(token["relative"], "PLAN.md")

    def test_tree_state_snapshot_grades_logical_plan_not_the_small_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            source = (repo / "PLAN.md").read_bytes()
            plan = install_plan_tree(repo, source)

            state, content = board_api.plan_state_snapshot(plan)

            self.assertRegex(state, r"^[0-9a-f]{64}$")
            self.assertEqual(content, source)

    def test_oversized_tree_is_refused_before_any_object_is_traversed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            source = (repo / "PLAN.md").read_bytes() + b"\n<!-- " + b"x" * 8192 + b" -->\n"
            plan = install_plan_tree(repo, source)
            snapshot = board_api.open_plan(plan)
            self.assertLess(len(snapshot.root_bytes), len(source))

            with mock.patch.object(
                board_api, "MAX_PLAN_BYTES", len(source) - 1
            ), mock.patch.object(
                board_api._plan_store.PlanSnapshot,
                "materialize",
                side_effect=AssertionError("oversized tree was traversed"),
            ):
                with self.assertRaisesRegex(
                    board_api.BoardError, "plan exceeds the bounded size limit"
                ):
                    board_api.read_plan_bytes(plan)
                state, content = board_api.plan_state_snapshot(plan)

            self.assertRegex(state, r"^[0-9a-f]{64}$")
            self.assertIsNone(content)

    def test_dirty_tree_object_refuses_a_committed_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            source = (repo / "PLAN.md").read_bytes()
            plan = install_plan_tree(repo, source)
            git(repo, "add", "PLAN.md", "PLAN.d")
            git(repo, "commit", "--quiet", "-m", "partition plan")
            object_path = next((repo / "PLAN.d" / "objects" / "sha256").glob("*/*"))
            object_path.write_bytes(object_path.read_bytes() + b"dirty")

            with self.assertRaisesRegex(
                board_api.BoardError,
                "entity plan or its staged index changed",
            ):
                board_api.committed_plan_snapshot(plan)


class PublicIdentityNeverCarriesCredentials(unittest.TestCase):
    def test_remote_query_and_fragment_never_change_or_leak_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            secret = "AKIA" + "IOSFODNN7EXAMPLE"
            git(repo, "remote", "add", "origin", f"https://github.com/org/project.git?token={secret}")

            before = board_api.entity_id(repo / "PLAN.md")
            locator = board_api.public_plan_locator(repo / "PLAN.md")
            git(
                repo,
                "remote",
                "set-url",
                "origin",
                "https://github.com/org/project.git?token=rotated#private",
            )

            self.assertEqual(board_api.entity_id(repo / "PLAN.md"), before)
            self.assertEqual(board_api.normalized_origin(
                f"https://github.com/org/project.git?token={secret}#private"
            ), "github.com/org/project")
            self.assertNotIn(secret, locator)
            self.assertNotIn("token=", locator)

    def test_default_remote_ports_do_not_split_one_logical_repository(self) -> None:

        self.assertEqual(
            board_api.normalized_origin("ssh://git@github.com:22/org/repo.git"),
            board_api.normalized_origin("git@github.com:org/repo.git"),
        )
        self.assertEqual(
            board_api.normalized_origin("https://github.com:443/org/repo.git"),
            board_api.normalized_origin("https://github.com/org/repo.git"),
        )
        self.assertEqual(
            board_api.normalized_origin("http://example.test:80/org/repo.git"),
            board_api.normalized_origin("http://example.test/org/repo.git"),
        )

    def test_plan_locator_shares_one_repo_resolution_per_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            child = repo / "plans" / "child"
            child.mkdir(parents=True)
            (child / "PLAN.md").write_text(
                (repo / "PLAN.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            git(repo, "add", "plans")
            git(repo, "commit", "--quiet", "-m", "child plan")

            module = fresh_board_module("shadow_locator_cache_count")
            calls: list[tuple[str, ...]] = []
            real_git = module._git

            def counting_git(git_root: Path, *args: str, **kwargs):
                calls.append(args)
                return real_git(git_root, *args, **kwargs)

            real = repo.resolve()
            module._git = counting_git
            try:
                with module.repository_identity_cache():
                    first = module.public_plan_locator(real / "PLAN.md")
                    second = module.public_plan_locator(real / "plans" / "child" / "PLAN.md")
            finally:
                module._git = real_git

            toplevels = sum(
                1 for args in calls if args[:2] == ("rev-parse", "--show-toplevel")
            )
            self.assertEqual(toplevels, 1, calls)
            self.assertTrue(first.startswith("project@"), first)
            self.assertTrue(first.endswith("/PLAN.md"), first)
            self.assertTrue(second.endswith("/plans/child/PLAN.md"), second)

    def test_commit_times_answers_many_plans_in_one_git_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            plans = [repo / "PLAN.md"]
            for index in range(3):
                child = repo / "plans" / f"child{index}"
                child.mkdir(parents=True)
                (child / "PLAN.md").write_text(
                    (repo / "PLAN.md").read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                plans.append(child / "PLAN.md")
            git(repo, "add", "plans")
            git(repo, "commit", "--quiet", "-m", "child plans")

            module = fresh_board_module("shadow_commit_times_batch")
            calls: list[tuple[str, ...]] = []
            real_git = module._git

            def counting_git(git_root: Path, *args: str, **kwargs):
                calls.append(args)
                return real_git(git_root, *args, **kwargs)

            module._git = counting_git
            try:
                times = module.plan_commit_times(repo, plans)
            finally:
                module._git = real_git

            log_calls = [args for args in calls if args and args[0] == "log"]
            self.assertEqual(len(log_calls), 1, calls)
            self.assertIn("--name-only", log_calls[0])
            self.assertEqual(len(times), len(plans))
            self.assertTrue(all(isinstance(value, int) for value in times.values()))
            latest = git(repo, "log", "-1", "--format=%ct", "--", "PLAN.md")
            self.assertEqual(
                times[str(Path(os.path.abspath(repo / "PLAN.md")))], int(latest)
            )

    def test_one_repo_resolves_toplevel_and_head_once_per_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            child = repo / "plans" / "child"
            child.mkdir(parents=True)
            (child / "PLAN.md").write_text(
                (repo / "PLAN.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            git(repo, "add", "plans")
            git(repo, "commit", "--quiet", "-m", "child plan")

            module = fresh_board_module("shadow_snapshot_cache_count")
            calls: list[tuple[str, ...]] = []
            real_git = module._git

            def counting_git(git_root: Path, *args: str, **kwargs):
                calls.append(args)
                return real_git(git_root, *args, **kwargs)

            module._git = counting_git
            try:
                with module.repository_identity_cache():
                    first_token, first_bytes = module.head_plan_snapshot(
                        repo / "PLAN.md", repo=repo
                    )
                    second_token, second_bytes = module.head_plan_snapshot(
                        child / "PLAN.md", repo=repo
                    )
                    # No authenticated repo: the fallback still resolves it.
                    module.head_plan_snapshot(repo / "PLAN.md")
            finally:
                module._git = real_git

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first_token["repo"], second_token["repo"])
            self.assertEqual(first_token["head"], second_token["head"])
            self.assertNotEqual(first_token["relative"], second_token["relative"])
            toplevels = sum(
                1 for args in calls if args[:2] == ("rev-parse", "--show-toplevel")
            )
            heads = sum(
                1 for args in calls if args[:2] == ("rev-parse", "HEAD")
            )
            # The authenticated caller never re-resolves the repo; only the
            # fallback call probes the toplevel, exactly once.
            self.assertEqual(toplevels, 1, calls)
            # First read memoized per repo; the post-read race-guard recheck
            # stays a real probe on every call — three calls, three rechecks,
            # plus the one memoized initial read. Uncached this is six.
            self.assertEqual(heads, 4, calls)

    def test_a_plan_owned_origin_must_already_be_normalized(self) -> None:

        self.assertEqual(
            board_api.well_formed_proof_origin("github.com/example/widget"),
            "github.com/example/widget",
        )
        for value in (
            "",
            "git@github.com:example/widget.git",
            "https://github.com/example/widget.git",
            "/tmp/widget.git",
            "local-remote:/tmp/widget",
            "github.com",
            "./.forge",
            "example/widget",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    board_api.well_formed_proof_origin(value)

    def test_filesystem_remotes_are_resolved_against_each_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left_parent = root / "left"
            right_parent = root / "right"
            left_parent.mkdir()
            right_parent.mkdir()
            left = project(left_parent, name="checkout")
            right = project(right_parent, name="checkout")
            git(left, "remote", "add", "origin", "../forge.git")
            git(right, "remote", "add", "origin", "../forge.git")

            self.assertNotEqual(
                board_api.entity_id(left / "PLAN.md"),
                board_api.entity_id(right / "PLAN.md"),
            )
            git(right, "remote", "set-url", "origin", str(left_parent / "forge.git"))
            self.assertEqual(
                board_api.entity_id(left / "PLAN.md"),
                board_api.entity_id(right / "PLAN.md"),
            )

    def test_git_introspection_failure_never_becomes_a_checkout_path_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            git(repo, "remote", "add", "origin", "git@example.invalid:team/project.git")
            branch = subprocess.run(
                ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            git(repo, "config", f"branch.{branch}.remote", "origin")
            git(repo, "config", f"branch.{branch}.merge", "refs/heads/main")
            module = fresh_board_module("shadow_git_failure")
            original = module._remote_claim._git
            probes = (
                ("symbolic-ref", "--quiet", "--short", "HEAD"),
                (
                    "config",
                    "--null",
                    "--get-regexp",
                    r"^branch\..*\.(remote|merge)$",
                ),
                ("config", "--get-all", "remote.origin.url"),
                ("remote", "get-url", "--all", "--", "origin"),
                ("remote", "get-url", "--push", "--all", "--", "origin"),
            )
            for failed_probe in probes:
                with self.subTest(probe=failed_probe):
                    def fail_selected(root: Path, *args: str, **kwargs):
                        if args == failed_probe:
                            return subprocess.CompletedProcess(
                                args,
                                124,
                                b"",
                                b"timed out",
                            )
                        return original(root, *args, **kwargs)

                    with mock.patch.object(
                        module._remote_claim,
                        "_git",
                        side_effect=fail_selected,
                    ):
                        with self.assertRaisesRegex(
                            module.BoardError,
                            "project Git identity could not be read",
                        ):
                            module.entity_id(repo / "PLAN.md")

    def test_git_environment_cannot_redirect_repository_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root, name="expected")
            injected = project(root, name="injected")
            expected = board_api.entity_id(repo / "PLAN.md")
            expected_locator = board_api.public_plan_locator(repo / "PLAN.md")
            expected_token, expected_content = board_api.committed_plan_snapshot(
                repo / "PLAN.md"
            )

            with mock.patch.dict(
                os.environ,
                {
                    "GIT_DIR": str(injected / ".git"),
                    "GIT_WORK_TREE": str(injected),
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "remote.origin.url",
                    "GIT_CONFIG_VALUE_0": "git@example.invalid:wrong/repo.git",
                },
                clear=False,
            ):
                self.assertEqual(board_api.entity_id(repo / "PLAN.md"), expected)
                self.assertEqual(
                    board_api.public_plan_locator(repo / "PLAN.md"),
                    expected_locator,
                )
                token, content = board_api.committed_plan_snapshot(repo / "PLAN.md")

            self.assertEqual(token, expected_token)
            self.assertEqual(content, expected_content)

    def test_replacement_refs_cannot_substitute_committed_plan_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            plan = repo / "PLAN.md"
            expected_token, expected_content = board_api.head_plan_snapshot(plan)
            original_head = expected_token["head"]
            plan.write_text("# substituted plan\n", encoding="utf-8")
            git(repo, "commit", "-qam", "replacement payload")
            replacement_head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            git(repo, "reset", "--hard", original_head)
            git(repo, "replace", original_head, replacement_head)
            unsanitized_env = {
                name: value
                for name, value in os.environ.items()
                if name != "GIT_NO_REPLACE_OBJECTS"
            }
            substituted = subprocess.run(
                ["git", "-C", str(repo), "show", "HEAD:PLAN.md"],
                capture_output=True,
                text=True,
                check=True,
                env=unsanitized_env,
            )
            self.assertEqual(substituted.stdout, "# substituted plan\n")

            head_token, head_content = board_api.head_plan_snapshot(plan)
            committed_token, committed_content = board_api.committed_plan_snapshot(plan)

            self.assertEqual(head_token, expected_token)
            self.assertEqual(committed_token, expected_token)
            self.assertEqual(head_content, expected_content)
            self.assertEqual(committed_content, expected_content)

    def test_secret_shaped_origin_path_uses_an_opaque_public_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            secret = "ghp_" + "A" * 24
            git(repo, "remote", "add", "origin", f"https://github.com/org/{secret}/repo.git")

            locator = board_api.public_plan_locator(repo / "PLAN.md")

            self.assertNotIn(secret, locator)
            self.assertRegex(locator, r"^entity@[0-9a-f]{8}/PLAN\.md$")

    def test_owner_is_public_safe_before_it_can_enter_the_board(self) -> None:
        for owner in (
            str(Path("/", "Users", "leo", "private")),
            "AKIA" + "IOSFODNN7EXAMPLE",
            "   ",
            " seat-a",
            "seat-a ",
            "seat\u200b-a",
            "seat\u202e-a",
        ):
            with self.assertRaises(ValueError):
                board_api.validate_owner(owner)


class SymlinkedPlansNeverBecomeAuthority(unittest.TestCase):
    def test_post_registration_symlink_swap_refuses_without_board_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            registered = run(home, "status", "--json", cwd=repo)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            before = (home / ".shadow" / "board.json").read_bytes()
            before_head = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            external = root / "external-plan"
            external.write_bytes((repo / "PLAN.md").read_bytes())
            (repo / "PLAN.md").unlink()
            (repo / "PLAN.md").symlink_to(external)
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "replace plan with symlink")

            refused = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )

            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertIn("non-symlink", refused.stderr)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                before_head,
            )

    def test_post_registration_ancestor_swap_is_broken_and_never_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            repo = project(portfolio)
            scope = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            self.assertEqual(
                run(home, "status", "--json", cwd=root, extra_env=scope).returncode,
                0,
            )
            outside = root / "outside-repo"
            repo.rename(outside)
            repo.symlink_to(outside, target_is_directory=True)
            plan = outside / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "TASK-BODY-MUST-NOT-ENTER-THE-BOARD", "EXTERNAL-AUTHORITY-MUST-NOT-RENDER"
                ),
                encoding="utf-8",
            )
            git(outside, "add", "PLAN.md")
            git(outside, "commit", "--quiet", "-m", "external change")

            observed = run(home, "status", "--json", cwd=root, extra_env=scope)
            refused = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )

            self.assertEqual(observed.returncode, 1, observed.stderr)
            self.assertNotIn("EXTERNAL-AUTHORITY-MUST-NOT-RENDER", observed.stdout)
            self.assertTrue(json.loads(observed.stdout)["v4_plans"][0]["broken"])
            self.assertEqual(refused.returncode, 2, refused.stderr)


class ColdSeatsResumeThroughBoardEntityIds(unittest.TestCase):
    def test_status_by_keeps_every_entity_owned_by_the_seat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            alpha = project(root, name="alpha", priority=2)
            beta = project(root, name="beta", priority=3)
            project(root, name="unowned", priority=1)
            registered = run(home, "status", "--root", str(root))
            self.assertEqual(registered.returncode, 0, registered.stderr)
            for repo in (alpha, beta):
                claimed = run(
                    home,
                    "throw",
                    "--repo",
                    str(repo),
                    "--task",
                    "~aa11",
                    "--by",
                    "cold-seat",
                )
                self.assertEqual(claimed.returncode, 0, claimed.stderr)

            observed = run(
                home,
                "status",
                "--root",
                str(root),
                "--by",
                "cold-seat",
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertIn("Portfolio: 3 entities", observed.stdout)
            self.assertIn("alpha —", observed.stdout)
            self.assertIn("beta —", observed.stdout)
            self.assertNotIn("unowned —", observed.stdout)
            self.assertEqual(observed.stdout.count("Continue:"), 2)

    def test_restart_resumes_owned_row_and_two_seats_take_disjoint_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            unrelated = root / "unrelated"
            home.mkdir()
            unrelated.mkdir()
            repo = project(root)
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    " | proof: cmd true | needs: ~aa11", " | proof: cmd true"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "make rows independently reachable")

            first = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "codex-mac"
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            identity = board(home)["entities"][0]["id"]

            cold_status = run(home, "status", "--by", "codex-mac", cwd=unrelated)
            self.assertEqual(cold_status.returncode, 0, cold_status.stderr)
            self.assertIn(
                f"Continue: shadow amp --entity {identity} --task '~aa11' --by codex-mac",
                cold_status.stdout,
            )
            resumed = run(
                home, "amp", "--entity", identity, "--by", "codex-mac", cwd=unrelated
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("TASK-BODY-MUST-NOT-ENTER-THE-BOARD ~aa11", resumed.stdout)

            unclaimed = run(
                home, "amp", "--entity", identity, "--by", "claude-mac", cwd=unrelated
            )
            self.assertEqual(unclaimed.returncode, 1, unclaimed.stderr)
            self.assertIn("shadow throw --entity", unclaimed.stderr)
            next_move = run(home, "status", "--by", "claude-mac", cwd=unrelated)
            self.assertIn(
                f"Claim: shadow throw --entity {identity} --task '~bb22' --by claude-mac",
                next_move.stdout,
            )
            rendered = next(
                line.split("Claim: ", 1)[1]
                for line in next_move.stdout.splitlines()
                if "Claim: " in line
            ).replace("shadow ", f"{shlex.quote(str(CLI))} ", 1)
            shell = shutil.which("zsh") or shutil.which("bash")
            self.assertIsNotNone(shell, "claim-command proof needs a tilde-expanding shell")
            second = subprocess.run(
                [shell, "-lc", rendered],
                cwd=unrelated,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            claims = board(home)["claims"]
            self.assertEqual(
                {(claim["row"], claim["owner"]) for claim in claims},
                {("~aa11", "codex-mac"), ("~bb22", "claude-mac")},
            )
            claude_resume = run(
                home, "amp", "--entity", identity, "--by", "claude-mac", cwd=unrelated
            )
            self.assertEqual(claude_resume.returncode, 0, claude_resume.stderr)
            self.assertIn("the outcome is proven ~bb22", claude_resume.stdout)
            codex_status = run(home, "status", "--by", "codex-mac", cwd=unrelated)
            self.assertIn(
                f"Continue: shadow amp --entity {identity} --task '~aa11' --by codex-mac",
                codex_status.stdout,
            )
            self.assertIn(
                "In flight: [pending] the outcome is proven | Owner: claude-mac",
                codex_status.stdout,
            )
            self.assertNotIn("--by claude-mac", codex_status.stdout)

    def test_new_claim_requires_an_explicit_stable_seat_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            refused = run(home, "throw", "--repo", str(repo), "--task", "~aa11")
            self.assertEqual(refused.returncode, 2)
            self.assertIn("--by", refused.stderr)
            self.assertFalse((home / ".shadow").exists())


class TheBoardHoldsPointersNeverRowCopies(unittest.TestCase):
    def test_project_record_is_only_a_locator_and_resume_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            before = (repo / "PLAN.md").read_bytes()

            result = run(home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = board(home)
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertTrue(
                {"claims", "projects", "entities", "revision", "schema"}.issubset(payload)
            )
            self.assertTrue(
                {"id", "project", "plan", "resume"}.issubset(payload["entities"][0])
            )
            self.assertEqual(payload["projects"], [{"id": "project", "priority": 2}])
            self.assertEqual(payload["entities"][0]["plan"], str((repo / "PLAN.md").resolve()))
            self.assertEqual(payload["entities"][0]["resume"], "~aa11")
            self.assertTrue(
                {"claimed_at", "owner", "entity", "row"}.issubset(payload["claims"][0])
            )
            self.assertEqual(
                payload["claims"][0]["entity"], payload["entities"][0]["id"]
            )
            copied_task_keys = {"text", "proof", "body", "milestone"}
            self.assertFalse(copied_task_keys.intersection(payload["entities"][0]))
            self.assertFalse(copied_task_keys.intersection(payload["claims"][0]))
            serialized = json.dumps(payload, sort_keys=True)
            for copied in (
                "TASK-BODY-MUST-NOT-ENTER-THE-BOARD",
                PROOF_SENTINEL,
            ):
                self.assertNotIn(copied, serialized)
                for path in (home / ".shadow").rglob("*"):
                    if path.is_file() and ".git" not in path.parts:
                        self.assertNotIn(copied.encode(), path.read_bytes())
            self.assertTrue((home / ".shadow" / ".git").is_dir())


class AWriteCountsWithNoRemoteConfigured(unittest.TestCase):
    def test_fresh_process_reads_a_successful_local_only_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            unrelated = root / "unrelated"
            home.mkdir()
            unrelated.mkdir()
            repo = project(root)

            claimed = run(home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a")
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            remotes = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "remote"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(remotes.stdout, "")
            board_path = home / ".shadow" / "board.json"
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "status", "--porcelain", "--", "board.json"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "show", "HEAD:board.json"],
                    capture_output=True,
                    check=True,
                ).stdout,
                board_path.read_bytes(),
            )

            observed = run(home, "status", "--json", cwd=unrelated)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            report = json.loads(observed.stdout)
            self.assertEqual(report["root_board"]["revision"], board(home)["revision"])
            self.assertEqual(report["root_board"]["entities"][0]["resume"], "~aa11")
            self.assertEqual(report["root_board"]["claims"][0]["owner"], "seat-a")

            accepted = run(
                home,
                "accept",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            payload = board(home)
            self.assertEqual(payload["claims"], [])
            self.assertEqual(payload["entities"][0]["resume"], "~bb22")

            reclaimed = run(
                home, "throw", "--repo", str(repo), "--task", "~bb22", "--by", "seat-b"
            )
            self.assertEqual(reclaimed.returncode, 0, reclaimed.stderr)
            (repo / "PLAN.md").unlink()
            broken = run(home, "status", cwd=unrelated)
            self.assertEqual(broken.returncode, 1, broken.stderr)
            self.assertIn("project", broken.stdout.lower())
            self.assertIn("missing or unreadable", broken.stdout)

            recovery = run(home, "status", "--in-flight", "--json", cwd=unrelated)
            self.assertEqual(recovery.returncode, 1, recovery.stderr)
            recovery_payload = json.loads(recovery.stdout)
            self.assertEqual(recovery_payload["rows"][0]["id"], "~bb22")
            self.assertTrue(recovery_payload["rows"][0]["broken"])

    def test_claim_journal_failure_restores_board_and_head_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            board_api.ensure(home=home)
            board_root = home / ".shadow"
            board_path = board_root / "board.json"
            unrelated = board_root / "unrelated.txt"
            unrelated.write_bytes(b"base\n")
            subprocess.run(
                ["git", "-C", str(board_root), "add", "-f", "--", unrelated.name],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(board_root), "commit", "--quiet", "-m", "unrelated"],
                check=True,
            )
            unrelated.write_bytes(b"staged\n")
            subprocess.run(
                ["git", "-C", str(board_root), "add", "-f", "--", unrelated.name],
                check=True,
            )
            unrelated.write_bytes(b"worktree\n")
            untracked = board_root / "untracked.txt"
            untracked.write_bytes(b"untracked\n")
            before_bytes = board_path.read_bytes()
            before_head = board_api._journal_head(board_root)
            before_unrelated = {
                "cached": subprocess.run(
                    ["git", "-C", str(board_root), "diff", "--cached", "--binary"],
                    capture_output=True,
                    check=True,
                ).stdout,
                "worktree": subprocess.run(
                    ["git", "-C", str(board_root), "diff", "--binary"],
                    capture_output=True,
                    check=True,
                ).stdout,
                "bytes": unrelated.read_bytes(),
                "untracked": untracked.read_bytes(),
            }
            original_commit = board_api._commit

            def fail_claim(root: Path, message: str) -> None:
                original_commit(root, message)
                if message == "shadow board: claim ~aa11":
                    raise board_api.BoardError("injected claim journal failure")

            with mock.patch.object(board_api, "_commit", side_effect=fail_claim):
                with self.assertRaisesRegex(
                    board_api.BoardError, "injected claim journal failure"
                ):
                    board_api.claim(
                        repo / "PLAN.md",
                        "~aa11",
                        "failed-seat",
                        project="project",
                        priority=2,
                        home=home,
                    )

            self.assertEqual(board_path.read_bytes(), before_bytes)
            self.assertEqual(board_api._journal_head(board_root), before_head)
            self.assertEqual(board(home)["claims"], [])
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(board_root),
                        "status",
                        "--porcelain=v1",
                        "--",
                        "board.json",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )
            self.assertEqual(
                {
                    "cached": subprocess.run(
                        ["git", "-C", str(board_root), "diff", "--cached", "--binary"],
                        capture_output=True,
                        check=True,
                    ).stdout,
                    "worktree": subprocess.run(
                        ["git", "-C", str(board_root), "diff", "--binary"],
                        capture_output=True,
                        check=True,
                    ).stdout,
                    "bytes": unrelated.read_bytes(),
                    "untracked": untracked.read_bytes(),
                },
                before_unrelated,
            )

            successor = board_api.claim(
                repo / "PLAN.md",
                "~aa11",
                "successor-seat",
                project="project",
                priority=2,
                home=home,
            )

            self.assertEqual(successor["claim"]["owner"], "successor-seat")
            self.assertEqual(board(home)["claims"][0]["owner"], "successor-seat")

    def test_claim_precommit_failure_unstages_only_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            board_api.ensure(home=home)
            board_root = home / ".shadow"
            board_path = board_root / "board.json"
            before_bytes = board_path.read_bytes()
            before_head = board_api._journal_head(board_root)
            original_commit = board_api._commit

            def fail_after_add(root: Path, message: str) -> None:
                if message == "shadow board: claim ~aa11":
                    added = board_api._git(root, "add", "--", board_api.BOARD_NAME)
                    self.assertEqual(added.returncode, 0, added.stderr)
                    raise board_api.BoardError("injected post-add failure")
                original_commit(root, message)

            with mock.patch.object(board_api, "_commit", side_effect=fail_after_add):
                with self.assertRaisesRegex(board_api.BoardError, "post-add failure"):
                    board_api.claim(
                        repo / "PLAN.md",
                        "~aa11",
                        "failed-seat",
                        project="project",
                        priority=2,
                        home=home,
                    )

            self.assertEqual(board_path.read_bytes(), before_bytes)
            self.assertEqual(board_api._journal_head(board_root), before_head)
            self.assertEqual(board(home)["claims"], [])
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(board_root),
                        "status",
                        "--porcelain=v1",
                        "--",
                        "board.json",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )

    def test_claim_failure_preserves_foreign_index_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            board_api.ensure(home=home)
            board_root = home / ".shadow"
            board_path = board_root / "board.json"
            index_lock = board_root / ".git" / "index.lock"
            before_bytes = board_path.read_bytes()
            before_head = board_api._journal_head(board_root)
            original_commit = board_api._commit

            def fail_before_add(root: Path, message: str) -> None:
                if message == "shadow board: claim ~aa11":
                    index_lock.write_bytes(b"foreign")
                    original_commit(root, message)
                    self.fail("Git unexpectedly accepted an existing index lock")
                original_commit(root, message)

            with mock.patch.object(board_api, "_commit", side_effect=fail_before_add):
                with self.assertRaisesRegex(
                    board_api.BoardError,
                    "could not record its local receipt",
                ):
                    board_api.claim(
                        repo / "PLAN.md",
                        "~aa11",
                        "failed-seat",
                        project="project",
                        priority=2,
                        home=home,
                    )

            self.assertEqual(board_path.read_bytes(), before_bytes)
            self.assertEqual(board_api._journal_head(board_root), before_head)
            self.assertEqual(board(home)["claims"], [])
            self.assertEqual(index_lock.read_bytes(), b"foreign")
            index_lock.unlink()

    def test_claim_failure_does_not_rewind_unexpected_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            board_api.ensure(home=home)
            board_root = home / ".shadow"
            board_path = board_root / "board.json"
            before_bytes = board_path.read_bytes()
            before_head = board_api._journal_head(board_root)
            foreign_heads: list[str] = []
            original_commit = board_api._commit

            def fail_after_foreign_child(root: Path, message: str) -> None:
                original_commit(root, message)
                if message == "shadow board: claim ~aa11":
                    foreign = root / "foreign.txt"
                    foreign.write_bytes(b"foreign\n")
                    subprocess.run(
                        ["git", "-C", str(root), "add", "-f", "--", foreign.name],
                        check=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(root), "commit", "--quiet", "-m", "foreign child"],
                        check=True,
                    )
                    foreign_heads.append(board_api._journal_head(root))
                    raise board_api.BoardError("injected foreign child")

            with mock.patch.object(
                board_api,
                "_commit",
                side_effect=fail_after_foreign_child,
            ):
                with self.assertRaisesRegex(
                    board_api.BoardError,
                    "exact recovery also failed",
                ):
                    board_api.claim(
                        repo / "PLAN.md",
                        "~aa11",
                        "failed-seat",
                        project="project",
                        priority=2,
                        home=home,
                    )

            self.assertEqual(board_path.read_bytes(), before_bytes)
            self.assertEqual(len(foreign_heads), 1)
            self.assertNotEqual(foreign_heads[0], before_head)
            self.assertEqual(board_api._journal_head(board_root), foreign_heads[0])
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(board_root), "show", "HEAD:foreign.txt"],
                    capture_output=True,
                    check=True,
                ).stdout,
                b"foreign\n",
            )

    def test_global_commit_signing_cannot_wedge_the_local_board_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            environment = {**os.environ, "HOME": str(home)}
            subprocess.run(
                ["git", "config", "--global", "commit.gpgSign", "true"],
                env=environment,
                check=True,
            )
            subprocess.run(
                ["git", "config", "--global", "gpg.program", str(root / "missing-gpg")],
                env=environment,
                check=True,
            )

            claimed = run(
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
                "seat-a",
            )

            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            board_path = home / ".shadow" / "board.json"
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "show", "HEAD:board.json"],
                    capture_output=True,
                    check=True,
                ).stdout,
                board_path.read_bytes(),
            )

    def test_local_board_commit_waits_for_automatic_git_maintenance(self) -> None:
        module = fresh_board_module("shadow_root_board_commit_test")
        calls: list[tuple[str, ...]] = []

        def observe_git(_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(
                ["git", *args],
                1 if args[:2] == ("diff", "--cached") else 0,
                "",
                "",
            )

        original_git = module._git
        module._git = observe_git
        try:
            module._commit(Path("/unused"), "shadow board: deterministic receipt")
        finally:
            module._git = original_git

        self.assertEqual(
            calls[-1][:9],
            (
                "-c", "core.hooksPath=/dev/null",
                "-c", "commit.gpgSign=false",
                "-c", "maintenance.autoDetach=false",
                "-c", "gc.autoDetach=false",
                "commit",
            ),
        )

    def test_real_board_commit_joins_automatic_git_maintenance(self) -> None:
        module = fresh_board_module("shadow_root_board_trace_test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "board"
            root.mkdir()
            git(root, "init", "--quiet")
            git(root, "config", "user.name", "Trace Test")
            git(root, "config", "user.email", "trace@example.invalid")
            (root / "board.json").write_text("{}\n", encoding="utf-8")
            trace = Path(tmp) / "git-trace.json"

            with mock.patch.dict(os.environ, {"GIT_TRACE2_EVENT": str(trace)}):
                module._commit(root, "shadow board: trace maintenance")

            events = [json.loads(line) for line in trace.read_text().splitlines()]
            maintenance_argv = [
                event["argv"]
                for event in events
                if event.get("event") == "child_start"
                and (
                    event.get("argv", [])[:4]
                    == ["git", "maintenance", "run", "--auto"]
                    or event.get("argv", [])[:3] == ["git", "gc", "--auto"]
                )
            ]
            self.assertTrue(maintenance_argv)
            # Modern Git spells the foreground choice `--no-detach`; older
            # Git inherits gc.autoDetach=false and emits no detach flag.
            self.assertTrue(all("--detach" not in argv for argv in maintenance_argv))


class LogicalIdentityOutranksCheckoutPaths(unittest.TestCase):
    def test_discarded_sibling_metadata_does_not_churn_the_board_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root, display_name="alpha")
            git(repo, "remote", "add", "origin", "git@example.invalid:team/shared.git")
            registered = run(home, "status", "--root", str(repo), "--json")
            self.assertEqual(registered.returncode, 0, registered.stderr)
            sibling = root / "sibling"
            git(repo, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")
            plan = sibling / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8")
                .replace("- Project: alpha", "- Project: beta")
                .replace("- Priority: 2", "- Priority: 5"),
                encoding="utf-8",
            )
            git(sibling, "add", "PLAN.md")
            git(sibling, "commit", "--quiet", "-m", "divergent sibling metadata")
            board_path = home / ".shadow" / "board.json"
            before = board_path.read_bytes()
            head = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            first = run(home, "status", "--root", str(sibling), "--json")
            second = run(home, "status", "--root", str(sibling), "--json")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(board_path.read_bytes(), before)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                head,
            )

    def test_two_worktrees_of_one_origin_cannot_both_claim_the_same_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            git(repo, "remote", "add", "origin", "git@github.com:example/shared.git")
            sibling = root / "sibling-worktree"
            git(repo, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")

            first = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            second = run(
                home,
                "throw",
                "--repo",
                str(sibling),
                "--task",
                "~aa11",
                "--by",
                "seat-b",
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 1, second.stderr)
            self.assertIn("claimed by seat-a", second.stderr)
            payload = board(home)
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(len(payload["entities"]), 1)
            self.assertEqual(len(payload["claims"]), 1)

    def test_dot_upstreams_share_one_identity_across_linked_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            primary_branch = subprocess.run(
                ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            sibling = root / "sibling-worktree"
            git(repo, "worktree", "add", "--quiet", "-b", "sibling", str(sibling), "HEAD")
            for checkout, branch in ((repo, primary_branch), (sibling, "sibling")):
                git(checkout, "config", f"branch.{branch}.remote", ".")
                git(
                    checkout,
                    "config",
                    f"branch.{branch}.merge",
                    f"refs/heads/{primary_branch}",
                )

            self.assertEqual(
                board_api.entity_id(repo / "PLAN.md"),
                board_api.entity_id(sibling / "PLAN.md"),
            )

    def test_compatible_local_entities_merge_when_their_git_identity_converges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            alpha = project(portfolio, name="alpha", display_name="shared")
            beta = project(portfolio, name="beta", display_name="shared")
            for repo in (alpha, beta):
                plan = repo / "PLAN.md"
                plan.write_text(
                    plan.read_text(encoding="utf-8").replace(" | needs: ~aa11", ""),
                    encoding="utf-8",
                )
                git(repo, "add", "PLAN.md")
                git(repo, "commit", "--quiet", "-m", "independent rows")
            scope = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            seeded = run(home, "status", "--json", cwd=root, extra_env=scope)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            self.assertEqual(len(board(home)["entities"]), 2)
            self.assertEqual(
                run(
                    home, "throw", "--repo", str(alpha), "--task", "~aa11", "--by", "seat-a"
                ).returncode,
                0,
            )
            self.assertEqual(
                run(
                    home, "throw", "--repo", str(beta), "--task", "~bb22", "--by", "seat-b"
                ).returncode,
                0,
            )
            remote = "git@example.invalid:team/converged.git"
            git(alpha, "remote", "add", "origin", remote)
            git(beta, "remote", "add", "origin", remote)

            before = board(home)["revision"]
            merged = run(home, "status", "--json", cwd=root, extra_env=scope)

            self.assertEqual(merged.returncode, 0, merged.stderr)
            payload = board(home)
            self.assertEqual(payload["revision"], before + 1)
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(len(payload["entities"]), 1)
            self.assertEqual(payload["entities"][0]["resume"], "~aa11")
            self.assertEqual(
                {(claim["row"], claim["owner"]) for claim in payload["claims"]},
                {("~aa11", "seat-a"), ("~bb22", "seat-b")},
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "show", "HEAD:board.json"],
                    capture_output=True,
                    check=True,
                ).stdout,
                (home / ".shadow" / "board.json").read_bytes(),
            )

    def test_conflicting_convergence_is_unchanged_until_one_exact_owner_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            alpha = project(portfolio, name="alpha", display_name="shared")
            beta = project(portfolio, name="beta", display_name="shared")
            scope = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            self.assertEqual(
                run(home, "status", "--json", cwd=root, extra_env=scope).returncode,
                0,
            )
            for repo, owner in ((alpha, "seat-a"), (beta, "seat-b")):
                result = run(
                    home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", owner
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            remote = "git@example.invalid:team/converged.git"
            git(alpha, "remote", "add", "origin", remote)
            git(beta, "remote", "add", "origin", remote)
            board_path = home / ".shadow" / "board.json"
            before = board_path.read_bytes()
            head_before = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            refused = run(home, "status", "--json", cwd=root, extra_env=scope)

            self.assertEqual(refused.returncode, 1)
            self.assertIn("both claim ~aa11 by seat-a, seat-b", refused.stderr)
            self.assertEqual(board_path.read_bytes(), before)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                head_before,
            )

            returned = run(
                home, "return", "--repo", str(beta), "--row", "~aa11", "--by", "seat-b"
            )
            self.assertEqual(returned.returncode, 0, returned.stderr)
            converged = run(home, "status", "--json", cwd=root, extra_env=scope)
            self.assertEqual(converged.returncode, 0, converged.stderr)
            payload = board(home)
            self.assertEqual(len(payload["entities"]), 1)
            self.assertEqual(len(payload["claims"]), 1)
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")

    def test_identity_cycle_rekeys_and_merges_without_moving_claims_between_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            alpha = project(portfolio, name="alpha", display_name="shared")
            beta = project(portfolio, name="beta", display_name="shared")
            gamma = project(portfolio, name="gamma", display_name="shared")
            for repo, remote in (
                (alpha, "git@example.invalid:team/a.git"),
                (beta, "git@example.invalid:team/b.git"),
                (gamma, "git@example.invalid:team/c.git"),
            ):
                plan = repo / "PLAN.md"
                plan.write_text(
                    plan.read_text(encoding="utf-8").replace(" | needs: ~aa11", ""),
                    encoding="utf-8",
                )
                git(repo, "add", "PLAN.md")
                git(repo, "commit", "--quiet", "-m", "make rows independent")
                git(repo, "remote", "add", "origin", remote)
            scope = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            self.assertEqual(
                run(home, "status", "--json", cwd=root, extra_env=scope).returncode,
                0,
            )
            for repo, row, owner in (
                (alpha, "~aa11", "seat-alpha"),
                (beta, "~bb22", "seat-beta"),
                (gamma, "~aa11", "seat-gamma"),
            ):
                claimed = run(
                    home, "throw", "--repo", str(repo), "--task", row, "--by", owner
                )
                self.assertEqual(claimed.returncode, 0, claimed.stderr)

            git(alpha, "remote", "set-url", "origin", "git@example.invalid:team/c.git")
            git(beta, "remote", "set-url", "origin", "git@example.invalid:team/c.git")
            git(gamma, "remote", "set-url", "origin", "git@example.invalid:team/a.git")
            before = board(home)["revision"]

            reconciled = run(home, "status", "--json", cwd=root, extra_env=scope)

            self.assertEqual(reconciled.returncode, 0, reconciled.stderr)
            payload = board(home)
            self.assertEqual(payload["revision"], before + 1)
            self.assertEqual(len(payload["entities"]), 2)
            owners = {claim["owner"]: claim["entity"] for claim in payload["claims"]}
            self.assertEqual(owners["seat-alpha"], owners["seat-beta"])
            self.assertNotEqual(owners["seat-alpha"], owners["seat-gamma"])
            self.assertEqual(
                {(claim["row"], claim["owner"]) for claim in payload["claims"]},
                {
                    ("~aa11", "seat-alpha"),
                    ("~bb22", "seat-beta"),
                    ("~aa11", "seat-gamma"),
                },
            )

    def test_linked_worktrees_without_a_remote_still_share_one_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            sibling = root / "no-remote-worktree"
            git(repo, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")

            first = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            second = run(
                home,
                "throw",
                "--repo",
                str(sibling),
                "--task",
                "~aa11",
                "--by",
                "seat-b",
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 1, second.stderr)
            self.assertIn("claimed by seat-a", second.stderr)
            payload = board(home)
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(len(payload["entities"]), 1)
            self.assertEqual(len(payload["claims"]), 1)


class RegisteredPointerIsCanonicalBeforePortfolioParsing(unittest.TestCase):
    REMOTE = "git@example.invalid:team/shadow.git"
    BANNER = (
        "**[verified 2026-07-29: HISTORICAL ROUTING CONFIRMED — this root plan "
        "remains a non-executable archive shell; do not revive or update this file.]**"
    )

    def _pair(self, root: Path) -> dict:
        home = root / "home"
        portfolio = root / "portfolio"
        blank = root / "blank"
        home.mkdir()
        portfolio.mkdir()
        blank.mkdir()
        healthy = project(root, name="installed-shadow", display_name="shadow")
        git(healthy, "remote", "add", "origin", self.REMOTE)
        registered = run(home, "status", "--root", str(healthy), "--json")
        self.assertEqual(registered.returncode, 0, registered.stderr)
        sibling = portfolio / "shadow"
        git(healthy, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")
        board_path = home / ".shadow" / "board.json"
        board_head = subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return {
            "home": home,
            "portfolio": portfolio,
            "blank": blank,
            "healthy": healthy,
            "sibling": sibling,
            "env": {"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            "board_path": board_path,
            "board_bytes": board_path.read_bytes(),
            "board_head": board_head,
            "revision": board(home)["revision"],
        }

    def _registered_alias_pair(self, root: Path) -> dict:
        home = root / "home"
        portfolio = root / "portfolio"
        blank = root / "blank"
        for path in (home, portfolio, blank):
            path.mkdir()
        aliases = [
            project(root, name="first-shadow", display_name="shadow"),
            project(root, name="second-shadow", display_name="shadow"),
        ]
        for index, alias in enumerate(aliases, start=1):
            git(
                alias,
                "remote",
                "add",
                "origin",
                f"git@example.invalid:team/shadow-alias-{index}.git",
            )
            registered = run(home, "status", "--root", str(alias), "--json")
            self.assertEqual(registered.returncode, 0, registered.stderr)
        self.assertEqual(len(board(home)["entities"]), 2)

        # Model migration debt without fabricating board bytes: two independently
        # registered checkouts later acquire the same durable Git identity.
        for alias in aliases:
            git(alias, "remote", "set-url", "origin", self.REMOTE)
        demoted = aliases[1] / "PLAN.md"
        demoted.write_text(
            demoted.read_text(encoding="utf-8").replace(
                "# Project\n", f"# Project\n\n{self.BANNER}\n", 1
            ),
            encoding="utf-8",
        )
        git(aliases[1], "add", "PLAN.md")
        git(aliases[1], "commit", "--quiet", "-m", "self demote one alias")
        board_path = home / ".shadow" / "board.json"
        board_head = subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return {
            "home": home,
            "portfolio": portfolio,
            "blank": blank,
            "aliases": aliases,
            "demoted": demoted,
            "env": {"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            "board_path": board_path,
            "board_bytes": board_path.read_bytes(),
            "board_head": board_head,
            "revision": board(home)["revision"],
        }

    def _assert_board_unchanged(self, fixture: dict) -> None:
        self.assertEqual(fixture["board_path"].read_bytes(), fixture["board_bytes"])
        head = subprocess.run(
            ["git", "-C", str(fixture["home"] / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(head, fixture["board_head"])

    def _importer_and_amp(self):
        import shadow_board_import as importer

        name = f"shadow_status_pointer_test_{id(self)}"
        spec = importlib.util.spec_from_file_location(
            name, ROOT / "scripts" / "shadow-status.py"
        )
        assert spec and spec.loader
        status = importlib.util.module_from_spec(spec)
        sys.modules[name] = status
        spec.loader.exec_module(status)
        return importer, status._amp

    def test_healthy_registered_pointer_suppresses_an_unreadable_same_identity_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            plan = fixture["sibling"] / "PLAN.md"
            plan.write_bytes(b"\xff\xfe")
            git(fixture["sibling"], "add", "PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "break stale sibling")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("portfolio refresh failed", result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["v4_plans"][0].get("broken", False))
            self.assertEqual(
                board(fixture["home"])["entities"][0]["plan"],
                str((fixture["healthy"] / "PLAN.md").resolve()),
            )
            self._assert_board_unchanged(fixture)

            hidden = run(
                fixture["home"],
                "status",
                "--shadowed",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )
            self.assertEqual(hidden.returncode, 0, hidden.stderr)
            receipt = json.loads(hidden.stdout)["rows"][0]
            self.assertEqual(set(receipt), {"path", "shadowed_by", "reason"})
            self.assertRegex(receipt["path"], r"^copy@[0-9a-f]{12}/PLAN\.md$")
            self.assertRegex(
                receipt["shadowed_by"], r"^entity@[0-9a-f]{12}/PLAN\.md$"
            )
            self.assertIn("registered", receipt["reason"])
            self.assertNotIn(str(Path(tmp)), json.dumps(receipt))

    def test_public_suppression_receipt_hashes_a_secret_shaped_checkout_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            secret_name = "ghp_" + ("A" * 24)
            poisoned = fixture["portfolio"] / secret_name
            git(
                fixture["healthy"],
                "worktree",
                "move",
                str(fixture["sibling"]),
                str(poisoned),
            )

            inspected = run(
                fixture["home"],
                "status",
                "--shadowed",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            row = json.loads(inspected.stdout)["rows"][0]
            self.assertEqual(set(row), {"path", "shadowed_by", "reason"})
            self.assertRegex(row["path"], r"^copy@[0-9a-f]{12}/PLAN\.md$")
            self.assertRegex(row["shadowed_by"], r"^entity@[0-9a-f]{12}/PLAN\.md$")
            self.assertNotIn(secret_name, json.dumps(row))
            self.assertNotIn(str(Path(tmp)), json.dumps(row))

    def test_same_identity_archive_veto_retires_the_registered_entity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            plan = fixture["sibling"] / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "# Project\n", f"# Project\n\n{self.BANNER}\n", 1
                ),
                encoding="utf-8",
            )
            git(fixture["sibling"], "add", "PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "demote sibling")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = board(fixture["home"])
            self.assertEqual(payload["entities"], [])
            self.assertEqual(payload["projects"], [])
            self.assertEqual(payload["claims"], [])
            self.assertEqual(payload["revision"], fixture["revision"] + 1)
            self.assertEqual(json.loads(result.stdout)["v4_plans"], [])

            hidden = run(
                fixture["home"],
                "status",
                "--shadowed",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )
            self.assertEqual(hidden.returncode, 0, hidden.stderr)
            self.assertIn(
                "non-executable archive shell",
                json.dumps(json.loads(hidden.stdout)["rows"]).lower(),
            )

    def test_a_strictly_newer_live_copy_supersedes_a_stale_checkouts_demotion(self) -> None:
        """A checkout parked in the past cannot retire a plan that moved on.

        The sibling above commits its banner LAST, so it is the identity's
        newest word and still retires it. Here the banner is the OLDER commit
        and the registered copy has since replaced it — the exact shape of a
        long-lived repository whose stale checkout keeps serving a superseded
        archive shell. The entity must survive repeated ordinary reconciles,
        because a demotion that lost the board once is a demotion that takes
        the project's live claims with it every time status runs.
        """

        def commit_at(repo: Path, message: str, when: str) -> None:
            stamped = {
                **os.environ,
                "GIT_AUTHOR_DATE": when,
                "GIT_COMMITTER_DATE": when,
            }
            result = subprocess.run(
                ["git", "-C", str(repo), "commit", "--quiet", "-m", message],
                capture_output=True,
                text=True,
                env=stamped,
                check=False,
            )
            if result.returncode:
                raise AssertionError(result.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()

            healthy = project(root, name="installed-shadow", display_name="shadow")
            git(healthy, "remote", "add", "origin", self.REMOTE)
            plan = healthy / "PLAN.md"
            live_text = plan.read_text(encoding="utf-8")

            # T0: the whole repository is a self-demoted archive shell.
            plan.write_text(
                live_text.replace("# Project\n", f"# Project\n\n{self.BANNER}\n", 1),
                encoding="utf-8",
            )
            git(healthy, "add", "PLAN.md")
            commit_at(healthy, "demote the plan", "2026-06-24T02:06:40+00:00")
            stale = portfolio / "shadow-stale"
            git(healthy, "worktree", "add", "--quiet", "--detach", str(stale), "HEAD")

            # T1: the repository revives the plan; the stale checkout does not
            # follow, so the banner survives only on a commit that lost.
            plan.write_text(live_text, encoding="utf-8")
            git(healthy, "add", "PLAN.md")
            commit_at(healthy, "revive the plan", "2026-08-10T18:15:14+00:00")

            registered = run(home, "status", "--root", str(healthy), "--json")
            self.assertEqual(registered.returncode, 0, registered.stderr)
            self.assertEqual(len(board(home)["entities"]), 1)

            env = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            for attempt in range(2):
                refreshed = run(home, "status", "--json", cwd=blank, extra_env=env)
                self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
                entities = board(home)["entities"]
                self.assertEqual(
                    [entity["project"] for entity in entities],
                    ["shadow"],
                    f"the live entity was dropped on reconcile {attempt + 1}",
                )
                self.assertEqual(
                    Path(entities[0]["plan"]).resolve(),
                    plan.resolve(),
                    "authority moved off the live copy",
                )

    def test_a_newer_live_copy_repairs_a_registered_stale_demotion(self) -> None:
        """The timestamp verdict is symmetric across the registered pointer.

        A registered checkout can itself be the copy parked on an older
        demotion while a same-origin worktree has committed the newer live
        plan. Discovery must compare both copies before retiring the identity,
        then move the registered pointer to the live copy under the same CAS.
        """

        def commit_at(repo: Path, message: str, when: str) -> None:
            stamped = {
                **os.environ,
                "GIT_AUTHOR_DATE": when,
                "GIT_COMMITTER_DATE": when,
            }
            result = subprocess.run(
                ["git", "-C", str(repo), "commit", "--quiet", "-m", message],
                capture_output=True,
                text=True,
                env=stamped,
                check=False,
            )
            if result.returncode:
                raise AssertionError(result.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()

            registered_repo = project(
                root, name="installed-shadow", display_name="shadow"
            )
            git(registered_repo, "remote", "add", "origin", self.REMOTE)
            registered_plan = registered_repo / "PLAN.md"
            live_text = registered_plan.read_text(encoding="utf-8")

            seeded = run(home, "status", "--root", str(registered_repo), "--json")
            self.assertEqual(seeded.returncode, 0, seeded.stderr)

            registered_plan.write_text(
                live_text.replace("# Project\n", f"# Project\n\n{self.BANNER}\n", 1),
                encoding="utf-8",
            )
            git(registered_repo, "add", "PLAN.md")
            commit_at(
                registered_repo,
                "demote the registered checkout",
                "2026-06-24T02:06:40+00:00",
            )

            live_repo = portfolio / "shadow"
            git(
                registered_repo,
                "worktree",
                "add",
                "--quiet",
                "--detach",
                str(live_repo),
                "HEAD",
            )
            live_plan = live_repo / "PLAN.md"
            live_plan.write_text(live_text, encoding="utf-8")
            git(live_repo, "add", "PLAN.md")
            commit_at(
                live_repo,
                "revive the plan in the current copy",
                "2026-08-10T18:15:14+00:00",
            )

            env = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            for attempt in range(2):
                refreshed = run(home, "status", "--json", cwd=blank, extra_env=env)
                self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
                entities = board(home)["entities"]
                self.assertEqual(
                    [entity["project"] for entity in entities],
                    ["shadow"],
                    f"the live entity was dropped on reconcile {attempt + 1}",
                )
                self.assertEqual(
                    Path(entities[0]["plan"]).resolve(),
                    live_plan.resolve(),
                    "the stale registered demotion remained canonical",
                )

    def test_every_copy_the_veto_read_is_a_retirement_predicate(self) -> None:
        """The verdict reads the whole identity, so the whole identity is CASed.

        This demotion retires the entity only because no strictly newer copy
        declined to repeat it. A token for the demoted copy alone would let the
        live copy it was compared against change — including into the newer
        word that supersedes the demotion — between discovery and the
        transaction, and retire a live project anyway.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            importer, amp = self._importer_and_amp()
            demoted = fixture["sibling"] / "PLAN.md"
            demoted.write_text(
                demoted.read_text(encoding="utf-8").replace(
                    "# Project\n", f"# Project\n\n{self.BANNER}\n", 1
                ),
                encoding="utf-8",
            )
            git(fixture["sibling"], "add", "PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "demote sibling")
            live = fixture["healthy"] / "PLAN.md"
            real_reconcile = importer.board.reconcile

            def revise_the_live_copy_then_reconcile(*args, **kwargs):
                live.write_text(
                    live.read_text(encoding="utf-8")
                    + "- 2026-08-11T00:00:00Z NOTE revised after discovery\n",
                    encoding="utf-8",
                )
                return real_reconcile(*args, **kwargs)

            importer.board.reconcile = revise_the_live_copy_then_reconcile
            try:
                with self.assertRaisesRegex(
                    importer.board.BoardError,
                    "changed during reconciliation",
                ):
                    importer.reconcile_portfolio(
                        fixture["portfolio"], amp, home=fixture["home"]
                    )
            finally:
                importer.board.reconcile = real_reconcile
            self._assert_board_unchanged(fixture)

    def test_every_copy_the_live_supersession_read_is_a_reconcile_predicate(self) -> None:
        """A live verdict CASes the stale demotion it proved superseded.

        Discovery initially sees an older demotion and a strictly newer live
        registered copy, so the entity stays live. If the demoted copy commits
        a newer word before reconciliation, the original verdict is stale and
        must not be allowed to refresh the board.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            importer, amp = self._importer_and_amp()

            def commit_at(repo: Path, message: str, when: str) -> None:
                stamped = {
                    **os.environ,
                    "GIT_AUTHOR_DATE": when,
                    "GIT_COMMITTER_DATE": when,
                }
                result = subprocess.run(
                    ["git", "-C", str(repo), "commit", "--quiet", "-m", message],
                    capture_output=True,
                    text=True,
                    env=stamped,
                    check=False,
                )
                if result.returncode:
                    raise AssertionError(result.stderr)

            demoted = fixture["sibling"] / "PLAN.md"
            demoted.write_text(
                demoted.read_text(encoding="utf-8").replace(
                    "# Project\n", f"# Project\n\n{self.BANNER}\n", 1
                ),
                encoding="utf-8",
            )
            git(fixture["sibling"], "add", "PLAN.md")
            commit_at(
                fixture["sibling"],
                "demote stale sibling",
                "2026-06-24T02:06:40+00:00",
            )

            live = fixture["healthy"] / "PLAN.md"
            live.write_text(
                live.read_text(encoding="utf-8")
                + "- 2026-08-10T18:15:14Z NOTE current copy remains live\n",
                encoding="utf-8",
            )
            git(fixture["healthy"], "add", "PLAN.md")
            commit_at(
                fixture["healthy"],
                "advance the live registered copy",
                "2026-08-10T18:15:14+00:00",
            )

            real_reconcile = importer.board.reconcile

            def revise_the_demoted_copy_then_reconcile(*args, **kwargs):
                demoted.write_text(
                    demoted.read_text(encoding="utf-8")
                    + "- 2026-08-11T00:00:00Z NOTE demotion revised after discovery\n",
                    encoding="utf-8",
                )
                git(fixture["sibling"], "add", "PLAN.md")
                commit_at(
                    fixture["sibling"],
                    "advance demotion after discovery",
                    "2026-08-11T00:00:00+00:00",
                )
                return real_reconcile(*args, **kwargs)

            importer.board.reconcile = revise_the_demoted_copy_then_reconcile
            try:
                with self.assertRaisesRegex(
                    importer.board.BoardError,
                    "changed during reconciliation",
                ):
                    importer.reconcile_portfolio(
                        fixture["portfolio"], amp, home=fixture["home"]
                    )
            finally:
                importer.board.reconcile = real_reconcile
            self._assert_board_unchanged(fixture)

    def test_duplicate_checkouts_do_not_multiply_the_vetos_git_scans(self) -> None:
        """N copies of one plan cost N commit reads, not N**2.

        The verdict is sought before deduplication, so every same-identity
        checkout asks for it and each ask dates the whole set. Uncached, a
        machine holding a dozen old clones pays that square on every ordinary
        `shadow status`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio = root / "portfolio"
            portfolio.mkdir()
            healthy = project(root, name="installed-shadow", display_name="shadow")
            git(healthy, "remote", "add", "origin", self.REMOTE)
            copies = []
            for index in range(4):
                copy = portfolio / f"shadow-{index}"
                git(healthy, "worktree", "add", "--quiet", "--detach", str(copy), "HEAD")
                copies.append(copy)

            from browser import server

            plan = healthy / "PLAN.md"
            identity = server._root_board.entity_id(plan)
            dated: list[str] = []
            real_commit_time = server._root_board.plan_commit_time

            def counted(candidate: Path):
                dated.append(str(candidate))
                return real_commit_time(candidate)

            server._root_board.plan_commit_time = counted
            try:
                records = server.discover_plans(
                    portfolio, registered_plans={identity: plan}
                )
            finally:
                server._root_board.plan_commit_time = real_commit_time

            self.assertEqual(len(records), 1)
            self.assertLessEqual(len(dated), len(copies) + 1)

    def test_a_cached_commit_date_is_not_reused_after_the_plan_changes(self) -> None:
        """The memo answers for the state it measured, not for the path.

        Election dates every candidate up front; the veto freezes plan CONTENT
        later in the same pass. A copy committed live in between would be judged
        as new content against the old date, look older than it is, and be
        retired by a demotion it has since dropped. The content CAS cannot catch
        that, because the state it validates is the new one.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp), name="widget", display_name="widget")
            plan = repo / "PLAN.md"

            from browser import server

            memo: dict[str, tuple[str, int | None]] = {}
            scans: list[str] = []
            real_commit_time = server._root_board.plan_commit_time

            def counted(candidate: Path):
                scans.append(str(candidate))
                return real_commit_time(candidate)

            server._root_board.plan_commit_time = counted
            try:
                first = server._dated(plan, memo)
                self.assertEqual(server._dated(plan, memo), first)
                self.assertEqual(len(scans), 1, "an unchanged plan stays one scan")

                plan.write_text(
                    plan.read_text(encoding="utf-8") + "\n<!-- moved on -->\n",
                    encoding="utf-8",
                )
                git(repo, "add", "PLAN.md")
                when = "2026-08-10T00:00:00+00:00"
                subprocess.run(
                    ["git", "-C", str(repo), "commit", "--quiet", "-m", "moved on"],
                    env={**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
                    capture_output=True,
                    check=True,
                )
                moved = server._dated(plan, memo)
            finally:
                server._root_board.plan_commit_time = real_commit_time

            self.assertEqual(len(scans), 2, "a changed plan is dated again")
            self.assertEqual(moved, real_commit_time(plan))
            self.assertNotEqual(moved, first)

    def test_registered_current_plan_can_explicitly_supersede_one_ancestor_archive(self) -> None:
        """A named, committed, ancestral archive is the one demotion an operator may retire.

        Dates are pinned so the archive banner is the identity's NEWEST commit:
        the commit-time rule therefore refuses to supersede it, and only the
        explicit handoff can. Ancestry, not a clock, is what proves the current
        plan came after — dates tie, skew, and survive rebases unchanged.
        """

        def commit_at(repo: Path, message: str, when: str) -> None:
            result = subprocess.run(
                ["git", "-C", str(repo), "commit", "--quiet", "-m", message],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "GIT_AUTHOR_DATE": when,
                    "GIT_COMMITTER_DATE": when,
                },
                check=False,
            )
            if result.returncode:
                raise AssertionError(result.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            archived_plan = fixture["sibling"] / "PLAN.md"
            archived_plan.write_text(
                archived_plan.read_text(encoding="utf-8").replace(
                    "# Project\n", f"# Project\n\n{self.BANNER}\n", 1
                ),
                encoding="utf-8",
            )
            git(fixture["sibling"], "add", "PLAN.md")
            commit_at(
                fixture["sibling"],
                "archive old authority",
                "2026-08-10T18:15:14+00:00",
            )
            archived_head = subprocess.run(
                ["git", "-C", str(fixture["sibling"]), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            # The new authority is deliberately a descendant of the archived
            # commit, then replaces the archive banner with the exact handoff.
            git(fixture["healthy"], "merge", "--ff-only", archived_head)
            current_plan = fixture["healthy"] / "PLAN.md"
            current_plan.write_text(
                current_plan.read_text(encoding="utf-8")
                .replace(f"\n{self.BANNER}\n", "\n", 1)
                .replace(
                    "- Priority: 2\n",
                    f"- Priority: 2\n- Supersedes archive commit: {archived_head}\n",
                    1,
                ),
                encoding="utf-8",
            )
            git(fixture["healthy"], "add", "PLAN.md")
            commit_at(
                fixture["healthy"],
                "supersede archived authority",
                "2026-06-24T02:06:40+00:00",
            )

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = board(fixture["home"])
            self.assertEqual(len(payload["entities"]), 1)
            self.assertEqual(
                payload["entities"][0]["plan"],
                str(current_plan.resolve()),
            )
            self.assertEqual(len(json.loads(result.stdout)["v4_plans"]), 1)

            hidden = run(
                fixture["home"],
                "status",
                "--shadowed",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )
            self.assertEqual(hidden.returncode, 0, hidden.stderr)
            self.assertIn(
                "historical archive explicitly superseded",
                json.dumps(json.loads(hidden.stdout)["rows"]),
            )

    def test_one_self_demoted_registered_alias_retires_the_whole_logical_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._registered_alias_pair(Path(tmp))

            retired = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(retired.returncode, 0, retired.stderr)
            payload = board(fixture["home"])
            self.assertEqual(payload["revision"], fixture["revision"] + 1)
            self.assertEqual(payload["entities"], [])
            self.assertEqual(payload["projects"], [])
            self.assertEqual(payload["claims"], [])
            self.assertEqual(json.loads(retired.stdout)["v4_plans"], [])
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(fixture["home"] / ".shadow"),
                        "show",
                        "HEAD:board.json",
                    ],
                    capture_output=True,
                    check=True,
                ).stdout,
                fixture["board_path"].read_bytes(),
            )
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(fixture["home"] / ".shadow"),
                        "status",
                        "--porcelain",
                        "--",
                        "board.json",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )

    def test_registered_alias_retirement_source_is_byte_cas_protected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._registered_alias_pair(Path(tmp))
            importer, amp = self._importer_and_amp()
            demoted = fixture["demoted"]
            exact_source = demoted.read_bytes()
            real_reconcile = importer.board.reconcile

            def mutate_then_reconcile(*args, **kwargs):
                demoted.write_bytes(exact_source.replace(b"archive shell", b"active shell"))
                return real_reconcile(*args, **kwargs)

            importer.board.reconcile = mutate_then_reconcile
            try:
                with self.assertRaisesRegex(
                    importer.board.BoardError,
                    "self-demotion source changed during reconciliation",
                ):
                    importer.reconcile_portfolio(
                        fixture["portfolio"], amp, home=fixture["home"]
                    )
            finally:
                importer.board.reconcile = real_reconcile
                demoted.write_bytes(exact_source)
            self._assert_board_unchanged(fixture)

    def test_healthy_registered_pointer_suppresses_a_symlink_same_identity_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            plan = fixture["sibling"] / "PLAN.md"
            plan.unlink()
            plan.symlink_to(fixture["healthy"] / "PLAN.md")
            git(fixture["sibling"], "add", "PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "link stale sibling")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)["v4_plans"][0].get("broken", False))
            self._assert_board_unchanged(fixture)

    def test_registered_root_owns_declared_nested_plan_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            root_plan = fixture["sibling"] / "PLAN.md"
            text = root_plan.read_text(encoding="utf-8")
            root_plan.write_text(
                text.replace("- Mode: ship\n", "- Mode: ship\n- Plans: plans/*/PLAN.md\n"),
                encoding="utf-8",
            )
            rogue = fixture["sibling"] / "plans" / "rogue"
            rogue.mkdir(parents=True)
            (rogue / "PLAN.md").write_text(
                text.replace("- Project: shadow", "- Project: rogue"),
                encoding="utf-8",
            )
            git(fixture["sibling"], "add", "PLAN.md", "plans/rogue/PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "widen stale scope")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [entity["project"] for entity in board(fixture["home"])["entities"]],
                ["shadow"],
            )
            self._assert_board_unchanged(fixture)

    def test_an_unknown_unreadable_candidate_still_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            unknown = project(fixture["portfolio"], name="unknown")
            git(unknown, "remote", "add", "origin", "git@example.invalid:team/unknown.git")
            (unknown / "PLAN.md").write_bytes(b"\xff\xfe")
            git(unknown, "add", "PLAN.md")
            git(unknown, "commit", "--quiet", "-m", "break unknown")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("portfolio import refused", result.stderr)
            self.assertIn("unknown/PLAN.md", result.stderr)
            self._assert_board_unchanged(fixture)

    def test_an_unknown_secret_named_candidate_fails_closed_without_leaking_its_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            # Build a clearly synthetic token shape at runtime: this test is
            # proving the scrubber, not storing a credential in its fixture.
            poisoned_name = bytes.fromhex("67 68 70 5f").decode("ascii") + ("A" * 24)
            unknown = project(fixture["portfolio"], name=poisoned_name)
            git(unknown, "remote", "add", "origin", "git@example.invalid:team/unknown.git")
            (unknown / "PLAN.md").write_bytes(b"\xff\xfe")
            git(unknown, "add", "PLAN.md")
            git(unknown, "commit", "--quiet", "-m", "break secret-named copy")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            public = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1)
            self.assertIn("portfolio import refused", result.stderr)
            self.assertRegex(result.stderr, r"copy@[0-9a-f]{12}/PLAN\.md")
            self.assertNotIn(poisoned_name, public)
            self.assertNotIn(str(Path(tmp)), public)
            self._assert_board_unchanged(fixture)

    def test_a_broken_registered_pointer_cannot_suppress_an_unreadable_same_identity_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            plan = fixture["sibling"] / "PLAN.md"
            plan.write_bytes(b"\xff\xfe")
            git(fixture["sibling"], "add", "PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "break candidate")
            (fixture["healthy"] / "PLAN.md").unlink()

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("shadow/PLAN.md", result.stderr)
            self.assertTrue(json.loads(result.stdout)["v4_plans"][0]["broken"])
            self._assert_board_unchanged(fixture)

    def test_an_unhealthy_registered_pointer_repairs_without_moving_its_reachable_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            sibling_plan = fixture["sibling"] / "PLAN.md"
            text = sibling_plan.read_text(encoding="utf-8")
            rows = [line for line in text.splitlines() if line.startswith("- [pending]")]
            reordered = text.replace(
                "\n".join(rows),
                "\n".join([rows[1].replace(" | needs: ~aa11", ""), rows[0]]),
            )
            sibling_plan.write_text(reordered, encoding="utf-8")
            git(fixture["sibling"], "add", "PLAN.md")
            git(fixture["sibling"], "commit", "--quiet", "-m", "reorder valid sibling")
            (fixture["healthy"] / "PLAN.md").write_bytes(b"\xff\xfe")

            result = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = board(fixture["home"])
            self.assertEqual(payload["revision"], fixture["revision"] + 1)
            self.assertEqual(payload["entities"][0]["plan"], str(sibling_plan.resolve()))
            self.assertEqual(payload["entities"][0]["resume"], "~aa11")
            self.assertFalse(json.loads(result.stdout)["v4_plans"][0].get("broken", False))
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(fixture["home"] / ".shadow"), "show", "HEAD:board.json"],
                    capture_output=True,
                    check=True,
                ).stdout,
                fixture["board_path"].read_bytes(),
            )

    def test_broken_canonical_named_registered_checkout_repairs_from_valid_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()
            registered = project(portfolio, name="shadow", display_name="shadow")
            git(registered, "remote", "add", "origin", self.REMOTE)
            seeded = run(home, "status", "--root", str(registered), "--json")
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            before = board(home)
            sibling = portfolio / "shadow-worktree"
            git(registered, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")
            (registered / "PLAN.md").write_bytes(b"\xff\xfe")
            git(registered, "add", "PLAN.md")
            git(registered, "commit", "--quiet", "-m", "break canonical checkout")

            repaired = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertEqual(repaired.returncode, 0, repaired.stderr)
            payload = board(home)
            self.assertEqual(payload["revision"], before["revision"] + 1)
            self.assertEqual(payload["entities"][0]["plan"], str((sibling / "PLAN.md").resolve()))
            self.assertFalse(json.loads(repaired.stdout)["v4_plans"][0].get("broken", False))
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "show", "HEAD:board.json"],
                    capture_output=True,
                    check=True,
                ).stdout,
                (home / ".shadow" / "board.json").read_bytes(),
            )

    def test_a_lone_broken_registered_checkout_still_fails_closed(self) -> None:
        # The repair bypass exists only because a same-identity copy can carry
        # the plan instead. With no alternative, skipping the broken checkout
        # would silently drop a registered entity, so it stays a hard refusal.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()
            registered = project(portfolio, name="shadow", display_name="shadow")
            git(registered, "remote", "add", "origin", self.REMOTE)
            seeded = run(home, "status", "--root", str(registered), "--json")
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            before = board(home)
            (registered / "PLAN.md").write_bytes(b"\xff\xfe")
            git(registered, "add", "PLAN.md")
            git(registered, "commit", "--quiet", "-m", "break the only checkout")

            refused = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertEqual(refused.returncode, 1)
            self.assertIn("shadow/PLAN.md", refused.stderr)
            self.assertEqual(board(home), before)

    def test_unsafe_registered_plan_declaration_repairs_to_a_valid_same_identity_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            registered_plan = fixture["healthy"] / "PLAN.md"
            registered_plan.write_text(
                registered_plan.read_text(encoding="utf-8").replace(
                    "- Mode: ship\n",
                    "- Mode: ship\n- Plans: /absolute/PLAN.md\n",
                    1,
                ),
                encoding="utf-8",
            )
            git(fixture["healthy"], "add", "PLAN.md")
            git(fixture["healthy"], "commit", "--quiet", "-m", "unsafe plan declaration")

            repaired = run(
                fixture["home"],
                "status",
                "--json",
                cwd=fixture["blank"],
                extra_env=fixture["env"],
            )

            self.assertEqual(repaired.returncode, 0, repaired.stderr)
            payload = board(fixture["home"])
            self.assertEqual(payload["revision"], fixture["revision"] + 1)
            self.assertEqual(
                payload["entities"][0]["plan"],
                str((fixture["sibling"] / "PLAN.md").resolve()),
            )
            self.assertNotIn("/absolute/PLAN.md", repaired.stdout)
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(fixture["home"] / ".shadow"),
                        "show",
                        "HEAD:board.json",
                    ],
                    capture_output=True,
                    check=True,
                ).stdout,
                fixture["board_path"].read_bytes(),
            )

    def test_unreadable_registered_pointer_repairs_to_a_valid_same_identity_sibling(self) -> None:
        if sys.platform != "darwin":
            self.skipTest("chmod unreadability is asserted on macOS")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            registered_plan = fixture["healthy"] / "PLAN.md"
            original_mode = registered_plan.stat().st_mode & 0o7777
            try:
                os.chmod(registered_plan, 0)
                if os.access(registered_plan, os.R_OK):
                    self.skipTest("this account can read chmod-000 files")
                repaired = run(
                    fixture["home"],
                    "status",
                    "--json",
                    cwd=fixture["blank"],
                    extra_env=fixture["env"],
                )
            finally:
                os.chmod(registered_plan, original_mode)

            self.assertEqual(repaired.returncode, 0, repaired.stderr)
            payload = board(fixture["home"])
            self.assertEqual(payload["revision"], fixture["revision"] + 1)
            self.assertEqual(
                payload["entities"][0]["plan"],
                str((fixture["sibling"] / "PLAN.md").resolve()),
            )
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(fixture["home"] / ".shadow"),
                        "show",
                        "HEAD:board.json",
                    ],
                    capture_output=True,
                    check=True,
                ).stdout,
                fixture["board_path"].read_bytes(),
            )

    def test_one_oversized_registered_pointer_is_broken_in_status_and_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            empty = root / "empty"
            blank = root / "blank"
            for path in (home, empty, blank):
                path.mkdir()
            repo = project(root, name="installed-shadow", display_name="shadow")
            git(repo, "remote", "add", "origin", self.REMOTE)
            seeded = run(home, "status", "--root", str(repo), "--json")
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            with (repo / "PLAN.md").open("a", encoding="utf-8") as stream:
                stream.write("\n<!-- " + ("x" * 1_000_000) + " -->\n")
            scope = {"SHADOW_PORTFOLIO_ROOT": str(empty)}

            terminal = run(home, "status", "--json", cwd=blank, extra_env=scope)
            from browser.server import board_plan_records

            browser_payload, records, warning = board_plan_records(empty, home)

            self.assertEqual(terminal.returncode, 1, terminal.stderr)
            terminal_payload = json.loads(terminal.stdout)
            self.assertTrue(terminal_payload["v4_plans"][0]["broken"])
            self.assertEqual(browser_payload["revision"], terminal_payload["root_board"]["revision"])
            self.assertTrue(records[0]["broken"])
            self.assertIn("broken", warning or "")

    def test_registered_self_demotion_is_private_inspectable_and_retires_without_a_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()
            repo = project(root, name="installed-shadow", display_name="shadow")
            git(repo, "remote", "add", "origin", self.REMOTE)
            seeded = run(home, "status", "--root", str(repo), "--json")
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            before = board(home)
            private = "/" + "Users/owner/private/worktree"
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "# Project\n",
                    "# Project\n\n"
                    f"This root plan at {private} remains a non-executable archive shell; "
                    "do not revive.\n",
                    1,
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "self demote")

            inspected = run(home, "status", "--root", str(repo), "--shadowed", "--json")
            rows = json.loads(inspected.stdout)["rows"]
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), {"path", "shadowed_by", "reason"})
            self.assertRegex(rows[0]["path"], r"^copy@[0-9a-f]{12}/PLAN\.md$")
            self.assertIsNone(rows[0]["shadowed_by"])
            self.assertIn("non-executable archive shell", rows[0]["reason"])
            self.assertNotIn(private, json.dumps(rows))

            retired = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )
            self.assertEqual(retired.returncode, 0, retired.stderr)
            payload = board(home)
            self.assertEqual(payload["revision"], before["revision"] + 1)
            self.assertEqual(payload["entities"], [])
            self.assertEqual(payload["projects"], [])

    def test_live_seed_edit_between_parse_and_reconcile_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._pair(Path(tmp))
            importer, amp = self._importer_and_amp()
            plan = fixture["healthy"] / "PLAN.md"
            original = plan.read_text(encoding="utf-8")
            plan.write_text(original.replace("~aa11", "~cc33"), encoding="utf-8")
            git(fixture["healthy"], "add", "PLAN.md")
            git(fixture["healthy"], "commit", "--quiet", "-m", "parsed snapshot")
            real_reconcile = importer.board.reconcile

            def mutate_then_reconcile(*args, **kwargs):
                plan.write_text(original.replace("~aa11", "~dd44"), encoding="utf-8")
                return real_reconcile(*args, **kwargs)

            importer.board.reconcile = mutate_then_reconcile
            try:
                with self.assertRaisesRegex(
                    importer.board.BoardError, "changed during reconciliation"
                ):
                    importer.reconcile_portfolio(
                        fixture["portfolio"], amp, home=fixture["home"]
                    )
            finally:
                importer.board.reconcile = real_reconcile
            self._assert_board_unchanged(fixture)

    def test_first_import_live_seed_edit_leaves_no_board_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            repo = project(portfolio, name="shadow", display_name="shadow")
            importer, amp = self._importer_and_amp()
            plan = repo / "PLAN.md"
            parsed_source = plan.read_text(encoding="utf-8")
            real_reconcile = importer.board.reconcile

            def mutate_then_reconcile(*args, **kwargs):
                plan.write_text(
                    parsed_source.replace("~aa11", "~cc33"), encoding="utf-8"
                )
                return real_reconcile(*args, **kwargs)

            importer.board.reconcile = mutate_then_reconcile
            try:
                with self.assertRaisesRegex(
                    importer.board.BoardError, "changed during reconciliation"
                ):
                    importer.reconcile_portfolio(portfolio, amp, home=home)
            finally:
                importer.board.reconcile = real_reconcile
            self.assertFalse((home / ".shadow").exists())

    def test_retirement_and_repair_predicates_refuse_lost_updates(self) -> None:
        for transition in ("retirement", "repair"):
            with self.subTest(transition=transition), tempfile.TemporaryDirectory() as tmp:
                fixture = self._pair(Path(tmp))
                importer, amp = self._importer_and_amp()
                plan = fixture["healthy"] / "PLAN.md"
                original = plan.read_text(encoding="utf-8")
                if transition == "retirement":
                    plan.write_text(
                        original.replace("# Project\n", f"# Project\n\n{self.BANNER}\n", 1),
                        encoding="utf-8",
                    )
                else:
                    plan.write_bytes(b"\xff\xfe")
                real_reconcile = importer.board.reconcile

                def heal_then_reconcile(*args, **kwargs):
                    plan.write_text(original, encoding="utf-8")
                    return real_reconcile(*args, **kwargs)

                importer.board.reconcile = heal_then_reconcile
                try:
                    with self.assertRaisesRegex(
                        importer.board.BoardError,
                        "changed during reconciliation",
                    ):
                        importer.reconcile_portfolio(
                            fixture["portfolio"], amp, home=fixture["home"]
                        )
                finally:
                    importer.board.reconcile = real_reconcile
                self._assert_board_unchanged(fixture)

    def test_crlf_plan_snapshot_and_default_discovery_never_leak_internal_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root, display_name="project")
            plan = repo / "PLAN.md"
            plan.write_bytes(plan.read_bytes().replace(b"\n", b"\r\n"))
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "crlf authority")

            imported = run(home, "status", "--root", str(repo), "--json")
            from browser.server import discover_plans

            raw = discover_plans(repo)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertFalse(any(key.startswith("_") for key in raw[0]))
            self.assertNotIn(str(root), json.dumps(raw))


class RootBoardImportScale(unittest.TestCase):
    def _importer_and_amp(self):
        import shadow_board_import as importer

        name = f"shadow_status_import_scale_test_{id(self)}"
        spec = importlib.util.spec_from_file_location(
            name, ROOT / "scripts" / "shadow-status.py"
        )
        assert spec and spec.loader
        status = importlib.util.module_from_spec(spec)
        sys.modules[name] = status
        spec.loader.exec_module(status)
        return importer, status._amp

    def test_250_entity_noop_refresh_bounds_identity_git_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root, name="mega", display_name="mega")
            git(repo, "remote", "add", "origin", "git@example.invalid:team/mega.git")
            root_plan = repo / "PLAN.md"
            child_text = root_plan.read_text(encoding="utf-8")
            root_plan.write_text(
                child_text.replace(
                    "- Mode: ship\n",
                    "- Mode: ship\n- Plans: entities/*/PLAN.md\n",
                    1,
                ),
                encoding="utf-8",
            )
            for index in range(249):
                child = repo / "entities" / f"e{index:04d}"
                child.mkdir(parents=True)
                (child / "PLAN.md").write_text(child_text, encoding="utf-8")
            git(repo, "add", "PLAN.md", "entities")
            git(repo, "commit", "--quiet", "-m", "seed 250 entity plans")
            importer, amp = self._importer_and_amp()
            importer.reconcile_portfolio(repo, amp, home=home)
            board_path = home / ".shadow" / "board.json"
            before_bytes = board_path.read_bytes()
            before_head = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            commands: list[tuple[str, ...]] = []
            real_run = subprocess.run

            def count_git(command, *args, **kwargs):
                if command and command[0] == "git":
                    commands.append(tuple(str(part) for part in command))
                return real_run(command, *args, **kwargs)

            with mock.patch.object(subprocess, "run", side_effect=count_git):
                refreshed = importer.reconcile_portfolio(repo, amp, home=home)

            after_head = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertEqual(len(refreshed["entities"]), 250)
            self.assertEqual(board_path.read_bytes(), before_bytes)
            self.assertEqual(after_head, before_head)
            repo_root = repo.resolve()

            def inside_fixture(command: tuple[str, ...]) -> bool:
                if len(command) < 3 or command[:2] != ("git", "-C"):
                    return False
                try:
                    Path(command[2]).resolve().relative_to(repo_root)
                except ValueError:
                    return False
                return True

            url_probe_count = sum(
                inside_fixture(command)
                and len(command) >= 3
                and command[-3:-1] == ("config", "--get-all")
                and re.fullmatch(r"remote\..+\.url", command[-1]) is not None
                for command in commands
            )
            top_level_count = sum(
                inside_fixture(command)
                and command[-2:] == ("rev-parse", "--show-toplevel")
                for command in commands
            )
            # Endpoint resolution binds one tracked remote per identity
            # computation; the bound stays constant, never per-entity.
            self.assertLessEqual(url_probe_count, 3)
            self.assertLessEqual(top_level_count, (2 * 250) + 8)

    def test_repository_identity_change_before_final_cas_refuses_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root, name="identity", display_name="identity")
            git(
                repo,
                "remote",
                "add",
                "origin",
                "git@example.invalid:team/identity.git",
            )
            importer, amp = self._importer_and_amp()
            importer.reconcile_portfolio(repo, amp, home=home)
            board_path = home / ".shadow" / "board.json"
            before_bytes = board_path.read_bytes()
            before_head = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            real_choose_resume = importer.board._choose_resume

            def mutate_origin_then_choose(*args, **kwargs):
                git(
                    repo,
                    "remote",
                    "set-url",
                    "origin",
                    "git@example.invalid:team/changed.git",
                )
                return real_choose_resume(*args, **kwargs)

            with mock.patch.object(
                importer.board,
                "_choose_resume",
                side_effect=mutate_origin_then_choose,
            ):
                with self.assertRaisesRegex(
                    importer.board.BoardError,
                    "identity changed during reconciliation",
                ):
                    importer.reconcile_portfolio(repo, amp, home=home)

            after_head = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertEqual(board_path.read_bytes(), before_bytes)
            self.assertEqual(after_head, before_head)


class PortfolioReconciliationIsBoundedAndComplete(unittest.TestCase):
    def test_first_claim_does_not_hide_another_portfolio_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            home.mkdir()
            portfolio.mkdir()
            blank.mkdir()
            alpha = project(portfolio, name="alpha", display_name="alpha")
            beta = project(portfolio, name="beta", display_name="beta")
            container = portfolio / "not-a-project"
            container.mkdir()
            project(container, name="nested", display_name="nested")

            claimed = run(
                home, "throw", "--repo", str(alpha), "--task", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            self.assertEqual(len(board(home)["entities"]), 1)

            observed = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            report = json.loads(observed.stdout)
            self.assertEqual(
                {item["project"] for item in report["root_board"]["projects"]},
                {"alpha", "beta"},
            )
            self.assertEqual(
                {Path(item["plan"]).parent.name for item in board(home)["entities"]},
                {alpha.name, beta.name},
            )


class ImportExcludesGhostCopiesByConstruction(unittest.TestCase):
    def test_bounded_discovery_deduplicates_worktrees_and_ignores_nested_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            # A worktree carries the SAME commits as the checkout it came from,
            # so both copies are seeded at one pinned date. Election ranks
            # commit recency ABOVE the origin-name match, so leaving the dates
            # to wall-clock time hands the identity to whichever copy happened
            # to be committed in the later second -- measured: the stale
            # duplicate wins whenever the two seed commits straddle a second
            # boundary, which reddened one CI interpreter and not its siblings.
            # Pinned equal, recency ties and the name match this test is about
            # decides.
            seeded = "2026-08-10T00:00:00+00:00"
            canonical = project(
                portfolio, name="shared", display_name="shared", commit_date=seeded
            )
            duplicate = project(
                portfolio,
                name="shared-worktree",
                display_name="stale-shared",
                commit_date=seeded,
            )
            remote = "git@example.invalid:team/shared.git"
            git(canonical, "remote", "add", "origin", remote)
            git(duplicate, "remote", "add", "origin", remote)
            snapshots = portfolio / "dated-snapshots"
            snapshots.mkdir()
            project(snapshots, name="snapshot", display_name="ghost")

            observed = run(
                home,
                "status",
                "--json",
                cwd=root,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            payload = board(home)
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(len(payload["entities"]), 1)
            self.assertEqual(
                payload["entities"][0]["plan"], str((canonical / "PLAN.md").resolve())
            )
            self.assertNotIn("ghost", observed.stdout)
            self.assertNotIn("stale-shared", observed.stdout)


class HotPlanBudgetsGateNormalBoardEntry(unittest.TestCase):
    def _board_snapshot(self, home: Path) -> tuple[bytes, str]:
        board_path = home / ".shadow" / "board.json"
        head = subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return board_path.read_bytes(), head

    def _assert_board_snapshot(
        self,
        home: Path,
        expected: tuple[bytes, str],
    ) -> None:
        board_bytes, head = expected
        self.assertEqual((home / ".shadow" / "board.json").read_bytes(), board_bytes)
        current = subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(current, head)

    def test_normal_portfolio_import_refuses_an_over_budget_hot_plan_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()
            anchor = project(portfolio, name="anchor", display_name="anchor")
            seeded = run(home, "status", "--root", str(anchor), "--json", cwd=blank)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            oversized = project(portfolio, name="oversized", display_name="oversized")
            make_plan_over_budget(oversized)
            before = self._board_snapshot(home)

            imported = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertEqual(imported.returncode, 1, imported.stdout + imported.stderr)
            self.assertRegex(imported.stderr.lower(), r"budget|hot plan|limit")
            self._assert_board_snapshot(home, before)

    def test_normal_claim_refuses_an_over_budget_hot_plan_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            anchor = project(root, name="anchor", display_name="anchor")
            seeded = run(home, "status", "--root", str(anchor), "--json", cwd=anchor)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            oversized = project(root, name="oversized", display_name="oversized")
            make_plan_over_budget(oversized)
            before = self._board_snapshot(home)

            claimed = run(
                home,
                "throw",
                "--repo",
                str(oversized),
                "--task",
                "~aa11",
                "--by",
                "budget-seat",
                cwd=anchor,
            )

            self.assertEqual(claimed.returncode, 1, claimed.stdout + claimed.stderr)
            self.assertRegex(claimed.stderr.lower(), r"budget|hot plan|limit")
            self._assert_board_snapshot(home, before)


class HistoricalClaimsAreConsumedOnce(unittest.TestCase):
    def test_old_progress_claim_is_imported_once_and_cannot_be_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            repo = project(portfolio, name="legacy", display_name="legacy")
            plan_path = repo / "PLAN.md"
            text = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                text.replace("- [pending] TASK-BODY", "- [in_progress] TASK-BODY")
                + "- 2026-08-10T01:00:00Z THROWN ~aa11 legacy work | by: old-seat\n",
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "seed historical claim")
            environment = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}

            imported = run(
                home, "status", "--json", cwd=root, extra_env=environment
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            first = board(home)
            self.assertEqual(len(first["claims"]), 1)
            self.assertEqual(first["claims"][0]["owner"], "old-seat")

            repeated = run(
                home, "status", "--json", cwd=root, extra_env=environment
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(board(home)["revision"], first["revision"])
            refused = run(
                home,
                "throw",
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
                "new-seat",
                extra_env=environment,
            )
            self.assertEqual(refused.returncode, 1, refused.stderr)
            self.assertIn("claimed by old-seat", refused.stderr)

    def test_a_project_added_after_initial_import_keeps_its_historical_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            project(portfolio, name="first", display_name="first")
            environment = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}

            initial = run(home, "status", "--json", cwd=root, extra_env=environment)
            self.assertEqual(initial.returncode, 0, initial.stderr)

            late = project(portfolio, name="late", display_name="late")
            late_plan = late / "PLAN.md"
            late_plan.write_text(
                late_plan.read_text(encoding="utf-8").replace(
                    "- [pending] TASK-BODY", "- [in_progress] TASK-BODY"
                )
                + "- 2026-08-10T01:00:00Z THROWN ~aa11 late work | by: old-seat\n",
                encoding="utf-8",
            )
            git(late, "add", "PLAN.md")
            git(late, "commit", "--quiet", "-m", "record work already in flight")

            imported = run(home, "status", "--json", cwd=root, extra_env=environment)

            self.assertEqual(imported.returncode, 0, imported.stderr)
            payload = board(home)
            late_id = next(
                item["id"] for item in payload["entities"]
                if Path(item["plan"]).parent.name == "late"
            )
            late_claims = [
                claim for claim in payload["claims"] if claim["entity"] == late_id
            ]
            self.assertEqual(len(late_claims), 1)
            self.assertEqual(late_claims[0]["owner"], "old-seat")
            refused = run(
                home,
                "throw",
                "--repo",
                str(late),
                "--task",
                "~aa11",
                "--by",
                "new-seat",
                extra_env=environment,
            )
            self.assertEqual(refused.returncode, 1, refused.stderr)
            self.assertIn("claimed by old-seat", refused.stderr)


class CanonicalPointersRejectBranchOnlyRows(unittest.TestCase):
    def test_claim_cannot_name_a_row_absent_from_the_stored_plan_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            canonical = project(portfolio, name="canonical", display_name="canonical")
            git(canonical, "remote", "add", "origin", "git@example.invalid:team/canonical.git")
            environment = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            registered = run(home, "status", "--json", cwd=root, extra_env=environment)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            self.assertEqual(
                board(home)["entities"][0]["plan"],
                str((canonical / "PLAN.md").resolve()),
            )

            branch = root / "branch-worktree"
            git(canonical, "worktree", "add", "--quiet", "-b", "branch-only", str(branch))
            branch_plan = branch / "PLAN.md"
            branch_plan.write_text(
                branch_plan.read_text(encoding="utf-8").replace(
                    "- [pending] the outcome is proven",
                    "- [pending] branch-only work ~cc33 | proof: cmd true\n"
                    "- [pending] the outcome is proven",
                ),
                encoding="utf-8",
            )
            git(branch, "add", "PLAN.md")
            git(branch, "commit", "--quiet", "-m", "add a row only on this branch")

            claimed = run(
                home,
                "throw",
                "--repo",
                str(branch),
                "--task",
                "~cc33",
                "--by",
                "branch-seat",
                extra_env=environment,
            )

            self.assertEqual(claimed.returncode, 1, claimed.stderr)
            self.assertIn("stored", claimed.stderr.lower())
            self.assertIn("~cc33", claimed.stderr)
            self.assertEqual(board(home)["claims"], [])


class ProjectsGroupEntitiesWithoutCollapsingThem(unittest.TestCase):
    def test_one_project_rotates_two_entities_with_one_shared_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            web = project(
                portfolio, name="shared-web", display_name="shared", priority=2
            )
            api = project(
                portfolio, name="shared-api", display_name="shared", priority=4
            )
            environment = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}

            observed = run(
                home, "status", "--json", cwd=root, extra_env=environment
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            payload = board(home)
            self.assertEqual(payload["projects"], [{"id": "shared", "priority": 2}])
            self.assertEqual(len(payload["entities"]), 2)
            report = json.loads(observed.stdout)["root_board"]
            self.assertEqual(report["projects"], [
                {"project": "shared", "priority": 2, "entities": 2}
            ])
            self.assertEqual(len({item["entity"] for item in report["entities"]}), 2)

            reprioritized = run(
                home,
                "priority",
                "--repo",
                str(api),
                "--value",
                "1",
                extra_env=environment,
            )
            self.assertEqual(reprioritized.returncode, 0, reprioritized.stderr)
            self.assertEqual(board(home)["projects"][0]["priority"], 1)

            first = run(
                home, "throw", "--repo", str(web), "--task", "~aa11",
                "--by", "seat-web", extra_env=environment,
            )
            second = run(
                home, "throw", "--repo", str(api), "--task", "~aa11",
                "--by", "seat-api", extra_env=environment,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            claims = board(home)["claims"]
            self.assertEqual({item["owner"] for item in claims}, {"seat-web", "seat-api"})
            self.assertEqual(len({item["entity"] for item in claims}), 2)

    def test_one_repository_project_map_preserves_entity_claims_and_cold_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            unrelated = root / "unrelated"
            home.mkdir()
            portfolio.mkdir()
            unrelated.mkdir()
            repo = project(
                portfolio,
                name="shared-repo",
                display_name="shared",
            )
            root_plan = repo / "PLAN.md"
            root_plan.write_text(
                root_plan.read_text(encoding="utf-8").replace(
                    "- Mode: ship\n",
                    "- Mode: ship\n- Plans: plans/*/PLAN.md\n",
                ),
                encoding="utf-8",
            )
            nested_plan = repo / "plans" / "api" / "PLAN.md"
            nested_plan.parent.mkdir(parents=True)
            nested_plan.write_text(
                "# API\n\n"
                "## Brief\n\n"
                "- Project: shared\n"
                "- Mode: ship\n"
                "- Priority: 2\n\n"
                "## Tasks\n\n"
                "### The API outcome\n"
                "- [pending] API-TASK-BELONGS-TO-NESTED-ENTITY ~aa11"
                " | proof: cmd true\n"
                "- [pending] the API outcome is proven ~bb22 (DoD)"
                " | proof: cmd true | needs: ~aa11\n\n"
                "## Progress\n\n"
                "- 2026-08-27T00:00:00Z NOTE seeded\n",
                encoding="utf-8",
            )
            linted = run(
                home,
                "lint",
                "PLAN.md",
                "plans/api/PLAN.md",
                cwd=repo,
            )
            self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
            git(repo, "add", "PLAN.md", "plans/api/PLAN.md")
            git(repo, "commit", "--quiet", "-m", "declare one project map")

            registered = run(
                home,
                "status",
                "--root",
                str(portfolio),
                "--json",
                cwd=root,
            )

            self.assertEqual(registered.returncode, 0, registered.stderr)
            payload = board(home)
            self.assertEqual(payload["projects"], [{"id": "shared", "priority": 2}])
            self.assertEqual(len(payload["entities"]), 2)
            entities = {
                Path(item["plan"]).resolve().relative_to(repo.resolve()).as_posix(): item["id"]
                for item in payload["entities"]
            }
            self.assertEqual(set(entities), {"PLAN.md", "plans/api/PLAN.md"})
            selected, owned = board_api.seat_board_entities(payload, "cold-seat")
            self.assertEqual(owned, 0)
            self.assertEqual(len(selected), 1)
            next_selected, next_owned = board_api.seat_board_entities(
                payload,
                "cold-seat",
                inspected_entities=selected,
            )
            self.assertEqual(next_owned, 0)
            self.assertEqual(len(next_selected), 1)
            self.assertEqual(selected | next_selected, set(entities.values()))

            for entity_id in entities.values():
                claimed = run(
                    home,
                    "throw",
                    "--entity",
                    entity_id,
                    "--task",
                    "~aa11",
                    "--by",
                    "map-seat",
                    cwd=unrelated,
                )
                self.assertEqual(claimed.returncode, 0, claimed.stderr)

            claims = [
                item for item in board(home)["claims"]
                if item["owner"] == "map-seat"
            ]
            self.assertEqual(
                {(item["entity"], item["row"]) for item in claims},
                {(entity_id, "~aa11") for entity_id in entities.values()},
            )
            selected_owned, owned_count = board_api.seat_board_entities(
                board(home),
                "map-seat",
                inspected_entities=set(entities.values()),
            )
            self.assertEqual(selected_owned, set(entities.values()))
            self.assertEqual(owned_count, 2)

            cold = run(home, "status", "--by", "map-seat", cwd=unrelated)
            self.assertEqual(cold.returncode, 0, cold.stderr)
            for entity_id in entities.values():
                self.assertIn(
                    f"Continue: shadow amp --entity {entity_id} "
                    "--task '~aa11' --by map-seat",
                    cold.stdout,
                )

            root_resume = run(
                home,
                "amp",
                "--entity",
                entities["PLAN.md"],
                "--by",
                "map-seat",
                cwd=unrelated,
            )
            nested_resume = run(
                home,
                "amp",
                "--entity",
                entities["plans/api/PLAN.md"],
                "--by",
                "map-seat",
                cwd=unrelated,
            )
            self.assertEqual(root_resume.returncode, 0, root_resume.stderr)
            self.assertEqual(nested_resume.returncode, 0, nested_resume.stderr)
            self.assertIn("TASK-BODY-MUST-NOT-ENTER-THE-BOARD", root_resume.stdout)
            self.assertNotIn("API-TASK-BELONGS-TO-NESTED-ENTITY", root_resume.stdout)
            self.assertIn("API-TASK-BELONGS-TO-NESTED-ENTITY", nested_resume.stdout)
            self.assertNotIn("TASK-BODY-MUST-NOT-ENTER-THE-BOARD", nested_resume.stdout)

            accepted_root = run(
                home,
                "accept",
                "--entity",
                entities["PLAN.md"],
                "--row",
                "~aa11",
                "--by",
                "map-seat",
                "--no-push",
                cwd=unrelated,
            )
            self.assertEqual(accepted_root.returncode, 0, accepted_root.stderr)
            after_root = board(home)
            after_root_entities = {
                Path(item["plan"]).resolve().relative_to(repo.resolve()).as_posix(): item
                for item in after_root["entities"]
            }
            self.assertEqual(
                {
                    (item["entity"], item["row"], item["owner"])
                    for item in after_root["claims"]
                },
                {
                    (
                        entities["plans/api/PLAN.md"],
                        "~aa11",
                        "map-seat",
                    )
                },
            )
            self.assertEqual(after_root_entities["PLAN.md"]["resume"], "~bb22")
            self.assertEqual(
                after_root_entities["plans/api/PLAN.md"]["resume"],
                "~aa11",
            )
            self.assertIn(
                "- [completed] TASK-BODY-MUST-NOT-ENTER-THE-BOARD ~aa11",
                root_plan.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "- [pending] API-TASK-BELONGS-TO-NESTED-ENTITY ~aa11",
                nested_plan.read_text(encoding="utf-8"),
            )

            accepted_nested = run(
                home,
                "accept",
                "--entity",
                entities["plans/api/PLAN.md"],
                "--row",
                "~aa11",
                "--by",
                "map-seat",
                "--no-push",
                cwd=unrelated,
            )
            self.assertEqual(accepted_nested.returncode, 0, accepted_nested.stderr)
            after_nested = board(home)
            self.assertEqual(after_nested["claims"], [])
            self.assertEqual(
                {
                    Path(item["plan"]).resolve().relative_to(repo.resolve()).as_posix():
                    item["resume"]
                    for item in after_nested["entities"]
                },
                {
                    "PLAN.md": "~bb22",
                    "plans/api/PLAN.md": "~bb22",
                },
            )
            self.assertIn(
                "- [completed] API-TASK-BELONGS-TO-NESTED-ENTITY ~aa11",
                nested_plan.read_text(encoding="utf-8"),
            )

    def test_sibling_row_id_never_satisfies_local_needs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            project(
                portfolio,
                name="producer",
                display_name="shared",
            )
            consumer = project(
                portfolio,
                name="consumer",
                display_name="shared",
            )
            consumer_plan = consumer / "PLAN.md"
            consumer_plan.write_text(
                "# Consumer\n\n"
                "## Brief\n\n"
                "- Project: shared\n"
                "- Mode: ship\n"
                "- Priority: 2\n\n"
                "## Tasks\n\n"
                "### Consume one producer\n"
                "- [pending] integration observes the producer ~cc33"
                " | proof: cmd true | needs: ~aa11\n"
                "- [pending] integration is proven ~dd44 (DoD)"
                " | proof: cmd true | needs: ~cc33\n\n"
                "## Progress\n\n"
                "- 2026-08-27T00:00:00Z NOTE seeded\n",
                encoding="utf-8",
            )
            git(consumer, "add", "PLAN.md")
            git(consumer, "commit", "--quiet", "-m", "add invalid sibling need")
            environment = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}

            refused = run(
                home,
                "status",
                "--json",
                cwd=root,
                extra_env=environment,
            )
            linted = run(
                home,
                "lint",
                str(consumer_plan),
                cwd=root,
                extra_env=environment,
            )

            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("blocking lint", refused.stderr)
            self.assertNotEqual(linted.returncode, 0)
            self.assertIn("NEEDS-DANGLE", linted.stdout + linted.stderr)
            board_path = home / ".shadow" / "board.json"
            if board_path.exists():
                self.assertEqual(board(home)["entities"], [])

            consumer_plan.write_text(
                consumer_plan.read_text(encoding="utf-8").replace(
                    "### Consume one producer\n",
                    "### Consume one producer\n"
                    "- [pending] local producer is explicit ~aa11"
                    " | proof: cmd true\n",
                ),
                encoding="utf-8",
            )
            git(consumer, "add", "PLAN.md")
            git(consumer, "commit", "--quiet", "-m", "add local dependency owner")

            accepted = run(
                home,
                "status",
                "--json",
                cwd=root,
                extra_env=environment,
            )

            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            payload = board(home)
            self.assertEqual(payload["projects"], [{"id": "shared", "priority": 2}])
            self.assertEqual(len(payload["entities"]), 2)

    def test_highest_priority_project_renders_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            project(portfolio, name="alpha", display_name="alpha", priority=5)
            project(portfolio, name="zeta", display_name="zeta", priority=1)

            observed = run(
                home,
                "status",
                "--json",
                cwd=root,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            records = json.loads(observed.stdout)["v4_plans"]
            self.assertEqual([item["project"] for item in records], ["zeta", "alpha"])


class ProjectMapMigrationIsAtomicAndReversible(unittest.TestCase):
    @staticmethod
    def _authority(payload: dict) -> str:
        authority = json.loads(json.dumps(payload))
        authority.pop("revision")
        return json.dumps(
            authority, sort_keys=True, separators=(",", ":")
        )

    def _fixture(self, root: Path) -> dict[str, object]:
        home = root / "home"
        portfolio = root / "portfolio"
        unrelated = root / "unrelated"
        home.mkdir()
        portfolio.mkdir()
        unrelated.mkdir()
        repo = project(
            portfolio,
            name="shared-repo",
            display_name="shared",
        )
        plan = repo / "PLAN.md"
        source_text = (
            "# Shared\n\n"
            "## Brief\n\n"
            "- Project: shared\n"
            "- Mode: ship\n"
            "- Priority: 2\n\n"
            "## Tasks\n\n"
            "### Root outcome\n"
            "- [pending] ROOT-TASK-STAYS-IN-ROOT ~cc33"
            " | proof: gate owner resume: root approved\n"
            "- [pending] ROOT-RESUME-STAYS-IN-ROOT ~ee55 | proof: cmd true\n"
            "- [pending] root outcome is proven ~dd44 (DoD)"
            " | proof: cmd true | needs: ~cc33, ~ee55\n\n"
            "### Child outcome\n"
            "- [pending] CHILD-TASK-MOVES-TO-CHILD ~aa11 | proof: cmd true\n"
            "- [pending] child outcome is proven ~bb22 (DoD)"
            " | proof: cmd true | needs: ~aa11\n\n"
            "## Contradictions\n\n"
            "- OPEN child contradiction names ~aa11 | winner: child owns it\n"
            "- RESOLVED root contradiction names ~cc33 | winner: root owns it\n\n"
            "## Progress\n\n"
            "- 2026-08-27T00:00:00Z ~aa11 NOTE child provenance\n"
            "- 2026-08-27T00:01:00Z ~cc33 NOTE root provenance\n"
        )
        plan.write_text(source_text, encoding="utf-8")
        git(repo, "add", "PLAN.md")
        git(repo, "commit", "--quiet", "-m", "seed migration monolith")
        registered = run(
            home,
            "status",
            "--root",
            str(portfolio),
            "--json",
            cwd=root,
        )
        self.assertEqual(registered.returncode, 0, registered.stderr)
        root_claimed = run(
            home,
            "throw",
            "--repo",
            str(repo),
            "--task",
            "~cc33",
            "--by",
            "root-seat",
            cwd=unrelated,
        )
        self.assertEqual(root_claimed.returncode, 0, root_claimed.stderr)
        claimed = run(
            home,
            "throw",
            "--repo",
            str(repo),
            "--task",
            "~aa11",
            "--by",
            "cold-seat",
            cwd=unrelated,
        )
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        source_head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        source_branch = subprocess.run(
            ["git", "-C", str(repo), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        before = board(home)
        board_bytes = (home / ".shadow" / "board.json").read_bytes()
        board_head = subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        child = repo / "plans" / "child" / "PLAN.md"
        child.parent.mkdir(parents=True)
        plan.write_text(
            "# Shared\n\n"
            "## Brief\n\n"
            "- Project: shared\n"
            "- Mode: ship\n"
            "- Priority: 2\n"
            "- Plans: plans/*/PLAN.md\n\n"
            "## Tasks\n\n"
            "### Root outcome\n"
            "- [pending] ROOT-TASK-STAYS-IN-ROOT ~cc33"
            " | proof: gate owner resume: root approved\n"
            "- [pending] ROOT-RESUME-STAYS-IN-ROOT ~ee55 | proof: cmd true\n"
            "- [pending] root outcome is proven ~dd44 (DoD)"
            " | proof: cmd true | needs: ~cc33, ~ee55\n\n"
            "## Contradictions\n\n"
            "- RESOLVED root contradiction names ~cc33 | winner: root owns it\n\n"
            "## Progress\n\n"
            "- 2026-08-27T00:01:00Z ~cc33 NOTE root provenance\n",
            encoding="utf-8",
        )
        child.write_text(
            "# Child\n\n"
            "## Brief\n\n"
            "- Project: shared\n"
            "- Mode: ship\n"
            "- Priority: 2\n\n"
            "## Tasks\n\n"
            "### Child outcome\n"
            "- [pending] CHILD-TASK-MOVES-TO-CHILD ~aa11 | proof: cmd true\n"
            "- [pending] child outcome is proven ~bb22 (DoD)"
            " | proof: cmd true | needs: ~aa11\n\n"
            "## Contradictions\n\n"
            "- OPEN child contradiction names ~aa11 | winner: child owns it\n\n"
            "## Progress\n\n"
            "- 2026-08-27T00:00:00Z ~aa11 NOTE child provenance\n",
            encoding="utf-8",
        )
        git(repo, "add", "PLAN.md", "plans/child/PLAN.md")
        git(repo, "commit", "--quiet", "-m", "prepare bounded project map")
        target_head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        git(repo, "branch", "map-target", target_head)
        git(repo, "reset", "--hard", "--quiet", source_head)
        return {
            "home": home,
            "portfolio": portfolio,
            "unrelated": unrelated,
            "repo": repo,
            "plan": plan,
            "child": child,
            "source_text": source_text,
            "source_branch": source_branch,
            "source_head": source_head,
            "target_head": target_head,
            "before": before,
            "board_bytes": board_bytes,
            "board_head": board_head,
        }

    @staticmethod
    def _map_args(fixture: dict[str, object]) -> list[str]:
        return [
            "plan",
            "map-migrate",
            str(fixture["plan"]),
            "--target-ref",
            "map-target",
            "--child",
            "plans/child/PLAN.md",
        ]

    def _dry_payload(self, fixture: dict[str, object]) -> dict:
        dry = run(
            fixture["home"],
            *self._map_args(fixture),
            "--dry-run",
            cwd=fixture["repo"],
        )
        self.assertEqual(dry.returncode, 0, dry.stderr)
        return json.loads(dry.stdout)

    @staticmethod
    def _head(repo: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    @staticmethod
    def _board_head(home: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def test_map_migration_round_trip_preserves_claim_and_cold_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            home = fixture["home"]
            repo = fixture["repo"]
            plan = fixture["plan"]
            unrelated = fixture["unrelated"]
            before = fixture["before"]
            dry = run(
                home,
                *self._map_args(fixture),
                "--dry-run",
                cwd=repo,
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            transaction = json.loads(dry.stdout)["transaction_sha256"]
            receipt = home / "migration-receipt.json"
            applied = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                transaction,
                "--receipt",
                str(receipt),
                cwd=repo,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            applied_payload = json.loads(applied.stdout)
            receipt_bytes = receipt.read_bytes()
            receipt_payload = json.loads(receipt_bytes)
            self.assertEqual(receipt_payload["phase"], "prepared")
            self.assertEqual(
                receipt_payload["transaction_sha256"],
                transaction,
            )
            after = board(home)
            entities = {item["id"]: item for item in after["entities"]}
            self.assertEqual(len(entities), 2)
            root_id = board_api.entity_id(plan)
            child_id = board_api.entity_id(fixture["child"])
            self.assertIn(root_id, entities)
            self.assertIn(child_id, entities)
            self.assertEqual(entities[root_id]["resume"], "~ee55")
            self.assertEqual(entities[child_id]["resume"], "~aa11")
            self.assertEqual(after["projects"], before["projects"])
            before_claims = {item["row"]: item for item in before["claims"]}
            after_claims = {item["row"]: item for item in after["claims"]}
            self.assertEqual(set(after_claims), {"~aa11", "~cc33"})
            self.assertEqual(after_claims["~aa11"]["entity"], child_id)
            self.assertEqual(after_claims["~cc33"]["entity"], root_id)
            for row in before_claims:
                self.assertEqual(
                    {
                        key: value
                        for key, value in after_claims[row].items()
                        if key != "entity"
                    },
                    {
                        key: value
                        for key, value in before_claims[row].items()
                        if key != "entity"
                    },
                )
            cold = run(home, "status", "--by", "cold-seat", cwd=unrelated)
            self.assertEqual(cold.returncode, 0, cold.stderr)
            self.assertIn(
                f"Continue: shadow amp --entity {child_id} "
                "--task '~aa11' --by cold-seat",
                cold.stdout,
            )
            root_cold = run(
                home,
                "status",
                "--by",
                "root-seat",
                cwd=unrelated,
            )
            self.assertEqual(root_cold.returncode, 0, root_cold.stderr)
            self.assertIn(
                f"Continue: shadow amp --entity {root_id} "
                "--task '~cc33' --by root-seat",
                root_cold.stdout,
            )

            rolled_back = run(
                home,
                "plan",
                "map-rollback",
                str(plan),
                "--receipt",
                str(receipt),
                "--apply",
                "--expect",
                applied_payload["applied_sha256"],
                cwd=repo,
            )
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            self.assertEqual(receipt.read_bytes(), receipt_bytes)
            rollback_path = receipt.with_name(
                receipt.stem + ".rollback.json"
            )
            rollback_payload = json.loads(
                rollback_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                rollback_payload["migration_sha256"],
                transaction,
            )
            frozen_rollback = dict(rollback_payload)
            rollback_digest = frozen_rollback.pop("rollback_sha256")
            self.assertEqual(
                hashlib.sha256(
                    json.dumps(
                        frozen_rollback,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                rollback_digest,
            )
            restored = board(home)
            self.assertEqual(plan.read_text(encoding="utf-8"), fixture["source_text"])
            self.assertFalse(fixture["child"].exists())
            self.assertEqual(
                self._authority(restored),
                self._authority(before),
            )
            self.assertEqual(restored["projects"], before["projects"])
            self.assertEqual(restored["entities"], before["entities"])
            self.assertEqual(restored["claims"], before["claims"])
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "rev-parse",
                        "--verify",
                        "HEAD",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip(),
                fixture["source_head"],
            )
            self.assertFalse(
                subprocess.run(
                    ["git", "-C", str(repo), "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
            )
            cold_restored = run(
                home,
                "status",
                "--by",
                "cold-seat",
                cwd=unrelated,
            )
            self.assertEqual(cold_restored.returncode, 0, cold_restored.stderr)
            self.assertIn(
                f"Continue: shadow amp --entity {root_id} "
                "--task '~aa11' --by cold-seat",
                cold_restored.stdout,
            )
            restored_board_head = self._board_head(home)
            repeated = run(
                home,
                "plan",
                "map-rollback",
                str(plan),
                "--receipt",
                str(receipt),
                "--apply",
                "--expect",
                transaction,
                cwd=repo,
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(self._head(repo), fixture["source_head"])
            self.assertEqual(self._board_head(home), restored_board_head)
            self.assertEqual(board(home), restored)

    def test_direct_board_api_rejects_forged_routes_and_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            home = fixture["home"]
            repo = fixture["repo"]
            git(repo, "reset", "--hard", "--quiet", fixture["target_head"])
            board_bytes = (home / ".shadow" / "board.json").read_bytes()
            board_head = self._board_head(home)

            wrong_route = json.loads(json.dumps(prepared))
            next(
                item for item in wrong_route["row_map"] if item["row"] == "~aa11"
            )["destination"] = "root"
            with self.assertRaisesRegex(
                board_api.BoardError,
                "actual plan membership",
            ):
                board_api.apply_project_map_migration(
                    fixture["plan"],
                    fixture["child"],
                    wrong_route,
                    home=home,
                )

            wrong_candidates = json.loads(json.dumps(prepared))
            wrong_candidates["plans"]["root"]["candidates"] = []
            with self.assertRaisesRegex(
                board_api.BoardError,
                "resume candidates changed",
            ):
                board_api.apply_project_map_migration(
                    fixture["plan"],
                    fixture["child"],
                    wrong_candidates,
                    home=home,
                )

            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                board_bytes,
            )
            self.assertEqual(self._board_head(home), board_head)

    def test_apply_journal_failure_restores_git_board_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            transaction = prepared["transaction_sha256"]
            home = fixture["home"]
            repo = fixture["repo"]
            receipt = home / "journal-failure.json"
            original_commit = board_api._commit

            def fail_after_commit(root: Path, message: str) -> None:
                original_commit(root, message)
                if message == "shadow board: apply project-map migration":
                    raise board_api.BoardError("injected apply journal failure")

            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                board_api,
                "_commit",
                side_effect=fail_after_commit,
            ):
                with self.assertRaisesRegex(
                    board_api.BoardError,
                    "injected apply journal failure",
                ):
                    plan_api._apply_project_map_migration(
                        fixture["plan"],
                        "map-target",
                        Path("plans/child/PLAN.md"),
                        transaction,
                        receipt,
                    )

            self.assertEqual(self._head(repo), fixture["source_head"])
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                fixture["board_bytes"],
            )
            self.assertEqual(self._board_head(home), fixture["board_head"])
            self.assertEqual(
                json.loads(receipt.read_text(encoding="utf-8"))["phase"],
                "prepared",
            )

            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                applied = plan_api._apply_project_map_migration(
                    fixture["plan"],
                    "map-target",
                    Path("plans/child/PLAN.md"),
                    transaction,
                    receipt,
                )
            self.assertEqual(applied["action"], "applied")
            self.assertEqual(self._head(repo), fixture["target_head"])
            self.assertEqual(len(board(home)["entities"]), 2)

    def test_apply_resumes_from_prepared_receipt_after_fast_forward(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            home = fixture["home"]
            repo = fixture["repo"]
            receipt = home / "crash-after-fast-forward.json"
            receipt.write_text(
                json.dumps(prepared, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.chmod(receipt, 0o600)
            git(repo, "reset", "--hard", "--quiet", fixture["target_head"])

            recovered = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                prepared["transaction_sha256"],
                "--receipt",
                str(receipt),
                cwd=repo,
            )

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(self._head(repo), fixture["target_head"])
            self.assertEqual(len(board(home)["entities"]), 2)
            self.assertEqual(
                json.loads(receipt.read_text(encoding="utf-8")),
                prepared,
            )

    def test_rollback_journal_failure_restores_target_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            transaction = prepared["transaction_sha256"]
            home = fixture["home"]
            repo = fixture["repo"]
            receipt = home / "rollback-journal-failure.json"
            applied = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                transaction,
                "--receipt",
                str(receipt),
                cwd=repo,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            applied_board = (home / ".shadow" / "board.json").read_bytes()
            applied_board_head = self._board_head(home)
            original_commit = board_api._commit

            def fail_after_commit(root: Path, message: str) -> None:
                original_commit(root, message)
                if message == "shadow board: roll back project-map migration":
                    raise board_api.BoardError("injected rollback journal failure")

            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                board_api,
                "_commit",
                side_effect=fail_after_commit,
            ):
                with self.assertRaisesRegex(
                    board_api.BoardError,
                    "injected rollback journal failure",
                ):
                    plan_api._rollback_project_map_migration(
                        fixture["plan"],
                        receipt,
                        transaction,
                    )

            self.assertEqual(self._head(repo), fixture["target_head"])
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                applied_board,
            )
            self.assertEqual(self._board_head(home), applied_board_head)
            self.assertTrue(
                receipt.with_name(receipt.stem + ".rollback.json").is_file()
            )

            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                rolled_back = plan_api._rollback_project_map_migration(
                    fixture["plan"],
                    receipt,
                    transaction,
                )
            self.assertEqual(rolled_back["migration_sha256"], transaction)
            self.assertEqual(self._head(repo), fixture["source_head"])
            self.assertEqual(
                self._authority(board(home)),
                self._authority(fixture["before"]),
            )

    def test_rollback_resumes_after_source_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            transaction = prepared["transaction_sha256"]
            home = fixture["home"]
            repo = fixture["repo"]
            receipt = home / "crash-after-source-reset.json"
            applied = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                transaction,
                "--receipt",
                str(receipt),
                cwd=repo,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            git(repo, "reset", "--hard", "--quiet", fixture["source_head"])

            recovered = run(
                home,
                "plan",
                "map-rollback",
                str(fixture["plan"]),
                "--receipt",
                str(receipt),
                "--apply",
                "--expect",
                transaction,
                cwd=repo,
            )

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(self._head(repo), fixture["source_head"])
            self.assertEqual(
                self._authority(board(home)),
                self._authority(fixture["before"]),
            )

    def test_receipt_inside_repository_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            home = fixture["home"]
            repo = fixture["repo"]
            receipt = repo / "migration.json"

            refused = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                prepared["transaction_sha256"],
                "--receipt",
                str(receipt),
                cwd=repo,
            )

            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("outside the repository", refused.stderr)
            self.assertFalse(receipt.exists())
            self.assertEqual(self._head(repo), fixture["source_head"])
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                fixture["board_bytes"],
            )
            self.assertEqual(self._board_head(home), fixture["board_head"])

    def test_unsafe_child_path_and_recursive_declaration_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            home = fixture["home"]
            repo = fixture["repo"]
            unsafe_child = run(
                home,
                "plan",
                "map-migrate",
                str(fixture["plan"]),
                "--dry-run",
                "--target-ref",
                "map-target",
                "--child",
                ":(glob)**/PLAN.md",
                cwd=repo,
            )
            self.assertNotEqual(unsafe_child.returncode, 0)
            self.assertIn("safe relative PLAN.md", unsafe_child.stderr)

            git(repo, "checkout", "--quiet", "map-target")
            fixture["plan"].write_text(
                fixture["plan"].read_text(encoding="utf-8").replace(
                    "- Plans: plans/*/PLAN.md",
                    "- Plans: **/PLAN.md",
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "--amend", "--no-edit")
            git(repo, "checkout", "--quiet", fixture["source_branch"])
            recursive = run(
                home,
                *self._map_args(fixture),
                "--dry-run",
                cwd=repo,
            )
            self.assertNotEqual(recursive.returncode, 0)
            self.assertIn("unsafe child plan declaration", recursive.stderr)
            self.assertEqual(self._head(repo), fixture["source_head"])
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                fixture["board_bytes"],
            )

    def test_rollback_sidecar_and_post_apply_board_tamper_refuse_before_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            prepared = self._dry_payload(fixture)
            transaction = prepared["transaction_sha256"]
            home = fixture["home"]
            repo = fixture["repo"]
            receipt = home / "rollback-preflight.json"
            applied = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                transaction,
                "--receipt",
                str(receipt),
                cwd=repo,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            applied_board = (home / ".shadow" / "board.json").read_bytes()
            applied_board_head = self._board_head(home)
            sidecar = receipt.with_name(receipt.stem + ".rollback.json")
            sidecar.mkdir()

            refused_sidecar = run(
                home,
                "plan",
                "map-rollback",
                str(fixture["plan"]),
                "--receipt",
                str(receipt),
                "--apply",
                "--expect",
                transaction,
                cwd=repo,
            )

            self.assertNotEqual(refused_sidecar.returncode, 0)
            self.assertIn("regular file", refused_sidecar.stderr)
            self.assertEqual(self._head(repo), fixture["target_head"])
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                applied_board,
            )
            self.assertEqual(self._board_head(home), applied_board_head)
            sidecar.rmdir()

            board_api.set_priority(
                fixture["plan"],
                3,
                home=home,
            )
            tampered_board = (home / ".shadow" / "board.json").read_bytes()
            tampered_head = self._board_head(home)
            refused_tamper = run(
                home,
                "plan",
                "map-rollback",
                str(fixture["plan"]),
                "--receipt",
                str(receipt),
                "--apply",
                "--expect",
                transaction,
                cwd=repo,
            )
            self.assertNotEqual(refused_tamper.returncode, 0)
            self.assertIn("state changed after apply", refused_tamper.stderr)
            self.assertEqual(self._head(repo), fixture["target_head"])
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                tampered_board,
            )
            self.assertEqual(self._board_head(home), tampered_head)

    def test_map_migration_child_change_after_dry_run_writes_no_board_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(Path(tmp))
            home = fixture["home"]
            repo = fixture["repo"]
            dry = run(
                home,
                *self._map_args(fixture),
                "--dry-run",
                cwd=repo,
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            transaction = json.loads(dry.stdout)["transaction_sha256"]
            git(repo, "checkout", "--quiet", "map-target")
            fixture["child"].write_text(
                fixture["child"].read_text(encoding="utf-8")
                + "\n<!-- changed after dry run -->\n",
                encoding="utf-8",
            )
            git(repo, "add", "plans/child/PLAN.md")
            git(repo, "commit", "--quiet", "-m", "mutate target after dry run")
            git(repo, "checkout", "--quiet", fixture["source_branch"])
            receipt = home / "stale-receipt.json"
            refused = run(
                home,
                *self._map_args(fixture),
                "--apply",
                "--expect",
                transaction,
                "--receipt",
                str(receipt),
                cwd=repo,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("changed", refused.stderr.lower())
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                fixture["source_head"],
            )
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                fixture["board_bytes"],
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                fixture["board_head"],
            )
            self.assertFalse(receipt.exists())
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                fixture["source_branch"],
            )
            self.assertFalse(
                subprocess.run(
                    ["git", "-C", str(repo), "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
            )


class ExistingBoardStateSurvivesSchemaAndFileRecovery(unittest.TestCase):
    def test_missing_authoritative_file_restores_from_git_without_losing_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            claimed = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            before = board(home)
            (home / ".shadow" / "board.json").unlink()

            module = fresh_board_module("shadow_board_recovery")
            observed = module.ensure(home=home)

            restored = board(home)
            self.assertEqual(restored, before)
            self.assertEqual(observed, before)
            self.assertEqual(restored["claims"][0]["owner"], "seat-a")

    def test_partial_git_lock_fails_closed_until_owner_removes_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            board_root = home / ".shadow"
            (board_root / ".git").mkdir(parents=True)
            module = fresh_board_module("shadow_board_partial_git")

            initialized = module.ensure(home=home)
            self.assertEqual(initialized["revision"], 0)
            (board_root / ".git" / "index.lock").write_bytes(b"")
            os.chmod(board_root, 0o755)
            os.chmod(board_root / "board.json", 0o644)

            with self.assertRaisesRegex(
                module.BoardError,
                "verify no Git process owns it, remove it, and retry",
            ):
                module.ensure(home=home)
            self.assertTrue((board_root / ".git" / "index.lock").exists())
            (board_root / ".git" / "index.lock").unlink()

            observed = module.ensure(home=home)
            self.assertEqual(observed, initialized)
            self.assertEqual(board_root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((board_root / "board.json").stat().st_mode & 0o777, 0o600)

    def test_root_and_git_symlinks_never_redirect_board_reads_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "external"
            external.mkdir()
            git(external, "init", "--quiet")
            git(external, "config", "user.email", "outside@example.invalid")
            git(external, "config", "user.name", "Outside")
            (external / "sentinel").write_text("outside\n", encoding="utf-8")
            git(external, "add", "sentinel")
            git(external, "commit", "--quiet", "-m", "outside")
            outside_head = subprocess.run(
                ["git", "-C", str(external), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout
            module = fresh_board_module("shadow_board_symlink_root")

            home = root / "home"
            home.mkdir()
            (home / ".shadow").symlink_to(external, target_is_directory=True)
            with self.assertRaises(module.BoardError):
                module.snapshot(home=home)
            with self.assertRaises(module.BoardError):
                module.ensure(home=home)

            (home / ".shadow").unlink()
            (home / ".shadow").mkdir()
            (home / ".shadow" / ".git").symlink_to(external / ".git", target_is_directory=True)
            with self.assertRaises(module.BoardError):
                module.ensure(home=home)
            self.assertFalse((home / ".shadow" / "board.json").exists())
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(external), "rev-parse", "HEAD"],
                    capture_output=True, text=True, check=True,
                ).stdout,
                outside_head,
            )

    def test_regular_file_at_root_is_a_bounded_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            (home / ".shadow").write_text("not a directory\n", encoding="utf-8")

            observed = run(home, "status", "--json", cwd=home)

            self.assertEqual(observed.returncode, 1)
            self.assertNotIn("Traceback", observed.stderr)
            self.assertIn("real private directory", observed.stderr)


class RootPriorityHasAnExplicitSetter(unittest.TestCase):
    def test_priority_command_changes_only_the_root_board_and_survives_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            repo = project(portfolio, name="priority", display_name="priority")
            environment = {"SHADOW_PORTFOLIO_ROOT": str(portfolio)}
            registered = run(home, "status", "--json", cwd=root, extra_env=environment)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            before_plan = (repo / "PLAN.md").read_bytes()
            before_revision = board(home)["revision"]

            changed = run(
                home,
                "priority",
                "--repo",
                str(repo),
                "--value",
                "1",
                extra_env=environment,
            )

            self.assertEqual(changed.returncode, 0, changed.stderr)
            payload = board(home)
            self.assertEqual(payload["projects"][0]["priority"], 1)
            self.assertEqual(payload["revision"], before_revision + 1)
            self.assertEqual((repo / "PLAN.md").read_bytes(), before_plan)

            plan_path = repo / "PLAN.md"
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8").replace(
                    "- Priority: 2", "- Priority: 5"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "change bootstrap priority")
            reconciled = run(home, "status", "--json", cwd=root, extra_env=environment)
            self.assertEqual(reconciled.returncode, 0, reconciled.stderr)
            self.assertEqual(board(home)["projects"][0]["priority"], 1)


class ManualProofsCanCloseClaims(unittest.TestCase):
    def test_manual_completion_then_return_closes_the_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root, first_proof="read observed result")
            claimed = run(
                home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            plan_path = repo / "PLAN.md"
            text = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                text.replace("- [pending] TASK-BODY", "- [completed] TASK-BODY")
                + "- 2026-08-10T00:01:00Z ~aa11 PROOF observed -> pass (manual)\n",
                encoding="utf-8",
            )
            refused = run(
                home,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )
            self.assertEqual(refused.returncode, 1, refused.stderr)
            self.assertIn("commit or restore", refused.stderr)
            self.assertEqual(len(board(home)["claims"]), 1)
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "record manual proof")

            returned = run(
                home,
                "return",
                "--repo",
                str(repo),
                "--row",
                "~aa11",
                "--by",
                "seat-a",
            )

            self.assertEqual(returned.returncode, 0, returned.stderr)
            payload = board(home)
            self.assertEqual(payload["claims"], [])
            self.assertEqual(payload["entities"][0]["resume"], "~bb22")


class ProjectLifecycleLocks(unittest.TestCase):
    LOCK_PROCESS = f"""
from pathlib import Path
import sys
sys.path.insert(0, {str(ROOT / 'scripts')!r})
import shadow_root_board
with shadow_root_board.project_lock(Path(sys.argv[1])):
    print('LOCKED', flush=True)
    if sys.argv[2] == 'hold':
        sys.stdin.read(1)
"""

    def _start_lock(
        self, plan: Path, *, hold: bool
    ) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [
                sys.executable,
                "-c",
                self.LOCK_PROCESS,
                str(plan),
                "hold" if hold else "once",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _read_lock_state(
        self, process: subprocess.Popen[str], timeout: float
    ) -> str | None:
        assert process.stdout is not None
        ready, _, _ = select.select([process.stdout], [], [], timeout)
        return process.stdout.readline().strip() if ready else None

    def _release_lock(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            assert process.stdin is not None
            process.stdin.write("g")
            process.stdin.flush()
            process.stdin.close()
            process.stdin = None
        _, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)

    def _finish_lock(self, process: subprocess.Popen[str]) -> None:
        _, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)

    def test_disjoint_sibling_plans_do_not_serialize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            plans = []
            for name in ("alpha", "beta"):
                plan = repo / name / "PLAN.md"
                plan.parent.mkdir()
                plan.write_bytes((repo / "PLAN.md").read_bytes())
                plans.append(plan)
            git(repo, "add", "alpha/PLAN.md", "beta/PLAN.md")
            git(repo, "commit", "--quiet", "-m", "add sibling plans")

            first = self._start_lock(plans[0], hold=True)
            second = None
            try:
                self.assertEqual(self._read_lock_state(first, 2), "LOCKED")
                second = self._start_lock(plans[1], hold=False)
                self.assertEqual(self._read_lock_state(second, 0.5), "LOCKED")
            finally:
                self._release_lock(first)
                if second is not None:
                    self._finish_lock(second)

    def test_same_plan_across_worktrees_still_serializes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            sibling = root / "sibling-worktree"
            git(repo, "worktree", "add", "--quiet", "--detach", str(sibling), "HEAD")

            first = self._start_lock(repo / "PLAN.md", hold=True)
            second = None
            try:
                self.assertEqual(self._read_lock_state(first, 2), "LOCKED")
                second = self._start_lock(sibling / "PLAN.md", hold=False)
                self.assertIsNone(self._read_lock_state(second, 0.25))
                self.assertIsNone(second.poll())
                self._release_lock(first)
                first = None
                self.assertEqual(self._read_lock_state(second, 2), "LOCKED")
            finally:
                if first is not None:
                    self._release_lock(first)
                if second is not None:
                    self._finish_lock(second)


class ConcurrentClaimsHaveExactlyOneWinner(unittest.TestCase):
    def test_two_seats_racing_one_pointer_produce_one_named_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = project(root)
            env = {**os.environ, "HOME": str(home)}
            run(home, "status", cwd=repo)
            race_script = f"""
import importlib.util
import sys
sys.path.insert(0, {str(ROOT / 'scripts')!r})
import shadow_root_board
real_flock = shadow_root_board.fcntl.flock
exclusive_locks = 0
def gated_flock(descriptor, operation):
    global exclusive_locks
    if operation & shadow_root_board.fcntl.LOCK_EX:
        exclusive_locks += 1
        if exclusive_locks == 1:
            print('READY', flush=True)
            if sys.stdin.read(1) != 'g':
                raise SystemExit(98)
    return real_flock(descriptor, operation)
shadow_root_board.fcntl.flock = gated_flock
spec = importlib.util.spec_from_file_location('shadow_throw_race', {str(ROOT / 'scripts' / 'shadow-throw.py')!r})
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
raise SystemExit(module.main(sys.argv[1:]))
"""
            command = (
                sys.executable,
                "-c",
                race_script,
                "--repo",
                str(repo),
                "--task",
                "~aa11",
                "--by",
            )
            owners = ("seat-a", "seat-b")
            processes = [
                subprocess.Popen(
                    [*command, owner],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
                for owner in owners
            ]
            for process in processes:
                assert process.stdout is not None
                self.assertEqual(process.stdout.readline().strip(), "READY")
            for process in processes:
                assert process.stdin is not None
                process.stdin.write("g")
                process.stdin.flush()
                process.stdin.close()
                process.stdin = None
            results = [
                (owner, *process.communicate(timeout=10), process.returncode)
                for owner, process in zip(owners, processes)
            ]

            self.assertEqual(sorted(result[3] for result in results), [0, 1], results)
            payload = board(home)
            self.assertEqual(len(payload["claims"]), 1)
            winner = payload["claims"][0]["owner"]
            process_winner = next(result[0] for result in results if result[3] == 0)
            self.assertEqual(winner, process_winner)
            loser = next(result for result in results if result[3] == 1)
            self.assertIn(f"claimed by {winner}", loser[2])
            self.assertEqual(loser[1], "")


class ACrashMidClaimLeavesARecoverableBoard(unittest.TestCase):
    def test_death_before_atomic_replace_cannot_corrupt_or_wedge_the_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            module = fresh_board_module("shadow_root_board")
            for death in ("before-replace", "after-replace"):
                home = root / death
                home.mkdir()
                module.ensure(home=home)
                board_path = home / ".shadow" / "board.json"
                before = board_path.read_bytes()

                child = os.fork()
                if child == 0:
                    real_replace = module._replace
                    if death == "before-replace":
                        module._replace = lambda _source, _destination: os.kill(
                            os.getpid(), signal.SIGKILL
                        )
                    else:
                        def replace_then_die(source, destination):
                            real_replace(source, destination)
                            os.kill(os.getpid(), signal.SIGKILL)
                        module._replace = replace_then_die
                    module.claim(
                        repo / "PLAN.md", "~aa11", "crashed-seat",
                        project="project", priority=2, home=home
                    )
                    os._exit(99)
                _, status = os.waitpid(child, 0)
                self.assertTrue(os.WIFSIGNALED(status))
                self.assertEqual(os.WTERMSIG(status), signal.SIGKILL)

                if death == "before-replace":
                    self.assertEqual(board_path.read_bytes(), before)
                    recovered = run(
                        home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "successor"
                    )
                    self.assertEqual(recovered.returncode, 0, recovered.stderr)
                    self.assertEqual(board(home)["claims"][0]["owner"], "successor")
                else:
                    payload = board(home)
                    self.assertEqual(payload["claims"][0]["owner"], "crashed-seat")
                    contender = run(
                        home, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "successor"
                    )
                    self.assertEqual(contender.returncode, 1)
                    self.assertIn("claimed by crashed-seat", contender.stderr)
                    self.assertEqual(
                        subprocess.run(
                            ["git", "-C", str(home / ".shadow"), "show", "HEAD:board.json"],
                            capture_output=True,
                            check=True,
                        ).stdout,
                        board_path.read_bytes(),
                    )
                    self.assertEqual(
                        subprocess.run(
                            ["git", "-C", str(home / ".shadow"), "status", "--porcelain", "--", "board.json"],
                            capture_output=True,
                            text=True,
                            check=True,
                        ).stdout,
                        "",
                    )


class BoardAuthorityDoesNotLiveOnVolatileStorage(unittest.TestCase):
    """A registered plan under a swept temp root yields to a durable sibling."""

    REMOTE = "git@example.invalid:team/shadow.git"

    def _fixture(self, root: Path, *, with_sibling: bool):
        home = root / "home"
        volatile = root / "volatile"
        durable = root / "durable"
        blank = root / "blank"
        for path in (home, volatile, durable, blank):
            path.mkdir()
        registered = project(volatile, name="shadow", display_name="shadow")
        git(registered, "remote", "add", "origin", self.REMOTE)
        out = run(home, "status", "--root", str(registered), "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(len(board(home)["entities"]), 1)
        if with_sibling:
            git(registered, "worktree", "add", "--quiet", "--detach",
                str(durable / "shadow"), "HEAD")
        return {
            "home": home,
            "registered": registered,
            "durable": durable,
            "blank": blank,
            "env": {
                "SHADOW_PORTFOLIO_ROOT": str(durable),
                "SHADOW_VOLATILE_ROOTS": str(volatile.resolve()),
            },
        }

    def test_a_durable_sibling_takes_authority_from_the_temp_root_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._fixture(Path(tmp), with_sibling=True)
            out = run(f["home"], "status", "--json", cwd=f["blank"], extra_env=f["env"])
            self.assertEqual(out.returncode, 0, out.stderr)
            entities = board(f["home"])["entities"]
            self.assertEqual(len(entities), 1, "the project must not vanish")
            plan = Path(entities[0]["plan"]).resolve()
            self.assertTrue(
                str(plan).startswith(str(f["durable"].resolve())),
                f"authority stayed on volatile storage: {plan}",
            )

    def test_with_no_durable_sibling_the_temp_copy_keeps_working(self):
        """The half that makes this safe: a sandbox with only a temp checkout."""
        with tempfile.TemporaryDirectory() as tmp:
            f = self._fixture(Path(tmp), with_sibling=False)
            out = run(f["home"], "status", "--json", cwd=f["blank"], extra_env=f["env"])
            self.assertEqual(out.returncode, 0, out.stderr)
            entities = board(f["home"])["entities"]
            self.assertEqual(len(entities), 1, "nothing to repair to, so nothing changes")
            plan = Path(entities[0]["plan"]).resolve()
            self.assertEqual(plan, (f["registered"] / "PLAN.md").resolve())

    def test_a_sibling_under_the_same_swept_root_takes_nothing(self):
        """One temp path for another is not a repair, so the rule stays silent.

        This is also every `tempfile` fixture in this suite on a platform whose
        tempdir IS the shared temp root: on Linux the whole tree is swept, and
        a rule that fired there would demote a healthy locator for no gain.
        """
        with tempfile.TemporaryDirectory() as tmp:
            f = self._fixture(Path(tmp), with_sibling=True)
            env = dict(f["env"])
            # The whole fixture is swept, sibling included, exactly as CI sees
            # it when `tempfile` hands out paths under the shared temp root.
            env["SHADOW_VOLATILE_ROOTS"] = str(Path(tmp).resolve())
            out = run(f["home"], "status", "--json", cwd=f["blank"], extra_env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            entities = board(f["home"])["entities"]
            self.assertEqual(len(entities), 1, "the project must not vanish")
            self.assertEqual(
                Path(entities[0]["plan"]).resolve(),
                (f["registered"] / "PLAN.md").resolve(),
                "authority moved off a swept root onto an equally swept sibling",
            )

    def test_an_unreadable_durable_sibling_takes_nothing_and_refuses_nothing(self):
        """A repair target is held to the standard of the locator it replaces.

        The registered plan is healthy; only the durable copy is not. Demoting
        the locator first and discovering that afterwards is how a working
        board becomes `showing the last-good computer board` on a machine that
        had nothing wrong with its authority.
        """
        with tempfile.TemporaryDirectory() as tmp:
            f = self._fixture(Path(tmp), with_sibling=True)
            (f["durable"] / "shadow" / "PLAN.md").write_bytes(b"\xff\xfe not a plan")

            out = run(f["home"], "status", "--json", cwd=f["blank"], extra_env=f["env"])

            self.assertEqual(out.returncode, 0, out.stderr)
            entities = board(f["home"])["entities"]
            self.assertEqual(len(entities), 1, "the project must not vanish")
            self.assertEqual(
                Path(entities[0]["plan"]).resolve(),
                (f["registered"] / "PLAN.md").resolve(),
                "a healthy locator was given up for a plan the import refuses",
            )


class ElectionPrefersTheMostRecentlyCommittedCopy(unittest.TestCase):
    """The name match was a proxy for 'current'. Commit date measures it."""

    REMOTE = "git@example.invalid:team/widget.git"

    def _commit_at(self, repo: Path, message: str, when: str) -> None:
        env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        r = subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", message],
                           capture_output=True, text=True, env=env, check=False)
        if r.returncode:
            raise AssertionError(r.stderr)

    def _two_copies(self, root: Path, *, matching_is_older: bool):
        portfolio = root / "portfolio"
        portfolio.mkdir()
        # `widget` matches the origin repository name; `widget-authority` does not.
        matching = project(portfolio, name="widget", display_name="widget")
        git(matching, "remote", "add", "origin", self.REMOTE)
        other = project(portfolio, name="widget-authority", display_name="widget")
        git(other, "remote", "add", "origin", self.REMOTE)
        old, new = "2026-06-24T00:00:00+00:00", "2026-08-10T00:00:00+00:00"
        for repo, when in ((matching, old if matching_is_older else new),
                           (other, new if matching_is_older else old)):
            (repo / "PLAN.md").write_text(
                (repo / "PLAN.md").read_text(encoding="utf-8") + f"\n<!-- {when} -->\n",
                encoding="utf-8")
            git(repo, "add", "PLAN.md")
            self._commit_at(repo, "date the plan", when)
        return portfolio

    def _elected(self, portfolio: Path) -> str:
        from browser import server

        records = server.discover_plans(portfolio, fail_on_skipped=True)
        return records[0]["path"].split("/")[0]

    def test_a_newer_copy_beats_the_name_matching_stale_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio = self._two_copies(Path(tmp), matching_is_older=True)
            self.assertEqual(self._elected(portfolio), "widget-authority")

    def test_the_name_match_still_wins_when_it_is_also_the_newest(self):
        """The original rename-era case, unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            portfolio = self._two_copies(Path(tmp), matching_is_older=False)
            self.assertEqual(self._elected(portfolio), "widget")


class MissingUnclaimedAliasCleanup(unittest.TestCase):
    """Status-time cleanup may remove only missing, claimless migration debris."""

    def _module(self):
        module = fresh_board_module("shadow_missing_alias")
        return module

    def _seed(
        self,
        module,
        home: Path,
        *,
        source_exists: bool,
        source_claimed: bool,
        declared_source: bool = True,
        source_resume: str = "~aa11",
        destination_resume: str = "~aa11",
    ):
        root = home.parent
        source = root / "former-source" / "PLAN.md"
        if source_exists:
            source.parent.mkdir()
            source.write_text("# Former source\n", encoding="utf-8")
        destination = home / ".shadow" / "plans" / "ai-leo" / "PLAN.md"
        destination.parent.mkdir(parents=True)
        destination.write_text(
            "# Private authority\n\n"
            "- [pending] resume row ~aa11\n"
            "- [pending] later row ~bb22\n",
            encoding="utf-8",
        )
        # Only a stored id that reproduces from a declared local-only origin
        # proves the vanished locator aliases the private authority. An
        # undeclared id stands for an ordinary product entity that merely
        # shares this project and row id.
        source_id = (
            module.logical_entity_id("github.com/leojkwan/ai-leo", "PLAN.md")
            if declared_source
            else "1" * 64
        )
        destination_id = "2" * 64
        with module._transaction(home) as (board_root, board_path, payload):
            payload["revision"] = 7
            payload["projects"] = [{"id": "ai-leo", "priority": 1}]
            payload["entities"] = [
                {
                    "id": source_id,
                    "project": "ai-leo",
                    "plan": str(source),
                    "resume": source_resume,
                },
                {
                    "id": destination_id,
                    "project": "ai-leo",
                    "plan": str(destination),
                    "resume": destination_resume,
                },
            ]
            payload["claims"] = [
                {
                    "entity": source_id if source_claimed else destination_id,
                    "row": "~aa11",
                    "owner": "stable-seat",
                    "claimed_at": "2026-08-11T00:00:00Z",
                    "return_by": "2026-08-11T08:00:00Z",
                    "recovery": module.RECOVERY_ACTION,
                }
            ]
            module._validate(payload)
            module._write(board_path, payload)
            module._commit(board_root, "seed missing alias fixture")
        return source_id, destination_id

    def _discard(self, module, home: Path) -> int:
        return module.discard_missing_unclaimed_aliases(
            local_only={"github.com/leojkwan/ai-leo": "ai-leo"},
            home=home,
        )

    def test_never_discards_a_missing_entity_without_declared_alias_proof(self):
        """A shared project and row id are not evidence of an alias."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            module = self._module()
            source_id, destination_id = self._seed(
                module,
                home,
                source_exists=False,
                source_claimed=False,
                declared_source=False,
            )
            before = (home / ".shadow" / "board.json").read_bytes()

            self.assertEqual(self._discard(module, home), 0)

            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before)
            payload = module.snapshot(home=home)
            self.assertEqual(
                {entity["id"] for entity in payload["entities"]},
                {source_id, destination_id},
            )
            stale = next(
                entity for entity in payload["entities"] if entity["id"] == source_id
            )
            self.assertEqual(stale["resume"], "~aa11")

    def test_discards_only_missing_claimless_alias_and_preserves_live_claim_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            module = self._module()
            source_id, destination_id = self._seed(
                module, home, source_exists=False, source_claimed=False
            )

            self.assertEqual(self._discard(module, home), 1)

            payload = module.snapshot(home=home)
            self.assertEqual([entity["id"] for entity in payload["entities"]], [destination_id])
            self.assertNotIn(source_id, [claim["entity"] for claim in payload["claims"]])
            self.assertEqual(payload["claims"][0]["entity"], destination_id)
            self.assertEqual(payload["claims"][0]["owner"], "stable-seat")
            self.assertEqual(payload["entities"][0]["resume"], "~aa11")

    def test_discards_a_missing_alias_after_the_private_resume_moved_on(self):
        """A dead locator must retire even once the survivor advanced past it.

        Measured 2026-08-16: a ghost entity pointing at a deleted worktree kept
        a second project of the same name registered for days, refusing every
        lifecycle successor with "duplicate logical entity", purely because the
        surviving plan had moved to a later resume row. Reachability is the
        honest predicate; equality only holds inside a window where nothing
        progressed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            module = self._module()
            source_id, destination_id = self._seed(
                module,
                home,
                source_exists=False,
                source_claimed=False,
                destination_resume="~bb22",
            )

            self.assertEqual(self._discard(module, home), 1)

            payload = module.snapshot(home=home)
            self.assertEqual(
                [entity["id"] for entity in payload["entities"]], [destination_id]
            )
            self.assertEqual(payload["entities"][0]["resume"], "~bb22")
            self.assertNotIn(
                source_id, [claim["entity"] for claim in payload["claims"]]
            )

    def test_never_discards_an_alias_whose_resume_left_the_private_plan(self):
        """Reachability is the surviving predicate: no row, no discard."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            module = self._module()
            source_id, destination_id = self._seed(
                module,
                home,
                source_exists=False,
                source_claimed=False,
                source_resume="~cc33",
                destination_resume="~bb22",
            )
            before = (home / ".shadow" / "board.json").read_bytes()

            self.assertEqual(self._discard(module, home), 0)

            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before)
            payload = module.snapshot(home=home)
            self.assertEqual(
                {entity["id"] for entity in payload["entities"]},
                {source_id, destination_id},
            )

    def test_never_discards_a_present_source_or_a_source_that_owns_a_claim(self):
        for source_exists, source_claimed in ((True, False), (False, True)):
            with self.subTest(source_exists=source_exists, source_claimed=source_claimed):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    home = root / "home"
                    home.mkdir()
                    module = self._module()
                    source_id, destination_id = self._seed(
                        module,
                        home,
                        source_exists=source_exists,
                        source_claimed=source_claimed,
                    )
                    before = (home / ".shadow" / "board.json").read_bytes()

                    self.assertEqual(self._discard(module, home), 0)

                    self.assertEqual((home / ".shadow" / "board.json").read_bytes(), before)
                    payload = module.snapshot(home=home)
                    self.assertEqual(
                        {entity["id"] for entity in payload["entities"]},
                        {source_id, destination_id},
                    )

    def test_status_discards_the_stale_ai_leo_alias_without_recreating_or_rekeying_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            home.mkdir()
            portfolio.mkdir()
            source_repo = project(portfolio, name="ai-leo", display_name="ai-leo")
            source_plan = source_repo / "PLAN.md"
            source_plan.write_text(
                source_plan.read_text(encoding="utf-8").replace("~aa11", "~c001"),
                encoding="utf-8",
            )
            git(source_repo, "add", "PLAN.md")
            git(source_repo, "commit", "--quiet", "-m", "make private resume fixture")
            git(source_repo, "remote", "add", "origin", "git@github.com:leojkwan/ai-leo.git")
            module = self._module()
            source_id = module.entity_id(source_plan)
            private_plan = home / ".shadow" / "plans" / "ai-leo" / "PLAN.md"
            private_plan.parent.mkdir(parents=True)
            private_plan.write_bytes(source_plan.read_bytes())
            # Main issues private plans a `local-plan:` identity rather than a
            # Git one, and reconcile rekeys a stored id that disagrees. Seed
            # the canonical id so this test proves the alias repair, not that
            # unrelated rekeying.
            private_id = module.logical_entity_id(
                f"local-plan:{(home / '.shadow' / 'plans').resolve()}",
                "ai-leo/PLAN.md",
            )
            stale_source = root / "ai-leo-main" / "PLAN.md"
            with module._transaction(home) as (board_root, board_path, payload):
                payload["revision"] = 7
                payload["projects"] = [{"id": "ai-leo", "priority": 1}]
                payload["entities"] = [
                    {
                        "id": source_id,
                        "project": "ai-leo",
                        "plan": str(stale_source),
                        "resume": "~c001",
                    },
                    {
                        "id": private_id,
                        "project": "ai-leo",
                        "plan": str(private_plan),
                        "resume": "~c001",
                    },
                ]
                payload["claims"] = [
                    {
                        "entity": private_id,
                        "row": "~c001",
                        "owner": "stable-seat",
                        "claimed_at": "2026-08-11T00:00:00Z",
                        "return_by": "2099-08-11T08:00:00Z",
                        "recovery": module.RECOVERY_ACTION,
                    }
                ]
                module._validate(payload)
                module._write(board_path, payload)
                module._commit(board_root, "seed live private authority")
            before_claim = dict(board(home)["claims"][0])

            observed = run(
                home,
                "status",
                "--root",
                str(portfolio),
                "--in-flight",
                "--json",
                cwd=root,
            )

            self.assertEqual(observed.returncode, 0, observed.stderr)
            payload = board(home)
            self.assertNotIn(source_id, [entity["id"] for entity in payload["entities"]])
            private = next(entity for entity in payload["entities"] if entity["id"] == private_id)
            self.assertEqual(private["plan"], str(private_plan))
            self.assertEqual(private["resume"], "~c001")
            self.assertEqual(payload["claims"], [before_claim])


class BoundedDiscoveryNamesItsDuplicateSeeds(unittest.TestCase):
    """The duplicate-entity refusal must not fire on one plan seen twice.

    Measured 2026-08-18: every `shadow lifecycle --apply` printed
    `Successor: refused — bounded discovery returned a duplicate logical
    entity` on a board with 11 entities and zero duplicate ids. Mechanism:
    lifecycle reconciles with the PLAN'S OWN DIRECTORY as the discovery root,
    so the machine-local plan is discovered as a record; the records loop
    skips local-only plans by ORIGIN slug, but a board repo with no `origin`
    remote yields a `local-plan:` identity that is not in the allowlist, so
    the record survives — and `_local_operational_plans` then appends the
    same file as the explicit seed. One plan, two seeds, one identity.

    Two pins: the same-path double-seed reconciles instead of refusing, and
    a REAL duplicate's refusal names both seed paths so the next reader does
    not spend a day guessing.
    """

    def _amp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cw02_amp", Path(__file__).resolve().parent.parent / "scripts" / "shadow-amp.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("cw02_amp", module)
        spec.loader.exec_module(module)
        return module

    def test_a_local_plan_discovered_from_its_own_directory_is_one_seed(self) -> None:
        import shadow_board_import as imp
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            slug_dir = home / ".shadow" / "plans" / "shadow"
            slug_dir.mkdir(parents=True)
            plan = slug_dir / "PLAN.md"
            plan.write_text(
                "# P\n\n## Brief\n\n- Project: shadow\n- Mode: ship\n\n"
                "## Tasks\n\n### M\n- [pending] a ~aa11 | proof: cmd true\n"
                "- [pending] b ~bb22 (DoD) | proof: cmd true | needs: ~aa11\n",
                encoding="utf-8",
            )
            # The failing shape verbatim: discovery root IS the plan directory.
            result = imp.reconcile_portfolio(slug_dir, self._amp(), home=home)
            self.assertIsInstance(result, dict)

    def test_a_real_duplicate_refusal_names_both_seed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            (home / ".shadow").mkdir(parents=True)
            a = home / "a" / "PLAN.md"
            a.parent.mkdir(parents=True)
            a.write_text("# P\n", encoding="utf-8")
            seed = {
                "project": "demo",
                "priority": 3,
                "candidates": [],
                "rows": [],
                "expected_size": None,
                "expected_sha256": None,
            }
            # The SAME file seeded twice is the only honest way to one id:
            # different paths hash to different logical identities.
            with self.assertRaises(board_api.BoardError) as caught:
                board_api.reconcile(
                    [
                        {**seed, "plan": str(a)},
                        {**seed, "plan": str(a)},
                    ],
                    [],
                    home=home,
                )
            message = str(caught.exception)
            self.assertIn("duplicate logical entity", message)
            self.assertIn(str(a), message)


class ReleaseStateSpeaksTheOneGrammar(unittest.TestCase):
    def test_a_row_the_grammar_rejects_is_not_validated(self) -> None:
        # Before the delegation, a hand-rolled twin accepted any "| ..." tail:
        # release could validate a claim-return row that lint cannot see.
        text = (
            "# P\n\n## Tasks\n\n### M1 — live\n"
            "- [pending] t ~aa11 | notafield\n"
        )
        with self.assertRaisesRegex(board_api.BoardError, "claim return row is missing"):
            board_api._release_state(Path("plan.md"), "~aa11", "return", text=text)


class LocatorNeverRaises(unittest.TestCase):
    def test_a_transient_origin_read_degrades_to_the_digest_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp), name="repo")
            with mock.patch.object(
                board_api,
                "origin_of",
                side_effect=board_api.BoardError("identity unavailable"),
            ):
                locator = board_api.public_plan_locator(repo / "PLAN.md")
            self.assertTrue(locator.startswith("repo@"), locator)
            self.assertTrue(locator.endswith("/PLAN.md"), locator)


if __name__ == "__main__":
    unittest.main()
