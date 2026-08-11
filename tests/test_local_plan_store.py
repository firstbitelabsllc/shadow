"""Local plan authorities must never enter the board's private Git journal."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402


PLAN = """# Local demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2

## Tasks

### The local outcome
- [pending] prove local authority ~aa11 | proof: cmd true
- [pending] local authority is done ~bb22 (DoD) | proof: cmd true | needs: ~aa11

## Progress

- 2026-08-11T00:00:00Z NOTE seeded locally
"""


class LocalPlanStore(unittest.TestCase):
    def test_portfolio_import_moves_registered_ai_leo_plan_to_private_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            portfolio = root / "portfolio"
            source = portfolio / "ai-leo"
            source.mkdir(parents=True)
            source_plan = source / "PLAN.md"
            source_plan.write_text(PLAN, encoding="utf-8")
            for args in (
                ("init", "--quiet"),
                ("config", "user.email", "shadow-test@example.invalid"),
                ("config", "user.name", "Shadow Test"),
                ("remote", "add", "origin", "git@github.com:leojkwan/ai-leo.git"),
                ("add", "PLAN.md"),
                ("commit", "--quiet", "-m", "seed"),
            ):
                result = subprocess.run(
                    ["git", "-C", str(source), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            local_plan = home / ".shadow" / "plans" / "ai-leo" / "PLAN.md"
            local_plan.parent.mkdir(parents=True)
            local_plan.write_text(PLAN, encoding="utf-8")
            board.reconcile(
                [{"plan": str(source_plan), "project": "demo", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )

            import shadow_board_import as importer

            spec = importlib.util.spec_from_file_location(
                "shadow_local_plan_status", ROOT / "scripts" / "shadow-status.py"
            )
            status = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(status)
            payload = importer.reconcile_portfolio(portfolio, status._amp, home=home)

            self.assertEqual(payload["entities"][0]["plan"], str(local_plan.resolve()))
            self.assertTrue(board.is_local_plan(Path(payload["entities"][0]["plan"]), home=home))
            # A stale executable can still append the old source alias once;
            # the next refresh removes that unclaimed duplicate rather than
            # letting it become a second authority.
            board.reconcile(
                [{"plan": str(source_plan), "project": "demo", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            again = importer.reconcile_portfolio(portfolio, status._amp, home=home)
            self.assertEqual(again["entities"][0]["plan"], str(local_plan.resolve()))
            self.assertEqual(len(again["entities"]), 1)

    def test_local_plan_claim_is_not_git_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            plan = home / ".shadow" / "plans" / "demo" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(PLAN, encoding="utf-8")

            payload = board.reconcile(
                [{"plan": str(plan), "project": "demo", "priority": 2, "candidates": ["~aa11"]}],
                [],
                home=home,
            )
            entity = payload["entities"][0]
            self.assertTrue(board.is_local_plan(plan, home=home))
            self.assertTrue((home / ".shadow" / ".git").is_dir())
            ignored = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "check-ignore", "-q", "plans/demo/PLAN.md"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ignored.returncode, 0, ignored.stderr)

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "shadow-throw.py"), "--entity", entity["id"], "--task", "~aa11", "--by", "local-seat"],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("read that local file directly", result.stdout)
            self.assertNotIn("current origin ref", result.stdout)
            state = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertEqual(state["claims"][0]["row"], "~aa11")
            tracked = subprocess.run(
                ["git", "-C", str(home / ".shadow"), "ls-files", "plans/demo/PLAN.md"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(tracked.stdout, "")
