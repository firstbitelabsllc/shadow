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
:root.theme-dark class block, which never applies without that class.

Round-10 panel findings, three more instances of gaps this file already
had precedent for but hadn't yet closed generally: (1) no test ever
computed a contrast ratio for any DARK-theme pairing -- only light-theme
values were checked against --paper/--paper-2, so a real dark-mode AA
failure (receipts.html's hardcoded button backgrounds going near-
invisible against dark var(--paper) text) shipped undetected; (2) the
round-9 dark-media-fallback test only checked a fixed tuple of token
names (DARK_STATUS_TOKENS), so a new :root.theme-dark property (here,
--shadow-sm/-md/-lg) could still go missing from the fallback block
without any test catching it; (3) --task-in-progress/--task-blocked also
render on --select (not just --paper/--paper-2) whenever the keyboard-
focusable .dashboard-item is hovered/focused, untested by either the
light or the new dark TEXT_TOKENS checks."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STYLE_CSS = ROOT / "browser" / "static" / "style.css"
RECEIPTS_HTML = ROOT / "browser" / "static" / "receipts.html"

# Round-11 panel finding: these background reference colors used to be
# hardcoded here (PAPER="#f8f5ee" etc). A concurrent palette rebrand shipped
# to style.css (:root --paper became #f7f9f8) WITHOUT touching this file, so
# the WCAG regression guard was silently validating a phantom palette that no
# longer matched the shipped surface. The guard now reads --paper/--paper-2/
# --select from the live CSS in setUp (self.paper etc), so it always tracks
# whatever palette actually ships.

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


def _custom_properties(block: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", block)
    }


DARK_STATUS_TOKENS = (
    "error", "error-bg", "error-ink", "warning", "warning-bg", "warning-ink",
)

# Round-10: status labels that render on --select (not just --paper/
# --paper-2) whenever their ancestor .dashboard-item is :hover/:focus-visible.
SELECT_TOKENS = ("task-in-progress", "task-blocked")


