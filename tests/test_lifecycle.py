"""Dry-run-first, provenance-safe hot-plan compaction."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.plan_tree_fixture import install_plan_tree


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-lifecycle.py"
CLI = ROOT / "bin" / "shadow"
LINT = ROOT / "scripts" / "shadow-lint.py"
SPEC = importlib.util.spec_from_file_location("shadow_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lifecycle
SPEC.loader.exec_module(lifecycle)


PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship

## Tasks

### Finished work
- [completed] first result exists ~aa11 | proof: cmd true
- [completed] finished result is accepted ~bb22 (DoD) | proof: cmd true | needs: ~aa11

### Next work
- [pending] next result starts ~cc33 | proof: cmd true | needs: ~bb22
- [pending] next result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~cc33

## Progress

- 2026-08-10T00:00:00Z ~aa11 PROOF true -> pass
  exact first-result detail remains attached
- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass
- 2026-08-10T00:02:00Z NOTE unrelated history remains live
"""


RETIREMENT_PLAN = """# Disposable retirement target

## Brief

- Project: disposable-retirement-target
- Mode: ship

## Tasks

### Finished work
- [completed] retirement source exists ~aa11 | proof: cmd true
- [completed] retirement source is accepted ~bb22 (DoD) | proof: cmd true | needs: ~aa11

## Progress

- 2026-08-10T00:00:00Z ~aa11 PROOF true -> pass
- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass
"""


def many_milestone_plan(completed: int = 33) -> str:
    milestones: list[str] = []
    receipts: list[str] = []
    for index in range(completed):
        first = f"~a{index:03d}"
        done = f"~b{index:03d}"
        milestones.append(
            f"### Finished {index}\n"
            f"- [completed] result {index} exists {first} | proof: cmd true\n"
            f"- [completed] result {index} is accepted {done} (DoD) | "
            f"proof: cmd true | needs: {first}\n"
        )
        receipts.extend(
            (
                f"- 2026-08-10T00:{index:02d}:00Z {first} PROOF true -> pass\n",
                f"- 2026-08-10T00:{index:02d}:01Z {done} PROOF true -> pass\n",
            )
        )
    milestones.append(
        "### Reachable successor\n"
        "- [pending] successor starts ~c001 | proof: cmd true\n"
        "- [pending] successor is accepted ~d001 (DoD) | "
        "proof: cmd true | needs: ~c001\n"
    )
    return (
        "# Demo\n\n"
        "## Brief\n\n"
        "- Project: demo\n"
        "- Mode: ship\n\n"
        "## Tasks\n\n"
        + "\n".join(milestones)
        + "\n## Progress\n\n"
        + "".join(receipts)
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_repo(root: Path, plan: str = PLAN) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Lifecycle Test")
    git(repo, "config", "user.email", "lifecycle@example.invalid")
    (repo / "PLAN.md").write_text(plan, encoding="utf-8")
    git(repo, "add", "PLAN.md")
    git(repo, "commit", "--quiet", "-m", "seed")
    return repo


def make_nested_repo(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    entity = repo / "entities" / "alpha"
    entity.mkdir(parents=True)
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Lifecycle Test")
    git(repo, "config", "user.email", "lifecycle@example.invalid")
    (entity / "PLAN.md").write_text(PLAN, encoding="utf-8")
    git(repo, "add", "entities/alpha/PLAN.md")
    git(repo, "commit", "--quiet", "-m", "seed nested entity")
    return repo, entity


def write_manifest(path: Path, payload: dict) -> str:
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    path.write_bytes(content)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def worktree_retirement_fixture(root: Path) -> dict:
    root = root.resolve(strict=True)
    repo = make_repo(root, RETIREMENT_PLAN)
    git(repo, "branch", "-M", "main")
    (repo / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "--quiet", "-m", "define ignored worktree state")
    target_head = git(repo, "rev-parse", "HEAD")
    target = root / "retired-worktree"
    target_branch = "refs/heads/retirement-candidate"
    git(repo, "branch", "retirement-candidate", target_head)
    git(repo, "worktree", "add", "--quiet", str(target), "retirement-candidate")
    (repo / "LANDED.txt").write_text("landed on main\n", encoding="utf-8")
    git(repo, "add", "LANDED.txt")
    git(repo, "commit", "--quiet", "-m", "land target on main")
    manifest = root / "worktree-retirement.json"
    digest = write_manifest(
        manifest,
        {
            "schema": "shadow.retirement.v1",
            "target": {
                "kind": "worktree",
                "path": str(target),
                "head": target_head,
                "landed_ref": "refs/heads/main",
            },
        },
    )
    return {
        "repo": repo,
        "target": target,
        "target_head": target_head,
        "target_branch": target_branch,
        "manifest": manifest,
        "digest": digest,
        "receipt": repo
        / "docs"
        / "plan-archive"
        / "retirements"
        / f"{digest}.json",
    }


def snapshot_retirement_fixture(
    root: Path,
    *,
    expires_at: str = "2000-01-01T00:00:00Z",
) -> dict:
    root = root.resolve(strict=True)
    repo = make_repo(root, RETIREMENT_PLAN)
    git(repo, "branch", "-M", "main")
    remote = "git@example.invalid:team/lifecycle-snapshot.git"
    git(repo, "remote", "add", "origin", remote)
    snapshot_root = root / "snapshots"
    snapshot_root.mkdir()
    name = "snapshot-a"
    target = snapshot_root / name
    cloned = subprocess.run(
        ["git", "clone", "--quiet", str(repo), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if cloned.returncode:
        raise AssertionError(cloned.stderr)
    git(target, "config", "user.name", "Lifecycle Test")
    git(target, "config", "user.email", "lifecycle@example.invalid")
    git(target, "remote", "set-url", "origin", remote)
    target_head = git(target, "rev-parse", "HEAD")
    entity = lifecycle._board.entity_id(repo / "PLAN.md")
    manifest = root / "snapshot-retirement.json"
    digest = write_manifest(
        manifest,
        {
            "schema": "shadow.retirement.v1",
            "target": {
                "kind": "snapshot",
                "root": str(snapshot_root),
                "name": name,
                "head": target_head,
                "entity": entity,
                "expires_at": expires_at,
                "recovery_ref": "refs/heads/main",
            },
        },
    )
    return {
        "repo": repo,
        "root": snapshot_root,
        "name": name,
        "target": target,
        "target_head": target_head,
        "entity": entity,
        "manifest": manifest,
        "digest": digest,
        "receipt": repo
        / "docs"
        / "plan-archive"
        / "retirements"
        / f"{digest}.json",
    }


def run(
    repo: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    # HOME defaults to a scratch directory beside the fixture repo, never the
    # operator's. A lifecycle verb that claims or registers (any --apply --by)
    # writes to $HOME/.shadow, so inheriting the real HOME wrote test-fixture
    # claims onto the operator's live board — measured twice on 2026-08-11,
    # both times corrupting the real board with temp-path entities. Tests that
    # need a specific HOME still pass one through extra_env.
    env = {**os.environ, **(extra_env or {})}
    if "HOME" not in (extra_env or {}):
        scratch = repo.parent / "test-home"
        scratch.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(scratch)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args, "--json"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, json.loads(result.stdout) if result.stdout.strip() else {}


def run_command(
    repo: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [str(CLI), "lifecycle", "--repo", str(repo), *args, "--json"],
        cwd=repo,
        env={**os.environ, **(extra_env or {})},
        capture_output=True,
        text=True,
        check=False,
    )
    return result, json.loads(result.stdout) if result.stdout.strip() else {}


def run_shadow(
    home: Path,
    *args: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args],
        cwd=cwd,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


def isolated_lifecycle_env(
    repo: Path,
    extra_env: dict[str, str] | None,
) -> dict[str, str]:
    env = dict(extra_env or {})
    if "HOME" not in env:
        repo_top = Path(git(repo, "rev-parse", "--show-toplevel"))
        home = repo_top.parent / ".lifecycle-test-home"
        home.mkdir(exist_ok=True)
        env["HOME"] = str(home)
    return env


def preview_cas(
    repo: Path,
    *args: str,
    command: bool = False,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, str]:
    runner = run_command if command else run
    env = isolated_lifecycle_env(repo, extra_env)
    result, report = runner(repo, *args, extra_env=env)
    if result.returncode:
        raise AssertionError((result.stderr, report))
    cas = report.get("cas")
    if not isinstance(cas, str) or not cas:
        raise AssertionError(f"dry run did not emit a CAS token: {report}")
    return result, report, cas


def apply_with_cas(
    repo: Path,
    *args: str,
    cas: str | None = None,
    by: str = "lifecycle-test-seat",
    command: bool = False,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, str]:
    runner = run_command if command else run
    env = isolated_lifecycle_env(repo, extra_env)
    if cas is None:
        _, _, cas = preview_cas(
            repo,
            *args,
            command=command,
            extra_env=env,
        )
    result, report = runner(
        repo,
        "--apply",
        "--expect",
        cas,
        "--by",
        by,
        *args,
        extra_env=env,
    )
    return result, report, cas


class ASharedReceiptStaysLiveInsteadOfBlockingTheArchive(unittest.TestCase):
    """A receipt naming BOTH an archiving row and a live one is live
    provenance: it must STAY in the hot plan, and the milestone must still
    archive. Refusing the whole archive made the byte ceiling unreachable —
    measured 2026-08-11 on Shadow's own plan, where all eight completed
    milestones refused for exactly this reason while the plan sat at its
    256 KiB limit with no legal way to shrink.
    """

    SHARED_PLAN = PLAN.replace(
        "- 2026-08-10T00:02:00Z NOTE unrelated history remains live\n",
        "- 2026-08-10T00:02:00Z NOTE ~bb22 groundwork is what ~cc33 builds on\n"
        "- 2026-08-10T00:03:00Z NOTE unrelated history remains live\n",
    )

    def test_the_milestone_archives_and_the_shared_receipt_stays(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root, self.SHARED_PLAN)
            _, preview = run(repo, "--milestone", "Finished work")
            self.assertEqual(preview.get("action"), "would_archive", preview)
            self.assertEqual(preview.get("shared_receipts_kept"), 1, preview)
            # Two exclusive receipts move; the shared one is kept back.
            self.assertEqual(preview.get("receipt_count"), 2, preview)
            applied = run(repo, "--milestone", "Finished work", "--apply",
                          "--expect", preview["cas"], "--by", "seat-a")[1]
            self.assertEqual(applied.get("action"), "archived", applied)
            live = (repo / "PLAN.md").read_text(encoding="utf-8")
            # The shared receipt stays where the live row can still read it.
            self.assertIn("~bb22 groundwork is what ~cc33 builds on", live)
            # The exclusive receipt left with the milestone.
            self.assertNotIn("~aa11 PROOF true -> pass", live)
            archive = (repo / "docs" / "plan-archive" / "finished-work.md").read_text(encoding="utf-8")
            self.assertIn("Receipts left in the live plan", archive)
            self.assertIn("~cc33", archive)

    def test_an_exclusive_only_milestone_still_moves_every_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root, PLAN)
            _, preview = run(repo, "--milestone", "Finished work")
            self.assertEqual(preview.get("action"), "would_archive", preview)
            self.assertEqual(preview.get("shared_receipts_kept"), 0, preview)
            applied = run(repo, "--milestone", "Finished work", "--apply",
                          "--expect", preview["cas"], "--by", "seat-a")[1]
            self.assertEqual(applied.get("action"), "archived", applied)
            archive = (repo / "docs" / "plan-archive" / "finished-work.md").read_text(encoding="utf-8")
            self.assertNotIn("Receipts left in the live plan", archive)


class TestsNeverWriteToTheOperatorsBoard(unittest.TestCase):
    """A lifecycle verb that claims or registers writes to $HOME/.shadow. If a
    test inherits the operator's real HOME, its fixture claims land on the
    operator's LIVE board — measured twice on 2026-08-11, both times leaving
    temp-path entities that made `shadow status` refuse to load. The helper
    must supply a scratch HOME by default so no future test can do it.
    """

    def test_the_helper_never_hands_a_verb_the_real_home(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            repo = make_repo(root)
            real_home = Path(os.environ["HOME"]).resolve()
            before = (real_home / ".shadow" / "board.json")
            stamp = before.read_bytes() if before.exists() else None
            preview = run(repo, "--milestone", "Finished work")[1]
            run(repo, "--milestone", "Finished work", "--apply",
                "--expect", preview["cas"], "--by", "leak-canary")
            after = before.read_bytes() if before.exists() else None
            self.assertEqual(after, stamp,
                             "a lifecycle test mutated the operator's real board")
            scratch_board = repo.parent / "test-home" / ".shadow"
            self.assertTrue(scratch_board.exists(),
                            "the verb did not write to the scratch HOME either — check the helper")


class ADuplicateRowIdCannotDefeatTheArchiveGuards(unittest.TestCase):
    """The shared-receipt guard and the dependency fold both key on row id.
    A duplicate id — the same `~xxxx` on an archiving row AND a live one —
    makes the archiving id its own alias: the receipt naming the live row
    reads as exclusive and moves out of the plan, and `fold_dependencies`
    strips a still-live `needs:` that points at the live twin. Uniqueness is
    asserted across the WHOLE plan before anything is archived.
    """

    # ~aa11 now names both an archiving row and a live one.
    DUPLICATE_PLAN = PLAN.replace(
        "- [pending] next result starts ~cc33 | proof: cmd true | needs: ~bb22\n"
        "- [pending] next result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~cc33\n",
        "- [pending] next result starts ~aa11 | proof: cmd true | needs: ~bb22\n"
        "- [pending] next result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~aa11\n",
    )

    def test_a_duplicate_id_refuses_the_archive_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname), self.DUPLICATE_PLAN)
            before = (repo / "PLAN.md").read_bytes()
            head = git(repo, "rev-parse", "HEAD")

            result, report = run(repo, "--milestone", "Finished work")

            self.assertEqual(result.returncode, 1, report)
            self.assertIn("duplicate", report["error"])
            self.assertIn("~aa11", report["error"])
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)

    def test_a_unique_plan_still_archives(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname), PLAN)
            _, preview = run(repo, "--milestone", "Finished work")
            self.assertEqual(preview.get("action"), "would_archive", preview)


class AnArchivedReceiptRangeStopsAtTheNextBullet(unittest.TestCase):
    """The last receipt in the Progress section owns its own continuation
    lines only. Trailing non-bullet prose after it belongs to the live plan,
    not to whichever milestone happens to archive next; running that range to
    EOF silently moved unrelated content into an archive file.
    """

    TRAILING_PLAN = PLAN.replace(
        "- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass\n"
        "- 2026-08-10T00:02:00Z NOTE unrelated history remains live\n",
        "- 2026-08-10T00:02:00Z NOTE unrelated history remains live\n"
        "- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass\n"
        "  exact accepted-result detail remains attached\n"
        "\n"
        "Receipts above are UTC; this closing note belongs to the live plan.\n",
    )

    def test_trailing_prose_after_the_last_receipt_stays_live(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname), self.TRAILING_PLAN)
            _, preview = run(repo, "--milestone", "Finished work")
            self.assertEqual(preview.get("action"), "would_archive", preview)
            applied = run(repo, "--milestone", "Finished work", "--apply",
                          "--expect", preview["cas"], "--by", "seat-a")[1]
            self.assertEqual(applied.get("action"), "archived", applied)

            live = (repo / "PLAN.md").read_text(encoding="utf-8")
            archive = (
                repo / "docs" / "plan-archive" / "finished-work.md"
            ).read_text(encoding="utf-8")
            self.assertIn("this closing note belongs to the live plan", live)
            self.assertNotIn("this closing note belongs to the live plan", archive)
            # The receipt itself, and its own indented continuation, still move.
            self.assertNotIn("~bb22 PROOF true -> pass", live)
            self.assertIn("exact accepted-result detail remains attached", archive)


