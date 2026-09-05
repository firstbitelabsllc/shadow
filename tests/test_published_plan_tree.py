"""Published completion readers use one Git tip, never worktree tree objects."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.test_return import (
    complete_manual_row, git, payload, recovery_command, remote_claim,
    remote_fixture, run,
)
from tests.plan_tree_fixture import install_plan_tree, shard_path
import shadow_plan_store as store


class PublishedPlanTree(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo, self.remote, self.home, self.env, self.receipt = remote_fixture(self.root)
        complete_manual_row(self.repo, "read artifact -> correct")
        self.content = (self.repo / "PLAN.md").read_bytes()

    def publish_tree(self, *, relative: str = "PLAN.md") -> dict:
        parent = (self.repo / relative).parent
        parent.mkdir(parents=True, exist_ok=True)
        _, self.build = install_plan_tree(parent, self.content, return_build=True)
        self.commit_push()
        return {
            "head": git(self.repo, "rev-parse", "HEAD"),
            "blob": git(self.repo, "rev-parse", f"HEAD:{relative}"),
            "relative": relative,
        }

    def commit_push(self) -> None:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "publish fixture change")
        git(self.repo, "push", "-qu", "origin", "HEAD:main")

    def assert_ref_unchanged(self, before: str) -> None:
        self.assertEqual(git(self.remote, "rev-parse", self.receipt["ref"]), before)

    def second_seat(self) -> tuple[Path, dict]:
        second = self.root / "second"
        subprocess.run(["git", "clone", "-q", str(self.remote), str(second)], check=True)
        home = self.root / "home-b"
        home.mkdir()
        git(second, "config", "user.email", "shadow-test@example.invalid")
        git(second, "config", "user.name", "Shadow Test")
        return second, {**os.environ, "HOME": str(home), "SHADOW_PORTFOLIO_ROOT": str(second)}

    def test_tree_materializes_from_pinned_git_tip_despite_local_poison(self) -> None:
        token = self.publish_tree()
        (self.repo / "PLAN.md").write_bytes(b"local unrelated plan")
        for digest in self.build.objects:
            shard_path(self.repo, digest).write_bytes(b"local poison")
        result = remote_claim.published_plan_snapshot(self.repo, token)
        self.assertEqual(result, (self.content, token["head"]))

    def test_nested_plan_does_not_fall_back_to_default_plan(self) -> None:
        token = self.publish_tree(relative="plans/operations/PLAN.md")
        (self.repo / "PLAN.md").write_text("# Different entity, no completed row\n")
        self.commit_push()
        self.assertEqual(remote_claim.published_plan_bytes(self.repo, token), self.content)

    def test_plain_markdown_still_reads_exact_bytes(self) -> None:
        git(self.repo, "push", "-qu", "origin", "HEAD:main")
        self.assertEqual(remote_claim.published_plan_bytes(self.repo, self.receipt["plan"]), self.content)

    def test_missing_remote_object_cannot_borrow_valid_local_object(self) -> None:
        token = self.publish_tree()
        digest = self.build.root["catalog_root"]
        path = shard_path(self.repo, digest)
        valid = path.read_bytes()
        path.unlink()
        self.commit_push()
        path.write_bytes(valid)
        before = git(self.remote, "rev-parse", self.receipt["ref"])
        with self.assertRaises(remote_claim.RemoteClaimError):
            remote_claim.published_plan_snapshot(self.repo, token)
        self.assert_ref_unchanged(before)

    def test_bad_digest_is_refused_even_with_good_local_object(self) -> None:
        token = self.publish_tree()
        path = shard_path(self.repo, self.build.root["catalog_root"])
        valid = path.read_bytes()
        # Remain valid JSON with the same logical contents. Only its binding
        # to the digest is wrong, so a parser failure cannot hide a missing
        # integrity check.
        path.write_bytes(valid + b"\n")
        self.commit_push()
        path.write_bytes(valid)
        with self.assertRaises(remote_claim.RemoteClaimError):
            remote_claim.published_plan_snapshot(self.repo, token)

    def test_symlink_blob_cannot_be_published_plan_or_object(self) -> None:
        token = self.publish_tree()
        path = shard_path(self.repo, self.build.root["catalog_root"])
        path.unlink()
        path.symlink_to("elsewhere")
        self.commit_push()
        with self.assertRaises(remote_claim.RemoteClaimError):
            remote_claim.published_plan_snapshot(self.repo, token)
        path.unlink()
        path.write_bytes(self.build.objects[self.build.root["catalog_root"]])
        plan = self.repo / "PLAN.md"
        plan.unlink()
        plan.symlink_to("elsewhere")
        self.commit_push()
        with self.assertRaises(remote_claim.RemoteClaimError):
            remote_claim.published_plan_snapshot(self.repo, token)

    def test_read_budget_stops_a_valid_tree_before_all_objects_are_read(self) -> None:
        token = self.publish_tree()
        # Lower the actual boundary for a small native-Git fixture; do not mock
        # any reader, object, digest or outcome.
        with mock.patch.object(remote_claim, "MAX_PUBLISHED_PLAN_READS", 2):
            with self.assertRaisesRegex(remote_claim.RemoteClaimError, "read budget"):
                remote_claim.published_plan_snapshot(self.repo, token)

    def test_source_byte_budget_is_independent_of_declared_logical_bytes(self) -> None:
        token = self.publish_tree()
        with mock.patch.object(remote_claim, "MAX_PUBLISHED_PLAN_SOURCE_BYTES", len(self.build.root_bytes)):
            with self.assertRaisesRegex(remote_claim.RemoteClaimError, "bounded size"):
                remote_claim.published_plan_snapshot(self.repo, token)

    def test_zero_byte_repeated_shards_cannot_evade_the_read_budget(self) -> None:
        token = self.publish_tree()
        empty_digest = store.digest_bytes(b"")
        catalog = store.canonical_json({
            "schema": store.PAGE_SCHEMA, "tree": "catalog", "kind": "leaf",
            "entries": [{"key": f"{n:012d}", "value": {"object": empty_digest, "bytes": 0}} for n in range(8)],
        })
        catalog_digest = store.digest_bytes(catalog)
        for digest, body in ((empty_digest, b""), (catalog_digest, catalog)):
            path = shard_path(self.repo, digest)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        root = {**self.build.root, "catalog_root": catalog_digest, "logical_bytes": 0, "logical_sha256": empty_digest}
        (self.repo / "PLAN.md").write_bytes(store.ROOT_PREFIX + store.canonical_json(root) + store.ROOT_SUFFIX)
        self.commit_push()
        with mock.patch.object(remote_claim, "MAX_PUBLISHED_PLAN_READS", 4):
            with self.assertRaisesRegex(remote_claim.RemoteClaimError, "read budget"):
                remote_claim.published_plan_snapshot(self.repo, token)

    def test_unpublished_head_is_refused(self) -> None:
        token = self.publish_tree()
        (self.repo / "unpublished.txt").write_text("unpublished")
        git(self.repo, "add", "unpublished.txt")
        git(self.repo, "commit", "-qm", "unpublished")
        token["head"] = git(self.repo, "rev-parse", "HEAD")
        self.assertIsNone(remote_claim.published_plan_snapshot(self.repo, token))

    def test_oversized_declared_logical_plan_is_refused(self) -> None:
        token = self.publish_tree()
        root = dict(self.build.root)
        root["logical_bytes"] = remote_claim.MAX_PLAN_BYTES + 1
        (self.repo / "PLAN.md").write_bytes(store.ROOT_PREFIX + store.canonical_json(root) + store.ROOT_SUFFIX)
        self.commit_push()
        with self.assertRaises(remote_claim.RemoteClaimError):
            remote_claim.published_plan_snapshot(self.repo, token)

    def test_native_return_recovers_tree_claim_and_preserves_owner_and_idempotence(self) -> None:
        self.publish_tree()
        second, env = self.second_seat()
        entity, _ = recovery_command(env, second)
        before = git(self.remote, "rev-parse", self.receipt["ref"])
        wrong = run(env, "return", "--entity", entity, "--row", "~aa11", "--by", "seat-b", cwd=second)
        self.assertNotEqual(wrong.returncode, 0)
        self.assert_ref_unchanged(before)
        returned = run(env, "return", "--entity", entity, "--row", "~aa11", "--by", "seat-a", cwd=second)
        self.assertEqual(returned.returncode, 0, returned.stdout + returned.stderr)
        stored = json.loads(git(self.remote, "show", f"{self.receipt['ref']}:claim.json"))
        self.assertEqual((stored["state"], stored["owner"]), ("completed", "seat-a"))
        self.assertEqual(payload(Path(env["HOME"]))["claims"], [])
        completed_tip = git(self.remote, "rev-parse", self.receipt["ref"])
        repeated = run(env, "return", "--entity", entity, "--row", "~aa11", "--by", "seat-a", cwd=second)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assert_ref_unchanged(completed_tip)

    def test_native_return_refuses_published_conflicting_row(self) -> None:
        self.publish_tree()
        second, env = self.second_seat()
        entity, _ = recovery_command(env, second)
        conflicted = self.content.replace(b"[completed] inspect", b"[pending] inspect")
        install_plan_tree(self.repo, conflicted)
        self.commit_push()
        before = git(self.remote, "rev-parse", self.receipt["ref"])
        result = run(env, "return", "--entity", entity, "--row", "~aa11", "--by", "seat-a", cwd=second)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_ref_unchanged(before)

    def test_native_accept_recovers_a_real_cmd_completion_after_tree_migration(self) -> None:
        root = self.root / "cmd-fixture"
        root.mkdir()
        repo, remote, _home, env, receipt = remote_fixture(root, proof="cmd true")
        accepted = run(env, "accept", "--repo", str(repo), "--row", "~aa11", "--by", "seat-a", "--no-push")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        content = (repo / "PLAN.md").read_bytes()
        self.assertIn(b"pass (accept)", content)
        install_plan_tree(repo, content)
        git(repo, "add", "PLAN.md", "PLAN.d")
        git(repo, "commit", "-qm", "migrate accepted plan")
        git(repo, "push", "-qu", "origin", "HEAD:main")
        second = root / "second"
        subprocess.run(["git", "clone", "-q", str(remote), str(second)], check=True)
        home = root / "home-b"
        home.mkdir()
        env_b = {**os.environ, "HOME": str(home), "SHADOW_PORTFOLIO_ROOT": str(second)}
        entity, _ = recovery_command(env_b, second)
        result = run(env_b, "accept", "--entity", entity, "--row", "~aa11", "--by", "seat-a", cwd=second)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        stored = json.loads(git(remote, "show", f"{receipt['ref']}:claim.json"))
        self.assertEqual(stored["state"], "completed")
        self.assertEqual(payload(home)["claims"], [])


if __name__ == "__main__":
    unittest.main()
