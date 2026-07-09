"""Tests for scripts/vidux-public-ready-grep-gate.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-public-ready-grep-gate.py"


class PublicReadyGrepGateTests(unittest.TestCase):
    def test_clean_current_surface_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "config.md").write_text("Plans are files.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["matches"], [])

    def test_forbidden_term_in_current_surface_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Add Linear sync back here.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["file"], "README.md")

    def test_ask_leo_is_in_scope_but_hygiene_exempt(self):
        # Round-3 panel finding: ASK-LEO.md was grouped with true history
        # files (ARCHIVE.md/CHANGELOG.md) and excluded from SCAN_TARGETS
        # entirely, hiding a real private-path leak. It's a LIVE, ongoing
        # queue (per its own header), not a closed record -- it must be
        # scanned. But its resolved Q&A entries are still historical enough
        # that HYGIENE_PATTERNS (e.g. "Linear") shouldn't retroactively fire.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            (root / "ASK-LEO.md").write_text(
                "## Q1\nAnswer: migrated off Linear sync in 2026-04.\n"
                "Private path leak: /Users/leokwan/Development/x\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        files_matched = {m["file"] for m in payload["matches"]}
        self.assertEqual(files_matched, {"ASK-LEO.md"})
        patterns_matched = {m["pattern"] for m in payload["matches"]}
        self.assertEqual(patterns_matched, {"private username"})

    def test_leo_flow_pattern_catches_hyphenated_slash_command_form(self):
        # Round-3 panel finding: the original pattern only matched the
        # spaced "Leo Flow" form and missed "/leo-flow"/"leo-flow", which is
        # the form actually used in prose -- 6 live occurrences in SKILL.md
        # passed the gate green while sitting in a live, current section.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Use `/leo-flow` for lane routing.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "private Leo Flow lane")

    def test_username_pattern_catches_bare_mentions_not_just_home_paths(self):
        # Round-3 panel finding: the old pattern only matched the
        # /Users/leokwan PATH form. A historical evidence file leaked 26
        # bare `com.leokwan.<private-project>` macOS LaunchAgent labels
        # (naming several unrelated private repos), unscanned because none
        # of them is a /Users/ path.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "launchctl print gui/501/com.leokwan.some-private-service\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "private username")

    def test_employer_source_path_pattern_was_a_silent_noop_now_catches_real_leaks(self):
        # Round-3 panel finding: the "employer source path" rule's regex had
        # been over-redacted to the literal placeholder text
        # "REDACTED-EMPLOYER-PATH" -- a string that never appears in real
        # content, so the rule matched nothing, ever. It missed a live leak:
        # this session's own evidence file quoting a real employer corporate
        # dev-tree path and email verbatim while documenting a
        # confidentiality finding about that exact content.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Evidence: /Users/lkwan/Snapchat/Dev/ai/skills\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "employer source path")

    def test_employer_email_and_hostname_patterns_catch_real_leaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Author: jchen3@snapchat.com; registry.snapchat.com and "
                "engflow-cache-gcp-prod.sc-corp.net were referenced.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        patterns_matched = {m["pattern"] for m in payload["matches"]}
        self.assertIn("employer email or domain", patterns_matched)
        self.assertIn("employer internal hostname", patterns_matched)

    def test_historical_plan_dirs_are_out_of_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "projects" / "old-cleanup" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("Historical Linear removal notes stay here.\n", encoding="utf-8")
            (root / "README.md").write_text("Current docs stay clean.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_new_top_level_file_not_named_in_any_allowlist_is_still_scanned(self):
        # Round-4 panel finding: SCAN_TARGETS was a hand-maintained allowlist.
        # AGENTS.md and CHANGELOG.md were both tracked, shipped, and leaked
        # real private strings for weeks because neither was ever added to
        # the list. The fix replaces the allowlist with default-on scanning
        # (everything minus a documented denylist) -- this proves a brand
        # new, never-named file is caught automatically, not just the two
        # specific files the round-4 panel happened to find.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            (root / "NOTES-NOBODY-NAMED-YET.md").write_text(
                "Use `/leo-flow` for lane routing.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["file"], "NOTES-NOBODY-NAMED-YET.md")

    def test_css_and_svg_linear_keyword_is_not_a_false_positive(self):
        # Round-4 panel finding: switching to default-on scanning surfaced 9
        # new HYGIENE_PATTERNS matches, all false positives -- "linear" as a
        # CSS gradient/timing-function keyword has nothing to do with the
        # retired Linear.app board integration the pattern exists to catch.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "style.css").write_text(
                "a { background: linear-gradient(180deg, #fff, #000); "
                "transition: all 1.5s linear infinite; }\n",
                encoding="utf-8",
            )
            (root / "banner.svg").write_text(
                "<style>.x { animation: flow 1.5s linear infinite; }</style>\n",
                encoding="utf-8",
            )
            (root / ".gitignore").write_text(".linear-state.json\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_css_file_still_catches_a_real_privacy_leak(self):
        # The hygiene exemption for CSS/SVG must not become a privacy
        # loophole -- PRIVACY_PATTERNS still apply to every scanned file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "style.css").write_text(
                "/* generated from /vidux-leo/tokens.json */\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "private vidux overlay name")

    def test_changelog_is_privacy_scanned_but_hygiene_exempt(self):
        # Round-4 panel finding: CHANGELOG.md was excluded outright and
        # leaked '/leo-flow' and '/vidux-leo' in cleartext. The fix moves it
        # into HISTORICAL_TARGETS (like PLAN.md/ARCHIVE.md) rather than
        # excluding it: PRIVACY_PATTERNS still apply, HYGIENE_PATTERNS don't
        # (a changelog legitimately mentions retired terms in past tense).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text(
                "## [1.0.0]\n- Migrated off Linear.\n- Kept locally under /vidux-leo.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        matches = payload["matches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["file"], "CHANGELOG.md")
        self.assertEqual(matches[0]["pattern"], "private vidux overlay name")


if __name__ == "__main__":
    unittest.main()
