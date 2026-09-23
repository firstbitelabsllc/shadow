"""`shadow status --json` exports each open checkpoint's two wakes verbatim.

Cabinet's "Waiting on Leo" section reads this export. It needs the row-level
`| wake:` text and the single Deferred wake side by side, never one chosen
over the other, and an ambiguous Deferred section must read as unknown
(null) rather than failing the whole board.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "shadow-status.py"

LONG_WAKE = "Leo reads the whole draft " + "and signs every page " * 40

ALPHA = f"""# Alpha

## Brief

- Project: alpha
- Mode: ship

## Tasks

### Alpha gates
- [blocked] Private route opens ~aa11 | proof: read route -> opens | wake: Leo authorizes the private route
- [pending] Self-mail send is proven ~bb22 | proof: read mail -> arrives
- [pending] Long wait is bounded ~cc33 | proof: read wait -> bounded | wake: {LONG_WAKE}
- [pending] Nothing waits here ~dd44 | proof: read quiet -> quiet
- [completed] Already shipped ~ee55 | proof: read shipped -> shipped
- [pending] Alpha is done ~ff66 (DoD) | proof: read alpha -> done

## Deferred

- ~aa11 route stays closed | needs an owner answer | wake: owner names the permanent destination
- ~bb22 first send failed | investigate admission | wake: the AM run reaches authoring
- ~bb22 second copy of the same deferral | duplicate | wake: a different predicate
- ~ee55 retired | shipped | wake: never

## Progress

- 2026-09-22T00:00:00Z ~ee55 PROOF read shipped -> shipped
"""

BETA = """# Beta

## Brief

- Project: beta
- Mode: ship

## Tasks

### Beta gate
- [pending] Beta waits on its row wake ~gg77 | proof: read beta -> waits | wake: Leo picks a channel
- [pending] Beta is done ~hh88 (DoD) | proof: read beta -> done
"""


def _load_status():
    spec = importlib.util.spec_from_file_location("shadow_status_wake_test", STATUS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StatusWakeExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / ".test-home"
        self.home.mkdir()
        for name, text in (("alpha", ALPHA), ("beta", BETA)):
            (self.root / name).mkdir()
            (self.root / name / "PLAN.md").write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def status_json(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(STATUS), "--root", str(self.root), "--json"],
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def checkpoints(record: dict) -> dict[str, dict]:
        return {
            checkpoint["id"]: checkpoint
            for milestone in record["milestones"]
            for checkpoint in milestone["checkpoints"]
        }

    def by_project(self, payload: dict) -> dict[str, dict]:
        return {record["project"]: record for record in payload["v4_plans"]}

    def test_every_open_checkpoint_of_every_entity_carries_both_fields(self) -> None:
        records = self.by_project(self.status_json())
        self.assertEqual(set(records), {"alpha", "beta"})
        expected_open = {"alpha": {"~aa11", "~bb22", "~cc33", "~dd44", "~ff66"},
                         "beta": {"~gg77", "~hh88"}}
        for project, record in records.items():
            checkpoints = self.checkpoints(record)
            self.assertEqual(set(checkpoints), expected_open[project])
            for row, checkpoint in checkpoints.items():
                self.assertIn("wake", checkpoint, f"{project} {row}")
                self.assertIn("deferred_wake", checkpoint, f"{project} {row}")

    def test_row_and_deferred_wakes_are_exact_and_never_arbitrated(self) -> None:
        records = self.by_project(self.status_json())
        alpha = self.checkpoints(records["alpha"])
        # Both texts differ and both survive verbatim.
        self.assertEqual(alpha["~aa11"]["wake"], "Leo authorizes the private route")
        self.assertEqual(alpha["~aa11"]["deferred_wake"], "owner names the permanent destination")
        # A row without either wake exports two nulls, not a guess.
        self.assertIsNone(alpha["~dd44"]["wake"])
        self.assertIsNone(alpha["~dd44"]["deferred_wake"])
        self.assertIsNone(alpha["~ff66"]["wake"])
        beta = self.checkpoints(records["beta"])
        self.assertEqual(beta["~gg77"]["wake"], "Leo picks a channel")
        self.assertIsNone(beta["~gg77"]["deferred_wake"])

    def test_ambiguous_deferred_entry_is_null_not_a_failure(self) -> None:
        alpha = self.checkpoints(self.by_project(self.status_json())["alpha"])
        self.assertIsNone(alpha["~bb22"]["deferred_wake"])
        self.assertIsNone(alpha["~bb22"]["wake"])

    def test_long_wake_is_bounded_as_a_marked_prefix(self) -> None:
        alpha = self.checkpoints(self.by_project(self.status_json())["alpha"])
        wake = alpha["~cc33"]["wake"]
        self.assertLess(len(wake), len(LONG_WAKE.strip()))
        self.assertTrue(wake.endswith("…"), wake[-20:])
        self.assertTrue(LONG_WAKE.startswith(wake[:-1]))

    def test_seat_brief_and_full_export_agree(self) -> None:
        full = self.by_project(self.status_json())
        previous = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        try:
            status = _load_status()
            payload = status._board.snapshot()
            assert payload is not None
            for entity in payload["entities"]:
                (brief,) = status.board_records(
                    payload, entity_ids={entity["id"]}, verify_identity=True,
                )
                wakes = {
                    row: (checkpoint["wake"], checkpoint["deferred_wake"])
                    for row, checkpoint in self.checkpoints(brief).items()
                }
                expected = {
                    row: (checkpoint["wake"], checkpoint["deferred_wake"])
                    for row, checkpoint in self.checkpoints(full[entity["project"]]).items()
                }
                self.assertEqual(wakes, expected, entity["project"])
        finally:
            if previous is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = previous


if __name__ == "__main__":
    unittest.main()
