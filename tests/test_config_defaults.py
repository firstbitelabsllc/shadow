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

## Tasks

### Demo
- [pending] Run the next bounded check ~aa11 | proof: read tests/test_config_defaults.py -> passes
- [pending] Demo closes ~bb22 (DoD) | proof: read demo -> visible
"""


class ConfigDefaultsTests(unittest.TestCase):
    def test_absent_config_and_reviewed_repo_config_are_both_explainable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            absent = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(repo), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(absent.returncode, 0, absent.stderr)
            absent_payload = json.loads(absent.stdout)
            self.assertEqual(absent_payload["source"], "built-in defaults")
            self.assertEqual(absent_payload["config"]["durability"]["claim_return_minutes"], 480)

            (repo / "shadow.yaml").write_text(
                "method:\n  adversarial_lenses:\n    - privacy\n",
                encoding="utf-8",
            )
            configured = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(repo), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            payload = json.loads(configured.stdout)
            self.assertEqual(payload["source"], "shadow.yaml")
            self.assertEqual(payload["config"]["method"]["adversarial_lenses"], ["privacy"])

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


class TheSubsetRefusesWhatItCannotParse(unittest.TestCase):
    def test_cli_names_the_file_and_line_for_unsupported_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            (repo / "shadow.yaml").write_text(
                "method:\n  adversarial_lenses: [privacy, correctness]\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("shadow.yaml:2:", result.stderr)
        self.assertIn("unsupported YAML", result.stderr)


class NoSelectorKeys(unittest.TestCase):
    def test_provider_model_account_credential_and_equivalent_keys_refuse_at_any_depth(self) -> None:
        forbidden = (
            "provider",
            "MODEL-ID",
            "account_name",
            "credential-file",
            "api_key",
            "access-token",
            "client_secret",
            "host_route",
            "seat_selector",
            "execution_profile",
        )
        for key in forbidden:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory)
                subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
                (repo / "shadow.yaml").write_text(
                    f"leads:\n  codex:\n    {key}: placeholder\n",
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [str(CLI), "config", "--explain", "--repo", str(repo)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("shadow.yaml:3:", result.stderr)
                self.assertIn(f"configuration key '{key}' is refused", result.stderr)
                self.assertNotIn("placeholder", result.stderr)


if __name__ == "__main__":
    unittest.main()
