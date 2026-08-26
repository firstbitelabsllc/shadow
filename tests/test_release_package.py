from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
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


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


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
            "--progress-before UTC_TIMESTAMP",
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

    def test_plan_migration_command_ships_with_its_store(self) -> None:
        self.assertIn("scripts/shadow-plan.py", mod.REQUIRED_FILES)
        self.assertIn("scripts/shadow_plan_store.py", mod.REQUIRED_FILES)
        output = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "help", "plan"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertIn("migrate /ABS/PLAN.md --dry-run", output.stdout)
        self.assertIn("rollback /ABS/PLAN.md --expect ROOT_SHA256", output.stdout)

    def test_bounded_plan_read_command_ships_with_its_store(self) -> None:
        self.assertIn("scripts/shadow-read.py", mod.REQUIRED_FILES)
        self.assertIn("scripts/shadow_plan_store.py", mod.REQUIRED_FILES)
        output = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "help", "read"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        for clause in (
            "read --entity ENTITY_ID",
            "--row '~hash'",
            "--receipt progress:N",
            "--find LITERAL",
            "--expect-root ROOT_SHA256",
            "never follows archive/spill links",
        ):
            self.assertIn(clause, output.stdout)

    def test_two_seat_harness_ships_with_its_process_boundary(self) -> None:
        self.assertIn("scripts/shadow-verify-two-seat.py", mod.REQUIRED_FILES)
        self.assertIn("scripts/shadow_process_lib.py", mod.REQUIRED_FILES)
        self.assertIn("SOURCE_REF", mod.REQUIRED_FILES)
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

    def test_cmd_proof_validator_ships_with_lint_and_accept(self) -> None:
        self.assertIn("scripts/shadow_cmd_proof.py", mod.REQUIRED_FILES)

    def test_plan_grammar_ships_with_its_consumers(self) -> None:
        self.assertIn("scripts/shadow_plan_grammar.py", mod.REQUIRED_FILES)

    def test_remote_claim_transport_ships_with_throw(self) -> None:
        self.assertIn("scripts/shadow_remote_claim.py", mod.REQUIRED_FILES)

    def test_local_event_vocabulary_ships_without_a_transport(self) -> None:
        self.assertIn("scripts/shadow_telemetry.py", mod.REQUIRED_FILES)
        self.assertIn("docs/reference/telemetry.md", mod.REQUIRED_FILES)

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
        self.assertTrue(any("native, portable, and amplify skills" in error for error in errors))
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


class CurrentReleaseCandidate(unittest.TestCase):
    def test_every_shipped_identity_reports_current_release(self) -> None:
        expected = "1.3.0"
        manifests = (
            ".claude-plugin/plugin.json",
            "plugins/shadow/plugin.json",
            "plugins/shadow/.codex-plugin/plugin.json",
            "plugins/shadow/.claude-plugin/plugin.json",
        )

        self.assertEqual(mod.source_version(ROOT), expected)
        self.assertEqual(mod.changelog_version(ROOT), expected)
        for relative in manifests:
            manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], expected, relative)

        cli = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(cli.stdout.strip(), expected)

        identity = mod.inspect_release_identity(ROOT, expected)
        self.assertEqual(identity["errors"], [])


