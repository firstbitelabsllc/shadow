"""Tests for scripts/vidux-public-ready-grep-gate.py.

All fixtures are synthetic. No real operator, family, employer, account,
machine-local, finance, or private-repository content is copied here.
"""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-public-ready-grep-gate.py"
SPEC = importlib.util.spec_from_file_location("vidux_public_ready_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)

# Synthetic identity tokens are assembled so this test source is itself
# scannable; only the temporary fixture files contain complete forbidden text.
SYN_USER = "ops-user"
SYN_HOME_MAC = f"/Use{'rs'}/{SYN_USER}/Projects/demo/"
SYN_HOME_LINUX = f"/ho{'me'}/{SYN_USER}/work/demo/"
SYN_EMAIL = "ops.user@" + "private-corp.dev"
SYN_PUBLIC_EMAIL = "leojkwan@" + "gmail.com"
RETIRED_BOARD = "Lin" + "ear"
PRIVATE_FLOW = "/leo" + "-flow"
PRIVATE_OVERLAY = "/vidux" + "-leo"
MACHINE_NAME = "M4" + " Pro"
STUDIO_NAME = "Mac" + " Studio"
PRIVATE_TEST_EMAIL = "test@" + "test.com"
LOCAL_TEST_EMAIL = "operator@" + "workstation.local"
FOREIGN_BOT_EMAIL = "stranger-bot@" + "users.noreply.github.com"
PRIVATE_HOST = "handoff." + "corp.internal"


class PublicReadyGrepGateTests(unittest.TestCase):
    def test_tracked_only_scans_the_shipping_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            leak = root / "LOCAL-NOTES.md"
            leak.write_text(f"Use `{PRIVATE_FLOW}` locally.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)

            clean = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(root),
                    "--tracked-only",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            subprocess.run(["git", "-C", str(root), "add", "LOCAL-NOTES.md"], check=True)
            leak.write_text("Clean worktree copy.\n", encoding="utf-8")
            leaking = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(root),
                    "--tracked-only",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        clean_payload = json.loads(clean.stdout)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertEqual(clean_payload["scope"], "tracked")
        self.assertEqual(clean_payload["scanned_files"], 1)
        self.assertEqual(leaking.returncode, 1)
        leaking_payload = json.loads(leaking.stdout)
        self.assertEqual(leaking_payload["matches"][0]["file"], "LOCAL-NOTES.md")

    def test_clean_current_surface_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "config.md").write_text("Plans are files.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["matches"], [])

    def test_privacy_leak_in_filename_is_caught_even_in_historical_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            # A leak-class string in the FILENAME, with clean redacted body
            # content -- content-only scanning once missed a real leak
            # sitting in a tracked filename.
            (evidence / f"2026-06-08-{PRIVATE_FLOW[1:]}-anti-slop.md").write_text(
                "Redacted body, no leak here.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        match = payload["matches"][0]
        self.assertEqual(match["line"], 0)
        self.assertIn("in filename", match["pattern"])

    def test_forbidden_term_in_current_surface_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"Add {RETIRED_BOARD} sync back here.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["file"], "README.md")

    def test_plan_live_sections_are_scanned_but_append_only_history_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PLAN.md").write_text(
                "# Plan\n"
                "## Current State\n"
                f"Restore {RETIRED_BOARD} sync now.\n"
                "## Decision Log\n"
                "### 2026-04-01\n"
                f"Retired {RETIRED_BOARD} sync.\n"
                "## Open work\n"
                "Keep plans in markdown.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["matches"]), 1, payload["matches"])
        self.assertEqual(payload["matches"][0]["line"], 3)
        self.assertEqual(payload["matches"][0]["pattern"], "retired board brand")

    def test_private_machine_ownership_assignment_variants_fail(self):
        phrases = [
            f"The {MACHINE_NAME} owns Project Atlas automation.\n",
            f"Project Atlas is owned by the {STUDIO_NAME}.\n",
            "Project Atlas is Studio-owned, not blocked waiting for this "
            + "Mac.\n",
            f"The {MACHINE_NAME} does not probe or edit Project Atlas.\n",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "README.md").write_text(phrase, encoding="utf-8")

                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 1)
                payload = json.loads(result.stdout)
                self.assertEqual(
                    payload["matches"][0]["pattern"],
                    "private machine-ownership assignment",
                )

    def test_private_machine_ownership_ignores_benign_own_phrases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "The M1 Max has its own binary cache.\n"
                "Matrix M3 chassis with its own housing.\n"
                "M5 own goal in the 90th minute.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_plan_fenced_heading_does_not_change_history_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PLAN.md").write_text(
                "# Plan\n"
                "## Current State\n"
                "```bash\n"
                "# progress\n"
                "```\n"
                f"Restore {RETIRED_BOARD} sync now.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual([match["line"] for match in payload["matches"]], [6])

    def test_plan_setext_heading_exits_append_only_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PLAN.md").write_text(
                "# Plan\n"
                "## Decision Log\n"
                f"Retired {RETIRED_BOARD} sync.\n"
                "Open work\n"
                "---------\n"
                f"Restore {RETIRED_BOARD} sync now.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual([match["line"] for match in payload["matches"]], [6])

    def test_plan_append_only_history_still_scans_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PLAN.md").write_text(
                "# Plan\n"
                "## Decision Log\n"
                f"The {MACHINE_NAME} owns Project Atlas automation.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["matches"][0]["pattern"],
            "private machine-ownership assignment",
        )

    def test_unreadable_file_does_not_crash_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            unreadable = root / "docs"
            unreadable.mkdir()
            blocked = unreadable / "blocked.md"
            blocked.write_text(
                f"Add {RETIRED_BOARD} sync back here.\n", encoding="utf-8",
            )
            blocked.chmod(0o000)

            try:
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                blocked.chmod(0o644)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"], [])
        self.assertEqual(len(payload["errors"]), 1)
        self.assertIn("docs/blocked.md: cannot scan content", payload["errors"][0])

    def test_tracked_binary_private_path_is_scanned_without_utf8_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            binary = root / "payload.bin"
            binary.write_bytes(
                b"\x89BIN\xff\x00private path: "
                + SYN_HOME_MAC.encode("ascii")
                + b"secret.txt\x00"
            )
            subprocess.run(["git", "-C", str(root), "add", "payload.bin"], check=True)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(root),
                    "--tracked-only",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["errors"], [])
        self.assertTrue(
            any(
                match["file"] == "payload.bin"
                and match["pattern"] == "absolute home path"
                for match in payload["matches"]
            ),
            payload["matches"],
        )

    def test_unapproved_absolute_url_and_host_field_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"Dashboard: https://{PRIVATE_HOST}/status\n"
                f'{{"host": "{PRIVATE_HOST}"}}\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(
            {match["pattern"] for match in payload["matches"]},
            {"unapproved absolute URL host", "unapproved host-valued field"},
        )

    def test_allowlisted_and_reserved_documentation_hosts_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Source: https://github.com/firstbitelabsllc/vidux\n"
                "Fixture: https://example.com/proof\n"
                '{"host": "localhost:7191"}\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_generic_private_context_markers_fail_without_named_allowlist(self):
        fixtures = [
            (
                "projects/demo-" + "family/PLAN.md\n",
                "private project category path",
            ),
            (
                "per" + "sona: Avery\n",
                "named-person private context",
            ),
            (
                '{"company' + '_name": "Synthetic Holdings"}\n',
                "private organization marker",
            ),
            (
                "Launch" + "Agent label com.synthetic.private-worker\n",
                "private launch service label",
            ),
        ]
        for body, expected in fixtures:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "NOTES.md").write_text(body, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["matches"][0]["pattern"], expected)

    def test_arbitrary_bare_name_is_outside_structural_gate_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Thanks to Avery for reviewing this public release.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_ask_leo_is_in_scope_but_hygiene_exempt(self):
        # ASK-LEO.md is live and must be privacy-scanned, while historical
        # hygiene terms in resolved Q&A remain exempt.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Vidux is markdown-plan-first.\n", encoding="utf-8")
            (root / "ASK-LEO.md").write_text(
                f"## Q1\nAnswer: migrated off {RETIRED_BOARD} sync in 2026-04.\n"
                f"Private path leak: {SYN_HOME_MAC}secret.md\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        files_matched = {m["file"] for m in payload["matches"]}
        self.assertEqual(files_matched, {"ASK-LEO.md"})
        patterns_matched = {m["pattern"] for m in payload["matches"]}
        self.assertEqual(patterns_matched, {"absolute home path"})

    def test_leo_flow_pattern_catches_hyphenated_slash_command_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"Use `{PRIVATE_FLOW}` for lane routing.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "private flow-lane marker")

    def test_generic_macos_and_linux_home_paths_are_caught(self):
        fixtures = [
            (f"Path: {SYN_HOME_MAC}\n", "absolute home path"),
            (f"Path: {SYN_HOME_LINUX}\n", "absolute home path"),
            ("Notes under ~/" + "Documents/local-tools/README.md\n", "home-relative private path"),
            ("Key material under ~/." + "ssh/id_ed25519\n", "home-relative private path"),
        ]
        for body, expected in fixtures:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "README.md").write_text(body, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["matches"][0]["pattern"], expected)

    def test_non_public_email_is_caught_public_identity_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"Contact: {SYN_EMAIL}\nPublic: {SYN_PUBLIC_EMAIL}\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        patterns = {m["pattern"] for m in payload["matches"]}
        self.assertEqual(patterns, {"non-public email address"})
        self.assertTrue(any(SYN_EMAIL in m["text"] for m in payload["matches"]))
        self.assertFalse(any(SYN_PUBLIC_EMAIL == m["text"] for m in payload["matches"]))

    def test_test_com_is_not_a_documentation_allowance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"Foreign fixture: {PRIVATE_TEST_EMAIL}\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(
            {match["pattern"] for match in payload["matches"]},
            {"non-public email address"},
        )

    def test_example_doc_email_is_not_a_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Docs may show user@example.com as a placeholder.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_quota_roster_and_auth_snapshots_are_caught(self):
        fixtures = [
            ('{"remaining_' + 'percent": 12, "ros' + 'ter": []}\n', "category_quota_payload"),
            ("Captured quota " + "snapshot before rotation.\n", "category_quota_payload"),
            (
                '{"access_'
                + 'token": "tok_'
                + "synthetic_"
                + '0001", "api_'
                + 'key": "key_'
                + 'synthetic"}\n',
                "credential-field payload",
            ),
        ]
        for body, expected in fixtures:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "NOTES.md").write_text(body, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["matches"][0]["pattern"], expected)

    def test_raw_transcript_and_session_dumps_are_caught(self):
        fixtures = [
            "Attached raw chat " + "transcript from the debug session.\n",
            "Do not publish the session " + "dump.\n",
            "Keep the conversation " + "export offline.\n",
        ]
        for body in fixtures:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "NOTES.md").write_text(body, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["matches"][0]["pattern"], "category_transcript_payload")

    def test_chat_role_content_json_is_not_a_false_positive(self):
        # Product tests and browser fixtures legitimately use role/content JSON.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "NOTES.md").write_text(
                '{"role": "user", "content": "synthetic prompt text"}\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_private_finance_and_account_material_is_caught(self):
        fixtures = [
            "routing " + "number 021000021 appears in the receipt.\n",
            '{"account_' + 'number": "000111222", "balance_' + 'cents": 1200}\n',
            "Export includes bank account " + "number and tax " + "id.\n",
        ]
        for body in fixtures:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "NOTES.md").write_text(body, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                payload = json.loads(result.stdout)
                self.assertEqual(
                    payload["matches"][0]["pattern"],
                    "finance-account payload",
                )

    def test_public_docs_and_synthetic_examples_do_not_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Vidux is markdown-plan-first.\n"
                "Email support at help@example.com.\n"
                "Tokens are configured via environment variables.\n"
                "The Mac Studio has its own SSD.\n"
                "Discuss account recovery without exporting balances.\n",
                encoding="utf-8",
            )
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text(
                "Use plans as files. No home paths. No dumps.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_maintainers_own_public_commit_identity_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"Every commit on origin/main is authored as {SYN_PUBLIC_EMAIL}.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_project_plan_append_only_history_is_hygiene_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "projects" / "old-cleanup" / "PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                "# Cleanup plan\n"
                "## Decisions\n"
                "Historical Linear removal notes stay here.\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text("Current docs stay clean.\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_new_top_level_file_not_named_in_any_allowlist_is_still_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            (root / "NOTES-NOBODY-NAMED-YET.md").write_text(
                f"Use `{PRIVATE_FLOW}` for lane routing.\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["file"], "NOTES-NOBODY-NAMED-YET.md")

    def test_css_and_svg_linear_keyword_is_not_a_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "style.css").write_text(
                "a { background: linear-gradient(180deg, #fff, #000); "
                "transition: all 1.5s linear infinite; }\n",
                encoding="utf-8",
            )
            (root / "banner.svg").write_text(
                "<style>.x { animation: flow 1.5s linear infinite; }</style>\n",
                encoding="utf-8",
            )
            (root / ".gitignore").write_text(".linear-state.json\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_css_file_still_catches_a_real_privacy_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "style.css").write_text(
                f"/* generated from {PRIVATE_OVERLAY}/tokens.json */\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["matches"][0]["pattern"], "private overlay marker")

    def test_changelog_is_privacy_scanned_but_hygiene_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text(
                f"## [1.0.0]\n- Migrated off {RETIRED_BOARD}.\n"
                f"- Kept locally under {PRIVATE_OVERLAY}.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        matches = payload["matches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["file"], "CHANGELOG.md")
        self.assertEqual(matches[0]["pattern"], "private overlay marker")

    def test_formerly_excluded_test_paths_are_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            tests_dir.joinpath("test_vidux_contracts.py").write_text(
                f"LEAK = '{SYN_HOME_MAC}contracts.txt'\n", encoding="utf-8",
            )
            tests_dir.joinpath("test_public_ready_grep_gate.py").write_text(
                f"LEAK = '{SYN_HOME_LINUX}gate.txt'\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        files_matched = {m["file"] for m in payload["matches"]}
        self.assertEqual(
            files_matched,
            {
                "tests/test_public_ready_grep_gate.py",
                "tests/test_vidux_contracts.py",
            },
        )
        self.assertEqual(
            {m["pattern"] for m in payload["matches"]},
            {"absolute home path"},
        )

    def test_docs_vitepress_dir_is_no_longer_bare_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            vitepress_dir = root / "docs" / ".vitepress"
            vitepress_dir.mkdir(parents=True)
            vitepress_dir.joinpath("config.ts").write_text(
                "export default { title: 'Vidux' }\n", encoding="utf-8",
            )
            vitepress_dir.joinpath("theme.ts").write_text(
                f"// LEAK = '{PRIVATE_FLOW}'\n", encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        files_matched = {m["file"] for m in payload["matches"]}
        self.assertEqual(files_matched, {"docs/.vitepress/theme.ts"})

    def test_gate_source_is_privacy_scanned_and_cannot_hide_unrelated_categories(self):
        # The gate script is hygiene-exempt (it must document retired terms)
        # but remains privacy-scanned. Prove an injected synthetic home path
        # in a sibling non-exempt file is still caught, and that the script
        # path itself is not on the full-path denylist.
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("scripts/vidux-public-ready-grep-gate.py", source.split("EXCLUDED_RELATIVE_PATHS")[1].split("}")[0])
        self.assertIn("vidux-public-ready-grep-gate.py", source)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            scripts.joinpath("vidux-public-ready-grep-gate.py").write_text(
                "print('clean gate body')\n", encoding="utf-8",
            )
            (root / "README.md").write_text(
                f"Leaked path: {SYN_HOME_LINUX}private.txt\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["matches"][0]["file"], "README.md")
        self.assertEqual(payload["matches"][0]["pattern"], "absolute home path")

    def test_gate_source_with_hidden_home_path_is_caught(self):
        # Regression: full path exemption must not hide an unrelated privacy
        # category inside the gate script itself.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            scripts.joinpath("vidux-public-ready-grep-gate.py").write_text(
                f"# accidental note: {SYN_HOME_MAC}notes.md\nprint('x')\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text("Clean.\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        files = {m["file"] for m in payload["matches"]}
        self.assertIn("scripts/vidux-public-ready-grep-gate.py", files)
        self.assertTrue(
            any(m["pattern"] == "absolute home path" for m in payload["matches"]),
            payload["matches"],
        )


class PublicReadyMetadataGateTests(unittest.TestCase):
    """--metadata scans commit identity + message trailers, which file-content
    scanning is structurally blind to (the exposures that survive a clean tree)."""

    @staticmethod
    def _commit(root, message, *, name, email):
        env = {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
        }
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "--allow-empty", "-m", message],
            check=True,
            env={**os.environ, **env},
        )

    def _run_metadata(self, root):
        return subprocess.run(
            [
                sys.executable, str(SCRIPT), "--repo-root", str(root),
                "--tracked-only", "--metadata", "--json",
            ],
            capture_output=True, text=True, check=False,
        )

    def test_clean_identity_and_message_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            self._commit(
                root, "docs: initial", name="Public Maintainer", email=SYN_PUBLIC_EMAIL
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["scanned_commits"], 1)

    def test_legacy_identity_waiver_is_exact_commit_role_and_digest(self):
        commit_sha = "d79cfb869cc6f9d5c886f85e82df8553cd41bc49"
        digest = "c535b8d5ff96384e34e93c92085ea40bad15b20f97b9733aa719c1043f1ff9b8"
        self.assertTrue(
            GATE._legacy_identity_digest_allowed(commit_sha, "author", digest)
        )
        self.assertTrue(
            GATE._legacy_identity_digest_allowed(commit_sha, "committer", digest)
        )
        self.assertFalse(
            GATE._legacy_identity_digest_allowed("0" * 40, "author", digest)
        )
        self.assertFalse(
            GATE._legacy_identity_digest_allowed(
                commit_sha, "co-author trailer", digest
            )
        )
        self.assertFalse(
            GATE._legacy_identity_digest_allowed(commit_sha, "author", "0" * 64)
        )

    def test_codesmith_automation_identity_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            env = {
                "GIT_AUTHOR_NAME": "public-maintainer",
                "GIT_AUTHOR_EMAIL": SYN_PUBLIC_EMAIL,
                "GIT_COMMITTER_NAME": "Codesmith",
                "GIT_COMMITTER_EMAIL": "codesmith-bot@users.noreply.github.com",
            }
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-q", "-m", "fix: automated"],
                check=True,
                env={**os.environ, **env},
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed", payload)

    def test_foreign_author_identity_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            self._commit(
                root, "chore: seed", name="Public Maintainer", email=PRIVATE_TEST_EMAIL
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        patterns = {m["pattern"] for m in payload["matches"]}
        self.assertIn("disallowed author identity", patterns)
        self.assertTrue(
            any(PRIVATE_TEST_EMAIL in m["text"] for m in payload["matches"]),
            payload["matches"],
        )

    def test_machine_local_author_identity_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            self._commit(
                root,
                "chore: seed",
                name="Local Operator",
                email=LOCAL_TEST_EMAIL,
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertTrue(
            any(
                match["pattern"] == "disallowed author identity"
                and LOCAL_TEST_EMAIL in match["text"]
                for match in payload["matches"]
            ),
            payload["matches"],
        )

    def test_non_public_coauthor_trailer_email_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            self._commit(
                root,
                f"feat: thing\n\nCo-authored-by: Synth Reviewer <{SYN_EMAIL}>",
                name="Public Maintainer",
                email=SYN_PUBLIC_EMAIL,
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        patterns = {m["pattern"] for m in payload["matches"]}
        self.assertTrue(
            "disallowed co-author trailer identity" in patterns
            or "non-public email address" in patterns,
            payload["matches"],
        )

    def test_foreign_coauthor_trailer_identity_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            self._commit(
                root,
                "feat: thing\n\n"
                f"Co-authored-by: Stranger <{FOREIGN_BOT_EMAIL}>",
                name="Public Maintainer",
                email=SYN_PUBLIC_EMAIL,
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        patterns = {m["pattern"] for m in payload["matches"]}
        self.assertIn("disallowed co-author trailer identity", patterns)
        self.assertTrue(
            any(
                FOREIGN_BOT_EMAIL in m["text"]
                for m in payload["matches"]
            ),
            payload["matches"],
        )

    def test_codesmith_trailer_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("Vidux.\n", encoding="utf-8")
            self._commit(
                root,
                "docs: fix onboarding\n\n"
                "Co-authored-by: codesmith-bot "
                "<codesmith-bot@users.noreply.github.com>",
                name="Public Maintainer",
                email=SYN_PUBLIC_EMAIL,
            )
            result = self._run_metadata(root)
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")


if __name__ == "__main__":
    unittest.main()
