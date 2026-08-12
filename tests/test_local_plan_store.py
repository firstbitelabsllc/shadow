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


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402


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
            compacted = plan.read_text(encoding="utf-8")
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

    def test_lint_and_accept_run_a_local_plan_against_its_source_checkout(self) -> None:
        """A private authority still proves work from its registered source repo.

        The local plan deliberately has no Git checkout of its own.  A public
        `shadow lint --repo` and `shadow accept --repo` must therefore use the
        clean source checkout for the proof while leaving the completed PLAN
        private to this computer.
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
                PLAN.replace("cmd true", "cmd python3 proof.py", 1).replace("[pending]", "[in_progress]", 1),
                encoding="utf-8",
            )
            board.reconcile(
                [{"plan": str(plan), "project": "widget", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            board.claim(plan, "~aa11", "local-seat", project="widget", priority=2, home=home)
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
                str(ROOT / "bin" / "shadow"), "accept", "--repo", str(repo),
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
            self.assertIn("proof did not pass in a clean source checkout", failed.stderr)
            self.assertEqual(plan.read_text(encoding="utf-8"), before)
            self.assertEqual(len(board.entity_state(plan, home=home)["claims"]), 1)

            (repo / "proof.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "proof.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "fix proof"], check=True)
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
            self.assertEqual(board.entity_state(plan, home=home)["claims"], [])
            self.assertEqual(subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True, text=True, check=False,
            ).stdout, "")