class ReleaseIdentityIsImmutable(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        git(repo, "config", "user.email", "release@example.invalid")
        git(repo, "config", "user.name", "Release Test")
        (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        git(repo, "add", "VERSION")
        git(repo, "commit", "-qm", "seed")
        return repo

    def inspect(self, repo: Path) -> dict:
        return mod.inspect_release_identity(repo, "1.0.0", require_release_ref=True)

    def clone_release_checkout(self, root: Path) -> Path:
        repo = root / "shadow"
        subprocess.run(
            ["git", "clone", "-q", "--no-local", "--no-tags", str(ROOT), str(repo)],
            check=True,
        )
        git(repo, "config", "user.email", "release@example.invalid")
        git(repo, "config", "user.name", "Release Test")
        git(repo, "remote", "set-url", "origin", "https://github.com/firstbitelabsllc/shadow.git")
        # The public checkout may already carry this real release tag. This
        # fixture owns its own tag at its cloned HEAD, so discard the inherited
        # name before minting that isolated identity.
        subprocess.run(["git", "-C", str(repo), "tag", "-d", f"shadow-v{VERSION}"],
                       capture_output=True, text=True, check=False)
        git(repo, "tag", "-a", f"shadow-v{VERSION}", "-m", f"Shadow {VERSION}")
        return repo

    def test_only_a_namespaced_annotated_tag_at_exact_head_is_public(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            head = git(repo, "rev-parse", "HEAD")

            legacy = self.inspect(repo)
            self.assertIsNone(legacy["release_ref"])
            self.assertTrue(any("shadow-v1.0.0" in error for error in legacy["errors"]))

            git(repo, "tag", "-a", "v1.0.0", "-m", "legacy")
            occupied_legacy = self.inspect(repo)
            self.assertIsNone(occupied_legacy["release_ref"])
            self.assertTrue(any("shadow-v1.0.0" in error for error in occupied_legacy["errors"]))

            git(repo, "tag", "shadow-v1.0.0")
            lightweight = self.inspect(repo)
            self.assertIsNone(lightweight["release_ref"])
            self.assertTrue(any("annotated" in error for error in lightweight["errors"]))

            git(repo, "tag", "-d", "shadow-v1.0.0")
            git(repo, "tag", "-a", "shadow-v1.0.0", "-m", "Shadow 1.0")
            exact = self.inspect(repo)
            self.assertEqual(exact, {"commit": head, "release_ref": "shadow-v1.0.0", "errors": []})

            (repo / "later.txt").write_text("later\n", encoding="utf-8")
            git(repo, "add", "later.txt")
            git(repo, "commit", "-qm", "later")
            moved = self.inspect(repo)
            self.assertIsNone(moved["release_ref"])
            self.assertTrue(any("exact HEAD" in error for error in moved["errors"]))

    def test_public_verification_records_commit_ref_and_archive_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.clone_release_checkout(Path(tmp))
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(repo),
                    "--expect-version",
                    VERSION,
                    "--public-release",
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            report = json.loads(result.stdout)
            head = git(repo, "rev-parse", "HEAD")

        self.assertEqual(result.returncode, 0, report)
        self.assertTrue(report["publishable"], report)
        self.assertEqual(report["commit"], head)
        self.assertEqual(report["release_ref"], f"shadow-v{VERSION}")
        self.assertRegex(report["sha256"], r"^[0-9a-f]{64}$")

    def test_archive_is_cut_from_the_receipted_commit_not_mutable_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            (repo / "SOURCE_REF").write_text("$Format:%H$\n", encoding="ascii")
            (repo / ".gitattributes").write_text("SOURCE_REF export-subst\n", encoding="utf-8")
            git(repo, "add", "SOURCE_REF", ".gitattributes")
            git(repo, "commit", "-qm", "source receipt")
            receipted = git(repo, "rev-parse", "HEAD")
            git(repo, "remote", "add", "origin", "https://github.com/firstbitelabsllc/shadow.git")
            (repo / "later.txt").write_text("later\n", encoding="utf-8")
            git(repo, "add", "later.txt")
            git(repo, "commit", "-qm", "move head")
            archive = root / "archive"
            archive.mkdir()
            try:
                _, tarball, _ = mod.pack(repo, archive, source_ref=receipted)
            except TypeError as exc:
                self.fail(f"release packer cannot bind an exact commit: {exc}")
            archived_ref = subprocess.check_output(
                ["tar", "-xOf", str(tarball), "SOURCE_REF"], text=True
            ).strip()

        self.assertEqual(archived_ref, receipted)

    def test_public_mode_never_accepts_allow_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.clone_release_checkout(Path(tmp))
            (repo / "README.md").write_text("dirty release bytes\n", encoding="utf-8")
            report = mod.verify(
                repo,
                expected_version=VERSION,
                allow_dirty=True,
                require_release_ref=True,
            )

        self.assertFalse(report["ok"])
        self.assertFalse(report["publishable"])
        self.assertTrue(any("allow dirty" in error for error in report["errors"]))

    def test_identity_drift_during_pack_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.clone_release_checkout(Path(tmp))
            real_pack = mod.pack
            calls = 0

            def moving_pack(*args, **kwargs):
                nonlocal calls
                result = real_pack(*args, **kwargs)
                calls += 1
                if calls == 1:
                    git(repo, "commit", "--allow-empty", "-qm", "move during verification")
                return result

            with mock.patch.object(mod, "pack", side_effect=moving_pack):
                report = mod.verify(
                    repo,
                    expected_version=VERSION,
                    require_release_ref=True,
                )

        self.assertFalse(report["ok"])
        self.assertFalse(report["publishable"])
        self.assertTrue(any("changed during verification" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
