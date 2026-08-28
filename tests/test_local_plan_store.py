"""Local plan authorities must never enter the board's private Git journal."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402
from tests.plan_tree_fixture import install_plan_tree  # noqa: E402


PLAN = """# Local demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2

## Tasks

### The local outcome
- [pending] prove local authority ~aa11 | proof: cmd true
- [pending] local authority is done ~bb22 (DoD) | proof: cmd true | needs: ~aa11

## Progress

- 2026-08-11T00:00:00Z NOTE seeded locally
"""


def plan_with_origin(origin: str) -> str:
    return PLAN.replace(
        "- Priority: 2\n",
        f"- Priority: 2\n- Origin: {origin}\n",
        1,
    )


_LIFECYCLE_SPEC = importlib.util.spec_from_file_location(
    "shadow_lifecycle", ROOT / "scripts" / "shadow-lifecycle.py"
)
assert _LIFECYCLE_SPEC and _LIFECYCLE_SPEC.loader
lifecycle = importlib.util.module_from_spec(_LIFECYCLE_SPEC)
sys.modules[_LIFECYCLE_SPEC.name] = lifecycle
_LIFECYCLE_SPEC.loader.exec_module(lifecycle)


def lifecycle_tombstone_re(slug: str) -> str:
    """The lifecycle module's own tombstone reader, for the archived slug."""
    return lifecycle.TOMBSTONE_RE_TEMPLATE.format(slug=slug)


ARCHIVABLE_PLAN = """# Local demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2

## Tasks

### Finished work
- [completed] first local result exists ~aa11 | proof: cmd true
- [completed] finished local result is accepted ~bb22 (DoD) | proof: cmd true | needs: ~aa11

### Next work
- [pending] next local result starts ~cc33 | proof: cmd true | needs: ~bb22
- [pending] next local result is accepted ~dd44 (DoD) | proof: cmd true | needs: ~cc33

## Progress

- 2026-08-11T00:00:00Z ~aa11 PROOF true -> pass
- 2026-08-11T00:01:00Z ~bb22 PROOF true -> pass
- 2026-08-11T00:02:00Z NOTE unrelated history remains live
"""