class BudgetsAreEnforced(unittest.TestCase):
    def test_all_three_checked_in_limits_have_teeth(self) -> None:
        too_many_rows = "## Tasks\n\n### Too many tasks\n" + "\n".join(
            f"- [pending] result {index} ~aa11 | proof: cmd true"
            for index in range(lifecycle.MAX_TASK_ROWS + 1)
        )
        too_many_milestones = "\n".join(
            f"### milestone {index}" for index in range(lifecycle.MAX_MILESTONES + 1)
        )
        self.assertIn(
            "bytes",
            lifecycle.measure("x" * (lifecycle.MAX_PLAN_BYTES + 1))["exceeded"],
        )
        self.assertIn("task_rows", lifecycle.measure(too_many_rows)["exceeded"])
        outside_tasks = too_many_rows.replace("## Tasks", "## Legal history", 1)
        self.assertNotIn("task_rows", lifecycle.measure(outside_tasks)["exceeded"])
        structured = f"## Tasks\n\n{too_many_milestones}\n\n## Progress\n"
        self.assertIn("milestones", lifecycle.measure(structured)["exceeded"])

    def test_over_budget_dry_run_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            oversized = PLAN + "\n<!-- " + ("x" * lifecycle.MAX_PLAN_BYTES) + " -->\n"
            (repo / "PLAN.md").write_text(oversized, encoding="utf-8")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "oversized")
            before = (repo / "PLAN.md").read_bytes()
            head = git(repo, "rev-parse", "HEAD")

            result, report = run_command(repo)

            self.assertEqual(result.returncode, 1, report)
            self.assertIn("bytes", report["budget"]["before"]["exceeded"])
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)


class LifecycleApplyCasIsMandatory(unittest.TestCase):
    def _snapshot(self, repo: Path) -> tuple[bytes, str, str]:
        return (
            (repo / "PLAN.md").read_bytes(),
            git(repo, "rev-parse", "HEAD"),
            git(repo, "status", "--porcelain=v2", "--untracked-files=all"),
        )

    def _assert_unchanged(self, repo: Path, expected: tuple[bytes, str, str]) -> None:
        self.assertEqual(self._snapshot(repo), expected)
        self.assertFalse((repo / "docs" / "plan-archive").exists())

    def test_apply_requires_both_dry_run_cas_and_seat(self) -> None:
        for missing in ("expect", "by"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as dirname:
                repo = make_repo(Path(dirname))
                env = isolated_lifecycle_env(repo, None)
                _, _, cas = preview_cas(
                    repo,
                    "--milestone",
                    "Finished work",
                    extra_env=env,
                )
                self.assertRegex(cas, r"^[0-9a-f]{64}$")
                args = ["--apply", "--milestone", "Finished work"]
                if missing != "expect":
                    args.extend(("--expect", cas))
                if missing != "by":
                    args.extend(("--by", "cas-test-seat"))
                before = self._snapshot(repo)

                result, report = run(repo, *args, extra_env=env)

                self.assertEqual(result.returncode, 1, (result.stderr, report))
                self.assertEqual(report["action"], "refused")
                self.assertRegex(
                    json.dumps(report).lower(),
                    r"expect|cas|dry.run|--by|seat",
                )
                self._assert_unchanged(repo, before)

    def test_committed_plan_change_makes_preview_cas_stale_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            env = isolated_lifecycle_env(repo, None)
            _, _, cas = preview_cas(
                repo,
                "--milestone",
                "Finished work",
                extra_env=env,
            )
            with (repo / "PLAN.md").open("a", encoding="utf-8") as stream:
                stream.write("\n- 2026-08-10T00:03:00Z NOTE changed after preview\n")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "change plan after lifecycle preview")
            before = self._snapshot(repo)

            result, report = run(
                repo,
                "--apply",
                "--milestone",
                "Finished work",
                "--expect",
                cas,
                "--by",
                "cas-test-seat",
                extra_env=env,
            )

            self.assertEqual(result.returncode, 1, (result.stderr, report))
            self.assertEqual(report["action"], "refused")
            self.assertRegex(json.dumps(report).lower(), r"expect|cas|stale|changed")
            self._assert_unchanged(repo, before)


