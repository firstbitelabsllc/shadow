from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "shadow-status.py"

PLAN = """# Demo

## Brief

- Outcome ID: ship-demo
- Outcome Revision: 1
- Outcome Updated At: 2026-08-03T03:00:00Z
- Outcome State: needs_input
- Outcome: Ship the demo.
- Next: Choose the review depth.
- Decision ID: choose-review
- Decision: How should we review it?
- Option A ID: focused-check
- Option A: Focused check
- Option A Consequence: Run only the direct regression.
- Option B ID: full-check
- Option B: Full check
- Option B Consequence: Run every local test.
- Option C ID: stop-now
- Option C: Stop now
- Option C Consequence: Leave the result unshipped.
"""


class StatusTests(unittest.TestCase):
    def run_status(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(STATUS), "--root", str(root), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_text_is_a_brief_with_abc(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = self.run_status(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Outcome: Ship the demo.", result.stdout)
        self.assertIn("A. Focused check", result.stdout)
        self.assertIn("C. Stop now", result.stdout)
        self.assertNotIn(dirname, result.stdout)

    def test_json_is_bounded_and_path_relative(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = self.run_status(root, "--json")
            payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.status.v1")
        self.assertEqual(payload["plans"][0]["path"], "PLAN.md")
        self.assertNotIn(dirname, result.stdout)

    def test_invalid_root_fails_cleanly(self) -> None:
        result = self.run_status(Path("/definitely/missing/shadow-root"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a directory", result.stderr)


if __name__ == "__main__":
    unittest.main()


V4_PLAN = """# Demo v4

## Brief

- Project: demo
- Mode: ship

## Tasks

### M1 — live milestone
- [completed] parser lands ~aa11 | proof: cmd true
- [pending] the ready row ~bb22 | proof: cmd npm run gate
- [pending] closes ~cc33 (DoD) | proof: read site -> renders | needs: ~bb22

## Progress

- 2026-08-08T00:00:00Z ~aa11 PROOF true -> ok
"""


class StatusV4Tests(StatusTests):
    def test_v4_plan_renders_brief_not_schema_error(self) -> None:
        # The regression this pins: status used to validate ONLY the retired v3
        # outcome schema, so a grammar-clean v4 plan reported "needs a valid
        # Brief / outcome must be a string" (250/250 plans on the reference
        # machine). A v4 plan must render its Brief and never the v3 error.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = self.run_status(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("demo", result.stdout)
            self.assertIn("Mode: ship", result.stdout)
            self.assertIn("M1 — live milestone (1/3 done)", result.stdout)
            self.assertIn("Resume: [pending] the ready row ~bb22", result.stdout)
            self.assertNotIn("outcome must be a string", result.stdout)
            self.assertNotIn("needs a valid Brief", result.stdout)

    def test_v4_plan_renders_from_any_cwd(self) -> None:
        # discover_plans emits root-relative paths; status must resolve them
        # against the scan root, not the process cwd.
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                cwd=dirname if dirname != str(ROOT) else "/",
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn("Mode: ship", result.stdout)

    def test_v4_json_carries_v4_plans(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "PLAN.md").write_text(V4_PLAN, encoding="utf-8")
            result = self.run_status(root, "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["v4_plans"]), 1)
            self.assertEqual(payload["v4_plans"][0]["project"], "demo")
