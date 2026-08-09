"""The Brief contract's enforcing half: an A/B/C must show its work."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "shadow-style-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("shadow_style_guard", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StyleGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(GUARD.is_file(), "the guard must ship under scripts/")
        self.guard = _load()

    def test_options_without_a_drawing_are_blocked(self) -> None:
        text = "- **A** — submit the build\n- **B** — merge the branches\n"
        self.assertTrue(self.guard.violations(text), "bare A/B must not pass")

    def test_same_options_with_a_fenced_block_pass(self) -> None:
        text = "```\nBEFORE -> AFTER\n```\n- **A** — submit\n- **B** — merge\n"
        self.assertFalse(self.guard.violations(text), "a drawing satisfies the contract")

    def test_same_options_with_a_table_pass(self) -> None:
        text = "| x | y |\n|---|---|\n- **A** — submit\n- **B** — merge\n"
        self.assertFalse(self.guard.violations(text), "a table satisfies the contract")

    def test_a_single_option_is_not_a_menu(self) -> None:
        self.assertFalse(self.guard.violations("- **A** — the only move\n"))

    def test_ordinary_prose_is_untouched(self) -> None:
        self.assertFalse(self.guard.violations("Merged the branch and ran the tests."))

    def test_end_to_end_blocks_through_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            transcript.write_text(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "- **A** — one\n- **B** — two\n"}]},
            }) + "\n")
            done = subprocess.run(
                [sys.executable, str(GUARD)],
                input=json.dumps({"transcript_path": str(transcript), "stop_hook_active": False}),
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["decision"], "block")

    def test_stop_hook_active_never_loops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            transcript.write_text(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "- **A** — one\n- **B** — two\n"}]},
            }) + "\n")
            done = subprocess.run(
                [sys.executable, str(GUARD)],
                input=json.dumps({"transcript_path": str(transcript), "stop_hook_active": True}),
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(done.stdout.strip(), "", "a second pass must always allow")

    def test_missing_transcript_is_silent(self) -> None:
        done = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps({"transcript_path": "/nonexistent/x.jsonl"}),
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(done.stdout.strip(), "", "an unreadable transcript must not block work")


if __name__ == "__main__":
    unittest.main()
