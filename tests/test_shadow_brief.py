"""Contract checks for the private, single-path Shadow brief producer."""

from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
