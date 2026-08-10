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
        self.assertIn("entity: plan.entity", APP)
        self.assertIn("root_board_revision: state.boardRevision", APP)
        self.assertIn("id=\"board-warning\"", HTML)
        self.assertIn("boardWarning.hidden = !state.warning", APP)
        self.assertNotIn("localStorage", APP)
        self.assertNotIn("WebSocket", APP)

    def test_names_the_brief_and_choices_in_everyday_language(self) -> None:
        self.assertIn("text: 'Now'", APP)
        self.assertIn("row('Change', briefing.changed)", APP)
        self.assertIn("text: 'Choose what happens next'", APP)
        self.assertIn("text: 'How Shadow can help'", APP)
        self.assertIn("'Drive the full outcome'", APP)
        self.assertIn("'Fan out safe work'", APP)
        self.assertIn("full acceptance stops the outcome", APP)
        self.assertIn("only exact hard rails pause it earlier", APP)
        self.assertIn("briefing.proof ? 'Proof' : 'Proof not available yet'", APP)
        # PROVEN FALSE GREEN (2026-08-09): this guard was written as
        # `assertNotIn("text: 'planner'", APP)`, but app.js never writes a role
        # as a literal `text:` value — the labels come from an array via
        # `el('dt', { text: work })`. Putting the deleted roster back into the
        # shipped UI passed 224 tests. The guard was shaped to a code style
        # that no longer existed. Match the array literal instead.
        for role in ("'planner'", "'dev'", "'debug'", "'review'", "'hard-dev'", "'lead'"):
            self.assertNotIn(role, APP, f"the deleted roster is back in the shipped UI: {role}")

    def test_keeps_responsive_and_reduced_motion_behavior(self) -> None:
        self.assertIn("@media (max-width: 760px)", CSS)
        self.assertIn("@media (prefers-reduced-motion: no-preference)", CSS)
        self.assertIn("@media (prefers-color-scheme: dark)", CSS)


# npm/npx in COMMAND position. Leading indentation counts as line start so an
# indented `npm ci` inside a YAML `run: |` block is caught; prose keeps npm
# mid-sentence, where this never fires.
INVOCATION = re.compile(r"(?:^\s*|[;&|`]\s*|\$\(\s*|\brun:\s*|\bexec\s+)(npm|npx)\b")


class NoNodeDependency(unittest.TestCase):
    """The 2026-08-09 ruling, enforced: Shadow installs and runs on Git, Bash,
    and Python alone. This test is the thing that keeps npm from creeping back."""

    BANNED = ("package.json", "package-lock.json", "vitest.config.mjs",
              "playwright.config.ts", "node_modules")

    def test_no_node_manifest_ships_at_the_root(self) -> None:
        for name in self.BANNED:
            self.assertFalse((ROOT / name).exists(), f"{name} is back — npm was ruled out 2026-08-09")

    def test_no_tracked_file_invokes_npm_or_npx(self) -> None:
        # This test previously used `git grep -E '\\b(npm|npx) '` and was a FALSE
        # GREEN: git grep's ERE has no \\b, so it matched nothing and could never
        # fail — the guard against npm was itself unguarded. It now strips
        # comments and looks for npm/npx in COMMAND position, so prose like
        # "No npm since 2026-08-09" is fine and `run: npm ci` is not.
        import subprocess

        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--", "bin/", "scripts/", ".github/"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        invocation = INVOCATION
        offenders = []
        for name in tracked:
            path = ROOT / name
            if path.suffix in {".md"} or not path.is_file():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]          # shell / python / yaml comment
                if invocation.search(code):
                    offenders.append(f"{name}:{number}: {line.strip()[:80]}")
        self.assertEqual(offenders, [], "npm/npx invoked in tracked tooling: " + "; ".join(offenders))

    def test_the_ban_test_can_actually_fail(self) -> None:
        # Mutation guard for the guard: the detector must fire on a real
        # invocation and stay quiet on prose. Without this, the false-green
        # regression above returns silently.
        invocation = INVOCATION
        for fires in ("npm ci", "  run: npm test", "foo && npx playwright install",
                      "exec npm start", "VER=$(npm pkg get version)",
                      "        npm ci", "\t\tnpx playwright install"):
            self.assertTrue(invocation.search(fires.split("#", 1)[0]), fires)
        for quiet in ("# No npm since 2026-08-09", "the npm allowlist is gone",
                      "  # tests fail if npm/npx appears",
                      '"""Public-readiness identity (npm removed):'):
            self.assertFalse(invocation.search(quiet.split("#", 1)[0]), quiet)
