"""The local telemetry boundary starts with one closed event vocabulary."""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow_telemetry.py"
DOC = ROOT / "docs" / "reference" / "telemetry.md"
EXPECTED_FIELDS = (
    "schema",
    "recorded_at",
    "project",
    "entity",
    "row",
    "verb",
    "duration_ms",
    "outcome",
)

from tests.test_throw import THROW, fixture as throw_fixture, run as run_shadow  # noqa: E402


def load_telemetry():
    if not SCRIPT.is_file():
        raise AssertionError("the local event constructor does not exist")
    spec = importlib.util.spec_from_file_location("shadow_telemetry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TheAllowlistIsClosed(unittest.TestCase):
    def test_unknown_fields_never_enter_the_constructed_record(self) -> None:
        telemetry = load_telemetry()
        candidate = {
            "schema": "attacker-controlled",
            "recorded_at": "2026-08-11T04:00:00Z",
            "project": "shadow",
            "entity": "a" * 64,
            "row": "~flds",
            "verb": "accept",
            "duration_ms": 17,
            "outcome": "ok",
            "prompt": "private prompt",
            "proof_output": "full proof output",
            "environment": {"SECRET": "should-not-survive"},
            "absolute_path": "/private/operator/path",
            "provider": "provider-private",
            "account": "account-private",
        }

        record = telemetry.event_record(candidate)

        self.assertEqual(tuple(record), EXPECTED_FIELDS)
        self.assertEqual(set(record), set(telemetry.EVENT_FIELDS))
        self.assertEqual(record["schema"], telemetry.SCHEMA)
        self.assertEqual(record["verb"], "accept")
        rejected_values = {
            "private prompt",
            "full proof output",
            "/private/operator/path",
            "provider-private",
            "account-private",
        }
        self.assertTrue(rejected_values.isdisjoint(record.values()))
        self.assertEqual(candidate["schema"], "attacker-controlled")

    def test_the_public_reference_names_exactly_the_constructor_fields(self) -> None:
        telemetry = load_telemetry()
        text = DOC.read_text(encoding="utf-8")
        documented = tuple(
            re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.MULTILINE)
        )

        self.assertEqual(telemetry.EVENT_FIELDS, EXPECTED_FIELDS)
        self.assertEqual(documented, EXPECTED_FIELDS)
        self.assertIn("no network transport", text.lower())
        self.assertIn("unknown input fields are omitted", text.lower())
        self.assertRegex(text.lower(), r"values remain\s+untrusted")


