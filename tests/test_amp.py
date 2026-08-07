"""shadow amp — the goal block is a bounded pointer, never a second plan."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("shadow_amp", ROOT / "scripts" / "shadow-amp.py")
amp = importlib.util.module_from_spec(SPEC)
sys.modules["shadow_amp"] = amp
SPEC.loader.exec_module(amp)

PLAN = """# Demo — Plan

## Brief

- Project: demo
- Mode: ship
- Priority: 2

## Tasks

### M1 — shipped already
- [completed] groundwork ~aa11 | proof: cmd true

### M2 — the live milestone
- tools: /craft for UI, /xbq for builds — simulator proof is the bar
- [completed] parser lands ~bb22 | proof: cmd npm test
- [pending] blocked-by-needs row ~cc33 | proof: cmd npm test | needs: ~dd44
- [pending] the ready row ~dd44 | proof: cmd npm run gate
- [pending] owner clicks release ~ee55 | proof: gate owner resume: release visible
- [pending] milestone closes ~ff66 (DoD) | proof: read site -> renders

## Contradictions

- speed vs proof | provisional winner proof | opened 2026-08-07T00:00:00Z

## Progress

- 2026-08-07T00:00:00Z ~aa11 PROOF true -> ok
"""


def _write(tmp: Path, text: str = PLAN) -> Path:
    plan = tmp / "PLAN.md"
    plan.write_text(text, encoding="utf-8")
    return plan


class AmpSelection(unittest.TestCase):
    def test_ready_row_wins_over_needs_gated_row(self) -> None:
        plan = amp._parse(PLAN)
        milestone, row = amp._select(plan, None)
        self.assertEqual(row["id"], "~dd44")  # ~cc33 needs ~dd44, not done
        self.assertEqual(milestone["title"], "M2 — the live milestone")

    def test_in_progress_preferred_over_pending(self) -> None:
        text = PLAN.replace("- [pending] the ready row", "- [in_progress] the ready row")
        milestone, row = amp._select(amp._parse(text), None)
        self.assertEqual(row["id"], "~dd44")
        self.assertEqual(row["state"], "in_progress")

    def test_task_flag_targets_one_row(self) -> None:
        _, row = amp._select(amp._parse(PLAN), "~cc33")
        self.assertEqual(row["id"], "~cc33")

    def test_complete_plan_raises_for_successor_minting(self) -> None:
        done = PLAN.replace("[pending]", "[completed]").replace("[in_progress]", "[completed]")
        with self.assertRaises(LookupError):
            amp.build_block(amp._parse(done), Path("."), Path("PLAN.md"), None, 4000)


class AmpBlock(unittest.TestCase):
    def _block(self, max_chars: int = 4000) -> tuple[str, list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            plan_path = _write(repo)
            return amp.build_block(amp._parse(PLAN), repo, plan_path, None, max_chars)

    def test_block_is_pointer_first_and_bounded(self) -> None:
        block, dropped = self._block()
        self.assertLessEqual(len(block), 4000)
        self.assertEqual(dropped, [])
        self.assertIn("AUTHORITY: PLAN.md", block)
        self.assertIn('section "### M2 — the live milestone"', block)
        self.assertIn("the plan wins", block)
        self.assertIn("RESUME: [pending] the ready row ~dd44", block)
        self.assertIn("PROOF: cmd npm run gate", block)

    def test_tools_line_is_projected(self) -> None:
        block, _ = self._block()
        self.assertIn("TOOLS: /craft for UI, /xbq for builds", block)

    def test_person_gate_and_contradictions_are_named(self) -> None:
        block, _ = self._block()
        self.assertIn("PERSON-GATED (do not take): owner clicks release ~ee55", block)
        self.assertIn("CONTRADICTIONS OPEN: 1", block)

    def test_over_budget_drops_optional_tail_never_the_resume(self) -> None:
        block, dropped = self._block(max_chars=760)
        self.assertLessEqual(len(block), 760)
        self.assertTrue(dropped)
        self.assertIn("RAILS", dropped)
        self.assertIn("RESUME: [pending] the ready row ~dd44", block)
        self.assertIn("AUTHORITY: PLAN.md", block)

    def test_impossible_budget_is_a_hard_error(self) -> None:
        with self.assertRaises(ValueError):
            self._block(max_chars=120)


class AmpCli(unittest.TestCase):
    def test_missing_plan_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(amp.main(["--repo", tmp]), 2)

    def test_bad_task_id_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp))
            self.assertEqual(amp.main(["--repo", tmp, "--task", "nope"]), 2)

    def test_happy_path_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp))
            self.assertEqual(amp.main(["--repo", tmp]), 0)


if __name__ == "__main__":
    unittest.main()
