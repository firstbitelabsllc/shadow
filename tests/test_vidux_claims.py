"""Tests for scripts/vidux-claims.py."""

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


class ViduxClaimsTests(unittest.TestCase):
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
