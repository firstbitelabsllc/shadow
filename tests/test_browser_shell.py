"""Source contracts for the dependency-free browser shell.

Ported verbatim from browser/tests/unit/app.test.mjs when npm was removed
(2026-08-09). Those four tests only ever read three static files and asserted
substrings — no DOM, no runtime, no browser — so the entire vitest +
happy-dom + vue dependency tree existed to run these greps. Same assertions,
same files, no fidelity lost.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "browser" / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "browser" / "static" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "browser" / "static" / "style.css").read_text(encoding="utf-8")


class BrowserShellContract(unittest.TestCase):
    def test_one_product_identity_and_one_application_script(self) -> None:
        self.assertIn("<title>Shadow</title>", HTML)
        self.assertIn("Your coding chief of staff", HTML)
        self.assertEqual(len(re.findall(r"<script ", HTML)), 1)

    def test_reads_plans_and_only_sends_explicit_local_choices(self) -> None:
        self.assertIn("fetch('/api/plans')", APP)
        self.assertIn("fetch('/api/decision'", APP)
        self.assertNotIn("/api/drive", APP)
        self.assertIn(
            "{ plan: plan.path, option_id: option.id, revision: plan.outcome.revision }",
            APP,
        )
        self.assertNotIn("localStorage", APP)
        self.assertNotIn("WebSocket", APP)

    def test_names_the_brief_and_choices_in_everyday_language(self) -> None:
        self.assertIn("text: 'Now'", APP)
        self.assertIn("row('Change', briefing.changed)", APP)
        self.assertIn("text: 'Choose what happens next'", APP)
        self.assertIn("text: 'How Shadow can help'", APP)
        self.assertIn("briefing.proof ? 'Proof' : 'Proof not available yet'", APP)
        self.assertNotIn("text: 'planner'", APP)
        self.assertNotIn("text: 'hard-dev'", APP)

    def test_keeps_responsive_and_reduced_motion_behavior(self) -> None:
        self.assertIn("@media (max-width: 760px)", CSS)
        self.assertIn("@media (prefers-reduced-motion: no-preference)", CSS)
        self.assertIn("@media (prefers-color-scheme: dark)", CSS)


class NoNodeDependency(unittest.TestCase):
    """The 2026-08-09 ruling, enforced: Shadow installs and runs on Git, Bash,
    and Python alone. This test is the thing that keeps npm from creeping back."""

    BANNED = ("package.json", "package-lock.json", "vitest.config.mjs",
              "playwright.config.ts", "node_modules")

    def test_no_node_manifest_ships_at_the_root(self) -> None:
        for name in self.BANNED:
            self.assertFalse((ROOT / name).exists(), f"{name} is back — npm was ruled out 2026-08-09")

    def test_no_tracked_file_invokes_npm_or_npx(self) -> None:
        import subprocess

        # Invocations, not the word: the ruling itself is written down in these
        # files ("no npm since 2026-08-09"), and a gate that fires on prose
        # would make recording the decision impossible.
        out = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "-lE",
             r"\b(npm|npx) +(run|install|ci|test|exec|pack|publish|start|build|i|x)\b", "--",
             "bin/", "scripts/", ".github/"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(out.stdout.strip(), "", f"npm/npx invoked in: {out.stdout}")


if __name__ == "__main__":
    unittest.main()
