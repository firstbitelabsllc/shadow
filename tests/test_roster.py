"""Focused safety and contract tests for the local Pilot Puppy roster."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CLI = SCRIPTS / "pilot-puppy-roster.py"
LIBRARY = SCRIPTS / "pilot_puppy_roster_lib.py"
SPEC = importlib.util.spec_from_file_location("pilot_puppy_roster_lib", LIBRARY)
assert SPEC and SPEC.loader
roster = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = roster
SPEC.loader.exec_module(roster)


def run(
    *args: str, environment: dict[str, str] | None = None, timeout: float = 5
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=timeout,
    )


def safe_root(dirname: str) -> Path:
    """Avoid macOS's conventional /var symlink in explicit override fixtures."""

    return Path(dirname).resolve()


def default_payload() -> dict[str, object]:
    return copy.deepcopy(roster.DEFAULT_ROSTER)


class RosterTests(unittest.TestCase):
    def assert_safe_error(self, result: subprocess.CompletedProcess[str], root: Path) -> None:
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(root), result.stderr)
        self.assertNotIn(".json", result.stderr)

    def test_init_creates_private_default_and_show_has_bounded_shape(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            initialized = run("init", "--file", str(config), "--json")
            shown = run("show", "--file", str(config), "--json")

            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(initialized.stdout), json.loads(shown.stdout))
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(config.parent.stat().st_mode), 0o700)

        view = json.loads(shown.stdout)
        self.assertEqual(set(view), {"schema", "roster", "fingerprint"})
        self.assertEqual(view["schema"], "pilot-puppy.roster-view.v1")
        self.assertEqual(set(view["roster"]), {"schema", "revision", "slots"})
        self.assertEqual(set(view["fingerprint"]), {"schema", "revision", "sha256"})
        self.assertEqual(view["fingerprint"]["revision"], 1)
        self.assertRegex(view["fingerprint"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(
            {slot["role"] for slot in view["roster"]["slots"]},
            {"lead", "planner", "bulk", "debug", "critic", "hard-ic"},
        )
        for slot in view["roster"]["slots"]:
            self.assertEqual(set(slot), {"id", "role", "host", "priority", "enabled"})

    def test_local_view_never_emits_model_credentials_or_private_paths(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            self.assertEqual(run("init", "--file", str(config)).returncode, 0)
            result = run("show", "--file", str(config), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = result.stdout.lower()
        self.assertNotIn(str(root).lower(), rendered)
        for forbidden in ("model", "credential", "token", "password", "account", "quota", "command", "private", "/tmp", "/users"):
            self.assertNotIn(forbidden, rendered)

    def test_default_path_honors_explicit_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            override = root / "trusted" / "roster.json"
            with mock.patch.dict(os.environ, {"PILOT_PUPPY_ROSTER_FILE": str(override)}):
                self.assertEqual(roster.default_roster_path(), override)
                initialized = run("init", environment={"PILOT_PUPPY_ROSTER_FILE": str(override)})
                shown = run("show", "--json", environment={"PILOT_PUPPY_ROSTER_FILE": str(override)})
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertTrue(override.is_file())

    def test_refuses_to_overwrite_existing_roster(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            first = run("init", "--file", str(config))
            original = config.read_bytes()
            second = run("init", "--file", str(config))
            preserved = config.read_bytes()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 1)
        self.assertIn("refusing to overwrite", second.stderr)
        self.assertEqual(preserved, original)

    def test_twenty_concurrent_inits_have_one_winner_and_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "race" / "roster.json"
            with ThreadPoolExecutor(max_workers=20) as pool:
                results = list(pool.map(lambda _: run("init", "--file", str(config)), range(20)))
            codes = [result.returncode for result in results]
            self.assertEqual(codes.count(0), 1, [(result.returncode, result.stderr) for result in results])
            self.assertEqual(codes.count(1), 19, [(result.returncode, result.stderr) for result in results])
            self.assertEqual(roster.load_roster(config), roster.DEFAULT_ROSTER)
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)

    def test_rejects_direct_symlink_for_show_and_init_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            config.parent.mkdir()
            target = root / "target.json"
            target.write_text(json.dumps(default_payload()), encoding="utf-8")
            config.symlink_to(target)
            shown = run("show", "--file", str(config), "--json")
            initialized = run("init", "--file", str(config), "--json")
            preserved = target.read_text(encoding="utf-8")
        self.assert_safe_error(shown, root)
        self.assert_safe_error(initialized, root)
        self.assertEqual(preserved, json.dumps(default_payload()))

    def test_rejects_parent_symlink_without_creating_backing_file(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            backing = root / "backing"
            backing.mkdir()
            alias = root / "alias"
            alias.symlink_to(backing, target_is_directory=True)
            result = run("init", "--file", str(alias / "roster.json"))
            self.assertFalse((backing / "roster.json").exists())
        self.assert_safe_error(result, root)

    def test_rejects_malformed_types_and_unknown_fields_without_traceback_or_path(self) -> None:
        malformed: list[object] = [
            [],
            {"schema": [], "revision": 1, "slots": []},
            {"schema": roster.ROSTER_SCHEMA, "revision": {}, "slots": []},
            {"schema": roster.ROSTER_SCHEMA, "revision": 1, "slots": {}},
            {
                "schema": roster.ROSTER_SCHEMA,
                "revision": 1,
                "slots": [{"id": [], "role": "lead", "host": "manual", "priority": 1, "enabled": True}],
            },
            {
                "schema": roster.ROSTER_SCHEMA,
                "revision": 1,
                "slots": [{"id": "lead-ok", "role": [], "host": "manual", "priority": 1, "enabled": True}],
            },
            {
                "schema": roster.ROSTER_SCHEMA,
                "revision": 1,
                "slots": [{"id": "lead-ok", "role": "lead", "host": {}, "priority": 1, "enabled": True}],
            },
            {
                "schema": roster.ROSTER_SCHEMA,
                "revision": 1,
                "slots": [{"id": "lead-ok", "role": "lead", "host": "manual", "priority": [], "enabled": True}],
            },
            {
                "schema": roster.ROSTER_SCHEMA,
                "revision": 1,
                "slots": [{"id": "lead-ok", "role": "lead", "host": "manual", "priority": 1, "enabled": {}}],
            },
            {"schema": roster.ROSTER_SCHEMA, "revision": 1, "slots": [], "unexpected": "nope"},
        ]
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            config.parent.mkdir()
            for payload in malformed:
                with self.subTest(payload=repr(payload)):
                    config.write_text(json.dumps(payload), encoding="utf-8")
                    self.assert_safe_error(run("show", "--file", str(config), "--json"), root)

    def test_rejects_unknown_role_host_invalid_identifier_and_ambiguous_priority(self) -> None:
        payloads = []
        unknown_role = default_payload()
        unknown_role["slots"][0]["role"] = "router"
        payloads.append(unknown_role)
        unknown_host = default_payload()
        unknown_host["slots"][0]["host"] = "grok"
        payloads.append(unknown_host)
        invalid_id = default_payload()
        invalid_id["slots"][0]["id"] = "../secret"
        payloads.append(invalid_id)
        bidi_id = default_payload()
        bidi_id["slots"][0]["id"] = "lead\u202eprivate"
        payloads.append(bidi_id)
        unicode_digit_id = default_payload()
        unicode_digit_id["slots"][0]["id"] = "lead\u0661"
        payloads.append(unicode_digit_id)
        ambiguous = default_payload()
        ambiguous["slots"][3]["priority"] = 1
        payloads.append(ambiguous)
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            config.parent.mkdir()
            for payload in payloads:
                with self.subTest(payload=payload):
                    config.write_text(json.dumps(payload), encoding="utf-8")
                    self.assert_safe_error(run("show", "--file", str(config)), root)

    def test_rejects_oversized_and_overdeep_content_before_it_can_be_used(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            config.parent.mkdir()
            config.write_bytes(b"x" * (roster.MAX_ROSTER_BYTES + 1))
            self.assert_safe_error(run("show", "--file", str(config)), root)

            deep: object = True
            for _ in range(roster.MAX_JSON_DEPTH + 2):
                deep = {"nested": deep}
            payload = default_payload()
            payload["slots"][0]["enabled"] = deep
            config.write_text(json.dumps(payload), encoding="utf-8")
            self.assert_safe_error(run("show", "--file", str(config)), root)

    def test_rejects_more_than_maximum_slots_and_duplicate_json_keys(self) -> None:
        payload = default_payload()
        payload["slots"] = [
            {"id": f"bulk-{index:02d}", "role": "bulk", "host": "codex", "priority": index + 1, "enabled": True}
            for index in range(roster.MAX_SLOTS + 1)
        ]
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            config.parent.mkdir()
            config.write_text(json.dumps(payload), encoding="utf-8")
            self.assert_safe_error(run("show", "--file", str(config)), root)
            config.write_text(
                '{"schema":"pilot-puppy.roster.v1","revision":1,"revision":2,"slots":[]}',
                encoding="utf-8",
            )
            self.assert_safe_error(run("show", "--file", str(config)), root)

    def test_content_hash_is_canonical_and_revision_is_available_to_later_routes(self) -> None:
        first = default_payload()
        second = copy.deepcopy(first)
        second["revision"] = 2
        self.assertEqual(roster.roster_sha256(first), roster.roster_sha256(copy.deepcopy(first)))
        self.assertNotEqual(roster.roster_sha256(first), roster.roster_sha256(second))
        fingerprint = roster.roster_fingerprint(first)
        self.assertEqual(fingerprint["schema"], "pilot-puppy.roster-fingerprint.v1")
        self.assertEqual(fingerprint["revision"], 1)
        self.assertEqual(fingerprint["sha256"], roster.roster_sha256(first))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes are unavailable on this platform")
    def test_named_pipe_roster_fails_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            config.parent.mkdir()
            os.mkfifo(config)
            result = run("show", "--file", str(config), timeout=2)
        self.assert_safe_error(result, root)

    def test_group_or_world_readable_roster_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            config = root / "config" / "roster.json"
            self.assertEqual(run("init", "--file", str(config)).returncode, 0)
            config.chmod(0o644)
            result = run("show", "--file", str(config))
        self.assert_safe_error(result, root)

    def test_route_binding_hash_excludes_private_slot_identifiers(self) -> None:
        first = default_payload()
        renamed = copy.deepcopy(first)
        renamed["slots"][2]["id"] = "fable-max"
        changed_route = copy.deepcopy(first)
        changed_route["slots"][2]["host"] = "codex"
        self.assertEqual(roster.route_roster_sha256(first), roster.route_roster_sha256(renamed))
        self.assertNotEqual(roster.route_roster_sha256(first), roster.route_roster_sha256(changed_route))


if __name__ == "__main__":
    unittest.main()
