from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-release-package.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
SPEC = importlib.util.spec_from_file_location("release_package", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def baseline() -> tuple[dict, dict, set[str]]:
    """No package dict since 2026-08-09: the release artifact is a git archive,
    so identity comes from the plugin manifest + VERSION + the origin remote."""
    plugin = {"name": "shadow", "version": VERSION}
    paths = set(mod.REQUIRED_FILES)
    pack = {
        "version": VERSION,
        "unpackedSize": 100_000,
        "origin": "git@github.com:firstbitelabsllc/shadow.git",
        "files": [{"path": path} for path in sorted(paths)],
    }
    return plugin, pack, paths


class ReleasePackageTests(unittest.TestCase):
    def errors(self, plugin: dict, pack: dict, tracked: set[str], **kwargs) -> list[str]:
        return mod.validate_release_candidate(
            plugin,
            pack,
            version=VERSION,
            tracked_paths=tracked,
            **kwargs,
        )

    def test_minimum_public_artifact_passes(self) -> None:
        plugin, pack, tracked = baseline()
        self.assertEqual(self.errors(plugin, pack, tracked), [])

    def test_top_changelog_release_matches_version(self) -> None:
        self.assertEqual(mod.changelog_version(ROOT), VERSION)

    def test_missing_required_file_fails(self) -> None:
        plugin, pack, tracked = baseline()
        pack["files"] = [item for item in pack["files"] if item["path"] != "bin/shadow"]
        self.assertTrue(any("missing" in error for error in self.errors(plugin, pack, tracked)))

    def test_lifecycle_command_ships_with_the_dispatcher(self) -> None:
        self.assertIn("scripts/shadow-lifecycle.py", mod.REQUIRED_FILES)
        self.assertIn("schemas/retirement-manifest.v1.json", mod.REQUIRED_FILES)
        output = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "help", "lifecycle"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        for clause in (
            "--milestone 'exact heading'",
            "--retirement-manifest /ABS/manifest.json",
            "--expect CAS",
            "--by SEAT",
        ):
            self.assertIn(clause, output.stdout)
        argparse_help = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "shadow-lifecycle.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(argparse_help.returncode, 0, argparse_help.stderr)
        self.assertIn("retire one exact manifested artifact", argparse_help.stdout)
        for option in ("--retirement-manifest", "--expect", "--by"):
            self.assertIn(option, argparse_help.stdout)

    def test_two_seat_harness_ships_with_its_process_boundary(self) -> None:
        self.assertIn("scripts/shadow-verify-two-seat.py", mod.REQUIRED_FILES)
        self.assertIn("scripts/shadow_process_lib.py", mod.REQUIRED_FILES)
        output = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "shadow-verify-two-seat.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        for clause in ("--live", "--goal-file", "--timeout-seconds", "--json"):
            self.assertIn(clause, output.stdout)

    def test_disposable_fixture_commit_waits_for_git_maintenance(self) -> None:
        project = Path("/unused-fixture")
        with mock.patch.object(mod, "command") as observed:
            mod.commit_disposable_fixture(project)

        argv, cwd = observed.call_args.args
        commit_index = argv.index("commit")
        self.assertEqual(cwd, project)
        self.assertLess(argv.index("maintenance.autoDetach=false"), commit_index)
        self.assertLess(argv.index("gc.autoDetach=false"), commit_index)

    def test_second_skill_or_private_stream_fails(self) -> None:
        plugin, pack, tracked = baseline()
        extras = ["nested/SKILL.md", "activity.jsonl"]
        pack["files"].extend({"path": path} for path in extras)
        tracked.update(extras)
        errors = self.errors(plugin, pack, tracked)
        self.assertTrue(any("exactly the root" in error for error in errors))
        self.assertTrue(any("forbidden" in error for error in errors))

    def test_dirty_bytes_require_explicit_development_mode(self) -> None:
        plugin, pack, tracked = baseline()
        errors = self.errors(plugin, pack, tracked, dirty_paths={"README.md"})
        self.assertTrue(any("uncommitted" in error for error in errors))
        self.assertEqual(self.errors(plugin, pack, tracked, dirty_paths={"README.md"}, allow_dirty=True), [])

    def test_only_the_canonical_github_remote_is_provenance(self) -> None:
        # A suffix test would trust any host that serves the canonical path.
        plugin, pack, tracked = baseline()
        for good in ("https://github.com/firstbitelabsllc/shadow.git",
                     "ssh://git@github.com/firstbitelabsllc/shadow",
                     "git@github.com:firstbitelabsllc/shadow.git"):
            pack["origin"] = good
            self.assertEqual(self.errors(plugin, pack, tracked), [], good)
        for bad in ("https://evil.example.com/firstbitelabsllc/shadow.git",
                    "https://github.com.evil.example.com/firstbitelabsllc/shadow",
                    "git@evil.example.com:firstbitelabsllc/shadow.git",
                    ""):
            pack["origin"] = bad
            self.assertTrue(
                any("canonical" in error for error in self.errors(plugin, pack, tracked)), bad
            )

    def test_current_checkout_packs_and_installs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT), "--allow-dirty", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, report)
        self.assertTrue(report["stranger_install"])
        self.assertTrue(report["reproducible"])
        self.assertFalse(report["publishable"])


if __name__ == "__main__":
    unittest.main()
