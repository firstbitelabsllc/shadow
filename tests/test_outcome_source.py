"""Tests for the one plan-derived Outcome source."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from browser import server
from browser.outcome_source import OutcomeSourceError, project_plan_outcome


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "shadow-outcome-validate.py"


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
    def test_projection_is_closed_and_valid(self) -> None:
        document = project_plan_outcome(canonical_brief())
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "outcome.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), "--input", str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(document["schema"], "shadow.outcome.v1")
        self.assertEqual(document["outcome"]["id"], "checkout-notes")
        self.assertNotIn("path", document)

    def test_missing_revision_fails_closed(self) -> None:
        brief = canonical_brief()
        del brief["outcome_revision"]
        with self.assertRaisesRegex(OutcomeSourceError, "outcome_revision"):
            project_plan_outcome(brief)

    def test_private_path_fails_closed(self) -> None:
        brief = canonical_brief()
        brief["next"] = str(Path.cwd())
        with self.assertRaisesRegex(OutcomeSourceError, "private filesystem"):
            project_plan_outcome(brief)

    def test_needs_input_requires_exactly_abc(self) -> None:
        brief = canonical_brief() | {
            "outcome_state": "needs_input",
            "decision_id": "choose-review",
            "decision": "How should we review?",
            "option_a_id": "focused-check",
            "option_a": "Focused check",
            "option_a_consequence": "Run the direct regression.",
            "option_b_id": "full-check",
            "option_b": "Full check",
            "option_b_consequence": "Run every local test.",
            "option_c_id": "stop-now",
            "option_c": "Stop now",
            "option_c_consequence": "Leave the result open.",
        }
        document = project_plan_outcome(brief)
        self.assertEqual(
            [item["id"] for item in document["ask"]["options"]],
            ["focused-check", "full-check", "stop-now"],
        )
        del brief["option_c"]
        with self.assertRaisesRegex(OutcomeSourceError, "option_c"):
            project_plan_outcome(brief)

    def test_server_attaches_one_source_to_both_views(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            plan = root / "PLAN.md"
            plan.write_text(
                "# Notes\n\n## Operator Brief\n"
                "- Outcome ID: checkout-notes\n"
                "- Outcome Revision: 7\n"
                "- Outcome Updated At: 2026-08-02T04:45:22Z\n"
                "- Outcome State: working\n"
                "- Outcome: Ship accurate notes for the next tagged build.\n"
                "- Next: Draft the outline from the owning plan.\n",
                encoding="utf-8",
            )
            record = server.plan_record(plan, root)
        self.assertIsNone(record["contract_error"])
        self.assertEqual(record["outcome"]["revision"], record["decision"]["revision"])
        self.assertEqual(record["briefing"]["outcome_id"], record["outcome"]["outcome"]["id"])


if __name__ == "__main__":
    unittest.main()
