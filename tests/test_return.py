"""Claim return and recovery are explicit, owner-safe lifecycle moves."""

from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_remote_claim as remote_claim  # noqa: E402
import shadow_root_board as board  # noqa: E402
RETURN_SPEC = importlib.util.spec_from_file_location("shadow_return_test", ROOT / "scripts" / "shadow-return.py")
return_mod = importlib.util.module_from_spec(RETURN_SPEC)
assert RETURN_SPEC and RETURN_SPEC.loader
RETURN_SPEC.loader.exec_module(return_mod)

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


def remote_fixture(
    root: Path,
    *,
    proof: str = "read artifact -> correct",
) -> tuple[Path, Path, Path, dict[str, str], dict]:
    repo, home, env = fixture(root)
    plan = repo / "PLAN.md"
    if proof != "read artifact -> correct":
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "proof: read artifact -> correct",
                f"proof: {proof}",
            ),
            encoding="utf-8",
        )
        git(repo, "add", "PLAN.md")
        git(repo, "commit", "--quiet", "-m", "select manual proof")
    remote = root / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-qu", "origin", "HEAD:main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
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
    if claimed.returncode:
        raise AssertionError(claimed.stdout + claimed.stderr)
    receipt = next(
        json.loads(line)
        for line in claimed.stderr.splitlines()
        if line.startswith("{")
    )
    return repo, remote, home, env, receipt


def complete_manual_row(repo: Path, proof: str) -> None:
    plan = repo / "PLAN.md"
    plan.write_text(
        plan.read_text(encoding="utf-8").replace(
            "- [pending] inspect the result ~aa11",
            "- [completed] inspect the result ~aa11",
        )
        + f"\n- 2026-08-22T17:00:00Z ~aa11 PROOF {proof} -> pass\n",
        encoding="utf-8",
    )
    git(repo, "add", "PLAN.md")
    git(repo, "commit", "--quiet", "-m", "record manual completion")


def recovery_command(
    env: dict[str, str], repo: Path, owner: str = "seat-a"
) -> tuple[str, str]:
    observed = run(
        env,
        "status",
        "--root",
        str(repo),
        "--by",
        owner,
        cwd=repo,
    )
    if observed.returncode:
        raise AssertionError(observed.stdout + observed.stderr)
    board_payload = payload(Path(env["HOME"]))
    entity = board_payload["entities"][0]["id"]
    line = next(
        candidate.strip()
        for candidate in observed.stdout.splitlines()
        if candidate.strip().startswith("Recover:")
    )
    return entity, line


