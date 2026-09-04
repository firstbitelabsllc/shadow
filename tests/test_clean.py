from __future__ import annotations

import importlib.util
import hashlib
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

    def test_lifecycle_summary_uses_safe_issued_state_and_strict_shape(self):
        destination = self.repo.parent / "managed-summary"
        self.clean.create_managed_worktree(
            self.repo, destination, entity=self.entity, checkpoint="~aa11", seat="seat-a",
            landed_ref="refs/heads/master", home=self.home,
        )
        plan = self.repo / "PLAN.md"
        plan.write_text(plan.read_text(encoding="utf-8").replace("[pending] managed worktree", "[completed] managed worktree") + "\n- 2026-09-04T00:00:00Z ~aa11 PROOF cmd true -> pass\n", encoding="utf-8")
        board.release(plan, "~aa11", owner="seat-a", reason="completed", home=self.home)
        summary = self.clean.lifecycle_summary(home=self.home)
        self.assertEqual(set(summary[0]), {"id", "state", "entity", "checkpoint"})
        self.assertEqual(summary[0]["state"], "issued")

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
        plan = self.repo / "PLAN.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("[pending] managed worktree", "[completed] managed worktree")
            + "\n- 2026-09-04T00:00:00Z ~aa11 PROOF cmd true -> pass\n",
            encoding="utf-8",
        )
        board.release(plan, "~aa11", owner="seat-a", reason="completed", home=self.home)
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
        with self.assertRaisesRegex(self.clean.CleanError, "not Shadow-created"):
            self.clean.prepare_manifest(
                {"worktree": {"path": "/tmp/managed", "head": "a" * 40}, "entity": self.entity, "checkpoint": "~aa11", "landed_ref": "refs/heads/master", "creation_receipt": "b" * 64, "issuance_journal": "c" * 64},
                home=self.home,
            )

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
        with self.assertRaises(self.clean.CleanError):
            self.clean.prepare_manifest(
                {"worktree": {"path": "/tmp/managed", "head": "a" * 40}, "entity": self.entity,
                 "checkpoint": "~aa11", "landed_ref": "refs/heads/master",
                 "creation_receipt": "b" * 64, "issuance_journal": "c" * 64},
                home=self.home, now="2026-09-03T00:00:00Z",
            )

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


