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
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow_telemetry.py"
OBSERVED = ROOT / "scripts" / "dev" / "shadow-observed-gauntlet.py"
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


def load_observed():
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("shadow_observed_gauntlet_test", OBSERVED)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TelemetryIsOffByDefault(unittest.TestCase):
    def test_only_the_exact_local_opt_in_enables_the_writer(self) -> None:
        telemetry = load_telemetry()

        for environment in (
            {},
            {"SHADOW_TELEMETRY": ""},
            {"SHADOW_TELEMETRY": "off"},
            {"SHADOW_TELEMETRY": "LOCAL"},
        ):
            with self.subTest(environment=environment):
                self.assertFalse(telemetry.local_enabled(environment))
        self.assertTrue(telemetry.local_enabled({"SHADOW_TELEMETRY": "local"}))


class EveryEventIsInspectableOnDisk(unittest.TestCase):
    def test_each_append_is_one_readable_json_line(self) -> None:
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve() / "project"
            repo.mkdir()
            candidate = {
                "recorded_at": "2026-08-11T05:00:00Z",
                "project": "shadow",
                "entity": "a" * 64,
                "row": "~tobs",
                "verb": "throw",
                "duration_ms": 17,
                "outcome": "claimed",
            }

            destination = telemetry.emit_local(repo, candidate)
            telemetry.emit_local(
                repo,
                {**candidate, "recorded_at": "2026-08-11T05:00:01Z"},
            )

            lines = destination.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(
                [json.loads(line)["recorded_at"] for line in lines],
                ["2026-08-11T05:00:00Z", "2026-08-11T05:00:01Z"],
            )
            self.assertTrue(
                all(tuple(json.loads(line)) == EXPECTED_FIELDS for line in lines)
            )


class AMachineThatNeverOptsInIsUnchanged(unittest.TestCase):
    def test_a_real_throw_claims_without_creating_an_event_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, env = throw_fixture(root)
            env.pop("SHADOW_TELEMETRY", None)

            result = run_shadow(
                THROW, repo, env, "--task", "~bb22", "--by", "unopted-seat"
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/goal demo", result.stdout)
            self.assertFalse(
                (repo / ".shadow" / "evidence" / "shadow-events.jsonl").exists()
            )
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                (board["claims"][0]["row"], board["claims"][0]["owner"]),
                ("~bb22", "unopted-seat"),
            )


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


