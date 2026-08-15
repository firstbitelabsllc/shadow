"""Contract checks for the private, single-path Shadow brief producer."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import plistlib
import stat
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

_TEST_SOURCE_COMMIT = subprocess.run(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()
_TEST_SCRIPT_SHA256 = hashlib.sha256(Path(brief.__file__).read_bytes()).hexdigest()


def _m5_producer_fixture() -> dict[str, object]:
    return {
        "schema": "shadow.brief-producer.v1",
        "source_commit": _TEST_SOURCE_COMMIT,
        "script_sha256": _TEST_SCRIPT_SHA256,
        "source_matches_commit": True,
    }


def _m5_mail_fixture(*, include_action: bool = True) -> dict[str, object]:
    expected_identities = [
        "leojkwan@gmail.com",
        "trysnowcubes@gmail.com",
        "firstbitelabs@gmail.com",
    ]
    coverage = [
        {
            "acting_email": "leojkwan@gmail.com",
            "expected": True,
            "linked": True,
            "status": "COMPLETE",
            "pagination": {"pages": 1, "exhausted": True, "truncated": False},
        },
        {
            "acting_email": "trysnowcubes@gmail.com",
            "expected": True,
            "linked": True,
            "status": "COMPLETE",
            "pagination": {"pages": 1, "exhausted": True, "truncated": False},
        },
        {
            "acting_email": "firstbitelabs@gmail.com",
            "expected": True,
            "linked": False,
            "status": "UNKNOWN",
            "pagination": {"pages": 0, "exhausted": False, "truncated": True},
            "problems": ["expected identity is not linked"],
            "wake": "Link firstbitelabs@gmail.com in Superhuman and rerun the read-only scan.",
        },
    ]
    action = {
        "signal_id": "mail-action-1",
        "thread_id": "thread-action-1",
        "last_message_id": "message-action-1",
        "stable_provider_identity": True,
        "thread_body_read": True,
        "action_tags": ["reply", "urgent"],
        "semantic_status": "PROPOSAL",
        "subject": "Reply requested before Friday",
        "proposal": "Proposal only: review the exact reply before any send.",
        "proposal_only": True,
        "source_identities": ["leojkwan@gmail.com"],
    }
    actions = [action] if include_action else []
    return {
        "schema": "shadow.superhuman-context.v2",
        "available": True,
        "complete": False,
        "status": "UNKNOWN",
        "all_clear_allowed": False,
        "expected_identities": expected_identities,
        "account_discovery": {
            "status": "COMPLETE",
            "malformed_rows": 0,
            "wake": None,
        },
        "linked_accounts": [
            {
                "acting_email": "leojkwan@gmail.com",
                "is_primary": True,
                "added_at": "2026-01-01T00:00:00Z",
                "sender_identities": ["leojkwan@gmail.com"],
                "sender_identity_complete": True,
            },
            {
                "acting_email": "trysnowcubes@gmail.com",
                "is_primary": False,
                "added_at": "2026-01-02T00:00:00Z",
                "sender_identities": ["trysnowcubes@gmail.com"],
                "sender_identity_complete": True,
            },
        ],
        "coverage": coverage,
        "signals": actions,
        "urgent_replies": actions,
        "waiting_replies": [],
        "forgotten_obligations": [],
        "order_return_follow_up": [],
        "proactive_candidates": [],
        "calendar_proposals": [],
    }


def _m5_html_fixture(row: dict[str, object]) -> str:
    generated = brief.datetime.fromisoformat(str(row["generated_at"]))
    month_day = generated.strftime("%b %d").replace(" 0", " ")
    hour = generated.strftime("%I").lstrip("0") or "12"
    reader_time = (
        f"{month_day} · {hour}:{generated.strftime('%M')} "
        f"{generated.strftime('%p')}"
    )
    return f"""<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width"/></head><body>
