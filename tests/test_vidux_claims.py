"""Tests for scripts/vidux-claims.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-claims.py"

spec = importlib.util.spec_from_file_location("vidux_claims", SCRIPT)
assert spec is not None
claims = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = claims
spec.loader.exec_module(claims)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def _claim_args(claims_file: str, *, owner: str = "codex-a") -> list[str]:
    return [
        "--claims-file",
        claims_file,
        "claim",
        "--repo",
        "vidux",
        "--claim",
        "PLAN.md",
        "--owner",
        owner,
        "--lane",
        f"lane-{owner}",
        "--plan-path",
        "PLAN.md",
        "--task-id",
        "T4",
    ]


def _assert_private_process_fields_absent(test: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        test.assertNotIn("host", value)
        test.assertNotIn("pid", value)
        for child in value.values():
            _assert_private_process_fields_absent(test, child)
    elif isinstance(value, list):
        for child in value:
            _assert_private_process_fields_absent(test, child)


class ViduxClaimsTests(unittest.TestCase):
    def test_claims_file_override_is_accepted_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = str(Path(tmp) / "claims.jsonl")
            claimed = _run(_claim_args(claims_file))
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            snapshot = _run(["snapshot", "--claims-file", claims_file])

            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            self.assertEqual(len(_json(snapshot)["claims"]), 1)

    def test_claim_release_round_trip_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = str(Path(tmp) / "claims.jsonl")

            claim = _run(
                [
                    "--claims-file",
                    claims_file,
                    "claim",
                    "--repo",
                    "vidux",
                    "--claim",
                    "scripts/vidux-pr-body.py",
                    "--owner",
                    "codex-a",
                    "--lane",
                    "vidux-self-improvement",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    "5.3.0c",
                ]
            )
            self.assertEqual(claim.returncode, 0, claim.stderr)
            claim_body = _json(claim)
            self.assertEqual(claim_body["status"], "claimed")
            claim_id = claim_body["claim"]["claim_id"]

            active = _run(["--claims-file", claims_file, "active", "--repo", "vidux"])
            self.assertEqual(active.returncode, 0, active.stderr)
            self.assertEqual(len(_json(active)["claims"]), 1)

            release = _run(
                [
                    "--claims-file",
                    claims_file,
                    "release",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                ]
            )
            self.assertEqual(release.returncode, 0, release.stderr)
            self.assertEqual(_json(release)["status"], "released")

            active_after = _run(["--claims-file", claims_file, "active", "--repo", "vidux"])
            self.assertEqual(active_after.returncode, 0, active_after.stderr)
            self.assertEqual(_json(active_after)["claims"], [])

            rows = [
                json.loads(line)
                for line in Path(claims_file).read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([row["event"] for row in rows], ["claim", "release"])

    def test_release_can_record_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = str(Path(tmp) / "claims.jsonl")
            claim = _run(
                [
                    "--claims-file",
                    claims_file,
                    "claim",
                    "--repo",
                    "vidux",
                    "--claim",
                    "PLAN.md",
                    "--owner",
                    "codex-a",
                    "--lane",
                    "lane-a",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    "T4",
                ]
            )
            self.assertEqual(claim.returncode, 0, claim.stderr)

            release = _run(
                [
                    "--claims-file",
                    claims_file,
                    "release",
                    "--repo",
                    "vidux",
                    "--claim",
                    "PLAN.md",
                    "--owner",
                    "codex-a",
                    "--status",
                    "blocked",
                ]
            )

            self.assertEqual(release.returncode, 0, release.stderr)
            self.assertEqual(_json(release)["release"]["status"], "blocked")

    def test_conflicting_active_claim_fails_without_appending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = str(Path(tmp) / "claims.jsonl")
            first = _run(
                [
                    "--claims-file",
                    claims_file,
                    "claim",
                    "--repo",
                    "vidux",
                    "--claim",
                    "PLAN.md",
                    "--owner",
                    "codex-a",
                    "--lane",
                    "lane-a",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    "T4",
                ]
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = _run(
                [
                    "--claims-file",
                    claims_file,
                    "claim",
                    "--repo",
                    "vidux",
                    "--claim",
                    "PLAN.md",
                    "--owner",
                    "codex-b",
                    "--lane",
                    "lane-b",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    "T4",
                ]
            )

            self.assertEqual(second.returncode, 3)
            self.assertEqual(_json(second)["status"], "conflict")
            self.assertEqual(len(Path(claims_file).read_text(encoding="utf-8").splitlines()), 1)

    def test_same_owner_claim_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = str(Path(tmp) / "claims.jsonl")
            args = [
                "--claims-file",
                claims_file,
                "claim",
                "--repo",
                "vidux",
                "--claim",
                "PLAN.md",
                "--owner",
                "codex-a",
                "--lane",
                "lane-a",
                "--plan-path",
                "PLAN.md",
                "--task-id",
                "T4",
            ]
            self.assertEqual(_run(args).returncode, 0)
            second = _run(args)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(_json(second)["status"], "already_claimed")
            self.assertEqual(len(Path(claims_file).read_text(encoding="utf-8").splitlines()), 1)

    def test_heartbeat_and_checkpoint_renew_owned_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = str(Path(tmp) / "claims.jsonl")
            claimed = _run(_claim_args(claims_file))
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            claim_id = _json(claimed)["claim"]["claim_id"]

            checkpoint = _run(
                [
                    "--claims-file",
                    claims_file,
                    "checkpoint",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                    "--summary",
                    "Tests are green",
                    "--resume",
                    "Continue at PLAN row T4",
                    "--proof",
                    "python3 -m unittest tests.test_vidux_claims",
                    "--ttl-hours",
                    "3",
                ]
            )
            self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)
            checkpoint_body = _json(checkpoint)
            self.assertEqual(checkpoint_body["status"], "checkpointed")
            self.assertEqual(
                checkpoint_body["claim"]["checkpoint"]["resume"],
                "Continue at PLAN row T4",
            )

            heartbeat = _run(
                [
                    "--claims-file",
                    claims_file,
                    "heartbeat",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                    "--ttl-hours",
                    "4",
                ]
            )
            self.assertEqual(heartbeat.returncode, 0, heartbeat.stderr)
            self.assertEqual(_json(heartbeat)["status"], "renewed")

            snapshot = _run(["--claims-file", claims_file, "snapshot"])
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            snapshot_body = _json(snapshot)
            self.assertEqual(len(snapshot_body["claims"]), 1)
            _assert_private_process_fields_absent(self, snapshot_body)

    def test_usage_exhausted_handoff_is_resumable_and_takeover_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            first = _run(_claim_args(str(path), owner="codex-a"))
            claim_id = _json(first)["claim"]["claim_id"]
            checkpoint = _run(
                [
                    "--claims-file",
                    str(path),
                    "checkpoint",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                    "--summary",
                    "Core written",
                    "--resume",
                    "Run the focused tests",
                ]
            )
            self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)

            released = _run(
                [
                    "--claims-file",
                    str(path),
                    "release",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                    "--status",
                    "usage_exhausted",
                ]
            )
            self.assertEqual(released.returncode, 0, released.stderr)
            self.assertEqual(
                _json(released)["release"]["checkpoint"]["resume"],
                "Run the focused tests",
            )

            second = _run(_claim_args(str(path), owner="codex-b"))
            self.assertEqual(second.returncode, 0, second.stderr)
            second_body = _json(second)
            self.assertEqual(second_body["claim"]["takeover_of"], claim_id)
            self.assertEqual(
                second_body["takeover"]["checkpoint"]["resume"],
                "Run the focused tests",
            )

    def test_usage_exhausted_requires_resume_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            first = _run(_claim_args(str(path)))
            claim_id = _json(first)["claim"]["claim_id"]
            released = _run(
                [
                    "--claims-file",
                    str(path),
                    "release",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                    "--status",
                    "usage_exhausted",
                ]
            )
            self.assertEqual(released.returncode, 2)
            self.assertIn("requires a checkpoint resume pointer", released.stderr)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_invalid_release_status_is_rejected_by_core_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            first = _run(_claim_args(str(path)))
            self.assertEqual(first.returncode, 0, first.stderr)
            claim_id = _json(first)["claim"]["claim_id"]
            original = path.read_text(encoding="utf-8")

            store = claims.CoordinationClaims(path)
            with self.assertRaisesRegex(
                claims.ClaimsError,
                "release status must be one of",
            ):
                store.release(
                    claim_id=claim_id,
                    owner="codex-a",
                    status="typo_complete",
                )
            self.assertEqual(path.read_text(encoding="utf-8"), original)

            cli = _run(
                [
                    "--claims-file",
                    str(path),
                    "release",
                    "--claim-id",
                    claim_id,
                    "--owner",
                    "codex-a",
                    "--status",
                    "typo_complete",
                ]
            )
            self.assertEqual(cli.returncode, 2)
            self.assertIn("invalid choice", cli.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_wrong_owner_cannot_renew_or_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            first = _run(_claim_args(str(path)))
            claim_id = _json(first)["claim"]["claim_id"]
            for command in ("heartbeat", "release"):
                result = _run(
                    [
                        "--claims-file",
                        str(path),
                        command,
                        "--claim-id",
                        claim_id,
                        "--owner",
                        "codex-b",
                    ]
                )
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(_json(result)["status"], "conflict")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_strict_reader_refuses_malformed_and_aliased_journals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            malformed = Path(tmp) / "malformed.jsonl"
            malformed.write_text("{not-json}\n", encoding="utf-8")
            result = _run(["--claims-file", str(malformed), "active"])
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid JSON", result.stderr)

            invalid_utf8 = Path(tmp) / "invalid-utf8.jsonl"
            invalid_utf8.write_bytes(b"\xff")
            invalid = _run(["--claims-file", str(invalid_utf8), "active"])
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("valid UTF-8", invalid.stderr)

            bounded = Path(tmp) / "bounded.jsonl"
            bounded.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(claims.ClaimsJournalError):
                claims.CoordinationClaims(bounded, max_bytes=2).snapshot()

            target = Path(tmp) / "target.jsonl"
            target.write_text("", encoding="utf-8")
            alias = Path(tmp) / "alias.jsonl"
            os.symlink(target, alias)
            aliased = _run(["--claims-file", str(alias), "active"])
            self.assertEqual(aliased.returncode, 2)
            self.assertIn("unsafe", aliased.stderr)

    def test_expired_claim_does_not_block_new_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "event": "claim",
                        "claim_id": "clm_old",
                        "ts": "2000-01-01T00:00:00Z",
                        "repo": "vidux",
                        "claim": "PLAN.md",
                        "files_claimed": ["PLAN.md"],
                        "owner": "codex-old",
                        "lane": "old",
                        "plan_path": "PLAN.md",
                        "task_id": "T4",
                        "ttl_hours": 2,
                        "expires_at": "2000-01-01T02:00:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = _run(
                [
                    "--claims-file",
                    str(path),
                    "claim",
                    "--repo",
                    "vidux",
                    "--claim",
                    "PLAN.md",
                    "--owner",
                    "codex-new",
                    "--lane",
                    "new",
                    "--plan-path",
                    "PLAN.md",
                    "--task-id",
                    "T4",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(_json(result)["status"], "claimed")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_main_empty_argv_does_not_read_process_argv(self) -> None:
        """Programmatic main([]) must not claim from ambient sys.argv."""
        with tempfile.TemporaryDirectory() as tmp:
            claims_file = Path(tmp) / "ambient-claims.jsonl"
            original_argv = sys.argv[:]
            sys.argv = [
                "probe",
                "--claims-file",
                str(claims_file),
                "claim",
                "--repo",
                "vidux",
                "--claim",
                "PLAN.md",
                "--owner",
                "codex-a",
                "--lane",
                "lane-a",
                "--plan-path",
                "PLAN.md",
                "--task-id",
                "T4",
            ]
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with (
                    self.assertRaises(SystemExit) as raised,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    claims.main([])
            finally:
                sys.argv = original_argv

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("the following arguments are required", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(claims_file.exists())


if __name__ == "__main__":
    unittest.main()
