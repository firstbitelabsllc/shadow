from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "shadow_brief_author",
    ROOT / "scripts" / "shadow-brief-author.py",
)
assert SPEC and SPEC.loader
author = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(author)


def packet() -> dict:
    return {
        "generated_at": "2026-08-15T08:00:00-04:00",
        "slot": "morning",
        "board": {
            "revision": 1981,
            "schema": "shadow.root-board.v1",
            "projects": [{"project": "ai-leo", "priority": 2}],
            "claims": [
                {
                    "project": "ai-leo",
                    "row": "~c6sp",
                    "owner": "codex-chief-of-staff",
                    "claimed_at": "2026-08-15T14:00:00Z",
                }
            ],
            "entities": [
                {
                    "project": "ai-leo",
                    "mode": "ship",
                    "priority": 2,
                    "resume": "~c6sp",
                    "availability": "available",
                    "open_checkpoints": [
                        {
                            "id": "c6sp",
                            "title": "define the model handoff",
                            "state": "pending",
                            "milestone": "M6",
                        }
                    ],
                    "recent_progress": ["Leo killed the deterministic producer."],
                }
            ],
        },
        "superhuman_context": {
            "status": "UNKNOWN",
            "available": True,
            "complete": False,
            "all_clear_allowed": False,
            "observed_at": "2026-08-15T12:00:00Z",
            "expected_identities": [
                "leojkwan@gmail.com",
                "trysnowcubes@gmail.com",
                "firstbitelabs@gmail.com",
            ],
            "coverage": [
                {
                    "expected_email": "firstbitelabs@gmail.com",
                    "linked": False,
                    "status": "UNKNOWN",
                    "wake": "Link the exact account.",
                }
            ],
            "urgent_replies": [],
            "forgotten_obligations": [],
            "waiting_replies": [],
        },
        "repos": [],
        "github_open_prs": [],
        "snowcubes_context": {"surfaces": []},
    }


def letter(ref: str = "packet.board") -> dict:
    return {
        "schema": "shadow.chief-of-staff-letter.v1",
        "verdict": "The old report is stopped; the replacement needs real judgment.",
        "what_matters": [
            {"text": "The deterministic producer is gone.", "source_refs": [ref]}
        ],
        "decisions_made": [],
        "needs_leo": [],
        "people_waiting": [],
        "risks": [],
        "next_owned_moves": [],
        "coverage_gaps": [],
        "closing": "I will keep the facts honest and the note human.",
    }


def artifact(evidence: dict, value: dict | None = None) -> dict:
    value = value or letter()
    return {
        "schema": author.ARTIFACT_SCHEMA,
        "letter": value,
        "author_receipt": {
            "schema": author.RECEIPT_SCHEMA,
            "status": "ok",
            "host": "codex",
            "evidence_sha256": author.sha256_json(evidence),
            "letter_sha256": author.sha256_json(value),
        },
        "evidence": evidence,
    }


