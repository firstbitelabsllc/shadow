from __future__ import annotations

import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import shadow_config as config  # noqa: E402
import shadow_root_board as board  # noqa: E402

LIFECYCLE_SPEC = importlib.util.spec_from_file_location(
    "shadow_board_context_lifecycle", ROOT / "scripts" / "shadow-lifecycle.py"
)
assert LIFECYCLE_SPEC and LIFECYCLE_SPEC.loader
lifecycle = importlib.util.module_from_spec(LIFECYCLE_SPEC)
sys.modules[LIFECYCLE_SPEC.name] = lifecycle
LIFECYCLE_SPEC.loader.exec_module(lifecycle)


def repository(path: Path, local_text: str) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    info = path / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "exclude").write_text("/.shadow/local.yaml\n", encoding="utf-8")
    local = path / ".shadow" / "local.yaml"
    local.parent.mkdir()
    local.write_text(local_text, encoding="utf-8")
    return path


class OneMachineBoardContext(unittest.TestCase):
    def test_explicit_root_is_the_board_directory_not_its_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "chosen-board"
            observed = board.ensure(root=root)

            self.assertEqual(observed["schema"], board.SCHEMA)
            self.assertTrue((root / board.BOARD_NAME).is_file())
            self.assertFalse((root / ".shadow").exists())

    def test_installed_machine_config_selects_the_implicit_board(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            selected = base.resolve() / "shared" / "board"
            installed = repository(
                base / "shadow-install",
                f"version: 1\nboard:\n  root: {selected}\n",
            )
            machine = installed / config.MACHINE_CONFIG
            machine.parent.mkdir(exist_ok=True)
            (installed / config.LOCAL_CONFIG).replace(machine)
            with (installed / ".git" / "info" / "exclude").open("a", encoding="utf-8") as stream:
                stream.write("/.shadow/machine.yaml\n")
            home = base / "home"
            home.mkdir()

            with mock.patch.dict(
                os.environ,
                {"SHADOW_ROOT": str(installed), "HOME": str(home)},
                clear=False,
            ):
                board.ensure()

            self.assertTrue((selected / board.BOARD_NAME).is_file())
            self.assertFalse((home / ".shadow").exists())

    def test_entity_expected_root_is_an_assertion_not_a_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            entity = repository(
                base / "entity",
                "version: 1\ncomputer:\n  expected_board_root: /other/board\n",
            )

            with self.assertRaisesRegex(
                config.ConfigError,
                "expected_board_root does not match",
            ):
                config.assert_expected_board_root(entity, base / "actual-board")

    def test_explicit_context_does_not_re_resolve_machine_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "board"
            with mock.patch.object(
                board,
                "configured_root",
                side_effect=AssertionError("board root was resolved twice"),
            ):
                board.ensure(root=root)
                board.snapshot(root=root)

    def test_configured_root_refuses_an_existing_symlink_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            real_parent = base / "real"
            real_parent.mkdir()
            linked_parent = base / "linked"
            linked_parent.symlink_to(real_parent, target_is_directory=True)

            with self.assertRaisesRegex(board.BoardError, "symlink component"):
                board.ensure(root=linked_parent / "board")
            self.assertFalse((real_parent / "board").exists())

    def test_retirement_journal_lives_under_the_selected_board(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            plan = base / "repo" / "PLAN.md"
            plan.parent.mkdir()
            selected = base / "machine-board"

            _, journal = lifecycle.retirement_paths(
                plan,
                "a" * 64,
                board_root=selected,
            )

            self.assertEqual(journal.parent, selected / "retirements")


if __name__ == "__main__":
    unittest.main()
