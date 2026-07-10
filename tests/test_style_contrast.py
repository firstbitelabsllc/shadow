"""Round-4 panel finding: several light-theme status colors used as small
text (10.5-11.5px) fail WCAG 1.4.3 AA (4.5:1) against --paper. Pins the
fixed values so a future edit can't silently regress them back below AA.

Round-7 panel finding: the round-4 fix only checked --paper. The same
status-label tokens also render on --paper-2 (a slightly darker surface
used for cards/panels), where they still failed (4.23-4.26:1).

Round-9 panel finding: --cold failed AA as receipts.html's ".exportable"
pill text color (3.91:1/4.23:1) -- missed because that usage lives in
receipts.html's own inline <style>, invisible to this test's :root-block
parsing. --error and --hot pass today but sit at the same razor-thin
4.5-5.0:1 margin that took three rounds to close for the other tokens,
untested despite identical small-text usage in receipts.html -- added
per round-8's own precedent for --task-blocked ("already passed... but
was untested despite identical usage").

Round-9 panel also found the bare `@media (prefers-color-scheme: dark)`
fallback block (index.html's own FOUC-guard falls through to it when
localStorage throws) omitted --error/--warning entirely, contradicting
a comment that falsely claimed they were "already handled" by the
:root.theme-dark class block, which never applies without that class."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STYLE_CSS = ROOT / "browser" / "static" / "style.css"

PAPER = "#f8f5ee"
PAPER_2 = "#f1ece1"

# Tokens confirmed used as `color:` (not just background/border) on small
# text in browser/static/style.css, at the time of this fix.
# Round-8 panel finding: added "warning" (failed AA at 11px on
# .ops-chip.is-warn, 3.91:1/3.61:1 -- darkened same as the original 4) and
# "task-blocked" (already passing, 4.97:1/4.59:1, just missing from this
# regression test despite being used identically to the other 5).
TEXT_TOKENS = (
    "task-shipped", "task-in-progress", "task-completed", "task-in-review",
    "warning", "task-blocked", "cold", "error", "hot",
)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _linearize(c: int) -> float:
    c_srgb = c / 255
    return c_srgb / 12.92 if c_srgb <= 0.03928 else ((c_srgb + 0.055) / 1.055) ** 2.4


def _relative_luminance(hexcolor: str) -> float:
    r, g, b = _hex_to_rgb(hexcolor)
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    l1, l2 = _relative_luminance(hex1), _relative_luminance(hex2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _first_root_block(css: str) -> str:
    # The light-theme token values live in the first `:root { ... }` block.
    start = css.index(":root {")
    end = css.index("}", start)
    return css[start:end]


def _named_block(css: str, marker: str) -> str:
    start = css.index(marker)
    brace = css.index("{", start)
    end = css.index("}", brace)
    return css[brace:end]


DARK_STATUS_TOKENS = (
    "error", "error-bg", "error-ink", "warning", "warning-bg", "warning-ink",
)


class StyleContrastTests(unittest.TestCase):
    def setUp(self):
        self.css = STYLE_CSS.read_text(encoding="utf-8")
        self.root_block = _first_root_block(self.css)

    def _token_value(self, token: str) -> str:
        match = re.search(rf"--{re.escape(token)}:\s*(#[0-9a-fA-F]{{6}})", self.root_block)
        self.assertIsNotNone(match, f"--{token} not found in :root block")
        return match.group(1)

    def test_light_theme_status_text_colors_meet_wcag_aa(self):
        for token in TEXT_TOKENS:
            value = self._token_value(token)
            ratio = _contrast_ratio(value, PAPER)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"--{token} ({value}) vs --paper ({PAPER}) is {ratio:.2f}:1, "
                f"below WCAG 1.4.3 AA (4.5:1) for the small text it's used at",
            )

    def test_light_theme_status_text_colors_meet_wcag_aa_against_paper_2(self):
        for token in TEXT_TOKENS:
            value = self._token_value(token)
            ratio = _contrast_ratio(value, PAPER_2)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"--{token} ({value}) vs --paper-2 ({PAPER_2}) is {ratio:.2f}:1, "
                f"below WCAG 1.4.3 AA (4.5:1) for the small text it's used at",
            )

    def test_dark_media_fallback_declares_error_and_warning_families(self):
        # Round-9: the bare @media(prefers-color-scheme: dark) block is a
        # real, reachable fallback path (FOUC-guard falls through to it when
        # localStorage throws), so it must carry the same --error/--warning
        # values as :root.theme-dark rather than silently omitting them.
        theme_dark_block = _named_block(self.css, ":root.theme-dark {")
        media_dark_block = _named_block(
            self.css, "@media (prefers-color-scheme: dark) {"
        )
        for token in DARK_STATUS_TOKENS:
            pattern = rf"--{re.escape(token)}:\s*(#[0-9a-fA-F]{{6}})"
            theme_match = re.search(pattern, theme_dark_block)
            media_match = re.search(pattern, media_dark_block)
            self.assertIsNotNone(
                theme_match, f"--{token} not found in :root.theme-dark block"
            )
            self.assertIsNotNone(
                media_match,
                f"--{token} not found in the @media(prefers-color-scheme: "
                f"dark) fallback block -- it will silently fail WCAG AA if "
                f"a browser hits this path with localStorage disabled",
            )
            self.assertEqual(
                theme_match.group(1),
                media_match.group(1),
                f"--{token} differs between :root.theme-dark and the bare "
                f"@media dark fallback -- keep them in sync",
            )


if __name__ == "__main__":
    unittest.main()
