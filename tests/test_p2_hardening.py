"""Four hardening fixes from the 2026-08-15 extension/migration audit."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.plan_tree_fixture import install_plan_tree
from tests.test_local_plan_store import ARCHIVABLE_PLAN
from tests.test_root_board import git, project, run
from tests.test_shadow_lint import CLEAN_PLAN, lint


ROOT = Path(__file__).resolve().parent.parent
HOT_PLAN_LIMIT = 256 * 1024
STATUS = ROOT / "scripts" / "shadow-status.py"

_DOCTOR_SPEC = importlib.util.spec_from_file_location(
    "shadow_doctor_p2", ROOT / "scripts" / "shadow-doctor.py"
)
assert _DOCTOR_SPEC and _DOCTOR_SPEC.loader
doctor = importlib.util.module_from_spec(_DOCTOR_SPEC)
sys.modules.setdefault(_DOCTOR_SPEC.name, doctor)
_DOCTOR_SPEC.loader.exec_module(doctor)

sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402


def _local_plan_text(project: str) -> str:
    return (
        f"# {project}\n\n"
        "## Brief\n\n"
        f"- Project: {project}\n"
        "- Mode: ship\n"
        "- Priority: 2\n\n"
        "## Tasks\n\n"
        "### The useful outcome\n"
        "- [pending] first result exists ~aa11 | proof: cmd true\n"
        "- [pending] the outcome is proven ~bb22 (DoD) | proof: cmd true | needs: ~aa11\n\n"
        "## Progress\n\n"
        "- 2026-08-15T00:00:00Z NOTE seeded\n"
    )


def _write_local_plan(home: Path, slug: str, project: str, *, bytes_over: int = 0) -> Path:
    body = _local_plan_text(project).encode("utf-8")
    if bytes_over:
        target = HOT_PLAN_LIMIT + bytes_over
        if len(body) >= target:
            raise AssertionError("fixture already meets the over-budget target")
        body = body + b"x" * (target - len(body))
    path = home / ".shadow" / "plans" / slug / "PLAN.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


class DoctorSlotsDegradeToOneFailRow(unittest.TestCase):
    def test_slots_machinery_exception_is_one_fail_row_not_a_traceback(self) -> None:
        crashes = (
            ImportError("cannot import slots machinery"),
            ValueError("slots.md exploded"),
            OSError("slots.md unreadable"),
        )
        for boom in crashes:
            with self.subTest(error=type(boom).__name__):
                spec = mock.Mock()
                spec.loader.exec_module.side_effect = boom
                with mock.patch("importlib.util.spec_from_file_location", return_value=spec):
                    try:
                        rows = doctor.slot_checks()
                    except Exception as exc:  # noqa: BLE001 — the bug is a leaked exception
                        self.fail(f"slots machinery leaked {exc!r}")
                self.assertEqual(len(rows), 1, rows)
                self.assertEqual(rows[0]["state"], "fail")
                self.assertIn(str(boom), rows[0]["detail"])


class LocalPlanQuarantineNeverBlanksTheBoard(unittest.TestCase):
    def test_an_unreadable_local_authority_sits_out_while_peers_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()
            project(portfolio, name="healthy", display_name="healthy")
            local = home / ".shadow" / "plans" / "shadow"
            local.mkdir(parents=True)
            (local / "PLAN.md").write_bytes(b"\xff\xfe not valid utf-8 \x80")

            seeded = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            # A quarantined plan registers broken, so status exits 1 — the
            # designed contract — but the import must complete: the priority
            # type bug aborted the whole reconcile before any peer registered.
            self.assertEqual(seeded.returncode, 1, seeded.stdout + seeded.stderr)
            self.assertIn("quarantined from board import", seeded.stderr)
            self.assertNotIn("priority must be 1-5", seeded.stderr)
            payload = json.loads(seeded.stdout)
            by_project = {
                entity["project"]: entity
                for entity in payload["root_board"]["entities"]
            }
            self.assertEqual(by_project["healthy"]["resume"], "~aa11")
            self.assertIsNone(by_project["shadow"]["resume"])


class CorruptPlanTreeBoardView(unittest.TestCase):
    def test_one_plan_failing_to_materialize_renders_broken_and_leaves_the_other(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            blank = root / "blank"
            for path in (home, portfolio, blank):
                path.mkdir()
            project(portfolio, name="healthy", display_name="healthy")
            sick = project(portfolio, name="sick", display_name="sick")
            source = (sick / "PLAN.md").read_bytes()
            install_plan_tree(sick, source)
            git(sick, "add", "PLAN.md", "PLAN.d")
            git(sick, "commit", "--quiet", "-m", "partition sick plan")
            seeded = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            digest = board.open_plan(sick / "PLAN.md").root["catalog_root"]
            object_path = sick / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
            object_path.write_bytes(b"tamper")

            observed = run(
                home,
                "status",
                "--json",
                cwd=blank,
                extra_env={"SHADOW_PORTFOLIO_ROOT": str(portfolio)},
            )

            self.assertNotIn("Traceback", observed.stderr)
            self.assertNotIn("Traceback", observed.stdout)
            self.assertEqual(observed.returncode, 1, observed.stdout + observed.stderr)
            payload = json.loads(observed.stdout)
            by_project = {row["project"]: row for row in payload["v4_plans"]}
            self.assertIn("healthy", by_project)
            self.assertFalse(by_project["healthy"].get("broken"))
            self.assertIn("sick", by_project)
            self.assertTrue(by_project["sick"].get("broken"))


class FreshBoardOverBudgetDoesNotBlank(unittest.TestCase):
    def test_first_status_keeps_healthy_local_plan_when_peer_is_one_byte_over_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            blank = root / "blank"
            home.mkdir()
            blank.mkdir()
            healthy = _write_local_plan(home, "shadow", "shadow")
            sick = _write_local_plan(home, "ai", "ai", bytes_over=1)
            self.assertEqual(len(sick.read_bytes()), HOT_PLAN_LIMIT + 1)
            self.assertLessEqual(len(healthy.read_bytes()), HOT_PLAN_LIMIT)
            env = {
                **os.environ,
                "HOME": str(home),
                "SHADOW_PORTFOLIO_ROOT": str(blank),
            }
            env.pop("SHADOW_DEV_ROOT", None)
            observed = subprocess.run(
                [sys.executable, str(STATUS), "--json"],
                cwd=blank,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )

            self.assertNotEqual(observed.stdout.strip(), "", observed.stderr)
            self.assertNotIn("portfolio import failed before a board existed", observed.stderr)
            payload = json.loads(observed.stdout)
            projects = {row["project"] for row in payload["v4_plans"]}
            self.assertIn("shadow", projects)
            healthy_row = next(row for row in payload["v4_plans"] if row["project"] == "shadow")
            self.assertIn("first result exists", json.dumps(healthy_row))
            combined = observed.stdout + observed.stderr
            self.assertRegex(combined.lower(), r"budget|hot plan|limit")
            self.assertEqual(observed.returncode, 1, observed.stdout + observed.stderr)


class OverBudgetRemedyNamesMigrateWhenNothingArchives(unittest.TestCase):
    def test_lint_and_status_name_migrate_when_zero_milestones_are_archive_eligible(self) -> None:
        oversized = CLEAN_PLAN + ("x" * (HOT_PLAN_LIMIT + 1 - len(CLEAN_PLAN.encode("utf-8"))))
        self.assertEqual(len(oversized.encode("utf-8")), HOT_PLAN_LIMIT + 1)
        findings = [item for item in lint.lint_plan(oversized) if item["check"] == "HOT-PLAN-BYTES"]
        self.assertTrue(findings)
        self.assertIn("trim or relocate plan text", findings[0]["detail"])
        with self.assertRaises(board.BoardError) as ctx:
            board.assert_hot_plan_budget(oversized.encode("utf-8"))
        self.assertIn("trim or relocate plan text", str(ctx.exception))
        self.assertNotIn("shadow lifecycle", str(ctx.exception))

    def test_lint_keeps_lifecycle_when_a_milestone_is_archive_eligible(self) -> None:
        body = ARCHIVABLE_PLAN.encode("utf-8")
        oversized = body + b"x" * (HOT_PLAN_LIMIT + 1 - len(body))
        findings = [
            item
            for item in lint.lint_plan(oversized.decode("utf-8"))
            if item["check"] == "HOT-PLAN-BYTES"
        ]
        self.assertTrue(findings)
        self.assertIn("shadow lifecycle", findings[0]["detail"])
        self.assertNotIn("trim or relocate plan text", findings[0]["detail"])


if __name__ == "__main__":
    unittest.main()