<!-- private machine identity: board rev {row['board_revision']} -->
<h1>Today’s read</h1>
<p class="stamp">{str(row['slot']).title()} note · twice-daily · {reader_time}</p>
<section><h2>What materially changed</h2></section>
<section><h2>The chief-of-staff read</h2></section>
<section><h2>Decided for you</h2></section>
<section><h2>Needs Leo now</h2></section>
<section><h2>Mail and calendar coverage</h2></section>
<section><h2>Architecture decisions you need to know about</h2></section>
<section><h2>Questions to challenge your point of view</h2></section>
<section><h2>Completion outlook</h2></section>
<section><h2>Lanes losing momentum — and how to improve them</h2></section>
<section><h2>Snowcubes in the portfolio</h2></section>
<section><h2>Evidence and blind spots</h2></section>
<footer>Supporting checks inform the note; they do not create another to-do list.</footer>
</body></html>
"""


def _write_m5_window_fixture(
    evidence_dir: Path,
    *,
    scheduled_for: str,
    generated_at: str,
    sent_at: str,
    slot: str,
    stamp: str,
    ledger_dir: Path | None = None,
    send_attempt_log: Path | None = None,
) -> dict[str, object]:
    ledger = ledger_dir or evidence_dir / "ledger"
    attempts = send_attempt_log or ledger / "send-attempts.jsonl"
    producer = _m5_producer_fixture()
    paint_health = {
        "local_git": {"available": True},
        "github": {"available": True},
        "vercel": {"available": True},
    }
    row: dict[str, object] = {
        "schema": "shadow.bidaily-window.v4",
        "on_schedule": True,
        "trigger": "launchd-calendar",
        "slot": slot,
        "scheduled_for": scheduled_for,
        "generated_at": generated_at,
        "board_revision": 41,
        "trigger_proof": {
            "is_launchd": True,
            "parent_pid": 1,
            "parent_command": "/sbin/launchd",
            "label": "com.leokwan.shadow-bidaily-brief",
            "domain": f"gui/{os.getuid()}",
            "current_pid": 4242,
            "job_pid": 4242,
            "xpc_service_name": "com.leokwan.shadow-bidaily-brief",
            "service_matches_label": True,
            "loaded_program": brief.launch_agent_plist(Path(brief.__file__).resolve())[
                "ProgramArguments"
            ][0],
            "loaded_program_arguments": brief.launch_agent_plist(
                Path(brief.__file__).resolve()
            )["ProgramArguments"],
            "loaded_path": str(
                Path.home() / "Library" / "LaunchAgents" / f"{brief.LABEL}.plist"
            ),
            "loaded_command_matches": True,
            "exact_job": True,
        },
        "notification": {
            "status": "ok",
            "title": "Shadow brief ready",
            "body": f"{slot} · board rev 41",
        },
        "paint_health": paint_health,
        "producer": producer,
        "receipt": {
            "status": "ok",
            "delivery_status": "sent",
            "message_id": f"message-{stamp}",
            "thread_id": f"thread-{stamp}",
            "draft_id": f"draft-{stamp}",
            "attempt_state": "PROVISIONAL_SENT",
            "attempt_id": None,
            "acting_email": "leojkwan@gmail.com",
            "from": "leojkwan@gmail.com",
            "to": ["leojkwan@gmail.com"],
            "subject": f"Shadow {slot} brief — {generated_at}",
            "sent_at": sent_at,
            "local_html": str(evidence_dir / f"brief-{stamp}.html"),
        },
    }
    html_path = evidence_dir / f"brief-{stamp}.html"
    json_path = evidence_dir / f"brief-{stamp}.json"
    packet = {
        "generated_at": generated_at,
        "slot": slot,
        "board": {"revision": 41},
        "authority": {
            "board_snapshot": {"consistent": True, "revision": 41},
        },
        "paint_health": paint_health,
        "superhuman_context": _m5_mail_fixture(),
        "producer": producer,
    }
    html_bytes = _m5_html_fixture(row).encode("utf-8")
    json_bytes = (json.dumps(packet, indent=2) + "\n").encode("utf-8")
    html_path.write_bytes(html_bytes)
    json_path.write_bytes(json_bytes)
    html_path.chmod(0o400)
    json_path.chmod(0o400)
    barrier_path = ledger / f"scheduled-attempt-{stamp}.json"
    barrier_path.parent.mkdir(parents=True, exist_ok=True)
    barrier_path.write_text(
        json.dumps(
            {
                "schema": brief.SCHEDULED_ATTEMPT_SCHEMA,
                "state": "RESERVED",
                "scheduled_for": scheduled_for,
                "slot": slot,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    barrier_path.chmod(0o400)
    attempts.parent.mkdir(parents=True, exist_ok=True)
    intent = {
        "schema": "shadow.superhuman-send-attempt.v1",
        "state": "UNKNOWN_NO_RETRY",
        "created_at": generated_at,
        "acting_email": brief.SELF_MAIL,
        "from": brief.SELF_MAIL,
        "to": [brief.SELF_MAIL],
        "subject": row["receipt"]["subject"],
        "draft_id": row["receipt"]["draft_id"],
        "thread_id": row["receipt"]["thread_id"],
        "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
    }
    intent["attempt_id"] = hashlib.sha256(
        json.dumps(intent, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    row["receipt"]["attempt_id"] = intent["attempt_id"]
    outcome = {
        "schema": "shadow.superhuman-send-attempt.v1",
        "state": "PROVISIONAL_SENT",
        "recorded_at": sent_at,
        "attempt_id": intent["attempt_id"],
        "message_id": row["receipt"]["message_id"],
        "thread_id": row["receipt"]["thread_id"],
        "sent_at": sent_at,
    }
    with attempts.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(intent, sort_keys=True) + "\n"
        )
        handle.write(
            json.dumps(outcome, sort_keys=True) + "\n"
        )
    attempts.chmod(0o600)
    row.update(
        {
            "archive_html": str(html_path),
            "archive_json": str(json_path),
            "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
            "json_sha256": hashlib.sha256(json_bytes).hexdigest(),
            "attempt_barrier": {
                "path": str(barrier_path),
                "state": "PRESENT",
            },
        }
    )
    return row


def _write_m5_pair(
    evidence_dir: Path,
    ledger_dir: Path | None = None,
    send_attempt_log: Path | None = None,
) -> list[dict[str, object]]:
    ledger = ledger_dir or evidence_dir / "ledger"
    return [
        _write_m5_window_fixture(
            evidence_dir,
            scheduled_for="2026-08-12T08:00:00-04:00",
            generated_at="2026-08-12T08:05:00-04:00",
            sent_at="2026-08-12T08:06:00-04:00",
            slot="morning",
            stamp="20260812-080000",
            ledger_dir=ledger,
            send_attempt_log=send_attempt_log,
        ),
        _write_m5_window_fixture(
            evidence_dir,
            scheduled_for="2026-08-12T20:00:00-04:00",
            generated_at="2026-08-12T20:05:00-04:00",
            sent_at="2026-08-12T20:06:00-04:00",
            slot="evening",
            stamp="20260812-200000",
            ledger_dir=ledger,
            send_attempt_log=send_attempt_log,
        ),
    ]


def _scheduled_proof_fixture() -> dict[str, object]:
    expected_arguments = brief.launch_agent_plist(Path(brief.__file__).resolve())[
        "ProgramArguments"
    ]
    return {
        "is_launchd": True,
        "parent_pid": 1,
        "parent_command": "/sbin/launchd",
        "label": brief.LABEL,
        "domain": f"gui/{os.getuid()}",
        "current_pid": os.getpid(),
        "job_pid": os.getpid(),
        "xpc_service_name": brief.LABEL,
        "service_matches_label": True,
        "loaded_program": expected_arguments[0],
        "loaded_program_arguments": expected_arguments,
        "loaded_path": str(
            Path.home() / "Library" / "LaunchAgents" / f"{brief.LABEL}.plist"
        ),
        "loaded_command_matches": True,
        "exact_job": True,
    }


def _scheduled_window_fixture() -> dict[str, object]:
    return {
        "on_schedule": True,
        "slot": "morning",
        "scheduled_for": "2026-08-12T08:00:00-04:00",
    }


def _scheduled_packet_fixture(
    *,
    generated_at: str = "2026-08-12T08:05:00-04:00",
    consistent: bool = True,
    producer: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "generated_at": generated_at,
        "slot": "morning",
        "board": {"revision": 41, "entities": [], "claims": []},
        "authority": {
            "board_snapshot": {"consistent": consistent, "revision": 41}
        },
        "paint_health": {},
        "producer": producer if producer is not None else _m5_producer_fixture(),
        "superhuman_context": _m5_mail_fixture(),
        "repos": [],
        "github_open_prs": [],
        "recommendations": [],
        "analysis": {},
        "snowcubes_context": {"surfaces": []},
    }


def _rewrite_m5_packet(row: dict[str, object], mutate) -> None:
    path = Path(str(row["archive_json"]))
    path.chmod(0o600)
    packet = json.loads(path.read_text(encoding="utf-8"))
    mutate(packet)
    rendered = (json.dumps(packet, indent=2) + "\n").encode("utf-8")
    path.write_bytes(rendered)
    path.chmod(0o400)
    row["json_sha256"] = hashlib.sha256(rendered).hexdigest()


def _replace_m5_packet(row: dict[str, object], packet: object) -> None:
    path = Path(str(row["archive_json"]))
    path.chmod(0o600)
    rendered = (json.dumps(packet, indent=2) + "\n").encode("utf-8")
    path.write_bytes(rendered)
    path.chmod(0o400)
    row["json_sha256"] = hashlib.sha256(rendered).hexdigest()


def _rewrite_m5_html(row: dict[str, object], mutate) -> None:
    path = Path(str(row["archive_html"]))
    path.chmod(0o600)
    rendered = mutate(path.read_text(encoding="utf-8")).encode("utf-8")
    path.write_bytes(rendered)
    path.chmod(0o400)
    row["html_sha256"] = hashlib.sha256(rendered).hexdigest()


class PrivateStoreTests(unittest.TestCase):
    def test_new_private_jsonl_entry_fsyncs_parent_and_preserves_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger" / "events.jsonl"
            real_fsync = os.fsync
            synced_kinds: list[str] = []

            def observe_fsync(descriptor):
                mode = os.fstat(descriptor).st_mode
                synced_kinds.append(
                    "directory" if stat.S_ISDIR(mode) else "file"
                )
                return real_fsync(descriptor)

            with mock.patch.object(
                brief.os,
                "fsync",
                side_effect=observe_fsync,
            ):
                brief._append_private_jsonl(path, {"sequence": 1})
                first_append_kinds = list(synced_kinds)
                brief._append_private_jsonl(path, {"sequence": 2})

            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            file_mode = stat.S_IMODE(path.stat().st_mode)

        self.assertIn("file", first_append_kinds)
        self.assertIn("directory", first_append_kinds)
        self.assertEqual(rows, [{"sequence": 1}, {"sequence": 2}])
        self.assertEqual(file_mode, 0o600)

    def test_private_jsonl_rejects_symlink_and_hardlink_targets(self):
        for link_kind in ("symlink", "hardlink"):
            with self.subTest(link_kind=link_kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                ledger = root / "ledger"
                ledger.mkdir()
                target = root / "unrelated.txt"
                target.write_text("do not mutate\n", encoding="utf-8")
                target.chmod(0o640)
                path = ledger / "events.jsonl"
                if link_kind == "symlink":
                    path.symlink_to(target)
                else:
                    os.link(target, path)
                before = target.read_bytes()
                before_mode = stat.S_IMODE(target.stat().st_mode)

                with self.assertRaises(OSError):
                    brief._append_private_jsonl(path, {"must": "not append"})

                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), before_mode)

    def test_private_jsonl_opens_nonblocking_before_fifo_shape_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            os.mkfifo(path, 0o600)
            real_open = os.open

            def require_nonblocking(candidate, flags, mode=0o777):
                self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(candidate, flags, mode)

            with mock.patch.object(
                brief.os,
                "open",
                side_effect=require_nonblocking,
            ), self.assertRaises(OSError):
                brief._append_private_jsonl(path, {"must": "not block"})

    def test_private_jsonl_reader_accepts_only_safe_complete_object_ledgers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "valid.jsonl"
            valid.write_text(
                '\n{"sequence": 1}\n{"sequence": 2}\n',
                encoding="utf-8",
            )
            valid.chmod(0o600)

            self.assertEqual(
                brief._read_jsonl(valid),
                [{"sequence": 1}, {"sequence": 2}],
            )
            self.assertEqual(brief._read_jsonl(root / "missing.jsonl"), [])

    def test_private_jsonl_reader_rejects_unsafe_or_corrupt_existing_ledgers(self):
        cases = (
            "symlink",
            "hardlink",
            "fifo",
            "mode",
            "invalid-json",
            "excessive-nesting",
            "nonobject",
            "invalid-utf8",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "events.jsonl"
                if case in {"symlink", "hardlink"}:
                    target = root / "target.jsonl"
                    target.write_text('{"safe": true}\n', encoding="utf-8")
                    target.chmod(0o600)
                    if case == "symlink":
                        path.symlink_to(target)
                    else:
                        os.link(target, path)
                elif case == "fifo":
                    os.mkfifo(path, 0o600)
                elif case == "mode":
                    path.write_text('{"safe": true}\n', encoding="utf-8")
                    path.chmod(0o644)
                elif case == "invalid-json":
                    path.write_text('{"truncated":\n', encoding="utf-8")
                    path.chmod(0o600)
                elif case == "excessive-nesting":
                    path.write_text(
                        "[" * 2_000 + "0" + "]" * 2_000 + "\n",
                        encoding="utf-8",
                    )
                    path.chmod(0o600)
                elif case == "nonobject":
                    path.write_text('["not", "an", "object"]\n', encoding="utf-8")
                    path.chmod(0o600)
                else:
                    path.write_bytes(b"\xff\n")
                    path.chmod(0o600)

                try:
                    brief._read_jsonl(path)
                except OSError as exc:
                    self.assertIn(str(path), str(exc))
                except UnicodeError as exc:
                    self.fail(f"Unicode error was not structured for {path}: {exc}")
                except RecursionError as exc:
                    self.fail(f"recursive JSON error was not structured for {path}: {exc}")
                else:
                    self.fail(f"unsafe or corrupt ledger was accepted: {case}")

    def test_private_jsonl_reader_structures_json_recursion_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"deeply": "nested"}\n', encoding="utf-8")
            path.chmod(0o600)

            with mock.patch.object(
                brief.json,
                "loads",
                side_effect=RecursionError("maximum nesting exceeded"),
            ), self.assertRaises(brief.PrivateJSONLError) as raised:
                brief._read_jsonl(path)

            self.assertIn("invalid JSON on line 1", str(raised.exception))

    def test_private_jsonl_reader_structures_integer_limit_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(
                '{"oversized": ' + "9" * 5_000 + "}\n",
                encoding="utf-8",
            )
            path.chmod(0o600)

            try:
                brief._read_jsonl(path)
            except brief.PrivateJSONLError as exc:
                self.assertIn("invalid JSON on line 1", str(exc))
            except ValueError as exc:
                self.fail(f"integer-limit JSON error was not structured: {exc}")
            else:
                self.fail("oversized JSON integer ledger was accepted")

    def test_record_send_attempt_rejects_corrupt_ledger_before_append(self):
        corrupt_payloads = (
            b'{"truncated":\n',
            b"\xff\xfe\x00",
        )
        for payload in corrupt_payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                html_path = root / "brief.html"
                html_path.write_text("<p>scheduled brief</p>", encoding="utf-8")
                attempt_log = root / "send-attempts.jsonl"
                attempt_log.write_bytes(payload)
                attempt_log.chmod(0o600)
                append = mock.Mock()

                with mock.patch.object(
                    brief,
                    "SEND_ATTEMPT_LOG",
                    attempt_log,
                ), mock.patch.object(
                    brief,
                    "_append_private_jsonl",
                    append,
                ), self.assertRaises(brief.PrivateJSONLError):
                    brief.record_send_attempt(
                        html_path,
                        subject="Shadow morning brief",
                        draft_id="draft-before-send",
                        thread_id="thread-before-send",
                    )

                self.assertEqual(attempt_log.read_bytes(), payload)
                append.assert_not_called()

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

    def test_mail_coverage_discovers_linked_accounts_and_keeps_missing_expected_identity_unknown(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        list_thread_identities = []

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {
                            "accountEmail": "leojkwan@gmail.com",
                            "addedAt": "2026-01-01T00:00:00Z",
                            "isPrimary": True,
                        },
                        {
                            "accountEmail": "trysnowcubes@gmail.com",
                            "addedAt": "2026-01-02T00:00:00Z",
                            "isPrimary": False,
                        },
                        {
                            "accountEmail": "newly-linked@example.com",
                            "addedAt": "2026-08-14T00:00:00Z",
                            "isPrimary": False,
                        },
                    ]
                }
            if name == "list_threads":
                list_thread_identities.append(arguments["acting_email"])
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                return {"answer": "No calendar conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        coverage = {row["acting_email"]: row for row in context["coverage"]}
        self.assertEqual(
            set(coverage),
            {
                "leojkwan@gmail.com",
                "trysnowcubes@gmail.com",
                "firstbitelabs@gmail.com",
                "newly-linked@example.com",
            },
        )
        self.assertEqual(coverage["leojkwan@gmail.com"]["status"], "COMPLETE")
        self.assertEqual(coverage["trysnowcubes@gmail.com"]["status"], "COMPLETE")
        self.assertEqual(coverage["firstbitelabs@gmail.com"]["status"], "UNKNOWN")
        self.assertEqual(coverage["newly-linked@example.com"]["status"], "COMPLETE")
        self.assertEqual(
            set(list_thread_identities),
            {
                "leojkwan@gmail.com",
                "trysnowcubes@gmail.com",
                "newly-linked@example.com",
            },
        )
        self.assertIn(
            "Link firstbitelabs@gmail.com in Superhuman",
            coverage["firstbitelabs@gmail.com"]["wake"],
        )
        self.assertFalse(context["all_clear_allowed"])
        self.assertEqual(context["status"], "UNKNOWN")

    def test_forgotten_horizon_clears_only_after_each_expected_active_inbox_exhausts(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        horizon_calls = []

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []} for email in identities
                    ]
                }
            if name == "list_threads":
                if "start_date" not in arguments:
                    horizon_calls.append(dict(arguments))
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                return {
                    "answer": "No conflict surfaced.",
                    "sources": [{"id": "calendar-source"}],
                }
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        self.assertEqual(len(horizon_calls), len(identities))
        self.assertTrue(
            all(call["sort"] == "oldest" for call in horizon_calls)
        )
        self.assertTrue(
            all(call["labels"] == ["INBOX"] for call in horizon_calls)
        )
        self.assertEqual(context["forgotten_horizon"]["status"], "COMPLETE")
        self.assertTrue(context["complete"])
        self.assertTrue(context["all_clear_allowed"])

    def test_forgotten_horizon_stays_unknown_when_a_cursor_cannot_exhaust(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []} for email in identities
                    ]
                }
            if name == "list_threads":
                if (
                    "start_date" not in arguments
                    and arguments["acting_email"] == identities[0]
                ):
                    return {"threads": [], "next_cursor": "stuck", "total_estimate": 0}
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                return {
                    "answer": "No conflict surfaced.",
                    "sources": [{"id": "calendar-source"}],
                }
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        self.assertEqual(context["forgotten_horizon"]["status"], "UNKNOWN")
        self.assertFalse(context["complete"])
        self.assertFalse(context["all_clear_allowed"])
        self.assertIn("not proven exhaustive", " ".join(context["problems"]))
        self.assertIn("no action was performed", context["forgotten_horizon"]["wake"])

    def test_mail_coverage_exhausts_pages_and_deduplicates_actions_across_accounts(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        linked = ("leojkwan@gmail.com", "trysnowcubes@gmail.com")

        def thread(*, thread_id, message_id, subject, sent_at):
            return {
                "thread_id": thread_id,
                "last_message_id": message_id,
                "last_message_at": sent_at,
                "message_count": 1,
                "subject": subject,
                "snippet": subject,
                "participants": ["merchant@example.com"],
                "labels": ["INBOX", "UNREAD"],
            }

        shared_personal = thread(
            thread_id="thread-personal-shared",
            message_id="shared-message",
            subject="Order return deadline",
            sent_at="2026-08-14T10:00:00Z",
        )
        shared_snowcubes = {**shared_personal, "thread_id": "thread-snow-shared"}
        license_notice = thread(
            thread_id="thread-license",
            message_id="license-message",
            subject="License renewal due",
            sent_at="2026-07-01T10:00:00Z",
        )

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {
                            "accountEmail": email,
                            "addedAt": "2026-01-01T00:00:00Z",
                            "isPrimary": index == 0,
                            "aliases": [],
                        }
                        for index, email in enumerate(linked)
                    ]
                }
            if name == "list_threads":
                account = arguments["acting_email"]
                cursor = arguments.get("cursor")
                if account == "leojkwan@gmail.com" and cursor is None:
                    return {"threads": [shared_personal], "next_cursor": "personal-page-2", "total_estimate": 2}
                if account == "leojkwan@gmail.com" and cursor == "personal-page-2":
                    return {"threads": [license_notice], "total_estimate": 2}
                return {"threads": [shared_snowcubes], "total_estimate": 1}
            if name == "get_thread":
                account = arguments["acting_email"]
                thread_id = arguments["thread_id"]
                selected = {
                    ("leojkwan@gmail.com", "thread-personal-shared"): shared_personal,
                    ("leojkwan@gmail.com", "thread-license"): license_notice,
                    ("trysnowcubes@gmail.com", "thread-snow-shared"): shared_snowcubes,
                }[(account, thread_id)]
                return {
                    **selected,
                    "user_is_participant": True,
                    "messages": [
                        {
                            "message_id": selected["last_message_id"],
                            "thread_id": selected["thread_id"],
                            "sent_at": selected["last_message_at"],
                            "subject": selected["subject"],
                            "snippet": selected["snippet"],
                            "body": selected["subject"],
                            "from": "merchant@example.com",
                            "to": [account],
                            "labels": selected["labels"],
                            "attachments": [],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {
                    "answer": "Proposal: keep the next fourteen days conflict-free.",
                    "sources": [{"id": "calendar-source", "title": "Calendar", "type": "calendar"}],
                }
            raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        coverage = {row["acting_email"]: row for row in context["coverage"]}
        self.assertEqual(coverage["leojkwan@gmail.com"]["pagination"]["pages"], 4)
        self.assertTrue(coverage["leojkwan@gmail.com"]["pagination"]["exhausted"])
        self.assertFalse(coverage["leojkwan@gmail.com"]["pagination"]["truncated"])
        self.assertEqual(context["threads_returned_raw"], 6)
        self.assertEqual(context["threads_unique"], 2)
        shared = next(row for row in context["signals"] if row["signal_id"] == "72144f1611ce5544224f9272")
        self.assertEqual(shared["source_identities"], list(linked))
        self.assertEqual(len(context["order_return_follow_up"]), 1)
        self.assertTrue(context["order_return_follow_up"][0]["proposal_only"])
        self.assertEqual(len(context["forgotten_obligations"]), 1)
        self.assertEqual(context["forgotten_obligations"][0]["signal_id"], "9bb6bee7a1fdca5fc63581d1")
        self.assertEqual(coverage["leojkwan@gmail.com"]["source_age_hours"], 0.0)
        self.assertEqual(coverage["leojkwan@gmail.com"]["newest_message_age_hours"], 2.0)
        self.assertEqual(len(context["calendar_proposals"]), 1)
        self.assertTrue(all(row["proposal_only"] for row in context["calendar_proposals"]))

    def test_mail_identity_is_stable_across_order_and_fails_closed_on_collisions(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        common_time = "2026-08-14T10:00:00Z"
        by_account = {
            "leojkwan@gmail.com": [
                {
                    "thread_id": "provider-collision-personal",
                    "last_message_id": "provider-collision",
                    "last_message_at": common_time,
                    "subject": "Alpha subject",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
                {
                    "thread_id": "distinct-a",
                    "last_message_id": "distinct-message-a",
                    "last_message_at": common_time,
                    "subject": "Identical metadata",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
                {
                    "last_message_at": common_time,
                    "subject": "ID-less metadata",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
                {
                    "thread_id": "account-local-thread-id",
                    "last_message_at": common_time,
                    "subject": "Thread-only metadata",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
            ],
            "trysnowcubes@gmail.com": [
                {
                    "thread_id": "provider-collision-snow",
                    "last_message_id": "provider-collision",
                    "last_message_at": common_time,
                    "subject": "  BETA   SUBJECT ",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
                {
                    "thread_id": "distinct-b",
                    "last_message_id": "distinct-message-b",
                    "last_message_at": common_time,
                    "subject": "Identical metadata",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
                {
                    "last_message_at": common_time,
                    "subject": "ID-less metadata",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
                {
                    "thread_id": "account-local-thread-id",
                    "last_message_at": common_time,
                    "subject": "Thread-only metadata",
                    "snippet": "Neutral note",
                    "labels": ["INBOX"],
                },
            ],
            "firstbitelabs@gmail.com": [],
        }

        def collect(order):
            def call_tool(name, arguments):
                if name == "list_accounts":
                    return {
                        "accounts": [
                            {
                                "accountEmail": email,
                                "isPrimary": index == 0,
                                "aliases": [],
                            }
                            for index, email in enumerate(order)
                        ]
                    }
                if name == "list_threads":
                    rows = list(by_account[arguments["acting_email"]])
                    if order[0] != identities[0]:
                        rows.reverse()
                    return {"threads": rows, "total_estimate": len(rows)}
                if name == "query_email_and_calendar":
                    return {
                        "answer": "Proposal only: no concrete conflict surfaced.",
                        "sources": [{"id": "same-calendar-source", "type": "calendar"}],
                    }
                if name == "get_thread":
                    selected = next(
                        row
                        for row in by_account[arguments["acting_email"]]
                        if row.get("thread_id") == arguments["thread_id"]
                    )
                    return {
                        **selected,
                        "user_is_participant": True,
                        "message_count": 1,
                        "messages": [
                            {
                                "message_id": selected.get("last_message_id") or "detail-message",
                                "thread_id": selected["thread_id"],
                                "sent_at": selected["last_message_at"],
                                "labels": list(selected["labels"]),
                                "body": selected["snippet"],
                                "from": "sender@example.com",
                                "to": [arguments["acting_email"]],
                            }
                        ],
                    }
                raise AssertionError(f"unexpected Superhuman tool: {name}")

            return brief.build_superhuman_context(call_tool, observed_at=observed_at)

        forward = collect(identities)
        reversed_context = collect(tuple(reversed(identities)))

        def identity_receipt(context):
            return [
                (
                    row["signal_id"],
                    row["subject"],
                    tuple(row["source_identities"]),
                    tuple(row["action_tags"]),
                )
                for row in context["signals"]
            ]

        self.assertEqual(identity_receipt(forward), identity_receipt(reversed_context))
        self.assertEqual(forward["threads_returned_raw"], 16)
        self.assertEqual(forward["threads_unique"], 8)
        self.assertEqual(len(forward["calendar_proposals"]), 1)
        self.assertEqual(
            forward["calendar_proposals"][0]["source_identities"],
            list(identities),
        )
        self.assertEqual(
            len([row for row in forward["signals"] if row["subject"] == "Identical metadata"]),
            2,
        )
        id_less = [row for row in forward["signals"] if row["subject"] == "ID-less metadata"]
        self.assertEqual(len(id_less), 2)
        self.assertEqual(len({row["signal_id"] for row in id_less}), 2)
        self.assertTrue(all(row["semantic_status"] == "UNKNOWN" for row in id_less))
        self.assertTrue(all("stable provider identity" in row["wake"] for row in id_less))
        thread_only = [row for row in forward["signals"] if row["subject"] == "Thread-only metadata"]
        self.assertEqual(len(thread_only), 2)
        self.assertEqual(len({row["signal_id"] for row in thread_only}), 2)
        collisions = [row for row in forward["signals"] if "subject" in row["subject"].lower()]
        provider_collisions = [
            row for row in collisions if row.get("last_message_id") == "provider-collision"
        ]
        self.assertEqual(len(provider_collisions), 2)
        self.assertTrue(all(row["semantic_status"] == "UNKNOWN" for row in provider_collisions))
        self.assertTrue(all("provider-ID collision" in row["wake"] for row in provider_collisions))

    def test_mail_coverage_marks_cursor_cycles_and_thread_truncation_unknown(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        truncated_thread = {
            "thread_id": "thread-cycle",
            "last_message_id": "message-cycle",
            "last_message_at": "2026-08-12T12:00:00Z",
            "message_count": 101,
            "subject": "Overdue registration action required",
            "snippet": "Action required",
            "participants": ["agency@example.com"],
            "labels": ["INBOX"],
            "truncated": True,
        }

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "addedAt": "2026-01-01T00:00:00Z", "isPrimary": index == 0}
                        for index, email in enumerate(identities)
                    ]
                }
            if name == "list_threads":
                if arguments["acting_email"] == "leojkwan@gmail.com":
                    return {
                        "threads": [truncated_thread],
                        "next_cursor": "same-cursor",
                        "total_estimate": 101,
                    }
                return {"threads": [], "total_estimate": 0}
            if name == "get_thread":
                return {
                    **truncated_thread,
                    "user_is_participant": True,
                    "messages": [],
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        personal = next(row for row in context["coverage"] if row["acting_email"] == "leojkwan@gmail.com")
        self.assertEqual(personal["status"], "UNKNOWN")
        self.assertFalse(personal["pagination"]["exhausted"])
        self.assertTrue(personal["pagination"]["truncated"])
        self.assertIn("cursor cycle", " ".join(personal["problems"]))
        self.assertIn("duplicate provider row", " ".join(personal["problems"]))
        self.assertIn("thread result truncated", " ".join(personal["problems"]))
        self.assertEqual(personal["source_age_hours"], 0.0)
        self.assertEqual(personal["newest_message_age_hours"], 48.0)
        self.assertFalse(context["all_clear_allowed"])

    def test_mail_coverage_detects_silent_page_and_message_truncation(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        registration = {
            "thread_id": "silent-truncation",
            "last_message_id": "silent-truncation-message",
            "last_message_at": "2026-04-01T12:00:00Z",
            "message_count": 2,
            "subject": "Registration renewal due",
            "snippet": "Exact instructions are in the earlier message",
            "labels": ["INBOX"],
        }

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []}
                        for email in identities
                    ]
                }
            if name == "list_threads":
                if arguments["acting_email"] == identities[0]:
                    # No cursor and no explicit truncation flag: the estimate is
                    # the only proof that page exhaustion is not source exhaustion.
                    return {
                        "threads": [registration],
                        "total_estimate": 2,
                        "truncated": True,
                    }
                return {"threads": [], "total_estimate": 0}
            if name == "get_thread":
                # Likewise, message_count proves the body result is incomplete
                # even though the connector omits `truncated`.
                return {
                    **registration,
                    "user_is_participant": True,
                    "messages": [
                        {
                            "message_id": registration["last_message_id"],
                            "thread_id": registration["thread_id"],
                            "sent_at": registration["last_message_at"],
                            "labels": list(registration["labels"]),
                            "body": "One visible message",
                            "from": "agency@example.com",
                            "to": [identities[0]],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        personal = next(row for row in context["coverage"] if row["acting_email"] == identities[0])
        self.assertEqual(personal["status"], "UNKNOWN")
        self.assertTrue(personal["pagination"]["exhausted"])
        self.assertTrue(personal["pagination"]["truncated"])
        self.assertIn("total estimate 2 exceeds 1", " ".join(personal["problems"]))
        self.assertIn("page result truncated", " ".join(personal["problems"]))
        self.assertIn("thread body truncated", " ".join(personal["problems"]))
        signal = next(row for row in context["signals"] if row["thread_id"] == "silent-truncation")
        self.assertEqual(signal["semantic_status"], "UNKNOWN")
        self.assertIn("silent-truncation", signal["wake"])

    def test_mail_coverage_isolates_account_failure_and_list_accounts_failure(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )

        def partially_failing_call(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "addedAt": "2026-01-01T00:00:00Z", "isPrimary": index == 0}
                        for index, email in enumerate(identities)
                    ]
                }
            if name == "list_threads":
                if arguments["acting_email"] == "leojkwan@gmail.com":
                    raise RuntimeError("personal mailbox timeout")
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        partial = brief.build_superhuman_context(partially_failing_call, observed_at=observed_at)
        partial_coverage = {row["acting_email"]: row for row in partial["coverage"]}
        self.assertEqual(partial_coverage["leojkwan@gmail.com"]["status"], "UNKNOWN")
        self.assertEqual(partial_coverage["trysnowcubes@gmail.com"]["status"], "COMPLETE")
        self.assertEqual(partial_coverage["firstbitelabs@gmail.com"]["status"], "COMPLETE")
        self.assertIn("personal mailbox timeout", " ".join(partial_coverage["leojkwan@gmail.com"]["problems"]))
        self.assertTrue(partial["available"])
        self.assertFalse(partial["all_clear_allowed"])

        def unavailable_accounts(name, _arguments):
            if name == "list_accounts":
                raise RuntimeError("account discovery unavailable")
            raise AssertionError(f"account discovery failure must stop reads, got {name}")

        unavailable = brief.build_superhuman_context(unavailable_accounts, observed_at=observed_at)
        self.assertFalse(unavailable["available"])
        self.assertEqual(unavailable["status"], "UNKNOWN")
        self.assertEqual(
            {row["acting_email"] for row in unavailable["coverage"]},
            set(identities),
        )
        self.assertTrue(all(row["status"] == "UNKNOWN" for row in unavailable["coverage"]))
        self.assertIn("account discovery unavailable", unavailable["error"])

    def test_mail_coverage_treats_error_payloads_and_parse_exceptions_as_unknown(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")

        def account_error_payload(name, _arguments):
            if name == "list_accounts":
                return {"error": "provider account lookup rejected"}
            raise AssertionError(f"account error payload must stop reads, got {name}")

        account_error = brief.build_superhuman_context(
            account_error_payload,
            observed_at=observed_at,
        )
        self.assertFalse(account_error["available"])
        self.assertEqual(account_error["status"], "UNKNOWN")
        self.assertIn("provider account lookup rejected", account_error["error"])

        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )

        def account_parse_failure(name, arguments):
            if name == "list_accounts":
                return {"accounts": [{"accountEmail": email} for email in identities]}
            if name == "list_threads":
                if arguments["acting_email"] == identities[0]:
                    raise TypeError("unexpected provider row type")
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        partial = brief.build_superhuman_context(account_parse_failure, observed_at=observed_at)
        by_identity = {row["acting_email"]: row for row in partial["coverage"]}
        self.assertEqual(by_identity[identities[0]]["status"], "UNKNOWN")
        self.assertIn("unexpected provider row type", " ".join(by_identity[identities[0]]["problems"]))
        self.assertEqual(by_identity[identities[1]]["status"], "COMPLETE")
        self.assertEqual(by_identity[identities[2]]["status"], "COMPLETE")
        self.assertTrue(partial["available"])
        self.assertEqual(partial["status"], "UNKNOWN")

    def test_mail_coverage_records_malformed_account_and_thread_rows_as_unknown(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []} for email in identities
                    ] + ["opaque-account-row"]
                }
            if name == "list_threads":
                if arguments["acting_email"] == identities[0]:
                    return {
                        "threads": [
                            {
                                "thread_id": "valid-thread",
                                "last_message_id": "valid-message",
                                "last_message_at": "2026-08-14T10:00:00Z",
                                "subject": "Neutral note",
                                "snippet": "No action",
                                "labels": ["INBOX"],
                            },
                            {
                                "thread_id": "naive-timestamp-thread",
                                "last_message_id": "naive-timestamp-message",
                                "last_message_at": "2026-08-14T10:00:00",
                                "subject": "Neutral timestamp note",
                                "snippet": "Timezone is absent",
                                "labels": ["INBOX"],
                            },
                            "opaque-thread-row",
                        ]
                    }
                return {"threads": []}
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            if name == "get_thread":
                sent_at = (
                    "2026-08-14T10:00:00"
                    if arguments["thread_id"] == "naive-timestamp-thread"
                    else "2026-08-14T10:00:00Z"
                )
                return {
                    "thread_id": arguments["thread_id"],
                    "user_is_participant": True,
                    "message_count": 1,
                    "messages": [
                        {
                            "message_id": (
                                "naive-timestamp-message"
                                if arguments["thread_id"] == "naive-timestamp-thread"
                                else "valid-message"
                            ),
                            "thread_id": arguments["thread_id"],
                            "sent_at": sent_at,
                            "labels": ["INBOX"],
                            "body": "No requested action",
                            "from": "sender@example.com",
                            "to": [identities[0]],
                        }
                    ],
                }
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        self.assertEqual(context["account_discovery"]["status"], "UNKNOWN")
        self.assertEqual(context["account_discovery"]["malformed_rows"], 1)
        self.assertIn("unusable account row", context["account_discovery"]["wake"])
        personal = next(row for row in context["coverage"] if row["acting_email"] == identities[0])
        self.assertEqual(personal["status"], "UNKNOWN")
        self.assertIn("1 unusable thread row", " ".join(personal["problems"]))
        self.assertIn("unusable source timestamp", " ".join(personal["problems"]))
        self.assertEqual(personal["threads_returned"], 2)
        timestamp_signal = next(
            row for row in context["signals"] if row["thread_id"] == "naive-timestamp-thread"
        )
        self.assertEqual(timestamp_signal["semantic_status"], "UNKNOWN")
        self.assertIn("source timestamp", timestamp_signal["wake"])
        self.assertEqual(context["status"], "UNKNOWN")

    def test_mail_calendar_proposals_require_sources_and_clarification_wakes(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        extra_identities = (
            "calendar-answer-cap@example.com",
            "calendar-source-cap@example.com",
        )

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email}
                        for email in identities + extra_identities
                    ]
                }
            if name == "list_threads":
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                account = arguments["acting_email"]
                if account == identities[0]:
                    return {"answer": "A possible conflict exists.", "sources": []}
                if account == identities[1]:
                    return {
                        "answer": "A date needs clarification.",
                        "sources": [{"id": "calendar-snow"}],
                        "clarification_needed": "Which lesson date is intended?",
                    }
                if account == identities[2]:
                    return {
                        "answer": "No conflict surfaced.",
                        "sources": [{"id": "calendar-firstbite"}],
                    }
                if account == extra_identities[0]:
                    return {
                        "answer": "x" * 1201,
                        "sources": [{"id": "calendar-long-answer"}],
                    }
                return {
                    "answer": "No conflict surfaced.",
                    "sources": [
                        {"id": f"calendar-source-{index}"} for index in range(21)
                    ],
                }
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        proposals = {row["source_identities"][0]: row for row in context["calendar_proposals"]}
        self.assertEqual(proposals[identities[0]]["status"], "UNKNOWN")
        self.assertEqual(proposals[identities[0]]["confidence"], "LOW")
        self.assertIn("source-labelled evidence", proposals[identities[0]]["wake"])
        self.assertEqual(proposals[identities[1]]["status"], "UNKNOWN")
        self.assertIn("Which lesson date is intended?", proposals[identities[1]]["wake"])
        self.assertEqual(proposals[identities[2]]["status"], "PROPOSAL")
        self.assertEqual(proposals[identities[2]]["confidence"], "MEDIUM")
        self.assertIn("1200-character", proposals[extra_identities[0]]["wake"])
        self.assertIn("20-source", proposals[extra_identities[1]]["wake"])

    def test_mail_query_contract_is_ninety_days_fifty_rows_and_page_cap_fails_closed(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        seen_queries = []
        personal_page = 0

        def call_tool(name, arguments):
            nonlocal personal_page
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "addedAt": "2026-01-01T00:00:00Z", "isPrimary": index == 0}
                        for index, email in enumerate(identities)
                    ]
                }
            if name == "list_threads":
                seen_queries.append(dict(arguments))
                if arguments["acting_email"] != "leojkwan@gmail.com":
                    return {"threads": [], "total_estimate": 0}
                personal_page += 1
                return {
                    "threads": [],
                    "next_cursor": f"page-{personal_page + 1}",
                    "total_estimate": 5000,
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        personal = next(row for row in context["coverage"] if row["acting_email"] == "leojkwan@gmail.com")
        self.assertEqual(personal["pagination"]["pages"], 2)
        self.assertFalse(personal["pagination"]["exhausted"])
        self.assertTrue(personal["pagination"]["truncated"])
        self.assertIn("exceeds the 2000-row pagination safety bound", " ".join(personal["problems"]))
        self.assertTrue(seen_queries)
        declared_queries = [query for query in seen_queries if "start_date" in query]
        horizon_queries = [query for query in seen_queries if "start_date" not in query]
        for query in declared_queries:
            self.assertEqual(query["start_date"], "2026-05-16T12:00:00+00:00")
            self.assertEqual(query["end_date"], "2026-08-14T12:00:00+00:00")
            self.assertEqual(query["limit"], 50)
            self.assertEqual(query["sort"], "newest")
            self.assertIn(query["labels"], [["INBOX"], ["SENT"]])
            self.assertIn(query["acting_email"], identities)
        for query in horizon_queries:
            self.assertEqual(query["end_date"], "2026-05-16T11:59:59+00:00")
            self.assertEqual(query["limit"], 50)
            self.assertEqual(query["sort"], "oldest")
            self.assertEqual(query["labels"], ["INBOX"])
            self.assertIn(query["acting_email"], identities)
        for email in identities:
            self.assertEqual(
                {
                    tuple(query["labels"])
                    for query in declared_queries
                    if query["acting_email"] == email
                },
                {("INBOX",), ("SENT",)},
            )

    def test_mail_read_budget_and_global_action_cap_fail_closed(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        calls = []
        action_rows = {
            email: [
                {
                    "thread_id": f"{index}-{email}",
                    "last_message_id": f"message-{index}-{email}",
                    "last_message_at": "2026-08-12T12:00:00Z",
                    "message_count": 1,
                    "subject": f"Registration renewal due {index}",
                    "snippet": "Action required",
                    "labels": ["INBOX"],
                }
                for index in range(21)
            ]
            for email in identities[:2]
        }
        action_rows[identities[2]] = []

        def call_tool(name, arguments):
            calls.append((name, dict(arguments)))
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []}
                        for email in identities
                    ]
                }
            if name == "list_threads":
                rows = action_rows[arguments["acting_email"]]
                return {"threads": rows, "total_estimate": len(rows)}
            if name == "get_thread":
                selected = next(
                    row
                    for row in action_rows[arguments["acting_email"]]
                    if row["thread_id"] == arguments["thread_id"]
                )
                return {
                    **selected,
                    "user_is_participant": True,
                    "messages": [
                        {
                            "message_id": selected["last_message_id"],
                            "thread_id": selected["thread_id"],
                            "sent_at": selected["last_message_at"],
                            "labels": list(selected["labels"]),
                            "body": selected["snippet"],
                            "from": "agency@example.com",
                            "to": [arguments["acting_email"]],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

        capped = brief.build_superhuman_context(call_tool, observed_at=observed_at)
        detail_calls = [call for call in calls if call[0] == "get_thread"]
        self.assertEqual(len(detail_calls), brief.SUPERHUMAN_GLOBAL_ACTION_LIMIT)
        self.assertEqual(capped["status"], "UNKNOWN")
        self.assertIn("global", " ".join(capped["problems"]).lower())
        unverified = [
            row
            for row in capped["signals"]
            if "exact thread read cap" in str(row.get("wake") or "")
        ]
        self.assertEqual(len(unverified), 2)
        self.assertTrue(all(row["semantic_status"] == "UNKNOWN" for row in unverified))
        self.assertEqual(len(capped["forgotten_obligations"]), 42)

        deadline_calls = []
        ticks = iter((0.0, 0.0, 421.0, 421.0, 421.0, 421.0))

        def deadline_tool(name, arguments):
            deadline_calls.append((name, dict(arguments)))
            if name == "list_accounts":
                return {"accounts": [{"accountEmail": email} for email in identities]}
            if name == "list_threads":
                return {"threads": [], "total_estimate": 0}
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        deadline = brief.build_superhuman_context(
            deadline_tool,
            observed_at=observed_at,
            monotonic=lambda: next(ticks, 421.0),
        )
        self.assertEqual(deadline["status"], "UNKNOWN")
        self.assertIn("420-second", " ".join(deadline["problems"]))
        self.assertLessEqual(
            len([call for call in deadline_calls if call[0] != "list_accounts"]),
            1,
        )
        self.assertTrue(
            any("read budget" in str(row.get("wake") or "") for row in deadline["coverage"])
        )

    def test_mail_signal_retention_cap_makes_overall_status_unknown_with_wake(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        rows = [
            {
                "thread_id": f"thread-{index}",
                "last_message_id": f"message-{index}",
                "last_message_at": f"2026-08-14T10:{index:02d}:00Z",
                "subject": f"Neutral note {index}",
                "snippet": "No requested action",
                "labels": ["INBOX"],
            }
            for index in range(51)
        ]
        rows[-1].update(
            {
                "last_message_at": "2026-06-01T10:00:00Z",
                "subject": "Driver license renewal due",
                "snippet": "Action required",
            }
        )

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []}
                        for email in identities
                    ]
                }
            if name == "list_threads":
                account_rows = rows if arguments["acting_email"] == identities[0] else []
                return {"threads": account_rows, "total_estimate": len(account_rows)}
            if name == "get_thread":
                selected = next(row for row in rows if row["thread_id"] == arguments["thread_id"])
                return {
                    **selected,
                    "user_is_participant": True,
                    "message_count": 1,
                    "messages": [
                        {
                            "message_id": selected["last_message_id"],
                            "thread_id": selected["thread_id"],
                            "sent_at": selected["last_message_at"],
                            "labels": list(selected["labels"]),
                            "body": selected["snippet"],
                            "from": "agency@example.com",
                            "to": [identities[0]],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        self.assertEqual(context["signals_retained"], 50)
        self.assertEqual(context["signals_omitted"], 1)
        self.assertFalse(context["complete"])
        self.assertEqual(context["status"], "UNKNOWN")
        self.assertFalse(context["all_clear_allowed"])
        self.assertIn("1 signal omitted", " ".join(context["problems"]))
        self.assertIn("retention cap", context["wake"])
        self.assertEqual(
            [row["thread_id"] for row in context["forgotten_obligations"]],
            ["thread-50"],
        )

    def test_obligations_beyond_the_retention_cap_are_still_classified_and_counted(self):
        # The retention cap bounds the generic `signals` sample. It must not run
        # BEFORE classification, or a real obligation past the cap is dropped
        # without ever being read as an obligation. Production hit exactly this:
        # 2,291 unique signals, 50 retained, and every retained row was
        # action-tagged -- so action-tagged rows past 50 were discarded silently.
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = ("leojkwan@gmail.com", "trysnowcubes@gmail.com", "firstbitelabs@gmail.com")
        obligation_count = 60
        rows = [
            {
                "thread_id": f"obligation-{index}",
                "last_message_id": f"obligation-message-{index}",
                "last_message_at": "2026-06-01T10:00:00Z",
                "subject": f"Driver license renewal due {index}",
                "snippet": "Action required",
                "labels": ["INBOX"],
            }
            for index in range(obligation_count)
        ]

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {"accounts": [{"accountEmail": email, "aliases": []} for email in identities]}
            if name == "list_threads":
                account_rows = rows if arguments["acting_email"] == identities[0] else []
                return {"threads": account_rows, "total_estimate": len(account_rows)}
            if name == "get_thread":
                selected = next(row for row in rows if row["thread_id"] == arguments["thread_id"])
                return {
                    **selected,
                    "user_is_participant": True,
                    "message_count": 1,
                    "messages": [
                        {
                            "message_id": selected["last_message_id"],
                            "thread_id": selected["thread_id"],
                            "sent_at": selected["last_message_at"],
                            "labels": list(selected["labels"]),
                            "body": selected["snippet"],
                            "from": "agency@example.com",
                            "to": [identities[0]],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        # Every obligation is classified from the full collision-safe set, not
        # from the already-truncated retention sample.
        self.assertEqual(len(context["forgotten_obligations"]), obligation_count)
        self.assertEqual(
            {row["thread_id"] for row in context["forgotten_obligations"]},
            {f"obligation-{index}" for index in range(obligation_count)},
        )
        # Truncating the generic sample stays honest, never an all-clear.
        self.assertFalse(context["all_clear_allowed"])
        self.assertEqual(context["status"], "UNKNOWN")

    def test_category_cap_drops_the_newest_rows_and_keeps_the_longest_neglected(self):
        # `unique_signals` is newest-first, so slicing it directly would discard
        # the OLDEST obligations -- precisely the ones a "forgotten obligation"
        # section exists to surface. action_candidate_sort_key is the intended
        # order: obligation-class first, then ascending timestamp.
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = ("leojkwan@gmail.com", "trysnowcubes@gmail.com", "firstbitelabs@gmail.com")
        overflow = brief.SUPERHUMAN_CATEGORY_LIMIT + 10
        base = brief.datetime.fromisoformat("2026-05-17T00:00:00+00:00")
        rows = [
            {
                "thread_id": f"obligation-{index:04d}",
                "last_message_id": f"obligation-message-{index:04d}",
                # index 0 is the oldest, index N-1 the newest.
                "last_message_at": (base + brief.timedelta(hours=index))
                .isoformat()
                .replace("+00:00", "Z"),
                "subject": f"Driver license renewal due {index}",
                "snippet": "Action required",
                "labels": ["INBOX"],
            }
            for index in range(overflow)
        ]

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {"accounts": [{"accountEmail": email, "aliases": []} for email in identities]}
            if name == "list_threads":
                account_rows = rows if arguments["acting_email"] == identities[0] else []
                return {"threads": account_rows, "total_estimate": len(account_rows)}
            if name == "get_thread":
                selected = next(row for row in rows if row["thread_id"] == arguments["thread_id"])
                return {
                    **selected,
                    "user_is_participant": True,
                    "message_count": 1,
                    "messages": [
                        {
                            "message_id": selected["last_message_id"],
                            "thread_id": selected["thread_id"],
                            "sent_at": selected["last_message_at"],
                            "labels": list(selected["labels"]),
                            "body": selected["snippet"],
                            "from": "agency@example.com",
                            "to": [identities[0]],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"unexpected Superhuman tool: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        retained = {row["thread_id"] for row in context["forgotten_obligations"]}
        self.assertEqual(len(retained), brief.SUPERHUMAN_CATEGORY_LIMIT)
        # The ten NEWEST are the ones dropped; every oldest row survives.
        self.assertEqual(
            retained,
            {f"obligation-{index:04d}" for index in range(brief.SUPERHUMAN_CATEGORY_LIMIT)},
        )
        self.assertIn("obligation-0000", retained)
        self.assertNotIn(f"obligation-{overflow - 1:04d}", retained)
        # Truncation is named, never silent.
        self.assertIn("10 forgotten obligations row omitted", " ".join(context["problems"]))

    def test_mail_action_candidates_include_old_waiting_urgent_and_snowcubes_but_unread_content_is_unknown(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        rows = {
            "leojkwan@gmail.com": [
                {
                    "thread_id": "old-registration",
                    "last_message_id": "old-registration-message",
                    "last_message_at": "2026-06-30T12:00:00Z",
                    "message_count": 1,
                    "subject": "Registration renewal due",
                    "snippet": "Renewal deadline",
                    "participants": ["agency@example.com"],
                    "labels": ["INBOX"],
                },
                {
                    "thread_id": "urgent-reply",
                    "last_message_id": "urgent-reply-message",
                    "last_message_at": "2026-08-14T11:00:00Z",
                    "message_count": 1,
                    "subject": "Urgent: please reply today",
                    "snippet": "Waiting on your response",
                    "participants": ["person@example.com"],
                    "labels": ["INBOX", "UNREAD"],
                },
                {
                    "thread_id": "waiting-outbound",
                    "last_message_id": "waiting-outbound-message",
                    "last_message_at": "2026-07-15T12:00:00Z",
                    "message_count": 1,
                    "subject": "Checking in about the repair",
                    "snippet": "I sent the details and am awaiting their answer",
                    "participants": ["repair@example.com"],
                    "labels": ["SENT", "INBOX"],
                },
                {
                    "thread_id": "return-attachment",
                    "last_message_id": "return-attachment-message",
                    "last_message_at": "2026-08-13T12:00:00Z",
                    "message_count": 1,
                    "subject": "Return label and refund deadline",
                    "snippet": "See the attached return label",
                    "participants": ["merchant@example.com"],
                    "labels": ["INBOX"],
                },
            ],
            "trysnowcubes@gmail.com": [
                {
                    "thread_id": "snowcubes-wholesale",
                    "last_message_id": "snowcubes-wholesale-message",
                    "last_message_at": "2026-08-14T09:00:00Z",
                    "message_count": 1,
                    "subject": "Wholesale cafe request",
                    "snippet": "Can we carry Snowcubes?",
                    "participants": ["buyer@cafe.example"],
                    # Read on another device but still inbound and unanswered.
                    "labels": ["INBOX"],
                }
            ],
            "firstbitelabs@gmail.com": [],
        }

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {
                            "accountEmail": email,
                            "addedAt": "2026-01-01T00:00:00Z",
                            "isPrimary": index == 0,
                            "aliases": [],
                        }
                        for index, email in enumerate(identities)
                    ]
                }
            if name == "list_threads":
                account_rows = rows[arguments["acting_email"]]
                return {"threads": account_rows, "total_estimate": len(account_rows)}
            if name == "get_thread":
                selected = next(
                    row
                    for row in rows[arguments["acting_email"]]
                    if row["thread_id"] == arguments["thread_id"]
                )
                message = {
                    "message_id": selected["last_message_id"],
                    "thread_id": selected["thread_id"],
                    "sent_at": selected["last_message_at"],
                    "subject": selected["subject"],
                    "snippet": selected["snippet"],
                    "from": (
                        arguments["acting_email"]
                        if selected["thread_id"] == "waiting-outbound"
                        else selected["participants"][0]
                    ),
                    "to": (
                        [selected["participants"][0]]
                        if selected["thread_id"] == "waiting-outbound"
                        else [arguments["acting_email"]]
                    ),
                    "labels": selected["labels"],
                    "body": selected["snippet"],
                    "attachments": [],
                }
                if selected["thread_id"] == "return-attachment":
                    message["body"] = ""
                    message["attachments"] = ["return-label.pdf"]
                return {
                    **selected,
                    "user_is_participant": True,
                    "messages": [message],
                }
            if name == "query_email_and_calendar":
                return {
                    "answer": "Proposal only: review the next fourteen days for conflicts.",
                    "sources": [{"id": "cal-1", "title": "Calendar", "type": "calendar"}],
                }
            raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        self.assertEqual(
            {row["thread_id"] for row in context["forgotten_obligations"]},
            {"old-registration", "waiting-outbound"},
        )
        self.assertEqual(len(context["urgent_replies"]), 1)
        self.assertEqual(context["urgent_replies"][0]["thread_id"], "urgent-reply")
        self.assertEqual(len(context["waiting_replies"]), 1)
        self.assertEqual(context["waiting_replies"][0]["thread_id"], "waiting-outbound")
        self.assertEqual(len(context["proactive_candidates"]), 1)
        self.assertEqual(
            context["proactive_candidates"][0]["source_identities"],
            ["trysnowcubes@gmail.com"],
        )
        unread = next(row for row in context["signals"] if row["thread_id"] == "return-attachment")
        self.assertEqual(unread["semantic_status"], "UNKNOWN")
        self.assertIn("return-attachment", unread["wake"])
        self.assertIn("return-label.pdf", unread["wake"])
        personal = next(row for row in context["coverage"] if row["acting_email"] == "leojkwan@gmail.com")
        self.assertEqual(personal["status"], "UNKNOWN")
        self.assertEqual(personal["source_age_hours"], 0.0)
        self.assertEqual(personal["newest_message_age_hours"], 1.0)
        self.assertEqual(context["forgotten_horizon"]["status"], "COMPLETE")
        self.assertIsNone(context["forgotten_horizon"]["wake"])
        self.assertFalse(context["all_clear_allowed"])

    def test_mail_waiting_direction_uses_last_message_and_suppresses_done_rows(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        identities = (
            "leojkwan@gmail.com",
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        rows = [
            {
                "thread_id": "mixed-sent-inbox",
                "last_message_id": "mixed-inbound-latest",
                "last_message_at": "2026-08-14T11:00:00Z",
                "message_count": 2,
                "subject": "Urgent: please reply today",
                "snippet": "Their inbound response arrived after Leo sent mail",
                "participants": ["person@example.com"],
                "labels": ["SENT", "INBOX", "UNREAD"],
            },
            {
                "thread_id": "archived-order",
                "last_message_id": "archived-order-message",
                "last_message_at": "2026-07-01T10:00:00Z",
                "message_count": 1,
                "subject": "Invoice and order return due",
                "snippet": "This was already handled",
                "participants": ["merchant@example.com"],
                # Gmail commonly represents archive as absence of INBOX.
                "labels": [],
            },
            {
                "thread_id": "done-license",
                "last_message_id": "done-license-message",
                "last_message_at": "2026-07-01T10:00:00Z",
                "message_count": 1,
                "subject": "Driver license renewal due",
                "snippet": "This was already handled",
                "participants": ["agency@example.com"],
                "labels": ["DONE"],
            },
            {
                "thread_id": "empty-exact-thread",
                "last_message_id": "empty-exact-message",
                "last_message_at": "2026-08-10T10:00:00Z",
                "subject": "Payment due",
                "snippet": "Open the exact source",
                "participants": ["billing@example.com"],
                "labels": ["INBOX"],
            },
            {
                "thread_id": "outbound-thank-you",
                "last_message_id": "outbound-thank-you-message",
                "last_message_at": "2026-07-01T10:00:00Z",
                "message_count": 1,
                "subject": "Thank you",
                "snippet": "Thanks again, everything is all set.",
                "participants": ["friend@example.com"],
                "labels": ["SENT"],
            },
            {
                "thread_id": "missing-listed-latest",
                "last_message_id": "missing-inbound-latest-message",
                "last_message_at": "2026-08-14T11:30:00Z",
                "message_count": 2,
                "subject": "Urgent: please reply",
                "snippet": "Latest inbound summary is absent from detail",
                "participants": ["person@example.com"],
                "labels": ["SENT", "INBOX", "UNREAD"],
            },
            {
                "thread_id": "detail-error-thread",
                "last_message_id": "detail-error-message",
                "last_message_at": "2026-08-14T09:00:00Z",
                "message_count": 1,
                "subject": "Order return due",
                "snippet": "Provider detail read fails",
                "participants": ["merchant@example.com"],
                "labels": ["INBOX"],
            },
            {
                "thread_id": "alias-outbound-waiting",
                "last_message_id": "alias-outbound-message",
                "last_message_at": "2026-07-10T10:00:00Z",
                "message_count": 1,
                "subject": "Checking in",
                "snippet": "Could you let me know the status?",
                "participants": ["person@example.com"],
                "labels": ["SENT", "INBOX"],
            },
            {
                "thread_id": "equal-time-direction",
                "last_message_at": "2026-08-14T08:00:00Z",
                "message_count": 2,
                "subject": "Checking in on the answer",
                "snippet": "Could you let me know?",
                "participants": ["person@example.com"],
                "labels": ["SENT", "INBOX"],
            },
        ]
        tool_names = []

        def call_tool(name, arguments):
            tool_names.append(name)
            if name == "list_accounts":
                return {
                    "accounts": [
                        {
                            "accountEmail": email,
                            "aliases": ["leo.alias@gmail.com"] if email == identities[0] else [],
                        }
                        for email in identities
                    ]
                }
            if name == "list_threads":
                account_rows = rows if arguments["acting_email"] == identities[0] else []
                return {"threads": account_rows, "total_estimate": len(account_rows)}
            if name == "get_thread":
                selected = next(row for row in rows if row["thread_id"] == arguments["thread_id"])
                if selected["thread_id"] == "empty-exact-thread":
                    return {**selected, "user_is_participant": True, "messages": []}
                if selected["thread_id"] == "detail-error-thread":
                    return {"error": "exact detail payload rejected"}
                if selected["thread_id"] == "missing-listed-latest":
                    return {
                        **selected,
                        "user_is_participant": True,
                        "messages": [
                            {
                                "message_id": "older-outbound-only",
                                "thread_id": selected["thread_id"],
                                "sent_at": "2026-08-13T12:00:00Z",
                                "labels": list(selected["labels"]),
                                "body": "Could you let me know?",
                                "from": identities[0],
                                "to": ["person@example.com"],
                            }
                        ],
                    }
                if selected["thread_id"] == "equal-time-direction":
                    return {
                        **selected,
                        "user_is_participant": True,
                        "messages": [
                            {
                                "message_id": "equal-outbound",
                                "thread_id": selected["thread_id"],
                                "sent_at": selected["last_message_at"],
                                "labels": list(selected["labels"]),
                                "body": "Could you let me know?",
                                "from": identities[0],
                                "to": ["person@example.com"],
                            },
                            {
                                "message_id": "equal-inbound",
                                "thread_id": selected["thread_id"],
                                "sent_at": selected["last_message_at"],
                                "labels": list(selected["labels"]),
                                "body": "Maybe",
                                "from": "person@example.com",
                                "to": [identities[0]],
                            },
                        ],
                    }
                messages = [
                    {
                        "message_id": selected["last_message_id"],
                        "thread_id": selected["thread_id"],
                        "sent_at": selected["last_message_at"],
                        "labels": list(selected["labels"]),
                        "body": selected["snippet"],
                        "from": (
                            identities[0]
                            if selected["thread_id"] == "outbound-thank-you"
                            else (
                                "leo.alias@gmail.com"
                                if selected["thread_id"] == "alias-outbound-waiting"
                                else selected["participants"][0]
                            )
                        ),
                        "to": (
                            [selected["participants"][0]]
                            if selected["thread_id"] in {"outbound-thank-you", "alias-outbound-waiting"}
                            else [identities[0]]
                        ),
                    }
                ]
                if selected["thread_id"] == "mixed-sent-inbox":
                    messages.insert(
                        0,
                        {
                            "message_id": "mixed-outbound-older",
                            "thread_id": selected["thread_id"],
                            "sent_at": "2026-08-13T12:00:00Z",
                            "labels": list(selected["labels"]),
                            "body": "Leo's earlier note",
                            "from": identities[0],
                            "to": ["person@example.com"],
                        },
                    )
                return {
                    **selected,
                    "user_is_participant": True,
                    "messages": messages,
                }
            if name == "query_email_and_calendar":
                return {"answer": "No conflict surfaced.", "sources": [{"id": "calendar-source"}]}
            raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        self.assertEqual(
            [row["thread_id"] for row in context["urgent_replies"]],
            ["mixed-sent-inbox"],
        )
        self.assertNotIn(
            "mixed-sent-inbox",
            [row["thread_id"] for row in context["waiting_replies"]],
        )
        mixed = next(row for row in context["signals"] if row["thread_id"] == "mixed-sent-inbox")
        self.assertEqual(mixed["semantic_status"], "PROPOSAL")
        self.assertTrue(mixed["thread_body_read"])
        empty = next(row for row in context["signals"] if row["thread_id"] == "empty-exact-thread")
        self.assertEqual(empty["semantic_status"], "UNKNOWN")
        self.assertIn("empty-exact-thread", empty["wake"])
        self.assertIn("no non-draft visible message", " ".join(
            next(
                row["problems"]
                for row in context["coverage"]
                if row["acting_email"] == identities[0]
            )
        ))
        elevated = {
            row["thread_id"]
            for category in (
                "forgotten_obligations",
                "order_return_follow_up",
                "urgent_replies",
                "waiting_replies",
            )
            for row in context[category]
        }
        self.assertNotIn("archived-order", elevated)
        self.assertNotIn("done-license", elevated)
        self.assertNotIn("outbound-thank-you", elevated)
        self.assertIn("alias-outbound-waiting", elevated)
        self.assertIn(
            "alias-outbound-waiting",
            [row["thread_id"] for row in context["waiting_replies"]],
        )
        self.assertNotIn("missing-listed-latest", elevated)
        self.assertNotIn("equal-time-direction", elevated)
        missing_latest = next(
            row for row in context["signals"] if row["thread_id"] == "missing-listed-latest"
        )
        self.assertEqual(missing_latest["semantic_status"], "UNKNOWN")
        self.assertIn("missing-listed-latest", missing_latest["wake"])
        detail_error = next(
            row for row in context["signals"] if row["thread_id"] == "detail-error-thread"
        )
        self.assertEqual(detail_error["semantic_status"], "UNKNOWN")
        self.assertIn("exact detail payload rejected", " ".join(
            next(
                row["problems"]
                for row in context["coverage"]
                if row["acting_email"] == identities[0]
            )
        ))
        self.assertEqual(
            set(tool_names),
            {"list_accounts", "list_threads", "get_thread", "query_email_and_calendar"},
        )

    def test_cross_account_self_mail_is_not_a_relationship_action(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        personal = "leojkwan@gmail.com"
        business = "trysnowcubes@gmail.com"
        identities = (personal, business, "firstbitelabs@gmail.com")
        sent_row = {
            "thread_id": "personal-self-copy",
            "last_message_id": "shared-self-message",
            "last_message_at": "2026-08-14T10:00:00Z",
            "subject": "Can we review this?",
            "snippet": "Please let me know.",
            "labels": ["SENT"],
        }
        inbox_row = {
            **sent_row,
            "thread_id": "business-self-copy",
            "labels": ["INBOX"],
        }
        tool_names = []

        def call_tool(name, arguments):
            tool_names.append(name)
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []}
                        for email in identities
                    ]
                }
            if name == "list_threads":
                email = arguments["acting_email"]
                labels = arguments["labels"]
                if email == personal and labels == ["SENT"]:
                    return {"threads": [sent_row], "total_estimate": 1}
                if email == business and labels == ["INBOX"]:
                    return {"threads": [inbox_row], "total_estimate": 1}
                return {"threads": [], "total_estimate": 0}
            if name == "get_thread":
                row = sent_row if arguments["acting_email"] == personal else inbox_row
                return {
                    **row,
                    "user_is_participant": True,
                    "message_count": 1,
                    "messages": [
                        {
                            "message_id": "shared-self-message",
                            "thread_id": row["thread_id"],
                            "sent_at": "2026-08-14T10:00:00Z",
                            "labels": list(row["labels"]),
                            "body": "Can we review this? Please let me know.",
                            "from": personal,
                            "to": [business],
                        }
                    ],
                }
            if name == "query_email_and_calendar":
                return {
                    "answer": "No conflict surfaced.",
                    "sources": [{"id": "calendar-source"}],
                }
            raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)

        signal = next(
            row for row in context["signals"]
            if row["last_message_id"] == "shared-self-message"
        )
        self.assertEqual(signal["source_identities"], [personal, business])
        self.assertEqual(signal["action_tags"], [])
        self.assertEqual(signal["semantic_status"], "OBSERVED")
        for category in (
            "urgent_replies",
            "waiting_replies",
            "proactive_candidates",
        ):
            self.assertNotIn(signal["signal_id"], {
                row["signal_id"] for row in context[category]
            })
        self.assertEqual(
            set(tool_names),
            {"list_accounts", "list_threads", "get_thread", "query_email_and_calendar"},
        )

    def test_exact_thread_schema_proves_participation_membership_drafts_and_recipients(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        personal = "leojkwan@gmail.com"
        identities = (
            personal,
            "trysnowcubes@gmail.com",
            "firstbitelabs@gmail.com",
        )
        rows = [
            {
                "thread_id": "draft-labelled-thread",
                "last_message_id": "draft-labelled-visible",
                "last_message_at": "2026-08-14T09:00:00Z",
                "subject": "Please reply",
                "snippet": "The non-draft message needs a reply.",
                "labels": ["INBOX"],
            },
            {
                "thread_id": "nonparticipant-thread",
                "last_message_id": "nonparticipant-message",
                "last_message_at": "2026-08-14T09:10:00Z",
                "subject": "Please reply to nonparticipant",
                "snippet": "This payload is not Leo's thread.",
                "labels": ["INBOX"],
            },
            {
                "thread_id": "wrong-message-thread",
                "last_message_id": "wrong-message",
                "last_message_at": "2026-08-14T09:20:00Z",
                "subject": "Please reply to wrong thread",
                "snippet": "The message belongs elsewhere.",
                "labels": ["INBOX"],
            },
            {
                "thread_id": "owned-missing-recipients",
                "last_message_id": "owned-missing-recipients-message",
                "last_message_at": "2026-08-14T09:30:00Z",
                "subject": "Can you answer?",
                "snippet": "Please let me know.",
                "labels": ["SENT"],
            },
        ]
        get_thread_arguments = []

        def exact_message(row, **overrides):
            return {
                "message_id": row["last_message_id"],
                "thread_id": row["thread_id"],
                "sent_at": row["last_message_at"],
                "labels": list(row["labels"]),
                "body": row["snippet"],
                "from": "sender@example.com",
                "to": [personal],
                **overrides,
            }

        def call_tool(name, arguments):
            if name == "list_accounts":
                return {
                    "accounts": [
                        {"accountEmail": email, "aliases": []}
                        for email in identities
                    ]
                }
            if name == "list_threads":
                if arguments["acting_email"] != personal:
                    return {"threads": [], "total_estimate": 0}
                label = arguments["labels"][0]
                lane_rows = [row for row in rows if label in row["labels"]]
                return {"threads": lane_rows, "total_estimate": len(lane_rows)}
            if name == "get_thread":
                get_thread_arguments.append(dict(arguments))
                row = next(row for row in rows if row["thread_id"] == arguments["thread_id"])
                if row["thread_id"] == "draft-labelled-thread":
                    messages = [
                        exact_message(row),
                        {
                            "message_id": "optional-is-draft-omitted",
                            "thread_id": row["thread_id"],
                            "sent_at": "2026-08-14T10:00:00Z",
                            "labels": ["DRAFT"],
                            "body": "Draft answer that must not determine direction.",
                            "from": personal,
                            "to": ["sender@example.com"],
                        },
                    ]
                    participant = True
                elif row["thread_id"] == "nonparticipant-thread":
                    messages = [exact_message(row)]
                    participant = False
                elif row["thread_id"] == "wrong-message-thread":
                    messages = [exact_message(row, thread_id="different-thread")]
                    participant = True
                else:
                    messages = [
                        exact_message(
                            row,
                            **{
                                "from": personal,
                                "to": None,
                            },
                        )
                    ]
                    participant = True
                return {
                    **row,
                    "user_is_participant": participant,
                    "message_count": len(messages),
                    "messages": messages,
                }
            if name == "query_email_and_calendar":
                return {
                    "answer": "No conflict surfaced.",
                    "sources": [{"id": "calendar-source"}],
                }
            raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

        context = brief.build_superhuman_context(call_tool, observed_at=observed_at)
        by_thread = {row["thread_id"]: row for row in context["signals"]}

        self.assertTrue(get_thread_arguments)
        self.assertTrue(all(call["include_drafts"] is False for call in get_thread_arguments))
        self.assertEqual(by_thread["draft-labelled-thread"]["semantic_status"], "PROPOSAL")
        self.assertIn("reply", by_thread["draft-labelled-thread"]["action_tags"])
        for thread_id in (
            "nonparticipant-thread",
            "wrong-message-thread",
            "owned-missing-recipients",
        ):
            self.assertEqual(by_thread[thread_id]["semantic_status"], "UNKNOWN")
            self.assertTrue(by_thread[thread_id].get("wake"))
        self.assertNotIn(
            "waiting_reply",
            by_thread["owned-missing-recipients"]["action_tags"],
        )

    def test_cross_account_classification_is_stable_and_projects_account_snapshot(self):
        observed_at = brief.datetime.fromisoformat("2026-08-14T12:00:00+00:00")
        personal = "leojkwan@gmail.com"
        business = "trysnowcubes@gmail.com"
        third = "firstbitelabs@gmail.com"
        common = {
            "last_message_id": "shared-external-message",
            "last_message_at": "2026-08-14T10:00:00Z",
            "subject": "Order return deadline",
            "snippet": "Here is the customer update.",
        }
        personal_row = {
            **common,
            "thread_id": "personal-active-copy",
            "labels": ["INBOX"],
        }
        business_row = {
            **common,
            "thread_id": "business-sent-only-copy",
            "labels": ["SENT"],
        }
        third_row = {
            **common,
            "thread_id": "third-active-copy",
            "labels": ["INBOX"],
        }

        def collect(order):
            def call_tool(name, arguments):
                if name == "list_accounts":
                    return {
                        "accounts": [
                            {"accountEmail": email, "aliases": []}
                            for email in order
                        ]
                    }
                if name == "list_threads":
                    email = arguments["acting_email"]
                    label = arguments["labels"][0]
                    if email == personal and label == "INBOX":
                        return {"threads": [personal_row], "total_estimate": 1}
                    if email == business and label == "SENT":
                        return {"threads": [business_row], "total_estimate": 1}
                    if email == third and label == "INBOX":
                        return {"threads": [third_row], "total_estimate": 1}
                    return {"threads": [], "total_estimate": 0}
                if name == "get_thread":
                    rows_by_identity = {
                        personal: personal_row,
                        business: business_row,
                        third: third_row,
                    }
                    row = rows_by_identity[arguments["acting_email"]]
                    return {
                        **row,
                        "user_is_participant": arguments["acting_email"] != third,
                        "message_count": 1,
                        "messages": [
                            {
                                "message_id": row["last_message_id"],
                                "thread_id": row["thread_id"],
                                "sent_at": row["last_message_at"],
                                "labels": list(row["labels"]),
                                "body": row["snippet"],
                                "from": "customer@example.com",
                                "to": [arguments["acting_email"]],
                            }
                        ],
                    }
                if name == "query_email_and_calendar":
                    return {
                        "answer": "No conflict surfaced.",
                        "sources": [{"id": "calendar-source"}],
                    }
                raise AssertionError(f"write or unexpected Superhuman tool invoked: {name}")

            return brief.build_superhuman_context(call_tool, observed_at=observed_at)

        forward = collect((personal, business, third))
        reverse = collect((third, business, personal))
        business_first = collect((business, personal, third))
        forward_signal = next(
            row for row in forward["signals"]
            if row["last_message_id"] == "shared-external-message"
        )
        reverse_signal = next(
            row for row in reverse["signals"]
            if row["last_message_id"] == "shared-external-message"
        )
        business_first_signal = next(
            row for row in business_first["signals"]
            if row["last_message_id"] == "shared-external-message"
        )
        comparisons = (
            ("proposal", forward_signal, business_first_signal),
            ("signal_id", forward_signal, reverse_signal),
            ("semantic_status", forward_signal, reverse_signal),
            ("confidence", forward_signal, reverse_signal),
            ("action_tags", forward_signal, reverse_signal),
            ("fail_closed_reasons", forward_signal, reverse_signal),
            ("wake", forward_signal, reverse_signal),
            ("proposal", forward_signal, reverse_signal),
        )
        for key, left, right in comparisons:
            with self.subTest(global_merge_field=key):
                self.assertEqual(left[key], right[key])
        self.assertEqual(forward_signal["semantic_status"], "UNKNOWN")
        self.assertEqual(forward_signal["confidence"], "LOW")
        self.assertIn("cross-account classification", forward_signal["wake"])
        self.assertIn(third, forward_signal["wake"])
        self.assertIn("verify the order, return", forward_signal["proposal"])

        personal_mail = brief.superhuman_account_context(forward, personal)
        business_mail = brief.superhuman_account_context(forward, business)
        self.assertEqual(personal_mail["signals"][0]["semantic_status"], "PROPOSAL")
        self.assertIn("reply", personal_mail["signals"][0]["action_tags"])
        self.assertIn(
            "verify the order, return",
            personal_mail["signals"][0]["proposal"],
        )
        self.assertEqual(business_mail["signals"][0]["semantic_status"], "OBSERVED")
        self.assertEqual(business_mail["signals"][0]["action_tags"], [])
        self.assertIn(
            "read the exact source",
            business_mail["signals"][0]["proposal"],
        )
        with mock.patch.object(
            brief,
            "_snowcubes_m12_surface",
            return_value={"name": "M12 cafe-doctor", "state": "unavailable"},
        ):
            companion = brief.collect_snowcubes_context(
                vercel={"available": False},
                board={"revision": 9},
                mail=business_mail,
            )
        reply = companion["surfaces"][0]
        self.assertEqual(reply["state"], "available")
        self.assertIn("No active Snowcubes reply", reply["now"])
        self.assertNotIn("proposal", reply)
        self.assertNotIn("thread_id", reply)
        self.assertNotIn("native_link", reply)

    def test_packet_and_render_have_one_reader_first_mail_section_from_one_read_only_collection(self):
        def signal(signal_id, subject, *, status="PROPOSAL", wake=None):
            return {
                "signal_id": signal_id,
                "last_message_id": f"raw-message-{signal_id}",
                "thread_id": f"raw-thread-{signal_id}",
                "subject": subject,
                "semantic_status": status,
                "confidence": "MEDIUM" if status == "PROPOSAL" else "LOW",
                "source_age_hours": 0.0,
                "message_age_hours": 2.0,
                "last_message_at": "2026-08-14T10:00:00Z",
                "source_identities": ["leojkwan@gmail.com"],
                "proposal": f"Proposal only: review {subject.lower()} before acting.",
                "proposal_only": True,
                "wake": wake,
            }

        urgent = signal("raw-urgent-id", "Reply to the urgent request")
        waiting = signal("raw-waiting-id", "Waiting on the repair answer")
        forgotten = signal(
            "raw-forgotten-id",
            "Driver license renewal",
            status="UNKNOWN",
            wake=(
                "Open Superhuman as leojkwan@gmail.com, read exact thread raw-thread-raw-forgotten-id "
                "including return-label.pdf; action-bearing attachment content unread."
            ),
        )
        order_return = signal("raw-order-id", "Lamp return follow-through")
        proactive = signal("raw-proactive-id", "Snowcubes cafe follow-up")
        mail = {
            "available": True,
            "complete": False,
            "status": "UNKNOWN",
            "all_clear_allowed": False,
            "threads_returned_raw": 1,
            "threads_unique": 1,
            "github_notification_threads": 0,
            "human_or_other_threads": 1,
            "cursor_limit_threads": 0,
            "problems": ["Forgotten-obligation history is not exhaustive."],
            "wake": (
                "Search read-only Superhuman mail before 2026-05-16 for unresolved registration, "
                "driver license, payment, order, and return obligations."
            ),
            "forgotten_horizon": {
                "status": "UNKNOWN",
                "wake": (
                    "Search read-only Superhuman mail before 2026-05-16 for unresolved registration, "
                    "driver license, payment, order, and return obligations."
                ),
            },
            "coverage": [
                {
                    "acting_email": "leojkwan@gmail.com",
                    "status": "COMPLETE",
                    "query_range": {
                        "start_date": "2026-05-16T12:00:00+00:00",
                        "end_date": "2026-08-14T12:00:00+00:00",
                    },
                    "source_age_hours": 0.0,
                    "newest_message_age_hours": 1.0,
                    "pagination": {"pages": 1, "exhausted": True, "truncated": False},
                },
                {
                    "acting_email": "firstbitelabs@gmail.com",
                    "status": "UNKNOWN",
                    "query_range": {
                        "start_date": "2026-05-16T12:00:00+00:00",
                        "end_date": "2026-08-14T12:00:00+00:00",
                    },
                    "source_age_hours": None,
                    "pagination": {"pages": 0, "exhausted": False, "truncated": True},
                    "wake": "Link firstbitelabs@gmail.com in Superhuman.",
                },
            ],
            "signals": [urgent, waiting, forgotten, order_return, proactive],
            "forgotten_obligations": [forgotten],
            "urgent_replies": [urgent],
            "waiting_replies": [waiting],
            "proactive_candidates": [proactive],
            "order_return_follow_up": [order_return],
            "calendar_proposals": [
                {
                    "acting_email": "leojkwan@gmail.com",
                    "summary": "Review one possible calendar conflict.",
                    "status": "UNKNOWN",
                    "confidence": "LOW",
                    "source_age_hours": 0.0,
                    "wake": "Open the exact calendar source before changing anything.",
                    "proposal_only": True,
                }
            ],
        }
        board = {"revision": 23, "entities": [], "claims": []}
        companion = {"observed_at": "2026-08-14T12:00:00Z", "surfaces": []}
        with mock.patch.object(brief, "portfolio_root", return_value=Path("/tmp/portfolio")), \
            mock.patch.object(brief, "collect_repos", return_value=[]), \
            mock.patch.object(brief, "collect_github", return_value=[]), \
            mock.patch.object(brief, "collect_vercel", return_value={"available": False}), \
            mock.patch.object(brief, "collect_supabase", return_value={"available": False}), \
            mock.patch.object(brief, "collect_superhuman_context", return_value=mail) as collect_mail, \
            mock.patch.object(brief, "collect_growth_source_status", return_value={}), \
            mock.patch.object(brief, "build_local_git_health", return_value={"available": True}), \
            mock.patch.object(brief, "build_paint_health", return_value={}), \
            mock.patch.object(brief, "collect_shadow_status_excerpt", return_value="status"), \
            mock.patch.object(brief, "collect_board", return_value=board), \
            mock.patch.object(brief, "_read_board_revision", return_value=23), \
            mock.patch.object(brief, "collect_snowcubes_context", return_value=companion), \
            mock.patch.object(brief, "build_recommendations", return_value=[]), \
            mock.patch.object(brief, "build_chief_of_staff_analysis", return_value={}):
            packet = brief.collect_packet(slot="morning")

        self.assertIs(packet["superhuman_context"], mail)
        collect_mail.assert_called_once_with()
        html = brief.render_html(packet)
        self.assertEqual(html.count("Mail and calendar coverage"), 1)
        self.assertEqual(html.count("What was checked"), 1)
        self.assertNotIn("Coverage mechanics", html)
        self.assertIn("firstbitelabs@gmail.com", html)
        self.assertIn("Review one possible calendar conflict", html)
        for category in (
            "Urgent reply",
            "Waiting reply",
            "Forgotten obligation",
            "Order or return",
            "Proactive Snowcubes candidate",
        ):
            self.assertIn(category, html)
            self.assertLess(html.index(category), html.index("What was checked"))
        self.assertIn("Search read-only Superhuman mail before 2026-05-16", html)
        self.assertIn("leojkwan@gmail.com", html)
        self.assertIn("return-label.pdf", html)
        self.assertIn("action-bearing attachment content unread", html)
        self.assertIn("exact thread", html)
        self.assertIn("Driver license renewal", html)
        self.assertLess(
            html.index("Search read-only Superhuman mail before 2026-05-16"),
            html.index("What was checked"),
        )
        self.assertIn("MEDIUM confidence", html)
        self.assertIn("source observed 0.0h ago", html)
        self.assertIn("newest message 2.0h old", html)
        self.assertIn("Proposal only", html)
        self.assertNotIn("raw-urgent-id", html)
        self.assertNotIn("raw-message-raw-urgent-id", html)
        self.assertNotIn("raw-thread-", html)
        self.assertNotIn("2026-05-16T", html)
        self.assertNotRegex(html, r"\d{4}-\d{2}-\d{2}T")
        self.assertNotIn("1 page", html)
        self.assertNotIn("not exhausted", html)
        self.assertNotIn("cursor", html.lower())
        self.assertNotIn("thread_id", html)
        self.assertNotIn("message_id", html)
        self.assertNotIn("Send reply", html)

    def test_superhuman_projection_does_not_manufacture_a_native_mail_route(self):
        context = {
            "coverage": [
                {
                    "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                    "linked": True,
                    "status": "COMPLETE",
                    "metrics": {},
                }
            ],
            "signals": [
                {
                    "signal_id": "shared-message",
                    "last_message_id": "shared-message",
                    "thread_id": "personal-thread",
                    "subject": "Snowcubes customer follow-up",
                    "kind": "human_or_other",
                    "action_tags": ["reply", "proactive"],
                    "semantic_status": "PROPOSAL",
                    "thread_body_read": True,
                    "source_identities": [
                        brief.SELF_MAIL,
                        brief.SNOWCUBES_BUSINESS_MAIL,
                    ],
                    "source_threads": [
                        {
                            "acting_email": brief.SELF_MAIL,
                            "thread_id": "personal-thread",
                            "last_message_id": "shared-message",
                        },
                        {
                            "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                            "thread_id": "business-thread",
                            "last_message_id": "shared-message",
                        },
                    ],
                    "account_snapshots": [
                        {
                            "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                            "thread_id": "business-thread",
                            "last_message_id": "shared-message",
                            "action_tags": ["reply", "proactive"],
                            "source_labels": ["inbox"],
                            "source_lanes": ["active_inbox"],
                            "semantic_status": "PROPOSAL",
                            "confidence": "MEDIUM",
                            "fail_closed_reasons": [],
                            "thread_body_read": True,
                        }
                    ],
                }
            ],
        }

        business_mail = brief.superhuman_account_context(
            context, brief.SNOWCUBES_BUSINESS_MAIL
        )
        self.assertNotIn("native_link", business_mail["signals"][0])
        with mock.patch.object(brief, "collect_board", return_value={"revision": 9}), \
            mock.patch.object(
                brief,
                "_snowcubes_m12_surface",
                return_value={"name": "M12 cafe-doctor", "state": "unavailable"},
            ):
            companion = brief.collect_snowcubes_context(
                vercel={"available": False},
                board={"revision": 9},
                mail=business_mail,
            )
        reply = companion["surfaces"][0]
        self.assertEqual(reply["state"], "available")
        self.assertIn("Snowcubes customer follow-up", reply["now"])
        self.assertIn("Proposal only", reply["proposal"])
        self.assertNotIn("native_link", reply)
        self.assertNotIn("thread_id", reply)

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

    def test_business_signal_has_account_subject_and_proposal_not_draft(self):
        signal = {
            "subject": "Some Knicks swag from Snowcubes",
            "last_message_at": "2026-08-12T00:17:20Z",
            "kind": "human_or_other",
            "thread_id": "19f5396bf1f4ab27",
            "action_tags": ["reply", "proactive"],
            "semantic_status": "PROPOSAL",
            "thread_body_read": True,
        }
        with mock.patch.object(
            brief,
            "collect_superhuman_context",
            return_value={"available": True, "complete": True, "signals": [signal]},
        ), mock.patch.object(brief, "collect_board", return_value={"revision": 9}), mock.patch.object(
            brief, "_snowcubes_m12_surface", return_value={"name": "M12 cafe-doctor", "state": "unavailable"}
        ):
            context = brief.collect_snowcubes_context(vercel={"available": False})
        reply = context["surfaces"][0]
        self.assertIn(brief.SNOWCUBES_BUSINESS_MAIL, reply["source"])
        self.assertIn(signal["subject"], reply["now"])
        self.assertNotIn("thread_id", reply)
        self.assertNotIn("native_link", reply)
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
        self.assertIn("do not infer an action", reply["wake"])
        self.assertNotIn("native_link", reply)
        self.assertNotIn("proposal", reply)
        self.assertEqual(nurture["state"], "unknown")
        self.assertNotIn("proposal", nurture)

    def test_rendered_companion_shows_proposal_without_manufactured_mail_link(self):
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
                    }
                ]
            },
        }
        html = brief.render_html(packet)
        self.assertNotIn("mail.superhuman.com", html)
        self.assertIn("Proposal only", html)
        self.assertIn("Superhuman business inbox", html)

    def test_evidence_keeps_background_work_out_of_the_reader_story(self):
        html = brief.render_html({
            "slot": "morning",
            "generated_at": "2026-08-12T08:00:00-04:00",
            "board": {"revision": 9, "entities": [], "claims": []},
            "repos": [{"name": "shadow", "dirty": True}],
            "github_open_prs": [],
            "recommendations": [],
            "analysis": {},
            "snowcubes_context": {"surfaces": []},
            "paint_health": {"local_git": {"scanned_roots": 1}},
            "vercel": {"deployments": []},
            "supabase": {"projects": []},
            "superhuman_context": {"available": False},
        })

        self.assertIn("Background work", html)
        self.assertIn("background work", html.lower())
        self.assertNotIn("checked projects", html.lower())
        self.assertNotIn("unfinished local work", html.lower())
        self.assertNotIn("technical inventory", html.lower())

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
        self.assertIn("brief", (change["headline"] + change["fact"] + change["meaning"]).lower())
        prose = json.dumps(change)
        self.assertNotIn("#468", prose)
        self.assertNotIn("root cas", prose.lower())
        self.assertNotIn("plan-scale-live", prose)
        self.assertNotIn("collector", prose.lower())
        self.assertNotIn("pointer files", prose.lower())

    def test_brief_change_fact_keeps_collection_mechanics_private(self):
        fact = brief._material_change_fact(
            "Shadow",
            ["feat(brief): keep the full plan readable for the chief-of-staff brief"],
            [],
        )

        self.assertEqual(
            fact,
            "The brief now keeps the full picture intact when a project is complex, and both editions "
            "follow the same clear, decision-focused standard.",
        )
        self.assertNotIn("collector", fact.lower())
        self.assertNotIn("pointer files", fact.lower())
        self.assertNotIn("editorial contract", fact.lower())

    def test_material_change_evidence_uses_reader_labels_not_activity_counts(self):
        changes = brief.build_material_changes(
            board={"projects": [], "entities": [], "claims": []},
            repos=[
                brief.RepoPaint(
                    name="shadow",
                    path="/private/shadow",
                    recent_commits=["feat(brief): keep the full plan readable"],
                )
            ],
            github=[{
                "title": "Review the reader-first brief copy",
                "url": "https://example.test/review/1",
                "repository": {"nameWithOwner": "leokwan/shadow"},
            }],
            vercel={"available": True, "deployments": []},
        )

        evidence = changes[0]["evidence"]
        self.assertEqual(evidence, ["Source confirmed", "Review in progress"])
        self.assertNotIn("recent source change", " ".join(evidence).lower())
        self.assertNotIn("open review", " ".join(evidence).lower())

    def test_executive_read_does_not_turn_internal_activity_into_the_story(self):
        analysis = brief.build_chief_of_staff_analysis(
            board={"entities": [], "claims": []},
            repos=[
                brief.RepoPaint(
                    name="shadow",
                    path="/private/shadow",
                    dirty=True,
                    recent_commits=["feat(brief): keep the full plan readable"],
                )
            ],
            github=[{
                "title": "Review the reader-first brief copy",
                "url": "https://example.test/review/1",
                "repository": {"nameWithOwner": "leokwan/shadow"},
            }],
            vercel={"available": True, "deployments": [{"state": "READY"}]},
            supabase={"available": True, "projects": [{"status": "HEALTHY"}]},
            mail={"available": False},
            source_health={},
        )

        executive = " ".join(analysis["executive_read"])
        self.assertIn("review work is active", executive.lower())
        self.assertIn("separate kinds of evidence", executive.lower())
        self.assertNotIn("proposed changes", executive.lower())
        self.assertNotIn("unfinished local changes", executive.lower())

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

    def test_architecture_decision_translates_maily_calendar_retirement_for_readers(self):
        raw_decision = (
            "shared Cally retention vs Leo's explicit instruction to retire Cally and use Maily "
            "| winner: M5 `~m5sk` retires both shared Cally and private Cally Leo only after "
            "their calendar selection, conflict, notification, exact-authorization, execute-once, "
            "and provider-ID readback rules move into Maily/Maily Leo and targeted three-host removal "
            "has a recorded rollback | closed 2026-08-14T05:56:09Z"
        )
        analysis = brief.build_chief_of_staff_analysis(
            board={
                "entities": [{
                    "project": "ai-leo",
                    "priority": 1,
                    "decisions": [raw_decision],
                }],
                "claims": [],
            },
            repos=[],
            github=[],
            vercel={"available": True, "deployments": []},
            supabase={"available": True, "projects": []},
            mail={"available": False},
            source_health={},
        )

        decision = analysis["architecture_decisions"][0]
        self.assertEqual(
            decision["decision"],
            "Move personal scheduling into one Leo-facing assistant after its safeguards are preserved.",
        )
        self.assertEqual(
            decision["tradeoff"],
            "keeping two overlapping personal assistants versus one clear front door with safe calendar controls",
        )
        reader_copy = json.dumps(decision)
        self.assertNotIn("~m5sk", reader_copy)
        self.assertNotIn("provider-ID", reader_copy)

    def test_untranslated_architecture_decision_keeps_implementation_private(self):
        raw_decision = (
            "fast host work vs a trustworthy release "
            "| winner: ~ops123 runs `root-cas` on branch feature/fast-host until ACK-42 returns "
            "| opened 2026-08-14T06:00:00Z"
        )
        analysis = brief.build_chief_of_staff_analysis(
            board={
                "entities": [{
                    "project": "resplit-ios",
                    "priority": 1,
                    "decisions": [raw_decision],
                }],
                "claims": [],
            },
            repos=[],
            github=[],
            vercel={"available": True, "deployments": []},
            supabase={"available": True, "projects": []},
            mail={"available": False},
            source_health={},
        )

        decision = analysis["architecture_decisions"][0]
        self.assertEqual(
            decision["decision"],
            "The current operating decision is recorded; its implementation stays in the private plan.",
        )
        self.assertEqual(
            decision["tradeoff"],
            "the practical options remain documented in the current product plan",
        )
        reader_copy = json.dumps(decision)
        self.assertNotIn("~ops123", reader_copy)
        self.assertNotIn("root-cas", reader_copy)
        self.assertNotIn("feature/fast-host", reader_copy)

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

    def test_customer_opportunity_joins_exact_business_thread_and_shopify_order(self):
        mail = {
            "available": True,
            "complete": True,
            "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
            "signals": [
                {
                    "thread_id": "thread-amy",
                    "last_message_id": "message-amy",
                    "stable_provider_identity": True,
                    "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
                    "thread_body_read": True,
                    "semantic_status": "PROPOSAL",
                    "confidence": "MEDIUM",
                    "verified_message_at": "2026-08-15T12:00:00Z",
                    "subject": "How did the first box land?",
                    "action_tags": ["reply", "proactive"],
                    "waiting_direction": (
                        "latest visible message is inbound; Leo is not waiting on them"
                    ),
                    "shopify_order_id": "order-1001",
                    "shopify_customer_id": "customer-amy",
                    "customer_email": "Amy@Example.com",
                    "customer_email_verified": True,
                }
            ],
        }
        shopify = {
            "available": True,
            "complete": True,
            "store": brief.SNOWCUBES_SHOPIFY_STORE,
            "observed_at": "2026-08-15T12:30:00Z",
            "orders": [
                {
                    "order_id": "order-1001",
                    "order_name": "#1001",
                    "customer_id": "customer-amy",
                    "customer_email": "amy@example.com",
                    "customer_email_verified": True,
                    "customer_order_count": 1,
                    "fulfillment_status": "fulfilled",
                    "delivery_status": "delivered",
                    "delivered_at": "2026-08-14T19:00:00Z",
                }
            ],
        }

        result = brief.build_snowcubes_customer_opportunities(
            mail=mail,
            shopify=shopify,
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(result["opportunities"]), 1)
        opportunity = result["opportunities"][0]
        self.assertEqual(opportunity["join_state"], "MATCHED")
        self.assertEqual(opportunity["match_basis"], "exact_order_id")
        self.assertEqual(opportunity["signals"]["first_order"]["state"], "CONFIRMED")
        self.assertEqual(opportunity["signals"]["delivery"]["state"], "CONFIRMED")
        self.assertEqual(opportunity["signals"]["relationship"]["state"], "PROPOSAL")
        self.assertEqual(opportunity["signals"]["waiting_reply"]["state"], "NOT_OBSERVED")
        self.assertEqual(opportunity["signals"]["recovery"]["state"], "NOT_OBSERVED")
        self.assertEqual(opportunity["permission_to_contact"], "UNKNOWN")
        self.assertEqual(opportunity["inventory_state"], "UNKNOWN")
        self.assertEqual(result["no_write_receipt"]["provider_calls"], 0)
        self.assertEqual(opportunity["mail"]["age_hours"], 1.0)
        self.assertEqual(opportunity["shopify"]["age_hours"], 0.5)

    def test_customer_opportunity_missing_shopify_fails_closed(self):
        mail = {
            "available": True,
            "complete": True,
            "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
            "signals": [
                {
                    "thread_id": "thread-delivered-words",
                    "stable_provider_identity": True,
                    "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
                    "thread_body_read": True,
                    "semantic_status": "PROPOSAL",
                    "confidence": "MEDIUM",
                    "last_message_at": "2026-08-15T12:00:00Z",
                    "subject": "Your order was delivered",
                    "action_tags": ["reply", "order_return"],
                }
            ],
        }

        result = brief.build_snowcubes_customer_opportunities(
            mail=mail,
            shopify={"available": False},
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(result["status"], "UNKNOWN")
        opportunity = result["opportunities"][0]
        self.assertEqual(opportunity["join_state"], "UNKNOWN")
        self.assertEqual(opportunity["signals"]["delivery"]["state"], "UNKNOWN")
        self.assertEqual(opportunity["signals"]["first_order"]["state"], "UNKNOWN")
        self.assertEqual(opportunity["signals"]["recovery"]["state"], "NOT_OBSERVED")
        self.assertEqual(opportunity["permission_to_contact"], "UNKNOWN")
        self.assertIn("Shopify order and fulfillment facts are unavailable", result["problems"])

    def test_customer_opportunity_missing_mail_never_grants_contact_permission(self):
        shopify = {
            "available": True,
            "complete": True,
            "store": brief.SNOWCUBES_SHOPIFY_STORE,
            "observed_at": "2026-08-15T12:00:00Z",
            "orders": [
                {
                    "order_id": "order-only",
                    "customer_id": "customer-only",
                    "customer_order_count": 1,
                    "delivery_status": "delivered",
                    "delivered_at": "2026-08-15T11:00:00Z",
                }
            ],
        }

        result = brief.build_snowcubes_customer_opportunities(
            mail={"available": False},
            shopify=shopify,
            observed_at="2026-08-15T13:00:00Z",
        )

        opportunity = result["opportunities"][0]
        self.assertEqual(opportunity["signals"]["first_order"]["state"], "CONFIRMED")
        self.assertEqual(opportunity["signals"]["delivery"]["state"], "CONFIRMED")
        self.assertEqual(opportunity["signals"]["relationship"]["state"], "UNKNOWN")
        self.assertEqual(opportunity["signals"]["waiting_reply"]["state"], "UNKNOWN")
        self.assertEqual(opportunity["permission_to_contact"], "UNKNOWN")
        self.assertEqual(opportunity["join_state"], "UNKNOWN")

    def test_customer_opportunity_dedupes_only_stable_provider_identities(self):
        signal = {
            "thread_id": "thread-one",
            "last_message_id": "message-one",
            "stable_provider_identity": True,
            "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
            "thread_body_read": True,
            "semantic_status": "PROPOSAL",
            "confidence": "MEDIUM",
            "last_message_at": "2026-08-15T12:00:00Z",
            "action_tags": ["waiting_reply"],
            "waiting_direction": (
                "last visible message sent by Leo with an explicit response expectation"
            ),
            "shopify_order_id": "order-one",
        }
        order = {
            "order_id": "order-one",
            "customer_order_count": 2,
            "fulfillment_status": "fulfilled",
        }
        result = brief.build_snowcubes_customer_opportunities(
            mail={
                "available": True,
                "complete": True,
                "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                "signals": [signal, dict(signal)],
            },
            shopify={
                "available": True,
                "complete": True,
                "store": brief.SNOWCUBES_SHOPIFY_STORE,
                "orders": [order, dict(order)],
            },
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(len(result["opportunities"]), 1)
        opportunity = result["opportunities"][0]
        self.assertEqual(opportunity["signals"]["waiting_reply"]["state"], "PROPOSAL")
        self.assertEqual(opportunity["signals"]["first_order"]["state"], "NOT_FIRST")
        self.assertEqual(opportunity["signals"]["delivery"]["state"], "UNKNOWN")
        self.assertEqual(opportunity["customer_identity"]["state"], "UNKNOWN")

    def test_customer_opportunity_verified_email_requires_one_unambiguous_order(self):
        mail_signal = {
            "thread_id": "thread-email",
            "stable_provider_identity": True,
            "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
            "thread_body_read": True,
            "semantic_status": "OBSERVED",
            "confidence": "MEDIUM",
            "customer_email": "customer@example.com",
            "customer_email_verified": True,
        }
        shopify_orders = [
            {
                "order_id": f"order-{index}",
                "customer_email": "customer@example.com",
                "customer_email_verified": True,
            }
            for index in (1, 2)
        ]

        result = brief.build_snowcubes_customer_opportunities(
            mail={
                "available": True,
                "complete": True,
                "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                "signals": [mail_signal],
            },
            shopify={
                "available": True,
                "complete": True,
                "store": brief.SNOWCUBES_SHOPIFY_STORE,
                "orders": shopify_orders,
            },
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(len(result["opportunities"]), 3)
        self.assertTrue(all(row["join_state"] == "UNKNOWN" for row in result["opportunities"]))

    def test_customer_opportunity_rejects_wrong_accounts_and_future_source_age(self):
        result = brief.build_snowcubes_customer_opportunities(
            mail={
                "available": True,
                "complete": True,
                "acting_email": "leojkwan@gmail.com",
                "signals": [],
            },
            shopify={
                "available": True,
                "complete": True,
                "store": brief.SNOWCUBES_SHOPIFY_STORE,
                "observed_at": "2026-08-16T13:00:00Z",
                "orders": [
                    {
                        "order_id": "future-order",
                        "delivery_status": "delivered",
                        "delivered_at": "2026-08-16T12:00:00Z",
                    }
                ],
            },
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(result["source_status"]["superhuman"], "UNAVAILABLE")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["opportunities"][0]["shopify"]["age_hours"])
        self.assertEqual(
            result["opportunities"][0]["signals"]["delivery"]["state"],
            "UNKNOWN",
        )
        self.assertIn("mail source is not the Snowcubes business account", result["problems"])

    def test_customer_opportunity_conflicting_order_identity_fails_closed(self):
        mail_signal = {
            "thread_id": "thread-collision",
            "stable_provider_identity": True,
            "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
            "thread_body_read": True,
            "semantic_status": "PROPOSAL",
            "confidence": "MEDIUM",
            "shopify_order_id": "order-collision",
            "shopify_customer_id": "customer-one",
        }
        orders = [
            {
                "order_id": "order-collision",
                "customer_id": customer_id,
                "customer_order_count": 1,
            }
            for customer_id in ("customer-one", "customer-two")
        ]

        result = brief.build_snowcubes_customer_opportunities(
            mail={
                "available": True,
                "complete": True,
                "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                "signals": [mail_signal],
            },
            shopify={
                "available": True,
                "complete": True,
                "store": brief.SNOWCUBES_SHOPIFY_STORE,
                "orders": orders,
            },
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(result["status"], "UNKNOWN")
        self.assertTrue(all(row["join_state"] == "UNKNOWN" for row in result["opportunities"]))
        self.assertIn(
            "conflicting duplicate Shopify order identity: order-collision",
            result["problems"],
        )

    def test_customer_opportunity_conflicting_thread_revision_is_order_independent(self):
        base = {
            "thread_id": "thread-revision",
            "stable_provider_identity": True,
            "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
            "thread_body_read": True,
            "semantic_status": "PROPOSAL",
            "confidence": "MEDIUM",
            "shopify_order_id": "order-revision",
        }
        versions = [
            {**base, "last_message_id": "message-one"},
            {**base, "last_message_id": "message-two"},
        ]
        shopify = {
            "available": True,
            "complete": True,
            "store": brief.SNOWCUBES_SHOPIFY_STORE,
            "orders": [
                {
                    "order_id": "order-revision",
                    "customer_id": "customer-revision",
                }
            ],
        }

        def build(rows):
            return brief.build_snowcubes_customer_opportunities(
                mail={
                    "available": True,
                    "complete": True,
                    "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                    "signals": rows,
                },
                shopify=shopify,
                observed_at="2026-08-15T13:00:00Z",
            )

        forward = build(versions)
        reverse = build(list(reversed(versions)))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward["status"], "UNKNOWN")
        self.assertTrue(all(row["join_state"] == "UNKNOWN" for row in forward["opportunities"]))
        self.assertIn(
            "conflicting duplicate Superhuman thread identity: thread-revision",
            forward["problems"],
        )

    def test_customer_opportunity_customer_conflict_and_direction_tags_fail_closed(self):
        result = brief.build_snowcubes_customer_opportunities(
            mail={
                "available": True,
                "complete": True,
                "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                "signals": [
                    {
                        "thread_id": "thread-mismatch",
                        "stable_provider_identity": True,
                        "source_identities": [brief.SNOWCUBES_BUSINESS_MAIL],
                        "thread_body_read": True,
                        "semantic_status": "PROPOSAL",
                        "confidence": "MEDIUM",
                        "action_tags": ["waiting_reply", "reply", "order_return"],
                        "shopify_order_id": "order-mismatch",
                        "shopify_customer_id": "mail-customer",
                    }
                ],
            },
            shopify={
                "available": True,
                "complete": True,
                "store": brief.SNOWCUBES_SHOPIFY_STORE,
                "orders": [
                    {
                        "order_id": "order-mismatch",
                        "customer_id": "shopify-customer",
                    }
                ],
            },
            observed_at="2026-08-15T13:00:00Z",
        )

        self.assertEqual(result["status"], "UNKNOWN")
        mail_only = next(row for row in result["opportunities"] if row["mail"].get("thread_id"))
        self.assertEqual(mail_only["join_state"], "UNKNOWN")
        self.assertEqual(mail_only["signals"]["waiting_reply"]["state"], "NOT_OBSERVED")
        self.assertEqual(mail_only["signals"]["relationship"]["state"], "NOT_OBSERVED")
        self.assertEqual(mail_only["signals"]["recovery"]["state"], "NOT_OBSERVED")
        self.assertIn("mail and Shopify customer IDs conflict", result["problems"])


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
    def test_owner_control_progress_survives_the_recent_progress_cap(self):
        old_controls = [
            "2026-08-15T14:00:00Z SCHEDULER DISABLED BY LEO -> keep it off",
            "2026-08-15T14:04:00Z MODEL-AUTHOR CONTRACT CORRECTION -> Codex or Claude writes it",
        ]
        newer = [
            f"2026-08-15T15:{index:02d}:00Z ordinary progress {index}"
            for index in range(10)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            plan.write_text(
                "## Brief\n- Project: ai-leo\n- Mode: ship\n\n"
                "## Tasks\n### Brief\n"
                "- [pending] Produce a useful brief ~br01 | proof: read artifact -> useful\n"
                "- [pending] Close the brief ~br02 (DoD) | proof: read artifact -> complete | needs: ~br01\n\n"
                "## Deferred\n\n## Contradictions\n\n## Progress\n"
                + "".join(f"- {line}\n" for line in [*old_controls, *newer]),
                encoding="utf-8",
            )

            parsed = brief.parse_plan(plan)

        self.assertEqual(parsed.recent_progress[:4], newer[-4:])
        self.assertEqual(parsed.recent_progress[-2:], old_controls)

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

    def test_collect_board_fails_closed_when_json_parser_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text('{"revision": 1}\n', encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path), mock.patch.object(
                brief.json,
                "loads",
                side_effect=ValueError("integer string conversion limit exceeded"),
            ):
                result = brief.collect_board()

        self.assertIsNone(result["revision"])
        self.assertEqual(result["entities"], [])
        self.assertIn("board unreadable", result["error"])
        self.assertIn("integer string conversion limit exceeded", result["error"])
        self.assertIn("Restore a readable local Shadow board", result["wake"])

    def test_collect_board_fails_closed_when_json_parser_recurses_too_deeply(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text('{"revision": 1}\n', encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path), mock.patch.object(
                brief.json,
                "loads",
                side_effect=RecursionError("maximum recursion depth exceeded"),
            ):
                result = brief.collect_board()

        self.assertIsNone(result["revision"])
        self.assertEqual(result["entities"], [])
        self.assertIn("board unreadable", result["error"])
        self.assertIn("maximum recursion depth exceeded", result["error"])
        self.assertIn("Restore a readable local Shadow board", result["wake"])

    def test_collect_board_fails_closed_when_json_root_is_not_an_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text("[]\n", encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path):
                result = brief.collect_board()

        self.assertIsNone(result["revision"])
        self.assertEqual(result["entities"], [])
        self.assertIn("board unreadable", result["error"])
        self.assertIn("JSON object", result["error"])
        self.assertIn("Restore a readable local Shadow board", result["wake"])

    def test_collect_board_fails_closed_on_malformed_nested_schema(self):
        base = {
            "revision": 1,
            "projects": [],
            "entities": [],
            "claims": [],
        }
        cases = (
            ("projects-container", {**base, "projects": 7}),
            ("entities-container", {**base, "entities": 7}),
            ("claims-container", {**base, "claims": 7}),
            ("project-row", {**base, "projects": [None]}),
            ("entity-row", {**base, "entities": [None]}),
            ("claim-row", {**base, "claims": [None]}),
            (
                "entity-plan",
                {
                    **base,
                    "entities": [
                        {"id": "entity", "project": "project", "plan": []}
                    ],
                },
            ),
        )
        for name, payload in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                board_path = Path(tmp) / "board.json"
                board_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                with mock.patch.object(brief, "BOARD_PATH", board_path):
                    try:
                        result = brief.collect_board()
                    except (AttributeError, TypeError) as exc:
                        self.fail(f"JSON-valid nested board shape crashed: {exc}")

                self.assertIsNone(result["revision"])
                self.assertEqual(result["projects"], [])
                self.assertEqual(result["entities"], [])
                self.assertEqual(result["claims"], [])
                self.assertIn("board unreadable", result["error"])
                self.assertIn("Restore a readable local Shadow board", result["wake"])

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
        mail = {
            "available": True,
            "status": "UNKNOWN",
            "problems": ["business mail unavailable"],
            "coverage": [
                {
                    "acting_email": brief.SNOWCUBES_BUSINESS_MAIL,
                    "linked": True,
                    "status": "UNKNOWN",
                    "problems": ["business mail unavailable"],
                    "wake": "Restore the read-only business-mail source.",
                    "metrics": {},
                }
            ],
            "signals": [],
        }
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
                return_value=mail,
            ) as collect_mail, \
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
        self.assertTrue(packet["paint_health"]["superhuman"]["available"])
        self.assertEqual(packet["superhuman_context"]["status"], "UNKNOWN")
        self.assertIs(collect_companion.call_args.kwargs["board"], packet["board"])
        self.assertEqual(collect_mail.call_count, 1)
        self.assertEqual(
            collect_companion.call_args.kwargs["mail"]["acting_email"],
            brief.SNOWCUBES_BUSINESS_MAIL,
        )
        self.assertIn(
            "business mail unavailable",
            collect_companion.call_args.kwargs["mail"]["error"],
        )
        self.assertNotIn("nia", packet)
        self.assertNotIn("nia", packet["paint_health"])
        self.assertEqual(
            set((packet.get("producer") or {}).keys()),
            {"schema", "source_commit", "script_sha256", "source_matches_commit"},
        )

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

    def test_producer_provenance_rejects_noncanonical_git_object_id_lengths(self):
        candidate = "a" * 41

        def run(argv, **_kwargs):
            if argv[-2:] == ["rev-parse", "--show-toplevel"]:
                return subprocess.CompletedProcess(argv, 0, f"{ROOT}\n", "")
            if argv[-2:] == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(argv, 0, f"{candidate}\n", "")
            if "status" in argv:
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 0, f"{'b' * 40}\n", "")

        with mock.patch.object(brief, "_run", side_effect=run):
            provenance = brief.producer_provenance()

        self.assertIsNone(provenance["source_commit"])
        self.assertFalse(provenance["source_matches_commit"])

    def test_producer_provenance_turns_every_git_probe_failure_into_invalid_receipt(self):
        def successful(argv):
            if argv[-2:] == ["rev-parse", "--show-toplevel"]:
                return subprocess.CompletedProcess(argv, 0, f"{ROOT}\n", "")
            if argv[-2:] == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(argv, 0, f"{'a' * 40}\n", "")
            if "status" in argv:
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 0, f"{'b' * 40}\n", "")

        for failure_index in range(5):
            for failure_type in ("oserror", "timeout"):
                with self.subTest(
                    failure_index=failure_index,
                    failure_type=failure_type,
                ):
                    calls = 0

                    def run(argv, **_kwargs):
                        nonlocal calls
                        index = calls
                        calls += 1
                        if index == failure_index:
                            if failure_type == "oserror":
                                raise OSError(f"git probe {failure_index} unavailable")
                            raise subprocess.TimeoutExpired(argv, 30)
                        return successful(argv)

                    with mock.patch.object(brief, "_run", side_effect=run):
                        try:
                            provenance = brief.producer_provenance()
                        except (OSError, subprocess.TimeoutExpired) as exc:
                            self.fail(f"producer provenance probe escaped: {exc}")

                    self.assertFalse(brief._valid_producer_provenance(provenance))
                    self.assertFalse(provenance["source_matches_commit"])
                    self.assertEqual(len(provenance["script_sha256"]), 64)

    def test_launch_trigger_requires_exact_xpc_service_and_current_launchctl_job_pid(self):
        commands = []
        expected_arguments = brief.launch_agent_plist(Path(brief.__file__).resolve())[
            "ProgramArguments"
        ]
        home = Path.home()
        expected_plist = home / "Library" / "LaunchAgents" / f"{brief.LABEL}.plist"
        uid = os.getuid()

        def run(argv, **_kwargs):
            commands.append(argv)
            if Path(argv[0]).name == "ps":
                return subprocess.CompletedProcess(argv, 0, "/sbin/launchd\n", "")
            if Path(argv[0]).name == "launchctl" and argv[1] == "print":
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    f"gui/{uid}/com.leokwan.shadow-bidaily-brief = {{\n"
                    f"\tprogram = {expected_arguments[0]}\n"
                    "\targuments = {\n"
                    + "".join(
                        f"\t\t{argument}\n" for argument in expected_arguments
                    )
                    + "\t}\n"
                    f"\tpath = {expected_plist}\n"
                    "\tpid = 4242\n"
                    "}\n",
                    "",
                )
            raise AssertionError(argv)

        with mock.patch.dict(
            os.environ,
            {
                "XPC_SERVICE_NAME": "com.leokwan.shadow-bidaily-brief",
                "HOME": str(home),
            },
            clear=True,
        ), mock.patch.object(brief.os, "getpid", return_value=4242), mock.patch.object(
            brief.os, "getppid", return_value=1
        ), mock.patch.object(brief.os, "getuid", return_value=uid), mock.patch.object(
            brief, "_run", side_effect=run
        ):
            proof = brief.launch_trigger_proof()

        self.assertTrue(brief.scheduled_trigger_is_authorized(True, proof))
        self.assertEqual(proof.get("label"), "com.leokwan.shadow-bidaily-brief")
        self.assertEqual(proof.get("domain"), f"gui/{uid}")
        self.assertEqual(proof.get("current_pid"), 4242)
        self.assertEqual(proof.get("job_pid"), 4242)
        self.assertEqual(proof.get("loaded_program_arguments"), expected_arguments)
        self.assertEqual(proof.get("loaded_path"), str(expected_plist))
        self.assertTrue(proof.get("loaded_command_matches"))
        self.assertTrue(proof.get("exact_job"))
        self.assertEqual(commands[0][0], "/bin/ps")
        self.assertEqual(commands[1][0], "/bin/launchctl")

        parent_only = {
            "is_launchd": True,
            "parent_pid": 1,
            "parent_command": "/sbin/launchd",
        }
        self.assertFalse(brief.scheduled_trigger_is_authorized(True, parent_only))
        self.assertFalse(
            brief.scheduled_trigger_is_authorized(
                True,
                {**proof, "xpc_service_name": "com.example.lookalike"},
            )
        )
        self.assertFalse(
            brief.scheduled_trigger_is_authorized(True, {**proof, "job_pid": 4243})
        )
        boolean_pid_cases = (
            ("parent_pid", {**proof, "parent_pid": True}),
            (
                "current_pid",
                {**proof, "current_pid": True, "job_pid": True},
            ),
            (
                "job_pid",
                {**proof, "current_pid": 1, "job_pid": True},
            ),
        )
        for field, malformed in boolean_pid_cases:
            with self.subTest(boolean_pid=field):
                self.assertFalse(
                    brief.scheduled_trigger_is_authorized(True, malformed)
                )
        self.assertFalse(
            brief.scheduled_trigger_is_authorized(
                True,
                {
                    **proof,
                    "loaded_program_arguments": [
                        expected_arguments[0],
                        "/old/replacement/shadow-brief.py",
                        *expected_arguments[2:],
                    ],
                    "loaded_command_matches": False,
                },
            )
        )

    def test_launch_trigger_rejects_ambiguous_launchctl_pid_output(self):
        def run(argv, **_kwargs):
            if Path(argv[0]).name == "ps":
                return subprocess.CompletedProcess(argv, 0, "/sbin/launchd\n", "")
            return subprocess.CompletedProcess(
                argv,
                0,
                "gui/501/com.leokwan.shadow-bidaily-brief = {\n\tpid = 4242\n\tpid = 4243\n}\n",
                "",
            )

        with mock.patch.dict(
            os.environ,
            {"XPC_SERVICE_NAME": "com.leokwan.shadow-bidaily-brief"},
            clear=True,
        ), mock.patch.object(brief.os, "getpid", return_value=4242), mock.patch.object(
            brief.os, "getppid", return_value=1
        ), mock.patch.object(brief.os, "getuid", return_value=501), mock.patch.object(
            brief, "_run", side_effect=run
        ):
            proof = brief.launch_trigger_proof()

        self.assertIsNone(proof.get("job_pid"))
        self.assertFalse(proof.get("exact_job"))
        self.assertFalse(brief.scheduled_trigger_is_authorized(True, proof))

    def test_launch_trigger_probe_failures_return_blocked_structured_proof(self):
        cases = (
            ("ps-oserror", "/bin/ps", OSError("ps unavailable"), "ps"),
            (
                "ps-timeout",
                "/bin/ps",
                subprocess.TimeoutExpired(["/bin/ps"], 5),
                "ps",
            ),
            (
                "launchctl-oserror",
                "/bin/launchctl",
                OSError("launchctl unavailable"),
                "launchctl",
            ),
            (
                "launchctl-timeout",
                "/bin/launchctl",
                subprocess.TimeoutExpired(["/bin/launchctl"], 5),
                "launchctl",
            ),
        )
        for name, failing_program, failure, expected_probe in cases:
            with self.subTest(name=name):
                def run(argv, **_kwargs):
                    if argv[0] == failing_program:
                        raise failure
                    if argv[0] == "/bin/ps":
                        return subprocess.CompletedProcess(
                            argv, 0, "/sbin/launchd\n", ""
                        )
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        "gui/501/com.leokwan.shadow-bidaily-brief = {\n"
                        "\tpid = 4242\n}\n",
                        "",
                    )

                with mock.patch.dict(
                    os.environ,
                    {"XPC_SERVICE_NAME": brief.LABEL},
                    clear=True,
                ), mock.patch.object(
                    brief.os, "getpid", return_value=4242
                ), mock.patch.object(
                    brief.os, "getppid", return_value=1
                ), mock.patch.object(
                    brief.os, "getuid", return_value=501
                ), mock.patch.object(
                    brief, "_run", side_effect=run
                ):
                    try:
                        proof = brief.launch_trigger_proof()
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        self.fail(f"launch trigger proof leaked {type(exc).__name__}: {exc}")

                self.assertFalse(proof["exact_job"])
                self.assertFalse(proof["is_launchd"])
                self.assertIn(expected_probe, proof["probe_errors"])

    def test_launch_trigger_fails_closed_when_expected_job_cannot_resolve(self):
        def run(argv, **_kwargs):
            if Path(argv[0]).name == "ps":
                return subprocess.CompletedProcess(argv, 0, "/sbin/launchd\n", "")
            return subprocess.CompletedProcess(
                argv,
                0,
                "gui/501/com.leokwan.shadow-bidaily-brief = {\n"
                "\tprogram = /usr/bin/python3\n"
                "\targuments = {\n\t\t/usr/bin/python3\n\t}\n"
                "\tpath = /tmp/com.leokwan.shadow-bidaily-brief.plist\n"
                "\tpid = 4242\n}\n",
                "",
            )

        with mock.patch.dict(
            os.environ,
            {"XPC_SERVICE_NAME": brief.LABEL},
            clear=True,
        ), mock.patch.object(brief.os, "getpid", return_value=4242), mock.patch.object(
            brief.os, "getppid", return_value=1
        ), mock.patch.object(brief.os, "getuid", return_value=501), mock.patch.object(
            brief,
            "launch_agent_plist",
            side_effect=RuntimeError("Could not determine home directory."),
        ), mock.patch.object(brief, "_run", side_effect=run):
            try:
                proof = brief.launch_trigger_proof()
            except RuntimeError as exc:
                self.fail(f"launch trigger proof leaked home failure: {exc}")

        self.assertFalse(proof["loaded_command_matches"])
        self.assertFalse(proof["exact_job"])
        self.assertFalse(proof["is_launchd"])
        self.assertIn("expected_job", proof["probe_errors"])
        self.assertFalse(brief.scheduled_trigger_is_authorized(True, proof))

    def test_authorization_fails_closed_when_expected_job_later_cannot_resolve(self):
        expected_job = brief._expected_loaded_job()
        pid = os.getpid()
        proof = {
            "is_launchd": True,
            "parent_pid": 1,
            "parent_command": "/sbin/launchd",
            "label": brief.LABEL,
            "domain": f"gui/{os.getuid()}",
            "current_pid": pid,
            "job_pid": pid,
            "xpc_service_name": brief.LABEL,
            "service_matches_label": True,
            "loaded_program": expected_job["program"],
            "loaded_program_arguments": expected_job["arguments"],
            "loaded_path": expected_job["path"],
            "loaded_command_matches": True,
            "exact_job": True,
        }

        with mock.patch.object(
            brief,
            "_expected_loaded_job",
            side_effect=RuntimeError("Could not determine home directory."),
        ):
            self.assertFalse(brief._loaded_job_matches_current(expected_job))
            self.assertFalse(brief.scheduled_trigger_is_authorized(True, proof))

    def test_scheduled_command_emits_blocked_proof_when_launch_probe_fails(self):
        def run(argv, **_kwargs):
            if argv[0] == "/bin/ps":
                raise OSError("ps unavailable")
            return subprocess.CompletedProcess(argv, 1, "", "not loaded")

        stderr = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {"XPC_SERVICE_NAME": brief.LABEL},
            clear=True,
        ), mock.patch.object(brief, "_run", side_effect=run), contextlib.redirect_stderr(stderr):
            try:
                exit_code = brief.cmd_run(mock.Mock(scheduled_trigger=True))
            except OSError as exc:
                self.fail(f"scheduled command leaked launch probe error: {exc}")

        emitted = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(emitted["status"], "blocked")
        self.assertFalse(emitted["trigger_proof"]["exact_job"])
        self.assertIn("ps", emitted["trigger_proof"]["probe_errors"])

    def test_scheduled_run_lock_rejects_second_invocation_before_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "scheduled-run.lock"
            descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            collect = mock.Mock(
                return_value={
                    "generated_at": "2026-08-12T08:05:00-04:00",
                    "board": {"revision": 1},
                    "authority": {"board_snapshot": {"consistent": False}},
                }
            )
            proof = _scheduled_proof_fixture()
            args = mock.Mock(scheduled_trigger=True)
            try:
                with mock.patch.object(brief, "LOG_DIR", root), mock.patch.object(
                    brief, "EVIDENCE_DIR", root / "evidence"
                ), mock.patch.object(
                    brief, "launch_trigger_proof", return_value=proof
                ), mock.patch.object(
                    brief, "collect_packet", collect
                ), contextlib.redirect_stderr(io.StringIO()):
                    exit_code = brief.cmd_run(args)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

        self.assertEqual(exit_code, 3)
        self.assertEqual(collect.call_count, 0)

    def test_scheduled_run_lock_rejects_a_preplaced_hard_link_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "unrelated-private-state"
            target.write_text("do not touch", encoding="utf-8")
            target.chmod(0o640)
            os.link(target, root / "scheduled-run.lock")
            original_mode = stat.S_IMODE(target.stat().st_mode)
            collect = mock.Mock(
                return_value={
                    "generated_at": "2026-08-12T08:05:00-04:00",
                    "board": {"revision": 1},
                    "authority": {"board_snapshot": {"consistent": False}},
                }
            )
            proof = _scheduled_proof_fixture()
            with mock.patch.object(brief, "LOG_DIR", root), mock.patch.object(
                brief, "EVIDENCE_DIR", root / "evidence"
            ), mock.patch.object(
                brief, "launch_trigger_proof", return_value=proof
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), contextlib.redirect_stderr(io.StringIO()):
                exit_code = brief.cmd_run(mock.Mock(scheduled_trigger=True))
            resulting_mode = stat.S_IMODE(target.stat().st_mode)
            resulting_content = target.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 3)
        self.assertEqual(collect.call_count, 0)
        self.assertEqual(resulting_mode, original_mode)
        self.assertEqual(resulting_content, "do not touch")

    def test_scheduled_run_lock_revalidates_the_canonical_name_after_flock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "scheduled-run.lock"
            displaced = root / "displaced-run.lock"
            collect = mock.Mock(
                return_value={
                    "generated_at": "2026-08-12T08:05:00-04:00",
                    "board": {"revision": 1},
                    "authority": {"board_snapshot": {"consistent": False}},
                }
            )
            proof = _scheduled_proof_fixture()
            window = {
                "on_schedule": True,
                "slot": "morning",
                "scheduled_for": "2026-08-12T08:00:00-04:00",
            }
            real_flock = fcntl.flock
            swapped = False

            def swap_name_after_lock(descriptor, operation):
                nonlocal swapped
                real_flock(descriptor, operation)
                if operation == fcntl.LOCK_EX | fcntl.LOCK_NB and not swapped:
                    lock_path.replace(displaced)
                    lock_path.write_text("replacement", encoding="utf-8")
                    swapped = True

            with mock.patch.object(brief, "LOG_DIR", root), mock.patch.object(
                brief, "WINDOW_LOG", root / "windows.jsonl"
            ), mock.patch.object(
                brief, "EVIDENCE_DIR", root / "evidence"
            ), mock.patch.object(
                brief, "launch_trigger_proof", return_value=proof
            ), mock.patch.object(
                brief, "scheduled_window", return_value=window
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), mock.patch.object(
                brief.fcntl, "flock", side_effect=swap_name_after_lock
            ), contextlib.redirect_stderr(io.StringIO()):
                exit_code = brief.cmd_run(mock.Mock(scheduled_trigger=True))

            replacement = os.open(lock_path, os.O_RDWR)
            try:
                real_flock(replacement, fcntl.LOCK_EX | fcntl.LOCK_NB)
                real_flock(replacement, fcntl.LOCK_UN)
            finally:
                os.close(replacement)
            displaced_descriptor = os.open(displaced, os.O_RDWR)
            try:
                real_flock(
                    displaced_descriptor,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                real_flock(displaced_descriptor, fcntl.LOCK_UN)
            finally:
                os.close(displaced_descriptor)

        self.assertTrue(swapped)
        self.assertEqual(exit_code, 3)
        self.assertEqual(collect.call_count, 0)

    def test_scheduled_run_lock_closes_descriptor_without_masking_setup_failure(self):
        real_open = os.open
        real_fstat = os.fstat
        real_fchmod = os.fchmod
        real_flock = fcntl.flock

        for stage in ("fstat", "fchmod", "flock"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                opened: list[int] = []

                def record_open(*args, **kwargs):
                    descriptor = real_open(*args, **kwargs)
                    opened.append(descriptor)
                    return descriptor

                def fail_fstat(descriptor):
                    if stage == "fstat":
                        raise OSError("original fstat setup failure")
                    return real_fstat(descriptor)

                def fail_fchmod(descriptor, mode):
                    if stage == "fchmod":
                        raise OSError("original fchmod setup failure")
                    return real_fchmod(descriptor, mode)

                def fail_flock(descriptor, operation):
                    if stage == "flock" and operation & fcntl.LOCK_EX:
                        raise OSError("original flock setup failure")
                    return real_flock(descriptor, operation)

                with mock.patch.object(brief, "LOG_DIR", root), mock.patch.object(
                    brief.os, "open", side_effect=record_open
                ), mock.patch.object(
                    brief.os, "fstat", side_effect=fail_fstat
                ), mock.patch.object(
                    brief.os, "fchmod", side_effect=fail_fchmod
                ), mock.patch.object(
                    brief.fcntl, "flock", side_effect=fail_flock
                ):
                    with self.assertRaisesRegex(OSError, f"original {stage} setup failure"):
                        brief._acquire_scheduled_run_lock()

                self.assertEqual(len(opened), 1)
                with self.assertRaises(OSError):
                    real_fstat(opened[0])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            opened = []
            fstat_calls = 0

            def record_open(*args, **kwargs):
                descriptor = real_open(*args, **kwargs)
                opened.append(descriptor)
                return descriptor

            def fail_post_lock_fstat(descriptor):
                nonlocal fstat_calls
                fstat_calls += 1
                if fstat_calls == 2:
                    raise OSError("original post-lock identity failure")
                return real_fstat(descriptor)

            def fail_cleanup_unlock(descriptor, operation):
                if operation == fcntl.LOCK_UN:
                    raise OSError("cleanup unlock failure")
                return real_flock(descriptor, operation)

            with mock.patch.object(brief, "LOG_DIR", root), mock.patch.object(
                brief.os, "open", side_effect=record_open
            ), mock.patch.object(
                brief.os, "fstat", side_effect=fail_post_lock_fstat
            ), mock.patch.object(
                brief.fcntl, "flock", side_effect=fail_cleanup_unlock
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "original post-lock identity failure",
                ):
                    brief._acquire_scheduled_run_lock()

            self.assertEqual(len(opened), 1)
            with self.assertRaises(OSError):
                real_fstat(opened[0])

    def test_scheduled_run_lock_release_never_masks_the_run_result_or_exception(self):
        proof = _scheduled_proof_fixture()
        for outcome in ("result", "exception"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                descriptor = os.open(
                    root / "held-run.lock",
                    os.O_RDWR | os.O_CREAT,
                    0o600,
                )
                handle = os.fdopen(descriptor, "r+", encoding="utf-8")
                run = mock.Mock(
                    return_value=3,
                    side_effect=(
                        RuntimeError("original scheduled run failure")
                        if outcome == "exception"
                        else None
                    ),
                )

                def fail_unlock(_descriptor, operation):
                    self.assertEqual(operation, fcntl.LOCK_UN)
                    raise OSError("scheduled lock cleanup unavailable")

                with mock.patch.object(brief, "EVIDENCE_DIR", root / "evidence"), mock.patch.object(
                    brief, "LOG_DIR", root / "ledger"
                ), mock.patch.object(
                    brief, "launch_trigger_proof", return_value=proof
                ), mock.patch.object(
                    brief, "_acquire_scheduled_run_lock", return_value=handle
                ), mock.patch.object(
                    brief, "_cmd_run_locked", run
                ), mock.patch.object(
                    brief.fcntl, "flock", side_effect=fail_unlock
                ):
                    if outcome == "result":
                        try:
                            exit_code = brief.cmd_run(mock.Mock(scheduled_trigger=True))
                        except OSError as exc:
                            self.fail(f"lock release masked completed result: {exc}")
                        self.assertEqual(exit_code, 3)
                    else:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "original scheduled run failure",
                        ):
                            brief.cmd_run(mock.Mock(scheduled_trigger=True))

                self.assertTrue(handle.closed)

    def test_scheduled_archive_is_exclusive_read_only_and_the_delivery_source(self):
        class FrozenDateTime(brief.datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromisoformat("2026-08-14T08:05:00-04:00")
                return value if tz is None else value.astimezone(tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            packet = {
                "generated_at": "2026-08-12T08:05:00-04:00",
                "slot": "morning",
                "board": {"revision": 41, "entities": [], "claims": []},
                "authority": {"board_snapshot": {"consistent": True, "revision": 41}},
                "paint_health": {},
                "producer": _m5_producer_fixture(),
                "superhuman_context": _m5_mail_fixture(),
                "repos": [],
                "github_open_prs": [],
                "recommendations": [],
                "analysis": {},
                "snowcubes_context": {"surfaces": []},
            }
            trigger_window = {
                "on_schedule": True,
                "slot": "morning",
                "scheduled_for": "2026-08-12T08:00:00-04:00",
            }
            proof = _scheduled_proof_fixture()
            delivered = {
                "status": "ok",
                "delivery_status": "sent",
                "message_id": "sent-once",
            }
            deliver = mock.Mock(return_value=delivered)
            notify = mock.Mock(return_value={"status": "ok"})
            collect = mock.Mock(return_value=packet)
            append_lock_states = []
            appended_summaries = []

            def append_while_locked(summary, *_args, **_kwargs):
                appended_summaries.append(summary)
                descriptor = os.open(ledger / "scheduled-run.lock", os.O_RDWR)
                try:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        append_lock_states.append("held")
                    else:
                        append_lock_states.append("free")
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "datetime", FrozenDateTime
            ), mock.patch.object(
                brief, "launch_trigger_proof", return_value=proof
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), mock.patch.object(
                brief, "scheduled_window", return_value=trigger_window
            ), mock.patch.object(
                brief, "macos_notify", notify
            ), mock.patch.object(
                brief, "deliver_superhuman", deliver
            ), mock.patch.object(
                brief, "append_scheduled_window", side_effect=append_while_locked
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                first_exit = brief.cmd_run(args)
                archive = next(evidence.glob("brief-*.html"))
                first_bytes = archive.read_bytes()
                second_exit = brief.cmd_run(args)
                attempt_barrier = ledger / "scheduled-attempt-20260812-080000.json"
                attempt_barrier_exists = attempt_barrier.is_file()
                attempt_barrier_mode = (
                    stat.S_IMODE(attempt_barrier.stat().st_mode)
                    if attempt_barrier_exists
                    else None
                )

            self.assertEqual(first_exit, 0)
            self.assertEqual(archive.name, "brief-20260812-080000.html")
            self.assertEqual(second_exit, 3)
            self.assertEqual(collect.call_count, 1)
            self.assertEqual(append_lock_states, ["held"])
            self.assertEqual(deliver.call_count, 1)
            self.assertEqual(notify.call_count, 1)
            self.assertEqual(deliver.call_args.args[0], archive)
            self.assertEqual(archive.read_bytes(), first_bytes)
            self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o400)
            json_archive = archive.with_suffix(".json")
            self.assertTrue(json_archive.is_file())
            self.assertEqual(stat.S_IMODE(json_archive.stat().st_mode), 0o400)
            self.assertTrue(attempt_barrier_exists)
            self.assertEqual(attempt_barrier_mode, 0o400)
            self.assertEqual(
                appended_summaries[0]["attempt_barrier"],
                {"path": str(attempt_barrier), "state": "PRESENT"},
            )

    def test_scheduled_archives_use_run_local_bytes_when_latest_is_interleaved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            packet = _scheduled_packet_fixture()
            appended: list[dict[str, object]] = []
            delivered = mock.Mock(
                return_value={
                    "status": "ok",
                    "delivery_status": "sent",
                    "message_id": "interleaving-safe",
                }
            )

            def overwrite_latest(_packet, out_json, out_html):
                out_json.parent.mkdir(parents=True, exist_ok=True)
                out_json.write_text(
                    json.dumps({"interleaved": True}) + "\n",
                    encoding="utf-8",
                )
                out_html.write_text("<html>INTERLEAVED</html>", encoding="utf-8")

            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", return_value=packet
            ), mock.patch.object(
                brief, "write_packet", side_effect=overwrite_latest
            ), mock.patch.object(
                brief, "macos_notify", return_value={"status": "ok"}
            ), mock.patch.object(
                brief, "deliver_superhuman", delivered
            ), mock.patch.object(
                brief,
                "append_scheduled_window",
                side_effect=lambda summary, **_kwargs: appended.append(summary),
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = brief._cmd_run_locked(args, _scheduled_proof_fixture())

            archive_json = evidence / "brief-20260812-080000.json"
            archive_html = evidence / "brief-20260812-080000.html"
            archived_packet = json.loads(archive_json.read_text(encoding="utf-8"))
            archived_html = archive_html.read_text(encoding="utf-8")
            archive_json_hash = hashlib.sha256(archive_json.read_bytes()).hexdigest()
            archive_html_hash = hashlib.sha256(archive_html.read_bytes()).hexdigest()

        self.assertEqual(exit_code, 0)
        self.assertEqual(archived_packet, packet)
        self.assertNotIn("INTERLEAVED", archived_html)
        self.assertEqual(archived_html, brief.render_html(packet))
        self.assertEqual(delivered.call_args.args[0], archive_html)
        self.assertEqual(
            appended[0]["json_sha256"],
            archive_json_hash,
        )
        self.assertEqual(
            appended[0]["html_sha256"],
            archive_html_hash,
        )

    def test_last_run_failure_after_send_does_not_prevent_window_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            real_write_text = Path.write_text
            appended: list[dict[str, object]] = []

            def fail_last_run(path, *args, **kwargs):
                if path.name == "last-run.json":
                    raise OSError("last-run unavailable after send")
                return real_write_text(path, *args, **kwargs)

            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", return_value=_scheduled_packet_fixture()
            ), mock.patch.object(
                brief, "macos_notify", return_value={"status": "ok"}
            ), mock.patch.object(
                brief,
                "deliver_superhuman",
                return_value={
                    "status": "ok",
                    "delivery_status": "sent",
                    "message_id": "sent-before-last-run-failure",
                },
            ), mock.patch.object(
                brief,
                "append_scheduled_window",
                side_effect=lambda summary, **_kwargs: appended.append(summary),
            ), mock.patch.object(
                brief.Path,
                "write_text",
                autospec=True,
                side_effect=fail_last_run,
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    exit_code = brief._cmd_run_locked(
                        args,
                        _scheduled_proof_fixture(),
                    )
                except OSError as exc:
                    self.fail(f"last-run failure prevented append: {exc}")

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(appended), 1)
        self.assertEqual(
            appended[0]["receipt"]["message_id"],
            "sent-before-last-run-failure",
        )

    def test_append_failure_after_send_records_no_retry_recovery_and_blocks_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            collect = mock.Mock(return_value=_scheduled_packet_fixture())
            deliver = mock.Mock(
                return_value={
                    "status": "ok",
                    "delivery_status": "sent",
                    "message_id": "sent-before-append-failure",
                    "attempt_state": "PROVISIONAL_SENT",
                    "attempt_id": "a" * 24,
                }
            )
            append = mock.Mock(side_effect=OSError("window ledger append unavailable"))
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), mock.patch.object(
                brief, "macos_notify", return_value={"status": "ok"}
            ), mock.patch.object(
                brief, "deliver_superhuman", deliver
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    first_exit = brief._cmd_run_locked(args, _scheduled_proof_fixture())
                    second_exit = brief._cmd_run_locked(args, _scheduled_proof_fixture())
                except OSError as exc:
                    self.fail(f"post-send append failure escaped: {exc}")

            last_run = json.loads((ledger / "last-run.json").read_text(encoding="utf-8"))

        self.assertEqual(first_exit, 3)
        self.assertEqual(second_exit, 3)
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(deliver.call_count, 1)
        self.assertEqual(append.call_count, 1)
        self.assertEqual(last_run["status"], "blocked")
        self.assertEqual(
            last_run["receipt"]["message_id"],
            "sent-before-append-failure",
        )
        self.assertIn("window ledger append unavailable", last_run["wake"])
        self.assertIn("never resend", last_run["wake"])

    def test_delivery_exception_appends_unknown_no_retry_window_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            send_attempt_log = ledger / "send-attempts.jsonl"
            appended: list[dict[str, object]] = []

            def fail_after_possible_send(_html_path, *, subject, **_kwargs):
                send_attempt_log.parent.mkdir(parents=True, exist_ok=True)
                send_attempt_log.write_text(
                    json.dumps(
                        {
                            "schema": "shadow.superhuman-send-attempt.v1",
                            "state": "UNKNOWN_NO_RETRY",
                            "attempt_id": "b" * 24,
                            "draft_id": "draft-before-exception",
                            "thread_id": "thread-before-exception",
                            "subject": subject,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                send_attempt_log.chmod(0o600)
                raise OSError("provider result lost after possible send")

            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "SEND_ATTEMPT_LOG", send_attempt_log
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", return_value=_scheduled_packet_fixture()
            ), mock.patch.object(
                brief, "macos_notify", return_value={"status": "ok"}
            ), mock.patch.object(
                brief, "deliver_superhuman", side_effect=fail_after_possible_send
            ), mock.patch.object(
                brief,
                "append_scheduled_window",
                side_effect=lambda summary, **_kwargs: appended.append(summary),
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    exit_code = brief._cmd_run_locked(
                        args,
                        _scheduled_proof_fixture(),
                    )
                except OSError as exc:
                    self.fail(f"delivery exception escaped scheduled receipt: {exc}")

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(len(appended), 1)
        receipt = appended[0]["receipt"]
        self.assertEqual(receipt["status"], "unknown")
        self.assertEqual(receipt["delivery_status"], "unknown_no_retry")
        self.assertEqual(receipt["attempt_state"], "UNKNOWN_NO_RETRY")
        self.assertEqual(receipt["attempt_id"], "b" * 24)
        self.assertIn("never retry", receipt["wake"])

    def test_delivery_exception_with_non_utf8_attempt_log_still_appends_unknown_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            send_attempt_log = ledger / "send-attempts.jsonl"
            appended: list[dict[str, object]] = []

            def fail_with_corrupt_attempt_log(*_args, **_kwargs):
                send_attempt_log.parent.mkdir(parents=True, exist_ok=True)
                send_attempt_log.write_bytes(b"\xff\xfe\x00")
                send_attempt_log.chmod(0o600)
                raise OSError("provider result lost after possible send")

            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "SEND_ATTEMPT_LOG", send_attempt_log
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", return_value=_scheduled_packet_fixture()
            ), mock.patch.object(
                brief, "macos_notify", return_value={"status": "ok"}
            ), mock.patch.object(
                brief, "deliver_superhuman", side_effect=fail_with_corrupt_attempt_log
            ), mock.patch.object(
                brief,
                "append_scheduled_window",
                side_effect=lambda summary, **_kwargs: appended.append(summary),
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    exit_code = brief._cmd_run_locked(
                        args,
                        _scheduled_proof_fixture(),
                    )
                except UnicodeError as exc:
                    self.fail(f"corrupt attempt log escaped recovery: {exc}")

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(len(appended), 1)
        receipt = appended[0]["receipt"]
        self.assertEqual(receipt["status"], "unknown")
        self.assertEqual(receipt["delivery_status"], "unknown_no_retry")
        self.assertIsNone(receipt["attempt_id"])
        self.assertIn("send-attempt ledger is unsafe or corrupt", receipt["notes"])
        self.assertIn(str(send_attempt_log), receipt["wake"])
        self.assertIn("never retry", receipt["wake"])

    def test_blocked_scheduled_branches_tolerate_last_run_write_failure(self):
        for branch in ("board", "freshness"):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                evidence = root / "evidence"
                ledger = root / "ledger"
                real_write_text = Path.write_text
                last_run_attempts: list[Path] = []
                packet = _scheduled_packet_fixture(
                    consistent=branch != "board",
                    generated_at=(
                        "2026-08-12T09:00:00-04:00"
                        if branch == "freshness"
                        else "2026-08-12T08:05:00-04:00"
                    ),
                )

                def fail_last_run(path, *args, **kwargs):
                    if path.name == "last-run.json":
                        last_run_attempts.append(path)
                        raise OSError(f"{branch} last-run unavailable")
                    return real_write_text(path, *args, **kwargs)

                notify = mock.Mock()
                deliver = mock.Mock()
                append = mock.Mock()
                args = mock.Mock(
                    scheduled_trigger=True,
                    slot="morning",
                    deliver=True,
                    dry_run=False,
                    send_authorized_self=True,
                )
                with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                    brief, "LOG_DIR", ledger
                ), mock.patch.object(
                    brief, "WINDOW_LOG", ledger / "windows.jsonl"
                ), mock.patch.object(
                    brief, "scheduled_window", return_value=_scheduled_window_fixture()
                ), mock.patch.object(
                    brief, "collect_packet", return_value=packet
                ), mock.patch.object(
                    brief, "macos_notify", notify
                ), mock.patch.object(
                    brief, "deliver_superhuman", deliver
                ), mock.patch.object(
                    brief, "append_scheduled_window", append
                ), mock.patch.object(
                    brief.Path,
                    "write_text",
                    autospec=True,
                    side_effect=fail_last_run,
                ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    try:
                        exit_code = brief._cmd_run_locked(
                            args,
                            _scheduled_proof_fixture(),
                        )
                    except OSError as exc:
                        self.fail(f"{branch} recovery write escaped: {exc}")

                self.assertNotEqual(exit_code, 0)
                self.assertEqual(last_run_attempts, [ledger / "last-run.json"])
                self.assertEqual(notify.call_count, 0)
                self.assertEqual(deliver.call_count, 0)
                self.assertEqual(append.call_count, 0)

    def test_invalid_runtime_provenance_blocks_scheduled_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            invalid = {
                "schema": brief.PRODUCER_PROVENANCE_SCHEMA,
                "source_commit": None,
                "script_sha256": "c" * 64,
                "source_matches_commit": False,
            }
            collect = mock.Mock(return_value=_scheduled_packet_fixture(producer=invalid))
            notify = mock.Mock(return_value={"status": "ok"})
            deliver = mock.Mock(
                return_value={
                    "status": "ok",
                    "delivery_status": "sent",
                    "message_id": "should-not-send",
                }
            )
            append = mock.Mock()
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), mock.patch.object(
                brief, "macos_notify", notify
            ), mock.patch.object(
                brief, "deliver_superhuman", deliver
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = brief._cmd_run_locked(args, _scheduled_proof_fixture())

            last_run = json.loads((ledger / "last-run.json").read_text(encoding="utf-8"))
            barrier = ledger / "scheduled-attempt-20260812-080000.json"
            barrier_exists = barrier.is_file()

        self.assertEqual(exit_code, 3)
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(notify.call_count, 0)
        self.assertEqual(deliver.call_count, 0)
        self.assertEqual(append.call_count, 0)
        self.assertTrue(barrier_exists)
        self.assertEqual(last_run["status"], "blocked")
        self.assertEqual(last_run["producer"], invalid)
        self.assertIn("producer provenance", last_run["wake"])

    def test_unsafe_window_ledger_blocks_scheduled_run_before_collection(self):
        for corruption in ("symlink", "invalid-json"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                evidence = root / "evidence"
                ledger = root / "ledger"
                ledger.mkdir()
                window_log = ledger / "windows.jsonl"
                if corruption == "symlink":
                    target = root / "window-target.jsonl"
                    target.write_text("{}\n", encoding="utf-8")
                    target.chmod(0o600)
                    window_log.symlink_to(target)
                else:
                    window_log.write_text('{"truncated":\n', encoding="utf-8")
                    window_log.chmod(0o600)
                collect = mock.Mock(return_value=_scheduled_packet_fixture())
                notify = mock.Mock(
                    return_value={
                        "status": "blocked",
                        "title": "Shadow brief ready",
                        "body": "morning · board rev 41",
                    }
                )
                deliver = mock.Mock()
                append = mock.Mock()
                args = mock.Mock(
                    scheduled_trigger=True,
                    slot="morning",
                    deliver=True,
                    dry_run=False,
                    send_authorized_self=True,
                )
                with mock.patch.object(
                    brief,
                    "EVIDENCE_DIR",
                    evidence,
                ), mock.patch.object(
                    brief,
                    "LOG_DIR",
                    ledger,
                ), mock.patch.object(
                    brief,
                    "WINDOW_LOG",
                    window_log,
                ), mock.patch.object(
                    brief,
                    "scheduled_window",
                    return_value=_scheduled_window_fixture(),
                ), mock.patch.object(
                    brief,
                    "collect_packet",
                    collect,
                ), mock.patch.object(
                    brief,
                    "macos_notify",
                    notify,
                ), mock.patch.object(
                    brief,
                    "deliver_superhuman",
                    deliver,
                ), mock.patch.object(
                    brief,
                    "append_scheduled_window",
                    append,
                ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    try:
                        exit_code = brief._cmd_run_locked(
                            args,
                            _scheduled_proof_fixture(),
                        )
                    except (OSError, UnicodeError) as exc:
                        self.fail(f"unsafe scheduled-window ledger escaped: {exc}")

                last_run = json.loads(
                    (ledger / "last-run.json").read_text(encoding="utf-8")
                )
                barrier = ledger / "scheduled-attempt-20260812-080000.json"
                self.assertEqual(exit_code, 3)
                collect.assert_not_called()
                notify.assert_not_called()
                deliver.assert_not_called()
                append.assert_not_called()
                self.assertFalse(os.path.lexists(barrier))
                self.assertEqual(last_run["status"], "blocked")
                self.assertIn("window ledger is unsafe or corrupt", last_run["wake"])

    def test_corrupt_send_attempt_ledger_blocks_before_scheduled_collection(self):
        corrupt_payloads = (
            b'{"truncated":\n',
            b"\xff\xfe\x00",
        )
        for payload in corrupt_payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                evidence = root / "evidence"
                ledger = root / "ledger"
                ledger.mkdir()
                attempt_log = ledger / "send-attempts.jsonl"
                attempt_log.write_bytes(payload)
                attempt_log.chmod(0o600)
                collect = mock.Mock(return_value=_scheduled_packet_fixture())
                notify = mock.Mock(
                    return_value={
                        "status": "blocked",
                        "title": "Shadow brief ready",
                        "body": "morning · board rev 41",
                    }
                )
                deliver = mock.Mock()
                append = mock.Mock()
                args = mock.Mock(
                    scheduled_trigger=True,
                    slot="morning",
                    deliver=True,
                    dry_run=False,
                    send_authorized_self=True,
                )
                with mock.patch.object(
                    brief,
                    "EVIDENCE_DIR",
                    evidence,
                ), mock.patch.object(
                    brief,
                    "LOG_DIR",
                    ledger,
                ), mock.patch.object(
                    brief,
                    "WINDOW_LOG",
                    ledger / "windows.jsonl",
                ), mock.patch.object(
                    brief,
                    "SEND_ATTEMPT_LOG",
                    attempt_log,
                ), mock.patch.object(
                    brief,
                    "scheduled_window",
                    return_value=_scheduled_window_fixture(),
                ), mock.patch.object(
                    brief,
                    "collect_packet",
                    collect,
                ), mock.patch.object(
                    brief,
                    "macos_notify",
                    notify,
                ), mock.patch.object(
                    brief,
                    "deliver_superhuman",
                    deliver,
                ), mock.patch.object(
                    brief,
                    "append_scheduled_window",
                    append,
                ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    exit_code = brief._cmd_run_locked(
                        args,
                        _scheduled_proof_fixture(),
                    )

                last_run = json.loads(
                    (ledger / "last-run.json").read_text(encoding="utf-8")
                )
                barrier = ledger / "scheduled-attempt-20260812-080000.json"
                self.assertEqual(exit_code, 3)
                collect.assert_not_called()
                notify.assert_not_called()
                deliver.assert_not_called()
                append.assert_not_called()
                self.assertFalse(os.path.lexists(barrier))
                self.assertIn(
                    "send-attempt ledger is unsafe or corrupt",
                    last_run["wake"],
                )

    def test_window_ledger_corruption_after_collection_blocks_before_notify_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            ledger.mkdir()
            window_log = ledger / "windows.jsonl"
            window_log.write_text("{}\n", encoding="utf-8")
            window_log.chmod(0o600)

            def collect_then_corrupt(*, slot):
                self.assertEqual(slot, "morning")
                window_log.write_text('{"truncated":\n', encoding="utf-8")
                window_log.chmod(0o600)
                return _scheduled_packet_fixture()

            collect = mock.Mock(side_effect=collect_then_corrupt)
            notify = mock.Mock(
                return_value={
                    "status": "blocked",
                    "title": "Shadow brief ready",
                    "body": "morning · board rev 41",
                }
            )
            deliver = mock.Mock()
            append = mock.Mock()
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(
                brief,
                "EVIDENCE_DIR",
                evidence,
            ), mock.patch.object(
                brief,
                "LOG_DIR",
                ledger,
            ), mock.patch.object(
                brief,
                "WINDOW_LOG",
                window_log,
            ), mock.patch.object(
                brief,
                "scheduled_window",
                return_value=_scheduled_window_fixture(),
            ), mock.patch.object(
                brief,
                "collect_packet",
                collect,
            ), mock.patch.object(
                brief,
                "macos_notify",
                notify,
            ), mock.patch.object(
                brief,
                "deliver_superhuman",
                deliver,
            ), mock.patch.object(
                brief,
                "append_scheduled_window",
                append,
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    exit_code = brief._cmd_run_locked(
                        args,
                        _scheduled_proof_fixture(),
                    )
                except (OSError, UnicodeError) as exc:
                    self.fail(f"post-collection window ledger error escaped: {exc}")

            last_run = json.loads(
                (ledger / "last-run.json").read_text(encoding="utf-8")
            )
            barrier = ledger / "scheduled-attempt-20260812-080000.json"
            barrier_exists = barrier.is_file()

        self.assertEqual(exit_code, 3)
        collect.assert_called_once()
        notify.assert_not_called()
        deliver.assert_not_called()
        append.assert_not_called()
        self.assertTrue(barrier_exists)
        self.assertIn("window ledger is unsafe or corrupt", last_run["wake"])

    def test_scheduled_collector_process_failures_preserve_attempt_barrier(self):
        collector_defaults = {
            "collect_github": [],
            "collect_vercel": {"available": False},
            "collect_supabase": {"available": False},
        }
        for collector_name in collector_defaults:
            for exception in (
                OSError(f"{collector_name} executable unavailable"),
                subprocess.TimeoutExpired([collector_name], 45),
                ValueError(f"{collector_name} JSON decoder limit exceeded"),
                RecursionError(f"{collector_name} JSON nesting limit exceeded"),
            ):
                with self.subTest(
                    collector=collector_name,
                    exception=type(exception).__name__,
                ), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    evidence = root / "evidence"
                    ledger = root / "ledger"
                    notify = mock.Mock()
                    deliver = mock.Mock()
                    append = mock.Mock()
                    args = mock.Mock(
                        scheduled_trigger=True,
                        slot="morning",
                        deliver=True,
                        dry_run=False,
                        send_authorized_self=True,
                    )
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(
                            mock.patch.object(brief, "EVIDENCE_DIR", evidence)
                        )
                        stack.enter_context(mock.patch.object(brief, "LOG_DIR", ledger))
                        stack.enter_context(
                            mock.patch.object(
                                brief,
                                "WINDOW_LOG",
                                ledger / "windows.jsonl",
                            )
                        )
                        stack.enter_context(
                            mock.patch.object(
                                brief,
                                "scheduled_window",
                                return_value=_scheduled_window_fixture(),
                            )
                        )
                        stack.enter_context(
                            mock.patch.object(brief, "portfolio_root", return_value=root)
                        )
                        stack.enter_context(
                            mock.patch.object(brief, "collect_repos", return_value=[])
                        )
                        for name, default in collector_defaults.items():
                            stack.enter_context(
                                mock.patch.object(
                                    brief,
                                    name,
                                    side_effect=(
                                        exception if name == collector_name else None
                                    ),
                                    return_value=(
                                        default if name != collector_name else mock.DEFAULT
                                    ),
                                )
                            )
                        stack.enter_context(
                            mock.patch.object(brief, "macos_notify", notify)
                        )
                        stack.enter_context(
                            mock.patch.object(brief, "deliver_superhuman", deliver)
                        )
                        stack.enter_context(
                            mock.patch.object(brief, "append_scheduled_window", append)
                        )
                        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                        try:
                            exit_code = brief._cmd_run_locked(
                                args,
                                _scheduled_proof_fixture(),
                            )
                        except (
                            OSError,
                            subprocess.TimeoutExpired,
                            ValueError,
                            RecursionError,
                        ) as exc:
                            self.fail(
                                f"{collector_name} process failure escaped after barrier: {exc}"
                            )

                    barrier = ledger / "scheduled-attempt-20260812-080000.json"
                    barrier_payload = json.loads(
                        barrier.read_text(encoding="utf-8")
                    )
                    last_run = json.loads(
                        (ledger / "last-run.json").read_text(encoding="utf-8")
                    )

                    self.assertEqual(exit_code, 3)
                    self.assertEqual(stat.S_IMODE(barrier.stat().st_mode), 0o400)
                    self.assertEqual(barrier_payload["state"], "RESERVED")
                    self.assertEqual(last_run["status"], "blocked")
                    self.assertEqual(
                        last_run["attempt_barrier"],
                        {"path": str(barrier), "state": "PRESENT"},
                    )
                    self.assertEqual(
                        last_run["collection_error"]["type"],
                        type(exception).__name__,
                    )
                    self.assertIn(collector_name, last_run["collection_error"]["message"])
                    self.assertIn("do not notify or send", last_run["wake"])
                    self.assertEqual(notify.call_count, 0)
                    self.assertEqual(deliver.call_count, 0)
                    self.assertEqual(append.call_count, 0)

    def test_archive_publication_oserror_preserves_barrier_and_blocks_retry(self):
        class FrozenDateTime(brief.datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromisoformat("2026-08-12T08:05:00-04:00")
                return value if tz is None else value.astimezone(tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            packet = {
                "generated_at": "2026-08-12T08:05:00-04:00",
                "slot": "morning",
                "board": {"revision": 41, "entities": [], "claims": []},
                "authority": {
                    "board_snapshot": {"consistent": True, "revision": 41}
                },
                "paint_health": {},
                "producer": _m5_producer_fixture(),
                "superhuman_context": _m5_mail_fixture(),
                "repos": [],
                "github_open_prs": [],
                "recommendations": [],
                "analysis": {},
                "snowcubes_context": {"surfaces": []},
            }
            window = {
                "on_schedule": True,
                "slot": "morning",
                "scheduled_for": "2026-08-12T08:00:00-04:00",
            }
            proof = _scheduled_proof_fixture()
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            collect = mock.Mock(return_value=packet)
            notify = mock.Mock(return_value={"status": "ok"})
            deliver = mock.Mock(return_value={"status": "ok"})
            append = mock.Mock()
            real_place = brief._place_private_archive

            def fail_json_publication(path, content):
                if path.parent == evidence and path.suffix == ".json":
                    raise PermissionError("archive JSON publication denied")
                return real_place(path, content)

            stderr = io.StringIO()
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "datetime", FrozenDateTime
            ), mock.patch.object(
                brief, "launch_trigger_proof", return_value=proof
            ), mock.patch.object(
                brief, "scheduled_window", return_value=window
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), mock.patch.object(
                brief, "_place_private_archive", side_effect=fail_json_publication
            ), mock.patch.object(
                brief, "macos_notify", notify
            ), mock.patch.object(
                brief, "deliver_superhuman", deliver
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), contextlib.redirect_stderr(stderr):
                try:
                    first_exit = brief.cmd_run(args)
                    second_exit = brief.cmd_run(args)
                except OSError as exc:
                    self.fail(f"archive publication error escaped cmd_run: {exc}")

            archive_html = evidence / "brief-20260812-080000.html"
            archive_json = evidence / "brief-20260812-080000.json"
            attempt_barrier = ledger / "scheduled-attempt-20260812-080000.json"
            last_run = json.loads((ledger / "last-run.json").read_text(encoding="utf-8"))
            archive_html_exists = archive_html.is_file()
            archive_json_exists = archive_json.exists()
            archive_html_mode = stat.S_IMODE(archive_html.stat().st_mode)
            attempt_barrier_exists = attempt_barrier.is_file()
            attempt_barrier_mode = stat.S_IMODE(attempt_barrier.stat().st_mode)

        self.assertEqual(first_exit, 3)
        self.assertEqual(second_exit, 3)
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(notify.call_count, 0)
        self.assertEqual(deliver.call_count, 0)
        self.assertEqual(append.call_count, 0)
        self.assertTrue(archive_html_exists)
        self.assertFalse(archive_json_exists)
        self.assertEqual(archive_html_mode, 0o400)
        self.assertTrue(attempt_barrier_exists)
        self.assertEqual(attempt_barrier_mode, 0o400)
        self.assertEqual(last_run["status"], "blocked")
        self.assertEqual(last_run["archive_html"], str(archive_html))
        self.assertEqual(last_run["archive_json"], str(archive_json))
        self.assertEqual(
            last_run["attempt_barrier"],
            {"path": str(attempt_barrier), "state": "PRESENT"},
        )
        self.assertIn("archive JSON publication denied", last_run["wake"])
        self.assertIn("do not notify, send, overwrite, or retry", last_run["wake"])

    def test_first_archive_publication_oserror_cannot_recollect_on_retry(self):
        class FrozenDateTime(brief.datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromisoformat("2026-08-12T08:05:00-04:00")
                return value if tz is None else value.astimezone(tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            packet = {
                "generated_at": "2026-08-12T08:05:00-04:00",
                "slot": "morning",
                "board": {"revision": 41, "entities": [], "claims": []},
                "authority": {
                    "board_snapshot": {"consistent": True, "revision": 41}
                },
                "paint_health": {},
                "producer": _m5_producer_fixture(),
                "superhuman_context": _m5_mail_fixture(),
                "repos": [],
                "github_open_prs": [],
                "recommendations": [],
                "analysis": {},
                "snowcubes_context": {"surfaces": []},
            }
            window = {
                "on_schedule": True,
                "slot": "morning",
                "scheduled_for": "2026-08-12T08:00:00-04:00",
            }
            proof = _scheduled_proof_fixture()
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            collect = mock.Mock(return_value=packet)
            notify = mock.Mock(return_value={"status": "ok"})
            deliver = mock.Mock(return_value={"status": "ok"})
            append = mock.Mock()
            real_place = brief._place_private_archive

            def fail_html_publication(path, content):
                if path.parent == evidence and path.suffix == ".html":
                    raise OSError("archive HTML publication unavailable")
                return real_place(path, content)

            stderr = io.StringIO()
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "datetime", FrozenDateTime
            ), mock.patch.object(
                brief, "launch_trigger_proof", return_value=proof
            ), mock.patch.object(
                brief, "scheduled_window", return_value=window
            ), mock.patch.object(
                brief, "collect_packet", collect
            ), mock.patch.object(
                brief, "_place_private_archive", side_effect=fail_html_publication
            ), mock.patch.object(
                brief, "macos_notify", notify
            ), mock.patch.object(
                brief, "deliver_superhuman", deliver
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), contextlib.redirect_stderr(stderr):
                try:
                    first_exit = brief.cmd_run(args)
                    second_exit = brief.cmd_run(args)
                except OSError as exc:
                    self.fail(f"first archive publication error escaped cmd_run: {exc}")

            attempt_barrier = ledger / "scheduled-attempt-20260812-080000.json"
            last_run = json.loads((ledger / "last-run.json").read_text(encoding="utf-8"))
            barrier_exists = attempt_barrier.is_file()
            archived_files = sorted(path.name for path in evidence.glob("brief-*"))

        self.assertEqual(first_exit, 3)
        self.assertEqual(second_exit, 3)
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(notify.call_count, 0)
        self.assertEqual(deliver.call_count, 0)
        self.assertEqual(append.call_count, 0)
        self.assertTrue(barrier_exists)
        self.assertEqual(archived_files, [])
        self.assertEqual(last_run["status"], "blocked")
        self.assertEqual(
            last_run["attempt_barrier"],
            {"path": str(attempt_barrier), "state": "PRESENT"},
        )
        self.assertIn("archive HTML publication unavailable", last_run["wake"])

    def test_publication_failure_stays_blocked_when_last_run_cannot_be_written(self):
        class FrozenDateTime(brief.datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromisoformat("2026-08-12T08:05:00-04:00")
                return value if tz is None else value.astimezone(tz)

        packet = {
            "generated_at": "2026-08-12T08:05:00-04:00",
            "slot": "morning",
            "board": {"revision": 41, "entities": [], "claims": []},
            "authority": {"board_snapshot": {"consistent": True, "revision": 41}},
            "paint_health": {},
            "producer": _m5_producer_fixture(),
            "superhuman_context": _m5_mail_fixture(),
            "repos": [],
            "github_open_prs": [],
            "recommendations": [],
            "analysis": {},
            "snowcubes_context": {"surfaces": []},
        }
        window = {
            "on_schedule": True,
            "slot": "morning",
            "scheduled_for": "2026-08-12T08:00:00-04:00",
        }
        proof = _scheduled_proof_fixture()
        args = mock.Mock(
            scheduled_trigger=True,
            slot="morning",
            deliver=True,
            dry_run=False,
            send_authorized_self=True,
        )
        real_place = brief._place_private_archive
        real_write_text = Path.write_text

        for failure_stage, expected_collects in (("barrier", 0), ("archive", 1)):
            with self.subTest(failure_stage=failure_stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                evidence = root / "evidence"
                ledger = root / "ledger"
                collect = mock.Mock(return_value=packet)
                notify = mock.Mock(return_value={"status": "ok"})
                deliver = mock.Mock(return_value={"status": "ok"})
                append = mock.Mock()

                def fail_publication(path, content):
                    if failure_stage == "barrier" and path.parent == ledger:
                        raise OSError("attempt barrier storage unavailable")
                    if (
                        failure_stage == "archive"
                        and path.parent == evidence
                        and path.suffix == ".html"
                    ):
                        raise OSError("archive storage unavailable")
                    return real_place(path, content)

                def fail_last_run(path, *args, **kwargs):
                    if path.name == "last-run.json":
                        raise OSError("last-run storage unavailable")
                    return real_write_text(path, *args, **kwargs)

                stderr = io.StringIO()
                with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                    brief, "LOG_DIR", ledger
                ), mock.patch.object(
                    brief, "WINDOW_LOG", ledger / "windows.jsonl"
                ), mock.patch.object(
                    brief, "datetime", FrozenDateTime
                ), mock.patch.object(
                    brief, "scheduled_window", return_value=window
                ), mock.patch.object(
                    brief, "collect_packet", collect
                ), mock.patch.object(
                    brief, "_place_private_archive", side_effect=fail_publication
                ), mock.patch.object(
                    brief, "macos_notify", notify
                ), mock.patch.object(
                    brief, "deliver_superhuman", deliver
                ), mock.patch.object(
                    brief, "append_scheduled_window", append
                ), mock.patch.object(
                    brief.Path,
                    "write_text",
                    autospec=True,
                    side_effect=fail_last_run,
                ), contextlib.redirect_stderr(stderr):
                    try:
                        exit_code = brief._cmd_run_locked(args, proof)
                    except OSError as exc:
                        self.fail(f"recovery persistence failure escaped: {exc}")

                emitted = json.loads(stderr.getvalue())
                barrier = ledger / "scheduled-attempt-20260812-080000.json"
                self.assertEqual(exit_code, 3)
                self.assertEqual(collect.call_count, expected_collects)
                self.assertEqual(notify.call_count, 0)
                self.assertEqual(deliver.call_count, 0)
                self.assertEqual(append.call_count, 0)
                self.assertEqual(emitted["status"], "blocked")
                self.assertEqual(emitted["attempt_barrier"]["path"], str(barrier))
                self.assertEqual(
                    emitted["attempt_barrier"]["state"],
                    "UNAVAILABLE" if failure_stage == "barrier" else "PRESENT",
                )
                self.assertEqual(barrier.exists(), failure_stage == "archive")

    def test_manual_runs_use_unique_namespace_at_an_exact_scheduled_clock_time(self):
        class FrozenDateTime(brief.datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromisoformat("2026-08-12T08:00:00-04:00")
                return value if tz is None else value.astimezone(tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            packet = {
                "generated_at": "2026-08-12T08:00:00-04:00",
                "slot": "morning",
                "board": {"revision": 41, "entities": [], "claims": []},
                "authority": {
                    "board_snapshot": {"consistent": True, "revision": 41}
                },
                "paint_health": {},
                "producer": _m5_producer_fixture(),
                "superhuman_context": _m5_mail_fixture(),
                "repos": [],
                "github_open_prs": [],
                "recommendations": [],
                "analysis": {},
                "snowcubes_context": {"surfaces": []},
            }
            args = mock.Mock(
                scheduled_trigger=False,
                slot="morning",
                deliver=False,
                dry_run=False,
                send_authorized_self=False,
            )
            notify = mock.Mock(return_value={"status": "ok"})
            append = mock.Mock()
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "datetime", FrozenDateTime
            ), mock.patch.object(
                brief, "collect_packet", return_value=packet
            ), mock.patch.object(
                brief, "macos_notify", notify
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), mock.patch.object(
                brief.time, "time_ns", return_value=101
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                first_exit = brief.cmd_run(args)
                second_exit = brief.cmd_run(args)

            html_names = sorted(path.name for path in evidence.glob("manual-brief-*.html"))
            json_names = sorted(path.name for path in evidence.glob("manual-brief-*.json"))
            scheduled_collision = (evidence / "brief-20260812-080000.html").exists()

        self.assertEqual(first_exit, 0)
        self.assertEqual(second_exit, 0)
        self.assertEqual(len(html_names), 2)
        self.assertEqual(len(json_names), 2)
        self.assertEqual(
            {name.removesuffix(".html") for name in html_names},
            {name.removesuffix(".json") for name in json_names},
        )
        self.assertTrue(
            all(name.startswith("manual-brief-20260812-080000-000000-") for name in html_names)
        )
        self.assertFalse(scheduled_collision)
        self.assertEqual(notify.call_count, 2)
        self.assertEqual(append.call_count, 2)

    def test_window_verifier_accepts_honest_unknown_expected_identity_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertTrue(result["ok"], result["problems"])

    def test_superhuman_verifier_reports_non_list_coverage_and_action_buckets(self):
        cases = (
            ("coverage", {"not": "a list"}),
            ("signals", "not a list"),
            ("urgent_replies", 7),
            ("waiting_replies", True),
            ("forgotten_obligations", {}),
            ("order_return_follow_up", "broken"),
            ("proactive_candidates", None),
            ("calendar_proposals", 0),
        )
        for key, malformed in cases:
            with self.subTest(bucket=key, value=malformed):
                mail = _m5_mail_fixture()
                mail[key] = malformed
                try:
                    problems = brief._superhuman_receipt_problems(mail)
                except TypeError as exc:
                    self.fail(f"JSON-valid {key} bucket raised TypeError: {exc}")

                self.assertIn(
                    f"Superhuman {key} bucket must be a list",
                    problems,
                )

    def test_superhuman_verifier_requires_exact_discovered_linked_account_coverage(self):
        linked = {
            "acting_email": "newly-linked@example.com",
            "is_primary": False,
            "added_at": "2026-08-14T00:00:00Z",
            "sender_identities": ["newly-linked@example.com"],
            "sender_identity_complete": True,
        }
        coverage = {
            "acting_email": "newly-linked@example.com",
            "expected": False,
            "linked": True,
            "status": "COMPLETE",
            "pagination": {"pages": 1, "exhausted": True, "truncated": False},
        }

        missing = _m5_mail_fixture()
        missing["linked_accounts"].append(linked)
        missing_problems = brief._superhuman_receipt_problems(missing)

        exact = _m5_mail_fixture()
        exact["linked_accounts"].append(linked)
        exact["coverage"].append(coverage)
        exact_problems = brief._superhuman_receipt_problems(exact)

        duplicate = _m5_mail_fixture()
        duplicate["linked_accounts"].append(linked)
        duplicate["coverage"].extend([coverage, dict(coverage)])
        duplicate_problems = brief._superhuman_receipt_problems(duplicate)

        stray = _m5_mail_fixture()
        stray["coverage"].append(
            {
                "acting_email": "stray@example.com",
                "expected": False,
                "linked": False,
                "status": "GARBAGE",
                "pagination": {
                    "pages": 0,
                    "exhausted": False,
                    "truncated": True,
                },
            }
        )
        stray_problems = brief._superhuman_receipt_problems(stray)

        wrong_expected = _m5_mail_fixture()
        wrong_expected["linked_accounts"].append(linked)
        wrong_expected["coverage"].append({**coverage, "expected": True})
        wrong_expected_problems = brief._superhuman_receipt_problems(wrong_expected)

        self.assertIn("linked Superhuman account coverage mismatch", missing_problems)
        self.assertNotIn("linked Superhuman account coverage mismatch", exact_problems)
        self.assertIn("linked Superhuman account coverage mismatch", duplicate_problems)
        self.assertIn("Superhuman coverage identity universe mismatch", stray_problems)
        self.assertIn(
            "dynamic linked Superhuman identity expected marker mismatch: newly-linked@example.com",
            wrong_expected_problems,
        )

    def test_superhuman_verifier_validates_account_discovery_and_linked_account_shapes(self):
        cases = (
            (
                "account-container",
                lambda mail: mail.__setitem__("account_discovery", []),
                "Superhuman account_discovery must be an object",
            ),
            (
                "account-status-list",
                lambda mail: mail["account_discovery"].__setitem__("status", []),
                "Superhuman account_discovery status must be COMPLETE or UNKNOWN",
            ),
            (
                "linked-container",
                lambda mail: mail.__setitem__("linked_accounts", {}),
                "Superhuman linked_accounts must be a list",
            ),
            (
                "linked-row",
                lambda mail: mail.__setitem__("linked_accounts", ["broken"]),
                "Superhuman linked_accounts row must be an object",
            ),
            (
                "linked-email-field",
                lambda mail: mail["linked_accounts"][0].__setitem__(
                    "acting_email",
                    "not-an-email",
                ),
                "invalid Superhuman linked_accounts row shape: not-an-email",
            ),
            (
                "unknown-without-wake",
                lambda mail: mail.__setitem__(
                    "account_discovery",
                    {"status": "UNKNOWN", "malformed_rows": 1, "wake": None},
                ),
                "UNKNOWN Superhuman account discovery lacks exact wake",
            ),
            (
                "unknown-all-clear",
                lambda mail: (
                    mail.__setitem__(
                        "account_discovery",
                        {
                            "status": "UNKNOWN",
                            "malformed_rows": 1,
                            "wake": "Repair the malformed list_accounts row.",
                        },
                    ),
                    mail.__setitem__("status", "COMPLETE"),
                    mail.__setitem__("complete", True),
                    mail.__setitem__("all_clear_allowed", True),
                ),
                "UNKNOWN Superhuman account discovery claimed an all-clear",
            ),
            (
                "complete-with-malformed-row",
                lambda mail: mail.__setitem__(
                    "account_discovery",
                    {
                        "status": "COMPLETE",
                        "malformed_rows": 1,
                        "wake": "Repair the malformed list_accounts row.",
                    },
                ),
                "COMPLETE Superhuman account discovery contains malformed rows",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                mail = _m5_mail_fixture()
                mutate(mail)
                try:
                    problems = brief._superhuman_receipt_problems(mail)
                except (AttributeError, TypeError) as exc:
                    self.fail(f"JSON-valid account discovery shape crashed: {exc}")
                self.assertIn(expected, problems)

        honest_unknown = _m5_mail_fixture()
        honest_unknown["account_discovery"] = {
            "status": "UNKNOWN",
            "malformed_rows": 1,
            "wake": "Repair the malformed list_accounts row.",
        }
        honest_problems = brief._superhuman_receipt_problems(honest_unknown)
        self.assertNotIn(
            "UNKNOWN Superhuman account discovery lacks exact wake",
            honest_problems,
        )
        self.assertNotIn(
            "UNKNOWN Superhuman account discovery claimed an all-clear",
            honest_problems,
        )

    def test_superhuman_verifier_accepts_linked_unknown_with_problem_and_wake(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)

            def make_linked_unknown(packet):
                row = packet["superhuman_context"]["coverage"][0]
                row["status"] = "UNKNOWN"
                row["problems"] = ["provider pagination was truncated"]
                row["wake"] = "Rerun the bounded read-only account scan."

            _rewrite_m5_packet(rows[0], make_linked_unknown)
            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertTrue(result["ok"], result["problems"])

    def test_superhuman_verifier_rejects_every_other_expected_identity_state(self):
        cases = (
            (True, "BOGUS", ["provider problem"], "retry read-only scan"),
            (False, "COMPLETE", [], None),
            (None, "UNKNOWN", ["provider problem"], "retry read-only scan"),
            (True, "UNKNOWN", [], "retry read-only scan"),
            (False, "UNKNOWN", [{}], "retry read-only scan"),
        )
        for linked, status_value, row_problems, wake in cases:
            with self.subTest(linked=linked, status=status_value):
                mail = _m5_mail_fixture()
                row = mail["coverage"][0]
                row["linked"] = linked
                row["status"] = status_value
                row["problems"] = row_problems
                row["wake"] = wake

                problems = brief._superhuman_receipt_problems(mail)

                self.assertIn(
                    "invalid expected Superhuman identity coverage state: leojkwan@gmail.com",
                    problems,
                )

    def test_window_verifier_binds_the_exact_declared_archive_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)
            rows[0]["archive_html"] = str(evidence / "missing-declared.html")

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: declared archived HTML is invalid",
            result["problems"],
        )

    def test_window_verifier_requires_the_exact_scheduled_attempt_barrier(self):
        for mutation in ("none", "missing-receipt", "missing-file"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                evidence = Path(tmp)
                ledger = evidence / "ledger"
                rows = _write_m5_pair(evidence, ledger)
                if mutation == "missing-receipt":
                    rows[0].pop("attempt_barrier")
                elif mutation == "missing-file":
                    Path(str(rows[0]["attempt_barrier"]["path"])).unlink()

                try:
                    result = brief.verify_window_receipts(
                        rows,
                        evidence_dir=evidence,
                        ledger_dir=ledger,
                    )
                except TypeError as exc:
                    self.fail(f"scheduled barrier verifier seam is missing: {exc}")

                if mutation == "none":
                    self.assertTrue(result["ok"], result["problems"])
                else:
                    self.assertFalse(result["ok"])
                    self.assertIn(
                        "2026-08-12T08:00:00-04:00: scheduled attempt barrier is invalid",
                        result["problems"],
                    )

    def test_window_verifier_opens_attempt_barriers_nonblocking_and_rejects_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            ledger = evidence / "ledger"
            rows = _write_m5_pair(evidence, ledger)
            fifo = Path(str(rows[0]["attempt_barrier"]["path"]))
            fifo.unlink()
            os.mkfifo(fifo, mode=0o400)
            real_open = os.open

            def require_nonblocking(path, flags, *args, **kwargs):
                self.assertTrue(
                    flags & os.O_NONBLOCK,
                    "attempt-barrier verifier open must be nonblocking",
                )
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(brief.os, "open", side_effect=require_nonblocking):
                result = brief.verify_window_receipts(
                    rows,
                    evidence_dir=evidence,
                    ledger_dir=ledger,
                )

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: scheduled attempt barrier is invalid",
            result["problems"],
        )

    def test_window_verifier_rejects_malformed_archive_json_object_shapes(self):
        cases = (
            (
                "root",
                lambda row: _replace_m5_packet(row, []),
                "archived JSON root must be an object",
            ),
            (
                "board",
                lambda row: _rewrite_m5_packet(
                    row,
                    lambda packet: packet.__setitem__("board", []),
                ),
                "archived JSON board must be an object",
            ),
            (
                "authority",
                lambda row: _rewrite_m5_packet(
                    row,
                    lambda packet: packet.__setitem__("authority", []),
                ),
                "archived JSON authority must be an object",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                evidence = Path(tmp)
                rows = _write_m5_pair(evidence)
                mutate(rows[0])
                try:
                    result = brief.verify_window_receipts(rows, evidence_dir=evidence)
                except (AttributeError, TypeError) as exc:
                    self.fail(f"JSON-valid archived packet shape crashed: {exc}")

                self.assertFalse(result["ok"])
                self.assertIn(
                    f"2026-08-12T08:00:00-04:00: {expected}",
                    result["problems"],
                )

    def test_window_verifier_requires_v2_expected_identity_coverage_with_honest_unknowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)

            def make_dishonest(packet):
                mail = packet["superhuman_context"]
                mail["schema"] = "shadow.superhuman-context.v1"
                mail["coverage"] = mail["coverage"][:-1]
                mail["status"] = "COMPLETE"
                mail["complete"] = True
                mail["all_clear_allowed"] = True

            _rewrite_m5_packet(rows[0], make_dishonest)
            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        joined = "\n".join(result["problems"])
        self.assertIn("Superhuman context schema mismatch", joined)
        self.assertIn("expected Superhuman identity coverage mismatch", joined)
        self.assertIn("UNKNOWN mail coverage claimed an all-clear", joined)

    def test_window_verifier_requires_a_real_mail_obligation(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)
            _rewrite_m5_packet(
                rows[1],
                lambda packet: packet.__setitem__(
                    "superhuman_context", _m5_mail_fixture(include_action=False)
                ),
            )

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T20:00:00-04:00: no real mail obligation or action proposal",
            result["problems"],
        )

    def test_window_verifier_requires_exactly_one_mail_and_calendar_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)
            _rewrite_m5_html(
                rows[0],
                lambda rendered: rendered.replace(
                    "</body>", "<h2>Mail and calendar coverage</h2></body>"
                ),
            )

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: archived HTML must contain exactly one Mail and calendar coverage section",
            result["problems"],
        )

    def test_window_verifier_binds_iso_free_reader_generation_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)
            _rewrite_m5_html(
                rows[0],
                lambda rendered: rendered.replace(
                    "Morning note · twice-daily · Aug 12 · 8:05 AM",
                    "Morning note · twice-daily · Aug 11 · 8:05 AM",
                ),
            )

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: archived HTML generation marker mismatch",
            result["problems"],
        )

    def test_actual_reader_html_satisfies_archive_and_mailbox_identity(self):
        class FakeResponse:
            def __init__(self, payload):
                self.headers = {}
                self._raw = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self._raw

        def tool_result(payload):
            return {
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(payload)}
                    ]
                }
            }

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            ledger = Path(tmp) / "ledger"
            evidence.mkdir()
            rows = _write_m5_pair(evidence, ledger)
            actual_html: dict[str, str] = {}
            for row in rows:
                archive_json = Path(row["archive_json"])
                packet = json.loads(archive_json.read_text(encoding="utf-8"))
                rendered = brief.render_html(packet)
                actual_html[str(row["scheduled_for"])] = rendered
                self.assertNotRegex(rendered, r"\d{4}-\d{2}-\d{2}T")
                self.assertIn(f"board rev {row['board_revision']}", rendered)
                self.assertIn(
                    "Supporting checks inform the note; they do not create another to-do list.",
                    rendered,
                )
                archive_html = Path(row["archive_html"])
                archive_html.chmod(0o600)
                archive_html.write_text(rendered, encoding="utf-8")
                archive_html.chmod(0o400)
                row["html_sha256"] = hashlib.sha256(
                    rendered.encode("utf-8")
                ).hexdigest()

            archive_result = brief.verify_window_receipts(
                rows,
                evidence_dir=evidence,
                ledger_dir=ledger,
            )

            window = rows[0]
            receipt = window["receipt"]
            subject = receipt["subject"]
            message_id = "provider-readback-message"
            thread_id = "provider-readback-thread"
            raw_html = actual_html[str(window["scheduled_for"])]
            self.assertNotEqual(message_id, receipt["message_id"])
            self.assertNotEqual(thread_id, receipt["thread_id"])

            def mailbox_responses(rendered_html):
                return [
                    FakeResponse({}),
                    FakeResponse({}),
                    FakeResponse(
                        tool_result(
                            {
                                "threads": [
                                    {
                                        "subject": subject,
                                        "labels": ["SENT"],
                                        "thread_id": thread_id,
                                        "last_message_id": message_id,
                                    }
                                ]
                            }
                        )
                    ),
                    FakeResponse(
                        tool_result(
                            {
                                "thread_id": thread_id,
                                "last_message_id": message_id,
                                "subject": subject,
                            }
                        )
                    ),
                    FakeResponse(
                        tool_result(
                            {
                                "message": {
                                    "message_id": message_id,
                                    "thread_id": thread_id,
                                    "from": brief.SELF_MAIL,
                                    "to": [brief.SELF_MAIL],
                                    "subject": subject,
                                    "labels": ["SENT"],
                                    "sent_at": receipt["sent_at"],
                                    "raw_html": rendered_html,
                                }
                            }
                        )
                    ),
                ]

            with mock.patch.object(
                brief,
                "_mcp_remote_token",
                return_value="test-token",
            ), mock.patch(
                "urllib.request.urlopen",
                side_effect=mailbox_responses(raw_html),
            ):
                mailbox_result = brief.fetch_superhuman_mailbox_readback(window)
            stale_html = raw_html.replace(
                "Morning note · twice-daily · Aug 12 · 8:05 AM",
                "Morning note · twice-daily · Aug 11 · 8:05 AM",
            )
            with mock.patch.object(
                brief,
                "_mcp_remote_token",
                return_value="test-token",
            ), mock.patch(
                "urllib.request.urlopen",
                side_effect=mailbox_responses(stale_html),
            ):
                stale_mailbox_result = brief.fetch_superhuman_mailbox_readback(window)
            mailbox_verification = brief.verify_mailbox_readbacks(
                [window],
                [mailbox_result],
            )

        self.assertTrue(archive_result["ok"], archive_result["problems"])
        self.assertEqual(mailbox_result["status"], "EXACT_SENT_CONFIRMED")
        self.assertTrue(
            mailbox_verification["ok"],
            mailbox_verification["problems"],
        )
        self.assertEqual(stale_mailbox_result["status"], "blocked")
        self.assertIn(
            "mailbox HTML does not match scheduled report identity",
            stale_mailbox_result["problems"],
        )
        self.assertEqual(mailbox_result["subject"], subject)
        self.assertEqual(mailbox_result["raw_html_sha256"], hashlib.sha256(raw_html.encode("utf-8")).hexdigest())

    def test_live_mailbox_readback_blocks_malformed_provider_identity_shapes(self):
        class FakeResponse:
            def __init__(self, payload):
                self.headers = {}
                self._raw = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self._raw

        def tool_result(payload):
            return {
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(payload)}
                    ]
                }
            }

        with tempfile.TemporaryDirectory() as tmp:
            window = _write_m5_pair(Path(tmp))[0]
            receipt = window["receipt"]
            subject = receipt["subject"]
            valid_thread_id = receipt["thread_id"]
            valid_message_id = receipt["message_id"]
            raw_html = Path(window["archive_html"]).read_text(encoding="utf-8")
            cases = (
                (
                    "candidate-labels-bool",
                    {
                        "subject": subject,
                        "labels": True,
                        "thread_id": valid_thread_id,
                        "last_message_id": valid_message_id,
                    },
                    valid_thread_id,
                    valid_message_id,
                    ["SENT"],
                ),
                (
                    "candidate-container-ids",
                    {
                        "subject": subject,
                        "labels": ["SENT"],
                        "thread_id": ["thread"],
                        "last_message_id": True,
                    },
                    "['thread']",
                    "True",
                    ["SENT"],
                ),
                (
                    "message-labels-bool",
                    {
                        "subject": subject,
                        "labels": ["SENT"],
                        "thread_id": valid_thread_id,
                        "last_message_id": valid_message_id,
                    },
                    valid_thread_id,
                    valid_message_id,
                    True,
                ),
            )
            for (
                case_name,
                candidate,
                echoed_thread_id,
                echoed_message_id,
                message_labels,
            ) in cases:
                with self.subTest(case=case_name):
                    responses = [
                        FakeResponse({}),
                        FakeResponse({}),
                        FakeResponse(tool_result({"threads": [candidate]})),
                        FakeResponse(
                            tool_result(
                                {
                                    "thread_id": echoed_thread_id,
                                    "last_message_id": echoed_message_id,
                                    "subject": subject,
                                }
                            )
                        ),
                        FakeResponse(
                            tool_result(
                                {
                                    "message": {
                                        "message_id": echoed_message_id,
                                        "thread_id": echoed_thread_id,
                                        "from": brief.SELF_MAIL,
                                        "to": [brief.SELF_MAIL],
                                        "subject": subject,
                                        "labels": message_labels,
                                        "sent_at": receipt["sent_at"],
                                        "raw_html": raw_html,
                                    }
                                }
                            )
                        ),
                    ]
                    with mock.patch.object(
                        brief,
                        "_mcp_remote_token",
                        return_value="test-token",
                    ), mock.patch(
                        "urllib.request.urlopen",
                        side_effect=responses,
                    ):
                        try:
                            result = brief.fetch_superhuman_mailbox_readback(window)
                        except (TypeError, AttributeError) as exc:
                            self.fail(f"malformed provider JSON escaped: {exc}")

                    self.assertEqual(result["status"], "blocked")
                    self.assertTrue(result.get("wake"))

    def test_live_mailbox_readback_blocks_malformed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = _write_m5_pair(Path(tmp))[0]
            malformed_receipt = {**window, "receipt": ["not", "an", "object"]}
            try:
                result = brief.fetch_superhuman_mailbox_readback(malformed_receipt)
            except AttributeError as exc:
                self.fail(f"malformed receipt escaped: {exc}")
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(result.get("wake"))

    def test_live_mailbox_readback_blocks_malformed_mcp_envelope(self):
        class FakeResponse:
            def __init__(self, payload):
                self.headers = {}
                self._raw = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self._raw

        with tempfile.TemporaryDirectory() as tmp:
            window = _write_m5_pair(Path(tmp))[0]
            responses = [
                FakeResponse({}),
                FakeResponse({}),
                FakeResponse({"result": [{"not": "an object envelope"}]}),
            ]
            with mock.patch.object(
                brief,
                "_mcp_remote_token",
                return_value="test-token",
            ), mock.patch(
                "urllib.request.urlopen",
                side_effect=responses,
            ):
                try:
                    result = brief.fetch_superhuman_mailbox_readback(window)
                except AttributeError as exc:
                    self.fail(f"malformed MCP envelope escaped: {exc}")
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(result.get("wake"))

    def test_mailbox_html_hash_requires_exact_lowercase_hex_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = _write_m5_pair(Path(tmp))[0]
            readback = {
                "schema": brief.MAILBOX_READBACK_SCHEMA,
                "status": "EXACT_SENT_CONFIRMED",
                "scheduled_for": window["scheduled_for"],
                "acting_email": brief.SELF_MAIL,
                "from": brief.SELF_MAIL,
                "to": [brief.SELF_MAIL],
                "subject": window["receipt"]["subject"],
                "generated_at": window["generated_at"],
                "board_revision": window["board_revision"],
                "message_id": "mailbox-message",
                "thread_id": "mailbox-thread",
                "labels": ["SENT"],
                "raw_html_sha256": "a" * 64,
                "sent_at": "2026-08-12T08:06:00-04:00",
            }
            positive = brief.verify_mailbox_readbacks([window], [readback])
            self.assertTrue(positive["ok"], positive["problems"])

            for bad_hash in (int("1" * 64), "z" * 64, ["a" * 64]):
                with self.subTest(bad_hash_type=type(bad_hash).__name__):
                    malformed = {**readback, "raw_html_sha256": bad_hash}
                    result = brief.verify_mailbox_readbacks(
                        [window],
                        [malformed],
                    )
                    self.assertIn(
                        "2026-08-12T08:00:00-04:00: mailbox HTML hash missing",
                        result["problems"],
                    )

    def test_window_verifier_rejects_mismatched_runtime_producer_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)
            rows[0]["producer"] = {**_m5_producer_fixture(), "source_commit": "c" * 40}

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: archived producer provenance mismatch",
            result["problems"],
        )

    def test_window_verifier_rejects_intermediate_length_git_object_ids(self):
        for oid_length in (41, 63):
            with self.subTest(oid_length=oid_length), tempfile.TemporaryDirectory() as tmp:
                evidence = Path(tmp)
                rows = _write_m5_pair(evidence)
                invalid = {
                    **_m5_producer_fixture(),
                    "source_commit": "c" * oid_length,
                }
                rows[0]["producer"] = invalid
                _rewrite_m5_packet(
                    rows[0],
                    lambda packet: packet.__setitem__("producer", invalid),
                )

                result = brief.verify_window_receipts(rows, evidence_dir=evidence)

                self.assertFalse(result["ok"])
                self.assertIn(
                    "2026-08-12T08:00:00-04:00: runtime producer provenance missing",
                    result["problems"],
                )

    def test_window_verifier_rejects_duplicate_receipts_for_one_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            rows = _write_m5_pair(evidence)
            rows.append(dict(rows[0]))

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: duplicate natural-window receipts found",
            result["problems"],
        )

    def test_window_verifier_ignores_old_duplicate_before_latest_clean_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            old_rows = _write_m5_pair(evidence)
            rows = [dict(old_rows[0]), *old_rows]
            rows.extend(
                [
                    _write_m5_window_fixture(
                        evidence,
                        scheduled_for="2026-08-13T08:00:00-04:00",
                        generated_at="2026-08-13T08:05:00-04:00",
                        sent_at="2026-08-13T08:06:00-04:00",
                        slot="morning",
                        stamp="20260813-080000",
                    ),
                    _write_m5_window_fixture(
                        evidence,
                        scheduled_for="2026-08-13T20:00:00-04:00",
                        generated_at="2026-08-13T20:05:00-04:00",
                        sent_at="2026-08-13T20:06:00-04:00",
                        slot="evening",
                        stamp="20260813-200000",
                    ),
                ]
            )

            result = brief.verify_window_receipts(rows, evidence_dir=evidence)

        self.assertTrue(result["ok"], result["problems"])
        self.assertEqual(
            result["windows"],
            ["2026-08-13T08:00:00-04:00", "2026-08-13T20:00:00-04:00"],
        )

    def test_window_verifier_rejects_non_string_slot_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = _write_m5_pair(Path(tmp))
            malformed_window = str(rows[0]["scheduled_for"])
            rows[0]["slot"] = []

            result = brief.verify_window_receipts(rows, evidence_dir=Path(tmp))

        self.assertNotIn(malformed_window, result["windows"])
        self.assertIn(malformed_window, result["ignored_nonslot_windows"])
        self.assertIn(
            "need two distinct current-schema natural 08:00/20:00 windows; found 1",
            result["problems"],
        )

    def test_verify_windows_command_rejects_non_string_slot_without_crashing(self):
        scheduled_for = "2026-08-12T08:00:00-04:00"
        row = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "trigger": "launchd-calendar",
            "slot": [],
            "scheduled_for": scheduled_for,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window_log = root / "windows.jsonl"
            mailbox_log = root / "mailbox.jsonl"
            window_log.write_text(json.dumps(row) + "\n", encoding="utf-8")
            window_log.chmod(0o600)
            output = io.StringIO()
            with mock.patch.object(brief, "WINDOW_LOG", window_log), mock.patch.object(
                brief, "MAILBOX_READBACK_LOG", mailbox_log
            ), mock.patch.object(
                brief, "EVIDENCE_DIR", root / "evidence"
            ), mock.patch.object(
                brief, "LOG_DIR", root / "ledger"
            ), mock.patch.object(
                brief, "SEND_ATTEMPT_LOG", root / "ledger" / "send-attempts.jsonl"
            ), contextlib.redirect_stdout(output):
                exit_code = brief.cmd_verify_windows(mock.Mock())

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["windows"], [])
        self.assertEqual(payload["ignored_nonslot_windows"], [scheduled_for])

    def test_readback_window_rejects_non_string_slot_before_provider_read(self):
        row = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "trigger": "launchd-calendar",
            "slot": [],
            "scheduled_for": "2026-08-12T08:00:00-04:00",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window_log = root / "windows.jsonl"
            mailbox_log = root / "mailbox.jsonl"
            window_log.write_text(json.dumps(row) + "\n", encoding="utf-8")
            window_log.chmod(0o600)
            with mock.patch.object(brief, "WINDOW_LOG", window_log), mock.patch.object(
                brief, "MAILBOX_READBACK_LOG", mailbox_log
            ), mock.patch.object(
                brief, "fetch_superhuman_mailbox_readback"
            ) as provider, contextlib.redirect_stderr(io.StringIO()):
                exit_code = brief.cmd_readback_window(
                    mock.Mock(scheduled_for=None)
                )

        self.assertEqual(exit_code, 2)
        provider.assert_not_called()

    def test_window_verifier_requires_exact_true_on_schedule_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = _write_m5_pair(Path(tmp))
            malformed_window = str(rows[0]["scheduled_for"])
            rows[0]["on_schedule"] = "yes"

            result = brief.verify_window_receipts(rows, evidence_dir=Path(tmp))

        self.assertNotIn(malformed_window, result["windows"])
        self.assertIn(
            "need two distinct current-schema natural 08:00/20:00 windows; found 1",
            result["problems"],
        )

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
        self.assertEqual(
            brief._parse_aware_datetime("2026-08-13T00:06:00Z"),
            brief.datetime.fromisoformat("2026-08-13T00:06:00+00:00"),
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
                host_timezone="America/New_York",
            ),
            [],
        )
        self.assertEqual(
            brief.schedule_configuration_problems(
                expected,
                expected,
                host_timezone="America/Bogota",
            ),
            ["HostTimezone"],
        )
        self.assertTrue(
            brief.host_timezone_matches_report("America/New_York")
        )
        self.assertFalse(
            brief.host_timezone_matches_report("America/Bogota")
        )
        self.assertFalse(
            brief.host_timezone_matches_report("Etc/UTC")
        )
        self.assertIn(
            "set the macOS system timezone to America/New_York",
            brief.schedule_configuration_recovery(["HostTimezone"]),
        )

    def test_schedule_status_rejects_an_alternate_program_and_other_scheduled_producers(self):
        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            agents = home / "Library" / "LaunchAgents"
            agents.mkdir(parents=True)
            alternate = home / "other" / "shadow-brief.py"
            alternate.parent.mkdir()
            alternate.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            canonical = agents / f"{brief.LABEL}.plist"
            canonical.write_bytes(
                plistlib.dumps(brief.launch_agent_plist(alternate), fmt=plistlib.FMT_XML)
            )
            duplicate = agents / "com.example.shadow-copy.plist"
            duplicate_doc = brief.launch_agent_plist(Path(brief.__file__).resolve())
            duplicate_doc["Label"] = "com.example.shadow-copy"
            duplicate.write_bytes(plistlib.dumps(duplicate_doc, fmt=plistlib.FMT_XML))
            cli_duplicate = agents / "com.example.shadow-cli.plist"
            cli_duplicate.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-cli",
                        "ProgramArguments": [
                            "/usr/local/bin/shadow",
                            "brief",
                            "run",
                            "--scheduled-trigger",
                        ],
                        "StartCalendarInterval": {"Hour": 8, "Minute": 0},
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            unrelated = agents / "com.example.unrelated.plist"
            unrelated.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.unrelated",
                        "ProgramArguments": ["/bin/echo", "--scheduled-trigger"],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            with mock.patch.object(brief.Path, "home", return_value=home), mock.patch.object(
                brief, "_host_timezone_name", return_value="America/New_York"
            ), mock.patch.object(
                brief,
                "_run",
                return_value=subprocess.CompletedProcess([], 0, "loaded", ""),
            ):
                status = brief.schedule_status()

        self.assertFalse(status["configuration_ok"])
        self.assertIn("ProgramArguments", status["configuration_problems"])
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-copy.plist",
            status["configuration_problems"],
        )
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-cli.plist",
            status["configuration_problems"],
        )
        self.assertNotIn(
            "OtherScheduledBriefLaunchAgent:com.example.unrelated.plist",
            status["configuration_problems"],
        )

    def test_schedule_status_reports_other_producer_even_when_canonical_plist_is_missing(self):
        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            agents = home / "Library" / "LaunchAgents"
            agents.mkdir(parents=True)
            duplicate = agents / "com.example.shadow-copy.plist"
            duplicate_doc = brief.launch_agent_plist(Path(brief.__file__).resolve())
            duplicate_doc["Label"] = "com.example.shadow-copy"
            duplicate.write_bytes(plistlib.dumps(duplicate_doc, fmt=plistlib.FMT_XML))

            with mock.patch.object(brief.Path, "home", return_value=home), mock.patch.object(
                brief, "_host_timezone_name", return_value="America/New_York"
            ):
                status = brief.schedule_status()

        self.assertFalse(status["installed"])
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-copy.plist",
            status["configuration_problems"],
        )

    def test_schedule_status_detects_shell_wrapped_producer_without_echo_false_positive(self):
        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            agents = home / "Library" / "LaunchAgents"
            agents.mkdir(parents=True)
            canonical = agents / f"{brief.LABEL}.plist"
            with mock.patch.object(brief.Path, "home", return_value=home):
                canonical_doc = brief.launch_agent_plist(
                    Path(brief.__file__).resolve()
                )
            canonical.write_bytes(
                plistlib.dumps(
                    canonical_doc,
                    fmt=plistlib.FMT_XML,
                )
            )
            wrapped = agents / "com.example.shadow-wrapped.plist"
            wrapped.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-wrapped",
                        "ProgramArguments": [
                            "/bin/zsh",
                            "-lc",
                            "/usr/local/bin/shadow brief run --deliver --scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            unrelated = agents / "com.example.shadow-quoted.plist"
            unrelated.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-quoted",
                        "ProgramArguments": [
                            "/bin/zsh",
                            "-lc",
                            "printf '%s' 'shadow brief run --scheduled-trigger'",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            echo_script_name = agents / "com.example.shadow-echo-script-name.plist"
            echo_script_name.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-echo-script-name",
                        "ProgramArguments": [
                            "/bin/echo",
                            "/tmp/shadow-brief.py",
                            "--scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            compound = agents / "com.example.shadow-compound.plist"
            compound.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-compound",
                        "ProgramArguments": [
                            "/bin/zsh",
                            "-lc",
                            "cd /tmp && /usr/local/bin/shadow brief run "
                            "--deliver --scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            no_command_option = agents / "com.example.shadow-bash-norc.plist"
            no_command_option.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-bash-norc",
                        "ProgramArguments": [
                            "/bin/bash",
                            "--norc",
                            "shadow brief run --scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            assigned = agents / "com.example.shadow-assigned.plist"
            assigned.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-assigned",
                        "ProgramArguments": [
                            "/bin/zsh",
                            "-lc",
                            "PATH=/usr/local/bin:$PATH /usr/local/bin/shadow "
                            "brief run --scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            env_unset = agents / "com.example.shadow-env-unset.plist"
            env_unset.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-env-unset",
                        "ProgramArguments": [
                            "/usr/bin/env",
                            "-u",
                            "PYTHONPATH",
                            "/usr/local/bin/shadow",
                            "brief",
                            "run",
                            "--scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            python_flags = agents / "com.example.shadow-python-flags.plist"
            python_flags.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-python-flags",
                        "ProgramArguments": [
                            "/usr/bin/python3",
                            "-I",
                            "-X",
                            "dev",
                            str(Path(brief.__file__).resolve()),
                            "run",
                            "--scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )
            python_hash_policy = agents / "com.example.shadow-python-hash-policy.plist"
            python_hash_policy.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.shadow-python-hash-policy",
                        "ProgramArguments": [
                            "/usr/bin/python3",
                            "--check-hash-based-pycs",
                            "always",
                            str(Path(brief.__file__).resolve()),
                            "run",
                            "--scheduled-trigger",
                        ],
                    },
                    fmt=plistlib.FMT_XML,
                )
            )

            with mock.patch.object(brief.Path, "home", return_value=home), mock.patch.object(
                brief, "_host_timezone_name", return_value="America/New_York"
            ), mock.patch.object(
                brief,
                "_run",
                return_value=subprocess.CompletedProcess([], 0, "loaded", ""),
            ):
                status = brief.schedule_status()

        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-wrapped.plist",
            status["configuration_problems"],
        )
        self.assertNotIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-quoted.plist",
            status["configuration_problems"],
        )
        self.assertNotIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-echo-script-name.plist",
            status["configuration_problems"],
        )
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-compound.plist",
            status["configuration_problems"],
        )
        self.assertNotIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-bash-norc.plist",
            status["configuration_problems"],
        )
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-assigned.plist",
            status["configuration_problems"],
        )
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-env-unset.plist",
            status["configuration_problems"],
        )
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-python-flags.plist",
            status["configuration_problems"],
        )
        self.assertIn(
            "OtherScheduledBriefLaunchAgent:com.example.shadow-python-hash-policy.plist",
            status["configuration_problems"],
        )

    def test_schedule_install_command_requires_post_install_configuration_proof(self):
        with mock.patch.object(
            brief,
            "schedule_install",
            return_value={
                "bootstrap_rc": 0,
                "host_timezone_matches_report": True,
                "configuration_ok": False,
                "launchctl_ok": True,
            },
        ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(brief.cmd_schedule(mock.Mock(install=True)), 1)

    def test_schedule_command_fails_closed_on_install_or_status_drift(self):
        with mock.patch.object(
            brief,
            "schedule_install",
            return_value={
                "bootstrap_rc": 1,
                "host_timezone_matches_report": True,
            },
        ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(brief.cmd_schedule(mock.Mock(install=True)), 1)

        with mock.patch.object(
            brief,
            "schedule_status",
            return_value={
                "installed": True,
                "configuration_ok": False,
                "launchctl_ok": True,
            },
        ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(brief.cmd_schedule(mock.Mock(install=False)), 1)

    def test_doctor_keeps_timezone_recovery_when_schedule_is_also_unarmed(self):
        with tempfile.TemporaryDirectory() as home_dir, mock.patch.object(
            brief.Path,
            "home",
            return_value=Path(home_dir),
        ), mock.patch.object(
            brief,
            "_host_timezone_name",
            return_value="America/Bogota",
        ):
            schedule = brief.schedule_status()

        self.assertFalse(schedule["installed"])
        self.assertEqual(schedule.get("configuration_problems"), ["HostTimezone"])
        with tempfile.TemporaryDirectory() as evidence_dir, mock.patch.object(
            brief,
            "EVIDENCE_DIR",
            Path(evidence_dir),
        ), mock.patch.object(
            brief,
            "schedule_status",
            return_value=schedule,
        ), mock.patch.object(
            brief,
            "_mcp_remote_token",
            return_value="available",
        ), contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(brief.doctor(), 1)

        payload = json.loads(stdout.getvalue())
        self.assertTrue(
            any(
                "set the macOS system timezone to America/New_York" in problem
                for problem in payload["problems"]
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
                "generated_at": evening,
                "board_revision": 41,
                "receipt": {"subject": "subject-evening"},
            },
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": "morning",
                "scheduled_for": morning,
                "generated_at": morning,
                "board_revision": 41,
                "receipt": {"subject": "subject-morning"},
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
                "subject": f"subject-{suffix}",
                "generated_at": scheduled_for,
                "board_revision": 41,
                "message_id": f"mailbox-{suffix}",
                "thread_id": f"thread-{suffix}",
                "labels": ["SENT"],
                "raw_html_sha256": "a" * 64,
                "sent_at": scheduled_for,
            }

        verification_template = {
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
            evidence = root / "evidence"
            ledger = root / "ledger"
            window_log.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            window_log.chmod(0o600)
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
            mailbox_log.chmod(0o600)
            output = io.StringIO()
            with mock.patch.object(brief, "WINDOW_LOG", window_log), mock.patch.object(
                brief, "MAILBOX_READBACK_LOG", mailbox_log
            ), mock.patch.object(
                brief, "EVIDENCE_DIR", evidence
            ), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "SEND_ATTEMPT_LOG", ledger / "send-attempts.jsonl"
            ), mock.patch.object(
                brief, "verify_window_receipts", return_value=verification_template
            ) as verify, contextlib.redirect_stdout(output):
                exit_code = brief.cmd_verify_windows(mock.Mock())

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["mailbox_readbacks"]["message_ids"],
            ["mailbox-evening", "mailbox-morning"],
        )
        verify.assert_called_once_with(
            rows,
            evidence_dir=evidence,
            ledger_dir=ledger,
            send_attempt_log=ledger / "send-attempts.jsonl",
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
            window_log.chmod(0o600)
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

    def test_verify_windows_reports_unsafe_window_and_mailbox_ledgers(self):
        verification_template = {
            "ok": True,
            "problems": [],
            "windows": [
                "2026-08-12T08:00:00-04:00",
                "2026-08-12T20:00:00-04:00",
            ],
            "message_ids": [],
            "ignored_legacy_windows": [],
            "ignored_noncalendar_windows": [],
            "ignored_nonslot_windows": [],
        }
        valid_rows = [
            {
                "schema": brief.WINDOW_RECEIPT_SCHEMA,
                "on_schedule": True,
                "trigger": "launchd-calendar",
                "slot": slot,
                "scheduled_for": scheduled_for,
            }
            for slot, scheduled_for in (
                ("morning", "2026-08-12T08:00:00-04:00"),
                ("evening", "2026-08-12T20:00:00-04:00"),
            )
        ]
        for ledger_name in ("window", "mailbox"):
            for corruption in ("symlink", "invalid-json"):
                with self.subTest(
                    ledger=ledger_name,
                    corruption=corruption,
                ), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    window_log = root / "windows.jsonl"
                    mailbox_log = root / "mailbox.jsonl"
                    window_log.write_text(
                        "\n".join(json.dumps(row) for row in valid_rows) + "\n",
                        encoding="utf-8",
                    )
                    window_log.chmod(0o600)
                    mailbox_log.write_text("{}\n", encoding="utf-8")
                    mailbox_log.chmod(0o600)
                    unsafe = window_log if ledger_name == "window" else mailbox_log
                    unsafe.unlink()
                    if corruption == "symlink":
                        target = root / f"{ledger_name}-target.jsonl"
                        target.write_text("{}\n", encoding="utf-8")
                        target.chmod(0o600)
                        unsafe.symlink_to(target)
                    else:
                        unsafe.write_text('{"truncated":\n', encoding="utf-8")
                        unsafe.chmod(0o600)
                    stdout = io.StringIO()
                    verification = {
                        **verification_template,
                        "ok": True,
                        "problems": [],
                        "windows": (
                            []
                            if ledger_name == "mailbox"
                            else list(verification_template["windows"])
                        ),
                    }
                    verify = mock.Mock(return_value=verification)
                    with mock.patch.object(
                        brief,
                        "WINDOW_LOG",
                        window_log,
                    ), mock.patch.object(
                        brief,
                        "MAILBOX_READBACK_LOG",
                        mailbox_log,
                    ), mock.patch.object(
                        brief,
                        "verify_window_receipts",
                        verify,
                    ), contextlib.redirect_stdout(stdout):
                        try:
                            exit_code = brief.cmd_verify_windows(mock.Mock())
                        except (OSError, UnicodeError, KeyError, TypeError) as exc:
                            self.fail(f"unsafe {ledger_name} ledger escaped: {exc}")

                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(exit_code, 1)
                    self.assertFalse(payload["ok"])
                    self.assertTrue(
                        any(
                            ledger_name in problem
                            and "unsafe or corrupt" in problem
                            for problem in payload["problems"]
                        ),
                        payload,
                    )
                    if ledger_name == "window":
                        verify.assert_not_called()

    def test_readback_window_blocks_unsafe_ledger_before_provider_or_append(self):
        for corruption in ("symlink", "invalid-json"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                window_log = root / "windows.jsonl"
                if corruption == "symlink":
                    target = root / "target.jsonl"
                    target.write_text("{}\n", encoding="utf-8")
                    target.chmod(0o600)
                    window_log.symlink_to(target)
                else:
                    window_log.write_text('{"truncated":\n', encoding="utf-8")
                    window_log.chmod(0o600)
                mailbox_log = root / "mailbox.jsonl"
                fetch = mock.Mock()
                append = mock.Mock()
                stdout = io.StringIO()
                with mock.patch.object(
                    brief,
                    "WINDOW_LOG",
                    window_log,
                ), mock.patch.object(
                    brief,
                    "MAILBOX_READBACK_LOG",
                    mailbox_log,
                ), mock.patch.object(
                    brief,
                    "fetch_superhuman_mailbox_readback",
                    fetch,
                ), mock.patch.object(
                    brief,
                    "_append_private_jsonl",
                    append,
                ), contextlib.redirect_stdout(stdout):
                    try:
                        exit_code = brief.cmd_readback_window(
                            mock.Mock(scheduled_for=None)
                        )
                    except (OSError, UnicodeError) as exc:
                        self.fail(f"unsafe window ledger escaped: {exc}")

                try:
                    payload = json.loads(stdout.getvalue())
                except json.JSONDecodeError as exc:
                    self.fail(f"unsafe window ledger was not reported as JSON: {exc}")
                self.assertEqual(exit_code, 1)
                self.assertEqual(payload["status"], "blocked")
                self.assertIn("unsafe or corrupt", payload["wake"])
                fetch.assert_not_called()
                append.assert_not_called()

    def test_readback_window_blocks_unsafe_mailbox_ledger_before_provider(self):
        valid_window = {
            "schema": brief.WINDOW_RECEIPT_SCHEMA,
            "on_schedule": True,
            "trigger": "launchd-calendar",
            "slot": "morning",
            "scheduled_for": "2026-08-12T08:00:00-04:00",
        }
        for corruption in ("symlink", "invalid-json"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                window_log = root / "windows.jsonl"
                window_log.write_text(
                    json.dumps(valid_window) + "\n",
                    encoding="utf-8",
                )
                window_log.chmod(0o600)
                mailbox_log = root / "mailbox.jsonl"
                if corruption == "symlink":
                    target = root / "mailbox-target.jsonl"
                    target.write_text("{}\n", encoding="utf-8")
                    target.chmod(0o600)
                    mailbox_log.symlink_to(target)
                else:
                    mailbox_log.write_text('{"truncated":\n', encoding="utf-8")
                    mailbox_log.chmod(0o600)
                fetch = mock.Mock(return_value={"status": "blocked"})
                append = mock.Mock()
                stdout = io.StringIO()
                with mock.patch.object(
                    brief,
                    "WINDOW_LOG",
                    window_log,
                ), mock.patch.object(
                    brief,
                    "MAILBOX_READBACK_LOG",
                    mailbox_log,
                ), mock.patch.object(
                    brief,
                    "fetch_superhuman_mailbox_readback",
                    fetch,
                ), mock.patch.object(
                    brief,
                    "_append_private_jsonl",
                    append,
                ), contextlib.redirect_stdout(stdout):
                    exit_code = brief.cmd_readback_window(
                        mock.Mock(scheduled_for=None)
                    )

                payload = json.loads(stdout.getvalue())
                self.assertEqual(exit_code, 1)
                self.assertEqual(payload["status"], "blocked")
                self.assertIn("mailbox ledger is unsafe or corrupt", payload["wake"])
                fetch.assert_not_called()
                append.assert_not_called()

    def test_dynamic_linked_coverage_requires_complete_or_honest_unknown_state(self):
        def complete_expected_roster(mail):
            third = mail["coverage"][2]
            third.update(
                {
                    "linked": True,
                    "status": "COMPLETE",
                    "pagination": {
                        "pages": 1,
                        "exhausted": True,
                        "truncated": False,
                    },
                }
            )
            third.pop("problems", None)
            third.pop("wake", None)
            mail["linked_accounts"].append(
                {
                    "acting_email": "firstbitelabs@gmail.com",
                    "is_primary": False,
                    "added_at": "2026-01-03T00:00:00Z",
                    "sender_identities": ["firstbitelabs@gmail.com"],
                    "sender_identity_complete": True,
                }
            )
            mail.update(
                {"status": "COMPLETE", "complete": True, "all_clear_allowed": True}
            )

        linked = {
            "acting_email": "newly-linked@example.com",
            "is_primary": False,
            "added_at": "2026-08-14T00:00:00Z",
            "sender_identities": ["newly-linked@example.com"],
            "sender_identity_complete": True,
        }
        complete_coverage = {
            "acting_email": "newly-linked@example.com",
            "expected": False,
            "linked": True,
            "status": "COMPLETE",
            "pagination": {"pages": 1, "exhausted": True, "truncated": False},
        }

        complete = _m5_mail_fixture()
        complete_expected_roster(complete)
        complete["linked_accounts"].append(linked)
        complete["coverage"].append(complete_coverage)
        self.assertEqual(brief._superhuman_receipt_problems(complete), [])

        garbage = _m5_mail_fixture()
        complete_expected_roster(garbage)
        garbage["linked_accounts"].append(linked)
        garbage["coverage"].append({**complete_coverage, "status": "GARBAGE"})
        self.assertIn(
            "invalid linked Superhuman identity coverage state: newly-linked@example.com",
            brief._superhuman_receipt_problems(garbage),
        )

        unknown = _m5_mail_fixture()
        complete_expected_roster(unknown)
        unknown["linked_accounts"].append(linked)
        unknown["coverage"].append(
            {
                **complete_coverage,
                "status": "UNKNOWN",
                "problems": ["provider pagination was truncated"],
                "wake": "Rerun the bounded read-only account scan.",
            }
        )
        self.assertIn(
            "UNKNOWN mail coverage claimed an all-clear",
            brief._superhuman_receipt_problems(unknown),
        )
        unknown.update(
            {"status": "UNKNOWN", "complete": False, "all_clear_allowed": False}
        )
        unknown_problems = brief._superhuman_receipt_problems(unknown)
        self.assertNotIn(
            "invalid linked Superhuman identity coverage state: newly-linked@example.com",
            unknown_problems,
        )
        self.assertNotIn("UNKNOWN mail coverage claimed an all-clear", unknown_problems)

    def test_linked_complete_coverage_requires_exhausted_clean_pagination(self):
        producer_positive = _m5_mail_fixture()
        producer_positive["coverage"][0]["pagination"]["pages"] = 2
        self.assertEqual(
            brief._superhuman_receipt_problems(producer_positive),
            [],
        )

        for mutation in (
            {"pagination": {"pages": True, "exhausted": True, "truncated": False}},
            {"pagination": {"pages": 0, "exhausted": True, "truncated": False}},
            {"pagination": {"pages": -1, "exhausted": True, "truncated": False}},
            {"pagination": {"pages": 1, "exhausted": False, "truncated": False}},
            {"pagination": {"pages": 1, "exhausted": True, "truncated": True}},
            {"problems": ["cursor coverage was incomplete"]},
        ):
            with self.subTest(mutation=mutation):
                mail = _m5_mail_fixture()
                linked = {
                    "acting_email": "newly-linked@example.com",
                    "is_primary": False,
                    "added_at": "2026-08-14T00:00:00Z",
                    "sender_identities": ["newly-linked@example.com"],
                    "sender_identity_complete": True,
                }
                coverage = {
                    "acting_email": "newly-linked@example.com",
                    "expected": False,
                    "linked": True,
                    "status": "COMPLETE",
                    "pagination": {
                        "pages": 1,
                        "exhausted": True,
                        "truncated": False,
                    },
                    "problems": [],
                    **mutation,
                }
                mail["linked_accounts"].append(linked)
                mail["coverage"].append(coverage)

                problems = brief._superhuman_receipt_problems(mail)

                self.assertIn(
                    "invalid linked Superhuman identity coverage state: newly-linked@example.com",
                    problems,
                )

    def test_real_obligation_is_retained_linked_and_strictly_shaped(self):
        malformed_cases = []
        orphan = _m5_mail_fixture()
        orphan["signals"] = []
        malformed_cases.append(("orphan", orphan))

        unlinked = _m5_mail_fixture()
        unlinked_action = dict(unlinked["urgent_replies"][0])
        unlinked_action["source_identities"] = ["unlinked@example.com"]
        unlinked["urgent_replies"] = [unlinked_action]
        malformed_cases.append(("unlinked-source", unlinked))

        wrong_types = _m5_mail_fixture()
        malformed_action = dict(wrong_types["urgent_replies"][0])
        malformed_action.update(
            {
                "signal_id": 123,
                "subject": 7,
                "proposal": {"text": "not a string"},
                "action_tags": ["reply", 3],
                "source_identities": "leojkwan@gmail.com",
            }
        )
        wrong_types["urgent_replies"] = [malformed_action]
        malformed_cases.append(("wrong-types", wrong_types))

        bucket_tag_cases = {
            "urgent_replies": ["neutral"],
            "waiting_replies": ["reply"],
            "order_return_follow_up": ["reply"],
            "forgotten_obligations": ["urgent"],
        }
        for bucket, tags in bucket_tag_cases.items():
            mail = _m5_mail_fixture()
            action = {**mail["signals"][0], "action_tags": tags}
            mail["signals"] = [action]
            for obligation_bucket in (
                "urgent_replies",
                "waiting_replies",
                "order_return_follow_up",
                "forgotten_obligations",
            ):
                mail[obligation_bucket] = []
            mail[bucket] = [dict(action)]
            malformed_cases.append((f"{bucket}-tags", mail))

        self.assertNotIn(
            "no real mail obligation or action proposal",
            brief._superhuman_receipt_problems(_m5_mail_fixture()),
        )
        for name, mail in malformed_cases:
            with self.subTest(name=name):
                self.assertIn(
                    "no real mail obligation or action proposal",
                    brief._superhuman_receipt_problems(mail),
                )

    def test_superhuman_action_buckets_reject_non_object_rows(self):
        for bucket in (
            "signals",
            "urgent_replies",
            "waiting_replies",
            "forgotten_obligations",
            "order_return_follow_up",
            "proactive_candidates",
            "calendar_proposals",
        ):
            with self.subTest(bucket=bucket):
                mail = _m5_mail_fixture()
                mail[bucket].append(7)

                problems = brief._superhuman_receipt_problems(mail)

                self.assertIn(
                    f"Superhuman {bucket} row must be an object",
                    problems,
                )

    def test_mcp_payload_parsers_fail_closed_on_json_decoder_limits(self):
        text_result = {
            "result": {
                "content": [
                    {"type": "text", "text": '{"threads": []}'},
                ]
            }
        }
        for exc in (
            ValueError("integer string conversion limit exceeded"),
            RecursionError("maximum recursion depth exceeded"),
        ):
            with self.subTest(exception=type(exc).__name__), mock.patch.object(
                brief.json, "loads", side_effect=exc
            ):
                plain = brief._parse_mcp_sse('{"result": {}}')
                streamed = brief._parse_mcp_sse('data: {"result": {}}')
                payload = brief._mcp_text_payload(text_result)

                self.assertIn("raw", plain)
                self.assertIn("raw", streamed)
                self.assertEqual(payload, {})

    def test_producer_identity_fields_reject_non_string_numeric_lookalikes(self):
        self.assertFalse(brief._is_full_git_object_id(int("1" * 40)))
        self.assertFalse(
            brief._valid_producer_provenance(
                {
                    "schema": brief.PRODUCER_PROVENANCE_SCHEMA,
                    "source_commit": int("1" * 40),
                    "script_sha256": int("2" * 64),
                    "source_matches_commit": True,
                }
            )
        )

    def test_nested_receipt_and_notification_shapes_never_crash_verifiers(self):
        for field in ("receipt", "notification"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                rows = _write_m5_pair(Path(tmp))
                rows[0][field] = []
                try:
                    result = brief.verify_window_receipts(rows)
                except (AttributeError, TypeError) as exc:
                    self.fail(f"JSON-valid {field} list crashed window verifier: {exc}")
                self.assertIn(
                    f"2026-08-12T08:00:00-04:00: {field} must be an object",
                    result["problems"],
                )

        with tempfile.TemporaryDirectory() as tmp:
            window = _write_m5_pair(Path(tmp))[0]
            window["receipt"] = []
            readback = {
                "schema": brief.MAILBOX_READBACK_SCHEMA,
                "status": "EXACT_SENT_CONFIRMED",
                "scheduled_for": window["scheduled_for"],
                "acting_email": brief.SELF_MAIL,
                "from": brief.SELF_MAIL,
                "to": [brief.SELF_MAIL],
                "subject": "irrelevant",
                "generated_at": window["generated_at"],
                "board_revision": window["board_revision"],
                "message_id": "mailbox-message",
                "thread_id": "mailbox-thread",
                "labels": ["SENT"],
                "raw_html_sha256": "a" * 64,
                "sent_at": "2026-08-12T08:06:00-04:00",
            }
            try:
                mailbox = brief.verify_mailbox_readbacks([window], [readback])
            except (AttributeError, TypeError) as exc:
                self.fail(f"JSON-valid receipt list crashed mailbox verifier: {exc}")
        self.assertIn(
            "2026-08-12T08:00:00-04:00: window receipt must be an object",
            mailbox["problems"],
        )

    def test_window_and_mailbox_stable_ids_require_exact_json_types(self):
        window_cases = (
            ("message_id", ["message-in-list"], "sent-message receipt missing"),
            ("message_id", True, "sent-message receipt missing"),
            ("attempt_id", {"id": "attempt-in-object"}, "durable pre-send attempt receipt missing"),
            ("attempt_id", True, "durable pre-send attempt receipt missing"),
        )
        for field, value, expected_problem in window_cases:
            with self.subTest(window_field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                rows = _write_m5_pair(Path(tmp))
                rows[0]["receipt"][field] = value
                try:
                    result = brief.verify_window_receipts(rows)
                except TypeError as exc:
                    self.fail(f"JSON-valid window {field} crashed verifier: {exc}")
                self.assertIn(
                    f"2026-08-12T08:00:00-04:00: {expected_problem}",
                    result["problems"],
                )

        mailbox_cases = (
            ("message_id", ["message-in-list"], "stable mailbox identity missing"),
            ("message_id", True, "stable mailbox identity missing"),
            ("thread_id", {"id": "thread-in-object"}, "stable mailbox identity missing"),
            ("labels", True, "mailbox labels must be a string list"),
            ("labels", ["SENT", 7], "mailbox labels must be a string list"),
        )
        for field, value, expected_problem in mailbox_cases:
            with self.subTest(mailbox_field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                window = _write_m5_pair(Path(tmp))[0]
                readback = {
                    "schema": brief.MAILBOX_READBACK_SCHEMA,
                    "status": "EXACT_SENT_CONFIRMED",
                    "scheduled_for": window["scheduled_for"],
                    "acting_email": brief.SELF_MAIL,
                    "from": brief.SELF_MAIL,
                    "to": [brief.SELF_MAIL],
                    "subject": window["receipt"]["subject"],
                    "generated_at": window["generated_at"],
                    "board_revision": window["board_revision"],
                    "message_id": "mailbox-message",
                    "thread_id": "mailbox-thread",
                    "labels": ["SENT"],
                    "raw_html_sha256": "a" * 64,
                    "sent_at": "2026-08-12T08:06:00-04:00",
                }
                readback[field] = value
                try:
                    result = brief.verify_mailbox_readbacks([window], [readback])
                except TypeError as exc:
                    self.fail(f"JSON-valid mailbox {field} crashed verifier: {exc}")
                self.assertIn(
                    f"2026-08-12T08:00:00-04:00: {expected_problem}",
                    result["problems"],
                )

    def test_window_and_mailbox_board_revision_rejects_boolean_int_lookalike(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = _write_m5_pair(Path(tmp))
            rows[0]["board_revision"] = True

            window_result = brief.verify_window_receipts(rows)

            window = rows[0]
            readback = {
                "schema": brief.MAILBOX_READBACK_SCHEMA,
                "status": "EXACT_SENT_CONFIRMED",
                "scheduled_for": window["scheduled_for"],
                "acting_email": brief.SELF_MAIL,
                "from": brief.SELF_MAIL,
                "to": [brief.SELF_MAIL],
                "subject": window["receipt"]["subject"],
                "generated_at": window["generated_at"],
                "board_revision": True,
                "message_id": "mailbox-message",
                "thread_id": "mailbox-thread",
                "labels": ["SENT"],
                "raw_html_sha256": "a" * 64,
                "sent_at": "2026-08-12T08:06:00-04:00",
            }
            mailbox_result = brief.verify_mailbox_readbacks(
                [window],
                [readback],
            )

        self.assertIn(
            "2026-08-12T08:00:00-04:00: missing board revision",
            window_result["problems"],
        )
        self.assertIn(
            "2026-08-12T08:00:00-04:00: mailbox board revision invalid",
            mailbox_result["problems"],
        )

    def test_board_revision_reader_rejects_boolean_int_lookalike(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text('{"revision": true}\n', encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path):
                revision = brief._read_board_revision()

        self.assertIsNone(revision)

    def test_board_revision_reader_returns_none_on_json_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text('{"revision": 1}\n', encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path), mock.patch.object(
                brief.json,
                "loads",
                side_effect=ValueError("integer string conversion limit exceeded"),
            ):
                revision = brief._read_board_revision()

        self.assertIsNone(revision)

    def test_board_revision_reader_returns_none_on_json_recursion_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text('{"revision": 1}\n', encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path), mock.patch.object(
                brief.json,
                "loads",
                side_effect=RecursionError("maximum recursion depth exceeded"),
            ):
                revision = brief._read_board_revision()

        self.assertIsNone(revision)

    def test_board_revision_reader_returns_none_when_json_root_is_not_an_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            board_path = Path(tmp) / "board.json"
            board_path.write_text("[]\n", encoding="utf-8")
            with mock.patch.object(brief, "BOARD_PATH", board_path):
                revision = brief._read_board_revision()

        self.assertIsNone(revision)

    def test_packet_authority_does_not_stabilize_on_boolean_board_revision(self):
        board = {"revision": True, "entities": [], "claims": []}
        with mock.patch.object(
            brief, "portfolio_root", return_value=Path("/tmp/portfolio")
        ), mock.patch.object(
            brief, "collect_repos", return_value=[]
        ), mock.patch.object(
            brief, "collect_github", return_value=[]
        ), mock.patch.object(
            brief, "collect_vercel", return_value={"available": False}
        ), mock.patch.object(
            brief, "collect_supabase", return_value={"available": False}
        ), mock.patch.object(
            brief, "collect_superhuman_context", return_value=_m5_mail_fixture()
        ), mock.patch.object(
            brief, "collect_growth_source_status", return_value={}
        ), mock.patch.object(
            brief, "build_local_git_health", return_value={"available": True}
        ), mock.patch.object(
            brief, "build_paint_health", return_value={}
        ), mock.patch.object(
            brief, "collect_shadow_status_excerpt", return_value="status"
        ), mock.patch.object(
            brief, "collect_board", return_value=board
        ), mock.patch.object(
            brief, "_read_board_revision", return_value=1
        ), mock.patch.object(
            brief, "build_shadow_board_health", return_value={"available": False}
        ), mock.patch.object(
            brief, "collect_snowcubes_context", return_value={"surfaces": []}
        ), mock.patch.object(
            brief, "build_recommendations", return_value=[]
        ), mock.patch.object(
            brief, "build_chief_of_staff_analysis", return_value={}
        ), mock.patch.object(
            brief, "producer_provenance", return_value=_m5_producer_fixture()
        ):
            packet = brief.collect_packet(slot="morning")

        self.assertFalse(packet["authority"]["board_snapshot"]["consistent"])

    def test_archive_proof_rejects_boolean_revision_equal_to_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = _write_m5_pair(root)
            rows[0]["board_revision"] = 1
            _rewrite_m5_packet(
                rows[0],
                lambda packet: (
                    packet["board"].update({"revision": True}),
                    packet["authority"]["board_snapshot"].update(
                        {"revision": True}
                    ),
                ),
            )

            result = brief.verify_window_receipts(rows, evidence_dir=root)

        self.assertIn(
            "2026-08-12T08:00:00-04:00: archived JSON board revision mismatch",
            result["problems"],
        )
        self.assertIn(
            "2026-08-12T08:00:00-04:00: board snapshot consistency missing",
            result["problems"],
        )

    def test_window_verifier_requires_exact_send_attempt_intent_and_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            attempts = ledger / "send-attempts.jsonl"
            evidence.mkdir()
            rows = _write_m5_pair(evidence, ledger, attempts)
            try:
                positive = brief.verify_window_receipts(
                    rows,
                    evidence_dir=evidence,
                    ledger_dir=ledger,
                    send_attempt_log=attempts,
                )
            except TypeError as exc:
                self.fail(f"send-attempt verifier seam is missing: {exc}")
            self.assertTrue(positive["ok"], positive["problems"])

            evening_attempt_id = rows[1]["receipt"]["attempt_id"]
            rows[1]["receipt"]["attempt_id"] = rows[0]["receipt"]["attempt_id"]
            duplicated = brief.verify_window_receipts(
                rows,
                evidence_dir=evidence,
                ledger_dir=ledger,
                send_attempt_log=attempts,
            )
            self.assertIn(
                "scheduled windows do not have distinct send-attempt receipts",
                duplicated["problems"],
            )
            rows[1]["receipt"]["attempt_id"] = evening_attempt_id

            original_attempt_rows = [
                json.loads(line)
                for line in attempts.read_text(encoding="utf-8").splitlines()
            ]

            def write_attempt_rows(candidate_rows):
                attempts.write_text(
                    "\n".join(json.dumps(row) for row in candidate_rows) + "\n",
                    encoding="utf-8",
                )
                attempts.chmod(0o600)

            def assert_morning_invalid():
                result = brief.verify_window_receipts(
                    rows,
                    evidence_dir=evidence,
                    ledger_dir=ledger,
                    send_attempt_log=attempts,
                )
                self.assertIn(
                    "2026-08-12T08:00:00-04:00: scheduled send attempt ledger proof is invalid",
                    result["problems"],
                )

            mismatched_outcome = json.loads(json.dumps(original_attempt_rows))
            mismatched_outcome[1]["message_id"] = "wrong-message"
            write_attempt_rows(mismatched_outcome)
            assert_morning_invalid()

            unexpected_key = json.loads(json.dumps(original_attempt_rows))
            unexpected_key[0]["unexpected"] = True
            write_attempt_rows(unexpected_key)
            assert_morning_invalid()

            for name, candidate_rows in (
                ("missing-intent", original_attempt_rows[1:]),
                (
                    "missing-outcome",
                    [original_attempt_rows[0], *original_attempt_rows[2:]],
                ),
            ):
                with self.subTest(attempt_mutation=name):
                    write_attempt_rows(candidate_rows)
                    assert_morning_invalid()

            duplicate_state = json.loads(json.dumps(original_attempt_rows))
            duplicate_state[1]["state"] = "UNKNOWN_NO_RETRY"
            write_attempt_rows(duplicate_state)
            assert_morning_invalid()

            for name, index, key, value in (
                ("intent-html", 0, "html_sha256", "c" * 64),
                ("intent-route", 0, "acting_email", "other@example.com"),
                ("intent-subject", 0, "subject", "Different subject"),
                ("intent-draft", 0, "draft_id", "different-draft"),
                ("outcome-thread", 1, "thread_id", "different-thread"),
                (
                    "outcome-sent-at",
                    1,
                    "sent_at",
                    "2026-08-12T08:07:00-04:00",
                ),
            ):
                with self.subTest(attempt_mutation=name):
                    candidate_rows = json.loads(json.dumps(original_attempt_rows))
                    candidate_rows[index][key] = value
                    write_attempt_rows(candidate_rows)
                    assert_morning_invalid()

            nonderived_id = json.loads(json.dumps(original_attempt_rows))
            for candidate in nonderived_id[:2]:
                candidate["attempt_id"] = "a" * 24
            original_attempt_id = rows[0]["receipt"]["attempt_id"]
            rows[0]["receipt"]["attempt_id"] = "a" * 24
            write_attempt_rows(nonderived_id)
            assert_morning_invalid()
            rows[0]["receipt"]["attempt_id"] = original_attempt_id

            write_attempt_rows(original_attempt_rows)
            original_local_html = rows[0]["receipt"]["local_html"]
            rows[0]["receipt"]["local_html"] = str(evidence / "latest.html")
            assert_morning_invalid()
            rows[0]["receipt"]["local_html"] = original_local_html

            write_attempt_rows(original_attempt_rows)
            _rewrite_m5_html(rows[0], lambda rendered: rendered + "<!-- changed -->\n")
            assert_morning_invalid()

            attempts.write_text("{broken\n", encoding="utf-8")
            attempts.chmod(0o600)
            assert_morning_invalid()

            attempts.unlink()
            assert_morning_invalid()

    def test_authoritative_json_proof_parsers_fail_closed_on_recursion(self):
        for boundary in ("attempt-barrier", "send-attempts", "archive"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rows = _write_m5_pair(root)
                try:
                    if boundary == "attempt-barrier":
                        with mock.patch.object(
                            brief.json,
                            "load",
                            side_effect=RecursionError("attempt barrier too deep"),
                        ):
                            accepted = brief._scheduled_attempt_barrier_is_valid(
                                root / "ledger",
                                rows[0],
                            )
                        self.assertFalse(accepted)
                    elif boundary == "send-attempts":
                        with mock.patch.object(
                            brief.json,
                            "loads",
                            side_effect=RecursionError("send attempts too deep"),
                        ):
                            attempts = brief._read_send_attempt_proof(
                                root / "ledger" / "send-attempts.jsonl"
                            )
                        self.assertIsNone(attempts)
                    else:
                        real_loads = brief.json.loads

                        def recurse_for_archived_packet(value, *args, **kwargs):
                            if (
                                isinstance(value, str)
                                and '"authority"' in value
                                and '"board_snapshot"' in value
                            ):
                                raise RecursionError("archived packet too deep")
                            return real_loads(value, *args, **kwargs)

                        with mock.patch.object(
                            brief.json,
                            "loads",
                            side_effect=recurse_for_archived_packet,
                        ):
                            result = brief.verify_window_receipts(
                                rows,
                                evidence_dir=root,
                            )
                        self.assertIn(
                            "2026-08-12T08:00:00-04:00: archived JSON unreadable",
                            result["problems"],
                        )
                except RecursionError as exc:
                    self.fail(
                        f"{boundary} authoritative JSON recursion escaped: {exc}"
                    )

    def test_authoritative_json_proof_parsers_fail_closed_on_integer_limit(self):
        oversized = "9" * 5_000
        for boundary in ("attempt-barrier", "send-attempts", "archive"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rows = _write_m5_pair(root)
                if boundary == "attempt-barrier":
                    proof_path = Path(str(rows[0]["attempt_barrier"]["path"]))
                    proof_path.chmod(0o600)
                    proof_path.write_text(
                        '{"oversized": ' + oversized + "}\n",
                        encoding="utf-8",
                    )
                    proof_path.chmod(0o400)
                elif boundary == "send-attempts":
                    proof_path = root / "ledger" / "send-attempts.jsonl"
                    proof_path.write_text(
                        '{"oversized": ' + oversized + "}\n",
                        encoding="utf-8",
                    )
                    proof_path.chmod(0o600)
                else:
                    proof_path = Path(str(rows[0]["archive_json"]))
                    proof_path.chmod(0o600)
                    rendered = ('{"oversized": ' + oversized + "}\n").encode()
                    proof_path.write_bytes(rendered)
                    proof_path.chmod(0o400)
                    rows[0]["json_sha256"] = hashlib.sha256(rendered).hexdigest()

                try:
                    if boundary == "attempt-barrier":
                        accepted = brief._scheduled_attempt_barrier_is_valid(
                            root / "ledger",
                            rows[0],
                        )
                        self.assertFalse(accepted)
                    elif boundary == "send-attempts":
                        attempts = brief._read_send_attempt_proof(proof_path)
                        self.assertIsNone(attempts)
                    else:
                        result = brief.verify_window_receipts(
                            rows,
                            evidence_dir=root,
                        )
                        self.assertIn(
                            "2026-08-12T08:00:00-04:00: archived JSON unreadable",
                            result["problems"],
                        )
                except ValueError as exc:
                    self.fail(
                        f"{boundary} integer-limit JSON error escaped: {exc}"
                    )

    def test_send_attempt_log_requires_intent_before_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            attempts = ledger / "send-attempts.jsonl"
            evidence.mkdir()
            rows = _write_m5_pair(evidence, ledger, attempts)
            attempt_rows = [
                json.loads(line)
                for line in attempts.read_text(encoding="utf-8").splitlines()
            ]
            attempt_rows[:2] = reversed(attempt_rows[:2])
            attempts.write_text(
                "\n".join(json.dumps(row) for row in attempt_rows) + "\n",
                encoding="utf-8",
            )
            attempts.chmod(0o600)

            result = brief.verify_window_receipts(
                rows,
                evidence_dir=evidence,
                ledger_dir=ledger,
                send_attempt_log=attempts,
            )

        self.assertIn(
            "2026-08-12T08:00:00-04:00: scheduled send attempt ledger proof is invalid",
            result["problems"],
        )

    def test_send_attempt_intent_must_precede_provider_sent_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            attempts = ledger / "send-attempts.jsonl"
            evidence.mkdir()
            rows = _write_m5_pair(evidence, ledger, attempts)
            attempt_rows = [
                json.loads(line)
                for line in attempts.read_text(encoding="utf-8").splitlines()
            ]
            intent = attempt_rows[0]
            outcome = attempt_rows[1]
            intent["created_at"] = "2026-08-12T08:05:30-04:00"
            identity = dict(intent)
            identity.pop("attempt_id")
            attempt_id = hashlib.sha256(
                json.dumps(identity, sort_keys=True).encode("utf-8")
            ).hexdigest()[:24]
            intent["attempt_id"] = attempt_id
            outcome.update(
                {
                    "attempt_id": attempt_id,
                    "recorded_at": "2026-08-12T08:05:45-04:00",
                    "sent_at": "2026-08-12T08:05:15-04:00",
                }
            )
            rows[0]["receipt"].update(
                {
                    "attempt_id": attempt_id,
                    "sent_at": "2026-08-12T08:05:15-04:00",
                }
            )
            attempts.write_text(
                "\n".join(json.dumps(row) for row in attempt_rows) + "\n",
                encoding="utf-8",
            )
            attempts.chmod(0o600)

            result = brief.verify_window_receipts(
                rows,
                evidence_dir=evidence,
                ledger_dir=ledger,
                send_attempt_log=attempts,
            )

        self.assertIn(
            "2026-08-12T08:00:00-04:00: scheduled send attempt ledger proof is invalid",
            result["problems"],
        )

    def test_send_attempt_stable_identities_require_exact_json_types(self):
        for mutation in ("numeric-message", "intent-thread-list", "outcome-thread-object"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                evidence = root / "evidence"
                ledger = root / "ledger"
                attempts = ledger / "send-attempts.jsonl"
                evidence.mkdir()
                rows = _write_m5_pair(evidence, ledger, attempts)
                attempt_rows = [
                    json.loads(line)
                    for line in attempts.read_text(encoding="utf-8").splitlines()
                ]
                intent = attempt_rows[0]
                outcome = attempt_rows[1]
                if mutation == "numeric-message":
                    outcome["message_id"] = 123
                    rows[0]["receipt"]["message_id"] = 123
                elif mutation == "intent-thread-list":
                    intent["thread_id"] = ["thread-in-a-list"]
                    identity = dict(intent)
                    identity.pop("attempt_id")
                    attempt_id = hashlib.sha256(
                        json.dumps(identity, sort_keys=True).encode("utf-8")
                    ).hexdigest()[:24]
                    intent["attempt_id"] = attempt_id
                    outcome["attempt_id"] = attempt_id
                    rows[0]["receipt"]["attempt_id"] = attempt_id
                else:
                    outcome["thread_id"] = {"id": "thread-in-an-object"}
                    rows[0]["receipt"]["thread_id"] = {
                        "id": "thread-in-an-object"
                    }
                attempts.write_text(
                    "\n".join(json.dumps(row) for row in attempt_rows) + "\n",
                    encoding="utf-8",
                )
                attempts.chmod(0o600)

                result = brief.verify_window_receipts(
                    rows,
                    evidence_dir=evidence,
                    ledger_dir=ledger,
                    send_attempt_log=attempts,
                )

                self.assertIn(
                    "2026-08-12T08:00:00-04:00: scheduled send attempt ledger proof is invalid",
                    result["problems"],
                )

    def test_schedule_status_binds_loaded_job_path_and_exact_arguments(self):
        def launchctl_output(arguments, path):
            return (
                f"gui/{os.getuid()}/{brief.LABEL} = {{\n"
                f"\tprogram = {arguments[0]}\n"
                "\targuments = {\n"
                + "".join(f"\t\t{argument}\n" for argument in arguments)
                + "\t}\n"
                f"\tpath = {path}\n"
                "}\n"
            )

        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            agents = home / "Library" / "LaunchAgents"
            agents.mkdir(parents=True)
            canonical = agents / f"{brief.LABEL}.plist"
            with mock.patch.object(brief.Path, "home", return_value=home):
                expected = brief.launch_agent_plist(Path(brief.__file__).resolve())
                canonical.write_bytes(plistlib.dumps(expected, fmt=plistlib.FMT_XML))
                exact_output = launchctl_output(expected["ProgramArguments"], canonical)
                stale_arguments = [
                    expected["ProgramArguments"][0],
                    "/old/replacement/shadow-brief.py",
                    *expected["ProgramArguments"][2:],
                ]
                reordered_arguments = list(expected["ProgramArguments"])
                reordered_arguments[-2:] = reversed(reordered_arguments[-2:])
                cases = (
                    ("exact", exact_output, True),
                    ("stale", launchctl_output(stale_arguments, canonical), False),
                    (
                        "reordered",
                        launchctl_output(reordered_arguments, canonical),
                        False,
                    ),
                    (
                        "wrong-loaded-path",
                        launchctl_output(
                            expected["ProgramArguments"],
                            agents / "com.example.replacement.plist",
                        ),
                        False,
                    ),
                    (
                        "duplicate-program",
                        exact_output.replace(
                            "\tprogram = ",
                            "\tprogram = /old/python\n\tprogram = ",
                            1,
                        ),
                        False,
                    ),
                    ("missing-arguments", "program = /usr/bin/python3\n", False),
                )
                for name, output, expected_ok in cases:
                    with self.subTest(name=name), mock.patch.object(
                        brief.Path, "home", return_value=home
                    ), mock.patch.object(
                    brief, "_host_timezone_name", return_value="America/New_York"
                    ), mock.patch.object(
                        brief,
                        "_run",
                        return_value=subprocess.CompletedProcess([], 0, output, ""),
                    ):
                        status = brief.schedule_status()
                    self.assertEqual(status["launchctl_ok"], expected_ok)
                    self.assertEqual(status["configuration_ok"], expected_ok)
                    if not expected_ok:
                        self.assertIn("LoadedJob", status["configuration_problems"])

    def test_env_split_string_wrappers_detect_only_executed_brief_commands(self):
        positives = (
            ["/usr/bin/env", "-S", "/usr/local/bin/shadow brief run --scheduled-trigger"],
            [
                "/usr/bin/env",
                "--split-string",
                "/usr/local/bin/shadow brief run --scheduled-trigger",
            ],
            [
                "/usr/bin/env",
                "--split-string=/usr/bin/python3 -I /opt/shadow-brief.py run --scheduled-trigger",
            ],
            ["/usr/bin/env", "-S/usr/local/bin/shadow brief run --scheduled-trigger"],
        )
        negatives = (
            ["/usr/bin/env", "-S", "printf '%s' 'shadow brief run --scheduled-trigger'"],
            ["/usr/bin/env", "--split-string=echo shadow brief run --scheduled-trigger"],
        )
        for values in positives:
            with self.subTest(values=values):
                self.assertTrue(brief._command_targets_scheduled_brief(values))
        for values in negatives:
            with self.subTest(values=values):
                self.assertFalse(brief._command_targets_scheduled_brief(values))

    def test_optional_host_commands_turn_process_failures_into_structured_results(self):
        for exception in (
            OSError("host command unavailable"),
            subprocess.TimeoutExpired(["osascript"], 10),
        ):
            with self.subTest(exception=type(exception).__name__):
                with mock.patch.object(brief, "_run", side_effect=exception):
                    try:
                        notification = brief.macos_notify("title", "body")
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        self.fail(f"notification process failure escaped: {exc}")
                self.assertEqual(notification["status"], "blocked")
                self.assertEqual(notification["title"], "title")
                self.assertEqual(notification["body"], "body")
                self.assertTrue(notification.get("error"))

        with mock.patch.object(
            brief, "_run", side_effect=OSError("shadow executable unavailable")
        ):
            try:
                excerpt = brief.collect_shadow_status_excerpt()
            except OSError as exc:
                self.fail(f"optional seat-status OSError escaped: {exc}")
        self.assertIn("unavailable", excerpt)
        self.assertIn("revision-checked Shadow board", excerpt)

    def test_blocked_notification_persists_wake_without_sending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            ledger = root / "ledger"
            deliver = mock.Mock(
                return_value={
                    "status": "ok",
                    "delivery_status": "sent",
                    "message_id": "must-not-send",
                }
            )
            append = mock.Mock()
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", evidence), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", return_value=_scheduled_packet_fixture()
            ), mock.patch.object(
                brief,
                "macos_notify",
                return_value={
                    "status": "blocked",
                    "title": "Shadow brief ready",
                    "body": "morning · board rev 41",
                    "error": "osascript unavailable",
                },
            ), mock.patch.object(
                brief, "deliver_superhuman", deliver
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = brief._cmd_run_locked(args, _scheduled_proof_fixture())

            last_run = json.loads((ledger / "last-run.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 3)
        deliver.assert_not_called()
        append.assert_called_once()
        self.assertEqual(last_run["notification"]["status"], "blocked")
        self.assertIn("notification", last_run["wake"])
        self.assertIn("do not send", last_run["wake"])

    def test_success_stdout_failure_cannot_prevent_exactly_one_window_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger"
            append = mock.Mock()
            args = mock.Mock(
                scheduled_trigger=True,
                slot="morning",
                deliver=True,
                dry_run=False,
                send_authorized_self=True,
            )
            with mock.patch.object(brief, "EVIDENCE_DIR", root / "evidence"), mock.patch.object(
                brief, "LOG_DIR", ledger
            ), mock.patch.object(
                brief, "WINDOW_LOG", ledger / "windows.jsonl"
            ), mock.patch.object(
                brief, "scheduled_window", return_value=_scheduled_window_fixture()
            ), mock.patch.object(
                brief, "collect_packet", return_value=_scheduled_packet_fixture()
            ), mock.patch.object(
                brief,
                "macos_notify",
                return_value={
                    "status": "ok",
                    "title": "Shadow brief ready",
                    "body": "morning · board rev 41",
                },
            ), mock.patch.object(
                brief,
                "deliver_superhuman",
                return_value={
                    "status": "ok",
                    "delivery_status": "sent",
                    "message_id": "sent-before-broken-pipe",
                },
            ), mock.patch.object(
                brief, "append_scheduled_window", append
            ), mock.patch("builtins.print", side_effect=BrokenPipeError("stdout closed")):
                try:
                    exit_code = brief._cmd_run_locked(args, _scheduled_proof_fixture())
                except BrokenPipeError as exc:
                    self.fail(f"success summary stdout failure escaped before append: {exc}")

        self.assertEqual(exit_code, 0)
        append.assert_called_once()

    def test_selected_windows_group_equivalent_timestamp_spellings(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = _write_m5_pair(Path(tmp))
            equivalent = dict(rows[0])
            equivalent["scheduled_for"] = "2026-08-12 08:00:00-04:00"
            result = brief.verify_window_receipts([rows[0], equivalent, rows[1]])

        self.assertFalse(result["ok"])
        self.assertIn(
            "2026-08-12T08:00:00-04:00: duplicate natural-window receipts found",
            result["problems"],
        )

    def test_selected_windows_require_exact_second_precision_timestamp_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            ledger = evidence / "ledger"
            rows = _write_m5_pair(evidence, ledger)
            fractional_values = (
                "2026-08-12T08:00:00.123456-04:00",
                "2026-08-12T20:00:00.654321-04:00",
            )
            for row, fractional in zip(rows, fractional_values):
                row["scheduled_for"] = fractional
                barrier = Path(row["attempt_barrier"]["path"])
                payload = json.loads(barrier.read_text(encoding="utf-8"))
                payload["scheduled_for"] = fractional
                barrier.chmod(0o600)
                barrier.write_text(
                    json.dumps(payload, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                barrier.chmod(0o400)

            result = brief.verify_window_receipts(
                rows,
                evidence_dir=evidence,
                ledger_dir=ledger,
            )

        for fractional in fractional_values:
            self.assertIn(
                f"{fractional}: scheduled_for is not a canonical report-window timestamp",
                result["problems"],
            )


if __name__ == "__main__":
    unittest.main()
