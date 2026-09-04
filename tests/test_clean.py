from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow_clean.py"
CLI = ROOT / "bin" / "shadow"
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402


PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2

## Tasks

### Work
- [pending] managed worktree ~aa11 | proof: cmd true

## Progress

- 2026-09-03T00:00:00Z NOTE seeded
"""


def load_module():
    spec = importlib.util.spec_from_file_location("shadow_clean_test_module", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class CleanPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = load_module()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir()
        self.repo = root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Clean Tests")
        (self.repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
        git(self.repo, "add", "PLAN.md")
        git(self.repo, "commit", "-qm", "seed")
        self.entity = board.entity_id(self.repo / "PLAN.md")
        board.claim(
            self.repo / "PLAN.md",
            "~aa11",
            "seat-a",
            project="demo",
            priority=2,
            home=self.home,
        )

    def test_creation_is_pending_then_issued_and_receipt_is_immutable(self):
        destination = self.repo.parent / "managed"
        created = self.clean.create_managed_worktree(
            self.repo,
            destination,
            entity=self.entity,
            checkpoint="~aa11",
            seat="seat-a",
            ref="HEAD",
            landed_ref="refs/heads/master",
            home=self.home,
        )
        self.assertEqual(created["state"], "issued")
        self.assertTrue(destination.is_dir())
        self.assertEqual(len(list((self.home / ".shadow" / "clean" / "receipts").glob("*.json"))), 1)
        receipt_path = Path(created["receipt_path"])
        before = receipt_path.read_bytes()
        with self.assertRaises(self.clean.CleanError):
            self.clean.create_managed_worktree(
                self.repo,
                destination,
                entity=self.entity,
                checkpoint="~aa11",
                seat="seat-a",
                ref="HEAD",
                landed_ref="refs/heads/master",
                home=self.home,
            )
        self.assertEqual(receipt_path.read_bytes(), before)

    def test_preview_reads_only_matching_issued_receipt_and_journal(self):
        destination = self.repo.parent / "managed"
        self.clean.create_managed_worktree(
            self.repo, destination, entity=self.entity, checkpoint="~aa11", seat="seat-a",
            ref="HEAD", landed_ref="refs/heads/master", home=self.home,
        )
        report = self.clean.preview(home=self.home)
        self.assertEqual(len(report["candidates"]), 1)
        self.assertTrue(report["candidates"][0]["id"].startswith("worktree@"))
        journals = list((self.home / ".shadow" / "clean" / "journals").glob("*.json"))
        journal = json.loads(journals[0].read_text(encoding="utf-8"))
        journal["receipt_sha256"] = "0" * 64
        journals[0].write_text(json.dumps(journal), encoding="utf-8")
        self.assertEqual(self.clean.preview(home=self.home)["candidates"], [])

    def test_create_cli_exposes_only_opaque_identity(self):
        destination = self.repo.parent / "managed-cli"
        result = subprocess.run(
            [str(CLI), "clean", "--create", "--repo", str(self.repo), "--worktree", str(destination),
             "--entity", self.entity, "--row", "~aa11", "--by", "seat-a", "--landed-ref", "refs/heads/master", "--json"],
            env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        public = json.loads(result.stdout)
        self.assertTrue(public["id"].startswith("worktree@"))
        self.assertNotIn(str(destination), result.stdout)
        self.assertNotIn("receipt_path", public)

    def test_prepare_cli_exposes_only_opaque_manifest_metadata(self):
        destination = self.repo.parent / "managed-prepare"
        create = subprocess.run(
            [str(CLI), "clean", "--create", "--repo", str(self.repo), "--worktree", str(destination),
             "--entity", self.entity, "--row", "~aa11", "--by", "seat-a", "--landed-ref", "refs/heads/master", "--json"],
            env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(create.returncode, 0, create.stderr)
        result = subprocess.run(
            [str(CLI), "clean", "--prepare", "--worktree", str(destination), "--json"],
            env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        public = json.loads(result.stdout)
        self.assertEqual(public["state"], "prepared")
        self.assertTrue(public["id"].startswith("manifest@"))
        self.assertTrue(public["worktree_id"].startswith("worktree@"))
        self.assertNotIn(str(destination), result.stdout)
        self.assertNotIn("receipt", result.stdout)
        self.assertNotIn("journal", result.stdout)
        self.assertNotIn("manifest_path", result.stdout)

    def test_interrupted_issuance_can_only_resume_matching_pending_nonce(self):
        destination = self.repo.parent / "managed"
        pending = self.clean.prepare_creation(
            self.repo,
            destination,
            entity=self.entity,
            checkpoint="~aa11",
            seat="seat-a",
            ref="HEAD",
            landed_ref="refs/heads/master",
            home=self.home,
        )
        self.assertEqual(pending["state"], "pending")
        with self.assertRaises(self.clean.CleanError):
            self.clean.finish_creation(pending["nonce"], home=self.home, destination=destination.parent / "other")
        issued = self.clean.finish_creation(pending["nonce"], home=self.home, destination=destination)
        self.assertEqual(issued["state"], "issued")
        self.assertTrue((self.home / ".shadow" / "clean" / "receipts").exists())

    def test_cli_retries_after_post_add_interruption_without_touching_child(self):
        destination = self.repo.parent / "managed-retry"
        pending = self.clean.prepare_creation(
            self.repo,
            destination,
            entity=self.entity,
            checkpoint="~aa11",
            seat="seat-a",
            ref="HEAD",
            landed_ref="refs/heads/master",
            home=self.home,
        )
        git(self.repo, "worktree", "add", "-q", str(destination), "HEAD")
        child_stat = destination.stat()
        result = subprocess.run(
            [str(CLI), "clean", "--create", "--repo", str(self.repo), "--worktree", str(destination),
             "--entity", self.entity, "--row", "~aa11", "--by", "seat-a", "--landed-ref", "refs/heads/master", "--json"],
            env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "issued")
        self.assertEqual(destination.stat().st_ino, child_stat.st_ino)
        self.assertEqual(pending["state"], "pending")

    def test_standalone_receipt_and_preexisting_worktree_are_not_candidates(self):
        preexisting = self.repo.parent / "old"
        git(self.repo, "worktree", "add", "-q", str(preexisting), "HEAD")
        fake = self.home / ".shadow" / "clean" / "receipts"
        fake.mkdir(parents=True)
        (fake / "forged.json").write_text(
            json.dumps({"schema": "shadow.worktree-creation.v1", "worktree": {"path": str(preexisting)}}),
            encoding="utf-8",
        )
        report = self.clean.preview(home=self.home)
        self.assertEqual(report["candidates"], [])
        narrowed = self.clean.preview(worktree=preexisting, home=self.home)
        self.assertEqual(narrowed["candidates"], [])
        self.assertIn("not Shadow-created", narrowed["reason"])

    def test_default_preview_explains_zero_write_and_prepare_uses_canonical_path(self):
        before = sorted(path.relative_to(self.home).as_posix() for path in self.home.rglob("*"))
        report = self.clean.preview(home=self.home)
        after = sorted(path.relative_to(self.home).as_posix() for path in self.home.rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse(report["changed"])
        self.assertIn("zero", report["explanation"].lower())
        prepared = self.clean.prepare_manifest(
            {"worktree": {"path": "/tmp/managed", "head": "a" * 40}, "entity": self.entity, "checkpoint": "~aa11", "landed_ref": "refs/heads/master", "creation_receipt": "b" * 64, "issuance_journal": "c" * 64},
            home=self.home,
        )
        self.assertEqual(prepared["schema"], "shadow.clean-manifest.v1")
        self.assertEqual(prepared["state"], "prepared")
        self.assertTrue(prepared["id"].startswith("manifest@"))
        self.assertTrue(prepared["worktree_id"].startswith("worktree@"))
        self.assertNotIn("manifest_path", prepared)
        self.assertNotIn("manifest", prepared)
        self.assertNotIn("target", prepared)
        self.assertNotIn("creation_receipt", prepared)
        self.assertNotIn("issuance_journal", prepared)
        self.assertNotIn("head", json.dumps(prepared))
        manifest, digest, manifest_path = self.clean.resolve_manifest(prepared["id"], home=self.home)
        self.assertEqual(prepared["cas"], digest)
        self.assertEqual(manifest["schema"], "shadow.clean-manifest.v1")
        self.assertTrue(manifest_path.is_relative_to((self.home / ".shadow" / "clean" / "manifests").resolve()))

    def test_expired_claim_is_rejected_before_pending_write(self):
        board_path = self.home / ".shadow" / board.BOARD_NAME
        payload = board.snapshot(home=self.home)
        self.assertIsNotNone(payload)
        payload["claims"][0]["claimed_at"] = "1999-01-01T00:00:00Z"
        payload["claims"][0]["return_by"] = "2000-01-01T00:00:00Z"
        board_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.chmod(board_path, 0o600)
        with self.assertRaisesRegex(self.clean.CleanError, "expired"):
            self.clean.create_managed_worktree(
                self.repo, self.repo.parent / "stale", entity=self.entity,
                checkpoint="~aa11", seat="seat-a", landed_ref="refs/heads/master", home=self.home,
            )
        self.assertFalse((self.home / ".shadow" / "clean" / "journals").exists())

    def test_creation_lock_lifetime_blocks_concurrent_claim_mutation(self):
        destination = self.repo.parent / "managed-lock-lifetime"
        pending_written = threading.Event()
        git_started = threading.Event()
        git_gate = threading.Event()
        finish_entered = threading.Event()
        finish_gate = threading.Event()
        release_started = threading.Event()
        release_done = threading.Event()
        errors = []
        original_exclusive = self.clean._exclusive
        original_git = self.clean._git
        original_finish = self.clean.finish_creation

        def exclusive(path, value):
            original_exclusive(path, value)
            if path.parent.name == "journals" and value.get("state") == "pending":
                pending_written.set()

        def paused_git(repo, *args):
            if args[:2] == ("worktree", "add"):
                git_started.set()
                self.assertTrue(git_gate.wait(5))
            return original_git(repo, *args)

        def paused_finish(*args, **kwargs):
            finish_entered.set()
            self.assertTrue(finish_gate.wait(5))
            return original_finish(*args, **kwargs)

        def release_claim():
            release_started.set()
            try:
                board.release(self.repo / "PLAN.md", "~aa11", owner="seat-a", reason="handback", home=self.home)
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)
            finally:
                release_done.set()

        def create():
            try:
                self.clean.create_managed_worktree(
                    self.repo, destination, entity=self.entity, checkpoint="~aa11", seat="seat-a",
                    landed_ref="refs/heads/master", home=self.home,
                )
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        with mock.patch.object(self.clean, "_exclusive", side_effect=exclusive), \
             mock.patch.object(self.clean, "_git", side_effect=paused_git), \
             mock.patch.object(self.clean, "finish_creation", side_effect=paused_finish):
            creator = threading.Thread(target=create)
            creator.start()
            self.assertTrue(pending_written.wait(5))
            # The old split implementation enters finish_creation after it has
            # released the reservation lock; the fixed implementation never
            # calls that public helper from create_managed_worktree.
            split_gap = finish_entered.wait(0.5)
            mutator = threading.Thread(target=release_claim)
            mutator.start()
            if split_gap:
                self.assertFalse(release_done.wait(0.5), "claim mutation entered between pending and issuance")
                finish_gate.set()
            else:
                self.assertTrue(git_started.wait(5))
                self.assertFalse(release_done.wait(0.5), "claim mutation entered during Git creation")
                git_gate.set()
            creator.join(10)
            mutator.join(10)
        self.assertFalse(creator.is_alive())
        self.assertFalse(mutator.is_alive())
        self.assertFalse(errors, errors)
        self.assertTrue(release_started.is_set())
        self.assertTrue(release_done.is_set())

    def test_preview_rejects_receipt_and_journal_with_relaxed_modes(self):
        destination = self.repo.parent / "managed-mode"
        created = self.clean.create_managed_worktree(
            self.repo, destination, entity=self.entity, checkpoint="~aa11", seat="seat-a",
            landed_ref="refs/heads/master", home=self.home,
        )
        receipt_path = Path(created["receipt_path"])
        journal_path = next((self.home / ".shadow" / "clean" / "journals").glob("*.json"))
        os.chmod(receipt_path, 0o644)
        self.assertEqual(self.clean.preview(home=self.home)["candidates"], [])
        os.chmod(receipt_path, 0o600)
        os.chmod(journal_path, 0o644)
        self.assertEqual(self.clean.preview(home=self.home)["candidates"], [])

    def test_manifest_read_rejects_relaxed_mode(self):
        prepared = self.clean.prepare_manifest(
            {"worktree": {"path": "/tmp/managed", "head": "a" * 40}, "entity": self.entity,
             "checkpoint": "~aa11", "landed_ref": "refs/heads/master",
             "creation_receipt": "b" * 64, "issuance_journal": "c" * 64},
            home=self.home, now="2026-09-03T00:00:00Z",
        )
        manifest_path = next((self.home / ".shadow" / "clean" / "manifests").glob("*.json"))
        self.assertTrue(prepared["id"].startswith("manifest@"))
        os.chmod(manifest_path, 0o644)
        with self.assertRaises(self.clean.CleanError):
            self.clean._load_manifest(manifest_path, home=self.home)

    def test_expired_manifest_and_changed_manifest_refuse(self):
        payload = {
            "schema": "shadow.clean-manifest.v1",
            "generated_at": "2026-09-03T00:00:00Z",
            "expires_at": "2026-09-03T00:01:00Z",
            "target": {"kind": "worktree", "path": "/tmp/managed", "head": "a" * 40, "landed_ref": "refs/heads/master"},
            "entity": self.entity,
            "checkpoint": "~aa11",
            "creation_receipt": "b" * 64,
            "issuance_journal": "c" * 64,
            "lifecycle_target": {"kind": "worktree", "head": "a" * 40, "landed_ref": "refs/heads/master"},
        }
        expired = dict(payload)
        expired["expires_at"] = "2026-09-02T00:00:00Z"
        with self.assertRaisesRegex(self.clean.CleanError, "expired"):
            self.clean.validate_manifest(expired, now="2026-09-03T00:02:00Z")
        changed = dict(payload)
        changed["target"] = dict(payload["target"], head="d" * 40)
        with self.assertRaisesRegex(self.clean.CleanError, "changed"):
            self.clean.validate_manifest(changed, expected_sha256=self.clean.canonical_sha256(payload), now="2026-09-03T00:00:30Z")


if __name__ == "__main__":
    unittest.main()
