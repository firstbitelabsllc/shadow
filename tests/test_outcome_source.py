"""Tests for the single plan-derived Outcome source and its desk projections."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from browser import server as browser_server
from browser.outcome_source import OutcomeSourceError, project_plan_outcome


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "vidux-outcome-validate.py"


def canonical_brief() -> dict[str, str]:
    return {
        "outcome_id": "checkout-notes",
        "outcome_revision": "7",
        "outcome_updated_at": "2026-08-02T04:45:22Z",
        "outcome_state": "working",
        "outcome": "Ship accurate notes for the next tagged build.",
        "next": "Draft the outline from the owning plan.",
    }


class OutcomeSourceTests(unittest.TestCase):
    def validate(self, document: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "outcome.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(VALIDATOR), "--input", str(path)],
                cwd=ROOT,
                env={**os.environ, "HOME": str(Path(dirname) / "home")},
                capture_output=True,
                text=True,
                check=False,
            )

    def test_projection_is_closed_and_passes_canonical_validator(self) -> None:
        document = project_plan_outcome(canonical_brief())
        self.assertEqual(
            document,
            {
                "schema": "vidux.outcome.v1",
                "revision": 7,
                "updated_at": "2026-08-02T04:45:22Z",
                "outcome": {
                    "id": "checkout-notes",
                    "summary": "Ship accurate notes for the next tagged build.",
                    "state": "working",
                    "current_move": "Draft the outline from the owning plan.",
                },
                "ask": None,
                "steers": [],
                "proof": [],
            },
        )
        result = self.validate(document)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_missing_explicit_revision_is_not_a_typed_outcome(self) -> None:
        brief = canonical_brief()
        del brief["outcome_revision"]
        with self.assertRaisesRegex(OutcomeSourceError, "outcome_revision"):
            project_plan_outcome(brief)

    def test_invalid_state_is_not_a_typed_outcome(self) -> None:
        brief = canonical_brief()
        brief["outcome_state"] = "shipping"
        with self.assertRaisesRegex(OutcomeSourceError, "outcome_state"):
            project_plan_outcome(brief)

    def test_private_path_is_rejected_before_consumers_see_it(self) -> None:
        brief = canonical_brief()
        brief["next"] = str(Path.cwd())
        with self.assertRaisesRegex(OutcomeSourceError, "private filesystem"):
            project_plan_outcome(brief)

    def test_server_attaches_one_source_to_drive_and_chief_projections(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            plan_path = root / "demo" / "projects" / "notes" / "PLAN.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text(
                "# Notes\n\n"
                "## Operator Brief\n"
                "- Outcome ID: checkout-notes\n"
                "- Outcome Revision: 7\n"
                "- Outcome Updated At: 2026-08-02T04:45:22Z\n"
                "- Outcome State: working\n"
                "- Status: watching\n"
                "- Priority: 10\n"
                "- Outcome: Ship accurate notes for the next tagged build.\n"
                "- Next: Draft the outline from the owning plan.\n\n"
                "## Tasks\n- [pending] Draft\n",
                encoding="utf-8",
            )
            previous_root = browser_server.DEV_ROOT
            browser_server.DEV_ROOT = root
            try:
                plan = browser_server.plan_meta(plan_path)
                dashboard = browser_server.build_mission_control([plan])
            finally:
                browser_server.DEV_ROOT = previous_root

        selected = dashboard["selected"]
        source = selected["outcome_document"]
        self.assertEqual(source["revision"], 7)
        self.assertEqual(source["outcome"]["id"], "checkout-notes")
        self.assertEqual(selected["drive_document"]["revision"], source["revision"])
        self.assertEqual(selected["chief_of_staff"]["revision"], source["revision"])
        self.assertEqual(selected["chief_of_staff"]["outcome_id"], source["outcome"]["id"])
        self.assertNotIn("path", source)
        self.assertNotIn("source_path", source)

    def test_malformed_canonical_fields_do_not_create_typed_source(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            plan_path = root / "demo" / "PLAN.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text(
                "# Demo\n\n## Operator Brief\n"
                "- Outcome ID: demo-outcome\n"
                "- Outcome Revision: nope\n"
                "- Outcome Updated At: 2026-08-02T04:45:22Z\n"
                "- Outcome State: working\n"
                "- Outcome: Do the work.\n"
                "- Next: Prove the work.\n",
                encoding="utf-8",
            )
            previous_root = browser_server.DEV_ROOT
            browser_server.DEV_ROOT = root
            try:
                plan = browser_server.plan_meta(plan_path)
            finally:
                browser_server.DEV_ROOT = previous_root
        self.assertIsNone(plan["outcome_document"])
        self.assertIsNone(plan["drive_document"])
        self.assertIsNone(plan["chief_of_staff"])


if __name__ == "__main__":
    unittest.main()
