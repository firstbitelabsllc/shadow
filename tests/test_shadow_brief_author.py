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
        "what_matters": [{"text": "The deterministic producer is gone.", "source_refs": [ref]}],
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


class ChiefOfStaffAuthorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = author.load_profile()
        self.evidence = author.build_evidence_projection(packet(), self.profile)

    def test_profile_has_no_default_author_and_keeps_three_expected_identities(self) -> None:
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

    def test_projection_is_bounded_and_excludes_deterministic_analysis_prose(self) -> None:
        source = packet()
        source["analysis"] = {"executive_read": "This renderer thinks for Leo."}
        source["board"]["entities"] = source["board"]["entities"] * 100
        source["board"]["entities"][0]["recent_progress"] = ["x" * 5000] * 100
        evidence = author.build_evidence_projection(source, self.profile)
        encoded = json.dumps(evidence)
        self.assertNotIn("This renderer thinks for Leo", encoded)
        self.assertEqual(evidence["schema"], author.EVIDENCE_SCHEMA)
        self.assertTrue(all(set(row) == {"ref", "kind", "fact"} for row in evidence["facts"]))
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

    def test_owner_scheduler_kill_is_pinned_even_when_newer_progress_would_drop_it(self) -> None:
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
        with self.assertRaisesRegex(author.AuthoringError, "deterministic collector cannot author"):
            author.resolve_host(self.profile, None, {})

    def test_unknown_source_reference_rejects_model_result(self) -> None:
        with self.assertRaisesRegex(author.AuthoringError, "unknown evidence"):
            author.validate_letter(letter("made.up.fact"), self.evidence, self.profile)

    def test_reader_rejects_technical_dump_language_and_duplicate_items(self) -> None:
        technical = letter()
        technical["what_matters"][0]["text"] = "The origin/main branch has 174/174 tests."
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
        with self.assertRaisesRegex(author.AuthoringError, "omits controlling evidence"):
            author.validate_letter(omitted, evidence, self.profile)

        obscured = letter("packet.board.entities.0.recent_progress.9")
        with self.assertRaisesRegex(author.AuthoringError, "obscures controlling evidence"):
            author.validate_letter(obscured, evidence, self.profile)

        explicit = letter("packet.board.entities.0.recent_progress.9")
        explicit["what_matters"][0]["text"] = "You killed the old report, and it stays off."
        self.assertEqual(author.validate_letter(explicit, evidence, self.profile), explicit)

    def test_renderer_is_short_responsive_and_hides_exact_evidence_in_appendix(self) -> None:
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
        rendered = author.render_letter_html(artifact(self.evidence, escaped), self.profile)
        self.assertIn("All boats rise &lt;together&gt;.", rendered)
        self.assertNotIn("<together>", rendered)

    @mock.patch.object(author.shutil, "which", return_value="/usr/local/bin/codex")
    def test_codex_success_requires_schema_valid_cited_json(self, _which: mock.Mock) -> None:
        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            result_path = Path(command[command.index("--output-last-message") + 1])
            result_path.write_text(json.dumps(letter()), encoding="utf-8")
            self.assertIn("--sandbox", command)
            self.assertIn("read-only", command)
            self.assertIn("--ignore-user-config", command)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertIn("Return only the schema-valid JSON letter", str(kwargs["input"]))
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
    def test_claude_runs_without_tools_and_no_automatic_host_fallback(self, _which: mock.Mock) -> None:
        calls: list[list[str]] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            self.assertIn("Return only the schema-valid JSON letter", str(kwargs["input"]))
            self.assertNotIn("Return only the schema-valid JSON letter", " ".join(command))
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
        def runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 9, "", "failed")

        with self.assertRaisesRegex(author.AuthoringError, "no letter emitted"):
            author.invoke_author(
                self.evidence,
                self.profile,
                host="codex",
                runner=runner,
                environ={},
            )

    def test_project_command_writes_private_evidence_without_invoking_a_model(self) -> None:
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
            self.assertEqual(json.loads(output.read_text())["schema"], author.EVIDENCE_SCHEMA)

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


if __name__ == "__main__":
    unittest.main()
