"""shadow-ci — release-pressure probes ignore an ambient repository redirect."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-ci.py"
SPEC = importlib.util.spec_from_file_location("shadow_ci", SCRIPT)
assert SPEC and SPEC.loader
shadow_ci = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = shadow_ci
SPEC.loader.exec_module(shadow_ci)


class AmbientGitRedirectPinTests(unittest.TestCase):
    def test_repository_pressure_ignores_an_ambient_repository_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            decoy = Path(tmp) / "decoy"
            subprocess.run(["git", "init", "-q", str(real)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-q", str(decoy)], check=True, capture_output=True)
            for args in (("config", "user.email", "t@example.invalid"), ("config", "user.name", "T")):
                subprocess.run(["git", "-C", str(decoy), *args], check=True, capture_output=True)
            (decoy / "f").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", str(decoy), "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(decoy), "commit", "-qm", "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(decoy), "tag", "v1.0.0"], check=True, capture_output=True)
            # The real repo has no release tag; the decoy has one. An
            # unsanitized probe follows GIT_DIR into the decoy and invents a
            # release baseline that does not exist in the real repository.
            with mock.patch.dict(
                os.environ,
                {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)},
            ):
                pressure = shadow_ci.repository_pressure(real)
            self.assertEqual(pressure["RELEASE_BASELINE"], "")


class HuddleSelectionTests(unittest.TestCase):
    def test_huddle_core_and_docs_select_huddle_proof(self) -> None:
        for path in ("scripts/shadow-huddle.py", "scripts/shadow_huddle_event.py",
                     "scripts/shadow_board_schema.py", "docs/reference/commands.md"):
            with self.subTest(path=path):
                selection = shadow_ci.select_paths([path])
                self.assertIn("tests.test_huddle", selection.modules)
        event = shadow_ci.select_paths(["scripts/shadow_huddle_event.py"])
        self.assertIn("tests.test_huddle_event", event.modules)

    def test_huddle_boundaries_select_their_direct_falsifiers(self) -> None:
        # One source can require two distinct boundaries; retain both checks.
        for path, module in (("scripts/shadow-huddle.py", "tests.test_huddle_cli"),
                             ("scripts/shadow_board_schema.py", "tests.test_board_schema"),
                             ("scripts/shadow_board_schema.py", "tests.test_huddle_event"),
                             ("scripts/shadow_root_board.py", "tests.test_huddle_amp"),
                             ("scripts/shadow_root_board.py", "tests.test_huddle_cli"),
                             ("scripts/shadow_root_board.py", "tests.test_local_plan_store"),
                             ("scripts/shadow_root_board.py", "tests.test_authority_proposal"),
                             ("scripts/shadow_root_board.py", "tests.test_lifecycle"),
                             ("scripts/shadow_board_schema.py", "tests.test_browser"),
                             ("scripts/shadow-amp.py", "tests.test_huddle_amp"),
                             ("scripts/shadow-throw.py", "tests.test_huddle_amp"),
                             ("scripts/shadow_remote_claim.py", "tests.test_huddle_cli"),
                             ("scripts/shadow-plan.py", "tests.test_root_board"),
                             ("scripts/shadow_git_fixture.py", "tests.test_two_seat_harness"),
                             ("scripts/shadow_process_lib.py", "tests.test_huddle_process")):
            with self.subTest(path=path, module=module):
                self.assertIn(module, shadow_ci.select_paths([path]).modules)


class LocalLaneTests(unittest.TestCase):
    def run_local(self, changed):
        output = io.StringIO()
        with mock.patch.object(shadow_ci, "merge_base", return_value="base") as base:
            with mock.patch.object(
                shadow_ci, "changed_paths", return_value=changed
            ) as paths:
                with mock.patch.object(shadow_ci, "run_selected") as run:
                    with mock.patch("sys.stdout", output):
                        code = shadow_ci.main(["local", "--base", "feature"])
        base.assert_called_once_with("feature")
        paths.assert_called_once_with("base", "HEAD")
        return code, output.getvalue(), run

    def test_mapped_change_runs_its_focused_modules(self) -> None:
        code, output, run = self.run_local(["tests/test_ci.py"])

        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        run.assert_called_once_with(
            False,
            json.dumps([
                "tests.test_ci",
                "tests.test_release_train",
                "tests.test_style_guard",
            ]),
        )

    def test_unmapped_change_runs_baseline_and_defers_full_proof(self) -> None:
        code, output, run = self.run_local(["unmapped/file.txt"])

        self.assertEqual(code, 0)
        self.assertEqual(
            output,
            "shadow-ci local: full proof deferred to landing "
            "(unmapped paths require full proof: unmapped/file.txt)\n",
        )
        run.assert_called_once_with(
            False,
            json.dumps(sorted(shadow_ci.BASELINE)),
        )

    def test_a_wide_selection_runs_baseline_and_defers_to_landing(self) -> None:
        wide = shadow_ci.Selection(
            False,
            tuple(sorted(shadow_ci.BASELINE | {f"tests.test_wide_{i}" for i in range(7)})),
            (), False, "mapped affected proof",
        )
        with mock.patch.object(shadow_ci, "select_paths", return_value=wide):
            code, output, run = self.run_local(["scripts/shadow-ci.py"])

        self.assertEqual(code, 0)
        self.assertIn("7 focused modules exceed --max-modules 6", output)
        run.assert_called_once_with(False, json.dumps(sorted(shadow_ci.BASELINE)))

    def test_unresolvable_base_is_reported_and_exits_two(self) -> None:
        result = subprocess.CompletedProcess(args=[], returncode=128)
        error = io.StringIO()
        with mock.patch.object(
            shadow_ci.subprocess, "run", return_value=result
        ) as git:
            with mock.patch.object(shadow_ci, "run_selected") as run:
                with mock.patch("sys.stderr", error):
                    code = shadow_ci.main(["local", "--base", "missing"])

        self.assertEqual(code, 2)
        self.assertEqual(error.getvalue(), "shadow-ci: comparison base is unavailable\n")
        run.assert_not_called()
        git.assert_called_once_with(
            ["git", "-C", str(shadow_ci.ROOT), "merge-base", "missing", "HEAD"],
            capture_output=True,
            env=mock.ANY,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
