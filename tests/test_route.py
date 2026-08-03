"""Focused contract and privacy tests for foreground local role routing."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ROSTER_LIBRARY = SCRIPTS / "pilot_puppy_roster_lib.py"
ROUTE_CLI = SCRIPTS / "pilot-puppy-route.py"
TOP_LEVEL_CLI = ROOT / "bin" / "pilot-puppy"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ROSTER_SPEC = importlib.util.spec_from_file_location("pilot_puppy_roster_lib", ROSTER_LIBRARY)
assert ROSTER_SPEC and ROSTER_SPEC.loader
roster = importlib.util.module_from_spec(ROSTER_SPEC)
sys.modules[ROSTER_SPEC.name] = roster
ROSTER_SPEC.loader.exec_module(roster)

ROUTE_SPEC = importlib.util.spec_from_file_location("pilot_puppy_route", ROUTE_CLI)
assert ROUTE_SPEC and ROUTE_SPEC.loader
route = importlib.util.module_from_spec(ROUTE_SPEC)
ROUTE_SPEC.loader.exec_module(route)


def safe_root(dirname: str) -> Path:
    return Path(dirname).resolve()


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "pilot-puppy-test@example.invalid")
    git(repo, "config", "user.name", "PilotPuppyTest")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "base")
    return repo


def make_task(root: Path, contents: str = "Change the bounded file.\n") -> Path:
    task = root / "task.md"
    task.write_text(contents, encoding="utf-8")
    return task


def make_roster(root: Path) -> Path:
    path = root / "config" / "roster.json"
    roster.initialize_roster(path)
    return path


def run(*args: str, timeout: float = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROUTE_CLI), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


class RouteTests(unittest.TestCase):
    def test_top_level_help_exposes_route_without_executing_help_text(self) -> None:
        result = subprocess.run(
            ["bash", str(TOP_LEVEL_CLI), "help", "route"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("pilot-puppy route", result.stdout)
        self.assertIn("--route-file", result.stdout)

    def test_task_kind_selects_lowest_same_role_priority_without_launching(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root)
            roster_file = make_roster(root)
            before = git_status(repo)
            result = run(
                "--repo",
                str(repo),
                "--task-id",
                "fix-file",
                "--task-file",
                str(task),
                "--task-kind",
                "dev",
                "--roster-file",
                str(roster_file),
                "--availability",
                "assume",
                "--json",
            )
            after = git_status(repo)

        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["status"], "ready")
        self.assertEqual(document["selection"], {
            "role": "bulk",
            "host": "cursor",
            "priority": 1,
            "state": "unprobed",
            "reason": "highest_enabled_priority",
        })
        self.assertEqual(document["alternatives"][0]["host"], "codex")
        self.assertEqual(document["execution"], {
            "performed": False,
            "automatic_reroute": False,
            "next_action": "explicit_host_run",
        })
        self.assertEqual(before, after)

    def test_explicit_manual_role_is_not_an_executable_host_run(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root)
            roster_file = make_roster(root)
            result = run(
                "--repo",
                str(repo),
                "--task-id",
                "plan-job",
                "--task-file",
                str(task),
                "--role",
                "planner",
                "--roster-file",
                str(roster_file),
                "--availability",
                "assume",
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["status"], "manual")
        self.assertEqual(document["selection"]["host"], "manual")
        self.assertEqual(document["execution"]["next_action"], "lead_manual_handoff")

    def test_review_task_kind_stays_a_separate_manual_critic_decision(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root)
            roster_file = make_roster(root)
            result = run(
                "--repo", str(repo), "--task-id", "review-job", "--task-file", str(task),
                "--task-kind", "review", "--roster-file", str(roster_file), "--availability", "assume", "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["status"], "manual")
        self.assertEqual(document["selection"]["role"], "critic")
        self.assertEqual(document["selection"]["host"], "manual")

    def test_host_constraint_never_silently_falls_back_to_another_host(self) -> None:
        payload = copy.deepcopy(roster.DEFAULT_ROSTER)
        with mock.patch.object(route, "probe_host", return_value=False):
            document = route.route_document(
                task_id="fix-file",
                task_hash="a" * 64,
                roster=payload,
                task_kind="dev",
                role="bulk",
                host="cursor",
                availability="probe",
            )

        self.assertEqual(document["status"], "blocked")
        self.assertIsNone(document["selection"])
        self.assertEqual(document["blocked"]["kind"], "no_available_slot")
        self.assertEqual(document["alternatives"], [
            {
                "role": "bulk",
                "host": "cursor",
                "state": "unavailable",
                "reason": "unavailable",
            }
        ])

    def test_all_unavailable_same_role_slots_block_without_cross_role_selection(self) -> None:
        payload = copy.deepcopy(roster.DEFAULT_ROSTER)
        with mock.patch.object(route, "probe_host", return_value=False):
            document = route.route_document(
                task_id="fix-file",
                task_hash="a" * 64,
                roster=payload,
                task_kind="dev",
                role="bulk",
                host=None,
                availability="probe",
            )

        self.assertEqual(document["status"], "blocked")
        self.assertIsNone(document["selection"])
        self.assertEqual({item["role"] for item in document["alternatives"]}, {"bulk"})
        self.assertEqual({item["host"] for item in document["alternatives"]}, {"cursor", "codex"})

    def test_route_hash_binds_frozen_task_and_canonical_roster(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root)
            roster_file = make_roster(root)
            first = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--json",
            )
            task.write_text("Changed frozen task.\n", encoding="utf-8")
            second = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--json",
            )
            payload = json.loads(roster_file.read_text(encoding="utf-8"))
            payload["revision"] = 2
            roster_file.write_text(json.dumps(payload), encoding="utf-8")
            third = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--json",
            )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(third.returncode, 0, third.stderr)
        first_document = json.loads(first.stdout)
        second_document = json.loads(second.stdout)
        third_document = json.loads(third.stdout)
        self.assertNotEqual(first_document["binding"]["task_sha256"], second_document["binding"]["task_sha256"])
        self.assertNotEqual(
            second_document["binding"]["route_roster_sha256"],
            third_document["binding"]["route_roster_sha256"],
        )
        self.assertEqual(third_document["binding"]["roster_revision"], 2)

    def test_route_output_never_contains_task_contents_paths_or_provider_details(self) -> None:
        marker_task = "Never serialize LEAK-MARKER-VALUE or /Users/example/private.txt.\n"
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root, marker_task)
            roster_file = make_roster(root)
            result = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = result.stdout.lower()
        self.assertNotIn(marker_task.lower().strip(), rendered)
        self.assertNotIn(str(root).lower(), rendered)
        for forbidden in ("model", "account", "quota", "credential", "token", "password", "command", "/users"):
            self.assertNotIn(forbidden, rendered)

    def test_private_local_slot_ids_never_escape_route_output(self) -> None:
        payload = copy.deepcopy(roster.DEFAULT_ROSTER)
        payload["slots"][2]["id"] = "fable-max"
        payload["slots"][3]["id"] = "grok-45"
        document = route.route_document(
            task_id="fix-file",
            task_hash="a" * 64,
            roster=payload,
            task_kind="dev",
            role="bulk",
            host=None,
            availability="assume",
        )
        rendered = json.dumps(document, sort_keys=True).lower() + route.render(document).lower()
        self.assertNotIn("fable", rendered)
        self.assertNotIn("grok", rendered)
        self.assertNotIn("slot", rendered)

    def test_human_route_output_includes_alternatives_and_escalation(self) -> None:
        document = route.route_document(
            task_id="fix-file",
            task_hash="a" * 64,
            roster=copy.deepcopy(roster.DEFAULT_ROSTER),
            task_kind="dev",
            role="bulk",
            host=None,
            availability="assume",
        )
        rendered = route.render(document)
        self.assertIn("Alternatives: bulk via codex", rendered)
        self.assertIn("Escalate: hard-ic", rendered)
        self.assertIn("no work was launched", rendered)

    def test_evidence_output_is_direct_atomic_no_overwrite_and_stays_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root)
            roster_file = make_roster(root)
            output = ".pilot-puppy/evidence/route.json"
            first = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--out", output,
            )
            route_file = repo / output
            original = route_file.read_bytes()
            second = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--out", output,
            )
            route_exists = route_file.is_file()
            route_schema = json.loads(original)["schema"]
            preserved = route_file.read_bytes()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(route_exists)
        self.assertEqual(route_schema, route.ROUTE_SCHEMA)
        self.assertEqual(second.returncode, 1)
        self.assertIn("refusing to overwrite", second.stderr)
        self.assertEqual(preserved, original)

    def test_route_refuses_non_evidence_output_and_private_errors_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = make_task(root)
            roster_file = make_roster(root)
            result = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume", "--out", "outside.json",
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(root), result.stderr)
        self.assertNotIn("outside.json", result.stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes are unavailable on this platform")
    def test_named_pipe_task_fails_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = safe_root(dirname)
            repo = make_repo(root)
            task = root / "task.pipe"
            os.mkfifo(task)
            roster_file = make_roster(root)
            result = run(
                "--repo", str(repo), "--task-id", "fix-file", "--task-file", str(task),
                "--task-kind", "dev", "--roster-file", str(roster_file), "--availability", "assume",
                timeout=2,
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(root), result.stderr)

    def test_route_schema_has_only_bounded_public_fields(self) -> None:
        schema = json.loads((ROOT / "schemas" / "route.v1.json").read_text(encoding="utf-8"))
        rendered = json.dumps(schema, sort_keys=True).lower()
        self.assertEqual(schema["properties"]["schema"]["const"], route.ROUTE_SCHEMA)
        for forbidden in ("model", "provider", "account", "quota", "credential", "prompt", "transcript", "path", "command"):
            self.assertNotIn(forbidden, rendered)


def git_status(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1"], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout


if __name__ == "__main__":
    unittest.main()
