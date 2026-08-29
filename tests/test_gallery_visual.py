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
why) whether the package is missing or its Chromium binary was never
downloaded.  With ``SHADOW_VISUAL=1`` — CI sets it — either absence is a
FAILURE, never a skip: the environment promised visual proof and could not
deliver it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
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

# Every state the stylesheet promises its own chip treatment for.  Each of
# these rules must FIRE — the suite proves that against an unstyled baseline,
# so deleting any one of them (or dropping one state from a shared selector)
# turns this job red.  Kept in step with the ``.state-*`` rules in
# browser/static/style.css.
STYLED_STATES = ("needs_you", "blocked", "ready", "working", "resting")


def fixture_states() -> set[str]:
    """The states the checked-in gallery fixtures promise to render."""
    fixtures = json.loads(
        (ROOT / "browser" / "static" / "gallery-fixtures.json").read_text()
    )
    return {entry["expected_state"] for entry in fixtures.values()}


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

    @staticmethod
    def _launch(pw):
        """Launch Chromium, honouring the same skip contract as the import.

        A partial install — playwright the package present, its browser binary
        never downloaded — must behave exactly like a missing package: a
        VISIBLE skip normally, a FAILURE under ``SHADOW_VISUAL=1``, never a
        confusing launch traceback standing in for either.
        """
        try:
            return pw.chromium.launch()
        except Exception as error:  # playwright.sync_api.Error and friends
            if VISUAL_REQUIRED:
                raise AssertionError(
                    "SHADOW_VISUAL=1 promises visual proof but chromium would "
                    f"not launch ({error}) — run `playwright install chromium` "
                    "or unset the promise. A silent skip here is the defect "
                    "class this suite exists to prevent."
                ) from error
            raise unittest.SkipTest(
                f"visual proof skipped: chromium would not launch ({error}) "
                "(set SHADOW_VISUAL=1 to make this a failure)"
            ) from error

    def test_the_gallery_renders_styled_differentiated_and_clean(self) -> None:
        with sync_playwright() as pw:
            browser = self._launch(pw)
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
            # EVERY promised state is probed, including the ones sharing a
            # selector and the ones no fixture renders, so dropping `.state-ready`
            # from its shared rule or deleting `.state-resting`'s opacity is red.
            styles = page.evaluate(
                """(states) => {
                    const signature = (el) => {
                      const s = getComputedStyle(el);
                      return [s.backgroundColor, s.color, s.opacity].join(' | ');
                    };
                    const probe = (className) => {
                      const card = document.createElement('article');
                      card.className = className;
                      const chip = document.createElement('span');
                      chip.className = 'status';
                      card.append(chip);
                      document.body.append(card);
                      const sig = signature(chip);
                      card.remove();
                      return sig;
                    };
                    const probed = {}, rendered = {};
                    for (const state of states) {
                      probed[state] = probe(`card state-${state}`);
                      const el = document.querySelector(`.card.state-${state} .status`);
                      rendered[state] = el ? signature(el) : null;
                    }
                    return { baseline: probe('card'), probed, rendered };
                }""",
                list(STYLED_STATES),
            )
            baseline = styles["baseline"]
            for state in STYLED_STATES:
                self.assertNotEqual(
                    styles["probed"][state], baseline,
                    f"the {state} state rule has no visual effect — "
                    "its style is broken or deleted",
                )

            # …and the fixtures the gallery promises actually wear those rules,
            # so the page cannot drift away from the classes just proven.
            for state in sorted(fixture_states() & set(STYLED_STATES)):
                self.assertIsNotNone(
                    styles["rendered"][state], f"no {state}-state card rendered"
                )
                self.assertEqual(
                    styles["rendered"][state], styles["probed"][state],
                    f"the rendered {state} chip does not carry its state style",
                )

            self.assertNotEqual(
                styles["probed"]["working"], styles["probed"]["blocked"],
                "working and blocked chips are visually identical",
            )

            self.assertEqual(console_errors, [], f"console errors: {console_errors}")

            shots = Path(os.environ.get("SHADOW_VISUAL_DIR", tempfile.gettempdir()))
            shots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shots / "gallery.png"), full_page=True)
            browser.close()

    def test_production_views_render_every_milestone_with_human_text(self) -> None:
        """The rotation contract, proven in the DOM instead of pinned in source.

        A plan carrying a real ``milestones`` array must have EVERY milestone
        iterated by the brief card, the plan page, and the board — never the
        ``board.milestone`` single fallback — and checkpoint rows must render
        their human text, never their ``~hash`` id.
        """
        plan = {
            "id": "rotation-proof",
            "title": "Rotation proof plan",
            "mode": "ship",
            "milestones": [
                {
                    "title": "M1 — First rotation shipped",
                    "current": False,
                    "counts": {"pending": 0, "in_progress": 0, "blocked": 0, "completed": 1},
                    "checkpoints": [
                        {
                            "id": "~zz11",
                            "text": "the first human checkpoint renders",
                            "state": "completed",
                            "availability": "completed",
                        },
                    ],
                },
                {
                    "title": "M2 — Second rotation current",
                    "current": True,
                    "counts": {"pending": 1, "in_progress": 0, "blocked": 0, "completed": 1},
                    "checkpoints": [
                        {
                            "id": "~zz22",
                            "text": "the second human checkpoint renders",
                            "state": "pending",
                            "availability": "waiting",
                        },
                    ],
                },
            ],
            "board": {
                "state": "working",
                "milestone": {"title": "FALLBACK-TITLE-MUST-NOT-RENDER"},
            },
            "outcome": {
                "outcome": {
                    "summary": "prove every milestone renders",
                    "current_move": "keep both milestones visible",
                },
            },
            "briefing": {"state": "working", "choices": []},
        }
        with sync_playwright() as pw:
            browser = self._launch(pw)
            page = browser.new_page()
            page.goto(f"{self.base}/gallery")
            page.wait_for_selector(".gallery-cell", timeout=10_000)
            views = page.evaluate(
                """(plan) => {
                    const out = {};
                    const probe = (root) => ({
                        text: root.innerText,
                        rotations: root.querySelectorAll('.milestone-rotation').length,
                    });
                    state.plans = [plan];
                    renderBoardBriefCard(plan);
                    out.brief = probe(main);
                    main.replaceChildren();
                    renderPlan(plan);
                    out.plan = probe(main);
                    renderBoard();
                    out.board = probe(board);
                    state.plans = [];
                    main.replaceChildren();
                    board.replaceChildren();
                    return out;
                }""",
                plan,
            )
            browser.close()
        for view, rendered in views.items():
            with self.subTest(view=view):
                self.assertEqual(
                    rendered["rotations"],
                    2,
                    f"{view} did not iterate the full milestone rotation",
                )
                self.assertIn("M1 — First rotation shipped", rendered["text"])
                self.assertIn("M2 — Second rotation current", rendered["text"])
                self.assertIn("the first human checkpoint renders", rendered["text"])
                self.assertIn("the second human checkpoint renders", rendered["text"])
                self.assertNotIn("FALLBACK-TITLE-MUST-NOT-RENDER", rendered["text"])
                self.assertIsNone(
                    re.search(r"~[0-9a-z]{4}\b", rendered["text"]),
                    f"{view} leaked a row id",
                )


if __name__ == "__main__":
    unittest.main()
