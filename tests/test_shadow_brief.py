"""Contract checks for the private, single-path Shadow brief producer."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_plan_store as plan_store  # noqa: E402

SPEC = importlib.util.spec_from_file_location("shadow_brief", ROOT / "scripts" / "shadow-brief.py")
assert SPEC and SPEC.loader
brief = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = brief
SPEC.loader.exec_module(brief)


class PrivateStoreTests(unittest.TestCase):
    def test_optional_shadow_status_timeout_does_not_abort_collection(self):
        timeout = subprocess.TimeoutExpired(["shadow", "status", "--by", "leo"], 8)
        with mock.patch.object(brief, "_run", side_effect=timeout):
            excerpt = brief.collect_shadow_status_excerpt()

        self.assertIn("timed out", excerpt)
        self.assertIn("revision-checked Shadow board", excerpt)

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

    def test_morning_brief_is_the_same_reader_first_umbrella_product(self):
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
            "analysis": {
                "executive_read": [
                    "Shadow changed how large plans are read, so one busy project can no longer erase the rest of the portfolio from the note."
                ],
                "material_changes": [
                    {
                        "project": "Shadow",
                        "status": "verified locally",
                        "headline": "Large plans no longer make the brief lose the plot",
                        "fact": "The plan reader now reconstructs the complete plan before extracting work and decisions.",
                        "meaning": "This restores the context the chief-of-staff analysis needs; the next natural window still has to prove delivery.",
                        "evidence": ["current Shadow plan", "recent source history"],
                        "links": [],
                    }
                ],
            },
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
            "Shadow morning brief — 2026-08-12T08:00:00-04:00",
        )
        self.assertEqual(
            brief.brief_subject("evening", packet["generated_at"]),
            "Shadow evening brief — 2026-08-12T08:00:00-04:00",
        )
        self.assertIn("What materially changed", html)
        self.assertIn("The chief-of-staff read", html)
        self.assertIn("Decided for you", html)
        self.assertIn("Snowcubes", html)
        self.assertIn("Reply and relationships", html)
        self.assertNotIn("Commerce observation", html)
        self.assertIn("8 Snowcubes sources were unavailable", html)
        self.assertIn("Proposal only: Leo approves before any send.", html)
        self.assertIn("Open native source", html)
        self.assertLess(html.index("What materially changed"), html.index("Decided for you"))
        self.assertNotIn("Snowcubes chief-of-staff brief", html)
        self.assertNotIn("How this note thinks", html)
        self.assertNotIn("What building looks like now", html)
        self.assertNotIn("Every workstream, in human terms", html)

    def test_material_changes_explain_code_motion_without_branch_mechanics(self):
        analysis = brief.build_chief_of_staff_analysis(
            board={"entities": [], "claims": []},
            repos=[
                brief.RepoPaint(
                    name="shadow",
                    path="/private/shadow",
                    last_commit_age_h=1.0,
                    recent_commits=[
                        "fix: keep brief alive when one plan read fails (#468)",
                        "feat: publish plan trees with root cas",
                    ],
                )
            ],
            github=[],
            vercel={"available": True, "deployments": []},
            supabase={"available": True, "projects": []},
            mail={"available": False},
            source_health={},
        )

        change = analysis["material_changes"][0]
        self.assertEqual(change["project"], "Shadow")
        self.assertIn("plan", (change["headline"] + change["fact"] + change["meaning"]).lower())
        prose = json.dumps(change)
        self.assertNotIn("#468", prose)
        self.assertNotIn("root cas", prose.lower())
        self.assertNotIn("plan-scale-live", prose)

    def test_analysis_has_no_retired_nia_context(self):
        analysis = brief.build_chief_of_staff_analysis(
            board={"entities": [], "claims": []},
            repos=[],
            github=[],
            vercel={"available": True, "deployments": []},
            supabase={"available": True, "projects": []},
            mail={"available": False},
            source_health={},
        )

        reasoning = analysis["reasoning_contract"]
        self.assertNotIn("historical_context", reasoning)
        self.assertNotIn("nia", json.dumps(analysis).lower())

    def test_expenses_web_change_is_not_mislabeled_as_snowcubes(self):
        changes = brief.build_material_changes(
            board={"projects": [], "entities": [], "claims": []},
            repos=[
                brief.RepoPaint(
                    name="expenses-web",
                    path="/private/expenses-web",
                    recent_commits=[
                        "feat(switchboard): restore source-only weekly planning",
                        "backup(cron): cover legacy transactions and paginate listings",
                    ],
                )
            ],
            github=[],
            vercel={"available": True, "deployments": []},
        )

        self.assertEqual(changes[0]["project"], "Expenses Web")
        self.assertIn("weekly planning", changes[0]["headline"].lower())
        self.assertIn("older transaction", changes[0]["fact"].lower())
        self.assertNotIn("Snowcubes", json.dumps(changes[0]))

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
    def test_partitioned_plan_is_materialized_before_the_brief_parses_it(self):
        logical = (
            "# Product plan\n\n"
            "## Brief\n- Project: snowcubes\n- Mode: ship\n- Priority: 3\n\n"
            "## Tasks\n### Customer truth\n"
            "- [pending] Make every food page explain its allergen risk ~safe | proof: read storefront -> disclosure is visible\n"
            "- [pending] Prove the disclosure in production ~dod1 (DoD) | proof: read storefront -> live proof exists | needs: ~safe\n\n"
            "## Deferred\n\n## Contradictions\n\n## Progress\n"
            "- 2026-08-13T12:00:00Z STRUCT customer truth added | trigger: safety gap\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            build = plan_store.build_tree(logical)
            plan.write_bytes(build.root_bytes)
            for digest, content in build.objects.items():
                object_path = plan.parent / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
                object_path.parent.mkdir(parents=True, exist_ok=True)
                object_path.write_bytes(content)

            parsed = brief.parse_plan(plan)

        self.assertEqual(parsed.project, "snowcubes")
        self.assertEqual(parsed.open_checkpoints[0].id, "safe")
        self.assertIn("allergen risk", parsed.open_checkpoints[0].title)
        self.assertIn("customer truth added", parsed.recent_progress[0])

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

    def test_one_unreadable_plan_is_explicit_and_does_not_abort_the_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readable = root / "readable" / "PLAN.md"
            unreadable = root / "unreadable" / "PLAN.md"
            readable.parent.mkdir()
            unreadable.parent.mkdir()
            readable.write_text("- Project: readable\n- Priority: 4\n", encoding="utf-8")
            unreadable.write_text("- Project: unreadable\n- Priority: 5\n", encoding="utf-8")
            board = root / "board.json"
            board.write_text(
                json.dumps(
                    {
                        "revision": 8,
                        "projects": [
                            {"id": "readable", "priority": 1},
                            {"id": "unreadable", "priority": 2},
                        ],
                        "entities": [
                            {"id": "entity-readable", "project": "readable", "plan": str(readable)},
                            {"id": "entity-unreadable", "project": "unreadable", "plan": str(unreadable)},
                        ],
                        "claims": [],
                    }
                ),
                encoding="utf-8",
            )
            original_parse_plan = brief.parse_plan

            def parse_with_deadlock(path):
                if path == unreadable:
                    raise OSError(11, "Resource deadlock avoided")
                return original_parse_plan(path)

            with mock.patch.object(brief, "BOARD_PATH", board), mock.patch.object(
                brief, "parse_plan", side_effect=parse_with_deadlock
            ):
                result = brief.collect_board()

        by_project = {entity["project"]: entity for entity in result["entities"]}
        self.assertEqual(result["revision"], 8)
        self.assertEqual(by_project["readable"]["availability"], "available")
        self.assertEqual(by_project["unreadable"]["availability"], "unavailable")
        self.assertIn("Resource deadlock avoided", by_project["unreadable"]["error"])
        self.assertIn(str(unreadable), by_project["unreadable"]["wake"])
        self.assertIn("next natural brief window", by_project["unreadable"]["wake"])
        health = brief.build_shadow_board_health(result)
        self.assertFalse(health["available"])
        self.assertIn("unreadable", health["error"])
        self.assertIn(str(unreadable), health["wake"])

    def test_snowcubes_card_names_a_partial_shadow_plan_outage(self):
        plan = Path("/tmp/example-unreadable-plan.md")
        board = {
            "revision": 12,
            "entities": [
                {
                    "project": "example",
                    "availability": "unavailable",
                    "error": "plan read failed: Resource deadlock avoided",
                    "wake": f"Make {plan} locally readable; the next natural brief window retries it.",
                }
            ],
        }
        with mock.patch.object(
            brief,
            "collect_superhuman_context",
            return_value={"available": False, "error": "account not linked"},
        ), mock.patch.object(
            brief, "_snowcubes_m12_surface", return_value={"name": "M12 cafe-doctor", "state": "unavailable"}
        ):
            context = brief.collect_snowcubes_context(vercel={"available": False}, board=board)

        shadow_card = next(item for item in context["surfaces"] if item["name"] == "Shadow work")
        self.assertEqual(shadow_card["state"], "unavailable")
        self.assertIn("1 plan source(s)", shadow_card["now"])
        self.assertIn("no execution state is inferred", shadow_card["now"])
        self.assertIn(str(plan), shadow_card["wake"])

    def test_partial_plan_outage_suppresses_portfolio_ranking_and_zero_inference(self):
        board = {
            "revision": 13,
            "entities": [
                {
                    "id": "unreadable-high-priority",
                    "project": "unreadable",
                    "priority": 1,
                    "availability": "unavailable",
                    "wake": "Make the named plan locally readable; retry at the next natural window.",
                },
                {
                    "id": "readable-lower-priority",
                    "project": "readable",
                    "priority": 2,
                    "availability": "available",
                    "resume": "rd1",
                    "open_checkpoints": [{"id": "rd1", "title": "Ship the readable result"}],
                    "blocked": [],
                    "forgotten": [],
                },
            ],
            "claims": [],
        }
        source_health = {
            "shadow_board": {
                "available": False,
                "error": "one plan is unreadable",
                "wake": "Make the named plan locally readable.",
            }
        }

        recommendations = brief.build_recommendations(board, [])
        recommendation_text = " ".join(item.text for item in recommendations)
        self.assertIn("UNKNOWN", recommendation_text)
        self.assertNotIn("Keep readable first", recommendation_text)

        analysis = brief.build_chief_of_staff_analysis(
            board=board,
            repos=[],
            github=[],
            vercel={},
            supabase={},
            mail={"available": False},
            source_health=source_health,
        )
        executive_read = " ".join(analysis["executive_read"])
        self.assertIn("portfolio-wide priority", executive_read)
        self.assertIn("UNKNOWN", executive_read)
        self.assertIn(
            "Hold portfolio ranking until every plan is readable",
            [item["title"] for item in analysis["decided_for_you"]],
        )
        # An unreadable plan may still hold a request for Leo, so no all-clear is claimed.
        self.assertNotEqual(analysis["needs_leo"]["title"], "No decision needs you right now")
        self.assertIn("not a portfolio-wide all-clear", analysis["needs_leo"]["prose"])

        html = brief.render_html({
            "slot": "evening",
            "generated_at": "2026-08-13T20:00:00-04:00",
            "board": board,
            "repos": [],
            "github_open_prs": [],
            "recommendations": [item.__dict__ for item in recommendations],
            "analysis": analysis,
            "paint_health": source_health,
            "snowcubes_context": {"surfaces": []},
        })
        self.assertIn("Part of the portfolio is unreadable", html)
        self.assertIn("open-work totals are UNKNOWN", html)
        self.assertNotIn("Nothing needs forcing right now", html)
        self.assertNotIn("Readable is the main move", html)

    def test_packet_snowcubes_card_uses_the_final_board_snapshot(self):
        board = {"revision": 23, "entities": [], "claims": []}
        personal_mail = {"available": False, "error": "personal mail unavailable"}
        business_mail = {"available": False, "error": "business mail unavailable"}
        companion = {"observed_at": "2026-08-13T15:00:00Z", "surfaces": []}

        with mock.patch.object(brief, "portfolio_root", return_value=Path("/tmp/portfolio")), \
            mock.patch.object(brief, "collect_repos", return_value=[]), \
            mock.patch.object(brief, "collect_github", return_value=[]), \
            mock.patch.object(brief, "collect_vercel", return_value={"available": False}), \
            mock.patch.object(brief, "collect_supabase", return_value={"available": False}), \
            mock.patch.object(brief.shutil, "which", side_effect=AssertionError("the brief must not query Nia")), \
            mock.patch.object(
                brief,
                "collect_superhuman_context",
                side_effect=[personal_mail, business_mail],
            ), \
            mock.patch.object(brief, "collect_growth_source_status", return_value={}), \
            mock.patch.object(brief, "build_local_git_health", return_value={"available": True}), \
            mock.patch.object(brief, "build_paint_health", return_value={}), \
            mock.patch.object(
                brief,
                "_run",
                return_value=subprocess.CompletedProcess([], 0, "status", ""),
            ), \
            mock.patch.object(brief, "collect_board", return_value=board), \
            mock.patch.object(brief, "_read_board_revision", return_value=23), \
            mock.patch.object(brief, "collect_snowcubes_context", return_value=companion) as collect_companion, \
            mock.patch.object(brief, "build_recommendations", return_value=[]), \
            mock.patch.object(brief, "build_chief_of_staff_analysis", return_value={}):
            packet = brief.collect_packet(slot="morning")

        self.assertIs(packet["board"], board)
        self.assertIs(collect_companion.call_args.kwargs["board"], packet["board"])
        self.assertIs(collect_companion.call_args.kwargs["mail"], business_mail)
        self.assertNotIn("nia", packet)
        self.assertNotIn("nia", packet["paint_health"])

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

    def test_delivery_evidence_accepts_two_consecutive_twice_daily_windows(self):
        morning = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "scheduled_for": "2026-08-12T08:00:00-04:00",
            "slot": "morning",
            "trigger": "launchd-calendar",
        }
        evening = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "scheduled_for": "2026-08-12T20:00:00-04:00",
            "slot": "evening",
            "trigger": "launchd-calendar",
        }

        result = brief.verify_window_receipts([morning, evening])

        self.assertFalse(result["ok"])
        self.assertEqual(result["windows"], [morning["scheduled_for"], evening["scheduled_for"]])
        self.assertNotIn("need two distinct current-schema natural windows; found 1", result["problems"])
        self.assertNotIn("latest natural windows are not consecutive", result["problems"])
        self.assertTrue(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-08-12T08:00:00-04:00"),
                brief.datetime.fromisoformat("2026-08-12T20:00:00-04:00"),
            )
        )
        self.assertFalse(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-08-12T08:00:00-04:00"),
                brief.datetime.fromisoformat("2026-08-13T20:00:00-04:00"),
            )
        )
        self.assertFalse(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-08-13T20:00:00-04:00"),
                brief.datetime.fromisoformat("2026-08-14T08:00:00+14:00"),
            )
        )
        self.assertFalse(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-08-13T20:00:00-04:00"),
                brief.datetime.fromisoformat("2026-08-14T08:00:00+05:00"),
            )
        )
        self.assertFalse(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-08-13T20:00:00-04:00"),
                brief.datetime.fromisoformat("2026-08-14T08:00:00-05:00"),
            )
        )
        self.assertTrue(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-10-31T20:00:00-04:00"),
                brief.datetime.fromisoformat("2026-11-01T08:00:00-05:00"),
            )
        )
        self.assertTrue(
            brief.natural_windows_are_consecutive(
                brief.datetime.fromisoformat("2026-03-07T20:00:00-05:00"),
                brief.datetime.fromisoformat("2026-03-08T08:00:00-04:00"),
            )
        )

    def test_window_and_mailbox_receipts_reject_naive_timestamps(self):
        morning = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "trigger": "launchd-calendar",
            "slot": "morning",
            "scheduled_for": "2026-08-12T08:00:00-04:00",
            "generated_at": "2026-08-12T08:05:00",
            "receipt": {"sent_at": "2026-08-12T08:06:00-04:00"},
        }
        evening = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "trigger": "launchd-calendar",
            "slot": "evening",
            "scheduled_for": "2026-08-12T20:00:00-04:00",
            "generated_at": "2026-08-12T20:05:00-04:00",
            "receipt": {"sent_at": "2026-08-12T20:06:00"},
        }

        window_result = brief.verify_window_receipts([morning, evening])

        self.assertIn(
            "2026-08-12T08:00:00-04:00: generated_at invalid",
            window_result["problems"],
        )
        self.assertIn(
            "2026-08-12T20:00:00-04:00: sent timestamp invalid",
            window_result["problems"],
        )

        mailbox_result = brief.verify_mailbox_readbacks(
            [evening],
            [
                {
                    "schema": brief.MAILBOX_READBACK_SCHEMA,
                    "status": "EXACT_SENT_CONFIRMED",
                    "scheduled_for": evening["scheduled_for"],
                    "sent_at": "2026-08-12T20:06:00",
                }
            ],
        )
        self.assertIn(
            "2026-08-12T20:00:00-04:00: mailbox sent timestamp invalid",
            mailbox_result["problems"],
        )

    def test_producer_records_report_timezone_from_any_host_timezone(self):
        window = brief.scheduled_window(
            brief.datetime.fromisoformat("2026-08-12T05:10:00-07:00")
        )

        self.assertTrue(window["on_schedule"])
        self.assertEqual(window["slot"], "morning")
        self.assertEqual(window["scheduled_for"], "2026-08-12T08:00:00-04:00")
        self.assertIsNotNone(
            brief._scheduled_window_instant({"scheduled_for": window["scheduled_for"]})
        )

        winter = brief.scheduled_window(
            brief.datetime.fromisoformat("2026-11-02T17:00:00-08:00")
        )
        self.assertTrue(winter["on_schedule"])
        self.assertEqual(winter["slot"], "evening")
        self.assertEqual(winter["scheduled_for"], "2026-11-02T20:00:00-05:00")

        off_slot = brief.scheduled_window(
            brief.datetime.fromisoformat("2026-08-12T08:00:00-07:00")
        )
        self.assertFalse(off_slot["on_schedule"])
        self.assertIsNone(off_slot["scheduled_for"])

        naive = brief.scheduled_window(
            brief.datetime.fromisoformat("2026-08-12T08:00:00")
        )
        self.assertFalse(naive["on_schedule"])
        self.assertIsNone(naive["scheduled_for"])

    def test_schedule_reports_host_timezone_drift_from_report_timezone(self):
        expected = brief.launch_agent_plist(Path("/opt/shadow/scripts/shadow-brief.py"))

        self.assertEqual(
            brief.schedule_configuration_problems(
                expected,
                expected,
                now=brief.datetime.fromisoformat("2026-08-12T08:00:00-04:00"),
            ),
            [],
        )
        self.assertEqual(
            brief.schedule_configuration_problems(
                expected,
                expected,
                now=brief.datetime.fromisoformat("2026-08-12T08:00:00-07:00"),
            ),
            ["HostTimezone"],
        )
        self.assertTrue(
            brief.host_timezone_matches_report(
                brief.datetime.fromisoformat("2026-11-02T20:00:00-05:00")
            )
        )
        self.assertFalse(
            brief.host_timezone_matches_report(
                brief.datetime.fromisoformat("2026-11-02T20:00:00-04:00")
            )
        )
        self.assertFalse(
            brief.host_timezone_matches_report(
                brief.datetime.fromisoformat("2026-11-02T20:00:00")
            )
        )

    def test_verify_windows_reads_mixed_slot_mailbox_pair(self):
        evening = "2026-08-13T20:00:00-04:00"
        morning = "2026-08-14T08:00:00-04:00"
        rows = [
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": "evening",
                "scheduled_for": evening,
            },
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": "morning",
                "scheduled_for": morning,
            },
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": False,
                "trigger": "launchd-calendar",
                "slot": "morning",
                "scheduled_for": morning,
                "receipt": {"subject": "off-schedule duplicate"},
            },
        ]

        def readback(scheduled_for: str, suffix: str) -> dict[str, object]:
            return {
                "schema": brief.MAILBOX_READBACK_SCHEMA,
                "status": "EXACT_SENT_CONFIRMED",
                "scheduled_for": scheduled_for,
                "acting_email": brief.SELF_MAIL,
                "from": brief.SELF_MAIL,
                "to": [brief.SELF_MAIL],
                "message_id": f"mailbox-{suffix}",
                "thread_id": f"thread-{suffix}",
                "labels": ["SENT"],
                "raw_html_sha256": "a" * 64,
                "sent_at": scheduled_for,
            }

        verification = {
            "ok": True,
            "problems": [],
            "windows": [evening, morning],
            "message_ids": [],
            "ignored_legacy_windows": [],
            "ignored_noncalendar_windows": [],
            "ignored_nonslot_windows": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window_log = root / "windows.jsonl"
            mailbox_log = root / "mailbox.jsonl"
            window_log.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            mailbox_log.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in (
                        readback(evening, "evening"),
                        readback(morning, "morning"),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with mock.patch.object(brief, "WINDOW_LOG", window_log), mock.patch.object(
                brief, "MAILBOX_READBACK_LOG", mailbox_log
            ), mock.patch.object(brief, "verify_window_receipts", return_value=verification), contextlib.redirect_stdout(output):
                exit_code = brief.cmd_verify_windows(mock.Mock())

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["mailbox_readbacks"]["message_ids"],
            ["mailbox-evening", "mailbox-morning"],
        )

    def test_window_selection_orders_offset_timestamps_by_instant(self):
        rows = [
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": "evening",
                "scheduled_for": "2026-08-12T20:00:00+14:00",
            },
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": "morning",
                "scheduled_for": "2026-08-12T08:00:00-04:00",
            },
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": "evening",
                "scheduled_for": "2026-08-12T20:00:00-04:00",
            },
        ]

        result = brief.verify_window_receipts(rows)

        self.assertEqual(
            result["windows"],
            ["2026-08-12T08:00:00-04:00", "2026-08-12T20:00:00-04:00"],
        )
        self.assertNotIn(
            "latest natural 08:00/20:00 windows are not consecutive",
            result["problems"],
        )

    def test_readback_ignores_trailing_off_schedule_duplicate(self):
        scheduled_for = "2026-08-14T08:00:00-04:00"
        eligible = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "trigger": "launchd-calendar",
            "slot": "morning",
            "scheduled_for": scheduled_for,
        }
        off_schedule = {
            **eligible,
            "on_schedule": False,
            "receipt": {"subject": "off-schedule duplicate"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window_log = root / "windows.jsonl"
            mailbox_log = root / "mailbox.jsonl"
            window_log.write_text(
                "\n".join(json.dumps(row) for row in (eligible, off_schedule)) + "\n",
                encoding="utf-8",
            )
            readback = {
                "schema": brief.MAILBOX_READBACK_SCHEMA,
                "status": "EXACT_SENT_CONFIRMED",
            }
            with mock.patch.object(brief, "WINDOW_LOG", window_log), mock.patch.object(
                brief, "MAILBOX_READBACK_LOG", mailbox_log
            ), mock.patch.object(
                brief, "fetch_superhuman_mailbox_readback", return_value=readback
            ) as fetch, contextlib.redirect_stdout(io.StringIO()):
                exit_code = brief.cmd_readback_window(mock.Mock(scheduled_for=None))

        self.assertEqual(exit_code, 0)
        self.assertEqual(fetch.call_args.args[0], eligible)


if __name__ == "__main__":
    unittest.main()