class LocalPlanStore(unittest.TestCase):
    def test_accept_mutates_a_partitioned_local_plan_without_losing_the_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            repo = root / "dev" / "feature-checkout"
            repo.mkdir(parents=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("remote", "add", "origin", "git@github.com:example/widget.git"),
                ("add", "README.md", "PLAN.md"),
                ("commit", "--quiet", "-m", "seed"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            plan_root = home / ".shadow" / "plans" / "widget"
            plan_root.mkdir(parents=True)
            source = plan_with_origin("github.com/example/widget").replace(
                "[pending]", "[in_progress]", 1
            ).encode("utf-8")
            plan = install_plan_tree(plan_root, source)
            board.reconcile(
                [{"plan": str(plan), "project": "widget", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            board.claim(
                plan,
                "~aa11",
                "local-seat",
                project="widget",
                priority=2,
                home=home,
            )
            entity = board.entity_state(plan, home=home)["entity"]["id"]

            accepted = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"), "accept", "--entity", entity,
                    "--repo", str(repo),
                    "--row", "~aa11", "--by", "local-seat",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            logical = board.read_plan_text(plan)
            self.assertIn("[completed] prove local authority ~aa11", logical)
            self.assertIn("~aa11 PROOF true -> pass (accept)", logical)
            self.assertTrue(board.open_plan(plan).is_tree)
            self.assertEqual(board.entity_state(plan, home=home)["claims"], [])

    def test_lifecycle_archives_a_partitioned_local_plan_losslessly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            plan_root = home / ".shadow" / "plans" / "widget"
            plan_root.mkdir(parents=True)
            plan = install_plan_tree(plan_root, ARCHIVABLE_PLAN.encode("utf-8"))
            board.reconcile(
                [{"plan": str(plan), "project": "widget", "priority": 2, "candidates": ["~cc33"]}],
                [],
                home=home,
            )
            before = board.read_plan_text(plan)

            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                preview, _ = lifecycle.inspect(plan_root, "Finished work")
                report = lifecycle.apply(
                    plan_root,
                    "Finished work",
                    expected=preview["cas"],
                    owner="local-seat",
                )

            self.assertTrue(report["ok"], report)
            self.assertEqual(report["action"], "archived")
            self.assertTrue(board.open_plan(plan).is_tree)
            logical = board.read_plan_text(plan)
            archive = plan_root / "docs" / "plan-archive" / "finished-work.md"
            self.assertIn("shadow:lifecycle:finished-work", logical)
            self.assertNotIn("first local result exists ~aa11", logical)
            self.assertIn("first local result exists ~aa11", archive.read_text())
            self.assertIn("unrelated history remains live", logical)
            self.assertNotEqual(logical, before)

    def test_portfolio_import_moves_registered_ai_leo_plan_to_private_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            source = portfolio / "ai-leo"
            source.mkdir(parents=True)
            source_plan = source / "PLAN.md"
            source_plan.write_text(PLAN, encoding="utf-8")
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("remote", "add", "origin", "git@github.com:leojkwan/ai-leo.git"),
                ("add", "PLAN.md"),
                ("commit", "--quiet", "-m", "seed"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(source), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            local_plan = home / ".shadow" / "plans" / "ai-leo" / "PLAN.md"
            local_plan.parent.mkdir(parents=True)
            local_plan.write_text(PLAN, encoding="utf-8")
            board.reconcile(
                [{"plan": str(source_plan), "project": "demo", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )

            import shadow_board_import as importer

            spec = importlib.util.spec_from_file_location(
                "shadow_local_plan_status", ROOT / "scripts" / "shadow-status.py"
            )
            status = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(status)
            payload = importer.reconcile_portfolio(portfolio, status._amp, home=home)

            self.assertEqual(payload["entities"][0]["plan"], str(local_plan.resolve()))
            self.assertTrue(board.is_local_plan(Path(payload["entities"][0]["plan"]), home=home))
            # A stale executable can still append the old source alias once;
            # the next refresh removes that unclaimed duplicate rather than
            # letting it become a second authority.
            board.reconcile(
                [{"plan": str(source_plan), "project": "demo", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            again = importer.reconcile_portfolio(portfolio, status._amp, home=home)
            self.assertEqual(again["entities"][0]["plan"], str(local_plan.resolve()))
            self.assertEqual(len(again["entities"]), 1)

            # Source cleanup can win the race with a board refresh.  The
            # duplicate source locator then points nowhere, but the local
            # authority still has every claimed row and resume target.  It is
            # safe to remove that stale metadata without recreating a plan.
            source_plan.unlink()
            missing_source = importer.reconcile_portfolio(portfolio, status._amp, home=home)
            self.assertEqual(missing_source["entities"][0]["plan"], str(local_plan.resolve()))
            self.assertEqual(len(missing_source["entities"]), 1)

    def test_a_tracked_shadow_plans_directory_is_not_machine_local(self) -> None:
        # A source repository may keep `<repo>/.shadow/plans/...`. That plan is
        # committed and public: classifying it by directory name alone would
        # skip its clean/committed checks and give it a private identity.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            repo = root / "product"
            plan = repo / ".shadow" / "plans" / "release" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(PLAN, encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)

            self.assertFalse(board.is_local_plan(plan, home=home))
            self.assertNotIn("local-plan:", board.plan_identity_parts(plan)[0])

    def test_repository_shaped_verbs_resolve_the_registered_local_plan(self) -> None:
        # `shadow status` lists a project whose authority is machine-local, so
        # `--repo` must reach the same authority instead of refusing work for a
        # plan that deliberately does not live in the checkout. The block it
        # prints has to point at this computer: no ref serves that file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            repo = root / "dev" / "widget"
            repo.mkdir(parents=True)
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            plan = home / ".shadow" / "plans" / "widget" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(PLAN, encoding="utf-8")
            board.reconcile(
                [{"plan": str(plan), "project": "widget", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            self.assertEqual(board.local_plan_for_repo(repo, home=home), plan.resolve())

            env = {**os.environ, "HOME": str(home)}
            claim = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "shadow-throw.py"), "--repo", str(repo), "--task", "~aa11", "--by", "local-seat"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(claim.returncode, 0, claim.stderr)

            block = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "shadow-amp.py"), "--repo", str(repo), "--by", "local-seat"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(block.returncode, 0, block.stderr)
            self.assertIn("@ this computer", block.stdout)
            self.assertIn("read that local file directly", block.stdout)
            self.assertNotIn("current origin ref", block.stdout)

    def test_a_local_plan_can_archive_a_proven_milestone(self) -> None:
        """The hot-plan byte ceiling must have a reachable remedy locally.

        `HOT-PLAN-BYTES` names exactly one remedy -- archive one proven
        milestone with `shadow lifecycle`. Every sibling verb already routes a
        machine-local authority through `frozen_plan_snapshot`; lifecycle alone
        still demanded a Git-tracked PLAN.md, so the one documented way to
        shrink a local plan refused by construction. Measured 2026-08-12 on
        Shadow's own plan: 506 bytes of headroom and no legal way to reclaim
        any.
        """
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            plan = home / ".shadow" / "plans" / "demo" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(ARCHIVABLE_PLAN, encoding="utf-8")

            board.reconcile(
                [{"plan": str(plan), "project": "demo", "priority": 2, "candidates": ["~cc33"]}],
                [],
                home=home,
            )
            self.assertTrue(board.is_local_plan(plan, home=home))

            preview = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "shadow-lifecycle.py"),
                    "--repo",
                    str(plan.parent),
                    "--milestone",
                    "Finished work",
                    "--json",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            report = json.loads(preview.stdout or "{}")
            cas = report.get("cas")
            self.assertTrue(
                isinstance(cas, str) and cas,
                f"a local dry run must emit a CAS token, got {report}",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "shadow-lifecycle.py"),
                    "--repo",
                    str(plan.parent),
                    "--milestone",
                    "Finished work",
                    "--apply",
                    "--expect",
                    cas,
                    "--by",
                    "local-archive-seat",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            # The archive is finished by atomic local writes, never a commit.
            archive = plan.parent / "docs" / "plan-archive" / "finished-work.md"
            self.assertTrue(archive.is_file(), "the archive file must be written")
            self.assertTrue(
                board.open_plan(plan).is_tree,
                "the first local lifecycle mutation must retain its plain source as tree lineage",
            )
            compacted = board.read_plan_text(plan)
            self.assertNotIn("### Finished work", compacted)
            self.assertIn("### Next work", compacted)

            # Provenance survives: the tombstone must carry the content address
            # `frozen_plan_snapshot` stamps, and the reader must accept it.
            self.assertRegex(compacted, r"head:local:[0-9a-f]{64}")
            slug = "finished-work"
            self.assertRegex(
                compacted,
                lifecycle_tombstone_re(slug),
                "lifecycle must not mint a receipt its own reader rejects",
            )

            # The private authority stays out of the board's Git journal.
            tracked = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "ls-files"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(tracked.stdout.strip(), "board.json")

    def test_local_plan_claim_is_not_git_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            plan = home / ".shadow" / "plans" / "demo" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(PLAN, encoding="utf-8")

            payload = board.reconcile(
                [{"plan": str(plan), "project": "demo", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            entity = payload["entities"][0]
            self.assertTrue(board.is_local_plan(plan, home=home))
            self.assertTrue((home / ".shadow" / ".git").is_dir())
            ignored = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "check-ignore", "-q", "plans/demo/PLAN.md"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ignored.returncode, 0, ignored.stderr)

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "shadow-throw.py"), "--entity", entity["id"], "--task", "~aa11", "--by", "local-seat"],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("read that local file directly", result.stdout)
            self.assertNotIn("current origin ref", result.stdout)
            state = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertEqual(state["claims"][0]["row"], "~aa11")
            tracked = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "ls-files", "plans/demo/PLAN.md"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(tracked.stdout, "")

    def test_lint_and_paired_accept_run_a_local_plan_against_its_source_checkout(self) -> None:
        """A private authority still proves work from its registered source repo.

        The local plan deliberately has no Git checkout of its own.  A public
        `shadow lint --repo` and paired `shadow accept --entity --repo` must
        therefore use the source checkout's committed HEAD for the proof while
        leaving the completed PLAN private to this computer.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            repo = root / "dev" / "widget"
            repo.mkdir(parents=True)
            (repo / "proof.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("add", "proof.py"),
                ("commit", "--quiet", "-m", "seed proof"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            plan = home / ".shadow" / "plans" / "widget" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                PLAN.replace("cmd true", "cmd python3 proof.py", 1).replace(
                    "[pending]", "[in_progress]", 1
                ),
                encoding="utf-8",
            )
            board.reconcile(
                [{"plan": str(plan), "project": "widget", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            board.claim(plan, "~aa11", "local-seat", project="widget", priority=2, home=home)
            entity = board.entity_state(plan, home=home)["entity"]["id"]
            env = {**os.environ, "HOME": str(home)}

            lint = subprocess.run(
                [str(ROOT / "bin" / "shadow"), "lint", "--repo", str(repo), str(plan)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(lint.returncode, 0, lint.stderr)

            accept_argv = [
                str(ROOT / "bin" / "shadow"), "accept", "--entity", entity,
                "--repo", str(repo),
                "--row", "~aa11", "--by", "local-seat",
            ]
            before = plan.read_text(encoding="utf-8")
            failed = subprocess.run(
                accept_argv,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertIn(
                "proof did not pass from the detached source checkout",
                failed.stderr,
            )
            self.assertEqual(plan.read_text(encoding="utf-8"), before)
            self.assertEqual(len(board.entity_state(plan, home=home)["claims"]), 1)

            (repo / "proof.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "proof.py"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "--quiet", "-m", "fix proof"],
                check=True,
            )
            accepted = subprocess.run(
                accept_argv,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("[completed] prove local authority ~aa11", text)
            self.assertIn("~aa11 PROOF python3 proof.py -> pass (accept)", text)
            source_receipts = [
                line for line in text.splitlines() if "~aa11 SOURCE " in line
            ]
            self.assertEqual(len(source_receipts), 1)
            self.assertIn(
                subprocess.run(
                    ["git", "-C", str(repo), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                source_receipts[0],
            )
            self.assertNotIn(str(root), source_receipts[0])
            self.assertEqual(board.entity_state(plan, home=home)["claims"], [])
            self.assertEqual(subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True, text=True, check=False,
            ).stdout, "")

    def test_entity_and_repo_accept_the_selected_sibling_plan(self) -> None:
        """Only paired selectors can choose among colliding local rows."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            repo = root / "dev" / "shadow-plan-map-20260826"
            repo.mkdir(parents=True)
            marker = root / "proof-ran"
            proof_file = repo / "proof.txt"
            proof_file.write_text("committed\n", encoding="utf-8")
            (repo / "proof.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "Path(os.environ['SHADOW_PROOF_MARKER']).write_text('ran\\n', encoding='utf-8')\n"
                "raise SystemExit(\n"
                "    0\n"
                "    if Path('proof.txt').read_text(encoding='utf-8') == 'committed\\n'\n"
                "    else 1\n"
                ")\n",
                encoding="utf-8",
            )
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("remote", "add", "origin", "https://github.com/example/source.git"),
                ("add", "proof.py", "proof.txt"),
                ("commit", "--quiet", "-m", "seed proof"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            target = home / ".shadow" / "plans" / "shadow-plan-map-source-release" / "PLAN.md"
            target.parent.mkdir(parents=True)
            proof = "cmd python3 proof.py"
            target.write_text(
                plan_with_origin("github.com/example/source")
                .replace("cmd true", proof, 1)
                .replace("[pending]", "[in_progress]", 1),
                encoding="utf-8",
            )
            sibling = home / ".shadow" / "plans" / repo.name / "PLAN.md"
            sibling.parent.mkdir(parents=True)
            sibling.write_text(
                plan_with_origin("github.com/example/source")
                .replace("cmd true", proof, 1)
                .replace("[pending]", "[in_progress]", 1),
                encoding="utf-8",
            )
            wrong = home / ".shadow" / "plans" / "wrong-entity" / "PLAN.md"
            wrong.parent.mkdir(parents=True)
            wrong.write_text(
                plan_with_origin("github.com/example/source")
                .replace("~aa11", "~cc33")
                .replace("~bb22", "~dd44"),
                encoding="utf-8",
            )
            board.reconcile(
                [
                    {
                        "plan": str(sibling),
                        "project": "shadow",
                        "priority": 1,
                        "candidates": ["~aa11"],
                    },
                    {
                        "plan": str(target),
                        "project": "shadow",
                        "priority": 1,
                        "candidates": ["~aa11"],
                    },
                    {
                        "plan": str(wrong),
                        "project": "shadow",
                        "priority": 1,
                        "candidates": ["~cc33"],
                    },
                ],
                [],
                home=home,
            )
            board.claim(
                sibling,
                "~aa11",
                "local-seat",
                project="shadow",
                priority=1,
                home=home,
            )
            board.claim(
                target,
                "~aa11",
                "local-seat",
                project="shadow",
                priority=1,
                home=home,
            )
            entity = board.entity_state(target, home=home)["entity"]["id"]
            wrong_entity = board.entity_state(wrong, home=home)["entity"]["id"]
            env = {
                **os.environ,
                "HOME": str(home),
                "SHADOW_PROOF_MARKER": str(marker),
            }
            proof_file.write_text("dirty\n", encoding="utf-8")
            target_before = target.read_bytes()
            sibling_before = sibling.read_bytes()
            wrong_before = wrong.read_bytes()
            board_before = (home / ".shadow" / "board.json").read_bytes()

            repo_only = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--repo",
                    str(repo),
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(repo_only.returncode, 0)
            self.assertIn("machine-local acceptance requires both", repo_only.stderr)
            self.assertIn("--entity ID --repo PATH", repo_only.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(target.read_bytes(), target_before)
            self.assertEqual(sibling.read_bytes(), sibling_before)
            self.assertEqual(wrong.read_bytes(), wrong_before)
            self.assertEqual((home / ".shadow" / "board.json").read_bytes(), board_before)

            entity_only = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    entity,
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(entity_only.returncode, 0)
            self.assertIn("also requires --repo", entity_only.stderr)
            self.assertFalse(marker.exists())

            non_git = root / "not-git"
            non_git.mkdir()
            non_git_source = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    entity,
                    "--repo",
                    str(non_git),
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(non_git_source.returncode, 0)
            self.assertIn("--repo must name a Git source checkout", non_git_source.stderr)
            self.assertFalse(marker.exists())

            wrong_owner = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    entity,
                    "--repo",
                    str(repo),
                    "--row",
                    "~aa11",
                    "--by",
                    "other-seat",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(wrong_owner.returncode, 0)
            self.assertIn("claimed by local-seat, not other-seat", wrong_owner.stderr)
            self.assertFalse(marker.exists())

            wrong_selection = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    wrong_entity,
                    "--repo",
                    str(repo),
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(wrong_selection.returncode, 0)
            self.assertIn("no task carries ~aa11", wrong_selection.stderr)
            self.assertFalse(marker.exists())

            accepted = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    entity,
                    "--repo",
                    str(repo),
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            target_text = target.read_text(encoding="utf-8")
            accepted_head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertIn("[completed] prove local authority ~aa11", target_text)
            self.assertIn("~aa11 PROOF python3 proof.py", target_text)
            self.assertIn(
                f"~aa11 SOURCE github.com/example/source HEAD "
                f"{accepted_head} "
                "-> proof and final lint (accept)",
                target_text,
            )
            self.assertEqual(sibling.read_bytes(), sibling_before)
            self.assertEqual(board.entity_state(target, home=home)["claims"], [])
            self.assertEqual(
                [claim["row"] for claim in board.entity_state(sibling, home=home)["claims"]],
                ["~aa11"],
            )
            self.assertEqual(marker.read_text(encoding="utf-8"), "ran\n")
            self.assertEqual(proof_file.read_text(encoding="utf-8"), "dirty\n")

    def test_moving_source_head_cannot_change_local_final_lint_or_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            repo = root / "dev" / "moving-source"
            repo.mkdir(parents=True)
            (repo / "move_head.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "import subprocess\n"
                "source = Path(os.environ['LIVE_SOURCE_REPO'])\n"
                "(source / 'move_head.py').unlink()\n"
                "subprocess.run(['git', '-C', str(source), 'add', '-u'], check=True)\n"
                "subprocess.run(\n"
                "    ['git', '-C', str(source), 'commit', '--quiet', '-m',\n"
                "     'move live source head'],\n"
                "    check=True,\n"
                ")\n",
                encoding="utf-8",
            )
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("remote", "add", "origin", "https://github.com/example/moving-head.git"),
                ("add", "move_head.py"),
                ("commit", "--quiet", "-m", "seed moving proof"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            frozen_head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            plan = home / ".shadow" / "plans" / "moving-source" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                plan_with_origin("github.com/example/moving-head")
                .replace("cmd true", "cmd python3 move_head.py", 1)
                .replace("[pending]", "[in_progress]", 1),
                encoding="utf-8",
            )
            board.reconcile(
                [
                    {
                        "plan": str(plan),
                        "project": "moving",
                        "priority": 1,
                        "candidates": ["~aa11"],
                    }
                ],
                [],
                home=home,
            )
            board.claim(
                plan,
                "~aa11",
                "local-seat",
                project="moving",
                priority=1,
                home=home,
            )
            entity = board.entity_state(plan, home=home)["entity"]["id"]

            accepted = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    entity,
                    "--repo",
                    str(repo),
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "LIVE_SOURCE_REPO": str(repo),
                },
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            moved_head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertNotEqual(moved_head, frozen_head)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("[completed] prove local authority ~aa11", text)
            self.assertIn(
                f"~aa11 SOURCE github.com/example/moving-head HEAD {frozen_head} "
                "-> proof and final lint (accept)",
                text,
            )
            self.assertNotIn(
                f"~aa11 SOURCE github.com/example/moving-head HEAD {moved_head}",
                text,
            )
            self.assertEqual(board.entity_state(plan, home=home)["claims"], [])

    def test_detached_proof_cannot_move_the_accepted_source_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            repo = root / "dev" / "detached-head-source"
            repo.mkdir(parents=True)
            (repo / "proof.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "import subprocess\n"
                "subprocess.run(\n"
                "    ['git', 'reset', '--hard', os.environ['OTHER_SOURCE_HEAD']],\n"
                "    check=True,\n"
                "    stdout=subprocess.DEVNULL,\n"
                ")\n"
                "raise SystemExit(\n"
                "    0\n"
                "    if Path('proof.txt').read_text(encoding='utf-8') == 'other\\n'\n"
                "    else 1\n"
                ")\n",
                encoding="utf-8",
            )
            (repo / "proof.txt").write_text("frozen\n", encoding="utf-8")
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                (
                    "remote",
                    "add",
                    "origin",
                    "https://github.com/example/detached-head.git",
                ),
                ("add", "proof.py", "proof.txt"),
                ("commit", "--quiet", "-m", "seed frozen proof"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            frozen_head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (repo / "proof.txt").write_text("other\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "proof.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "--quiet", "-m", "other proof"],
                check=True,
            )
            other_head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", str(repo), "reset", "--hard", frozen_head],
                capture_output=True,
                text=True,
                check=True,
            )
            plan = home / ".shadow" / "plans" / "detached-head" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                plan_with_origin("github.com/example/detached-head")
                .replace("cmd true", "cmd python3 proof.py", 1)
                .replace("[pending]", "[in_progress]", 1),
                encoding="utf-8",
            )
            board.reconcile(
                [
                    {
                        "plan": str(plan),
                        "project": "detached",
                        "priority": 1,
                        "candidates": ["~aa11"],
                    }
                ],
                [],
                home=home,
            )
            board.claim(
                plan,
                "~aa11",
                "local-seat",
                project="detached",
                priority=1,
                home=home,
            )
            entity = board.entity_state(plan, home=home)["entity"]["id"]
            plan_before = plan.read_bytes()
            board_before = (home / ".shadow" / "board.json").read_bytes()

            accepted = subprocess.run(
                [
                    str(ROOT / "bin" / "shadow"),
                    "accept",
                    "--entity",
                    entity,
                    "--repo",
                    str(repo),
                    "--row",
                    "~aa11",
                    "--by",
                    "local-seat",
                ],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "OTHER_SOURCE_HEAD": other_head,
                },
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(accepted.returncode, 1, accepted.stdout + accepted.stderr)
            self.assertIn(
                "proof did not pass from the detached source checkout",
                accepted.stderr,
            )
            self.assertEqual(plan.read_bytes(), plan_before)
            self.assertEqual(
                (home / ".shadow" / "board.json").read_bytes(),
                board_before,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                frozen_head,
            )
            self.assertEqual(
                [
                    claim["row"]
                    for claim in board.entity_state(plan, home=home)["claims"]
                ],
                ["~aa11"],
            )
