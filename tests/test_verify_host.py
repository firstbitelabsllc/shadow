"""The host verifier must be able to fail.

`shadow doctor` answers "is it installed". Every one of its host checks is an
existence check, and the failure this milestone cares about slips past all of
them: a host that has the files and still opens cold, without the skill, asking
which project to attach to.

So every check here is proven by breaking the thing it guards. A verifier that
cannot go red is the same class of defect as the three false greens this repo
shipped and later found: a promise nothing checks.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-verify-host.sh"


PLAN = """# Fixture

## Brief

- Project: fixture
- Mode: ship

## Tasks

### M1 — live
- [pending] ship the cold activation verifier from a clean clone ~aa11 | proof: cmd true

## Progress

- 2026-08-09T00:00:00Z NOTE seeded
"""


def run(home: Path, host: str = "claude-code", path: str | None = None,
        live: bool = False, by: str | None = None,
        timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # A scratch HOME has no ~/Development, so the board check would fail for a
    # reason that has nothing to do with the host's wiring. Point the portfolio
    # at a directory that owns one plan; the verifier is what is under test.
    portfolio = home / "portfolio" / "project"
    if not portfolio.exists():
        portfolio.mkdir(parents=True)
        (portfolio / "PLAN.md").write_text(PLAN, encoding="utf-8")
    # A cold session types `shadow`, so a wired host has this checkout's bin on
    # PATH. The fixture has to say so, or the verifier is right to go red.
    if path is None:
        path = f"{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
    command = ["bash", str(SCRIPT), "--host", host]
    if live:
        command.append("--live")
    if by:
        command.extend(["--by", by])
    if timeout_seconds is not None:
        command.extend(["--timeout-seconds", str(timeout_seconds)])
    env = {**os.environ, "HOME": str(home), "PATH": path,
           "SHADOW_PORTFOLIO_ROOT": str(home / "portfolio")}
    env.update(extra_env or {})
    return subprocess.run(
        command,
        capture_output=True, text=True, check=False,
        env=env,
    )


def wired(home: Path, host: str = "claude-code") -> None:
    """A correctly wired host: mount plus a current standing goal."""
    mount = {"claude-code": ".claude/skills", "codex": ".agents/skills",
             "cursor": ".cursor/skills", "grok": ".grok/skills"}[host]
    (home / mount).mkdir(parents=True, exist_ok=True)
    (home / mount / "shadow").symlink_to(ROOT, target_is_directory=True)
    directive = {
        "claude-code": ".claude/CLAUDE.md",
        "codex": ".codex/AGENTS.md",
        "grok": ".grok/AGENTS.md",
    }.get(host)
    if directive:
        path = home / directive
        path.parent.mkdir(parents=True, exist_ok=True)
        block = subprocess.run([str(ROOT / "bin" / "shadow"), "goal"],
                               capture_output=True, text=True, check=True).stdout.strip()
        path.write_text(f"# my rules\n\nkeep these\n\n{block}\n", encoding="utf-8")


def add_dirty_managed_plan(home: Path) -> None:
    """Add one unrelated Git plan whose remote-claim health is unavailable."""
    repo = home / "portfolio" / "unrelated"
    repo.mkdir(parents=True)
    plan = repo / "PLAN.md"
    plan.write_text(
        PLAN.replace("# Fixture", "# Unrelated")
        .replace("- Project: fixture", "- Project: unrelated")
        .replace("~aa11", "~bb11"),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "PLAN.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Verifier Test",
            "-c",
            "user.email=verifier@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )
    remote = home / "unrelated.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(remote)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "-q", "-u", "origin", "main"],
        check=True,
    )
    plan.write_text(plan.read_text(encoding="utf-8") + "\n<!-- dirty -->\n")


class AWiredHostPasses(unittest.TestCase):
    def test_the_happy_path_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            result = run(home)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("wiring verified", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)

    def test_a_wired_grok_host_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home, "grok")
            result = run(home, host="grok")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("wiring verified", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)
            self.assertIn("standing goal is present and current", result.stdout)

    def test_the_session_check_is_skipped_not_silently_passed(self) -> None:
        # It costs the owner's quota, so it must never run by default — and it
        # must say so, rather than leaving a green run implying it happened.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            self.assertIn("[SKIP] session check", run(home).stdout)


class EveryCheckCanFail(unittest.TestCase):
    def _broken(self, mutate) -> subprocess.CompletedProcess[str]:
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            mutate(home)
            return run(home)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_mount_fails(self) -> None:
        result = self._broken(lambda home: (home / ".claude/skills/shadow").unlink())
        self.assertEqual(result.returncode, 1)
        self.assertIn("no skill mount", result.stdout)

    def test_a_mount_pointing_at_another_checkout_fails(self) -> None:
        def mutate(home: Path) -> None:
            (home / ".claude/skills/shadow").unlink()
            other = home / "another-clone"
            other.mkdir()
            (other / "SKILL.md").write_text("# not this one\n", encoding="utf-8")
            (home / ".claude/skills/shadow").symlink_to(other, target_is_directory=True)

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("another checkout is serving this host", result.stdout)

    def test_a_competing_skill_in_another_root_fails(self) -> None:
        # Host loaders take the first match, so a same-named skill in another
        # root wins silently and forever.
        def mutate(home: Path) -> None:
            other = home / ".agents" / "skills"
            other.mkdir(parents=True)
            impostor = home / "impostor"
            impostor.mkdir()
            (other / "shadow").symlink_to(impostor, target_is_directory=True)

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("one of them is stale", result.stdout)

    def test_a_skill_whose_frontmatter_a_loader_cannot_use_fails(self) -> None:
        # Opening with `---` is not the same as parsing. A block that closes
        # without a description is dropped by the loader without a word, and
        # "SKILL.md exists" reports nothing about that.
        def mutate(home: Path) -> None:
            (home / ".claude/skills/shadow").unlink()
            damaged = home / "damaged"
            damaged.mkdir()
            (damaged / "SKILL.md").write_text("---\nname: shadow\n---\n\n# Shadow\n",
                                              encoding="utf-8")
            (home / ".claude/skills/shadow").symlink_to(damaged, target_is_directory=True)

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("a loader would drop the skill", result.stdout)

    def test_shadow_missing_from_path_fails(self) -> None:
        # The installer can link into a directory the host never sees. Every
        # file is in place and the session's first command is not found.
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            empty = home / "empty-bin"
            empty.mkdir()
            result = run(home, path=f"{empty}{os.pathsep}/usr/bin{os.pathsep}/bin")
            self.assertEqual(result.returncode, 1)
            self.assertIn("first command is not found", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_path_shadow_from_another_checkout_fails(self) -> None:
        # Mount and directive can both point here while `shadow` earlier on
        # PATH belongs to another clone — the session reads one version's law
        # and runs another's board.
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            other = home / "other-bin"
            other.mkdir()
            shim = other / "shadow"
            shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            shim.chmod(0o755)
            result = run(home, path=f"{other}{os.pathsep}{ROOT / 'bin'}"
                                    f"{os.pathsep}{os.environ.get('PATH', '')}")
            self.assertEqual(result.returncode, 1)
            self.assertIn("another checkout", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_directive_fails_with_the_command_that_fixes_it(self) -> None:
        result = self._broken(lambda home: (home / ".claude/CLAUDE.md").unlink())
        self.assertEqual(result.returncode, 1)
        self.assertIn("shadow goal --install", result.stdout)

    def test_two_copies_of_the_standing_goal_fail(self) -> None:
        # The exact false green the doctor check had: append twice, and a
        # substring test says "current" while the host reads the stale one.
        def mutate(home: Path) -> None:
            path = home / ".claude/CLAUDE.md"
            block = subprocess.run([str(ROOT / "bin" / "shadow"), "goal"],
                                   capture_output=True, text=True, check=True).stdout.strip()
            path.write_text(path.read_text(encoding="utf-8") + "\n" + block + "\n", encoding="utf-8")

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("reads the first one", result.stdout)

    def test_an_empty_board_fails(self) -> None:
        # THE POINT of the whole milestone. Files can all be in place and the
        # session still opens cold with nothing to take — which is when a host
        # asks "which project?", the one question this exists to prevent.
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            wired(home)
            (home / "nothing").mkdir()
            result = subprocess.run(
                ["bash", str(SCRIPT), "--host", "claude-code"],
                capture_output=True, text=True, check=False,
                env={**os.environ, "HOME": str(home),
                     "PATH": f"{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
                     "SHADOW_PORTFOLIO_ROOT": str(home / "nothing")},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("a session would have nothing to take", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_board_with_only_resume_none_fails(self) -> None:
        # A syntactically present Resume line is not work. The verifier used
        # to accept `Resume: none`, which let a cold host pass while every
        # checkpoint on the board was blocked.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            project = home / "portfolio" / "project"
            project.mkdir(parents=True)
            project.joinpath("PLAN.md").write_text(
                PLAN.replace(
                    "- [pending] ship the cold activation verifier from a clean clone ~aa11 | proof: cmd true",
                    "- [blocked] ship the cold activation verifier from a clean clone ~aa11 | proof: gate owner resume: credentials arrive",
                ).replace(
                    "## Progress",
                    "## Deferred\n\n"
                    "- a row ~aa11 | credentials are absent | wake: credentials arrive\n\n"
                    "## Progress",
                ),
                encoding="utf-8",
            )
            result = run(home)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("no reachable resume checkpoint", result.stdout)

    def test_a_last_good_board_does_not_hide_a_failed_refresh(self) -> None:
        # A cold session must not treat stale authority as current merely
        # because the previous board still contains a reachable row.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            self.assertEqual(run(home).returncode, 0)
            plan = home / "portfolio" / "project" / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "- Mode: ship", "- Mode: invalid"
                ),
                encoding="utf-8",
            )
            result = run(home)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("board refresh fails", result.stdout)

    def test_unrelated_plan_health_does_not_hide_a_reachable_checkpoint(self) -> None:
        # `shadow status` exits 1 when any registered plan cannot authenticate
        # remote claims. That is important portfolio health, but it is not a
        # failed refresh when the current seat still has fresh board facts and
        # one reachable checkpoint. The host verifier must distinguish those
        # cases or one dirty sibling checkout disables every cold host.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            add_dirty_managed_plan(home)

            result = run(home)

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("reachable from an unrelated directory", result.stdout)
            self.assertIn("unrelated plan health", result.stdout)

    def test_a_stale_standing_goal_fails(self) -> None:
        def mutate(home: Path) -> None:
            path = home / ".claude/CLAUDE.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("shadow accept", "shadow flip"),
                encoding="utf-8")

        result = self._broken(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout)


class CursorIsHonestAboutWhatItCannotCheck(unittest.TestCase):
    def test_cursor_skips_the_directive_instead_of_inventing_a_path(self) -> None:
        # Its user rules live in application settings, not a file. Asserting
        # ~/.cursor/rules/shadow.md would invent a convention and then report
        # success for wiring that does nothing.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home, "cursor")
            result = run(home, "cursor")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("cold directive activation is unsupported", result.stdout)
            self.assertNotIn(".cursor/rules", result.stdout)


class LiveSessionEvidenceIsDynamicAndUncoached(unittest.TestCase):
    def _fake_host(self, home: Path, name: str, body: str) -> str:
        fake_bin = home / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        command = fake_bin / name
        command.write_text("#!/bin/sh\nset -eu\n" + body + "\n", encoding="utf-8")
        command.chmod(0o755)
        return f"{fake_bin}{os.pathsep}{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"

    def test_a_richer_answer_passes_when_all_dynamic_board_facts_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            prompt = home / "prompt.txt"
            cwd = home / "cwd.txt"
            path = self._fake_host(
                home,
                "claude",
                """printf '%s' "$*" > "$SHADOW_TEST_PROMPT"
