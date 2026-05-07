"""Tests for scripts/vidux-pr-body.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-pr-body.py"

spec = importlib.util.spec_from_file_location("vidux_pr_body", SCRIPT)
assert spec is not None
pr_body = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = pr_body
spec.loader.exec_module(pr_body)


class PrBodyTests(unittest.TestCase):
    def test_builds_ready_pr_body_with_linear_ref(self):
        body = pr_body.build_pr_body(
            lane="codex/linear-hardening",
            task="LI-5",
            linear="eve-123",
            resume="nurse CI and reply to review findings",
            changes=["update templates", "add helper"],
        )

        self.assertIn("Lane: codex/linear-hardening", body)
        self.assertIn("Plan task: LI-5", body)
        self.assertIn("Linear: EVE-123", body)
        self.assertIn("Resume point: nurse CI and reply to review findings", body)
        self.assertIn("- update templates", body)
        self.assertTrue(body.endswith("\n"))

    def test_rejects_malformed_linear_ref(self):
        with self.assertRaises(ValueError):
            pr_body.build_pr_body(
                lane="codex/linear-hardening",
                task="LI-5",
                linear="linear:abc",
                resume="nurse CI",
                changes=["update templates"],
            )

    def test_cli_prints_canonical_body(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--lane",
                "codex/test",
                "--task",
                "BD-68",
                "--linear",
                "EVE-456",
                "--resume",
                "fix checks",
                "--change",
                "ship fix",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plan task: BD-68", result.stdout)
        self.assertIn("Linear: EVE-456", result.stdout)
        self.assertIn("- ship fix", result.stdout)


if __name__ == "__main__":
    unittest.main()
