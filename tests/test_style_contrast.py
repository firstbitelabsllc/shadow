"""Round-4 panel finding: several light-theme status colors used as small
text (10.5-11.5px) fail WCAG 1.4.3 AA (4.5:1) against --paper. Pins the
fixed values so a future edit can't silently regress them back below AA."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STYLE_CSS = ROOT / "browser" / "static" / "style.css"

PAPER = "#f8f5ee"

# Tokens confirmed used as `color:` (not just background/border) on small
# text in browser/static/style.css, at the time of this fix.
TEXT_TOKENS = ("task-shipped", "task-in-progress", "task-completed", "task-in-review")


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


if __name__ == "__main__":
    unittest.main()
