"""Focused safety and binding tests for private Pilot Puppy native seats."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CLI = SCRIPTS / "pilot-puppy-seat.py"
LIBRARY = SCRIPTS / "pilot_puppy_seat_lib.py"
TOP_LEVEL_CLI = ROOT / "bin" / "pilot-puppy"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from pilot_puppy_roster_lib import initialize_roster

SPEC = importlib.util.spec_from_file_location("pilot_puppy_seat_lib", LIBRARY)
assert SPEC and SPEC.loader
seat = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = seat
SPEC.loader.exec_module(seat)


def run(*args: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def run_top_level(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PILOT_PUPPY_ROOT"] = str(ROOT)
    return subprocess.run(
        ["bash", str(TOP_LEVEL_CLI), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def safe_root(dirname: str) -> Path:
    return Path(dirname).resolve()


class SeatOverlayTests(unittest.TestCase):
    def assert_safe_error(self, result: subprocess.CompletedProcess[str], root: Path, value: str | None = None) -> None:
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(root), result.stderr)
        self.assertNotIn(".json", result.stderr)
        if value is not None:
            self.assertNotIn(value, result.stderr)

    def setup_roster(self, root: Path) -> Path:
        roster_file = root / "config" / "roster.json"
        initialize_roster(roster_file)
        return roster_file

    def test_init_set_show_binds_one_existing_native_slot_with_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            roster_file = self.setup_roster(root)
            seat_file = root / "config" / "seats.json"
            initialized = run("init", "--file", str(seat_file), "--json")
            configured = run_top_level(
                "seat",
                "set",
                "--slot",
                "dev-cursor",
                "--model",
                "example-model-1",
                "--file",
                str(seat_file),
                "--roster-file",
                str(roster_file),
                "--json",
            )
            shown = run("show", "--file", str(seat_file), "--roster-file", str(roster_file), "--json")
            file_mode = stat.S_IMODE(seat_file.stat().st_mode)
            parent_mode = stat.S_IMODE(seat_file.parent.stat().st_mode)

        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(configured.stdout), json.loads(shown.stdout))
        view = json.loads(shown.stdout)
        self.assertEqual(view["schema"], "pilot-puppy.seat-overlay-view.v1")
        self.assertEqual(view["overlay"]["revision"], 2)
        self.assertEqual(
            view["overlay"]["seats"],
            [{"slot": "dev-cursor", "host": "cursor", "selector": {"kind": "model", "value": "example-model-1"}}],
        )
        self.assertNotIn(str(root), shown.stdout)
        self.assertEqual(file_mode, 0o600)
        self.assertEqual(parent_mode, 0o700)

    def test_codex_profile_is_allowed_and_other_host_profile_is_refused_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            roster_file = self.setup_roster(root)
            seat_file = root / "config" / "seats.json"
            self.assertEqual(run("init", "--file", str(seat_file)).returncode, 0)
            codex = run(
                "set", "--slot", "debug-codex", "--profile", "local-profile", "--file", str(seat_file),
                "--roster-file", str(roster_file),
            )
            before = seat_file.read_bytes()
            cursor = run(
                "set", "--slot", "dev-cursor", "--profile", "local-profile", "--file", str(seat_file),
                "--roster-file", str(roster_file),
            )
            after = seat_file.read_bytes()

        self.assertEqual(codex.returncode, 0, codex.stderr)
        self.assert_safe_error(cursor, root, "local-profile")
        self.assertEqual(before, after)

    def test_set_rejects_absent_manual_disabled_or_secret_shaped_slot_data(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            roster_file = self.setup_roster(root)
            seat_file = root / "config" / "seats.json"
            self.assertEqual(run("init", "--file", str(seat_file)).returncode, 0)
            cases = (
                ("missing-slot", "example-model-1"),
                ("lead-local", "example-model-1"),
                ("dev-cursor", "api_key_example"),
                ("dev-cursor", "../escape"),
            )
            for slot, value in cases:
                with self.subTest(slot=slot, value=value):
                    result = run(
                        "set", "--slot", slot, "--model", value, "--file", str(seat_file),
                        "--roster-file", str(roster_file),
                    )
                    self.assert_safe_error(result, root, value)
            roster = json.loads(roster_file.read_text(encoding="utf-8"))
            next(slot for slot in roster["slots"] if slot["id"] == "dev-cursor")["enabled"] = False
            roster_file.write_text(json.dumps(roster), encoding="utf-8")
            roster_file.chmod(0o600)
            disabled = run(
                "set", "--slot", "dev-cursor", "--model", "example-model-1", "--file", str(seat_file),
                "--roster-file", str(roster_file),
            )

        self.assert_safe_error(disabled, root, "example-model-1")

    def test_overlay_rejects_symlink_unknown_fields_and_stale_host_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            roster_file = self.setup_roster(root)
            seat_file = root / "config" / "seats.json"
            target = root / "target.json"
            target.write_bytes(seat.canonical_seat_bytes(seat.DEFAULT_SEAT_OVERLAY) + b"\n")
            target.chmod(0o600)
            seat_file.symlink_to(target)
            symlink = run("show", "--file", str(seat_file), "--roster-file", str(roster_file))
            preserved = target.read_bytes()
            seat_file.unlink()
            seat_file.write_text(
                json.dumps({"schema": seat.SEAT_SCHEMA, "revision": 1, "seats": [], "extra": "no"}),
                encoding="utf-8",
            )
            seat_file.chmod(0o600)
            malformed = run("show", "--file", str(seat_file), "--roster-file", str(roster_file))
            seat_file.write_bytes(
                seat.canonical_seat_bytes(
                    {
                        "schema": seat.SEAT_SCHEMA,
                        "revision": 1,
                        "seats": [
                            {
                                "slot": "dev-cursor",
                                "host": "codex",
                                "selector": {"kind": "model", "value": "example-model-1"},
                            }
                        ],
                    }
                )
                + b"\n"
            )
            seat_file.chmod(0o600)
            stale = run("show", "--file", str(seat_file), "--roster-file", str(roster_file))

        self.assert_safe_error(symlink, root)
        self.assertEqual(preserved, seat.canonical_seat_bytes(seat.DEFAULT_SEAT_OVERLAY) + b"\n")
        self.assert_safe_error(malformed, root)
        self.assert_safe_error(stale, root)

    def test_init_is_no_overwrite_and_explicit_environment_override_is_honored(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            override = root / "private" / "seats.json"
            with mock.patch.dict(os.environ, {"PILOT_PUPPY_SEATS_FILE": str(override)}):
                self.assertEqual(seat.default_seat_path(), override)
            first = run("init", environment={"PILOT_PUPPY_SEATS_FILE": str(override)})
            original = override.read_bytes()
            second = run("init", environment={"PILOT_PUPPY_SEATS_FILE": str(override)})
            preserved = override.read_bytes()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 1)
        self.assertIn("refusing to overwrite", second.stderr)
        self.assertEqual(original, preserved)

    def test_top_level_help_exposes_private_seats_without_claiming_provider_discovery(self) -> None:
        result = run_top_level("help", "seat")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pilot-puppy seat set --slot SLOT", result.stdout)
        self.assertIn("--use-seat", result.stdout)
        self.assertIn("never discovers models", result.stdout)


if __name__ == "__main__":
    unittest.main()