class AutomaticCleanupObservations(unittest.TestCase):
    def _record(self, report: dict, trigger: str = "return") -> dict:
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve() / "project"
            repo.mkdir()
            return telemetry.cleanup_record(repo, report, trigger)

    def test_disabled_and_zero_passes_are_closed_and_distinct(self) -> None:
        telemetry = load_telemetry()
        disabled = self._record({"enabled": False, "candidates": []})
        zero = self._record({"enabled": True, "candidates": []}, "accept")
        self.assertEqual(tuple(disabled), telemetry.CLEANUP_FIELDS)
        self.assertEqual(disabled["outcomes"]["disabled"], 1)
        self.assertEqual(zero["outcomes"]["no_candidates"], 1)
        self.assertEqual(disabled["candidate_count"], 0)
        self.assertEqual(zero["candidate_count"], 0)
        self.assertEqual(telemetry.validate_cleanup_record(disabled), disabled)
        self.assertEqual(telemetry.validate_cleanup_record(zero), zero)

    def test_refused_and_changed_passes_aggregate_without_candidate_identity(self) -> None:
        telemetry = load_telemetry()
        refused = self._record({
            "enabled": True,
            "candidates": [{"id": "worktree@a" * 8, "state": "refused", "reason": "/private/path"}],
        })
        changed = self._record({
            "enabled": True,
            "candidates": [{"id": "worktree@b" * 8, "state": "trashed", "changed": True}],
        }, "lifecycle")
        self.assertEqual(refused["outcomes"]["refused"], 1)
        self.assertEqual(changed["outcomes"]["trashed"], 1)
        self.assertEqual(changed["changed_count"], 1)
        self.assertNotIn("worktree@", json.dumps(refused))
        self.assertNotIn("/private/path", json.dumps(refused))

    def test_write_failure_is_nonthrowing_and_never_changes_cleanup(self) -> None:
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve() / "project"
            repo.mkdir()
            with mock.patch.dict(os.environ, {"SHADOW_TELEMETRY": "local"}, clear=False), \
                 mock.patch.object(telemetry, "append_record", side_effect=telemetry.TelemetryError("write failed")):
                self.assertFalse(telemetry.emit_cleanup_observation(
                    repo, {"enabled": True, "candidates": []}, "sweep"
                ))
            self.assertFalse((repo / ".shadow" / "evidence" / "shadow-events.jsonl").exists())

    def test_malformed_trigger_and_inconsistent_sentinels_are_refused_without_throwing(self) -> None:
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve() / "project"
            repo.mkdir()
            with mock.patch.dict(os.environ, {"SHADOW_TELEMETRY": "local"}, clear=False):
                self.assertFalse(telemetry.emit_cleanup_observation(
                    repo, {"enabled": True, "candidates": []}, []  # type: ignore[arg-type]
                ))
            record = self._record({"enabled": False, "candidates": []})
            record["candidate_count"] = 1
            with self.assertRaises(telemetry.TelemetryError):
                telemetry.validate_cleanup_record(record)

    def test_owner_discovery_uses_nul_porcelain_and_cannot_escape_as_oserror(self) -> None:
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            owner = root / "primary\ncheckout"
            source.mkdir()
            owner.mkdir()
            porcelain = b"worktree " + os.fsencode(owner) + b"\0HEAD " + b"a" * 40 + b"\0\0"
            result = subprocess.CompletedProcess([], 0, porcelain, b"")
            with mock.patch.object(telemetry.subprocess, "run", return_value=result) as run:
                self.assertEqual(telemetry.cleanup_observation_owner(source), owner)
            self.assertIn("-z", run.call_args.args[0])
            with mock.patch.object(telemetry.subprocess, "run", side_effect=OSError("private failure")):
                with self.assertRaises(telemetry.TelemetryError):
                    telemetry.cleanup_observation_owner(source)
            record = self._record({"enabled": True, "candidates": [{"state": "trashed"}]})
            record["changed_count"] = 0
            with self.assertRaises(telemetry.TelemetryError):
                telemetry.validate_cleanup_record(record)

    def test_export_rejects_unknown_or_malformed_cleanup_records_before_send(self) -> None:
        observed = load_observed()
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            events.write_text('{"schema":"untrusted","absolute_path":"/private/path"}\n', encoding="utf-8")
            sink = mock.Mock()
            count, delivered = observed.forward_events(sink, events, "a" * 32, "b" * 16)
            self.assertEqual((count, delivered), (0, False))
            sink.send_spans.assert_not_called()

            record = self._record({"enabled": True, "candidates": []})
            record["outcomes"]["no_candidates"] = 2
            events.write_text(json.dumps(record) + "\n", encoding="utf-8")
            count, delivered = observed.forward_events(sink, events, "a" * 32, "b" * 16)
            self.assertEqual((count, delivered), (0, False))
            sink.send_spans.assert_not_called()
            self.assertEqual(record["schema"], telemetry.CLEANUP_SCHEMA)

    def test_export_forwards_a_valid_cleanup_aggregate_only(self) -> None:
        observed = load_observed()
        telemetry = load_telemetry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, child = root / "repo", root / "child"
            repo.mkdir()
            for argv in (("init", "-q"), ("config", "user.email", "telemetry@example.invalid"),
                         ("config", "user.name", "Telemetry")):
                subprocess.run(["git", "-C", str(repo), *argv], check=True)
            (repo / "tracked").write_text("seed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(child), "HEAD"], check=True)
            report = {
                "enabled": True,
                "candidates": [{"state": "trashed", "changed": True}],
            }
            with mock.patch.dict(os.environ, {"SHADOW_TELEMETRY": "local"}, clear=False):
                self.assertTrue(telemetry.emit_cleanup_observation(child, report, "create"))
            events = repo / ".shadow" / "evidence" / "shadow-events.jsonl"
            self.assertTrue(events.is_file())
            self.assertFalse((child / ".shadow" / "evidence" / "shadow-events.jsonl").exists())
            record = telemetry.validate_cleanup_record(json.loads(events.read_text(encoding="utf-8")))
            self.assertEqual(record["report_sha256"], telemetry.cleanup_observation_sha256(report, "create"))
            sink = mock.Mock()
            sink.send_spans.return_value = True
            count, delivered = observed.forward_events(sink, events, "a" * 32, "b" * 16)
            self.assertEqual((count, delivered), (1, True))
            span = sink.send_spans.call_args.args[0][0]
            self.assertEqual(span["name"], "cleanup:create")
            attributes = {entry["key"]: next(iter(entry["value"].values())) for entry in span["attributes"]}
            self.assertEqual(attributes["shadow.schema"], "shadow.clean-observation.v1")
            self.assertNotIn("shadow.absolute_path", attributes)
            self.assertNotIn("shadow.id", attributes)


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