class RemoteOnlyManualCompletionRecovery(unittest.TestCase):
    def test_status_command_recovers_published_read_and_gate_claims_idempotently(self) -> None:
        for proof in (
            "read artifact -> correct",
            "gate leo resume: artifact accepted",
        ):
            with self.subTest(proof=proof), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                repo, remote, _home_a, _env_a, receipt = remote_fixture(
                    root, proof=proof
                )
                complete_manual_row(repo, proof)
                git(repo, "push", "-qu", "origin", "HEAD:main")

                second = root / "second"
                subprocess.run(
                    ["git", "clone", "-q", str(remote), str(second)],
                    check=True,
                )
                git(second, "config", "user.email", "shadow-test@example.invalid")
                git(second, "config", "user.name", "Shadow Test")
                home_b = root / "home-b"
                home_b.mkdir()
                env_b = {
                    **os.environ,
                    "HOME": str(home_b),
                    "SHADOW_PORTFOLIO_ROOT": str(second),
                }
                entity, recovery_line = recovery_command(env_b, second)
                self.assertEqual(
                    recovery_line,
                    f"Recover: shadow return --entity {entity} --row '~aa11' --by seat-a",
                )
                projected = run(
                    env_b,
                    "status",
                    "--json",
                    "--root",
                    str(second),
                    cwd=second,
                )
                self.assertEqual(projected.returncode, 0, projected.stderr)
                live_claim = json.loads(projected.stdout)["v4_plans"][0][
                    "live_claims"
                ][0]
                self.assertEqual(live_claim["proof_class"], proof.partition(" ")[0])
                self.assertNotIn("proof", live_claim)

                wrong = run(
                    env_b,
                    "return",
                    "--entity",
                    entity,
                    "--row",
                    "~aa11",
                    "--by",
                    "seat-b",
                    cwd=second,
                )
                self.assertEqual(wrong.returncode, 1, wrong.stdout + wrong.stderr)
                self.assertIn("seat-a", wrong.stderr)

                recovery_argv = shlex.split(recovery_line.removeprefix("Recover: "))
                recovered = run(env_b, *recovery_argv[1:], cwd=second)

                self.assertEqual(
                    recovered.returncode, 0, recovered.stdout + recovered.stderr
                )
                completed_tip = subprocess.run(
                    ["git", "-C", str(remote), "rev-parse", receipt["ref"]],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                stored = json.loads(
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(remote),
                            "show",
                            f"{completed_tip}:claim.json",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout
                )
                self.assertEqual(
                    (stored["state"], stored["reason"]),
                    ("completed", "completed"),
                )
                self.assertEqual(
                    {
                        key: stored[key]
                        for key in ("entity", "project", "row", "owner")
                    },
                    {
                        "entity": entity,
                        "project": "return-fixture",
                        "row": "~aa11",
                        "owner": "seat-a",
                    },
                )
                self.assertEqual(stored["claim"], receipt["claim"])
                self.assertEqual(payload(home_b)["claims"], [])

                repeated = run(env_b, *recovery_argv[1:], cwd=second)

                self.assertEqual(
                    repeated.returncode, 0, repeated.stdout + repeated.stderr
                )
                self.assertEqual(
                    subprocess.run(
                        ["git", "-C", str(remote), "rev-parse", receipt["ref"]],
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout.strip(),
                    completed_tip,
                )
                after = run(
                    env_b,
                    "status",
                    "--root",
                    str(second),
                    "--by",
                    "seat-a",
                    cwd=second,
                )
                self.assertEqual(after.returncode, 0, after.stderr)
                self.assertNotIn("Recover:", after.stdout)

    def test_unpublished_manual_completion_keeps_the_remote_claim_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, remote, _home_a, _env_a, receipt = remote_fixture(root)
            complete_manual_row(repo, "read artifact -> correct")
            home_b = root / "home-b"
            home_b.mkdir()
            env_b = {
                **os.environ,
                "HOME": str(home_b),
                "SHADOW_PORTFOLIO_ROOT": str(repo),
            }
            entity, recovery_line = recovery_command(env_b, repo)
            self.assertEqual(
                recovery_line,
                f"Recover: shadow return --entity {entity} --row '~aa11' --by seat-a",
            )
            recovery_argv = shlex.split(recovery_line.removeprefix("Recover: "))

            refused = run(env_b, *recovery_argv[1:], cwd=repo)

            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("not published", refused.stderr)
            stored = json.loads(
                subprocess.run(
                    ["git", "-C", str(remote), "show", f"{receipt['ref']}:claim.json"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
            )
            self.assertEqual(stored["state"], "acquired")
            self.assertEqual(payload(home_b)["claims"], [])

    def test_reverted_published_manual_completion_keeps_the_remote_claim_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, remote, _home_a, _env_a, receipt = remote_fixture(root)
            complete_manual_row(repo, "read artifact -> correct")
            completed = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            git(repo, "push", "-qu", "origin", "HEAD:main")
            git(repo, "revert", "--no-edit", completed)
            git(repo, "push", "-qu", "origin", "HEAD:main")
            git(repo, "checkout", "--quiet", "-b", "completion-retry", completed)
            git(repo, "config", "branch.completion-retry.remote", "origin")
            git(repo, "config", "branch.completion-retry.merge", "refs/heads/main")
            home_b = root / "home-b"
            home_b.mkdir()
            env_b = {
                **os.environ,
                "HOME": str(home_b),
                "SHADOW_PORTFOLIO_ROOT": str(repo),
            }
            entity, recovery_line = recovery_command(env_b, repo)
            self.assertEqual(
                recovery_line,
                f"Recover: shadow return --entity {entity} --row '~aa11' --by seat-a",
            )
            recovery_argv = shlex.split(recovery_line.removeprefix("Recover: "))

            refused = run(env_b, *recovery_argv[1:], cwd=repo)

            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("no longer carries", refused.stderr)
            stored = json.loads(
                subprocess.run(
                    ["git", "-C", str(remote), "show", f"{receipt['ref']}:claim.json"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
            )
            self.assertEqual(stored["state"], "acquired")
            self.assertEqual(payload(home_b)["claims"], [])

    def test_conflicting_local_owner_cannot_partially_close_the_remote_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, remote, _home_a, _env_a, receipt = remote_fixture(root)
            complete_manual_row(repo, "read artifact -> correct")
            git(repo, "push", "-qu", "origin", "HEAD:main")
            second = root / "second"
            subprocess.run(
                ["git", "clone", "-q", str(remote), str(second)],
                check=True,
            )
            git(second, "config", "user.email", "shadow-test@example.invalid")
            git(second, "config", "user.name", "Shadow Test")
            home_b = root / "home-b"
            home_b.mkdir()
            env_b = {
                **os.environ,
                "HOME": str(home_b),
                "SHADOW_PORTFOLIO_ROOT": str(second),
            }
            entity, recovery_line = recovery_command(env_b, second)
            board.claim(
                second / "PLAN.md",
                "~aa11",
                "seat-b",
                project="return-fixture",
                priority=2,
                home=home_b,
            )
            acquired_tip = subprocess.run(
                ["git", "-C", str(remote), "rev-parse", receipt["ref"]],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            recovery_argv = shlex.split(recovery_line.removeprefix("Recover: "))

            refused = run(env_b, *recovery_argv[1:], cwd=second)

            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("seat-b", refused.stderr)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(remote), "rev-parse", receipt["ref"]],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                acquired_tip,
            )
            stored = json.loads(
                subprocess.run(
                    ["git", "-C", str(remote), "show", f"{receipt['ref']}:claim.json"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
            )
            self.assertEqual(stored["state"], "acquired")
            self.assertEqual(payload(home_b)["claims"][0]["owner"], "seat-b")


class ReturnRequiresTheClaimOwner(unittest.TestCase):
    def test_legacy_local_claim_can_atomically_create_a_released_remote_tip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = fixture(root)
            remote = root / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            git(repo, "remote", "add", "origin", str(remote))
            git(repo, "push", "-qu", "origin", "HEAD:main")
            self.assertEqual(run(env, "status", "--json", cwd=repo).returncode, 0)
            board.claim(
                repo / "PLAN.md", "~aa11", "seat-a",
                project="return-fixture", priority=2, home=home,
            )
            entity = payload(home)["entities"][0]["id"]
            ref = remote_claim.claim_ref(entity, "~aa11")

            returned = run(
                env, "return", "--repo", str(repo), "--row", "~aa11", "--by", "seat-a"
            )

            self.assertEqual(returned.returncode, 0, returned.stderr)
            self.assertEqual(payload(home)["claims"], [])
            stored = subprocess.run(
                ["git", "-C", str(remote), "show", f"{ref}:claim.json"],
                capture_output=True, text=True, check=True,
            )
            receipt = json.loads(stored.stdout)
            self.assertEqual((receipt["state"], receipt["reason"]), ("released", "handback"))

    def test_released_remote_half_state_retries_only_the_local_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = fixture(root)
            remote = root / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            git(repo, "remote", "add", "origin", str(remote))
            git(repo, "push", "-qu", "origin", "HEAD:main")
            claimed = run(
                env, "throw", "--repo", str(repo), "--task", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            receipt = next(json.loads(line) for line in claimed.stderr.splitlines() if line.startswith("{"))
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, env),
                mock.patch.object(return_mod.board, "release", side_effect=board.BoardError("local release failed")),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                first = return_mod.main(
                    ["--repo", str(repo), "--row", "~aa11", "--by", "seat-a"]
                )
            self.assertEqual(first, 1, output.getvalue())
            self.assertEqual(payload(home)["claims"][0]["owner"], "seat-a")
            stored = json.loads(
                subprocess.run(
                    ["git", "-C", str(remote), "show", f"{receipt['ref']}:claim.json"],
                    capture_output=True, text=True, check=True,
                ).stdout
            )
            self.assertEqual(stored["state"], "released")

            retry = run(
                env, "return", "--repo", str(repo), "--row", "~aa11", "--by", "seat-a"
            )
            self.assertEqual(retry.returncode, 0, retry.stderr)
            self.assertEqual(payload(home)["claims"], [])

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

    def test_retired_row_orphan_is_released_by_exact_owner(self) -> None:
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
                    "- [pending] inspect the result ~aa11 | proof: read artifact -> correct\n",
                    "",
                ).replace(" | needs: ~aa11", ""),
                encoding="utf-8",
            )
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "retire claimed row")

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
            self.assertIn("returned ~aa11 (orphan)", recovered.stdout)
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
