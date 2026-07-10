"""Contract coverage for the installable Vidux release candidate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-release-package.py"
SPEC = importlib.util.spec_from_file_location("vidux_release_package", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def baseline() -> tuple[dict, dict, set[str]]:
    package = {
        "name": "vidux",
        "version": "2.23.0",
        "private": False,
        "bin": {"vidux": "bin/vidux"},
        "files": ["bin/", "scripts/"],
        "engines": {"node": ">=20"},
        "publishConfig": {"access": "public", "provenance": True},
        "scripts": {"release:verify": "python3 scripts/vidux-release-package.py"},
    }
    paths = set(mod.REQUIRED_FILES)
    pack = {
        "name": "vidux",
        "version": "2.23.0",
        "unpackedSize": 100_000,
        "files": [{"path": path, "size": 1} for path in sorted(paths)],
    }
    return package, pack, paths


class ReleasePackageTests(unittest.TestCase):
    def errors(self, package: dict, pack: dict, tracked: set[str]) -> list[str]:
        return mod.validate_release_candidate(
            package,
            pack,
            version="2.23.0",
            tracked_paths=tracked,
            plugin_version="2.23.0",
        )

    def test_baseline_contract_passes(self) -> None:
        package, pack, tracked = baseline()
        self.assertEqual(self.errors(package, pack, tracked), [])

    def test_rejects_private_or_version_drifted_package(self) -> None:
        package, pack, tracked = baseline()
        package["private"] = True
        package["version"] = "2.22.0"
        errors = self.errors(package, pack, tracked)
        self.assertTrue(any("private" in error for error in errors), errors)
        self.assertTrue(any("package.json version" in error for error in errors), errors)

    def test_rejects_plugin_version_drift(self) -> None:
        package, pack, tracked = baseline()
        errors = mod.validate_release_candidate(
            package,
            pack,
            version="2.23.0",
            tracked_paths=tracked,
            plugin_version="2.22.0",
        )
        self.assertTrue(any("plugin version" in error for error in errors), errors)

    def test_rejects_missing_cli_and_broad_local_material(self) -> None:
        package, pack, tracked = baseline()
        pack["files"] = [entry for entry in pack["files"] if entry["path"] != "bin/vidux"]
        for path in ["evaluations/run.json", ".opencode/agent.md", "evidence/private.jsonl"]:
            pack["files"].append({"path": path, "size": 1})
            tracked.add(path)
        errors = self.errors(package, pack, tracked)
        self.assertTrue(any("missing required" in error and "bin/vidux" in error for error in errors), errors)
        self.assertTrue(any("forbidden files" in error for error in errors), errors)

    def test_rejects_untracked_or_oversized_artifact(self) -> None:
        package, pack, tracked = baseline()
        pack["files"].append({"path": "scripts/local-only.sh", "size": 1})
        pack["unpackedSize"] = mod.MAX_UNPACKED_BYTES + 1
        errors = self.errors(package, pack, tracked)
        self.assertTrue(any("not tracked by git" in error for error in errors), errors)
        self.assertTrue(any("unpacked bytes" in error for error in errors), errors)

    def test_requires_only_the_public_v3_preflight_surface(self) -> None:
        package, pack, tracked = baseline()
        pack["files"].append({"path": "benchmarks/v3/private-oracles.json", "size": 1})
        tracked.add("benchmarks/v3/private-oracles.json")

        errors = self.errors(package, pack, tracked)

        self.assertTrue(
            any("runtime or evaluator v3 files" in error for error in errors),
            errors,
        )

    def test_requires_only_the_public_v4_preflight_surface(self) -> None:
        package, pack, tracked = baseline()
        pack["files"].append({"path": "benchmarks/v4/private-evaluator.json", "size": 1})
        tracked.add("benchmarks/v4/private-evaluator.json")

        errors = self.errors(package, pack, tracked)

        self.assertTrue(
            any("runtime or evaluator v4 files" in error for error in errors),
            errors,
        )

    def test_rejects_unsafe_publish_configuration(self) -> None:
        package, pack, tracked = baseline()
        package["publishConfig"] = {"access": "restricted"}
        errors = self.errors(package, pack, tracked)
        self.assertTrue(any("provenance" in error for error in errors), errors)

    def test_current_checkout_package_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT), "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