class RetirementManifestSchemaMatchesRuntime(unittest.TestCase):
    def test_paths_names_and_expiry_match_the_runtime_parser(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "retirement-manifest.v1.json").read_text(
                encoding="utf-8"
            )
        )
        worktree, snapshot = schema["properties"]["target"]["oneOf"]
        path_pattern = worktree["properties"]["path"]["pattern"]
        root_pattern = snapshot["properties"]["root"]["pattern"]
        name_pattern = snapshot["properties"]["name"]["pattern"]
        expiry_pattern = snapshot["properties"]["expires_at"]["pattern"]

        self.assertIsNotNone(re.search(path_pattern, "/tmp/worktree"))
        self.assertIsNone(re.search(path_pattern, "relative/worktree"))
        self.assertIsNotNone(re.search(root_pattern, "/tmp/snapshots"))
        self.assertIsNotNone(re.fullmatch(name_pattern, ".snapshot"))
        self.assertIsNone(re.fullmatch(name_pattern, "."))
        self.assertIsNone(re.fullmatch(name_pattern, ".."))
        self.assertIsNone(re.fullmatch(name_pattern, "nested/snapshot"))
        self.assertIsNotNone(
            re.fullmatch(expiry_pattern, "2026-08-10T12:34:56.123Z")
        )
        self.assertIsNone(
            re.fullmatch(expiry_pattern, "2026-08-10T12:34:56-04:00")
        )


class AtomicWritesAreDurable(unittest.TestCase):
    def test_lifecycle_fsyncs_the_final_mode_before_replacing(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            destination = Path(dirname) / "archive.md"
            observed: list[tuple[str, int]] = []
            real_fchmod = os.fchmod
            real_fsync = os.fsync

            def fchmod(fd: int, mode: int) -> None:
                observed.append(("fchmod", mode))
                real_fchmod(fd, mode)

            def fsync(fd: int) -> None:
                observed.append(("fsync", stat.S_IMODE(os.fstat(fd).st_mode)))
                real_fsync(fd)

            with (
                mock.patch.object(lifecycle.os, "fchmod", side_effect=fchmod),
                mock.patch.object(lifecycle.os, "fsync", side_effect=fsync),
            ):
                lifecycle.atomic_write(destination, b"archive\n", 0o640)
        self.assertLess(
            next(index for index, item in enumerate(observed) if item[0] == "fchmod"),
            next(index for index, item in enumerate(observed) if item == ("fsync", 0o640)),
        )


class CleanupIsDryRunFirstAndIdempotent(unittest.TestCase):
    def test_apply_commits_a_partitioned_plan_root_objects_and_archive_together(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            source = (repo / "PLAN.md").read_bytes()
            install_plan_tree(repo, source)
            git(repo, "add", "PLAN.md", "PLAN.d")
            git(repo, "commit", "--quiet", "-m", "partition plan")
            before_head = git(repo, "rev-parse", "HEAD")

            _, preview, cas = preview_cas(repo, "--milestone", "Finished work")
            result, report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "archived")
            self.assertNotEqual(git(repo, "rev-parse", "HEAD"), before_head)
            self.assertEqual(git(repo, "status", "--porcelain=v1"), "")
            self.assertTrue(lifecycle._board.open_plan(repo / "PLAN.md").is_tree)
            logical = lifecycle._board.read_plan_text(repo / "PLAN.md")
            self.assertIn("shadow:lifecycle:finished-work", logical)
            self.assertNotIn("first result exists ~aa11", logical)
            changed = set(
                git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines()
            )
            self.assertIn("PLAN.md", changed)
            self.assertIn("docs/plan-archive/finished-work.md", changed)
            self.assertTrue(any(path.startswith("PLAN.d/objects/sha256/") for path in changed))

    def test_exact_cas_recovers_each_atomic_archive_half_state(self) -> None:
        for crash_after in (1, 2):
            with (
                self.subTest(crash_after=crash_after),
                tempfile.TemporaryDirectory() as dirname,
            ):
                root = Path(dirname)
                home = root / "home"
                home.mkdir()
                repo = make_repo(root)
                with mock.patch.dict(os.environ, {"HOME": str(home)}):
                    preview, _ = lifecycle.inspect(repo, "Finished work")
                    cas = preview["cas"]
                    original_atomic_write = lifecycle.atomic_write
                    calls = 0

                    def crash_after_replace(path: Path, payload: bytes, mode: int = 0o644) -> None:
                        nonlocal calls
                        original_atomic_write(path, payload, mode)
                        calls += 1
                        if calls == crash_after:
                            raise SystemExit("simulated lifecycle crash")

                    with (
                        mock.patch.object(
                            lifecycle,
                            "atomic_write",
                            side_effect=crash_after_replace,
                        ),
                        self.assertRaisesRegex(SystemExit, "simulated lifecycle crash"),
                    ):
                        lifecycle.apply(
                            repo,
                            "Finished work",
                            expected=cas,
                            owner="recovery-seat",
                        )

                result, report = run(
                    repo,
                    "--apply",
                    "--expect",
                    cas,
                    "--by",
                    "recovery-seat",
                    "--milestone",
                    "Finished work",
                    extra_env={"HOME": str(home)},
                )

                self.assertEqual(result.returncode, 0, (result.stderr, report))
                self.assertEqual(report["action"], "archived")
                self.assertTrue(report["changed"])
                self.assertEqual(git(repo, "rev-list", "--count", "HEAD^..HEAD"), "1")
                self.assertEqual(git(repo, "status", "--porcelain=v1"), "")
                self.assertTrue(
                    (repo / "docs" / "plan-archive" / "finished-work.md").is_file()
                )

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            before = (repo / "PLAN.md").read_bytes()
            head = git(repo, "rev-parse", "HEAD")

            result, report = run(repo, "--milestone", "Finished work")

            self.assertEqual(result.returncode, 0, report)
            self.assertEqual(report["action"], "would_archive")
            self.assertFalse(report["changed"])
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertFalse((repo / "docs" / "plan-archive").exists())
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head)

    def test_apply_preserves_receipts_commits_once_and_repeats_as_noop(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            original = (repo / "PLAN.md").read_text(encoding="utf-8")
            block = original[
                original.index("### Finished work") : original.index("### Next work")
            ]
            hook = repo / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\nexit 91\n", encoding="utf-8")
            hook.chmod(0o755)
            before_head = git(repo, "rev-parse", "HEAD")
            trace = Path(dirname) / "lifecycle-git-trace.json"

            _, preview, cas = preview_cas(
                repo,
                "--milestone",
                "Finished work",
            )
            self.assertEqual(preview["action"], "would_archive")
            result, report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
                extra_env={"GIT_TRACE2_EVENT": str(trace)},
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "archived")
            self.assertTrue(report["changed"])
            self.assertNotEqual(report["commit"], before_head)
            self.assertEqual(git(repo, "rev-list", "--count", f"{before_head}..HEAD"), "1")
            changed = set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines())
            self.assertEqual(changed, {"PLAN.md", "docs/plan-archive/finished-work.md"})

            plan = (repo / "PLAN.md").read_text(encoding="utf-8")
            archive = (repo / "docs" / "plan-archive" / "finished-work.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(block, archive)
            self.assertIn("~aa11 PROOF true -> pass\n  exact first-result detail", archive)
            self.assertNotIn("~aa11", plan)
            self.assertNotIn("~bb22", plan)
            self.assertIn("shadow:lifecycle:finished-work", plan)
            self.assertIn("unrelated history remains live", plan)
            self.assertNotIn("needs: ~bb22", plan)
            self.assertIn(
                "STRUCT archived milestone finished-work | successor: Next work",
                plan,
            )
            self.assertEqual(report["successor"], "Next work")
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            commit_argv = next(
                event["argv"]
                for event in events
                if event.get("event") == "start"
                and "shadow: archive milestone finished-work" in event.get("argv", [])
            )
            commit_index = commit_argv.index("commit")
            self.assertLess(commit_argv.index("maintenance.autoDetach=false"), commit_index)
            self.assertLess(commit_argv.index("gc.autoDetach=false"), commit_index)
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
            lint = subprocess.run(
                [sys.executable, str(LINT), str(repo / "PLAN.md")],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

            archived_head = git(repo, "rev-parse", "HEAD")
            repeated, repeated_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
            )
            self.assertEqual(repeated.returncode, 0, repeated_report)
            self.assertEqual(repeated_report["action"], "already_archived")
            self.assertFalse(repeated_report["changed"])
            self.assertEqual(git(repo, "rev-parse", "HEAD"), archived_head)

    def test_dispatcher_documents_and_runs_the_dry_run(self) -> None:
        help_result = subprocess.run(
            [str(CLI), "help", "lifecycle"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--apply --repo PATH", help_result.stdout)
        self.assertIn("canonical absolute", help_result.stdout)

    def test_nested_entity_archives_adjacent_and_commits_only_its_two_paths(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo, entity = make_nested_repo(Path(dirname))
            before_head = git(repo, "rev-parse", "HEAD")

            result, report, cas = apply_with_cas(
                entity,
                "--milestone",
                "Finished work",
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            expected_archive = entity / "docs" / "plan-archive" / "finished-work.md"
            self.assertEqual(Path(report["plan"]).resolve(), (entity / "PLAN.md").resolve())
            self.assertEqual(Path(report["archive"]).resolve(), expected_archive.resolve())
            changed = set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines())
            self.assertEqual(
                changed,
                {
                    "entities/alpha/PLAN.md",
                    "entities/alpha/docs/plan-archive/finished-work.md",
                },
            )
            self.assertEqual(git(repo, "rev-list", "--count", f"{before_head}..HEAD"), "1")
            plan = (entity / "PLAN.md").read_text(encoding="utf-8")
            link = re.search(r"\[finished-work\]\(([^)]+)\)", plan)
            self.assertIsNotNone(link)
            self.assertEqual((entity / link.group(1)).resolve(), expected_archive.resolve())
            self.assertTrue(expected_archive.is_file())

            archived_head = git(repo, "rev-parse", "HEAD")
            repeated, repeated_report, _ = apply_with_cas(
                entity,
                "--milestone",
                "Finished work",
                cas=cas,
            )
            self.assertEqual(repeated.returncode, 0, repeated_report)
            self.assertEqual(repeated_report["action"], "already_archived")
            self.assertEqual(git(repo, "rev-parse", "HEAD"), archived_head)

    def test_over_budget_plan_compacts_across_monotonic_committed_passes(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo = make_repo(root)
            seeded = run_shadow(home, "status", "--root", str(repo), "--json", cwd=repo)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            (repo / "PLAN.md").write_text(many_milestone_plan(), encoding="utf-8")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "seed over-budget lifecycle plan")
            initial_head = git(repo, "rev-parse", "HEAD")
            lifecycle_env = {"HOME": str(home)}

            first, first_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished 0",
                by="compactor-seat",
                extra_env=lifecycle_env,
            )

            self.assertEqual(first.returncode, 0, (first.stderr, first_report))
            self.assertEqual(first_report["action"], "archived")
            self.assertGreater(
                first_report["budget"]["before"]["milestones"],
                first_report["budget"]["after"]["milestones"],
            )
            self.assertFalse(first_report["budget"]["after"]["within_limits"])
            first_head = git(repo, "rev-parse", "HEAD")
            self.assertNotEqual(first_head, initial_head)
            self.assertEqual(
                json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))[
                    "claims"
                ],
                [],
            )

            second, second_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished 1",
                by="compactor-seat",
                extra_env=lifecycle_env,
            )

            self.assertEqual(second.returncode, 0, (second.stderr, second_report))
            self.assertEqual(second_report["action"], "archived")
            self.assertEqual(
                second_report["budget"]["before"],
                first_report["budget"]["after"],
            )
            self.assertGreater(
                second_report["budget"]["before"]["milestones"],
                second_report["budget"]["after"]["milestones"],
            )
            self.assertTrue(second_report["budget"]["after"]["within_limits"])
            self.assertNotEqual(git(repo, "rev-parse", "HEAD"), first_head)
            board_payload = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [(claim["row"], claim["owner"]) for claim in board_payload["claims"]],
                [("~c001", "compactor-seat")],
            )


