from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from browser import server


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import shadow_config


LOCAL_CONFIG = Path(".shadow/local.yaml")
MACHINE_CONFIG = Path(".shadow/machine.yaml")
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
                if key != "SHADOW_PORTFOLIO_ROOT"
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
                if key != "SHADOW_PORTFOLIO_ROOT"
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

    def test_status_ignores_obsolete_dev_root_env_and_cli_flag_wins(self) -> None:
        with (
            tempfile.TemporaryDirectory() as dirname,
            tempfile.TemporaryDirectory() as override,
            tempfile.TemporaryDirectory() as home,
        ):
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            override_root = Path(override)
            (override_root / "PLAN.md").write_text(
                PLAN.replace("- Project: demo", "- Project: override"),
                encoding="utf-8",
            )
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
            self.assertNotIn("demo", {plan["project"] for plan in report["v4_plans"]})

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
            projects = {plan["project"] for plan in report["v4_plans"]}
            self.assertIn("override", projects)
            self.assertNotIn("demo", projects)

    def test_browser_defaults_use_environment_and_flags_override(self) -> None:
        with tempfile.TemporaryDirectory() as portfolio, patch.dict(
            os.environ,
            {
                "SHADOW_PORTFOLIO_ROOT": portfolio,
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


class ConsumerOverridesStayInsideTheDeclaredBoundary(unittest.TestCase):
    def _write_local(self, root: Path, text: str, *, scope: str = "entity") -> Path:
        subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
        relative = LOCAL_CONFIG if scope == "entity" else MACHINE_CONFIG
        exclude = root / ".git/info/exclude"
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write(f"/{relative.as_posix()}\n")
        local = root / relative
        local.parent.mkdir(exist_ok=True)
        local.write_text(text, encoding="utf-8")
        return local

    def test_entity_scope_accepts_only_consumer_preferences_and_board_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_local(
                root,
                """version: 1
computer:
  expected_board_root: ~/shadow-board
leads:
  codex:
    display_name: Codex
    default_lenses:
      - integration
method:
  adversarial_lenses:
    - correctness
    - privacy
buckets:
  taste: taste
  future: future
durability:
  claim_return_minutes: 90
""",
            )
            loaded = shadow_config.load_config(root, scope="entity")

        self.assertEqual(loaded["computer"]["expected_board_root"], "~/shadow-board")
        self.assertEqual(loaded["leads"]["codex"]["display_name"], "Codex")
        self.assertEqual(loaded["method"]["adversarial_lenses"], ["correctness", "privacy"])
        self.assertEqual(loaded["buckets"], {"taste": "taste", "future": "future"})
        self.assertEqual(loaded["durability"]["claim_return_minutes"], 90)
        self.assertNotIn("board", loaded)
        self.assertNotIn("directives", loaded)

    def test_entity_scope_refuses_machine_board_and_directive_topology(self) -> None:
        cases = {
            "board": "board:\n  root: ~/shadow-board\n",
            "directives": """directives:
  source: ~/leo/AGENTS.md
  targets:
    claude: ~/.claude/CLAUDE.md
    codex: ~/.codex/AGENTS.md
  projections:
    cursor: user_rules
""",
        }
        for key, text in cases.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                local = self._write_local(root, text)
                with self.assertRaises(shadow_config.ConfigError) as raised:
                    shadow_config.load_config(root, scope="entity")
                self.assertEqual(raised.exception.path, local.resolve())
                self.assertEqual(raised.exception.line, 1)
                self.assertIn(f"{key} is machine bootstrap configuration", raised.exception.detail)

    def test_machine_scope_accepts_one_board_and_exact_directive_topology(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_local(
                root,
                """version: 1
board:
  root: ~/shadow-board
directives:
  source: ~/leo/AGENTS.md
  targets:
    claude: ~/.claude/CLAUDE.md
    codex: ~/.codex/AGENTS.md
  projections:
    cursor: user_rules
""",
                scope="machine",
            )
            loaded = shadow_config.load_machine_config(root)

        self.assertEqual(loaded["board"]["root"], "~/shadow-board")
        self.assertEqual(loaded["directives"]["source"], "~/leo/AGENTS.md")
        self.assertEqual(
            loaded["directives"]["targets"],
            {"claude": "~/.claude/CLAUDE.md", "codex": "~/.codex/AGENTS.md"},
        )
        self.assertEqual(loaded["directives"]["projections"], {"cursor": "user_rules"})
        self.assertNotIn("computer", loaded)
        self.assertNotIn("leads", loaded)
        self.assertNotIn("method", loaded)
        self.assertNotIn("buckets", loaded)
        self.assertNotIn("durability", loaded)

    def test_machine_scope_refuses_entity_preferences(self) -> None:
        cases = {
            "computer": "computer:\n  expected_board_root: ~/shadow-board\n",
            "leads": "leads:\n  codex:\n    display_name: Codex\n",
            "method": "method:\n  adversarial_lenses:\n    - correctness\n",
            "buckets": "buckets:\n  taste: taste\n",
            "durability": "durability:\n  claim_return_minutes: 90\n",
        }
        for key, text in cases.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                local = self._write_local(root, text, scope="machine")
                with self.assertRaises(shadow_config.ConfigError) as raised:
                    shadow_config.load_machine_config(root)
                self.assertEqual(raised.exception.path, local.resolve())
                self.assertEqual(raised.exception.line, 1)
                self.assertIn(f"{key} is entity configuration", raised.exception.detail)

    def test_cursor_is_a_named_manual_projection_not_a_target_or_hash(self) -> None:
        refused = {
            "cursor-target": """directives:
  source: ~/leo/AGENTS.md
  targets:
    claude: ~/.claude/CLAUDE.md
    codex: ~/.codex/AGENTS.md
    cursor: ~/.cursor/rules
""",
            "cursor-file": """directives:
  source: ~/leo/AGENTS.md
  targets:
    claude: ~/.claude/CLAUDE.md
    codex: ~/.codex/AGENTS.md
  projections:
    cursor: ~/.cursor/rules
""",
            "stored-hash": """directives:
  source: ~/leo/AGENTS.md
  targets:
    claude: ~/.claude/CLAUDE.md
    codex: ~/.codex/AGENTS.md
  projections:
    cursor: user_rules
  expected_hash: deadbeef
""",
        }
        for name, text in refused.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._write_local(root, text, scope="machine")
                with self.assertRaises(shadow_config.ConfigError):
                    shadow_config.load_machine_config(root)

    def test_absent_scopes_return_separate_minimal_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
            entity = shadow_config.load_config(root, scope="entity")
            machine = shadow_config.load_machine_config(root)

        self.assertEqual(
            set(entity),
            {"version", "computer", "leads", "method", "buckets", "durability"},
        )
        self.assertEqual(set(machine), {"version", "board", "directives"})


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


class MachineBootstrapTemplateIsSeparate(unittest.TestCase):
    TEMPLATE = """# Machine bootstrap only.\nversion: 1\nboard:\n  root: null\ndirectives:\n  source: null\n"""

    def _installed_checkout(self, directory: str) -> Path:
        root = Path(directory)
        subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "shadow-test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Shadow Test"], check=True)
        (root / "shadow.machine.example.yaml").write_text(self.TEMPLATE, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "shadow.machine.example.yaml"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "--quiet", "-m", "seed"], check=True)
        return root

    def _config_command(self, *args: str) -> list[str]:
        return [
            str(ROOT / "scripts" / "shadow-python.sh"),
            str(ROOT / "scripts" / "shadow-config-cli.py"),
            *args,
        ]

    def test_init_machine_uses_only_the_installed_machine_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installed = self._installed_checkout(directory)
            result = subprocess.run(
                self._config_command("--init-machine", "--json"),
                env={**os.environ, "SHADOW_ROOT": str(installed)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["scope"], "machine")
            self.assertEqual(payload["template"], "shadow.machine.example.yaml")
            effective = installed / MACHINE_CONFIG
            self.assertEqual(
                shadow_config.parse_config(effective.read_text(encoding="utf-8")),
                shadow_config.parse_config(self.TEMPLATE),
            )
            self.assertEqual(
                set(shadow_config.parse_config(effective.read_text(encoding="utf-8"))),
                {"version", "board", "directives"},
            )
            self.assertNotIn(
                MACHINE_CONFIG.as_posix(),
                subprocess.run(
                    ["git", "-C", str(installed), "status", "--short", "--untracked-files=all"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
            )

    def test_explain_machine_reads_the_installed_checkout_not_the_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as installed_directory, tempfile.TemporaryDirectory() as consumer_directory:
            installed = self._installed_checkout(installed_directory)
            initialized = subprocess.run(
                self._config_command("--init-machine"),
                env={**os.environ, "SHADOW_ROOT": str(installed)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            (installed / MACHINE_CONFIG).write_text(
                "version: 1\nboard:\n  root: ~/shadow-board\ndirectives:\n  source: null\n",
                encoding="utf-8",
            )
            consumer = Path(consumer_directory)
            subprocess.run(["git", "-C", str(consumer), "init", "--quiet"], check=True)
            explained = subprocess.run(
                self._config_command("--explain-machine", "--repo", str(consumer), "--json"),
                env={**os.environ, "SHADOW_ROOT": str(installed)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(explained.returncode, 0, explained.stderr)
            payload = json.loads(explained.stdout)
            self.assertEqual(payload["scope"], "machine")
            self.assertEqual(payload["config"]["board"]["root"], "~/shadow-board")
            self.assertEqual(payload["root"], str(installed.resolve()))

    def test_installed_checkout_can_hold_independent_entity_and_machine_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installed = self._installed_checkout(directory)
            (installed / "shadow.example.yaml").write_text(
                "version: 1\ndurability:\n  claim_return_minutes: 31\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(installed), "add", "shadow.example.yaml"], check=True)
            subprocess.run(["git", "-C", str(installed), "commit", "--quiet", "-m", "entity template"], check=True)
            env = {**os.environ, "SHADOW_ROOT": str(installed)}
            machine = subprocess.run(
                self._config_command("--init-machine"), env=env,
                capture_output=True, text=True, check=False,
            )
            entity = subprocess.run(
                self._config_command("--init-local", "--repo", str(installed)), env=env,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(machine.returncode, 0, machine.stderr)
            self.assertEqual(entity.returncode, 0, entity.stderr)
            self.assertTrue((installed / MACHINE_CONFIG).is_file())
            self.assertTrue((installed / LOCAL_CONFIG).is_file())
            self.assertEqual(
                shadow_config.load_machine_config(installed)["board"]["root"], None
            )
            self.assertEqual(
                shadow_config.load_config(installed)["durability"]["claim_return_minutes"], 31
            )

    def test_machine_config_must_be_locally_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installed = self._installed_checkout(directory)
            effective = installed / MACHINE_CONFIG
            effective.parent.mkdir()
            effective.write_text(self.TEMPLATE, encoding="utf-8")
            with self.assertRaises(shadow_config.ConfigError) as raised:
                shadow_config.load_machine_config(installed)
            self.assertIn("shadow config --init-machine", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