pwd > "$SHADOW_TEST_CWD"
printf '%s\n' 'For fixture, I am finishing the verifier that activates cold hosts from a fresh checkout.'""",
            )
            result = run(
                home,
                path=path,
                live=True,
                extra_env={"SHADOW_TEST_PROMPT": str(prompt), "SHADOW_TEST_CWD": str(cwd)},
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)
            asked = prompt.read_text(encoding="utf-8")
            self.assertNotIn("shadow status", asked)
            self.assertNotIn("root-board", asked)
            self.assertNotIn("project slug", asked)
            self.assertNotIn("resume checkpoint", asked)
            self.assertNotIn("fixture", asked)
            self.assertNotIn("~aa11", asked)
            self.assertIn("seat claude", asked)
            self.assertIn("--no-session-persistence", asked)
            self.assertIn("--permission-mode plan", asked)
            self.assertNotEqual(cwd.read_text(encoding="utf-8").strip(), str(ROOT))

    def test_unrelated_plan_health_does_not_block_the_live_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            add_dirty_managed_plan(home)
            path = self._fake_host(
                home,
                "claude",
                "printf '%s\\n' 'For fixture, I am finishing the verifier that activates cold hosts from a fresh checkout.'",
            )

            result = run(home, path=path, live=True)

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("unrelated plan health", result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_the_named_seats_claim_outranks_another_projects_global_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            first = home / "portfolio" / "alpha"
            owned = home / "portfolio" / "zeta"
            first.mkdir(parents=True)
            owned.mkdir(parents=True)
            first.joinpath("PLAN.md").write_text(
                PLAN.replace("Project: fixture", "Project: alpha").replace(
                    "ship the cold activation verifier from a clean clone",
                    "prepare the unrelated alpha report",
                ),
                encoding="utf-8",
            )
            owned.joinpath("PLAN.md").write_text(
                PLAN.replace("Project: fixture", "Project: zeta").replace(
                    "ship the cold activation verifier from a clean clone",
                    "finish the seat owned zeta verifier",
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q", str(owned)], check=True)
            subprocess.run(["git", "-C", str(owned), "config", "user.name", "Fixture"], check=True)
            subprocess.run(["git", "-C", str(owned), "config", "user.email", "fixture@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(owned), "add", "--", "PLAN.md"], check=True)
            subprocess.run(["git", "-C", str(owned), "commit", "-qm", "seed"], check=True)
            seeded = run(home, by="worker")
            self.assertEqual(seeded.returncode, 0, seeded.stdout)
            claim = subprocess.run(
                [str(ROOT / "bin" / "shadow"), "throw", "--repo", str(owned),
                 "--task", "~aa11", "--by", "worker"],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "HOME": str(home),
                     "PATH": f"{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
                     "SHADOW_PORTFOLIO_ROOT": str(home / "portfolio")},
            )
            self.assertEqual(claim.returncode, 0, claim.stdout + claim.stderr)
            path = self._fake_host(
                home,
                "claude",
                "printf '%s\\n' 'The zeta project is finishing the seat owned zeta verifier.'",
            )
            result = run(home, path=path, live=True, by="worker")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_a_live_host_timeout_is_bounded_and_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(home, "claude", "sleep 30")
            result = run(home, path=path, live=True, timeout_seconds=1)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("timed out after 1 second", result.stdout)
            self.assertIn("inconclusive", result.stdout)

    def test_every_host_exit_drains_its_background_process_group(self) -> None:
        for exit_status in (0, 23):
            with self.subTest(exit_status=exit_status), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                wired(home)
                marker = home / "descendant-terminated.txt"
                path = self._fake_host(
                    home,
                    "claude",
                    f"""marker="$SHADOW_TEST_MARKER"
