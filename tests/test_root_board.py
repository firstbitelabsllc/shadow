from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
BOARD_MODULE = ROOT / "scripts" / "shadow_root_board.py"
PROOF_SENTINEL = "PROOF-MUST-NOT-ENTER-THE-BOARD"
sys.path.insert(0, str(ROOT / "scripts"))


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise AssertionError(result.stderr)


def project(
    root: Path,
    sentinel: str = "TASK-BODY-MUST-NOT-ENTER-THE-BOARD",
    *,
    name: str = "project",
    display_name: str | None = None,
    priority: int = 2,
    first_proof: str = f"cmd python3 -c \"print('{PROOF_SENTINEL}')\"",
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
    git(repo, "commit", "--quiet", "-m", "seed")
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


class PublicIdentityNeverCarriesCredentials(unittest.TestCase):
    def test_remote_query_and_fragment_never_change_or_leak_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            secret = "AKIA" + "IOSFODNN7EXAMPLE"
            git(repo, "remote", "add", "origin", f"https://github.com/org/project.git?token={secret}")

            first = importlib.util.spec_from_file_location("shadow_identity", BOARD_MODULE)
            module = importlib.util.module_from_spec(first)
            assert first and first.loader
            sys.modules[first.name] = module
            first.loader.exec_module(module)
            before = module.entity_id(repo / "PLAN.md")
            locator = module.public_plan_locator(repo / "PLAN.md")
            git(
                repo,
                "remote",
                "set-url",
                "origin",
                "https://github.com/org/project.git?token=rotated#private",
            )

            self.assertEqual(module.entity_id(repo / "PLAN.md"), before)
            self.assertEqual(module.normalized_origin(
                f"https://github.com/org/project.git?token={secret}#private"
            ), "github.com/org/project")
            self.assertNotIn(secret, locator)
            self.assertNotIn("token=", locator)

    def test_default_remote_ports_do_not_split_one_logical_repository(self) -> None:
        spec = importlib.util.spec_from_file_location("shadow_default_ports", BOARD_MODULE)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        self.assertEqual(
            module.normalized_origin("ssh://git@github.com:22/org/repo.git"),
            module.normalized_origin("git@github.com:org/repo.git"),
        )
        self.assertEqual(
            module.normalized_origin("https://github.com:443/org/repo.git"),
            module.normalized_origin("https://github.com/org/repo.git"),
        )
        self.assertEqual(
            module.normalized_origin("http://example.test:80/org/repo.git"),
            module.normalized_origin("http://example.test/org/repo.git"),
        )

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
            spec = importlib.util.spec_from_file_location("shadow_local_remotes", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            self.assertNotEqual(
                module.entity_id(left / "PLAN.md"),
                module.entity_id(right / "PLAN.md"),
            )
            git(right, "remote", "set-url", "origin", str(left_parent / "forge.git"))
            self.assertEqual(
                module.entity_id(left / "PLAN.md"),
                module.entity_id(right / "PLAN.md"),
            )

    def test_git_introspection_failure_never_becomes_a_checkout_path_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = project(Path(tmp))
            spec = importlib.util.spec_from_file_location("shadow_git_failure", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            original = module._git
            module._git = lambda *_args: subprocess.CompletedProcess([], 124, "", "timed out")
            try:
                with self.assertRaisesRegex(
                    module.BoardError,
                    "project Git identity could not be read",
                ):
                    module.entity_id(repo / "PLAN.md")
            finally:
                module._git = original

    def test_secret_shaped_origin_path_uses_an_opaque_public_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = project(root)
            secret = "ghp_" + "A" * 24
            git(repo, "remote", "add", "origin", f"https://github.com/org/{secret}/repo.git")
            spec = importlib.util.spec_from_file_location("shadow_secret_locator", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            locator = module.public_plan_locator(repo / "PLAN.md")

            self.assertNotIn(secret, locator)
            self.assertRegex(locator, r"^entity@[0-9a-f]{8}/PLAN\.md$")

    def test_owner_is_public_safe_before_it_can_enter_the_board(self) -> None:
        spec = importlib.util.spec_from_file_location("shadow_owner", BOARD_MODULE)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
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
                module.validate_owner(owner)


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
                env={**os.environ, "HOME": str(home)},
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
            self.assertEqual(receipt["path"], "shadow/PLAN.md")
            self.assertTrue(receipt["shadowed_by"])
            self.assertIn("registered", receipt["reason"])
            self.assertNotIn(str(Path(tmp)), json.dumps(receipt))

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
            canonical = project(portfolio, name="shared", display_name="shared")
            duplicate = project(
                portfolio, name="shared-worktree", display_name="stale-shared"
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

            spec = importlib.util.spec_from_file_location("shadow_board_recovery", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            observed = module.ensure(home=home)

            restored = board(home)
            self.assertEqual(restored, before)
            self.assertEqual(observed, before)
            self.assertEqual(restored["claims"][0]["owner"], "seat-a")

    def test_partial_git_stale_lock_and_loose_modes_recover_privately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            board_root = home / ".shadow"
            (board_root / ".git").mkdir(parents=True)
            spec = importlib.util.spec_from_file_location("shadow_board_partial_git", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            initialized = module.ensure(home=home)
            self.assertEqual(initialized["revision"], 0)
            (board_root / ".git" / "index.lock").write_bytes(b"")
            os.chmod(board_root, 0o755)
            os.chmod(board_root / "board.json", 0o644)

            observed = module.ensure(home=home)

            self.assertEqual(observed, initialized)
            self.assertFalse((board_root / ".git" / "index.lock").exists())
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
            spec = importlib.util.spec_from_file_location("shadow_board_symlink_root", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

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
            spec = importlib.util.spec_from_file_location("shadow_root_board", BOARD_MODULE)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
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


if __name__ == "__main__":
    unittest.main()
