"""Tests for scripts/vidux-local-operator-deferrals.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-local-operator-deferrals.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vidux_local_operator_deferrals", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


deferrals = _load_module()


class LocalOperatorDeferralsTests(unittest.TestCase):
    def test_build_payload_proves_rows_and_preserves_non_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "projects" / "connect-the-fleet" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("- [pending] **C-7: Ship mobile PR.**\n", encoding="utf-8")

            entries = [
                {
                    "id": "mobile",
                    "surface": "Mobile",
                    "gate": "owner_gated",
                    "canonical_refs": [
                        {"plan": "projects/connect-the-fleet/PLAN.md", "rows": ["C-7"]},
                    ],
                    "summary": "Mobile is elsewhere.",
                    "re_entry": ["Owner returns proof."],
                    "non_claim": "Does not claim mobile shipped.",
                }
            ]

            with mock.patch.object(deferrals, "FIREWALL_ENTRIES", entries):
                payload = deferrals.build_payload(root)

            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["mode"], "honest_deferrals_firewall")
            self.assertIn("did not execute local-CI lanes", " ".join(payload["global_non_claims"]))
            entry = payload["entries"][0]
            self.assertEqual(entry["status"], "ready")
            self.assertEqual(entry["canonical_refs"][0]["rows"][0]["line"], 1)
            self.assertEqual(entry["canonical_refs"][0]["rows"][0]["status"], "pending")

    def test_missing_row_blocks_firewall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "projects" / "connect-the-fleet" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("- [pending] **C-7: Ship mobile PR.**\n", encoding="utf-8")

            entries = [
                {
                    "id": "mobile",
                    "surface": "Mobile",
                    "gate": "owner_gated",
                    "canonical_refs": [
                        {"plan": "projects/connect-the-fleet/PLAN.md", "rows": ["C-999"]},
                    ],
                    "summary": "Mobile is elsewhere.",
                    "re_entry": ["Owner returns proof."],
                    "non_claim": "Does not claim mobile shipped.",
                }
            ]

            with mock.patch.object(deferrals, "FIREWALL_ENTRIES", entries):
                payload = deferrals.build_payload(root)

            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["entries"][0]["status"], "blocked")
            self.assertFalse(payload["entries"][0]["canonical_refs"][0]["rows"][0]["found"])

    def test_cli_markdown_and_json_outputs(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(ROOT),
                "--markdown",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Local Operator Deferrals Firewall", result.stdout)
        self.assertIn("Moussey mobile PWA", result.stdout)

        json_result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        payload = json.loads(json_result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertGreaterEqual(len(payload["entries"]), 6)


if __name__ == "__main__":
    unittest.main()
