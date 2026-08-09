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


class WiringTests(unittest.TestCase):
    """The documented install is a skills-directory mount, not a project checkout.

    `install.sh` symlinks the clone into `~/.claude/skills/shadow`, putting a
    directory holding `.claude-plugin/plugin.json` under a skills directory, so
    Claude Code loads
    it as the plugin `shadow@skills-dir`. That load reads `hooks/hooks.json` and
    defines `${CLAUDE_PLUGIN_ROOT}`; it never reads this repo's
    `.claude/settings.json`, which applies only to whatever project is active.
    """

    def test_the_stop_hook_ships_where_a_plugin_load_reads_it(self) -> None:
        self.assertTrue((ROOT / ".claude-plugin" / "plugin.json").is_file(),
                        "the manifest is what makes the skills-dir mount a plugin")
        wiring = ROOT / "hooks" / "hooks.json"
        self.assertTrue(wiring.is_file(), "plugin hooks live in hooks/hooks.json")
        entries = json.loads(wiring.read_text(encoding="utf-8"))["hooks"]["Stop"]
        commands = [
            hook["command"]
            for entry in entries
            for hook in entry["hooks"]
            if hook.get("type") == "command"
        ]
        self.assertTrue(
            any("shadow-style-guard.py" in command for command in commands),
            "an installed user must actually execute the guard",
        )
        self.assertTrue(
            all("${CLAUDE_PLUGIN_ROOT}" in command for command in commands),
            "the plugin root is the only path that survives a symlinked mount",
        )

    def test_project_settings_do_not_claim_a_plugin_root(self) -> None:
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", json.dumps(settings),
                         "project settings are not a plugin; that variable is undefined there")

    def test_the_artifact_carries_the_hook_and_the_guard(self) -> None:
        """No package.json since 2026-08-09: the release artifact is a git
        archive, so what ships is what the release gate requires of it."""
        spec = importlib.util.spec_from_file_location(
            "shadow_release_package", ROOT / "scripts" / "shadow-release-package.py"
        )
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        self.assertIn("hooks/hooks.json", release.REQUIRED_FILES,
                      "an unshipped hook enforces nothing")
        self.assertIn("scripts/shadow-style-guard.py", release.REQUIRED_FILES,
                      "an unshipped guard enforces nothing")


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

    def test_an_inline_pipe_is_not_a_table(self) -> None:
        text = "- **A** — submit\n- **B** — merge\n\nUse `cat x | sort` if needed.\n"
        self.assertTrue(self.guard.violations(text), "a shell pipe shows the reader nothing")

    def test_a_borderless_table_still_passes(self) -> None:
        text = "x | y\n--- | ---\n1 | 2\n\n- **A** — submit\n- **B** — merge\n"
        self.assertFalse(self.guard.violations(text), "outer pipes are optional in Markdown")

    def test_options_weighed_mid_report_are_not_a_menu(self) -> None:
        text = (
            "Two ways to land this:\n\n"
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n\n"
            "I took A. The rebase is pushed, the branch is green, and the merge\n"
            "commit B would have added is gone. Nothing is waiting on you.\n"
        )
        self.assertFalse(self.guard.violations(text),
                         "a report that already chose is not handing over a menu")

    def test_a_conclusion_running_straight_on_is_still_a_conclusion(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n"
            "I took A. The rebase is pushed and the branch is green.\n"
            "Nothing is waiting on you.\n"
        )
        self.assertFalse(self.guard.violations(text),
                         "a blank line is not what makes prose the ending; the margin is")

    def test_a_menu_still_asking_is_still_a_menu(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n"
            "B keeps every hash.\n"
            "Which one?\n"
        )
        self.assertTrue(self.guard.violations(text),
                        "a message still asking has not moved on, however it lays the tail out")

    def test_a_report_that_signs_off_with_a_question_has_moved_on(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n"
            "I took A. The rebase is pushed and the branch is green.\n"
            "Reviewers keep their place, and nothing downstream needs a reset.\n"
            "The merge commit B would have added is gone.\n"
            "Anything else you want covered?\n"
        )
        self.assertFalse(self.guard.violations(text),
                         "a closing courtesy is not the message re-offering the menu")

    def test_a_short_sign_off_is_read_the_same_as_a_long_one(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n"
            "I took A; the branch is green.\n"
            "Anything else?\n"
        )
        self.assertFalse(self.guard.violations(text),
                         "the same sign-off must not flip on how many lines precede it")

    def test_offering_a_next_step_is_not_re_offering_the_menu(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n"
            "I took A. The rebase is pushed and the branch is green.\n"
            "Reviewers keep their place, and nothing downstream needs a reset.\n"
            "The merge commit B would have added is gone.\n"
            "Want me to open the follow-up PR?\n"
        )
        self.assertFalse(self.guard.violations(text),
                         "offering one new thing is not sending the reader back to A or B")

    def test_a_long_report_that_reopens_the_menu_is_a_menu(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "- **B** — merge main in\n"
            "Both are ready to run and neither is started.\n"
            "A costs a force-push; B costs a merge commit.\n"
            "Nothing else is blocking either one.\n"
            "Which do you prefer?\n"
        )
        self.assertTrue(self.guard.violations(text),
                        "an open menu stays open however long the tail is")

    def test_a_bare_menu_is_a_menu_whatever_its_one_closing_line_says(self) -> None:
        """The one-line tail is the base case, not an exemption to be argued with.

        `Want me to open the follow-up PR?` passes on a resolved report because
        the report said it chose, not because of the question. Here nothing said
        that, so requiring the closing line to name a choice would let the exact
        shape this guard exists to catch walk straight through.
        """
        for closer in ("Want me to open the follow-up PR?", "Thoughts?", "Let me know."):
            with self.subTest(closer=closer):
                text = f"- **A** — rebase\n- **B** — merge\n{closer}\n"
                self.assertTrue(self.guard.violations(text),
                                "nothing here told the reader which one happened")

    def test_a_menu_with_one_closing_question_is_still_a_menu(self) -> None:
        text = "- **A** — rebase\n- **B** — merge\n\nWhich one?\n"
        self.assertTrue(self.guard.violations(text), "the message still ends on the menu")

    def test_a_wrapped_option_stays_in_the_menu(self) -> None:
        text = "- **A** — rebase onto main,\n  which rewrites the branch\n- **B** — merge\n"
        self.assertTrue(self.guard.violations(text), "a wrapped line must not split the menu")

    def test_explained_options_stay_one_menu(self) -> None:
        text = (
            "- **A** — rebase onto main\n"
            "  It rewrites the branch, so every reviewer loses their place.\n"
            "  CI reruns from scratch, and anyone who pulled needs to reset.\n"
            "  Roughly twenty minutes.\n\n"
            "- **B** — merge main in\n"
            "  Keeps every hash, costs a merge commit.\n\n"
            "Which one?\n"
        )
        self.assertTrue(self.guard.violations(text),
                        "prose between options argues for a drawing, not against one")

    def test_a_single_option_is_not_a_menu(self) -> None:
        self.assertFalse(self.guard.violations("- **A** — the only move\n"))

    def test_a_third_letter_does_not_inherit_the_single_option_pass(self) -> None:
        """The pass is for a message with one option, not for the third letter.

        A message that printed A and B and then offers C has shown the reader
        three letters and no drawing. The only scoping that would free it, count
        just the trailing run of options, also frees a bare A/B whose halves are
        simply written far apart, which is the plainest miss there is.
        """
        settled_then_one_more = (
            "- **A** — rebase\n"
            "- **B** — merge\n"
            "I took A. Pushed and green.\n"
            "Reviewers keep their place.\n\n"
            "One thing left:\n\n"
            "- **C** — deploy now\n"
        )
        halves_written_far_apart = (
            "- **A** — rebase\n"
            "Rewrites the branch, so reviewers lose their place.\n"
            "- **B** — merge\n"
            "Keeps every hash.\n"
        )
        self.assertTrue(self.guard.violations(settled_then_one_more),
                        "three letters and no drawing is the shape this guard is for")
        self.assertTrue(self.guard.violations(halves_written_far_apart),
                        "the miss any trailing-run scope would let through")

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

    def test_payload_message_wins_over_a_stale_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            transcript.write_text(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "an older, clean ending"}]},
            }) + "\n")
            done = subprocess.run(
                [sys.executable, str(GUARD)],
                input=json.dumps({
                    "transcript_path": str(transcript),
                    "last_assistant_message": "- **A** — one\n- **B** — two\n",
                }),
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(json.loads(done.stdout)["decision"], "block",
                         "the turn's own message must be judged, not a lagging transcript")

    def test_blank_payload_message_falls_back_to_the_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            transcript.write_text(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "- **A** — one\n- **B** — two\n"}]},
            }) + "\n")
            done = subprocess.run(
                [sys.executable, str(GUARD)],
                input=json.dumps({
                    "transcript_path": str(transcript),
                    "last_assistant_message": "   ",
                }),
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(json.loads(done.stdout)["decision"], "block",
                         "an empty message field must not disable the guard")

    def test_payload_message_alone_is_enough(self) -> None:
        done = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps({"last_assistant_message": "- **A** — one\n- **B** — two\n"}),
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(json.loads(done.stdout)["decision"], "block",
                         "no transcript is needed when the payload carries the message")

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
