from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
            now="2026-09-03T00:00:00Z",
        )
        self.assertTrue(Path(prepared["manifest_path"]).is_relative_to((self.home / ".shadow" / "clean" / "manifests").resolve()))

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
