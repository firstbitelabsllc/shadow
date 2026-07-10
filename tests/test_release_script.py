"""Contract tests for scripts/vidux-release.sh publish propagation."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-release.sh"
TASK_ID = "Release publish gate"


def _run(args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ReleaseScriptTests(unittest.TestCase):
    def _make_repo(self, root: Path) -> tuple[Path, Path]:
        repo = root / "fixture"
        repo.mkdir()
        (repo / "VERSION").write_text("1.2.3\n# retained comment\n", encoding="utf-8")
        (repo / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- test change\n",
            encoding="utf-8",
        )
        (repo / "PLAN.md").write_text(
            "# Fixture Plan\n\n"
            f"- [in_progress] {TASK_ID}\n",
            encoding="utf-8",
        )
        package = {"name": "vidux-release-fixture", "version": "1.2.3", "private": True}
        (repo / "package.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
        package_lock = {
            "name": "vidux-release-fixture",
            "version": "1.2.3",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {
                "": {"name": "vidux-release-fixture", "version": "1.2.3"},
            },
        }
        (repo / "package-lock.json").write_text(
            json.dumps(package_lock, indent=2) + "\n", encoding="utf-8"
        )
        (repo / ".claude-plugin").mkdir()
        (repo / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "vidux-release-fixture", "version": "1.2.3"}, indent=2) + "\n",
            encoding="utf-8",
        )

        for command in (
            ["git", "init"],
            ["git", "branch", "-M", "main"],
            ["git", "config", "user.email", "vidux-test@example.com"],
            ["git", "config", "user.name", "Vidux Test"],
            [
                "git",
                "add",
                "VERSION",
                "CHANGELOG.md",
                "PLAN.md",
                "package.json",
                "package-lock.json",
                ".claude-plugin/plugin.json",
            ],
            ["git", "commit", "-m", "initial"],
        ):
            result = _run(command, cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)

        remote = root / "origin.git"
        result = _run(["git", "init", "--bare", str(remote)])
        self.assertEqual(result.returncode, 0, result.stderr)
        result = _run(["git", "remote", "add", "origin", str(remote)], cwd=repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        return repo, remote

    def _make_fake_ledger(self, root: Path) -> tuple[Path, Path]:
        ledger_log = root / "ledger-args.log"
        ledger_emit = root / "ledger-emit.sh"
        ledger_emit.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" >> \"${LEDGER_LOG:?}\"\n",
            encoding="utf-8",
        )
        ledger_emit.chmod(0o755)
        return ledger_emit, ledger_log

    def _release_env(self, repo: Path, ledger_emit: Path, ledger_log: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["VIDUX_ROOT"] = str(repo)
        env["LEDGER_EMIT"] = str(ledger_emit)
        env["LEDGER_LOG"] = str(ledger_log)
        return env

    def _values_after(self, ledger_lines: list[str], flag: str) -> list[str]:
        values: list[str] = []
        for line in ledger_lines:
            parts = line.split()
            for index, part in enumerate(parts[:-1]):
                if part == flag:
                    values.append(parts[index + 1])
        return values

    def test_apply_emits_publish_rows_around_release_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, remote = self._make_repo(root)
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--bump",
                    "patch",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    TASK_ID,
                    "--proof",
                    "python3 -m unittest tests.test_release_script",
                    "--resume",
                    "resume release follow-up",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            self.assertTrue(ledger_log.exists(), "release did not call the ledger emitter")
            ledger_lines = ledger_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(ledger_lines), 2, ledger_lines)
            joined = "\n".join(ledger_lines)
            self.assertIn("--event publish", joined)
            self.assertIn(f"--repo-path {repo}", joined)
            self.assertIn(f"--task-id {TASK_ID}", joined)
            self.assertIn(f"--plan-path {repo / 'PLAN.md'}", joined)
            self.assertIn("--handoff-status in_progress", ledger_lines[0])
            self.assertIn("--handoff-status done", ledger_lines[1])
            self.assertIn("--resume resume release follow-up", joined)
            self.assertIn("--file VERSION", joined)
            self.assertIn("--file package.json", joined)
            self.assertIn("--file package-lock.json", joined)
            self.assertIn("--file .claude-plugin/plugin.json", joined)
            self.assertIn("--file CHANGELOG.md", joined)
            self.assertIn("--file PLAN.md", joined)
            self.assertIn("--claim VERSION", joined)
            self.assertIn("--claim package.json", joined)
            self.assertIn("--claim package-lock.json", joined)
            self.assertIn("--claim .claude-plugin/plugin.json", joined)
            self.assertIn("--claim CHANGELOG.md", joined)
            self.assertIn("--claim PLAN.md", joined)
            self.assertIn("--claim scripts/vidux-release.sh", joined)
            self.assertTrue(
                set(self._values_after(ledger_lines, "--file")).issubset(
                    set(self._values_after(ledger_lines, "--claim"))
                ),
                ledger_lines,
            )

            self.assertTrue((repo / "VERSION").read_text(encoding="utf-8").startswith("1.2.4\n"))
            self.assertEqual(json.loads((repo / "package.json").read_text())["version"], "1.2.4")
            lock = json.loads((repo / "package-lock.json").read_text())
            self.assertEqual(lock["version"], "1.2.4")
            self.assertEqual(lock["packages"][""]["version"], "1.2.4")
            plugin = json.loads((repo / ".claude-plugin" / "plugin.json").read_text())
            self.assertEqual(plugin["version"], "1.2.4")
            self.assertIn(
                f"Release v1.2.4 for {TASK_ID}: python3 -m unittest tests.test_release_script",
                (repo / "PLAN.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "[handoff=done; resume=resume release follow-up]",
                (repo / "PLAN.md").read_text(encoding="utf-8"),
            )
            tag_result = _run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/tags/v1.2.4"])
            self.assertEqual(tag_result.returncode, 0, tag_result.stderr)

    def test_apply_claims_default_and_extra_changed_files_even_with_custom_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, _remote = self._make_repo(root)
            (repo / "docs").mkdir()
            (repo / "docs" / "release-extra.md").write_text("release extra initial\n", encoding="utf-8")
            result = _run(["git", "add", "docs/release-extra.md"], cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = _run(["git", "commit", "-m", "add release extra"], cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            (repo / "docs" / "release-extra.md").write_text("release extra changed\n", encoding="utf-8")
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--allow-dirty",
                    "--bump",
                    "patch",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    TASK_ID,
                    "--proof",
                    "python3 -m unittest tests.test_release_script",
                    "--resume",
                    "resume release follow-up",
                    "--file",
                    "docs/release-extra.md",
                    "--claim",
                    "docs/manual-claim.md",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            ledger_lines = ledger_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(ledger_lines), 2, ledger_lines)
            files = self._values_after(ledger_lines, "--file")
            claims = self._values_after(ledger_lines, "--claim")
            for expected in [
                "VERSION",
                "package.json",
                "package-lock.json",
                ".claude-plugin/plugin.json",
                "CHANGELOG.md",
                "PLAN.md",
                "docs/release-extra.md",
            ]:
                self.assertIn(expected, files)
                self.assertIn(expected, claims)
            self.assertIn("scripts/vidux-release.sh", claims)
            self.assertIn("docs/manual-claim.md", claims)
            self.assertTrue(set(files).issubset(set(claims)), ledger_lines)
            self.assertIn(
                "docs/release-extra.md",
                _run(["git", "show", "--name-only", "--format=", "HEAD"], cwd=repo).stdout.splitlines(),
            )
            self.assertEqual(_run(["git", "status", "--short"], cwd=repo).stdout.strip(), "")

    def test_apply_refuses_missing_plan_before_mutation_or_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, remote = self._make_repo(root)
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--proof",
                    "proof without owning plan",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--plan-path", result.stderr)
            self.assertFalse(ledger_log.exists(), "ledger should not run after failed propagation preflight")
            self.assertEqual((repo / "VERSION").read_text(encoding="utf-8"), "1.2.3\n# retained comment\n")
            self.assertEqual(_run(["git", "tag"], cwd=repo).stdout.strip(), "")
            self.assertEqual(_run(["git", "--git-dir", str(remote), "tag"]).stdout.strip(), "")

    def test_apply_refuses_missing_task_id_before_mutation_or_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, remote = self._make_repo(root)
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--plan-path",
                    "PLAN.md",
                    "--proof",
                    "proof without task id",
                    "--resume",
                    "resume release follow-up",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--task-id", result.stderr)
            self.assertFalse(ledger_log.exists(), "ledger should not run after failed propagation preflight")
            self.assertEqual((repo / "VERSION").read_text(encoding="utf-8"), "1.2.3\n# retained comment\n")
            self.assertEqual(_run(["git", "tag"], cwd=repo).stdout.strip(), "")
            self.assertEqual(_run(["git", "--git-dir", str(remote), "tag"]).stdout.strip(), "")

    def test_apply_refuses_task_id_absent_from_plan_before_mutation_or_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, remote = self._make_repo(root)
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    "No such row",
                    "--proof",
                    "proof without task row",
                    "--resume",
                    "resume release follow-up",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must appear in --plan-path as a task row", result.stderr)
            self.assertFalse(ledger_log.exists(), "ledger should not run after failed propagation preflight")
            self.assertEqual((repo / "VERSION").read_text(encoding="utf-8"), "1.2.3\n# retained comment\n")
            self.assertEqual(_run(["git", "tag"], cwd=repo).stdout.strip(), "")
            self.assertEqual(_run(["git", "--git-dir", str(remote), "tag"]).stdout.strip(), "")

    def test_apply_refuses_task_id_mentioned_only_in_progress_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, remote = self._make_repo(root)
            (repo / "PLAN.md").write_text(
                "# Fixture Plan\n\n"
                "## Progress\n\n"
                "- [2026-06-02] Ghost release completed in prose only.\n",
                encoding="utf-8",
            )
            result = _run(["git", "add", "PLAN.md"], cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = _run(["git", "commit", "-m", "prose-only ghost release"], cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--plan-path",
                    "PLAN.md",
                    "--task",
                    "Ghost release",
                    "--proof",
                    "proof without task row",
                    "--resume",
                    "resume release follow-up",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must appear in --plan-path as a task row", result.stderr)
            self.assertFalse(ledger_log.exists(), "ledger should not run after failed propagation preflight")
            self.assertEqual((repo / "VERSION").read_text(encoding="utf-8"), "1.2.3\n# retained comment\n")
            self.assertEqual(_run(["git", "tag"], cwd=repo).stdout.strip(), "")
            self.assertEqual(_run(["git", "--git-dir", str(remote), "tag"]).stdout.strip(), "")

    def test_apply_refuses_missing_resume_before_mutation_or_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, remote = self._make_repo(root)
            ledger_emit, ledger_log = self._make_fake_ledger(root)

            result = _run(
                [
                    "bash",
                    str(SCRIPT),
                    "--apply",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    TASK_ID,
                    "--proof",
                    "proof without resume",
                ],
                env=self._release_env(repo, ledger_emit, ledger_log),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--resume", result.stderr)
            self.assertFalse(ledger_log.exists(), "ledger should not run after failed propagation preflight")
            self.assertEqual((repo / "VERSION").read_text(encoding="utf-8"), "1.2.3\n# retained comment\n")
            self.assertEqual(_run(["git", "tag"], cwd=repo).stdout.strip(), "")
            self.assertEqual(_run(["git", "--git-dir", str(remote), "tag"]).stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
