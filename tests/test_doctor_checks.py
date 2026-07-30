"""Hermetic tests for runtime-doctor documentation and JSON escaping."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "scripts" / "vidux-doctor.sh"


def build_fixture(
    tmp_dir: str,
    *,
    automation_boundary: bool = True,
    operations_boundary: bool = True,
    omit_automation: bool = False,
    omit_operations: bool = False,
) -> Path:
    root = Path(tmp_dir)
    (root / "guides").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "fleet").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(DOCTOR, root / "scripts" / "vidux-doctor.sh")

    if not omit_automation:
        body = (
            "The selected coding host owns scheduling and worker dispatch.\n"
            if automation_boundary
            else "Automation runs work.\n"
        )
        (root / "guides" / "automation.md").write_text(body, encoding="utf-8")

    if not omit_operations:
        body = (
            "Vidux is not an agent scheduler.\n"
            if operations_boundary
            else "Vidux fleet operations.\n"
        )
        (root / "docs" / "fleet" / "operations.md").write_text(
            body,
            encoding="utf-8",
        )
    return root


def run_doctor(root: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "bash",
            str(root / "scripts" / "vidux-doctor.sh"),
            "--json",
            "--repo",
            str(root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def find_check(payload: dict, check_id: str) -> dict | None:
    return next((item for item in payload["checks"] if item["id"] == check_id), None)


class HostExecutionBoundaryCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def check(self, root: Path) -> dict:
        _rc, out, err = run_doctor(root)
        self.assertNotIn("command not found", err)
        payload = json.loads(out)
        result = find_check(payload, "host_execution_boundary_intact")
        self.assertIsNotNone(result)
        return result

    def test_passes_when_both_public_boundaries_are_intact(self) -> None:
        self.assertEqual(self.check(build_fixture(self._tmp.name))["status"], "pass")

    def test_warns_when_automation_boundary_is_missing(self) -> None:
        result = self.check(
            build_fixture(self._tmp.name, automation_boundary=False)
        )
        self.assertEqual(result["status"], "warn")
        self.assertIn("guides/automation.md", result["details"])

    def test_warns_when_operations_boundary_is_missing(self) -> None:
        result = self.check(
            build_fixture(self._tmp.name, operations_boundary=False)
        )
        self.assertEqual(result["status"], "warn")
        self.assertIn("docs/fleet/operations.md", result["details"])

    def test_warns_when_a_boundary_document_is_absent(self) -> None:
        result = self.check(build_fixture(self._tmp.name, omit_operations=True))
        self.assertEqual(result["status"], "warn")
        self.assertIn("docs/fleet/operations.md", result["details"])

    def test_doctor_contains_no_destructive_cleanup_commands(self) -> None:
        source = DOCTOR.read_text(encoding="utf-8")
        self.assertNotIn("worktree remove", source)
        self.assertNotIn("rm -rf", source)


class JsonEscapeFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        extracted = subprocess.run(
            ["sed", "-n", "/^json_escape()/,/^}/p", str(DOCTOR)],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        self.assertTrue(extracted.strip())
        self._fn_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sh",
            delete=False,
        )
        self._fn_file.write(extracted)
        self._fn_file.close()
        self.addCleanup(lambda: Path(self._fn_file.name).unlink(missing_ok=True))

    def escape(self, raw: str) -> str:
        result = subprocess.run(
            ["bash", "-c", f'source {self._fn_file.name}; json_escape "$1"', "--", raw],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_escapes_double_quotes(self) -> None:
        self.assertEqual(self.escape('say "hi"'), 'say \\"hi\\"')

    def test_escapes_backslashes(self) -> None:
        self.assertEqual(self.escape("a\\b"), "a\\\\b")

    def test_plain_text_passes_through(self) -> None:
        self.assertEqual(self.escape("guides/automation.md"), "guides/automation.md")


if __name__ == "__main__":
    unittest.main()
