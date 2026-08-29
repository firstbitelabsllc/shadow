from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from browser import server
from tests.proc_fixture import git


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "shadow-status.py"

PLAN = """# M20 — Shadow releases itself safely

## Brief

- Project: release-confidence
- Mode: ship
- Priority: 1

## Tasks

### M20 — Nightly proof earns release confidence
- [pending] Fresh-home migration survives rollback ~aa11 | proof: cmd true
- [pending] Installed Shadow survives the release story ~bb22 (DoD) | proof: read release receipt -> every story passed | needs: ~aa11
"""


class PlainOutcomeNamesLeadEveryHumanSurface(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        git(repo, "add", "PLAN.md")
        git(repo, "commit", "-qm", "fixture")
        return repo

    def run_status(
        self,
        repo: Path,
        home: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        home.mkdir()
        return subprocess.run(
            [sys.executable, str(STATUS), "--root", str(repo), *args],
            cwd=ROOT,
            env={**os.environ, "HOME": str(home)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_status_leads_with_plain_names_and_keeps_ids_in_commands(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            result = self.run_status(repo, root / "status-home")

        self.assertEqual(result.returncode, 0, result.stderr)
        entity_block = result.stdout.strip().split("\n\n", 1)[1]
        self.assertEqual(
            entity_block.splitlines()[0],
            "release confidence — Shadow releases itself safely",
        )
        ordered_names = [
            "Shadow releases itself safely",
            "Current outcome: Nightly proof earns release confidence",
            "current: Nightly proof earns release confidence",
            "Fresh-home migration survives rollback",
            "Installed Shadow survives the release story",
        ]
        positions = [entity_block.index(name) for name in ordered_names]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("M20", entity_block)

        id_lines = [
            line.strip()
            for line in entity_block.splitlines()
            if "~aa11" in line or "~bb22" in line
        ]
        self.assertEqual(len(id_lines), 1)
        self.assertTrue(id_lines[0].startswith("Claim: shadow throw "), id_lines[0])

    def test_json_retains_the_machine_ids_hidden_from_status(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            result = self.run_status(repo, root / "json-home", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)["v4_plans"][0]
        self.assertEqual(record["board_resume"], "~aa11")
        self.assertEqual(
            [
                checkpoint["id"]
                for milestone in record["milestones"]
                for checkpoint in milestone["checkpoints"]
            ],
            ["~aa11", "~bb22"],
        )

    def test_browser_projects_only_plain_names_into_visible_fields(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "browser-home"
            home.mkdir()
            _, records, warning = server.board_plan_records(repo, home)

        self.assertIsNone(warning)
        record = records[0]
        self.assertEqual(record["project"], "release-confidence")
        self.assertEqual(record["title"], "Shadow releases itself safely")
        self.assertEqual(
            [milestone["title"] for milestone in record["milestones"]],
            ["Nightly proof earns release confidence"],
        )
        self.assertEqual(
            [checkpoint["text"] for checkpoint in record["milestones"][0]["checkpoints"]],
            [
                "Fresh-home migration survives rollback",
                "Installed Shadow survives the release story",
            ],
        )
        self.assertEqual(
            [checkpoint["id"] for checkpoint in record["milestones"][0]["checkpoints"]],
            ["~aa11", "~bb22"],
        )


if __name__ == "__main__":
    unittest.main()
