"""Contract checks for the private, single-path Shadow brief producer."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("shadow_brief", ROOT / "scripts" / "shadow-brief.py")
assert SPEC and SPEC.loader
brief = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = brief
SPEC.loader.exec_module(brief)


class PrivateStoreTests(unittest.TestCase):
    def test_receipts_are_private_shadow_state(self):
        self.assertEqual(brief.PRIVATE_BRIEF_ROOT, Path.home() / ".shadow" / "briefs")
        self.assertEqual(brief.EVIDENCE_DIR, brief.PRIVATE_BRIEF_ROOT / "evidence")
        self.assertEqual(brief.LOG_DIR, brief.PRIVATE_BRIEF_ROOT / "ledger")
        self.assertNotIn("plans", str(brief.EVIDENCE_DIR))

    def test_delivery_never_falls_back_to_an_ide_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html = root / "brief.html"
            html.write_text("<p>brief</p>", encoding="utf-8")
            evidence = root / "evidence"
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "deliver_superhuman_http", return_value=None
            ):
                receipt = brief.deliver_superhuman(
                    html,
                    subject="Shadow morning brief",
                    send_authorized_self=True,
                )

            self.assertEqual(receipt["status"], "blocked")
            self.assertEqual(receipt["delivery_status"], "not_sent")
            self.assertEqual(receipt["to"], [brief.SELF_MAIL])
            self.assertTrue((evidence / "superhuman-receipt.json").is_file())

    def test_scheduler_has_one_calendar_producer(self):
        program = Path("/opt/shadow/scripts/shadow-brief.py")
        plist = brief.launch_agent_plist(program)

        self.assertEqual(plist["Label"], brief.LABEL)
        self.assertEqual(
            plist["StartCalendarInterval"],
            [{"Hour": 8, "Minute": 0}, {"Hour": 20, "Minute": 0}],
        )
        self.assertEqual(plist["ProgramArguments"][1], str(program))
        self.assertEqual(plist["ProgramArguments"][-1], "--scheduled-trigger")

    def test_snowcubes_companion_keeps_missing_business_sources_explicit(self):
        with mock.patch.object(
            brief,
            "collect_superhuman_context",
            return_value={"available": False, "error": "account not linked"},
        ):
            context = brief.collect_snowcubes_context()

        reply = context["surfaces"][0]
        self.assertEqual(reply["name"], "Reply and relationships")
        self.assertEqual(reply["state"], "unavailable")
        self.assertIn("no inbox state is inferred", reply["now"])
        self.assertIn(brief.SNOWCUBES_BUSINESS_MAIL, reply["wake"])
        self.assertTrue(all(item["state"] == "unavailable" for item in context["surfaces"][1:]))


class SourceBoundaryTests(unittest.TestCase):
    def test_source_contains_no_cursor_agent_delivery_path(self):
        source = (ROOT / "scripts" / "shadow-brief.py").read_text(encoding="utf-8")
        self.assertNotIn("cursor-agent", source)
        self.assertNotIn("shadow-bidaily-digest", source)
        self.assertNotIn("/plans/", source)
        self.assertNotIn("noreply.github.com", source)

    def test_public_command_dispatches_to_the_owned_producer(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "brief", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verify-windows", result.stdout)


class AuthorityScopeTests(unittest.TestCase):
    def test_claims_are_scoped_by_entity_and_row(self):
        claims = [
            {"entity": "entity-a", "row": "~aa11", "return_by": "a"},
            {"entity": "entity-b", "row": "~aa11", "return_by": "b"},
        ]
        index = brief._claim_index(claims)
        self.assertEqual(index[("entity-a", "aa11")]["return_by"], "a")
        self.assertEqual(index[("entity-b", "aa11")]["return_by"], "b")
        self.assertNotIn(("entity-c", "aa11"), index)

    def test_board_project_priority_overrides_plan_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "snowcubes" / "PLAN.md"
            plan.parent.mkdir()
            plan.write_text("- Project: snowcubes\n- Priority: 99\n", encoding="utf-8")
            board = root / "board.json"
            board.write_text(
                json.dumps(
                    {
                        "revision": 4,
                        "projects": [{"id": "snowcubes", "priority": 3}],
                        "entities": [{"id": "entity-snow", "project": "snowcubes", "plan": str(plan)}],
                        "claims": [],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(brief, "BOARD_PATH", board):
                entities = brief.collect_board()["entities"]
            self.assertEqual(entities[0]["priority"], 3)

    def test_scheduled_receipt_keeps_original_trigger_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "windows.jsonl"
            scheduled_for = "2026-08-12T08:00:00-04:00"
            summary = {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "trigger_proof": {"source": "launchd"},
                "scheduled_window": {
                    "on_schedule": True,
                    "slot": "morning",
                    "scheduled_for": scheduled_for,
                },
            }
            with mock.patch.object(brief, "WINDOW_LOG", log), mock.patch.object(
                brief, "LOG_DIR", root
            ), mock.patch.object(brief, "scheduled_trigger_is_authorized", return_value=True):
                brief.append_scheduled_window(
                    summary,
                    scheduled_trigger=True,
                    now=brief.datetime.fromisoformat("2026-08-12T09:45:00-04:00"),
                )
            row = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(row["scheduled_for"], scheduled_for)
            self.assertEqual(row["slot"], "morning")


if __name__ == "__main__":
    unittest.main()
