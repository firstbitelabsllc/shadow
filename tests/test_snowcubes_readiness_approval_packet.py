"""Tests for scripts/vidux-snowcubes-readiness-approval-packet.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-snowcubes-readiness-approval-packet.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("snowcubes_readiness_approval_packet", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


approval_packet = _load_module()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _init_git_repo(path: Path) -> str:
    path.mkdir(parents=True)
    (path / "README.md").write_text("source\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=path, capture_output=True, text=True, check=True)
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, text=True, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Vidux Test",
            "-c",
            "user.email=vidux-test@example.invalid",
            "commit",
            "-m",
            "seed source",
        ],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class SnowcubesReadinessApprovalPacketTests(unittest.TestCase):
    def test_packet_is_ready_for_approval_without_mutating(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "trysnowcubes-web-worktrees" / "reviews-otel-traces" / "outputs" / "consignment-tracker"
            candidate.mkdir(parents=True)
            (candidate / "snowcubes-consignment-partners.csv").write_text("redacted\nredacted\n", encoding="utf-8")
            (candidate / "snowcubes-consignment-live-ledger.csv").write_text("redacted\n" * 4, encoding="utf-8")
            canonical = root / "trysnowcubes-web-consign" / "outputs" / "consignment-tracker"
            source_worktree = root / "moussey-worktrees" / "snowcubes-local-ci-source-20260601"
            source_ref = _init_git_repo(source_worktree)
            goal_audit = root / "goal-audit.json"
            _write_json(
                goal_audit,
                {
                    "local_ci_launch_trust": {
                        "current_source_notes": {
                            "tracker_diagnosis": {
                                "canonical_tracker": str(canonical),
                                "recommended_candidate": {"path": str(candidate)},
                            },
                            "clean_source_candidate": {
                                "source_ref": source_ref,
                                "worktree": str(source_worktree),
                            },
                        }
                    }
                },
            )

            payload = approval_packet.build_packet(
                goal_audit_path=goal_audit,
                mcp_dir=root / "firstbite-local-ci",
                run_id_prefix="test-snowcubes-readiness",
            )

            self.assertEqual(payload["status"], "ready_for_approval")
            self.assertTrue(payload["readonly"])
            self.assertFalse(payload["local_ci_lanes_executed"])
            self.assertFalse(payload["tracker_files_copied"])
            self.assertEqual(payload["approval_gate_status"], "operator_gated")
            self.assertTrue(payload["restore_requires_explicit_approval"])
            self.assertTrue(payload["execute_requires_explicit_approval"])
            self.assertTrue(payload["approval_required"])
            self.assertIn("explicit operator approval", payload["next_action"])
            self.assertEqual(payload["required_files"], approval_packet.REQUIRED_TRACKER_FILES)
            self.assertFalse(canonical.exists())
            self.assertTrue(payload["candidate"]["ready"])
            self.assertEqual(
                payload["candidate"]["files"]["snowcubes-consignment-live-ledger.csv"]["line_count"],
                4,
            )
            self.assertFalse(payload["canonical_tracker"]["complete"])
            self.assertTrue(payload["source_ref"]["ready"])
            commands = payload["lane"]["commands"]
            self.assertTrue(commands["approval_required"])
            self.assertTrue(commands["execute_approval_required"])
            self.assertIn("cp -p", commands["restore_commands"][1])
            self.assertIn("moussey_snowcubes_readiness", commands["execute_command"])
            self.assertIn(source_ref, commands["execute_command"])
            self.assertIn("run_lanes", commands["execute_command"])
            self.assertIn("did not execute local-CI lanes", " ".join(payload["non_claims"]))

    def test_dirty_source_ref_blocks_approval_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate"
            candidate.mkdir()
            for filename in approval_packet.REQUIRED_TRACKER_FILES:
                (candidate / filename).write_text("redacted\n", encoding="utf-8")
            source_worktree = root / "source"
            source_ref = _init_git_repo(source_worktree)
            (source_worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            goal_audit = root / "goal-audit.json"
            _write_json(
                goal_audit,
                {
                    "local_ci_launch_trust": {
                        "current_source_notes": {
                            "tracker_diagnosis": {
                                "canonical_tracker": str(root / "canonical"),
                                "recommended_candidate": {"path": str(candidate)},
                            },
                            "clean_source_candidate": {
                                "source_ref": source_ref,
                                "worktree": str(source_worktree),
                            },
                        }
                    }
                },
            )

            payload = approval_packet.build_packet(goal_audit_path=goal_audit)

            self.assertEqual(payload["status"], "not_ready")
            self.assertFalse(payload["source_ref"]["ready"])
            checks = {item["id"]: item for item in payload["checks"]}
            self.assertEqual(checks["source_ref"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