class CleanApplyTests(unittest.TestCase):
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
        git(self.repo, "config", "user.name", "Clean Apply Tests")
        (self.repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
        git(self.repo, "add", "PLAN.md")
        git(self.repo, "commit", "-qm", "seed")
        self.entity = board.entity_id(self.repo / "PLAN.md")
        board.claim(
            self.repo / "PLAN.md", "~aa11", "seat-a", project="demo", priority=2,
            home=self.home,
        )
        self.process_patch = mock.patch.object(self.clean, "_process_holds", return_value=None)
        self.process_patch.start()
        self.addCleanup(self.process_patch.stop)

    def _terminal_managed(self):
        destination = self.repo.parent / "managed-apply"
        created = self.clean.create_managed_worktree(
            self.repo, destination, entity=self.entity, checkpoint="~aa11", seat="seat-a",
            ref="HEAD", landed_ref="refs/heads/master", home=self.home,
        )
        plan = self.repo / "PLAN.md"
        text = plan.read_text(encoding="utf-8")
        text = text.replace("[pending] managed worktree", "[completed] managed worktree")
        text += "\n- 2026-09-04T00:00:00Z ~aa11 PROOF cmd true -> pass\n"
        plan.write_text(text, encoding="utf-8")
        board.release(plan, "~aa11", owner="seat-a", reason="completed", home=self.home)
        candidate = {
            "worktree": {
                "path": str(destination),
                "head": git(destination, "rev-parse", "HEAD"),
                "landed_ref": "refs/heads/master",
            },
            "entity": self.entity,
            "checkpoint": "~aa11",
            "creation_receipt": created["receipt_sha256"],
            "issuance_journal": self.clean.canonical_sha256({}),
        }
        receipt_path = next((self.home / ".shadow" / "clean" / "receipts").glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        candidate["issuance_journal"] = receipt["issuance_journal_sha256"]
        prepared = self.clean.prepare_manifest(candidate, home=self.home)
        manifest, digest, manifest_path = self.clean.resolve_manifest(prepared["id"], home=self.home)
        return destination, prepared, manifest_path, digest

    def _prepare_current(self, destination):
        receipt_path = next((self.home / ".shadow" / "clean" / "receipts").glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        candidate = {
            "worktree": {"path": str(destination), "head": git(destination, "rev-parse", "HEAD"), "landed_ref": "refs/heads/master"},
            "entity": self.entity, "checkpoint": "~aa11", "creation_receipt": receipt["receipt_sha256"],
            "issuance_journal": receipt["issuance_journal_sha256"],
        }
        _path, _payload, digest = self.clean._prepare_manifest_record(candidate, home=self.home)
        return digest, _path

    def _registration_bytes(self, destination):
        listing = git(self.repo, "worktree", "list", "--porcelain")
        admin = Path(git(destination, "rev-parse", "--git-dir"))
        locked = (admin / "locked").read_bytes() if (admin / "locked").exists() else None
        return listing, locked

    def _assert_preserved(self, destination, inode, registration):
        self.assertEqual(destination.stat().st_ino, inode)
        self.assertEqual(self._registration_bytes(destination), registration)

    def test_apply_moves_exact_inode_to_injected_trash_and_restore_is_recoverable(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        inode = destination.stat().st_ino
        result = self.clean.apply_manifest(
            manifest_path, expected_sha256=digest, home=self.home,
            trash_root=trash, by="seat-a",
        )
        self.assertEqual(result["action"], "trashed")
        self.assertFalse(destination.exists())
        self.assertEqual(len(list(trash.iterdir())), 1)
        summary = self.clean.lifecycle_summary(home=self.home)
        self.assertEqual(summary, [{"id": result["receipt"], "state": "trashed", "entity": self.entity, "checkpoint": "~aa11"}])
        trashed = next(trash.iterdir())
        self.assertEqual(trashed.stat().st_ino, inode)
        self.assertTrue(result["receipt"].startswith("worktree@"))
        preview = self.clean.restore_preview(result["receipt"], home=self.home, trash_root=trash)
        self.assertEqual(preview["action"], "would_restore")
        restored = self.clean.restore_apply(
            result["receipt"], expected=preview["cas"], home=self.home, trash_root=trash,
        )
        self.assertEqual(restored["action"], "restored")
        self.assertEqual(destination.stat().st_ino, inode)
        loaded, _ = self.clean._load_trash_receipt(result["receipt"], self.home)
        self.assertEqual(loaded["state"], "restored")
        self.assertTrue(loaded["restored_at"])

    def test_apply_command_surface_never_removes_prunes_forces_or_copies(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        calls = []
        original_git = self.clean._git
        def traced(repo, *args):
            calls.append(args)
            return original_git(repo, *args)
        with mock.patch.object(self.clean, "_git", side_effect=traced):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        flat = " ".join(" ".join(call) for call in calls)
        self.assertNotRegex(flat, r"\b(remove|prune|copy|--force)\b")

    def test_apply_no_replace_race_preserves_intervening_sentinel(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        original_move = self.clean._atomic_move_noreplace
        def race(source, target, **kwargs):
            target.mkdir()
            return original_move(source, target, **kwargs)
        with mock.patch.object(self.clean, "_atomic_move_noreplace", side_effect=race):
            with self.assertRaisesRegex(self.clean.CleanError, "destination appeared|atomic"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        sentinel = trash / f".shadow-{prepared['worktree_id'][len('worktree@'):]}-{digest[:12]}"
        self.assertTrue(sentinel.is_dir())
        self.assertTrue(destination.is_dir())
        self.assertEqual(self._registration_bytes(destination)[1], None)

    def test_apply_source_substitution_refuses_without_unlocking_or_retiring(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        aside = Path(self.tmp.name) / "authentic-apply-aside"
        original_move = self.clean._atomic_move_noreplace

        def substitute(source, target, **kwargs):
            source.rename(aside)
            source.mkdir()
            return original_move(source, target, **kwargs)

        admin = Path(git(destination, "rev-parse", "--git-dir"))
        with mock.patch.object(self.clean, "_atomic_move_noreplace", side_effect=substitute):
            with self.assertRaisesRegex(self.clean.CleanError, "source changed"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self.assertTrue(destination.is_dir())
        self.assertFalse((destination / "PLAN.md").exists())
        self.assertTrue(aside.is_dir())
        self.assertTrue((admin / "locked").is_file())
        self.assertEqual(len(list((self.home / ".shadow" / "clean" / "trash-journals").glob("*.json"))), 1)

    def test_prepare_rejects_caller_controlled_lineage_labels(self):
        destination, _prepared, _manifest_path, _digest = self._terminal_managed()
        receipt_path = next((self.home / ".shadow" / "clean" / "receipts").glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        base = {
            "worktree": {
                "path": str(destination), "head": git(destination, "rev-parse", "HEAD"),
                "landed_ref": receipt["landed_ref"],
            },
            "entity": self.entity, "checkpoint": receipt["claim"]["checkpoint"],
            "creation_receipt": receipt["receipt_sha256"],
            "issuance_journal": receipt["issuance_journal_sha256"],
        }
        for altered in (
            {**base, "entity": "f" * 64},
            {**base, "worktree": {**base["worktree"], "landed_ref": "refs/heads/other"}},
        ):
            with self.assertRaisesRegex(self.clean.CleanError, "lineage|created|entity|checkpoint|landed"):
                self.clean.prepare_manifest(altered, home=self.home)

    def test_restore_no_replace_race_preserves_intervening_sentinel(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        admin = Path(git(destination, "rev-parse", "--git-dir"))
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        artifact = next(trash.iterdir())
        inode = artifact.stat().st_ino
        sentinel = destination
        original_move = self.clean._atomic_move_noreplace
        def race(source, target, **kwargs):
            sentinel.mkdir()
            return original_move(source, target, **kwargs)
        with mock.patch.object(self.clean, "_atomic_move_noreplace", side_effect=race):
            with self.assertRaisesRegex(self.clean.CleanError, "destination appeared|atomic"):
                self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertTrue(sentinel.is_dir())
        self.assertTrue((admin / "locked").is_file())
        self.assertEqual(
            self.clean._read_git_lock(admin / "locked"),
            self.clean._lock_reason(applied["receipt"], digest),
        )
        self.assertTrue(next(trash.iterdir()).is_dir())
        sentinel.rmdir()
        restored = self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(restored["action"], "restored")
        self.assertEqual(destination.stat().st_ino, inode)
        self.assertFalse((admin / "locked").exists())

    def test_apply_retries_after_rename_crash_without_removing_or_forcing(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.apply_manifest(
                manifest_path, expected_sha256=digest, home=self.home,
                trash_root=trash, by="seat-a", crash_at="after_rename",
            )
        self.assertFalse(destination.exists())
        retry = self.clean.apply_manifest(
            prepared["id"], expected_sha256=digest, home=self.home,
            trash_root=trash, by="seat-a",
        )
        self.assertEqual(retry["action"], "trashed")

    def test_expired_prepared_intent_unlocks_and_refuses_without_moving(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a", crash_at="after_lock")
        with mock.patch.object(self.clean, "_load_manifest", side_effect=self.clean.CleanError("manifest expired")):
            with self.assertRaisesRegex(self.clean.CleanError, "expired"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)
        self.assertEqual(list(trash.iterdir()), [])

    def test_apply_recovers_if_power_fails_before_journal_state_replace(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.apply_manifest(
                manifest_path, expected_sha256=digest, home=self.home,
                trash_root=trash, by="seat-a", crash_at="after_rename_before_journal",
            )
        self.assertFalse(destination.exists())
        retry = self.clean.apply_manifest(
            prepared["id"], expected_sha256=digest, home=self.home,
            trash_root=trash, by="seat-a",
        )
        self.assertEqual(retry["action"], "trashed")

    def test_apply_finishes_authenticated_move_after_manifest_expiry(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.apply_manifest(
                manifest_path, expected_sha256=digest, home=self.home,
                trash_root=trash, by="seat-a", crash_at="after_rename_before_journal",
            )
        with mock.patch.object(self.clean, "_load_manifest", side_effect=self.clean.CleanError("manifest expired")):
            retry = self.clean.apply_manifest(
                prepared["id"], expected_sha256=digest, home=self.home,
                trash_root=trash, by="seat-a",
            )
        self.assertEqual(retry["action"], "trashed")
        self.assertFalse(destination.exists())

    def test_apply_recovered_move_content_change_rolls_back_exact_inode(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.apply_manifest(
                manifest_path, expected_sha256=digest, home=self.home,
                trash_root=trash, by="seat-a", crash_at="after_rename_before_journal",
            )
        artifact = next(trash.iterdir())
        plan_file = artifact / "PLAN.md"
        plan_file.write_bytes(plan_file.read_bytes() + b"changed-in-trash\n")
        with self.assertRaisesRegex(self.clean.CleanError, "dirty|content"):
            self.clean.apply_manifest(prepared["id"], expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)
        self.assertEqual(list(trash.iterdir()), [])

    def test_apply_committed_move_sync_failure_retries_from_journal(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        original_move = self.clean._atomic_move_noreplace

        def fail_sync_after_move(source, target, **kwargs):
            def fail(_fd):
                raise OSError("sync failure")
            with mock.patch.object(self.clean.os, "fsync", side_effect=fail):
                return original_move(source, target, **kwargs)

        with mock.patch.object(self.clean, "_atomic_move_noreplace", side_effect=fail_sync_after_move):
            with self.assertRaisesRegex(self.clean.CleanError, "sync"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self.assertFalse(destination.exists())
        self.assertEqual(len(list((self.home / ".shadow" / "clean" / "trash-journals").glob("*.json"))), 1)
        retry = self.clean.apply_manifest(prepared["id"], expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self.assertEqual(retry["action"], "trashed")

    def test_apply_receipt_crash_retires_moved_journal_on_retry(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.apply_manifest(
                manifest_path, expected_sha256=digest, home=self.home,
                trash_root=trash, by="seat-a", crash_at="after_public_receipt",
            )
        journals = list((self.home / ".shadow" / "clean" / "trash-journals").glob("*.json"))
        self.assertEqual(len(journals), 1)
        retry = self.clean.apply_manifest(
            prepared["id"], expected_sha256=digest, home=self.home,
            trash_root=trash, by="seat-a",
        )
        self.assertEqual(retry["action"], "already_trashed")
        self.assertEqual(list((self.home / ".shadow" / "clean" / "trash-journals").glob("*.json")), [])

    def test_apply_refuses_changed_target_metadata_after_preview(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        os.utime(destination, None)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "unchanged|changed"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")

    def test_apply_refuses_tracked_dirty_and_preserves_registration(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        original = (destination / "PLAN.md").read_bytes()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        (destination / "PLAN.md").write_bytes(original + b"dirty\n")
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "dirty|untracked"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self.assertEqual((destination / "PLAN.md").read_bytes(), original + b"dirty\n")
        self._assert_preserved(destination, inode, registration)
        summaries = self.clean.lifecycle_summary(home=self.home)
        self.assertEqual(summaries[0]["state"], "noneligible")
        git(destination, "add", "PLAN.md")
        with self.assertRaisesRegex(self.clean.CleanError, "dirty|ignored"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)

    def test_apply_refuses_untracked_and_ignored_files(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        (destination / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "dirty|untracked"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)
        (self.repo / ".git" / "info" / "exclude").write_text("ignored.txt\n", encoding="utf-8")
        (destination / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        with self.assertRaisesRegex(self.clean.CleanError, "dirty|ignored"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)

    def test_apply_refuses_unlanded_head_and_preserves_registration(self):
        destination, _prepared, _old_path, _old_digest = self._terminal_managed()
        (destination / "landed-later.txt").write_text("pending\n", encoding="utf-8")
        git(destination, "add", "landed-later.txt")
        git(destination, "commit", "-qm", "unlanded")
        new_digest, _new_path = self._prepare_current(destination)
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "landed"):
            self.clean.apply_manifest(_new_path, expected_sha256=new_digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)

    def test_apply_refuses_process_cwd_and_open_fd(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        self.process_patch.stop()
        old_cwd = Path.cwd()
        try:
            os.chdir(destination)
            with self.assertRaisesRegex(self.clean.CleanError, "process holds"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        finally:
            os.chdir(old_cwd)
            self.process_patch.start()
        self._assert_preserved(destination, inode, registration)
        with (destination / "PLAN.md").open("rb"):
            self.process_patch.stop()
            try:
                with self.assertRaisesRegex(self.clean.CleanError, "process holds"):
                    self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
            finally:
                self.process_patch.start()
        self._assert_preserved(destination, inode, registration)

    def test_apply_refuses_when_process_inspection_is_unavailable(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with mock.patch.object(self.clean, "_process_holds", side_effect=self.clean.CleanError("process inspection unavailable")):
            with self.assertRaisesRegex(self.clean.CleanError, "inspection unavailable"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)

    def test_apply_refuses_submodule_state(self):
        destination, _prepared, _old_path, _old_digest = self._terminal_managed()
        module = Path(self.tmp.name) / "module"
        module.mkdir()
        git(module, "init", "-q")
        git(module, "config", "user.email", "test@example.invalid")
        git(module, "config", "user.name", "Clean Apply Tests")
        (module / "module.txt").write_text("module\n", encoding="utf-8")
        git(module, "add", "module.txt")
        git(module, "commit", "-qm", "module")
        subprocess.run(["git", "-C", str(destination), "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(module), "modules/sub"], check=True)
        git(destination, "commit", "-qm", "add submodule")
        head = git(destination, "rev-parse", "HEAD")
        git(self.repo, "update-ref", "refs/heads/master", head)
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        with self.assertRaisesRegex(self.clean.CleanError, "submodule"):
            self.clean.prepare_manifest({
                "worktree": {"path": str(destination), "head": head, "landed_ref": "refs/heads/master"},
                "entity": self.entity, "checkpoint": "~aa11",
                "creation_receipt": json.loads(next((self.home / ".shadow" / "clean" / "receipts").glob("*.json")).read_text())["receipt_sha256"],
                "issuance_journal": json.loads(next((self.home / ".shadow" / "clean" / "receipts").glob("*.json")).read_text())["issuance_journal_sha256"],
            }, home=self.home)
        self._assert_preserved(destination, inode, registration)

    def test_apply_collision_refusal_does_not_leave_git_locked(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        collision = trash / f".shadow-{prepared['worktree_id'][len('worktree@'):]}-{digest[:12]}"
        collision.mkdir()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        with self.assertRaisesRegex(self.clean.CleanError, "destination"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)

    def test_wrong_or_symlinked_git_lock_refuses_untouched(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        admin = Path(git(destination, "rev-parse", "--git-dir"))
        locked = admin / "locked"
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        locked.write_text("shadow clean other-transaction\n", encoding="utf-8")
        locked_registration = self._registration_bytes(destination)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "locked"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, locked_registration)
        locked.unlink()
        marker = admin / "wrong-lock-reason"
        marker.write_text("shadow clean\n", encoding="utf-8")
        locked.symlink_to(marker)
        symlink_registration = self._registration_bytes(destination)
        with self.assertRaisesRegex(self.clean.CleanError, "unsafe"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, symlink_registration)
        locked.unlink()
        marker.unlink()

    def test_primary_worktree_is_rejected_by_snapshot_guard(self):
        destination, _prepared, _manifest_path, _digest = self._terminal_managed()
        created_path = next((self.home / ".shadow" / "clean" / "receipts").glob("*.json"))
        receipt = json.loads(created_path.read_text(encoding="utf-8"))
        source = self.repo.resolve()
        git(source, "add", "PLAN.md")
        git(source, "commit", "-qm", "terminalize plan")
        metadata = source.lstat()
        listing, _paths = self.clean._worktree_listing(source)
        head = git(source, "rev-parse", "HEAD")
        status_sha = hashlib.sha256(b"").hexdigest()
        manifest = {
            "target": {
                "path": str(source), "head": head, "landed_ref": "refs/heads/master",
                "device": metadata.st_dev, "inode": metadata.st_ino, "mode": metadata.st_mode,
                "mtime_ns": metadata.st_mtime_ns, "ctime_ns": metadata.st_ctime_ns,
                "status_sha256": status_sha,
                "worktree_listing_sha256": hashlib.sha256(listing.encode()).hexdigest(),
                "tree_sha256": self.clean._tree_snapshot(source),
            }
        }
        fake = {**receipt, "worktree": {"path": str(source), "device": metadata.st_dev, "inode": metadata.st_ino}, "git": {"common_dir": str(source / ".git"), "admin_dir": str(source / ".git")}}
        journal = {"source_repo": str(source)}
        with self.assertRaisesRegex(self.clean.CleanError, "primary"):
            self.clean._target_snapshot(manifest, fake, journal, self.home)

    def test_apply_refuses_symlinked_target_without_touching_registered_child(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        backup = destination.with_name("managed-symlink-backup")
        destination.rename(backup)
        destination.symlink_to(backup, target_is_directory=True)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        try:
            with self.assertRaisesRegex(self.clean.CleanError, "symlink"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
            self.assertTrue(backup.is_dir())
            self.assertTrue(destination.is_symlink())
        finally:
            destination.unlink()
            backup.rename(destination)

    def test_apply_refuses_changed_manifest_and_forged_trash_receipt(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        original_manifest = manifest_path.read_bytes()
        manifest_path.write_bytes(original_manifest.replace(b'"head": "', b'"head": "0'))
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "changed|manifest"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        manifest_path.write_bytes(original_manifest)
        self._assert_preserved(destination, inode, registration)

        # A strict-shaped private file is still not an authenticated retirement.
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        receipt_path = next((self.home / ".shadow" / "clean" / "trash-receipts").glob("*.json"))
        forged = json.loads(receipt_path.read_text(encoding="utf-8"))
        forged["creation_receipt"] = "0" * 64
        receipt_path.write_text(json.dumps(forged, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(receipt_path, 0o600)
        with self.assertRaisesRegex(self.clean.CleanError, "backed|lineage|malformed|digest"):
            self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)

    def test_apply_rechecks_final_status_race_before_rename(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        empty_sha = hashlib.sha256(b"").hexdigest()
        with mock.patch.object(self.clean, "_status_snapshot", side_effect=[("", empty_sha), self.clean.CleanError("worktree became dirty")]):
            with self.assertRaisesRegex(self.clean.CleanError, "dirty"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)

    def test_apply_retries_owned_unlock_after_post_lock_refusal(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        original_git = self.clean._git
        original_final = self.clean._final_apply_check
        unlock_attempts = []
        mutation = []

        def fail_first_unlock(repo, *args):
            if args[:2] == ("worktree", "unlock") and not unlock_attempts:
                unlock_attempts.append(1)
                raise self.clean.CleanError("unlock unavailable")
            return original_git(repo, *args)

        def mutate_at_final(info, *, worktree_id, manifest_digest, journal_path):
            if not mutation:
                mutation.append(1)
                plan_file = destination / "PLAN.md"
                plan_file.write_bytes(plan_file.read_bytes() + b"changed-after-lock\n")
            return original_final(info, worktree_id=worktree_id, manifest_digest=manifest_digest, journal_path=journal_path)

        # A real target mutation after lock makes both the first final check
        # and the retry fail. The first rollback cannot unlock, so the
        # authenticated prepared journal must remain for the second attempt
        # to retry that exact unlock before refusing cleanly.
        with mock.patch.object(self.clean, "_final_apply_check", side_effect=mutate_at_final), \
             mock.patch.object(self.clean, "_git", side_effect=fail_first_unlock):
            with self.assertRaisesRegex(self.clean.CleanError, "changed after lock|dirty"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
            journal_dir = self.home / ".shadow" / "clean" / "trash-journals"
            self.assertEqual(len(list(journal_dir.glob("*.json"))), 1)
            self.assertTrue((Path(git(destination, "rev-parse", "--git-dir")) / "locked").is_file())
            with self.assertRaisesRegex(self.clean.CleanError, "changed after lock|dirty"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)
        self.assertEqual(list((self.home / ".shadow" / "clean" / "trash-journals").glob("*.json")), [])
        self.assertEqual(list(trash.iterdir()), [])

    def test_post_move_mismatch_rolls_back_same_inode_and_unlocks(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        inode, registration = destination.stat().st_ino, self._registration_bytes(destination)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with mock.patch.object(self.clean, "_post_move_check", side_effect=self.clean.CleanError("Trash worktree content changed after move")):
            with self.assertRaisesRegex(self.clean.CleanError, "content changed"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self._assert_preserved(destination, inode, registration)
        self.assertEqual(list(trash.iterdir()), [])

    def test_post_move_rollback_collision_keeps_journal_until_safe_retry(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        original_post = self.clean._post_move_check
        injected = []

        def collide_after_move(info, target, *, worktree_id, manifest_digest):
            if not injected:
                injected.append(1)
                info["target"].mkdir()
                raise self.clean.CleanError("post-move mismatch")
            return original_post(info, target, worktree_id=worktree_id, manifest_digest=manifest_digest)

        with mock.patch.object(self.clean, "_post_move_check", side_effect=collide_after_move):
            with self.assertRaisesRegex(self.clean.CleanError, "post-move mismatch|destination appeared"):
                self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
            self.assertTrue(destination.is_dir())
            self.assertEqual(len(list((self.home / ".shadow" / "clean" / "trash-journals").glob("*.json"))), 1)
            with self.assertRaisesRegex(self.clean.CleanError, "destination|changed"):
                self.clean.apply_manifest(prepared["id"], expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
            self.assertTrue(destination.is_dir())
            destination.rmdir()
            retry = self.clean.apply_manifest(prepared["id"], expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self.assertEqual(retry["action"], "trashed")
        self.assertFalse(destination.exists())

    def test_restore_crash_after_unlock_converges(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash, crash_at="restore_after_unlock")
        restored = self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(restored["action"], "restored")
        self.assertTrue(destination.is_dir())

    def test_restore_receipt_crash_retires_unlocked_journal_on_retry(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash, crash_at="restore_after_receipt")
        self.assertTrue((self.home / ".shadow" / "clean" / "restore-journals").exists())
        retry = self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(retry["action"], "already_restored")
        self.assertEqual(list((self.home / ".shadow" / "clean" / "restore-journals").glob("*.json")), [])

    def test_apply_refuses_active_claim_and_preserves_worktree(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        board.claim(self.repo / "PLAN.md", "~aa11", "seat-a", project="demo", priority=2, home=self.home)
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        with self.assertRaisesRegex(self.clean.CleanError, "checkpoint is not terminal|active claim"):
            self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        self.assertTrue(destination.exists())

    def test_cli_apply_and_restore_keep_output_path_free(self):
        destination, prepared, manifest_path, digest = self._terminal_managed()
        trash = self.home / ".Trash"
        trash.mkdir()
        env = {**os.environ, "HOME": str(self.home)}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch("sys.stdout", new_callable=__import__("io").StringIO):
            self.clean.main(["--apply", "--manifest", str(manifest_path), "--expect", digest, "--by", "seat-a", "--json"])
            applied_stdout = __import__("sys").stdout.getvalue()
        self.assertNotIn(str(destination), applied_stdout)
        public = json.loads(applied_stdout)
        self.assertEqual(public["action"], "trashed")
        with mock.patch.dict(os.environ, env, clear=False), mock.patch("sys.stdout", new_callable=__import__("io").StringIO):
            self.clean.main(["--restore", "--receipt", public["receipt"], "--json"])
            restore_stdout = __import__("sys").stdout.getvalue()
        restore = json.loads(restore_stdout)
        self.assertTrue(restore["cas"])
        self.assertNotIn(str(destination), restore_stdout)

    def test_restore_retries_after_rename_crash(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        with self.assertRaisesRegex(self.clean.CleanError, "simulated crash"):
            self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash, crash_at="restore_after_rename")
        restored = self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(restored["action"], "restored")
        self.assertTrue(destination.is_dir())

    def test_restore_retries_after_post_rename_sync_failure(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        original_sync = self.clean._fsync_directory
        sync_calls = []

        def fail_first_sync(path):
            if not sync_calls:
                sync_calls.append(1)
                raise self.clean.CleanError("sync failure")
            return original_sync(path)

        with mock.patch.object(self.clean, "_fsync_directory", side_effect=fail_first_sync):
            with self.assertRaisesRegex(self.clean.CleanError, "sync"):
                self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(trash.iterdir()), [])
        self.assertEqual(len(list((self.home / ".shadow" / "clean" / "restore-journals").glob("*.json"))), 1)
        restored = self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(restored["action"], "restored")

    def test_restore_source_substitution_never_unlocks_replacement(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        aside = Path(self.tmp.name) / "authentic-aside"
        original_move = self.clean._atomic_move_noreplace

        def substitute(source, target, **kwargs):
            source.rename(aside)
            source.mkdir()
            return original_move(source, target, **kwargs)

        admin = self.repo / ".git" / "worktrees" / destination.name
        with mock.patch.object(self.clean, "_atomic_move_noreplace", side_effect=substitute):
            with self.assertRaisesRegex(self.clean.CleanError, "identity|content|changed"):
                self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertTrue(destination.is_dir())
        self.assertFalse((destination / "PLAN.md").exists())
        self.assertTrue((admin / "locked").is_file())
        self.assertTrue(aside.is_dir())

    def test_restore_source_identity_change_before_unlock_refuses_and_keeps_lock(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        admin = Path(git(destination, "rev-parse", "--git-dir"))
        applied = self.clean.apply_manifest(manifest_path, expected_sha256=digest, home=self.home, trash_root=trash, by="seat-a")
        preview = self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)
        unlocks = []
        original_git = self.clean._git

        def traced_git(repo, *args):
            if args[:2] == ("worktree", "unlock"):
                unlocks.append(1)
            return original_git(repo, *args)

        with mock.patch.object(self.clean, "_source_identity", return_value="substituted-source"), \
             mock.patch.object(self.clean, "_git", side_effect=traced_git):
            with self.assertRaisesRegex(self.clean.CleanError, "source|identity|registration"):
                self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(unlocks, [])
        self.assertTrue(destination.is_dir())
        self.assertTrue((destination / "PLAN.md").is_file())
        self.assertTrue((admin / "locked").exists())
        self.assertTrue(next((self.home / ".shadow" / "clean" / "restore-journals").glob("*.json")).is_file())
        restored = self.clean.restore_apply(applied["receipt"], expected=preview["cas"], home=self.home, trash_root=trash)
        self.assertEqual(restored["action"], "restored")

    def test_restore_refuses_post_trash_content_change(self):
        destination, _prepared, manifest_path, digest = self._terminal_managed()
        trash = Path(self.tmp.name) / "Trash"
        trash.mkdir()
        applied = self.clean.apply_manifest(
            manifest_path, expected_sha256=digest, home=self.home,
            trash_root=trash, by="seat-a",
        )
        artifact = next(trash.iterdir())
        tracked = artifact / "PLAN.md"
        tracked.write_text(tracked.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
        with self.assertRaisesRegex(self.clean.CleanError, "content|dirty|changed"):
            self.clean.restore_preview(applied["receipt"], home=self.home, trash_root=trash)


if __name__ == "__main__":
    unittest.main()
