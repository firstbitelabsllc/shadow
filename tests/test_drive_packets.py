"""Focused tests for PLAN-owned Shadow Drive Packets."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import shadow_drive_lib as drive


def document() -> dict:
    return {
        "schema": "shadow.drive.v1",
        "revision": 3,
        "lanes": [
            {
                "id": "improve-copy",
                "state": "ready",
                "task_kind": "dev",
                "summary": "Make the welcome message easier to understand.",
                "task": "Improve the welcome message and keep the focused test green.",
                "allowed_paths": ["src/welcome.ts", "tests/welcome.test.ts"],
                "proof": ["python3", "-m", "unittest", "tests.test_welcome"],
                "merge": "ordinary",
            },
            {
                "id": "repair-parser",
                "state": "ready",
                "task_kind": "debug",
                "summary": "Fix the reproducible parser failure.",
                "task": "Fix the parser failure and run the declared proof.",
                "allowed_paths": ["src/parser.py", "tests/test_parser.py"],
                "proof": ["python3", "-m", "unittest", "tests.test_parser"],
                "merge": "manual",
            },
        ],
    }


def plan(payload: dict) -> str:
    return "# Example\n\n## Shadow Drive\n\n<!-- shadow-drive.v1\n" + json.dumps(payload, indent=2) + "\n-->\n"


class DrivePacketTests(unittest.TestCase):
    def test_extracts_one_closed_plan_owned_packet(self) -> None:
        parsed = drive.extract_document(plan(document()))
        assert parsed is not None
        self.assertEqual(parsed["schema"], drive.DRIVE_SCHEMA)
        self.assertEqual(parsed["revision"], 3)
        self.assertEqual(parsed["lanes"][0]["id"], "improve-copy")
        self.assertEqual(parsed["lanes"][0]["proof"], ["python3", "-m", "unittest", "tests.test_welcome"])

    def test_packet_rejects_unknown_fields_multiple_blocks_and_private_content(self) -> None:
        unknown = document()
        unknown["owner"] = "not a second authority"
        with self.assertRaises(drive.DrivePacketError):
            drive.extract_document(plan(unknown))

        private_task = document()
        private_task["lanes"][0]["task"] = "Read /Users/example/private-plan.md before changing anything."
        with self.assertRaises(drive.DrivePacketError):
            drive.extract_document(plan(private_task))

        secret_proof = document()
        secret_proof["lanes"][0]["proof"] = ["tool", "Bearer " + "abcdefghijklmnopqrstuvwxyz"]
        with self.assertRaises(drive.DrivePacketError):
            drive.extract_document(plan(secret_proof))

        delivery_proof = document()
        delivery_proof["lanes"][0]["proof"] = ["npm", "run", "deploy"]
        with self.assertRaises(drive.DrivePacketError):
            drive.extract_document(plan(delivery_proof))

        two_blocks = plan(document()) + "\n" + plan(document())
        with self.assertRaises(drive.DrivePacketError):
            drive.extract_document(two_blocks)

    def test_preview_excludes_task_paths_and_proof_commands(self) -> None:
        parsed = drive.extract_document(plan(document()))
        preview = drive.public_preview(parsed)
        assert preview is not None
        rendered = json.dumps(preview, sort_keys=True)
        self.assertIn("Make the welcome message easier", rendered)
        for forbidden in ("allowed_paths", "proof", "src/welcome.ts", "focused test green"):
            self.assertNotIn(forbidden, rendered)

    def test_ready_lanes_are_disjoint_and_never_silently_rerouted(self) -> None:
        parsed = drive.extract_document(plan(document()))
        assert parsed is not None
        candidate = copy.deepcopy(parsed)
        candidate["lanes"][0]["selection"] = {"host": "cursor"}
        candidate["lanes"][1]["selection"] = {"host": "codex"}
        overlapping = copy.deepcopy(candidate["lanes"][1])
        overlapping["id"] = "also-copy"
        overlapping["selection"] = {"host": "claude-code"}
        overlapping["allowed_paths"] = ["src/welcome.ts"]
        same_host = copy.deepcopy(candidate["lanes"][1])
        same_host["id"] = "same-tool"
        same_host["selection"] = {"host": "cursor"}
        candidate["lanes"].extend([overlapping, same_host])

        selected, notices = drive.select_disjoint_ready_lanes(candidate)

        self.assertEqual([lane["id"] for lane in selected], ["improve-copy", "repair-parser"])
        self.assertEqual(
            notices,
            [
                {"id": "also-copy", "reason": "overlaps_another_piece_of_work"},
                {"id": "same-tool", "reason": "shares_a_coding_tool"},
            ],
        )
        self.assertTrue(drive.paths_overlap(["src"], ["src/file.py"]))
        self.assertFalse(drive.paths_overlap(["src/file.py"], ["tests/file.py"]))

    def test_legacy_pilot_puppy_packet_stays_readable(self) -> None:
        payload = document()
        payload["schema"] = "pilot-puppy.drive.v1"
        legacy = plan(payload).replace("shadow-drive.v1", "pilot-puppy-drive.v1")
        parsed = drive.extract_document(legacy)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["schema"], "shadow.drive.v1")

    def test_missing_packet_is_not_an_error(self) -> None:
        self.assertIsNone(drive.extract_document("# Ordinary plan\n"))


if __name__ == "__main__":
    unittest.main()
