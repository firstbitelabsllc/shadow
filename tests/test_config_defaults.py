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


if __name__ == "__main__":
    unittest.main()