class ManifestedWorktreeRetirement(unittest.TestCase):
    def _assert_refused(
        self,
        result: subprocess.CompletedProcess[str],
        report: dict,
    ) -> None:
        self.assertEqual(result.returncode, 1, (result.stderr, report))
        self.assertEqual(report["action"], "refused")
        self.assertFalse(report["changed"])

    def _assert_public_receipt(self, fixture: dict, *, ref: str) -> bytes:
        receipt = fixture["receipt"]
        content = receipt.read_bytes()
        payload = json.loads(content)
        self.assertEqual(
            set(payload),
            {
                "schema",
                "kind",
                "target_hash",
                "head",
                "ref",
                "successor_row",
                "retired_at",
            },
        )
        self.assertEqual(payload["schema"], "shadow.retirement-receipt.v1")
        self.assertEqual(payload["kind"], "worktree")
        self.assertRegex(payload["target_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(payload["head"], fixture["target_head"])
        self.assertEqual(payload["ref"], ref)
        self.assertIsNone(payload["successor_row"])
        self.assertRegex(payload["retired_at"], r"^\d{4}-\d{2}-\d{2}T.*Z$")
        public_bytes = content.decode("utf-8")
        for secret in (
            str(fixture["target"]),
            str(fixture["manifest"]),
            str(fixture["target"].parent),
        ):
            self.assertNotIn(secret, public_bytes)
        return content

    def test_dry_run_apply_and_exact_completed_rerun_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            fixture = worktree_retirement_fixture(Path(dirname))
            repo = fixture["repo"]
            target = fixture["target"]
            env = isolated_lifecycle_env(repo, None)
            authority_head = git(repo, "rev-parse", "HEAD")
            plan_bytes = (repo / "PLAN.md").read_bytes()
            branch_head = git(repo, "rev-parse", fixture["target_branch"])
            worktrees_before = git(repo, "worktree", "list", "--porcelain")

            dry, dry_report, cas = preview_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                extra_env=env,
            )

            self.assertEqual(dry.returncode, 0, (dry.stderr, dry_report))
            self.assertEqual(dry_report["action"], "would_retire")
            self.assertFalse(dry_report["changed"])
            self.assertTrue(target.is_dir())
            self.assertFalse(fixture["receipt"].exists())
            self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
            self.assertEqual(git(repo, "worktree", "list", "--porcelain"), worktrees_before)

            applied, report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="retirement-seat",
                extra_env=env,
            )

            self.assertEqual(applied.returncode, 0, (applied.stderr, report))
            self.assertEqual(report["action"], "retired")
            self.assertTrue(report["changed"])
            self.assertFalse(target.exists())
            self.assertTrue(repo.is_dir())
            self.assertEqual((repo / "PLAN.md").read_bytes(), plan_bytes)
            self.assertEqual(
                git(repo, "rev-parse", fixture["target_branch"]),
                branch_head,
            )
            self.assertNotIn(str(target), git(repo, "worktree", "list", "--porcelain"))
            self.assertEqual(git(repo, "rev-list", "--count", f"{authority_head}..HEAD"), "1")
            receipt_relative = fixture["receipt"].relative_to(repo).as_posix()
            self.assertEqual(
                set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines()),
                {receipt_relative},
            )
            receipt_bytes = self._assert_public_receipt(
                fixture,
                ref="refs/heads/main",
            )
            self.assertIsNone(report.get("successor"))
            retired_head = git(repo, "rev-parse", "HEAD")

            repeated, repeated_report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="retirement-seat",
                extra_env=env,
            )

            self.assertEqual(
                repeated.returncode,
                0,
                (repeated.stderr, repeated_report),
            )
            self.assertEqual(repeated_report["action"], "already_retired")
            self.assertFalse(repeated_report["changed"])
            self.assertEqual(git(repo, "rev-parse", "HEAD"), retired_head)
            self.assertEqual(fixture["receipt"].read_bytes(), receipt_bytes)

    def test_revalidation_refuses_tracked_staged_untracked_and_ignored_dirt(self) -> None:
        for dirty_kind in ("tracked", "staged", "untracked", "ignored"):
            with (
                self.subTest(dirty_kind=dirty_kind),
                tempfile.TemporaryDirectory() as dirname,
            ):
                fixture = worktree_retirement_fixture(Path(dirname))
                repo = fixture["repo"]
                target = fixture["target"]
                env = isolated_lifecycle_env(repo, None)
                _, _, cas = preview_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=env,
                )
                if dirty_kind == "tracked":
                    with (target / "PLAN.md").open("a", encoding="utf-8") as stream:
                        stream.write("\ndirty after preview\n")
                    dirty_path = target / "PLAN.md"
                elif dirty_kind == "staged":
                    dirty_path = target / "staged.txt"
                    dirty_path.write_text("staged after preview\n", encoding="utf-8")
                    git(target, "add", "staged.txt")
                elif dirty_kind == "untracked":
                    dirty_path = target / "untracked.txt"
                    dirty_path.write_text("untracked after preview\n", encoding="utf-8")
                else:
                    dirty_path = target / "ignored.tmp"
                    dirty_path.write_text("ignored after preview\n", encoding="utf-8")
                dirty_bytes = dirty_path.read_bytes()
                authority_head = git(repo, "rev-parse", "HEAD")
                worktrees_before = git(repo, "worktree", "list", "--porcelain")

                result, report, _ = apply_with_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    cas=cas,
                    by="retirement-seat",
                    extra_env=env,
                )

                self._assert_refused(result, report)
                self.assertTrue(target.is_dir())
                self.assertEqual(dirty_path.read_bytes(), dirty_bytes)
                self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
                self.assertEqual(
                    git(repo, "worktree", "list", "--porcelain"),
                    worktrees_before,
                )
                self.assertFalse(fixture["receipt"].exists())

    def test_unmerged_target_created_after_preview_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve(strict=True)
            repo = make_repo(root, RETIREMENT_PLAN)
            git(repo, "branch", "-M", "main")
            (repo / "conflict.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", "conflict.txt")
            git(repo, "commit", "--quiet", "-m", "seed conflict")
            base = git(repo, "rev-parse", "HEAD")
            target = root / "unmerged-worktree"
            git(repo, "branch", "retirement-candidate", base)
            git(repo, "worktree", "add", "--quiet", str(target), "retirement-candidate")
            (target / "conflict.txt").write_text("target\n", encoding="utf-8")
            git(target, "add", "conflict.txt")
            git(target, "commit", "--quiet", "-m", "target conflict side")
            target_head = git(target, "rev-parse", "HEAD")
            (repo / "conflict.txt").write_text("landed\n", encoding="utf-8")
            git(repo, "add", "conflict.txt")
            git(repo, "commit", "--quiet", "-m", "landed conflict side")
            landed_side = git(repo, "rev-parse", "HEAD")
            merge = subprocess.run(
                ["git", "-C", str(repo), "merge", "--no-edit", target_head],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(merge.returncode, 0)
            (repo / "conflict.txt").write_text("resolved\n", encoding="utf-8")
            git(repo, "add", "conflict.txt")
            git(repo, "commit", "--quiet", "-m", "merge retirement target")
            manifest = root / "unmerged-retirement.json"
            digest = write_manifest(
                manifest,
                {
                    "schema": "shadow.retirement.v1",
                    "target": {
                        "kind": "worktree",
                        "path": str(target),
                        "head": target_head,
                        "landed_ref": "refs/heads/main",
                    },
                },
            )
            receipt = (
                repo
                / "docs"
                / "plan-archive"
                / "retirements"
                / f"{digest}.json"
            )
            env = isolated_lifecycle_env(repo, None)
            _, _, cas = preview_cas(
                repo,
                "--retirement-manifest",
                str(manifest),
                extra_env=env,
            )
            target_merge = subprocess.run(
                ["git", "-C", str(target), "merge", "--no-edit", landed_side],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(target_merge.returncode, 0)
            self.assertIn("u UU", git(target, "status", "--porcelain=v2"))
            authority_head = git(repo, "rev-parse", "HEAD")

            result, report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(manifest),
                cas=cas,
                by="retirement-seat",
                extra_env=env,
            )

            self._assert_refused(result, report)
            self.assertTrue(target.is_dir())
            self.assertIn("u UU", git(target, "status", "--porcelain=v2"))
            self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
            self.assertFalse(receipt.exists())

    def test_initialized_submodule_worktree_is_refused_before_any_journal(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve(strict=True)
            component_parent = root / "component-parent"
            component_parent.mkdir()
            component = make_repo(component_parent, RETIREMENT_PLAN)
            repo = make_repo(root, RETIREMENT_PLAN)
            git(repo, "branch", "-M", "main")
            added = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    "--quiet",
                    str(component),
                    "modules/component",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            git(repo, "commit", "--quiet", "-am", "add component")
            target_head = git(repo, "rev-parse", "HEAD")
            target = root / "submodule-worktree"
            git(repo, "branch", "retirement-candidate", target_head)
            git(repo, "worktree", "add", "--quiet", str(target), "retirement-candidate")
            initialized = subprocess.run(
                [
                    "git",
                    "-C",
                    str(target),
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "update",
                    "--init",
                    "--recursive",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            (repo / "LANDED.txt").write_text("landed\n", encoding="utf-8")
            git(repo, "add", "LANDED.txt")
            git(repo, "commit", "--quiet", "-m", "land submodule target")
            manifest = root / "submodule-retirement.json"
            digest = write_manifest(
                manifest,
                {
                    "schema": "shadow.retirement.v1",
                    "target": {
                        "kind": "worktree",
                        "path": str(target),
                        "head": target_head,
                        "landed_ref": "refs/heads/main",
                    },
                },
            )
            receipt = (
                repo
                / "docs"
                / "plan-archive"
                / "retirements"
                / f"{digest}.json"
            )
            env = isolated_lifecycle_env(repo, None)
            authority_head = git(repo, "rev-parse", "HEAD")

            result, report = run(
                repo,
                "--retirement-manifest",
                str(manifest),
                extra_env=env,
            )

            self._assert_refused(result, report)
            self.assertIn("submodule", report["error"])
            self.assertTrue(target.is_dir())
            self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
            self.assertFalse(receipt.exists())
            self.assertFalse(
                (Path(env["HOME"]) / ".shadow" / "retirements").exists()
            )

    def test_strict_schema_rejects_unknown_top_and_target_keys(self) -> None:
        for unknown_at in ("top", "target"):
            with (
                self.subTest(unknown_at=unknown_at),
                tempfile.TemporaryDirectory() as dirname,
            ):
                fixture = worktree_retirement_fixture(Path(dirname))
                payload = json.loads(fixture["manifest"].read_text(encoding="utf-8"))
                if unknown_at == "top":
                    payload["unexpected"] = True
                else:
                    payload["target"]["unexpected"] = True
                write_manifest(fixture["manifest"], payload)
                authority_head = git(fixture["repo"], "rev-parse", "HEAD")

                result, report = run(
                    fixture["repo"],
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=isolated_lifecycle_env(fixture["repo"], None),
                )

                self._assert_refused(result, report)
                self.assertTrue(fixture["target"].is_dir())
                self.assertEqual(git(fixture["repo"], "rev-parse", "HEAD"), authority_head)
                self.assertFalse(
                    (fixture["repo"] / "docs" / "plan-archive" / "retirements").exists()
                )

    def test_primary_unregistered_symlink_and_unlanded_targets_are_refused(self) -> None:
        for provenance in ("primary", "unregistered", "symlink", "unlanded"):
            with (
                self.subTest(provenance=provenance),
                tempfile.TemporaryDirectory() as dirname,
            ):
                root = Path(dirname).resolve(strict=True)
                fixture = worktree_retirement_fixture(root)
                repo = fixture["repo"]
                payload = json.loads(fixture["manifest"].read_text(encoding="utf-8"))
                protected: Path
                if provenance == "primary":
                    protected = repo
                    payload["target"]["path"] = str(repo)
                    payload["target"]["head"] = git(repo, "rev-parse", "HEAD")
                elif provenance == "unregistered":
                    protected = root / "independent-clone"
                    cloned = subprocess.run(
                        ["git", "clone", "--quiet", str(repo), str(protected)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(cloned.returncode, 0, cloned.stderr)
                    payload["target"]["path"] = str(protected)
                    payload["target"]["head"] = git(protected, "rev-parse", "HEAD")
                elif provenance == "symlink":
                    protected = fixture["target"]
                    alias = root / "worktree-alias"
                    os.symlink(protected, alias, target_is_directory=True)
                    payload["target"]["path"] = str(alias)
                else:
                    protected = fixture["target"]
                    (protected / "UNLANDED.txt").write_text("unique\n", encoding="utf-8")
                    git(protected, "add", "UNLANDED.txt")
                    git(protected, "commit", "--quiet", "-m", "unlanded target head")
                    payload["target"]["head"] = git(protected, "rev-parse", "HEAD")
                write_manifest(fixture["manifest"], payload)
                authority_head = git(repo, "rev-parse", "HEAD")

                result, report = run(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=isolated_lifecycle_env(repo, None),
                )

                self._assert_refused(result, report)
                self.assertTrue(protected.exists())
                self.assertTrue(repo.exists())
                self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
                self.assertFalse(
                    (repo / "docs" / "plan-archive" / "retirements").exists()
                )

    def test_linked_authority_cannot_retire_the_shared_stores_primary_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve(strict=True)
            primary = make_repo(root, RETIREMENT_PLAN)
            git(primary, "branch", "authority-seat")
            authority = root / "authority-worktree"
            git(primary, "worktree", "add", "--quiet", str(authority), "authority-seat")
            head = git(primary, "rev-parse", "HEAD")
            manifest = root / "primary-retirement.json"
            digest = write_manifest(
                manifest,
                {
                    "schema": "shadow.retirement.v1",
                    "target": {
                        "kind": "worktree",
                        "path": str(primary),
                        "head": head,
                        "landed_ref": "refs/heads/authority-seat",
                    },
                },
            )
            env = isolated_lifecycle_env(authority, None)

            result, report = run(
                authority,
                "--retirement-manifest",
                str(manifest),
                extra_env=env,
            )

            self._assert_refused(result, report)
            self.assertIn("primary worktree", report["error"])
            self.assertTrue(primary.is_dir())
            self.assertEqual(git(primary, "rev-parse", "HEAD"), head)
            self.assertFalse(
                (authority / "docs" / "plan-archive" / "retirements" / f"{digest}.json").exists()
            )
            self.assertFalse(
                (Path(env["HOME"]) / ".shadow" / "retirements").exists()
            )

    def test_manifest_or_target_change_after_preview_refuses_without_mutation(self) -> None:
        for changed in ("manifest", "target_head"):
            with (
                self.subTest(changed=changed),
                tempfile.TemporaryDirectory() as dirname,
            ):
                fixture = worktree_retirement_fixture(Path(dirname))
                repo = fixture["repo"]
                env = isolated_lifecycle_env(repo, None)
                if changed == "manifest":
                    git(repo, "branch", "landed-alias", "refs/heads/main")
                _, _, cas = preview_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=env,
                )
                if changed == "manifest":
                    payload = json.loads(
                        fixture["manifest"].read_text(encoding="utf-8")
                    )
                    payload["target"]["landed_ref"] = "refs/heads/landed-alias"
                    write_manifest(fixture["manifest"], payload)
                else:
                    (fixture["target"] / "AFTER_PREVIEW.txt").write_text(
                        "changed\n",
                        encoding="utf-8",
                    )
                    git(fixture["target"], "add", "AFTER_PREVIEW.txt")
                    git(
                        fixture["target"],
                        "commit",
                        "--quiet",
                        "-m",
                        "advance target after preview",
                    )
                target_head_after = git(fixture["target"], "rev-parse", "HEAD")
                authority_head = git(repo, "rev-parse", "HEAD")
                worktrees_before = git(repo, "worktree", "list", "--porcelain")

                result, report, _ = apply_with_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    cas=cas,
                    by="retirement-seat",
                    extra_env=env,
                )

                self._assert_refused(result, report)
                self.assertTrue(fixture["target"].is_dir())
                self.assertEqual(
                    git(fixture["target"], "rev-parse", "HEAD"),
                    target_head_after,
                )
                self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
                self.assertEqual(
                    git(repo, "worktree", "list", "--porcelain"),
                    worktrees_before,
                )
                self.assertFalse(
                    (repo / "docs" / "plan-archive" / "retirements").exists()
                )


class ManifestedSnapshotRetirement(unittest.TestCase):
    def _assert_refused(
        self,
        result: subprocess.CompletedProcess[str],
        report: dict,
    ) -> None:
        self.assertEqual(result.returncode, 1, (result.stderr, report))
        self.assertEqual(report["action"], "refused")
        self.assertFalse(report["changed"])

    def _assert_public_receipt(self, fixture: dict) -> bytes:
        content = fixture["receipt"].read_bytes()
        payload = json.loads(content)
        self.assertEqual(
            set(payload),
            {
                "schema",
                "kind",
                "target_hash",
                "head",
                "ref",
                "successor_row",
                "retired_at",
            },
        )
        self.assertEqual(payload["schema"], "shadow.retirement-receipt.v1")
        self.assertEqual(payload["kind"], "snapshot")
        self.assertRegex(payload["target_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(payload["head"], fixture["target_head"])
        self.assertEqual(payload["ref"], "refs/heads/main")
        self.assertIsNone(payload["successor_row"])
        self.assertRegex(payload["retired_at"], r"^\d{4}-\d{2}-\d{2}T.*Z$")
        public_bytes = content.decode("utf-8")
        for secret in (
            str(fixture["root"]),
            str(fixture["target"]),
            str(fixture["manifest"]),
        ):
            self.assertNotIn(secret, public_bytes)
        return content

    def test_expired_snapshot_dry_run_apply_and_rerun_remove_only_exact_child(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            fixture = snapshot_retirement_fixture(Path(dirname))
            repo = fixture["repo"]
            env = isolated_lifecycle_env(repo, None)
            sibling = fixture["root"] / "sibling-canary"
            sibling.mkdir()
            (sibling / "keep.txt").write_text("keep\n", encoding="utf-8")
            plan_bytes = (repo / "PLAN.md").read_bytes()
            authority_head = git(repo, "rev-parse", "HEAD")

            dry, dry_report, cas = preview_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                extra_env=env,
            )

            self.assertEqual(dry.returncode, 0, (dry.stderr, dry_report))
            self.assertEqual(dry_report["action"], "would_retire")
            self.assertFalse(dry_report["changed"])
            self.assertTrue(fixture["target"].is_dir())
            self.assertFalse(fixture["receipt"].exists())
            self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)

            applied, report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="snapshot-seat",
                extra_env=env,
            )

            self.assertEqual(applied.returncode, 0, (applied.stderr, report))
            self.assertEqual(report["action"], "retired")
            self.assertTrue(report["changed"])
            self.assertFalse(fixture["target"].exists())
            self.assertTrue(fixture["root"].is_dir())
            self.assertEqual((sibling / "keep.txt").read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(repo.is_dir())
            self.assertEqual((repo / "PLAN.md").read_bytes(), plan_bytes)
            self.assertEqual(
                git(repo, "merge-base", "--is-ancestor", fixture["target_head"], "refs/heads/main"),
                "",
            )
            self.assertEqual(git(repo, "rev-list", "--count", f"{authority_head}..HEAD"), "1")
            receipt_relative = fixture["receipt"].relative_to(repo).as_posix()
            self.assertEqual(
                set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines()),
                {receipt_relative},
            )
            receipt_bytes = self._assert_public_receipt(fixture)
            self.assertIsNone(report.get("successor"))
            retired_head = git(repo, "rev-parse", "HEAD")

            repeated, repeated_report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="snapshot-seat",
                extra_env=env,
            )

            self.assertEqual(
                repeated.returncode,
                0,
                (repeated.stderr, repeated_report),
            )
            self.assertEqual(repeated_report["action"], "already_retired")
            self.assertFalse(repeated_report["changed"])
            self.assertEqual(git(repo, "rev-parse", "HEAD"), retired_head)
            self.assertEqual(fixture["receipt"].read_bytes(), receipt_bytes)

    def test_live_snapshot_is_retained_without_receipt_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            fixture = snapshot_retirement_fixture(
                Path(dirname),
                expires_at="2999-01-01T00:00:00Z",
            )
            authority_head = git(fixture["repo"], "rev-parse", "HEAD")
            target_head = git(fixture["target"], "rev-parse", "HEAD")

            result, report = run(
                fixture["repo"],
                "--retirement-manifest",
                str(fixture["manifest"]),
                extra_env=isolated_lifecycle_env(fixture["repo"], None),
            )

            self._assert_refused(result, report)
            self.assertRegex(json.dumps(report).lower(), r"expir|live|future")
            self.assertTrue(fixture["target"].is_dir())
            self.assertEqual(git(fixture["target"], "rev-parse", "HEAD"), target_head)
            self.assertEqual(git(fixture["repo"], "rev-parse", "HEAD"), authority_head)
            self.assertFalse(fixture["receipt"].exists())

    def test_dirty_or_head_swapped_snapshot_after_preview_is_preserved(self) -> None:
        for changed in ("dirty", "head"):
            with (
                self.subTest(changed=changed),
                tempfile.TemporaryDirectory() as dirname,
            ):
                fixture = snapshot_retirement_fixture(Path(dirname))
                repo = fixture["repo"]
                env = isolated_lifecycle_env(repo, None)
                _, _, cas = preview_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=env,
                )
                changed_path = fixture["target"] / "PLAN.md"
                with changed_path.open("a", encoding="utf-8") as stream:
                    stream.write(f"\n{changed} after preview\n")
                if changed == "head":
                    git(fixture["target"], "add", "PLAN.md")
                    git(
                        fixture["target"],
                        "commit",
                        "--quiet",
                        "-m",
                        "advance snapshot after preview",
                    )
                target_head = git(fixture["target"], "rev-parse", "HEAD")
                target_bytes = changed_path.read_bytes()
                authority_head = git(repo, "rev-parse", "HEAD")

                result, report, _ = apply_with_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    cas=cas,
                    by="snapshot-seat",
                    extra_env=env,
                )

                self._assert_refused(result, report)
                self.assertTrue(fixture["target"].is_dir())
                self.assertEqual(changed_path.read_bytes(), target_bytes)
                self.assertEqual(git(fixture["target"], "rev-parse", "HEAD"), target_head)
                self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)
                self.assertFalse(fixture["receipt"].exists())

    def test_entity_mismatch_and_authority_unreachable_head_are_refused(self) -> None:
        for mismatch in ("entity", "recovery"):
            with (
                self.subTest(mismatch=mismatch),
                tempfile.TemporaryDirectory() as dirname,
            ):
                fixture = snapshot_retirement_fixture(Path(dirname))
                payload = json.loads(fixture["manifest"].read_text(encoding="utf-8"))
                if mismatch == "entity":
                    payload["target"]["entity"] = "0" * 64
                else:
                    unique = fixture["target"] / "UNIQUE.txt"
                    unique.write_text("only snapshot has this\n", encoding="utf-8")
                    git(fixture["target"], "add", "UNIQUE.txt")
                    git(
                        fixture["target"],
                        "commit",
                        "--quiet",
                        "-m",
                        "snapshot-only commit",
                    )
                    payload["target"]["head"] = git(
                        fixture["target"],
                        "rev-parse",
                        "HEAD",
                    )
                write_manifest(fixture["manifest"], payload)
                authority_head = git(fixture["repo"], "rev-parse", "HEAD")

                result, report = run(
                    fixture["repo"],
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=isolated_lifecycle_env(fixture["repo"], None),
                )

                self._assert_refused(result, report)
                self.assertTrue(fixture["target"].is_dir())
                self.assertEqual(git(fixture["repo"], "rev-parse", "HEAD"), authority_head)
                self.assertFalse(
                    (fixture["repo"] / "docs" / "plan-archive" / "retirements").exists()
                )

    def test_broad_name_symlink_root_and_symlink_child_are_refused(self) -> None:
        for unsafe in ("broad_name", "symlink_root", "symlink_child"):
            with (
                self.subTest(unsafe=unsafe),
                tempfile.TemporaryDirectory() as dirname,
            ):
                root = Path(dirname)
                fixture = snapshot_retirement_fixture(root)
                payload = json.loads(fixture["manifest"].read_text(encoding="utf-8"))
                protected = fixture["target"]
                if unsafe == "broad_name":
                    victim = root / "victim"
                    cloned = subprocess.run(
                        ["git", "clone", "--quiet", str(fixture["repo"]), str(victim)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(cloned.returncode, 0, cloned.stderr)
                    protected = victim
                    payload["target"]["name"] = "../victim"
                elif unsafe == "symlink_root":
                    alias_root = root / "snapshots-alias"
                    os.symlink(fixture["root"], alias_root, target_is_directory=True)
                    payload["target"]["root"] = str(alias_root)
                else:
                    victim = root / "victim"
                    cloned = subprocess.run(
                        ["git", "clone", "--quiet", str(fixture["repo"]), str(victim)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(cloned.returncode, 0, cloned.stderr)
                    git(victim, "remote", "set-url", "origin", "git@example.invalid:team/lifecycle-snapshot.git")
                    alias = fixture["root"] / "snapshot-alias"
                    os.symlink(victim, alias, target_is_directory=True)
                    protected = victim
                    payload["target"]["name"] = "snapshot-alias"
                write_manifest(fixture["manifest"], payload)
                authority_head = git(fixture["repo"], "rev-parse", "HEAD")

                result, report = run(
                    fixture["repo"],
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=isolated_lifecycle_env(fixture["repo"], None),
                )

                self._assert_refused(result, report)
                self.assertTrue(protected.exists())
                self.assertTrue(fixture["repo"].exists())
                self.assertEqual(git(fixture["repo"], "rev-parse", "HEAD"), authority_head)
                self.assertFalse(
                    (fixture["repo"] / "docs" / "plan-archive" / "retirements").exists()
                )

    def test_missing_or_tampered_receipt_never_authorizes_absent_target(self) -> None:
        for receipt_state in ("missing", "tampered"):
            with (
                self.subTest(receipt_state=receipt_state),
                tempfile.TemporaryDirectory() as dirname,
            ):
                fixture = snapshot_retirement_fixture(Path(dirname))
                repo = fixture["repo"]
                env = isolated_lifecycle_env(repo, None)
                applied, applied_report, _ = apply_with_cas(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    by="snapshot-seat",
                    extra_env=env,
                )
                self.assertEqual(
                    applied.returncode,
                    0,
                    (applied.stderr, applied_report),
                )
                self.assertFalse(fixture["target"].exists())
                if receipt_state == "missing":
                    git(repo, "rm", "--quiet", fixture["receipt"].relative_to(repo).as_posix())
                else:
                    payload = json.loads(fixture["receipt"].read_text(encoding="utf-8"))
                    payload["target_hash"] = "0" * 64
                    fixture["receipt"].write_text(
                        json.dumps(payload, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    git(repo, "add", fixture["receipt"].relative_to(repo).as_posix())
                git(repo, "commit", "--quiet", "-m", f"make retirement receipt {receipt_state}")
                authority_head = git(repo, "rev-parse", "HEAD")

                result, report = run(
                    repo,
                    "--retirement-manifest",
                    str(fixture["manifest"]),
                    extra_env=env,
                )

                self._assert_refused(result, report)
                self.assertFalse(fixture["target"].exists())
                self.assertEqual(git(repo, "rev-parse", "HEAD"), authority_head)


class RetirementJournalRecovery(unittest.TestCase):
    def _crash_after_snapshot_delete(
        self,
        fixture: dict,
        home: Path,
        *,
        staged_receipt: str | None,
    ) -> str:
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            preview, _ = lifecycle.inspect_retirement(
                fixture["repo"],
                fixture["manifest"],
            )
            cas = preview["cas"]

            def crash(repo: Path, plan: Path, operation: dict) -> str:
                if staged_receipt is not None:
                    payload = dict(operation["receipt_payload"])
                    if staged_receipt == "mismatched":
                        payload["retired_at"] = "2001-01-01T00:00:00Z"
                    lifecycle.atomic_write(
                        operation["receipt"],
                        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(
                            "utf-8"
                        ),
                    )
                    lifecycle.git(
                        repo,
                        "add",
                        "--",
                        operation["receipt"].relative_to(repo).as_posix(),
                    )
                raise SystemExit("simulated receipt commit crash")

            with (
                mock.patch.object(
                    lifecycle,
                    "commit_retirement_receipt",
                    side_effect=crash,
                ),
                self.assertRaisesRegex(SystemExit, "simulated receipt commit crash"),
            ):
                lifecycle.apply_retirement(
                    fixture["repo"],
                    fixture["manifest"],
                    expected=cas,
                    owner="recovery-seat",
                )
        self.assertFalse(fixture["target"].exists())
        journal = home / ".shadow" / "retirements" / f"{fixture['digest']}.applying.json"
        self.assertTrue(journal.is_file())
        return cas

    def test_absent_target_with_exact_journal_finalizes_frozen_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            fixture = snapshot_retirement_fixture(root)
            cas = self._crash_after_snapshot_delete(
                fixture,
                home,
                staged_receipt=None,
            )

            result, report, _ = apply_with_cas(
                fixture["repo"],
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="recovery-seat",
                extra_env={"HOME": str(home)},
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "retired")
            self.assertTrue(report["changed"])
            self.assertTrue(fixture["receipt"].is_file())
            self.assertEqual(git(fixture["repo"], "status", "--porcelain=v1"), "")
            self.assertFalse(
                (home / ".shadow" / "retirements" / f"{fixture['digest']}.applying.json").exists()
            )

    def test_exact_staged_receipt_and_journal_commit_once_on_retry(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            fixture = snapshot_retirement_fixture(root)
            cas = self._crash_after_snapshot_delete(
                fixture,
                home,
                staged_receipt="exact",
            )
            before = git(fixture["repo"], "rev-parse", "HEAD")

            result, report, _ = apply_with_cas(
                fixture["repo"],
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="recovery-seat",
                extra_env={"HOME": str(home)},
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(git(fixture["repo"], "rev-list", "--count", f"{before}..HEAD"), "1")
            self.assertEqual(git(fixture["repo"], "status", "--porcelain=v1"), "")
            payload = json.loads(fixture["receipt"].read_text(encoding="utf-8"))
            self.assertEqual(payload["target_hash"], cas)

    def test_mismatched_staged_receipt_never_finalizes_deleted_target(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            fixture = snapshot_retirement_fixture(root)
            cas = self._crash_after_snapshot_delete(
                fixture,
                home,
                staged_receipt="mismatched",
            )
            head = git(fixture["repo"], "rev-parse", "HEAD")

            result, report, _ = apply_with_cas(
                fixture["repo"],
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="recovery-seat",
                extra_env={"HOME": str(home)},
            )

            self.assertEqual(result.returncode, 1, (result.stderr, report))
            self.assertIn("crash journal", report["error"])
            self.assertEqual(git(fixture["repo"], "rev-parse", "HEAD"), head)
            self.assertFalse(fixture["target"].exists())

    def test_late_ignored_worktree_dirt_is_preserved_before_removal(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            fixture = worktree_retirement_fixture(root)
            target = fixture["target"]
            original_inspect = lifecycle.inspect_retirement
            calls = 0

            def inject_after_second_inspect(repo: Path, manifest: Path):
                nonlocal calls
                result = original_inspect(repo, manifest)
                calls += 1
                if calls == 2:
                    (target / "ignored.tmp").write_text("late ignored dirt\n", encoding="utf-8")
                return result

            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                preview, _ = original_inspect(fixture["repo"], fixture["manifest"])
                with (
                    mock.patch.object(
                        lifecycle,
                        "inspect_retirement",
                        side_effect=inject_after_second_inspect,
                    ),
                    self.assertRaisesRegex(lifecycle.LifecycleError, "ignored|state"),
                ):
                    lifecycle.apply_retirement(
                        fixture["repo"],
                        fixture["manifest"],
                        expected=preview["cas"],
                        owner="recovery-seat",
                    )

            self.assertTrue(target.is_dir())
            self.assertEqual(
                (target / "ignored.tmp").read_text(encoding="utf-8"),
                "late ignored dirt\n",
            )
            self.assertFalse(fixture["receipt"].exists())
            self.assertIn(str(target), git(fixture["repo"], "worktree", "list", "--porcelain"))


class DirtyOrProvenanceBearingStateIsRefused(unittest.TestCase):
    def test_dirty_plan_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            with (repo / "PLAN.md").open("a", encoding="utf-8") as stream:
                stream.write("\n")
            result, report = run(repo, "--milestone", "Finished work")
            self.assertEqual(result.returncode, 1, report)
            self.assertEqual(report["action"], "refused")
            self.assertIn("changed", report["error"])

    def test_clean_archive_collision_is_refused_as_existing_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            target = repo / "docs" / "plan-archive" / "finished-work.md"
            target.parent.mkdir(parents=True)
            target.write_text("independent archive\n", encoding="utf-8")
            git(repo, "add", target.relative_to(repo).as_posix())
            git(repo, "commit", "--quiet", "-m", "independent archive")

            result, report = run(repo, "--milestone", "Finished work")

            self.assertEqual(result.returncode, 1, report)
            self.assertIn("different provenance", report["error"])
            self.assertEqual(target.read_text(encoding="utf-8"), "independent archive\n")

    def test_clean_tamper_of_content_addressed_archive_is_refused_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            applied, applied_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
            )
            self.assertEqual(applied.returncode, 0, (applied.stderr, applied_report))
            archive = repo / "docs" / "plan-archive" / "finished-work.md"
            archive.write_text(
                archive.read_text(encoding="utf-8") + "tampered after archive\n",
                encoding="utf-8",
            )
            git(repo, "add", archive.relative_to(repo).as_posix())
            git(repo, "commit", "--quiet", "-m", "tamper with lifecycle archive")
            plan_before = (repo / "PLAN.md").read_bytes()
            archive_before = archive.read_bytes()
            head_before = git(repo, "rev-parse", "HEAD")

            repeated, report = run(repo, "--milestone", "Finished work")

            self.assertEqual(repeated.returncode, 1, (repeated.stderr, report))
            self.assertEqual(report["action"], "refused")
            self.assertIn("archive", report["error"].lower())
            self.assertEqual((repo / "PLAN.md").read_bytes(), plan_before)
            self.assertEqual(archive.read_bytes(), archive_before)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head_before)

    def test_coordinated_digest_and_cas_tamper_cannot_replace_lifecycle_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            applied, applied_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
            )
            self.assertEqual(applied.returncode, 0, (applied.stderr, applied_report))
            archive = repo / "docs" / "plan-archive" / "finished-work.md"
            plan = repo / "PLAN.md"
            tombstone = re.search(
                lifecycle.TOMBSTONE_RE_TEMPLATE.format(slug="finished\\-work"),
                plan.read_text(encoding="utf-8"),
            )
            self.assertIsNotNone(tombstone)
            assert tombstone is not None
            _, _, body = archive.read_bytes().partition(b"\n")
            tampered_body = body + b"coordinated replacement\n"
            digest = hashlib.sha256(tampered_body).hexdigest()
            successor = tombstone.group("successor")
            forged_cas = lifecycle.canonical_sha256(
                {
                    "schema": "shadow.lifecycle-archive.v1",
                    "relative": "PLAN.md",
                    "head": tombstone.group("head"),
                    "blob": tombstone.group("blob"),
                    "milestone": "Finished work",
                    "archive_sha256": digest,
                    "successor": successor,
                }
            )
            forged_marker = (
                f"<!-- shadow:lifecycle:finished-work:sha256:{digest}:cas:{forged_cas}:"
                f"head:{tombstone.group('head')}:blob:{tombstone.group('blob')}:"
                f"successor:{successor} -->"
            )
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(tombstone.group(0), forged_marker),
                encoding="utf-8",
            )
            archive.write_bytes(
                lifecycle.ARCHIVE_HEADER_TEMPLATE.format(
                    slug="finished-work",
                    digest=digest,
                    cas=forged_cas,
                    head=tombstone.group("head"),
                    blob=tombstone.group("blob"),
                    successor=successor,
                ).encode("ascii")
                + tampered_body
            )
            git(repo, "add", "PLAN.md", "docs/plan-archive/finished-work.md")
            git(repo, "commit", "--quiet", "-m", "forge coordinated lifecycle bytes")
            head_before = git(repo, "rev-parse", "HEAD")

            repeated, report = run(
                repo,
                "--apply",
                "--expect",
                forged_cas,
                "--by",
                "lifecycle-test-seat",
                "--milestone",
                "Finished work",
            )

            self.assertEqual(repeated.returncode, 1, (repeated.stderr, report))
            self.assertIn("introduction", report["error"])
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head_before)

    def test_unproven_milestone_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            text = PLAN.replace(
                "- 2026-08-10T00:01:00Z ~bb22 PROOF true -> pass\n", ""
            )
            repo = make_repo(Path(dirname), text)
            result, report = run(repo, "--milestone", "Finished work")
            self.assertEqual(result.returncode, 1, report)
            self.assertIn("lacks PROOF", report["error"])

    def test_non_git_and_symlinked_plans_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            plain = root / "plain"
            plain.mkdir()
            (plain / "PLAN.md").write_text(PLAN, encoding="utf-8")
            plain_result, plain_report = run(plain)
            self.assertEqual(plain_result.returncode, 1, plain_report)

            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "--quiet")
            git(repo, "config", "user.name", "Lifecycle Test")
            git(repo, "config", "user.email", "lifecycle@example.invalid")
            (repo / "REAL.md").write_text(PLAN, encoding="utf-8")
            os.symlink("REAL.md", repo / "PLAN.md")
            git(repo, "add", "PLAN.md", "REAL.md")
            git(repo, "commit", "--quiet", "-m", "symlink plan")
            linked_result, linked_report = run(repo)
            self.assertEqual(linked_result.returncode, 1, linked_report)
            self.assertIn("non-symlink", linked_report["error"])

    def test_retirement_requires_a_manifest_and_never_invents_a_target(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname))
            result, report = run(repo)
            self.assertEqual(result.returncode, 0, report)
            self.assertTrue(report["retirement"]["supported"])
            self.assertEqual(report["retirement"]["action"], "manifest_required")
            self.assertIn("never", report["retirement"]["reason"])
            self.assertIn("guess", report["retirement"]["reason"])


class LifecycleClaimsReachableSuccessor(unittest.TestCase):
    def test_apply_by_claims_the_first_reachable_successor(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            repo = make_repo(root)
            seeded = run_shadow(home, "status", "--root", str(repo), "--json", cwd=repo)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)

            result, report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                by="lifecycle-seat",
                command=True,
                extra_env={"HOME": str(home)},
            )

            self.assertEqual(result.returncode, 0, (result.stderr, report))
            self.assertEqual(report["action"], "archived")
            payload = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [(claim["row"], claim["owner"]) for claim in payload["claims"]],
                [("~cc33", "lifecycle-seat")],
            )
            self.assertEqual(payload["entities"][0]["resume"], "~cc33")

    def test_committed_archive_reports_successor_failure_and_exact_retry_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            (home / ".shadow").write_text("board unavailable\n", encoding="utf-8")
            repo = make_repo(root)
            env = {"HOME": str(home)}
            _, _, cas = preview_cas(
                repo,
                "--milestone",
                "Finished work",
                extra_env=env,
            )
            initial_head = git(repo, "rev-parse", "HEAD")

            failed, failed_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
                by="recovery-seat",
                extra_env=env,
            )

            self.assertEqual(failed.returncode, 1, (failed.stderr, failed_report))
            self.assertEqual(failed_report["action"], "archived_needs_successor")
            self.assertTrue(failed_report["changed"])
            archived_head = git(repo, "rev-parse", "HEAD")
            self.assertNotEqual(archived_head, initial_head)

            repeated, repeated_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
                by="recovery-seat",
                extra_env=env,
            )
            self.assertEqual(repeated.returncode, 1, (repeated.stderr, repeated_report))
            self.assertEqual(
                repeated_report["action"],
                "already_archived_needs_successor",
            )
            self.assertFalse(repeated_report["changed"])
            self.assertEqual(git(repo, "rev-parse", "HEAD"), archived_head)

            (home / ".shadow").unlink()
            recovered, recovered_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
                by="recovery-seat",
                extra_env=env,
            )
            self.assertEqual(recovered.returncode, 0, (recovered.stderr, recovered_report))
            self.assertEqual(recovered_report["successor_claim"]["row"], "~cc33")
            board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [(claim["row"], claim["owner"]) for claim in board["claims"]],
                [("~cc33", "recovery-seat")],
            )
            self.assertEqual(git(repo, "rev-parse", "HEAD"), archived_head)

    def test_old_archive_cas_never_advances_to_a_second_successor(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            plan = PLAN.replace(
                "- [pending] next result is accepted ~dd44 (DoD)",
                "- [pending] parallel result starts ~ee55 | proof: cmd true\n"
                "- [pending] next result is accepted ~dd44 (DoD)",
            )
            repo = make_repo(root, plan)
            env = {"HOME": str(home)}
            seeded = run_shadow(home, "status", "--root", str(repo), "--json", cwd=repo)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            _, _, cas = preview_cas(
                repo,
                "--milestone",
                "Finished work",
                extra_env=env,
            )
            first, first_report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
                by="lifecycle-seat",
                extra_env=env,
            )
            self.assertEqual(first.returncode, 0, (first.stderr, first_report))
            self.assertEqual(first_report["successor_claim"]["row"], "~cc33")
            plan_path = repo / "PLAN.md"
            evolved = plan_path.read_text(encoding="utf-8").replace(
                "- [pending] next result starts ~cc33 | proof: cmd true",
                "- [completed] next result starts ~cc33 | proof: cmd true",
            )
            evolved += "\n- 2026-08-10T00:03:00Z ~cc33 PROOF true -> pass\n"
            plan_path.write_text(evolved, encoding="utf-8")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "complete bound lifecycle successor")

            repeated, report, _ = apply_with_cas(
                repo,
                "--milestone",
                "Finished work",
                cas=cas,
                by="lifecycle-seat",
                extra_env=env,
            )

            self.assertEqual(repeated.returncode, 0, (repeated.stderr, report))
            self.assertEqual(report["successor_claim"]["action"], "advanced")
            self.assertEqual(report["successor_claim"]["row"], "~cc33")
            board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertNotIn("~ee55", [claim["row"] for claim in board["claims"]])

    def test_retirement_receipt_durably_binds_one_successor_and_clean_repeat_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            home = root / "home"
            home.mkdir()
            fixture = snapshot_retirement_fixture(root)
            repo = fixture["repo"]
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "\n## Progress\n",
                    "\n### Continue after retirement\n"
                    "- [pending] continue exact work ~cc33 | proof: cmd true\n"
                    "- [pending] accept continued work ~dd44 (DoD) | proof: cmd true | needs: ~cc33\n"
                    "\n## Progress\n",
                ),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "add retirement successor")
            env = {"HOME": str(home)}
            seeded = run_shadow(home, "status", "--root", str(repo), "--json", cwd=repo)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            _, _, cas = preview_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                extra_env=env,
            )

            applied, report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="retirement-seat",
                extra_env=env,
            )

            self.assertEqual(applied.returncode, 0, (applied.stderr, report))
            self.assertEqual(report["successor_claim"]["row"], "~cc33")
            receipt = json.loads(fixture["receipt"].read_text(encoding="utf-8"))
            self.assertEqual(receipt["successor_row"], "~cc33")
            journal = home / ".shadow" / "retirements" / f"{fixture['digest']}.applying.json"
            self.assertFalse(journal.exists())
            board_before = (home / ".shadow" / "board.json").read_bytes()
            head_before = git(repo, "rev-parse", "HEAD")

            repeated, repeated_report, _ = apply_with_cas(
                repo,
                "--retirement-manifest",
                str(fixture["manifest"]),
                cas=cas,
                by="retirement-seat",
                extra_env=env,
            )

            self.assertEqual(repeated.returncode, 0, (repeated.stderr, repeated_report))
            self.assertEqual(repeated_report["action"], "already_retired")
            self.assertEqual(repeated_report["successor_row"], "~cc33")
            self.assertNotIn("successor_claim", repeated_report)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), board_before)
            self.assertEqual(git(repo, "rev-parse", "HEAD"), head_before)


if __name__ == "__main__":
    unittest.main()