(
  trap 'printf terminated > "$marker"; exit 0' TERM INT
  while :; do sleep 1; done
) &
printf '%s\\n' 'For fixture, I am finishing the verifier that activates cold hosts from a fresh checkout.'
exit {exit_status}""",
                )
                result = run(
                    home,
                    path=path,
                    live=True,
                    extra_env={"SHADOW_TEST_MARKER": str(marker)},
                )
                self.assertEqual(result.returncode, 0 if exit_status == 0 else 1, result.stdout)
                self.assertEqual(marker.read_text(encoding="utf-8"), "terminated")

    def test_a_humanized_hyphenated_project_slug_is_the_same_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            plan = home / "portfolio" / "project" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(PLAN.replace("Project: fixture", "Project: demo-project"), encoding="utf-8")
            path = self._fake_host(
                home,
                "claude",
                "printf '%s\\n' 'The demo project is finishing the verifier that activates cold hosts from a fresh checkout.'",
            )
            result = run(home, path=path, live=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_the_old_resume_prefix_without_project_identity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(
                home,
                "claude",
                "printf '%s\\n' '[pending] ship the cold activation verifier from a clean clone ~aa11'",
            )
            result = run(home, path=path, live=True)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("did not identify the current project", result.stdout)

    def test_wrong_project_and_vague_or_unrelated_work_each_fail(self) -> None:
        cases = (
            "The another project is shipping its cold activation verifier from a clean clone.",
            "The fixture project has some work in progress.",
            "The fixture project is reviewing an unrelated payment report.",
        )
        for evidence in cases:
            with self.subTest(evidence=evidence), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                wired(home)
                path = self._fake_host(home, "claude", f"printf '%s\\n' '{evidence}'")
                result = run(home, path=path, live=True)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("did not identify the current project", result.stdout)

    def test_any_board_drift_during_the_host_run_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(
                home,
                "claude",
                """"$SHADOW_TEST_REAL" priority --repo "$SHADOW_PORTFOLIO_ROOT/project" --value 2 >/dev/null
