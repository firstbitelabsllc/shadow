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
LOCAL_CONFIG = Path(".shadow/local.yaml")
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

            initialized = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            (repo / LOCAL_CONFIG).write_text(
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
            self.assertEqual(payload["source"], LOCAL_CONFIG.as_posix())
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
            initialized = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            (repo / LOCAL_CONFIG).write_text(
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
        self.assertIn(".shadow/local.yaml:2:", result.stderr)
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
                initialized = subprocess.run(
                    [str(CLI), "config", "--init-local", "--repo", str(repo)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                (repo / LOCAL_CONFIG).write_text(
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
                self.assertIn(".shadow/local.yaml:3:", result.stderr)
                self.assertIn(f"configuration key '{key}' is refused", result.stderr)
                self.assertNotIn("placeholder", result.stderr)


class TheRecommendedTemplateIsNotEffectiveConfig(unittest.TestCase):
    def test_recommended_template_is_named_but_never_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            (repo / "shadow.example.yaml").write_text(
                "durability:\n  claim_return_minutes: 17\nprovider: ignored-template-sentinel\n",
                encoding="utf-8",
            )
            nested = repo / "nested"
            nested.mkdir()
            before_exclude = (repo / ".git/info/exclude").read_bytes()
            result = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(nested), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["source"], "built-in defaults")
            self.assertEqual(payload["template"], "shadow.example.yaml")
            self.assertEqual(payload["effective"], LOCAL_CONFIG.as_posix())
            self.assertEqual(payload["config"]["durability"]["claim_return_minutes"], 480)
            self.assertEqual((repo / ".git/info/exclude").read_bytes(), before_exclude)
            self.assertFalse((repo / LOCAL_CONFIG).exists())

    def test_clean_clones_receive_the_template_but_never_a_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            first = root / "first"
            second = root / "second"
            source.mkdir()
            subprocess.run(["git", "-C", str(source), "init", "--quiet"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "shadow-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "Shadow Test"], check=True)
            (source / "shadow.example.yaml").write_bytes((ROOT / "shadow.example.yaml").read_bytes())
            subprocess.run(["git", "-C", str(source), "add", "shadow.example.yaml"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "--quiet", "-m", "template"], check=True)
            subprocess.run(["git", "clone", "--quiet", str(source), str(first)], check=True)
            self.assertTrue((first / "shadow.example.yaml").is_file())
            self.assertFalse((first / LOCAL_CONFIG).exists())
            absent = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(first), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(absent.returncode, 0, absent.stderr)
            self.assertEqual(json.loads(absent.stdout)["source"], "built-in defaults")
            initialized = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(first)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertTrue((first / LOCAL_CONFIG).is_file())
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(first), "status", "--porcelain=v1", "--untracked-files=all"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )
            (first / LOCAL_CONFIG).write_text(
                "durability:\n  claim_return_minutes: 17\n", encoding="utf-8"
            )
            subprocess.run(["git", "clone", "--quiet", str(first), str(second)], check=True)
            self.assertTrue((second / "shadow.example.yaml").is_file())
            self.assertFalse((second / LOCAL_CONFIG).exists())


class TheEffectiveConfigIsLocallyIgnored(unittest.TestCase):
    def test_init_creates_only_an_ignored_effective_copy_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo with spaces"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            exclude = repo / ".git/info/exclude"
            exclude.write_text("# keep this comment\n\n\n", encoding="utf-8")
            exclude_before = exclude.read_text(encoding="utf-8")
            nested = repo / "nested"
            nested.mkdir()
            first = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(nested), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            payload = json.loads(first.stdout)
            self.assertTrue(payload["created"])
            self.assertEqual(payload["effective"], LOCAL_CONFIG.as_posix())
            self.assertFalse(payload["tracked"])
            local = repo / LOCAL_CONFIG
            self.assertTrue(local.is_file())
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "check-ignore", "--quiet", "--", LOCAL_CONFIG.as_posix()]
                ).returncode,
                0,
            )
            self.assertNotIn(LOCAL_CONFIG.as_posix(), subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
                capture_output=True, text=True, check=True,
            ).stdout)
            local.write_text("durability:\n  claim_return_minutes: 17\n", encoding="utf-8")
            second = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse(json.loads(second.stdout)["created"])
            self.assertEqual(local.read_text(encoding="utf-8"), "durability:\n  claim_return_minutes: 17\n")
            self.assertEqual(exclude.read_text(encoding="utf-8").count("/.shadow/local.yaml"), 1)
            self.assertEqual(
                exclude.read_text(encoding="utf-8"),
                exclude_before + "/.shadow/local.yaml\n",
            )
            explained = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(repo), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(explained.returncode, 0, explained.stderr)
            self.assertEqual(json.loads(explained.stdout)["config"]["durability"]["claim_return_minutes"], 17)

    def test_tracked_effective_config_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            local = repo / LOCAL_CONFIG
            local.parent.mkdir()
            local.write_text("version: 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-f", "--", LOCAL_CONFIG.as_posix()], check=True)
            result = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("must not be tracked", result.stderr)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", LOCAL_CONFIG.as_posix()],
                    capture_output=True,
                    check=False,
                ).returncode,
                0,
            )

    def test_a_tracked_effective_path_missing_from_the_worktree_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            local = repo / LOCAL_CONFIG
            local.parent.mkdir()
            local.write_text("version: 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-f", "--", LOCAL_CONFIG.as_posix()], check=True)
            local.unlink()
            result = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("must not be tracked", result.stderr)

    def test_an_ignore_negation_refuses_without_mutating_the_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            (repo / ".gitignore").write_text("!/.shadow/local.yaml\n", encoding="utf-8")
            exclude = repo / ".git/info/exclude"
            before = exclude.read_bytes()
            result = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ignore rules expose", result.stderr)
            self.assertFalse((repo / LOCAL_CONFIG).exists())
            self.assertEqual(exclude.read_bytes(), before)

    def test_a_symlinked_effective_path_is_never_read_or_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            outside = repo / "outside.yaml"
            outside.write_text("provider: untouched\n", encoding="utf-8")
            local = repo / LOCAL_CONFIG
            local.parent.mkdir()
            local.symlink_to(outside)
            result = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("must not be a symlink", result.stderr)
            self.assertTrue(local.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "provider: untouched\n")

    def test_a_symlinked_effective_parent_refuses_before_exclude_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            outside = Path(directory) / "outside"
            repo.mkdir()
            outside.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            (repo / ".shadow").symlink_to(outside, target_is_directory=True)
            exclude = repo / ".git/info/exclude"
            before = exclude.read_bytes()
            result = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("parent must not be a symlink", result.stderr)
            self.assertEqual(exclude.read_bytes(), before)
            self.assertEqual(list(outside.iterdir()), [])

    def test_existing_invalid_local_config_does_not_report_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            initialized = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            local = repo / LOCAL_CONFIG
            local.write_text("provider: forbidden\n", encoding="utf-8")
            exclude = repo / ".git/info/exclude"
            before = exclude.read_bytes()
            repeated = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(repeated.returncode, 1)
            self.assertIn("configuration key 'provider' is refused", repeated.stderr)
            self.assertEqual(exclude.read_bytes(), before)
            self.assertEqual(local.read_text(encoding="utf-8"), "provider: forbidden\n")

    def test_dirty_repository_template_is_not_called_reviewed_or_copied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "shadow-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Shadow Test"], check=True)
            template = repo / "shadow.example.yaml"
            template.write_text("version: 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "shadow.example.yaml"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "template"], check=True)
            template.write_text("durability:\n  claim_return_minutes: 17\n", encoding="utf-8")
            exclude = repo / ".git/info/exclude"
            before = exclude.read_bytes()
            result = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("must match its committed HEAD bytes", result.stderr)
            self.assertFalse((repo / LOCAL_CONFIG).exists())
            self.assertEqual(exclude.read_bytes(), before)

    def test_linked_worktrees_keep_independent_local_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "primary"
            sibling = root / "sibling"
            primary.mkdir()
            subprocess.run(["git", "-C", str(primary), "init", "--quiet"], check=True)
            subprocess.run(["git", "-C", str(primary), "config", "user.email", "shadow-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(primary), "config", "user.name", "Shadow Test"], check=True)
            (primary / "seed").write_text("seed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(primary), "add", "seed"], check=True)
            subprocess.run(["git", "-C", str(primary), "commit", "--quiet", "-m", "seed"], check=True)
            subprocess.run(
                ["git", "-C", str(primary), "worktree", "add", "--quiet", "-b", "sibling", str(sibling)],
                check=True,
            )
            initialized = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(sibling)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertTrue((sibling / LOCAL_CONFIG).is_file())
            self.assertFalse((primary / LOCAL_CONFIG).exists())
            (sibling / LOCAL_CONFIG).write_text(
                "durability:\n  claim_return_minutes: 19\n", encoding="utf-8"
            )
            explained = subprocess.run(
                [str(CLI), "config", "--explain", "--repo", str(sibling), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(explained.returncode, 0, explained.stderr)
            self.assertEqual(json.loads(explained.stdout)["config"]["durability"]["claim_return_minutes"], 19)


class InitNeverStagesLocalConfig(unittest.TestCase):
    def test_init_preserves_the_index_and_unrelated_dirty_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "shadow-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Shadow Test"], check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "seed"], check=True)
            tracked.write_text("staged\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            tracked.write_text("unstaged\n", encoding="utf-8")
            (repo / "unrelated.txt").write_text("mine\n", encoding="utf-8")
            index_before = subprocess.run(
                ["git", "-C", str(repo), "write-tree"], capture_output=True, text=True, check=True
            ).stdout
            cached_before = subprocess.run(
                ["git", "-C", str(repo), "diff", "--cached", "--binary"],
                capture_output=True, text=True, check=True,
            ).stdout
            result = subprocess.run(
                [str(CLI), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(subprocess.run(
                ["git", "-C", str(repo), "write-tree"], capture_output=True, text=True, check=True
            ).stdout, index_before)
            self.assertEqual(subprocess.run(
                ["git", "-C", str(repo), "diff", "--cached", "--binary"],
                capture_output=True, text=True, check=True,
            ).stdout, cached_before)
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            cached_names = subprocess.run(
                ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
                capture_output=True, text=True, check=True,
            ).stdout.splitlines()
            self.assertNotIn(LOCAL_CONFIG.as_posix(), cached_names)
            self.assertEqual(tracked.read_text(encoding="utf-8"), "unstaged\n")
            self.assertEqual((repo / "unrelated.txt").read_text(encoding="utf-8"), "mine\n")


if __name__ == "__main__":
    unittest.main()
