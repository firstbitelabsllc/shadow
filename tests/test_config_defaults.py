from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from browser import server


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
PLAN = """# Demo

## Operator Brief

- Outcome ID: ship-demo
- Outcome Revision: 1
- Outcome Updated At: 2026-08-03T03:00:00Z
- Outcome State: working
- Outcome: Ship the demo.
- Next: Run the next bounded check.
"""


class ConfigDefaultsTests(unittest.TestCase):
    def test_status_uses_dev_root_env_and_cli_flag_wins(self) -> None:
        with tempfile.TemporaryDirectory() as dirname, tempfile.TemporaryDirectory() as override:
            root = Path(dirname)
            (root / "PLAN.md").write_text(PLAN, encoding="utf-8")
            result = subprocess.run(
                [str(CLI), "status", "--json"],
                cwd=ROOT,
                env={**os.environ, "SHADOW_DEV_ROOT": str(root)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["plans"][0]["path"], "PLAN.md")

            result = subprocess.run(
                [str(CLI), "status", "--json", "--root", override],
                cwd=ROOT,
                env={**os.environ, "SHADOW_DEV_ROOT": str(root)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["plans"], [])

    def test_browser_defaults_use_environment_and_flags_override(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SHADOW_DEV_ROOT": "/tmp/env-root",
                "SHADOW_BROWSER_HOST": "localhost",
                "SHADOW_BROWSER_PORT": "8123",
            },
            clear=False,
        ):
            args = server.parser().parse_args([])
            self.assertEqual(args.root, "/tmp/env-root")
            self.assertEqual(args.host, "localhost")
            self.assertEqual(args.port, 8123)

            args = server.parser().parse_args(
                ["--root", "/tmp/flag-root", "--host", "127.0.0.1", "--port", "8124"]
            )
            self.assertEqual(args.root, "/tmp/flag-root")
            self.assertEqual(args.host, "127.0.0.1")
            self.assertEqual(args.port, 8124)


if __name__ == "__main__":
    unittest.main()
