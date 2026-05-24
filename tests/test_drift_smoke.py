"""Long smoke tests for realistic vidux drift workflows."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DRIFT = ROOT / "scripts" / "vidux-drift-log.py"
SIGNPOST = ROOT / "scripts" / "vidux_signpost.py"
EXAMPLES = ROOT / "examples" / "drift-smoke"


class DriftSmokeTests(unittest.TestCase):
    def _copy_example(self, name: str, root: Path) -> Path:
        source = EXAMPLES / name
        target = root / name
        shutil.copytree(source, target)
        return target

    def test_api_to_cli_pivot_records_cache_and_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self._copy_example("api-cli-pivot", Path(tmp))
            plan = work / "PLAN.md"
            cache = Path(tmp) / "drift-cache.jsonl"
            telemetry = Path(tmp) / "signposts.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DRIFT),
                    str(plan),
                    "--task",
                    "API-1",
                    "--planned",
                    "Add an HTTP API endpoint for local invoice generation.",
                    "--actual",
                    "Added a CLI helper because the caller is a local script.",
                    "--why",
                    "The original plan named the transport before identifying the caller.",
                    "--plan-update",
                    "Future API work now requires a caller/transport row before implementation.",
                    "--next",
                    "Document the CLI invocation and add a follow-up API task only if a network caller appears.",
                    "--prevention",
                    "Before coding, name the caller and transport separately.",
                    "--block-task",
                    "API-1",
                    "--add-task",
                    "API-2: Document CLI invocation [Evidence: Drift D-20260522-01]",
                    "--cache",
                    str(cache),
                    "--telemetry",
                    str(telemetry),
                    "--today",
                    "2026-05-22",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("## Drift Log", text)
            self.assertIn("Prevention: Before coding, name the caller and transport separately.", text)
            self.assertIn("- [blocked] API-1: Add an HTTP API endpoint", text)
            self.assertIn("[Drift: D-20260522-01]", text)
            self.assertIn("API-2: Document CLI invocation", text)

            cache_row = json.loads(cache.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(cache_row["drift_id"], "D-20260522-01")
            self.assertEqual(cache_row["blocked_task"], "API-1")
            self.assertEqual(cache_row["prevention_hints"], ["Before coding, name the caller and transport separately."])

            suggest = subprocess.run(
                [
                    sys.executable,
                    str(DRIFT),
                    "suggest",
                    str(plan),
                    "--cache",
                    str(cache),
                    "--limit",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(suggest.returncode, 0, suggest.stderr)
            self.assertIn("Before coding, name the caller and transport separately.", suggest.stdout)

    def test_ui_telemetry_subplan_mirrors_and_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self._copy_example("ui-telemetry-subplan", Path(tmp))
            plan = work / "PLAN.md"
            subplan = work / "investigations" / "telemetry-render.md"
            cache = Path(tmp) / "drift-cache.jsonl"
            telemetry = Path(tmp) / "signposts.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DRIFT),
                    str(plan),
                    "--task",
                    "UI-3",
                    "--planned",
                    "Render telemetry directly in the browser sidebar.",
                    "--actual",
                    "Split raw signpost capture from sidebar rendering and mirrored the rendering risk into a subplan.",
                    "--why",
                    "The plan combined collection, aggregation, and UI proof in one row.",
                    "--plan-update",
                    "Parent plan tracks signpost capture first; subplan owns render proof.",
                    "--next",
                    "Run the signpost summary and then implement the sidebar view.",
                    "--prevention",
                    "Separate collection, aggregation, and rendering rows in future plans.",
                    "--block-task",
                    "UI-3",
                    "--add-task",
                    "UI-4: Capture raw signpost events before rendering [Evidence: Drift D-20260522-01]",
                    "--add-task",
                    "UI-5: Render sidebar summary from signpost output [Depends: UI-4] [Evidence: Drift D-20260522-01]",
                    "--subplan",
                    str(subplan),
                    "--cache",
                    str(cache),
                    "--telemetry",
                    str(telemetry),
                    "--today",
                    "2026-05-22",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            plan_text = plan.read_text(encoding="utf-8")
            self.assertIn("## Drift Log", plan_text)
            self.assertIn("- [blocked] UI-3: Render telemetry directly", plan_text)
            self.assertIn("UI-4: Capture raw signpost events before rendering", plan_text)
            self.assertIn("UI-5: Render sidebar summary from signpost output", plan_text)
            self.assertIn("D-20260522-01 from `PLAN.md`", subplan.read_text(encoding="utf-8"))

            profile = subprocess.run(
                [
                    sys.executable,
                    str(SIGNPOST),
                    "summary",
                    "--log",
                    str(telemetry),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(profile.returncode, 0, profile.stderr)
            summary = json.loads(profile.stdout)
            self.assertEqual(summary["features"]["drift.record"]["count"], 1)
            self.assertEqual(summary["features"]["drift.record"]["statuses"]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
