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
        by_name = {item["name"]: item for item in context["surfaces"]}
        for name in ("Commerce", "Funnel", "Search", "Local profile", "Lifecycle email", "SEO"):
            self.assertEqual(by_name[name]["state"], "unavailable")
            self.assertTrue(by_name[name].get("native_link"))
            self.assertTrue(by_name[name].get("wake"))
        self.assertIn("Shadow work", by_name)
        self.assertIn("Deploy", by_name)
        self.assertIn("M12 cafe-doctor", by_name)
        self.assertEqual(by_name["Relationships to nurture"]["state"], "unavailable")

    def test_business_signal_has_private_thread_identity_and_proposal_not_draft(self):
        signal = {
            "subject": "Some Knicks swag from Snowcubes",
            "last_message_at": "2026-08-12T00:17:20Z",
            "kind": "human_or_other",
            "thread_id": "19f5396bf1f4ab27",
            "native_link": "https://mail.superhuman.com/thread/opaque",
        }
        with mock.patch.object(
            brief,
            "collect_superhuman_context",
            return_value={"available": True, "signals": [signal]},
        ), mock.patch.object(brief, "collect_board", return_value={"revision": 9}), mock.patch.object(
            brief, "_snowcubes_m12_surface", return_value={"name": "M12 cafe-doctor", "state": "unavailable"}
        ):
            context = brief.collect_snowcubes_context(vercel={"available": False})
        reply = context["surfaces"][0]
        self.assertEqual(reply["thread_id"], signal["thread_id"])
        self.assertEqual(reply["native_link"], signal["native_link"])
        self.assertIn("Proposal only", reply["proposal"])
        self.assertIn("no draft or send was created", reply["proposal"])
        nurture = next(item for item in context["surfaces"] if item["name"] == "Relationships to nurture")
        self.assertIn("Proposal only", nurture["proposal"])

    def test_linkless_business_signal_is_unknown_not_a_reply_prompt(self):
        signal = {
            "subject": "A real person wrote",
            "last_message_at": "2026-08-12T00:17:20Z",
            "kind": "human_or_other",
            "thread_id": "opaque-thread-id",
            "native_link": None,
        }
        with mock.patch.object(
            brief,
            "collect_superhuman_context",
            return_value={"available": True, "signals": [signal]},
        ), mock.patch.object(brief, "collect_board", return_value={"revision": 9}), mock.patch.object(
            brief, "_snowcubes_m12_surface", return_value={"name": "M12 cafe-doctor", "state": "unavailable"}
        ):
            context = brief.collect_snowcubes_context(vercel={"available": False})

        reply = context["surfaces"][0]
        nurture = next(item for item in context["surfaces"] if item["name"] == "Relationships to nurture")
        self.assertEqual(reply["state"], "unknown")
        self.assertIn("not ranked as a reply", reply["now"])
        self.assertIn("do not manufacture", reply["wake"])
        self.assertNotIn("native_link", reply)
        self.assertNotIn("proposal", reply)
        self.assertEqual(nurture["state"], "unknown")
        self.assertNotIn("proposal", nurture)

    def test_rendered_companion_shows_native_link_and_proposal(self):
        packet = {
            "slot": "morning",
            "generated_at": "2026-08-12T08:00:00-04:00",
            "board": {"revision": 9, "entities": [], "claims": []},
            "repos": [],
            "github_open_prs": [],
            "recommendations": [],
            "analysis": {},
            "snowcubes_context": {
                "surfaces": [
                    {
                        "name": "Reply and relationships",
                        "state": "available",
                        "now": "Reply now",
                        "next": "Nurture next",
                        "source": "Superhuman business inbox",
                        "observed_at": "2026-08-12T12:00:00Z",
                        "proposal": "Proposal only: prepare for Leo's approval.",
                        "native_link": "https://mail.superhuman.com/thread/opaque",
                    }
                ]
            },
        }
        html = brief.render_html(packet)
        self.assertIn("Open native source", html)
        self.assertIn("Proposal only", html)
        self.assertIn("Superhuman business inbox", html)

    def test_morning_brief_is_snowcubes_first_and_compact(self):
        names = [
            "Reply and relationships",
            "Relationships to nurture",
            "Commerce",
            "Funnel",
            "Search",
            "Local profile",
            "Lifecycle email",
            "Shadow work",
            "Deploy",
        ]
        packet = {
            "slot": "morning",
            "generated_at": "2026-08-12T08:00:00-04:00",
            "board": {"revision": 9, "entities": [], "claims": []},
            "repos": [],
            "github_open_prs": [],
            "recommendations": [],
            "analysis": {},
            "snowcubes_context": {
                "surfaces": [
                    {
                        "name": name,
                        "state": "available" if index == 0 else "unavailable",
                        "now": f"{name} observation",
                        "next": f"{name} next move",
                        "source": f"{name} source",
                        "observed_at": "2026-08-12T12:00:00Z",
                        "native_link": f"https://example.test/{index}",
                        "wake": None if index == 0 else f"Restore {name} read access.",
                        "proposal": "Proposal only: Leo approves before any send."
                        if index == 0
                        else None,
                    }
                    for index, name in enumerate(names)
                ]
            },
        }

        html = brief.render_html(packet)

        self.assertEqual(
            brief.brief_subject("morning", packet["generated_at"]),
            "Snowcubes morning brief — 2026-08-12T08:00:00-04:00",
        )
        self.assertEqual(
            brief.brief_subject("evening", packet["generated_at"]),
            "Shadow evening brief — 2026-08-12T08:00:00-04:00",
        )
        self.assertIn("Snowcubes chief-of-staff brief", html)
        self.assertLess(
            html.index("Snowcubes: now → then → waiting"),
            html.index("Business coverage"),
        )
        self.assertLess(html.index("Priority 1"), html.index("Priority 2"))
        self.assertLess(html.index("Priority 2"), html.index("Priority 3"))
        for name in names:
            self.assertIn(name, html)
        self.assertIn("Proposal only: Leo approves before any send.", html)
        self.assertIn("Open native source", html)
        self.assertIn("This email is a read-only projection, not a plan or task store.", html)
        self.assertNotIn("What building looks like now", html)
        self.assertNotIn("Every workstream, in human terms", html)

    def test_m12_card_uses_the_source_packet_timestamp_without_claiming_current_money(self):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio = Path(tmp)
            repo = portfolio / "trysnowcubes-web"
            script = repo / "scripts" / "cafe-doctor.py"
            fixture = repo / "tests" / "fixtures" / "cafe-native-three-partner.json"
            script.parent.mkdir(parents=True)
            fixture.parent.mkdir(parents=True)
            script.write_text("# present", encoding="utf-8")
            fixture.write_text("{}", encoding="utf-8")
            result = {
                "ok": True,
                "checks": [{
                    "name": "fresh-native",
                    "ok": True,
                    "state": "HEALTHY",
                    "detail": "three falsifiers passed",
                    "observed_at": "2026-08-12T02:00:00Z",
                    "action": "suppressed",
                    "wake": "collect a fresh read-only Calendar, Superhuman, and Shopify packet before any money action",
                }],
            }
            with mock.patch.object(brief, "portfolio_root", return_value=portfolio), mock.patch.object(
                brief, "_run", return_value=subprocess.CompletedProcess([], 0, json.dumps(result), "")
            ) as run:
                card = brief._snowcubes_m12_surface("2026-08-12T08:00:00Z")

        self.assertEqual(card["state"], "unavailable")
        self.assertEqual(card["observed_at"], "2026-08-12T02:00:00Z")
        self.assertIn("safety fixture", card["now"])
        self.assertIn("no cafe balance is inferred", card["now"])
        self.assertEqual(card["wake"], result["checks"][0]["wake"])
        self.assertEqual(
            run.call_args.args[0],
            [sys.executable, str(script), "--json", "--fresh-native", str(fixture)],
        )

    def test_m12_card_paints_a_discrepancy_and_missing_packet_without_connector_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio = Path(tmp)
            repo = portfolio / "trysnowcubes-web"
            script = repo / "scripts" / "cafe-doctor.py"
            fixture = repo / "tests" / "fixtures" / "cafe-native-three-partner.json"
            script.parent.mkdir(parents=True)
            fixture.parent.mkdir(parents=True)
            script.write_text("# present", encoding="utf-8")
            fixture.write_text("{}", encoding="utf-8")
            discrepancy = {
                "ok": False,
                "checks": [{
                    "name": "fresh-native", "ok": False, "state": "DISCREPANCY",
                    "detail": "provider state disagrees", "observed_at": "2026-08-12T02:00:00Z",
                    "wake": "reconcile the stable provider ID before any action",
                }],
            }
            with mock.patch.object(brief, "portfolio_root", return_value=portfolio), mock.patch.object(
                brief, "_run", return_value=subprocess.CompletedProcess([], 1, json.dumps(discrepancy), "")
            ):
                card = brief._snowcubes_m12_surface("2026-08-12T08:00:00Z")
            with mock.patch.object(brief, "portfolio_root", return_value=portfolio), mock.patch.object(
                brief, "_run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "checks": []}), "")
            ):
                missing = brief._snowcubes_m12_surface("2026-08-12T08:00:00Z")

        self.assertEqual(card["state"], "attention")
        self.assertEqual(card["observed_at"], "2026-08-12T02:00:00Z")
        self.assertEqual(card["wake"], "reconcile the stable provider ID before any action")
        self.assertEqual(missing["state"], "unavailable")
        self.assertIn("fresh-native packet is unavailable", missing["now"])


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
