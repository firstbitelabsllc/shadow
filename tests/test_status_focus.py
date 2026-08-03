from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "pilot-puppy-status.py"

PLAN = """# Demo

## Operator Brief

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
        self.assertEqual(payload["schema"], "pilot-puppy.status.v1")
        self.assertEqual(payload["plans"][0]["path"], "PLAN.md")
        self.assertNotIn(dirname, result.stdout)

    def test_invalid_root_fails_cleanly(self) -> None:
        result = self.run_status(Path("/definitely/missing/pilot-puppy-root"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