def customer_packet() -> dict:
    opportunity_id = "opp-1"
    return {
        "generated_at": "2026-08-15T09:00:00-04:00",
        "snowcubes_customer_opportunities": {
            "schema": "shadow.snowcubes-customer-opportunities.v1",
            "observed_at": "2026-08-15T13:00:00+00:00",
            "status": "COMPLETE",
            "source_status": {"superhuman": "COMPLETE", "shopify": "COMPLETE"},
            "problems": [],
            "opportunities": [
                {
                    "opportunity_id": opportunity_id,
                    "join_state": "MATCHED",
                    "match_basis": "exact_order_id",
                    "confidence": "HIGH",
                    "customer_identity": {
                        "state": "KNOWN",
                        "shopify_customer_id": "gid://shopify/Customer/7",
                        "customer_email": "alice@example.com",
                    },
                    "mail": {
                        "provider_key": "superhuman:trysnowcubes@gmail.com:thread-7",
                        "thread_id": "thread-7",
                        "last_message_id": "message-8",
                        "subject": "Your first Snowcubes order",
                        "observed_at": "2026-08-15T12:00:00Z",
                        "age_hours": 1.0,
                        "confidence": "HIGH",
                        "semantic_status": "OBSERVED",
                        "waiting_direction": (
                            "latest visible message is inbound; Leo is not waiting on them"
                        ),
                        "action_tags": ["proactive"],
                    },
                    "shopify": {
                        "provider_key": "shopify:939cf1-24:order-9",
                        "order_id": "order-9",
                        "order_name": "TSC01615",
                        "shopify_customer_id": "gid://shopify/Customer/7",
                        "customer_email": "alice@example.com",
                        "created_at": "2026-08-11T12:00:00Z",
                        "observed_at": "2026-08-15T12:30:00Z",
                        "age_hours": 0.5,
                        "customer_order_count": 1,
                        "fulfillment_status": "fulfilled",
                        "delivery_status": "delivered",
                        "delivered_at": "2026-08-15T10:00:00Z",
                    },
                    "signals": {
                        "first_order": {
                            "state": "CONFIRMED",
                            "source": "shopify",
                            "confidence": "HIGH",
                        },
                        "delivery": {
                            "state": "CONFIRMED",
                            "source": "shopify",
                            "confidence": "HIGH",
                        },
                        "waiting_reply": {
                            "state": "NOT_OBSERVED",
                            "source": "superhuman",
                            "confidence": "HIGH",
                        },
                        "recovery": {
                            "state": "NOT_OBSERVED",
                            "source": "superhuman",
                            "confidence": "HIGH",
                        },
                        "relationship": {
                            "state": "PROPOSAL",
                            "source": "superhuman",
                            "confidence": "HIGH",
                        },
                    },
                    "permission_to_contact": "UNKNOWN",
                    "inventory_state": "UNKNOWN",
                    "protected_action": "PROPOSAL_ONLY",
                }
            ],
            "no_write_receipt": {
                "provider_calls": 0,
                "drafts_created": 0,
                "messages_sent": 0,
                "shopify_mutations": 0,
            },
        },
    }


def customer_letter(opportunity_id: str = "opp-1") -> dict:
    prefix = f"packet.snowcubes_customer_opportunities.{opportunity_id}"
    return {
        "schema": author.CUSTOMER_LETTER_SCHEMA,
        "status": "READY",
        "ranked_opportunities": [
            {
                "why_now": {
                    "text": "This first order is confirmed delivered and is ready for a personal review.",
                    "source_refs": [f"{prefix}.shopify", f"{prefix}.signals"],
                },
                "customer_order_thread_provenance": [
                    {
                        "source_ref": f"{prefix}.customer",
                        "provider": "shopify_customer",
                        "provider_id": "gid://shopify/Customer/7",
                    },
                    {
                        "source_ref": f"{prefix}.shopify",
                        "provider": "shopify_order",
                        "provider_id": "order-9",
                    },
                    {
                        "source_ref": f"{prefix}.mail",
                        "provider": "superhuman_thread",
                        "provider_id": "thread-7",
                    },
                ],
                "recommended_next_step": {
                    "text": "Review whether a personal arrival check-in would be useful.",
                    "source_refs": [f"{prefix}.shopify", f"{prefix}.mail"],
                },
                "draft_ready_factual_context": [
                    {
                        "text": "Order TSC01615 is the customer's first recorded order.",
                        "source_refs": [f"{prefix}.shopify", f"{prefix}.signals"],
                    },
                    {
                        "text": "Shopify records the order as delivered.",
                        "source_refs": [f"{prefix}.shopify"],
                    },
                ],
            }
        ],
        "exact_wake": None,
    }


def customer_artifact(evidence: dict, value: dict | None = None) -> dict:
    value = value or customer_letter()
    return {
        "schema": author.CUSTOMER_ARTIFACT_SCHEMA,
        "letter": value,
        "author_receipt": {
            "schema": author.CUSTOMER_RECEIPT_SCHEMA,
            "status": "ok",
            "host": "codex",
            "profile_sha256": author.sha256_json(author.load_customer_profile()),
            "prompt_sha256": author.hashlib.sha256(
                author.CUSTOMER_PROMPT_PATH.read_bytes()
            ).hexdigest(),
            "tools_allowed": "read-only sandbox",
            "evidence_sha256": author.sha256_json(evidence),
            "letter_sha256": author.sha256_json(value),
        },
        "evidence": evidence,
    }


