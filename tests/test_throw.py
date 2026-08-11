"""The public claim command is a thin gate onto the computer root board."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_root_board as board  # noqa: E402
import shadow_remote_claim as remote_claim  # noqa: E402

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


class AProtectedTrunkStillTakesAClaim(unittest.TestCase):
    RECEIPT_FIELDS = {
        "schema", "status", "ref", "entity", "row", "owner", "project",
        "plan", "claim", "winner", "failure",
    }

    def git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def protected_fixture(self, root: Path) -> tuple[Path, Path, Path, Path, str]:
        bare = root / "protected.git"
        seed = root / "seed"
        first = root / "first"
        second = root / "second"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        seed.mkdir()
        self.git(seed, "init", "-q")
        self.git(seed, "config", "user.email", "protected@example.invalid")
        self.git(seed, "config", "user.name", "Protected Fixture")
        (seed / "PLAN.md").write_text(
            PLAN.replace("- Project: demo", "- Project: protected-demo"),
            encoding="utf-8",
        )
        self.git(seed, "add", "PLAN.md")
        self.git(seed, "commit", "-qm", "seed protected project")
        self.git(seed, "remote", "add", "origin", str(bare))
        self.git(seed, "push", "-qu", "origin", "HEAD:main")
        self.git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
        main = self.git(bare, "rev-parse", "refs/heads/main")
        hook = bare / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\n"
            "while read old new ref; do\n"
            "  test \"$ref\" != refs/heads/main || exit 1\n"
            "done\n"
            "exit 0\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)
        subprocess.run(["git", "clone", "-q", str(bare), str(first)], check=True)
        subprocess.run(["git", "clone", "-q", str(bare), str(second)], check=True)
        return bare, first, second, seed, main

    def throw_process(
        self,
        repo: Path,
        home: Path,
        seat: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.Popen[str]:
        home.mkdir()
        return subprocess.Popen(
            [
                sys.executable,
                str(THROW),
                "--repo",
                str(repo),
                "--task",
                "~bb22",
                "--by",
                seat,
            ],
            cwd=repo,
            env={**os.environ, "HOME": str(home), **(extra_env or {})},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def receipt(self, stderr: str) -> dict:
        matches = []
        for line in stderr.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("schema") == "shadow.remote-claim.v1":
                matches.append(value)
        self.assertEqual(len(matches), 1, stderr)
        self.assertEqual(set(matches[0]), self.RECEIPT_FIELDS)
        self.assertEqual(set(matches[0]["plan"]), {"head", "blob", "relative"})
        self.assertEqual(
            set(matches[0]["claim"]), {"claimed_at", "return_by", "recovery"}
        )
        return matches[0]

    def publish_receipt(
        self,
        repo: Path,
        receipt: dict,
        *,
        padding: int = 0,
    ) -> str:
        encoded = (
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
            + (b" " * padding)
            + b"\n"
        )
        blob = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=encoded,
            capture_output=True,
            check=True,
        ).stdout.decode().strip()
        tree = subprocess.run(
            ["git", "-C", str(repo), "mktree"],
            input=f"100644 blob {blob}\tclaim.json\n".encode(),
            capture_output=True,
            check=True,
        ).stdout.decode().strip()
        commit = subprocess.run(
            [
                "git", "-C", str(repo), "commit-tree", tree,
                "-p", receipt["plan"]["head"],
            ],
            input=b"hostile remote receipt\n",
            capture_output=True,
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            },
        ).stdout.decode().strip()
        self.git(repo, "push", "-q", "origin", f"{commit}:{receipt['ref']}")
        return commit

    def test_protected_main_uses_one_remote_cas_before_printing_one_packet(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, second, _, original_main = self.protected_fixture(root)
            processes = [
                self.throw_process(first, root / "home-a", "seat-a"),
                self.throw_process(second, root / "home-b", "seat-b"),
            ]
            results = [process.communicate(timeout=30) for process in processes]
            codes = [process.returncode for process in processes]

            winners = [index for index, code in enumerate(codes) if code == 0]
            losers = [index for index, code in enumerate(codes) if code == 1]
            self.assertEqual(winners, [0] if codes[0] == 0 else [1], results)
            self.assertEqual(losers, [0] if codes[0] == 1 else [1], results)
            winner_index = winners[0]
            loser_index = losers[0]
            winner_seat = ("seat-a", "seat-b")[winner_index]
            loser_seat = ("seat-a", "seat-b")[loser_index]
            winner_stdout, winner_stderr = results[winner_index]
            loser_stdout, loser_stderr = results[loser_index]
            self.assertIn("/goal protected-demo", winner_stdout)
            self.assertEqual(loser_stdout, "")
            self.assertIn(winner_seat, loser_stderr)

            winner_receipt = self.receipt(winner_stderr)
            loser_receipt = self.receipt(loser_stderr)
            self.assertEqual(winner_receipt["status"], "acquired")
            self.assertEqual(winner_receipt["owner"], winner_seat)
            self.assertEqual(winner_receipt["winner"], winner_seat)
            self.assertIsNone(winner_receipt["failure"])
            self.assertEqual(loser_receipt["status"], "lost")
            self.assertEqual(loser_receipt["owner"], loser_seat)
            self.assertEqual(loser_receipt["winner"], winner_seat)
            self.assertEqual(loser_receipt["failure"], "claim_exists")
            self.assertEqual(winner_receipt["entity"], loser_receipt["entity"])
            self.assertEqual(winner_receipt["row"], "~bb22")
            self.assertEqual(winner_receipt["project"], "protected-demo")
            self.assertEqual(winner_receipt["plan"], loser_receipt["plan"])
            self.assertNotIn(str(root), winner_stderr + loser_stderr)

            self.assertEqual(self.git(bare, "rev-parse", "refs/heads/main"), original_main)
            refs = self.git(bare, "for-each-ref", "--format=%(refname)").splitlines()
            self.assertEqual(set(refs), {"refs/heads/main", winner_receipt["ref"]})
            stored = json.loads(
                self.git(bare, "show", f"{winner_receipt['ref']}:claim.json")
            )
            self.assertEqual(stored, winner_receipt)
            for index, home_name in enumerate(("home-a", "home-b")):
                board_payload = json.loads(
                    (root / home_name / ".shadow" / "board.json").read_text(encoding="utf-8")
                )
                expected = 1 if index == winner_index else 0
                self.assertEqual(len(board_payload["claims"]), expected)

    def test_claim_ref_makes_the_exact_unpushed_plan_authority_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, _, _, original_main = self.protected_fixture(root)
            with (first / "PLAN.md").open("a", encoding="utf-8") as stream:
                stream.write("\n- local authority remains unmerged\n")
            self.git(first, "add", "PLAN.md")
            self.git(first, "commit", "-qm", "local plan authority")
            local_head = self.git(first, "rev-parse", "HEAD")
            missing = subprocess.run(
                ["git", "-C", str(bare), "cat-file", "-e", f"{local_head}^{{commit}}"],
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)

            process = self.throw_process(first, root / "home-a", "seat-a")
            stdout, stderr = process.communicate(timeout=30)

            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("/goal protected-demo", stdout)
            receipt = self.receipt(stderr)
            self.assertEqual(receipt["plan"]["head"], local_head)
            self.assertEqual(receipt["plan"]["relative"], "PLAN.md")
            self.assertEqual(self.git(bare, "rev-parse", f"{receipt['ref']}^"), local_head)
            self.git(bare, "merge-base", "--is-ancestor", local_head, receipt["ref"])
            self.assertEqual(self.git(bare, "rev-parse", "refs/heads/main"), original_main)
            local_claim = json.loads(
                (root / "home-a" / ".shadow" / "board.json").read_text(encoding="utf-8")
            )["claims"][0]
            self.assertEqual(
                receipt["claim"],
                {
                    "claimed_at": local_claim["claimed_at"],
                    "return_by": local_claim["return_by"],
                    "recovery": local_claim["recovery"],
                },
            )

    def test_nonzero_push_that_stored_this_attempt_is_still_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, _, _, _ = self.protected_fixture(root)
            hook = first / ".git" / "hooks" / "pre-push"
            hook.write_text(
                "#!/bin/sh\n"
                "while read local_ref local_oid remote_ref remote_oid; do\n"
                "  git push --no-verify \"$2\" \"$local_oid:$remote_ref\" >/dev/null 2>&1 || exit 2\n"
                "done\n"
                "exit 1\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)

            process = self.throw_process(first, root / "home-a", "seat-a")
            stdout, stderr = process.communicate(timeout=30)

            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("/goal protected-demo", stdout)
            receipt = self.receipt(stderr)
            self.assertEqual(receipt["status"], "acquired")
            self.assertEqual(receipt["winner"], "seat-a")
            self.assertEqual(
                json.loads(self.git(bare, "show", f"{receipt['ref']}:claim.json")),
                receipt,
            )

    def test_git_config_injection_cannot_redirect_origin_transport(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, _, _, _ = self.protected_fixture(root)
            second = root / "injected.git"
            subprocess.run(["git", "init", "-q", "--bare", str(second)], check=True)
            expected_entity = board.entity_id(first / "PLAN.md")
            process = self.throw_process(
                first,
                root / "home-a",
                "seat-a",
                {
                    "GIT_DIR": str(second),
                    "GIT_WORK_TREE": str(root / "injected-worktree"),
                    "GIT_CONFIG_COUNT": "2",
                    "GIT_CONFIG_KEY_0": "remote.origin.pushurl",
                    "GIT_CONFIG_VALUE_0": str(second),
                    "GIT_CONFIG_KEY_1": "remote.origin.url",
                    "GIT_CONFIG_VALUE_1": str(second),
                },
            )
            stdout, stderr = process.communicate(timeout=30)

            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("/goal protected-demo", stdout)
            receipt = self.receipt(stderr)
            self.assertEqual(receipt["entity"], expected_entity)
            self.assertEqual(
                receipt["ref"],
                f"refs/heads/shadow/claims/v1/{expected_entity}/bb22",
            )
            self.assertEqual(
                json.loads(self.git(bare, "show", f"{receipt['ref']}:claim.json")),
                receipt,
            )
            injected_refs = self.git(second, "for-each-ref", "--format=%(refname)")
            self.assertEqual(injected_refs, "")

    def test_oversized_remote_receipt_is_not_read_or_named_as_a_winner(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, _, _, _ = self.protected_fixture(root)
            token, _ = board.committed_plan_snapshot(first / "PLAN.md")
            entity = board.entity_id(first / "PLAN.md")
            ref = remote_claim.claim_ref(entity, "~bb22")
            hostile = remote_claim._receipt(
                status="acquired",
                ref=ref,
                entity=entity,
                row="~bb22",
                owner="other-seat",
                project="protected-demo",
                plan_token=token,
                claimed_at="2026-08-11T12:00:00Z",
                return_by="2026-08-11T20:00:00Z",
                recovery=board.RECOVERY_ACTION,
                winner="other-seat",
                failure=None,
            )
            self.publish_receipt(
                first,
                hostile,
                padding=remote_claim.MAX_RECEIPT_BYTES + 1,
            )

            process = self.throw_process(first, root / "home-a", "seat-a")
            stdout, stderr = process.communicate(timeout=30)

            self.assertEqual(process.returncode, 1, stderr)
            self.assertEqual(stdout, "")
            receipt = self.receipt(stderr)
            self.assertEqual(receipt["status"], "error")
            self.assertEqual(receipt["failure"], "transport_failed")
            self.assertIsNone(receipt["winner"])
            board_payload = json.loads(
                (root / "home-a" / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board_payload["claims"], [])

    def test_transport_error_compensates_exact_local_claim_without_leaking_paths(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, _, _, _ = self.protected_fixture(root)
            shutil.rmtree(bare)

            process = self.throw_process(first, root / "home-a", "seat-a")
            stdout, stderr = process.communicate(timeout=30)

            self.assertEqual(process.returncode, 1, stderr)
            self.assertEqual(stdout, "")
            receipt = self.receipt(stderr)
            self.assertEqual(receipt["status"], "error")
            self.assertEqual(receipt["owner"], "seat-a")
            self.assertIsNone(receipt["winner"])
            self.assertEqual(receipt["failure"], "transport_failed")
            self.assertNotIn(str(root), stdout + stderr)
            board_payload = json.loads(
                (root / "home-a" / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board_payload["claims"], [])

    def test_pre_push_hook_blocks_transport_and_is_scrubbed_before_compensation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            bare, first, _, _, original_main = self.protected_fixture(root)
            hook = first / ".git" / "hooks" / "pre-push"
            hook.write_text(
                f"#!/bin/sh\necho 'private hook output: {root}' >&2\nexit 1\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)

            process = self.throw_process(first, root / "home-a", "seat-a")
            stdout, stderr = process.communicate(timeout=30)

            self.assertEqual(process.returncode, 1, stderr)
            self.assertEqual(stdout, "")
            receipt = self.receipt(stderr)
            self.assertEqual(receipt["status"], "error")
            self.assertEqual(receipt["failure"], "transport_failed")
            self.assertNotIn("private hook output", stderr)
            self.assertNotIn(str(root), stderr)
            board_payload = json.loads(
                (root / "home-a" / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board_payload["claims"], [])
            self.assertEqual(self.git(bare, "rev-parse", "refs/heads/main"), original_main)
            refs = self.git(bare, "for-each-ref", "--format=%(refname)").splitlines()
            self.assertEqual(refs, ["refs/heads/main"])


if __name__ == "__main__":
    unittest.main()
