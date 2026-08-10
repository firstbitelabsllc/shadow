"""The public claim command is a thin gate onto the computer root board."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402

THROW = ROOT / "scripts" / "shadow-throw.py"
STATUS = ROOT / "scripts" / "shadow-status.py"
AMP = ROOT / "scripts" / "shadow-amp.py"

PLAN = """# Demo

## Brief

- Project: demo
- Mode: ship
- Priority: 2

## Tasks

### The live outcome
- [completed] groundwork ~aa11 | proof: cmd true
- [pending] the ready row ~bb22 | proof: cmd true
- [pending] blocked by needs ~cc33 | proof: cmd true | needs: ~dd44
- [pending] the unfinished dependency ~dd44 | proof: cmd true
- [pending] proof can be removed for a refusal test ~ee55 | proof: cmd true
- [pending] owner clicks ship ~ff66 (DoD) | proof: gate owner resume: visible

## Progress

- 2026-08-09T00:00:00Z ~aa11 PROOF true -> ok
"""


def fixture(root: Path) -> tuple[Path, Path, dict[str, str]]:
    repo = root / "repo"
    home = root / "home"
    repo.mkdir()
    home.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "PLAN.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "plan"], check=True)
    return repo, home, {**os.environ, "HOME": str(home)}


def run(script: Path, repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--repo", str(repo), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ThrowRefusesAmbiguousWork(unittest.TestCase):
    def test_unknown_needs_blocked_and_proofless_rows_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            cases = (
                ("~zzzz", "no task carries"),
                ("~cc33", "still needs ~dd44"),
            )
            for row, expected in cases:
                result = run(THROW, repo, env, "--task", row, "--by", "seat-a")
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stderr)
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    " ~ee55 | proof: cmd true", " ~ee55"
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "remove proof"], check=True)
            proofless = run(THROW, repo, env, "--task", "~ee55", "--by", "seat-a")
            self.assertEqual(proofless.returncode, 1)
            self.assertIn("has no proof", proofless.stderr)

    def test_dirty_or_conflicted_plan_refuses_before_the_board_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            (repo / "PLAN.md").write_text(PLAN + "\nunsafe edit\n", encoding="utf-8")
            result = run(THROW, repo, env, "--task", "~bb22", "--by", "seat-a")
            self.assertEqual(result.returncode, 1)
            self.assertIn("uncommitted changes", result.stderr)
            self.assertFalse((home / ".shadow").exists())

    def test_duplicate_target_refuses_before_the_board_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            plan = repo / "PLAN.md"
            plan.write_text(
                plan.read_text(encoding="utf-8").replace(
                    "- [pending] blocked by needs ~cc33",
                    "- [pending] duplicate target ~bb22 | proof: cmd true\n"
                    "- [pending] blocked by needs ~cc33",
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "duplicate"], check=True)

            result = run(THROW, repo, env, "--task", "~bb22", "--by", "seat-a")

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("does not read clean", result.stderr)
            self.assertFalse((home / ".shadow").exists())

    def test_bad_id_removed_timestamp_and_bad_return_are_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            self.assertEqual(
                run(THROW, repo, env, "--task", "nope", "--by", "seat-a").returncode,
                2,
            )
            result = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--timestamp",
                "2099-01-01T00:00:00Z",
            )
            self.assertEqual(result.returncode, 2)
            result = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--return-by",
                "not-a-time",
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse((home / ".shadow").exists())


class ThrowUsesTheRootBoard(unittest.TestCase):
    def test_claim_prints_the_pointer_without_changing_the_project_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            before = (repo / "PLAN.md").read_bytes()
            head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            result = run(THROW, repo, env, "--task", "~bb22", "--by", "codex")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/goal demo", result.stdout)
            self.assertEqual((repo / "PLAN.md").read_bytes(), before)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                head,
            )
            payload = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["claims"][0]["owner"], "codex")

    def test_second_claim_names_the_persisted_owner_and_amp_skips_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, env = fixture(Path(tmp))
            self.assertEqual(
                run(THROW, repo, env, "--task", "~bb22", "--by", "claude").returncode,
                0,
            )
            losing = run(THROW, repo, env, "--task", "~bb22", "--by", "codex")
            self.assertEqual(losing.returncode, 1)
            self.assertIn("claimed by claude", losing.stderr)
            projected = run(AMP, repo, env)
            self.assertNotIn("the ready row ~bb22", projected.stdout)

    def test_claim_receipt_cannot_confuse_the_same_owner_and_row_across_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_repo, home, env = fixture(root)
            second_repo = root / "second"
            second_repo.mkdir()
            subprocess.run(["git", "init", "-q", str(second_repo)], check=True)
            subprocess.run(["git", "-C", str(second_repo), "config", "user.email", "t@t"], check=True)
            subprocess.run(["git", "-C", str(second_repo), "config", "user.name", "t"], check=True)
            (second_repo / "PLAN.md").write_text(
                PLAN.replace("- Project: demo", "- Project: second").replace(
                    "- Priority: 2", "- Priority: 5"
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(second_repo), "add", "PLAN.md"], check=True)
            subprocess.run(
                ["git", "-C", str(second_repo), "commit", "-qm", "plan"],
                check=True,
            )

            first = run(
                THROW, first_repo, env, "--task", "~bb22", "--by", "same-seat"
            )
            second = run(
                THROW, second_repo, env, "--task", "~bb22", "--by", "same-seat"
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            expected = next(
                item
                for item in payload["entities"]
                if Path(item["plan"]) == (second_repo / "PLAN.md").resolve()
            )
            self.assertIn(f"Entity: {expected['id']}.", second.stdout)
            self.assertIn("Priority: 5", second.stdout)
            self.assertEqual(
                [(item["entity"], item["row"], item["owner"]) for item in payload["claims"]],
                sorted(
                    [
                        (item["entity"], item["row"], item["owner"])
                        for item in payload["claims"]
                    ]
                ),
            )
            self.assertEqual(len(payload["claims"]), 2)

    def test_a_committed_plan_change_at_claim_time_refuses_without_a_stale_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            spec = importlib.util.spec_from_file_location("shadow_throw_race", THROW)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            real_claim = module._board.claim

            def race(*args, **kwargs):
                plan = repo / "PLAN.md"
                plan.write_text(
                    plan.read_text(encoding="utf-8").replace(
                        "the ready row ~bb22 | proof: cmd true",
                        "the ready row ~bb22 | proof: cmd false",
                    ),
                    encoding="utf-8",
                )
                subprocess.run(
                    ["git", "-C", str(repo), "commit", "-qam", "race plan proof"],
                    check=True,
                )
                return real_claim(*args, **kwargs)

            output = io.StringIO()
            errors = io.StringIO()
            with (
                mock.patch.dict(os.environ, env, clear=False),
                mock.patch.object(module._board, "claim", side_effect=race),
                redirect_stdout(output),
                redirect_stderr(errors),
            ):
                result = module.main(
                    ["--repo", str(repo), "--task", "~bb22", "--by", "seat-a"]
                )

            self.assertEqual(result, 1)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("changed", errors.getvalue())
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"], [])

    def test_amp_and_throw_never_emit_remote_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, env = fixture(Path(tmp))
            secret = "AKIA" + "IOSFODNN7EXAMPLE"
            subprocess.run(
                [
                    "git", "-C", str(repo), "remote", "add", "origin",
                    f"https://user:{secret}@github.com/org/repo.git?token={secret}#private",
                ],
                check=True,
            )

            claimed = run(THROW, repo, env, "--task", "~bb22", "--by", "seat-a")
            preview = run(AMP, repo, env, "--by", "seat-a")

            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            for stream in (preview.stdout, preview.stderr, claimed.stdout, claimed.stderr):
                self.assertNotIn(secret, stream)
                self.assertNotIn("token=", stream)

    def test_in_flight_reads_owner_and_proof_from_board_plus_project_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            claimed = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--by",
                "codex",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            observed = subprocess.run(
                [sys.executable, str(STATUS), "--in-flight", "--json"],
                cwd=home,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            report = json.loads(observed.stdout)
            self.assertEqual(len(report["rows"]), 1)
            self.assertEqual(report["rows"][0]["by"], "codex")
            self.assertEqual(report["rows"][0]["proof"], "cmd true")

    def test_an_expired_claim_requires_explicit_adoption_before_owner_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            board.reconcile(
                [{"plan": str(repo / "PLAN.md"), "project": "demo", "priority": 2, "candidates": ["~bb22"]}],
                [],
                home=home,
            )
            board.claim(
                repo / "PLAN.md",
                "~bb22",
                "old-seat",
                project="demo",
                priority=2,
                now=datetime(2000, 1, 1, tzinfo=timezone.utc),
                home=home,
            )

            ordinary = run(THROW, repo, env, "--task", "~bb22", "--by", "new-seat")
            self.assertEqual(ordinary.returncode, 1, ordinary.stderr)
            self.assertIn("claimed by old-seat", ordinary.stderr)

            adopted = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--by",
                "new-seat",
                "--adopt-expired",
            )

            self.assertEqual(adopted.returncode, 0, adopted.stderr)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(len(payload["claims"]), 1)
            self.assertEqual(payload["claims"][0]["owner"], "new-seat")

    def test_a_caller_supplied_future_clock_cannot_steal_a_live_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home, env = fixture(Path(tmp))
            first = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--by",
                "seat-a",
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            unbounded = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--by",
                "seat-a",
                "--return-by",
                "2098-01-01T00:00:00Z",
            )

            stolen = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--by",
                "seat-b",
                "--timestamp",
                "2099-01-01T00:00:00Z",
                "--adopt-expired",
            )
            still_live = run(
                THROW,
                repo,
                env,
                "--task",
                "~bb22",
                "--by",
                "seat-b",
                "--adopt-expired",
            )

            self.assertEqual(unbounded.returncode, 2, unbounded.stderr)
            self.assertEqual(stolen.returncode, 2, stolen.stderr)
            self.assertEqual(still_live.returncode, 1, still_live.stderr)
            payload = json.loads((home / ".shadow" / "board.json").read_text())
            self.assertEqual(payload["claims"][0]["owner"], "seat-a")


if __name__ == "__main__":
    unittest.main()