CUSTOMER_NOW = author.datetime.fromisoformat("2026-08-15T13:00:00+00:00")


def project_customer(source: dict, profile: dict) -> dict:
    return author.build_customer_evidence_projection(
        source,
        profile,
        now=CUSTOMER_NOW,
    )


class ChiefOfStaffAuthorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = author.load_profile()
        self.evidence = author.build_evidence_projection(packet(), self.profile)

    def test_profile_has_no_default_author_and_keeps_three_expected_identities(
        self,
    ) -> None:
        self.assertIsNone(self.profile["default_host"])
        self.assertEqual(self.profile["allowed_hosts"], ["codex", "claude-code"])
        self.assertEqual(
            self.profile["expected_identities"],
            [
                "leojkwan@gmail.com",
                "trysnowcubes@gmail.com",
                "firstbitelabs@gmail.com",
            ],
        )

    def test_projection_is_bounded_and_excludes_deterministic_analysis_prose(
        self,
    ) -> None:
        source = packet()
        source["analysis"] = {"executive_read": "This renderer thinks for Leo."}
        source["board"]["entities"] = source["board"]["entities"] * 100
        source["board"]["entities"][0]["recent_progress"] = ["x" * 5000] * 100
        evidence = author.build_evidence_projection(source, self.profile)
        encoded = json.dumps(evidence)
        self.assertNotIn("This renderer thinks for Leo", encoded)
        self.assertEqual(evidence["schema"], author.EVIDENCE_SCHEMA)
        self.assertTrue(
            all(set(row) == {"ref", "kind", "fact"} for row in evidence["facts"])
        )
        missing = {
            row["fact"]["expected_email"]
            for row in evidence["facts"]
            if row["ref"].startswith("packet.superhuman.coverage.missing.")
        }
        self.assertEqual(missing, {"leojkwan@gmail.com", "trysnowcubes@gmail.com"})
        self.assertLessEqual(
            len([row for row in evidence["facts"] if row["kind"] == "entity_status"]),
            self.profile["evidence_caps"]["entities"],
        )
        self.assertNotIn("x" * 1201, encoded)

    def test_mail_projection_reports_all_populations_without_provider_ids(self) -> None:
        source = packet()
        mail = source["superhuman_context"]
        private_thread_id = "thread-private-7"
        private_message_id = "message-private-8"
        mail["problems"] = [f"Re-open exact thread {private_thread_id}."]
        mail["wake"] = f"Inspect message {private_message_id}."
        mail["coverage"][0]["wake"] = f"Verify {private_thread_id} before an all-clear."
        mail["category_index"] = {
            category: {
                "total": index + 10,
                "shown": 1,
                "omitted": index + 9,
                "locations_complete": True,
                "signal_ids": [f"signal-{index}"],
            }
            for index, category in enumerate(author.MAIL_ACTION_CATEGORIES)
        }
        for index, category in enumerate(author.MAIL_ACTION_CATEGORIES):
            mail[category] = [
                {
                    "subject": f"Candidate {index}",
                    "last_message_at": "2026-08-15T11:00:00Z",
                    "thread_id": private_thread_id,
                    "last_message_id": private_message_id,
                    "source_threads": [
                        {
                            "acting_email": "trysnowcubes@gmail.com",
                            "thread_id": private_thread_id,
                            "last_message_id": private_message_id,
                        }
                    ],
                    "source_identities": ["trysnowcubes@gmail.com"],
                    "action_tags": ["proactive"],
                    "semantic_status": "PROPOSAL",
                    "confidence": "HIGH",
                    "message_age_hours": 4.0,
                    "proposal": "Consider a personal follow-up.",
                    "wake": f"Open {private_message_id} in the exact account.",
                }
            ]

        evidence = author.build_evidence_projection(source, self.profile)
        populations = [
            row for row in evidence["facts"] if row["kind"] == "mail_population"
        ]
        self.assertEqual(
            {row["fact"]["category"] for row in populations},
            set(author.MAIL_ACTION_CATEGORIES),
        )
        self.assertEqual(len(populations), 5)
        self.assertTrue(
            all(
                set(row["fact"])
                == {"category", "total", "shown", "omitted", "locations_complete"}
                for row in populations
            )
        )
        candidates = [
            row for row in evidence["facts"] if row["kind"] == "mail_candidate"
        ]
        self.assertEqual(len(candidates), 5)
        self.assertTrue(
            all(
                not {"thread_id", "last_message_id", "source_threads"}
                & set(row["fact"])
                for row in candidates
            )
        )
        encoded = json.dumps(evidence, sort_keys=True)
        self.assertNotIn(private_thread_id, encoded)
        self.assertNotIn(private_message_id, encoded)
        self.assertIn("[private mail item]", encoded)

        cited_population = "packet.superhuman.category_index.urgent_replies"
        rendered = author.render_letter_html(
            artifact(evidence, letter(cited_population)),
            self.profile,
        )
        self.assertNotIn(private_thread_id, rendered)
        self.assertNotIn(private_message_id, rendered)

    def test_owner_scheduler_kill_is_pinned_even_when_newer_progress_would_drop_it(
        self,
    ) -> None:
        source = packet()
        source["board"]["entities"][0]["recent_progress"] = [
            "SCHEDULER DISABLED BY LEO -> keep it dead.",
            *[f"newer line {index}" for index in range(12)],
        ]
        evidence = author.build_evidence_projection(source, self.profile)
        progress = [
            row["fact"] for row in evidence["facts"] if row["kind"] == "recent_progress"
        ]
        self.assertIn("SCHEDULER DISABLED BY LEO -> keep it dead.", progress)

    def test_missing_host_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            author.AuthoringError, "deterministic collector cannot author"
        ):
            author.resolve_host(self.profile, None, {})

    def test_unknown_source_reference_rejects_model_result(self) -> None:
        with self.assertRaisesRegex(author.AuthoringError, "unknown evidence"):
            author.validate_letter(letter("made.up.fact"), self.evidence, self.profile)

    def test_reader_rejects_technical_dump_language_and_duplicate_items(self) -> None:
        technical = letter()
        technical["what_matters"][0]["text"] = (
            "The origin/main branch has 174/174 tests."
        )
        with self.assertRaisesRegex(author.AuthoringError, "forbidden reader-body"):
            author.validate_letter(technical, self.evidence, self.profile)
        duplicate = letter()
        duplicate["risks"] = [dict(duplicate["what_matters"][0])]
        with self.assertRaisesRegex(author.AuthoringError, "repeats"):
            author.validate_letter(duplicate, self.evidence, self.profile)

    def test_reader_must_plainly_cite_an_owner_kill_when_present(self) -> None:
        evidence = dict(self.evidence)
        evidence["facts"] = [
            *self.evidence["facts"],
            {
                "ref": "packet.board.entities.0.recent_progress.9",
                "kind": "recent_progress",
                "fact": "SCHEDULER DISABLED BY LEO -> the old report stays off.",
            },
        ]
        omitted = letter()
        with self.assertRaisesRegex(
            author.AuthoringError, "omits controlling evidence"
        ):
            author.validate_letter(omitted, evidence, self.profile)

        obscured = letter("packet.board.entities.0.recent_progress.9")
        with self.assertRaisesRegex(
            author.AuthoringError, "obscures controlling evidence"
        ):
            author.validate_letter(obscured, evidence, self.profile)

        explicit = letter("packet.board.entities.0.recent_progress.9")
        explicit["what_matters"][0]["text"] = (
            "You killed the old report, and it stays off."
        )
        self.assertEqual(
            author.validate_letter(explicit, evidence, self.profile), explicit
        )

    def test_renderer_is_short_responsive_and_hides_exact_evidence_in_appendix(
        self,
    ) -> None:
        rendered = author.render_letter_html(artifact(self.evidence), self.profile)
        self.assertLess(len(rendered), 30_000)
        self.assertIn('name="viewport"', rendered)
        self.assertIn("@media (max-width:520px)", rendered)
        self.assertIn("Private evidence appendix", rendered)
        self.assertNotIn("developer status", rendered)
        self.assertNotIn("~c6sp", rendered)
        self.assertIn("Authored by codex", rendered)

    def test_renderer_rejects_receipt_that_does_not_bind_letter(self) -> None:
        forged = artifact(self.evidence)
        forged["letter"]["verdict"] = "Changed after authoring."
        with self.assertRaisesRegex(author.AuthoringError, "does not bind its letter"):
            author.render_letter_html(forged, self.profile)

    def test_renderer_escapes_model_prose(self) -> None:
        escaped = letter()
        escaped["closing"] = "All boats rise <together>."
        rendered = author.render_letter_html(
            artifact(self.evidence, escaped), self.profile
        )
        self.assertIn("All boats rise &lt;together&gt;.", rendered)
        self.assertNotIn("<together>", rendered)

    @mock.patch.object(author.shutil, "which", return_value="/usr/local/bin/codex")
    def test_codex_success_requires_schema_valid_cited_json(
        self, _which: mock.Mock
    ) -> None:
        def runner(
            command: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            result_path = Path(command[command.index("--output-last-message") + 1])
            result_path.write_text(json.dumps(letter()), encoding="utf-8")
            self.assertIn("--sandbox", command)
            self.assertIn("read-only", command)
            self.assertIn("--ignore-user-config", command)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertIn(
                "Return only the schema-valid JSON letter", str(kwargs["input"])
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        result, receipt = author.invoke_author(
            self.evidence,
            self.profile,
            host="codex",
            runner=runner,
            environ={},
        )
        self.assertEqual(result["schema"], author.LETTER_SCHEMA)
        self.assertEqual(receipt["host"], "codex")
        self.assertEqual(receipt["status"], "ok")

    @mock.patch.object(author.shutil, "which", return_value="/usr/local/bin/claude")
    def test_claude_runs_without_tools_and_no_automatic_host_fallback(
        self, _which: mock.Mock
    ) -> None:
        calls: list[list[str]] = []

        def runner(
            command: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            self.assertIn(
                "Return only the schema-valid JSON letter", str(kwargs["input"])
            )
            self.assertNotIn(
                "Return only the schema-valid JSON letter", " ".join(command)
            )
            envelope = {"structured_output": letter()}
            return subprocess.CompletedProcess(command, 0, json.dumps(envelope), "")

        result, receipt = author.invoke_author(
            self.evidence,
            self.profile,
            host="claude-code",
            runner=runner,
            environ={},
        )
        self.assertEqual(result["schema"], author.LETTER_SCHEMA)
        self.assertEqual(receipt["host"], "claude-code")
        self.assertEqual(len(calls), 1)
        tools_index = calls[0].index("--tools")
        self.assertEqual(calls[0][tools_index + 1], "")

    @mock.patch.object(author.shutil, "which", return_value="/usr/local/bin/codex")
    def test_failed_model_writes_no_success_artifact(self, _which: mock.Mock) -> None:
        def runner(
            command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 9, "", "failed")

        with self.assertRaisesRegex(author.AuthoringError, "no letter emitted"):
            author.invoke_author(
                self.evidence,
                self.profile,
                host="codex",
                runner=runner,
                environ={},
            )

    def test_project_command_writes_private_evidence_without_invoking_a_model(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "source.json"
            output = Path(temp_name) / "evidence.json"
            source.write_text(json.dumps(packet()), encoding="utf-8")
            rc = author.main(
                [
                    "project",
                    "--input",
                    str(source),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                json.loads(output.read_text())["schema"], author.EVIDENCE_SCHEMA
            )

    def test_author_command_without_configured_host_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "source.json"
            output = Path(temp_name) / "letter.json"
            source.write_text(json.dumps(packet()), encoding="utf-8")
            with mock.patch.dict(author.os.environ, {}, clear=True):
                rc = author.main(
                    [
                        "author",
                        "--input",
                        str(source),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(rc, 1)
            self.assertFalse(output.exists())


class SnowcubesCustomerOpportunityAuthorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = author.load_customer_profile()
        self.evidence = project_customer(customer_packet(), self.profile)

    def test_profile_has_no_default_and_pins_exact_business_sources(self) -> None:
        self.assertIsNone(self.profile["default_host"])
        self.assertEqual(
            self.profile["expected_mail_account"], "trysnowcubes@gmail.com"
        )
        self.assertEqual(self.profile["expected_shopify_store"], "939cf1-24")

    def test_projection_keeps_exact_customer_order_thread_and_no_write_receipt(
        self,
    ) -> None:
        self.assertEqual(self.evidence["summary"]["status"], "COMPLETE")
        self.assertEqual(
            self.evidence["summary"]["no_write_receipt"],
            {
                "provider_calls": 0,
                "drafts_created": 0,
                "messages_sent": 0,
                "shopify_mutations": 0,
            },
        )
        refs = {row["ref"] for row in self.evidence["facts"]}
        prefix = "packet.snowcubes_customer_opportunities.opp-1"
        self.assertEqual(
            refs,
            {
                f"{prefix}.customer",
                f"{prefix}.mail",
                f"{prefix}.shopify",
                f"{prefix}.signals",
            },
        )

    def test_identical_duplicates_disappear_and_conflicts_fail_closed(self) -> None:
        source = customer_packet()
        opportunity = source["snowcubes_customer_opportunities"]["opportunities"][0]
        source["snowcubes_customer_opportunities"]["opportunities"].append(
            json.loads(json.dumps(opportunity))
        )
        deduped = project_customer(source, self.profile)
        self.assertEqual(len(deduped["facts"]), 4)

        conflict = json.loads(json.dumps(opportunity))
        conflict["shopify"]["order_id"] = "another-order"
        source["snowcubes_customer_opportunities"]["opportunities"].append(conflict)
        failed = project_customer(source, self.profile)
        self.assertEqual(failed["summary"]["status"], "UNKNOWN")
        self.assertEqual(failed["facts"], [])
        self.assertTrue(
            any(
                "conflicting duplicate" in value
                for value in failed["summary"]["problems"]
            )
        )

    def test_unavailable_shopify_stays_unknown_and_cannot_emit_a_candidate(
        self,
    ) -> None:
        source = customer_packet()
        joined = source["snowcubes_customer_opportunities"]
        joined["status"] = "UNKNOWN"
        joined["source_status"]["shopify"] = "UNAVAILABLE"
        joined["problems"] = ["Shopify order and fulfillment facts are unavailable"]
        evidence = project_customer(source, self.profile)
        self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
        self.assertEqual(evidence["facts"], [])
        unknown = {
            "schema": author.CUSTOMER_LETTER_SCHEMA,
            "status": "UNKNOWN",
            "ranked_opportunities": [],
            "exact_wake": "Authorize the exact read-only Shopify store adapter and re-read the order.",
        }
        self.assertEqual(
            author.validate_customer_letter(unknown, evidence, self.profile), unknown
        )
        with self.assertRaisesRegex(author.AuthoringError, "empty UNKNOWN"):
            author.validate_customer_letter(customer_letter(), evidence, self.profile)

    def test_wrong_mail_account_or_store_fails_closed_in_the_projection(self) -> None:
        for path, value in (
            (("mail", "provider_key"), "superhuman:leojkwan@gmail.com:thread-7"),
            (
                ("mail", "provider_key"),
                "superhuman:trysnowcubes@gmail.com:another-thread",
            ),
            (("shopify", "provider_key"), "shopify:another-store:order-9"),
            (("shopify", "provider_key"), "shopify:939cf1-24:another-order"),
        ):
            source = customer_packet()
            row = source["snowcubes_customer_opportunities"]["opportunities"][0]
            row[path[0]][path[1]] = value
            evidence = project_customer(source, self.profile)
            self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
            self.assertEqual(evidence["facts"], [])
            self.assertTrue(
                any(
                    "not an exact two-source join" in problem
                    for problem in evidence["summary"]["problems"]
                )
            )

    def test_reused_provider_identity_or_cross_customer_order_fails_closed(
        self,
    ) -> None:
        source = customer_packet()
        first = source["snowcubes_customer_opportunities"]["opportunities"][0]
        second = json.loads(json.dumps(first))
        second["opportunity_id"] = "opp-2"
        second["customer_identity"]["shopify_customer_id"] = "gid://shopify/Customer/8"
        second["shopify"]["shopify_customer_id"] = "gid://shopify/Customer/8"
        second["shopify"]["order_id"] = "order-10"
        second["shopify"]["provider_key"] = "shopify:939cf1-24:order-10"
        source["snowcubes_customer_opportunities"]["opportunities"].append(second)
        evidence = project_customer(source, self.profile)
        self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
        self.assertEqual(evidence["facts"], [])
        self.assertTrue(
            any(
                "reused across rows" in value
                for value in evidence["summary"]["problems"]
            )
        )

        mismatch = customer_packet()
        mismatch["snowcubes_customer_opportunities"]["opportunities"][0]["shopify"][
            "shopify_customer_id"
        ] = "gid://shopify/Customer/8"
        evidence = project_customer(mismatch, self.profile)
        self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
        self.assertEqual(evidence["facts"], [])

    def test_stale_future_or_invalid_source_observation_fails_closed(self) -> None:
        for observed_at in (
            "2026-08-13T12:00:00Z",
            "2026-08-16T12:00:00Z",
            "not-a-time",
        ):
            source = customer_packet()
            source["snowcubes_customer_opportunities"]["observed_at"] = observed_at
            evidence = project_customer(source, self.profile)
            self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
            self.assertEqual(evidence["facts"], [])

        old = customer_packet()
        old["generated_at"] = "2025-08-15T09:00:00-04:00"
        old["snowcubes_customer_opportunities"]["observed_at"] = "2025-08-15T13:00:00Z"
        evidence = author.build_customer_evidence_projection(
            old,
            self.profile,
            now=author.datetime.fromisoformat("2026-08-15T13:00:00+00:00"),
        )
        self.assertEqual(evidence["summary"]["status"], "UNKNOWN")

        malformed = customer_packet()
        malformed["generated_at"] = "not-a-time"
        evidence = author.build_customer_evidence_projection(
            malformed,
            self.profile,
            now=author.datetime.fromisoformat("2026-08-15T13:00:00+00:00"),
        )
        self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
        self.assertEqual(evidence["facts"], [])

    def test_guessed_match_email_mismatch_or_future_row_time_fails_closed(self) -> None:
        mutations = (
            lambda row: row.update(match_basis="subject_line_guess"),
            lambda row: row["customer_identity"].update(
                customer_email="other-customer@example.com"
            ),
            lambda row: row["mail"].update(observed_at="2026-08-16T12:00:00Z"),
        )
        for mutate in mutations:
            source = customer_packet()
            mutate(source["snowcubes_customer_opportunities"]["opportunities"][0])
            evidence = project_customer(source, self.profile)
            self.assertEqual(evidence["summary"]["status"], "UNKNOWN")
            self.assertEqual(evidence["facts"], [])

    def test_exact_provenance_survives_and_cross_customer_or_draft_prose_is_rejected(
        self,
    ) -> None:
        value = customer_letter()
        self.assertEqual(
            author.validate_customer_letter(value, self.evidence, self.profile), value
        )
        forged = json.loads(json.dumps(value))
        forged["ranked_opportunities"][0]["customer_order_thread_provenance"][2][
            "provider_id"
        ] = "made-up-thread"
        with self.assertRaisesRegex(author.AuthoringError, "not exact evidence"):
            author.validate_customer_letter(forged, self.evidence, self.profile)
        drafted = json.loads(json.dumps(value))
        drafted["ranked_opportunities"][0]["draft_ready_factual_context"][0]["text"] = (
            "Hi Alice, your order arrived!"
        )
        with self.assertRaisesRegex(author.AuthoringError, "contains draft prose"):
            author.validate_customer_letter(drafted, self.evidence, self.profile)
        protected = json.loads(json.dumps(value))
        protected["ranked_opportunities"][0]["recommended_next_step"]["text"] = (
            "Review the facts, then send the customer an arrival email."
        )
        with self.assertRaisesRegex(author.AuthoringError, "protected boundary"):
            author.validate_customer_letter(protected, self.evidence, self.profile)
        protected_why = json.loads(json.dumps(value))
        protected_why["ranked_opportunities"][0]["why_now"]["text"] = (
            "Send this customer a message now."
        )
        with self.assertRaisesRegex(author.AuthoringError, "protected boundary"):
            author.validate_customer_letter(protected_why, self.evidence, self.profile)

    def test_unknown_wake_cannot_smuggle_a_protected_action(self) -> None:
        source = customer_packet()
        source["snowcubes_customer_opportunities"]["status"] = "UNKNOWN"
        source["snowcubes_customer_opportunities"]["source_status"]["shopify"] = (
            "UNAVAILABLE"
        )
        source["snowcubes_customer_opportunities"]["problems"] = ["Shopify unavailable"]
        evidence = project_customer(source, self.profile)
        value = {
            "schema": author.CUSTOMER_LETTER_SCHEMA,
            "status": "UNKNOWN",
            "ranked_opportunities": [],
            "exact_wake": "Read Shopify, then send a draft now.",
        }
        with self.assertRaisesRegex(author.AuthoringError, "protected boundary"):
            author.validate_customer_letter(value, evidence, self.profile)
        value["exact_wake"] = "Re-read the calendar account."
        with self.assertRaisesRegex(
            author.AuthoringError, "does not name missing shopify"
        ):
            author.validate_customer_letter(value, evidence, self.profile)

    def test_renderer_is_separate_private_responsive_and_not_a_mail_draft(self) -> None:
        rendered = author.render_customer_letter_html(
            customer_artifact(self.evidence), self.profile
        )
        self.assertIn("Snowcubes customer opportunities", rendered)
        self.assertIn("No draft or send", rendered)
        self.assertIn('name="viewport"', rendered)
        self.assertIn("@media (max-width:520px)", rendered)
        self.assertIn("Customer · order · thread", rendered)
        self.assertNotIn("Chief-of-staff brief", rendered)
        self.assertNotIn("Hi Alice", rendered)

    def test_customer_artifact_rejects_unapproved_host_or_tool_receipt(self) -> None:
        forged = customer_artifact(self.evidence)
        forged["author_receipt"]["host"] = "mail-writer"
        with self.assertRaisesRegex(author.AuthoringError, "unsupported host"):
            author.validate_customer_artifact(forged, self.profile)
        forged = customer_artifact(self.evidence)
        forged["author_receipt"]["tools_allowed"] = True
        with self.assertRaisesRegex(author.AuthoringError, "tool isolation"):
            author.validate_customer_artifact(forged, self.profile)

    def test_customer_artifact_rejects_stale_evidence(self) -> None:
        stale = json.loads(json.dumps(self.evidence))
        stale["generated_at"] = "2025-08-15T13:00:00Z"
        forged = customer_artifact(stale)
        with self.assertRaisesRegex(author.AuthoringError, "evidence is stale"):
            author.validate_customer_artifact(forged, self.profile)

    @mock.patch.object(author.shutil, "which", return_value="/usr/local/bin/codex")
    def test_customer_codex_runs_read_only_with_its_own_schema(
        self, _which: mock.Mock
    ) -> None:
        def runner(
            command: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            result_path = Path(command[command.index("--output-last-message") + 1])
            result_path.write_text(json.dumps(customer_letter()), encoding="utf-8")
            schema_path = command[command.index("--output-schema") + 1]
            self.assertTrue(
                schema_path.endswith("snowcubes-customer-opportunity-letter.v1.json")
            )
            self.assertIn("--sandbox", command)
            self.assertIn("read-only", command)
            self.assertIn("customer-opportunity brief", str(kwargs["input"]))
            return subprocess.CompletedProcess(command, 0, "", "")

        result, receipt = author.invoke_customer_author(
            self.evidence,
            self.profile,
            host="codex",
            runner=runner,
            environ={},
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(receipt["schema"], author.CUSTOMER_RECEIPT_SCHEMA)

    def test_customer_author_without_configured_host_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "source.json"
            output = Path(temp_name) / "opportunities.json"
            source.write_text(json.dumps(customer_packet()), encoding="utf-8")
            with mock.patch.dict(author.os.environ, {}, clear=True):
                rc = author.main(
                    [
                        "customer-author",
                        "--input",
                        str(source),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(rc, 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
