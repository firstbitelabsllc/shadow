"""Visual proof for the gallery: real browser, real styles, loud on skip.

The fixture catalog (``/gallery``) is only proof if something LOOKS at it.
This file opens it in a headless browser and asserts the properties that the
DOM-level goldens cannot see — the ones every gallery review finding to date
has lived in: styles actually applied (a CSP once silently discarded them),
state chips actually differentiated (a lint red once dressed normal cards as
errors), and a clean console.  A full-page screenshot is written for CI to
keep as an artifact, so a human can re-observe any run.

The skip contract, per the register's silent-skip law: without
``SHADOW_VISUAL=1`` these tests skip VISIBLY (the runner prints the skip and
why).  With ``SHADOW_VISUAL=1`` — CI sets it — a missing browser is a
FAILURE, never a skip: the environment promised visual proof and could not
deliver it.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from browser import server  # noqa: E402

VISUAL_REQUIRED = os.environ.get("SHADOW_VISUAL") == "1"

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ModuleNotFoundError:
    HAVE_PLAYWRIGHT = False


class TheGalleryLooksRight(unittest.TestCase):
    """Computed-style and console assertions against the live gallery page."""

    @classmethod
    def setUpClass(cls) -> None:
        if not HAVE_PLAYWRIGHT:
            if VISUAL_REQUIRED:
                raise AssertionError(
                    "SHADOW_VISUAL=1 promises visual proof but playwright is not "
                    "installed — install it (pip install playwright; playwright "
                    "install chromium) or unset the promise. A silent skip here "
                    "is the defect class this suite exists to prevent."
                )
            raise unittest.SkipTest(
                "visual proof skipped: playwright not installed "
                "(set SHADOW_VISUAL=1 to make this a failure)"
            )
        cls._tmp = tempfile.TemporaryDirectory()
        cls.service = server.Server(("127.0.0.1", 0), Path(cls._tmp.name))
        cls.service.RequestHandlerClass.log_message = lambda *a: None
        cls.thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.service.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        if HAVE_PLAYWRIGHT:
            cls.service.shutdown()
            cls._tmp.cleanup()

    def test_the_gallery_renders_styled_differentiated_and_clean(self) -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            console_errors: list[str] = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            page.goto(f"{self.base}/gallery")
            page.wait_for_selector(".gallery-cell", timeout=10_000)

            # Styles are APPLIED, not just served — the CSP finding's class.
            grid = page.eval_on_selector(
                ".gallery", "el => getComputedStyle(el).display"
            )
            self.assertEqual(grid, "grid", "the gallery stylesheet is not applied")
            border = page.eval_on_selector(
                ".gallery-cell .stage", "el => getComputedStyle(el).borderTopStyle"
            )
            self.assertEqual(border, "dashed", "stage framing is not applied")

            # Every fixture rendered a brief card AND a board card.
            cells = page.eval_on_selector_all(".gallery-cell", "els => els.length")
            self.assertGreaterEqual(cells, 6)
            empty_stages = page.eval_on_selector_all(
                ".gallery-cell .stage",
                "els => els.filter(el => el.childElementCount === 0).length",
            )
            self.assertEqual(empty_stages, 0, "a fixture rendered an empty stage")

            # State chips are DIFFERENTIATED — the red-treatment finding's
            # class: a working chip and a blocked chip must not share a
            # background, and breaking a state style collapses them together.
            # Each state's rule must FIRE, not merely differ from a sibling
            # that happens to have its own rule: every stateful chip is
            # compared against an unstyled baseline chip injected into a
            # stateless card. (First version compared working to blocked only,
            # and deleting the working rule survived — the vacuous-guard trap.)
            backgrounds = page.evaluate(
                """() => {
                    const probe = document.createElement('article');
                    probe.className = 'card';
                    const chip = document.createElement('span');
                    chip.className = 'status';
                    probe.append(chip);
                    document.body.append(probe);
                    const baseline = getComputedStyle(chip).backgroundColor;
                    probe.remove();
                    const of = (sel) => {
                      const el = document.querySelector(sel);
                      return el ? getComputedStyle(el).backgroundColor : null;
                    };
                    return {
                      baseline,
                      working: of('.card.state-working .status'),
                      blocked: of('.card.state-blocked .status'),
                    };
                }"""
            )
            self.assertIsNotNone(backgrounds["working"], "no working-state card rendered")
            self.assertIsNotNone(backgrounds["blocked"], "no blocked-state card rendered")
            for name in ("working", "blocked"):
                self.assertNotEqual(
                    backgrounds[name], backgrounds["baseline"],
                    f"the {name} state rule has no visual effect — its style is broken or deleted",
                )
            self.assertNotEqual(
                backgrounds["working"], backgrounds["blocked"],
                "working and blocked chips are visually identical",
            )

            self.assertEqual(console_errors, [], f"console errors: {console_errors}")

            shots = Path(os.environ.get("SHADOW_VISUAL_DIR", tempfile.gettempdir()))
            shots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shots / "gallery.png"), full_page=True)
            browser.close()


if __name__ == "__main__":
    unittest.main()