class EventsCarryNoPayload(unittest.TestCase):
    def _run_bounded_throw(
        self, repo: Path, env: dict[str, str], *, seat: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
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
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    def test_a_real_throw_writes_only_the_closed_local_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = throw_fixture(root)
            secret = "private-environment-value-that-must-never-be-recorded"
            env = {
                **env,
                "SHADOW_TELEMETRY": "local",
                "SHADOW_TEST_PRIVATE_VALUE": secret,
            }

            result = run_shadow(
                THROW, repo, env, "--task", "~bb22", "--by", "telemetry-seat"
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            event_path = repo / ".shadow" / "evidence" / "shadow-events.jsonl"
            self.assertTrue(event_path.is_file())
            self.assertEqual(stat.S_IMODE(event_path.stat().st_mode), 0o600)
            lines = event_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            claim = board["claims"][0]
            entity = next(
                item for item in board["entities"] if item["id"] == claim["entity"]
            )

            self.assertEqual(tuple(event), EXPECTED_FIELDS)
            self.assertEqual(event["schema"], "shadow.telemetry.event.v1")
            self.assertEqual(event["project"], entity["project"])
            self.assertEqual(event["entity"], claim["entity"])
            self.assertEqual(event["row"], "~bb22")
            self.assertEqual(event["verb"], "throw")
            self.assertEqual(event["outcome"], "claimed")
            self.assertIsInstance(event["duration_ms"], int)
            self.assertGreaterEqual(event["duration_ms"], 0)
            self.assertRegex(
                event["recorded_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
            )

            serialized = lines[0]
            forbidden = (
                secret,
                str(root),
                str(repo),
                str(home),
                "the ready row",
                "proof: cmd true",
                "SHADOW_TEST_PRIVATE_VALUE",
                "telemetry-seat",
            )
            for value in forbidden:
                self.assertNotIn(value, serialized)
            self.assertFalse((home / ".shadow" / "evidence").exists())

    def test_a_symlinked_project_state_cannot_redirect_the_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = throw_fixture(root)
            outside = root / "outside"
            outside.mkdir()
            (repo / ".shadow").symlink_to(outside, target_is_directory=True)
            env = {**env, "SHADOW_TELEMETRY": "local"}

            result = run_shadow(
                THROW, repo, env, "--task", "~bb22", "--by", "telemetry-seat"
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "the claim succeeded but its optional local event was not recorded",
                result.stderr,
            )
            self.assertFalse((outside / "evidence").exists())
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board["claims"][0]["row"], "~bb22")

    def test_a_fifo_destination_cannot_hang_after_the_claim_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = throw_fixture(root)
            evidence = repo / ".shadow" / "evidence"
            evidence.mkdir(parents=True)
            destination = evidence / "shadow-events.jsonl"
            os.mkfifo(destination, 0o600)
            before = destination.lstat()

            result = self._run_bounded_throw(
                repo, {**env, "SHADOW_TELEMETRY": "local"}, seat="fifo-seat"
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/goal demo", result.stdout)
            self.assertIn("~bb22 claimed by fifo-seat", result.stderr)
            self.assertIn("optional local event was not recorded", result.stderr)
            after = destination.lstat()
            self.assertTrue(stat.S_ISFIFO(after.st_mode))
            self.assertEqual((after.st_dev, after.st_ino), (before.st_dev, before.st_ino))
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board["claims"][0]["owner"], "fifo-seat")

    def test_a_held_event_lock_cannot_hang_after_the_claim_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = throw_fixture(root)
            evidence = repo / ".shadow" / "evidence"
            evidence.mkdir(parents=True)
            destination = evidence / "shadow-events.jsonl"
            destination.write_text("", encoding="utf-8")
            descriptor = os.open(destination, os.O_RDWR)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = self._run_bounded_throw(
                    repo,
                    {**env, "SHADOW_TELEMETRY": "local"},
                    seat="locked-seat",
                )
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/goal demo", result.stdout)
            self.assertIn("~bb22 claimed by locked-seat", result.stderr)
            self.assertIn("optional local event was not recorded", result.stderr)
            self.assertEqual(destination.read_bytes(), b"")
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(board["claims"][0]["owner"], "locked-seat")


class NothingSensitiveSurvivesTheEmitter(unittest.TestCase):
    def test_secret_path_environment_and_proof_values_never_reach_disk(self) -> None:
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "project"
            repo.mkdir()
            secret_prefix = bytes.fromhex("6768705f").decode("ascii")
            secret = secret_prefix + "0123456789abcdefghijklmnopqrstuvwxyz"
            operator_home = root / "Users" / "operator"
            proof_output = (
                "proof failed: private prompt and complete subprocess output\n"
                "TOKEN=should-never-be-recorded"
            )
            candidate = {
                "recorded_at": "2026-08-11T04:30:00Z",
                "project": "shadow",
                "entity": "a" * 64,
                "row": "~redk",
                "verb": "throw",
                "duration_ms": 23,
                "outcome": "claimed",
                "secret": secret,
                "absolute_home": str(operator_home),
                "proof_output": proof_output,
                "environment": {
                    "SHADOW_TEST_TOKEN": secret,
                    "HOME": str(operator_home),
                },
            }

            destination = telemetry.emit_local(repo, candidate)

            self.assertEqual(
                destination,
                repo / ".shadow" / "evidence" / "shadow-events.jsonl",
            )
            serialized = destination.read_text(encoding="utf-8")
            event = json.loads(serialized)
            self.assertEqual(tuple(event), EXPECTED_FIELDS)
            self.assertEqual(event["row"], "~redk")
            for forbidden in (
                secret,
                str(root),
                str(repo),
                str(operator_home),
                proof_output,
                "private prompt",
                "complete subprocess output",
                "TOKEN=should-never-be-recorded",
                "SHADOW_TEST_TOKEN",
                "HOME",
                "absolute_home",
                "environment",
                "proof_output",
            ):
                self.assertNotIn(forbidden, serialized)


class TheLocalSinkIsOwnerOptInOnly(unittest.TestCase):
    """The owner's local Langfuse sink never runs for users: without the
    three explicit env vars it refuses and does nothing, and no product
    script reaches for it — the ~obsv product kill stands.
    """

    def test_without_the_env_vars_it_refuses_and_does_nothing(self) -> None:
        script = ROOT / "scripts" / "dev" / "shadow-observed-gauntlet.py"
        env = {k: v for k, v in os.environ.items() if not k.startswith("SHADOW_LANGFUSE")}
        result = subprocess.run(
            [str(ROOT / "scripts" / "shadow-python.sh"), str(script), "--rounds", "1"],
            capture_output=True, text=True, check=False, env=env, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("owner opt-in only", result.stderr)

    def test_no_product_script_reaches_for_the_sink(self) -> None:
        offenders = []
        for path in (ROOT / "scripts").glob("*.py"):
            if "shadow-observed-gauntlet" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual(offenders, [], "a product script references the owner-only sink")


if __name__ == "__main__":
    unittest.main()