class StyleContrastTests(unittest.TestCase):
    def setUp(self):
        self.css = STYLE_CSS.read_text(encoding="utf-8")
        self.root_block = _first_root_block(self.css)
        self.dark_block = _named_block(self.css, ":root.theme-dark {")
        # Read the actual shipped background surfaces from the live CSS rather
        # than hardcoding them, so a palette change can't leave this guard
        # checking a stale target (round-11 finding).
        self.paper = self._token_value("paper")
        self.paper_2 = self._token_value("paper-2")
        self.select_light = self._token_value("select")
        self.dark_paper = self._dark_token_value("paper")
        self.dark_paper_2 = self._dark_token_value("paper-2")
        self.select_dark = self._dark_token_value("select")

    def _token_value(self, token: str) -> str:
        match = re.search(rf"--{re.escape(token)}:\s*(#[0-9a-fA-F]{{6}})", self.root_block)
        self.assertIsNotNone(match, f"--{token} not found in :root block")
        return match.group(1)

    def _dark_token_value(self, token: str) -> str:
        match = re.search(rf"--{re.escape(token)}:\s*(#[0-9a-fA-F]{{6}})", self.dark_block)
        self.assertIsNotNone(match, f"--{token} not found in :root.theme-dark block")
        return match.group(1)

    def test_light_theme_status_text_colors_meet_wcag_aa(self):
        for token in TEXT_TOKENS:
            value = self._token_value(token)
            ratio = _contrast_ratio(value, self.paper)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"--{token} ({value}) vs --paper ({self.paper}) is {ratio:.2f}:1, "
                f"below WCAG 1.4.3 AA (4.5:1) for the small text it's used at",
            )

    def test_light_theme_status_text_colors_meet_wcag_aa_against_paper_2(self):
        for token in TEXT_TOKENS:
            value = self._token_value(token)
            ratio = _contrast_ratio(value, self.paper_2)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"--{token} ({value}) vs --paper-2 ({self.paper_2}) is {ratio:.2f}:1, "
                f"below WCAG 1.4.3 AA (4.5:1) for the small text it's used at",
            )

    def test_dark_theme_status_text_colors_meet_wcag_aa(self):
        # Round-10: the light-theme checks above have no dark-theme
        # counterpart, so a real dark-mode AA failure would sail through
        # green. Mirrors test_light_theme_status_text_colors_meet_wcag_aa
        # against the dark-theme surfaces instead.
        for token in TEXT_TOKENS:
            value = self._dark_token_value(token)
            ratio = _contrast_ratio(value, self.dark_paper)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"--{token} ({value}) vs dark --paper ({self.dark_paper}) is "
                f"{ratio:.2f}:1, below WCAG 1.4.3 AA (4.5:1)",
            )

    def test_dark_theme_status_text_colors_meet_wcag_aa_against_paper_2(self):
        for token in TEXT_TOKENS:
            value = self._dark_token_value(token)
            ratio = _contrast_ratio(value, self.dark_paper_2)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"--{token} ({value}) vs dark --paper-2 ({self.dark_paper_2}) is "
                f"{ratio:.2f}:1, below WCAG 1.4.3 AA (4.5:1)",
            )

    def test_dashboard_status_labels_meet_wcag_aa_against_select(self):
        # Round-10: --task-in-progress/--task-blocked render on --select
        # (not --paper/--paper-2) whenever the keyboard-focusable
        # .dashboard-item ancestor is :hover/:focus-visible -- --select is a
        # harder surface than either in both themes and was never checked.
        for token in SELECT_TOKENS:
            light_value = self._token_value(token)
            light_ratio = _contrast_ratio(light_value, self.select_light)
            self.assertGreaterEqual(
                light_ratio,
                4.5,
                f"--{token} ({light_value}) vs light --select ({self.select_light}) "
                f"is {light_ratio:.2f}:1, below WCAG 1.4.3 AA (4.5:1)",
            )
            dark_value = self._dark_token_value(token)
            dark_ratio = _contrast_ratio(dark_value, self.select_dark)
            self.assertGreaterEqual(
                dark_ratio,
                4.5,
                f"--{token} ({dark_value}) vs dark --select ({self.select_dark}) "
                f"is {dark_ratio:.2f}:1, below WCAG 1.4.3 AA (4.5:1)",
            )

    def test_dark_media_fallback_matches_theme_dark_for_every_custom_property(self):
        # Round-10: generalizes the round-9 fixed-tuple check (below) to
        # every custom property in :root.theme-dark, so a future addition
        # (this round: --shadow-sm/-md/-lg) can't go missing from the bare
        # fallback again without a token-by-token test update.
        media_dark_block = _named_block(
            self.css, "@media (prefers-color-scheme: dark) {"
        )
        theme_props = _custom_properties(self.dark_block)
        media_props = _custom_properties(media_dark_block)
        missing = sorted(set(theme_props) - set(media_props))
        self.assertFalse(
            missing,
            f"properties in :root.theme-dark missing from the bare "
            f"@media(prefers-color-scheme: dark) fallback block: {missing} "
            f"-- it will silently diverge if a browser hits this path with "
            f"localStorage disabled",
        )
        mismatched = {
            name: (theme_props[name], media_props[name])
            for name in theme_props
            if name in media_props and theme_props[name] != media_props[name]
        }
        self.assertFalse(
            mismatched,
            f"properties differ between :root.theme-dark and the bare "
            f"@media dark fallback -- keep them in sync: {mismatched}",
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


class ReceiptsHtmlContrastTests(unittest.TestCase):
    """Round-10 panel finding: receipts.html's inline <style> block hardcodes
    button backgrounds (.local, .local:hover, .primary:hover) while
    inheriting color:var(--paper) from base rules -- --paper flips to
    near-black in dark mode, landing near-black text on a background that
    never lightens (contrast collapsed to 1.49-2.20:1, far below AA). Fixed
    by using a fixed light text color on these fixed-background buttons.
    .ext .prov.local had the mirror problem (fixed text color on a
    background, --paper-2, that DOES flip) -- fixed by switching to the
    already-vetted theme-relative --task-in-review token."""

    def setUp(self):
        self.html = RECEIPTS_HTML.read_text(encoding="utf-8")
        start = self.html.index("<style>")
        end = self.html.index("</style>")
        self.inline_css = self.html[start:end]

    def _rule_declarations(self, selector: str) -> str:
        start = self.inline_css.index(selector)
        brace = self.inline_css.index("{", start)
        end = self.inline_css.index("}", brace)
        return self.inline_css[brace:end]

    def test_fixed_background_buttons_do_not_use_theme_relative_text_color(self):
        # Regression guard for the actual bug: these three rules must not
        # go back to color:var(--paper), which is what silently broke dark
        # mode (the property looked fine -- it's a real theme token -- but
        # the background next to it doesn't invert).
        for selector in ("button.local {", "button.local:hover {", "button.primary:hover {"):
            decl = self._rule_declarations(selector)
            self.assertNotIn(
                "var(--paper)",
                decl,
                f"{selector} uses color:var(--paper) again, but its "
                f"background is a fixed hex that never inverts with theme "
                f"-- this is the exact round-10 dark-mode contrast bug",
            )

    def test_fixed_background_buttons_meet_wcag_aa(self):
        cases = {
            "button.local {": "#1f3b52",
            "button.local:hover {": "#2a5577",
            "button.primary:hover {": "#244e30",
        }
        for selector, bg in cases.items():
            decl = self._rule_declarations(selector)
            match = re.search(r"color:\s*(#[0-9a-fA-F]{6})", decl)
            self.assertIsNotNone(match, f"{selector} has no literal color: value")
            text = match.group(1)
            ratio = _contrast_ratio(text, bg)
            self.assertGreaterEqual(
                ratio,
                4.5,
                f"{selector} text {text} vs background {bg} is {ratio:.2f}:1, "
                f"below WCAG 1.4.3 AA (4.5:1)",
            )

    def test_ext_prov_local_uses_theme_relative_token(self):
        decl = self._rule_declarations(".ext .prov.local {")
        self.assertIn(
            "var(--task-in-review)",
            decl,
            ".ext .prov.local should use the theme-relative --task-in-review "
            "token (already AA-vetted against --paper/--paper-2 in both "
            "themes) rather than a hardcoded hex that doesn't invert with "
            "the --paper-2 background it renders on",
        )


if __name__ == "__main__":
    unittest.main()