printf '%s\n' 'The fixture project is shipping its cold activation verifier from a clean clone.'""",
            )
            result = run(
                home,
                path=path,
                live=True,
                extra_env={"SHADOW_TEST_REAL": str(ROOT / "bin" / "shadow")},
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("result is inconclusive", result.stdout)

    def test_the_host_cannot_mutate_the_board_through_its_shadow_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(
                home,
                "claude",
                """if shadow priority --repo "$SHADOW_PORTFOLIO_ROOT/project" --value 2 >/dev/null 2>&1; then
  exit 41
fi
printf '%s\n' 'The fixture project is shipping its cold activation verifier from a clean clone.'""",
            )
            result = run(home, path=path, live=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_the_cold_host_cannot_load_the_full_json_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(
                home,
                "claude",
                """if shadow status --json >/dev/null 2>&1; then
  exit 41
fi
printf '%s\n' 'For fixture, I am finishing the verifier that activates cold hosts from a fresh checkout.'""",
            )
            result = run(home, path=path, live=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_the_cold_host_can_read_compact_in_flight_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(
                home,
                "claude",
                """shadow status --in-flight --json | grep -q 'shadow.in-flight.v1'
printf '%s\n' 'For fixture, I am finishing the verifier that activates cold hosts from a fresh checkout.'""",
            )
            result = run(home, path=path, live=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_a_nonzero_host_exit_fails_distinctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home)
            path = self._fake_host(home, "claude", "exit 23")
            result = run(home, path=path, live=True)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("session invocation failed", result.stdout)

    def test_codex_matches_only_the_final_message_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home, "codex")
            path = self._fake_host(
                home,
                "codex",
                """out=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--output-last-message' ]; then out="$2"; shift 2; else shift; fi
done
printf '%s\n' 'diagnostic text without evidence'
printf '%s\n' 'For fixture, I am finishing the verifier that activates cold hosts from a fresh checkout.' > "$out"
""",
            )
            result = run(home, host="codex", path=path, live=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("described its current work", result.stdout)

    def test_cursor_live_is_an_explicit_skip_not_a_fake_session_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wired(home, "cursor")
            result = run(home, host="cursor", live=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("live session check is unsupported", result.stdout)


class TheScriptItself(unittest.TestCase):
    def test_an_unknown_host_is_refused(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT), "--host", "emacs"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)

    def test_help_names_both_tiers(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT), "--help"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("offline", result.stdout)
        self.assertIn("--live", result.stdout)
        self.assertIn("--by", result.stdout)
        self.assertIn("--timeout-seconds", result.stdout)


if __name__ == "__main__":
    unittest.main()
