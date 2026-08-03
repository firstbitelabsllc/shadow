from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "pilot-puppy"
DOCTOR = ROOT / "scripts" / "pilot-puppy-doctor.py"


class DoctorTests(unittest.TestCase):
    def run_doctor(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(CLI), "doctor", *args],
            cwd=ROOT,
            env={**os.environ, **(env or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_json_report_has_one_product_and_native_host_floor(self) -> None:
        result = self.run_doctor("--json")
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "pilot-puppy.doctor.v1")
        self.assertEqual(report["product"], "Pilot Puppy")
        self.assertEqual(result.returncode, 0 if report["ok"] else 1)
        names = {item["name"] for item in report["checks"]}
        self.assertIn("product identity", names)
        self.assertIn("native host floor", names)
        self.assertNotIn("token permissions", names)
        self.assertNotIn("background process", names)

    def test_bad_root_fails_identity_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            result = subprocess.run(
                ["python3", str(DOCTOR), "--json"],
                cwd=ROOT,
                env={**os.environ, "PILOT_PUPPY_ROOT": dirname},
                capture_output=True,
                text=True,
                check=False,
            )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["ok"])
        self.assertNotIn("Traceback", result.stderr)

    def test_text_output_is_human_readable(self) -> None:
        result = self.run_doctor()
        self.assertIn("[PASS] product identity", result.stdout)
        self.assertIn("checks without hard failure", result.stdout)


if __name__ == "__main__":
    unittest.main()
