from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from browser import server


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2
- Outcome ID: ship-demo
- Outcome Revision: 1
- Outcome Updated At: 2026-08-03T03:00:00Z
- Outcome State: working
- Outcome: Ship the demo.
- Next: Run the next bounded check.

## Tasks

### Demo
- [pending] Run the next bounded check ~aa11 | proof: read tests/test_config_defaults.py -> passes
- [pending] Demo closes ~bb22 (DoD) | proof: read demo -> visible
"""


def git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
    for args in (
        ("init", "--quiet"),
        ("config", "user.email", "shadow-test@example.invalid"),
        ("config", "user.name", "Shadow Test"),
        ("add", "PLAN.md"),
        ("commit", "--quiet", "-m", "seed"),
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    return repo


def run_config(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "config", "--explain", "--json", *args],
        cwd=repo,
        env={**os.environ, "SHADOW_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )


class ConfigDefaultsTests(unittest.TestCase):
    def test_this_repositorys_plan_enters_its_own_computer_board(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            repo = home_path / "Development" / "shadow"
            repo.mkdir(parents=True)
            (repo / "PLAN.md").write_text(
                (ROOT / "PLAN.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("add", "PLAN.md"),
                ("commit", "--quiet", "-m", "seed"),
            ):
                subprocess.run(["git", "-C", str(repo), *args], check=True)
            scratch = home_path / "blank"
            scratch.mkdir()
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in {"SHADOW_PORTFOLIO_ROOT", "SHADOW_DEV_ROOT"}
            }
            env["HOME"] = home
            result = subprocess.run(
                [str(CLI), "status", "--json"],
                cwd=scratch,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            entities = report["root_board"]["entities"]
            self.assertTrue(
                any(entity["project"] == "shadow" for entity in entities),
                "Shadow's shipped PLAN.md must be importable by Shadow itself",
            )

    def test_an_invalid_priority_names_the_offending_plan(self) -> None:
        with (
            tempfile.TemporaryDirectory() as dirname,
            tempfile.TemporaryDirectory() as home,
        ):
            home_path = Path(home)
            root = home_path / "Development"
            broken = root / "broken"
            broken.mkdir(parents=True)
            (broken / "PLAN.md").write_text(
                PLAN.replace("- Priority: 2", "- Priority: urgent"),
                encoding="utf-8",
            )
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in {"SHADOW_PORTFOLIO_ROOT", "SHADOW_DEV_ROOT"}
            }
            env["HOME"] = home
            result = subprocess.run(
                [str(CLI), "status", "--json"],
                cwd=Path(dirname),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("broken/PLAN.md: project Priority must be 1-5", result.stderr)

    def test_status_uses_dev_root_env_and_cli_flag_wins(self) -> None:
        with (
            tempfile.TemporaryDirectory() as dirname,
            tempfile.TemporaryDirectory() as override,
            tempfile.TemporaryDirectory() as home,
        ):
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = subprocess.run(
                [str(CLI), "status", "--json"],
                cwd=ROOT,
                env={**os.environ, "HOME": home, "SHADOW_DEV_ROOT": str(root)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["plans"], [])
            self.assertEqual(report["v4_plans"][0]["project"], "demo")

            result = subprocess.run(
                [str(CLI), "status", "--json", "--root", override],
                cwd=ROOT,
                env={**os.environ, "HOME": home, "SHADOW_DEV_ROOT": str(root)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["plans"], [])
            self.assertEqual(report["v4_plans"][0]["project"], "demo")

    def test_browser_defaults_use_environment_and_flags_override(self) -> None:
        with tempfile.TemporaryDirectory() as portfolio, patch.dict(
            os.environ,
            {
                "SHADOW_PORTFOLIO_ROOT": portfolio,
                "SHADOW_DEV_ROOT": "/tmp/losing-legacy-root",
                "SHADOW_BROWSER_HOST": "localhost",
                "SHADOW_BROWSER_PORT": "8123",
            },
            clear=False,
        ):
            args = server.parser().parse_args([])
            self.assertEqual(args.root, str(Path(portfolio).resolve()))
            self.assertEqual(args.host, "localhost")
            self.assertEqual(args.port, 8123)

            args = server.parser().parse_args(
                ["--root", "/tmp/flag-root", "--host", "127.0.0.1", "--port", "8124"]
            )
            self.assertEqual(args.root, "/tmp/flag-root")
            self.assertEqual(args.host, "127.0.0.1")
            self.assertEqual(args.port, 8124)


class RepoLocalConfigDefaults(unittest.TestCase):
    def test_one_repo_local_config_is_read_from_the_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = git_repo(root)
            nested = repo / "nested" / "work"
            nested.mkdir(parents=True)
            (root / "shadow.yaml").write_text("not: this one\n", encoding="utf-8")
            (repo / "shadow.yaml").write_text("version: 1\n", encoding="utf-8")

            result = run_config(nested)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "schema": "shadow.config.explain.v1",
                    "source": "shadow.yaml",
                    "version": 1,
                    "bindings": {},
                },
            )

    def test_no_config_uses_builtin_defaults_without_creating_state(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = git_repo(Path(dirname))
            before = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain=v1", "-z"],
                capture_output=True,
                check=True,
            ).stdout

            result = run_config(repo)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "schema": "shadow.config.explain.v1",
                    "source": "built-in",
                    "version": 1,
                    "bindings": {},
                },
            )
            self.assertFalse((repo / "shadow.yaml").exists())
            self.assertFalse((repo / ".shadow").exists())
            after = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain=v1", "-z"],
                capture_output=True,
                check=True,
            ).stdout
            self.assertEqual(after, before)


class TheSubsetRefusesWhatItCannotParse(unittest.TestCase):
    def test_supported_comments_do_not_expand_the_subset(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = git_repo(Path(dirname))
            (repo / "shadow.yaml").write_text(
                "# repository declaration\n\nversion: 1 # current schema\n",
                encoding="utf-8",
            )

            result = run_config(repo)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["version"], 1)

    def test_unsupported_yaml_is_refused_at_the_first_offending_line(self) -> None:
        cases = {
            "document marker": ("---\nversion: 1\n", 1),
            "quoted scalar": ('version: "1"\n', 1),
            "flow syntax": ("version: [1]\n", 1),
            "tab separator": ("version:\t1\n", 1),
            "nested mapping": ("version:\n  major: 1\n", 1),
            "sequence": ("version: 1\nleads:\n  - codex\n", 2),
            "unknown key": ("# header\nversion: 1\ntaste: taste\n", 3),
            "duplicate key": ("version: 1\nversion: 1\n", 2),
        }
        for name, (content, line) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as dirname:
                repo = git_repo(Path(dirname))
                (repo / "shadow.yaml").write_text(content, encoding="utf-8")

                result = run_config(repo)

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(f"shadow.yaml:{line}:", result.stderr)


if __name__ == "__main__":
    unittest.main()
