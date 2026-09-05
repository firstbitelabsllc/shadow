"""Amp projects one exact v2 claim instance and never launches a held seat."""

from __future__ import annotations

import importlib.util
import io
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

SPEC = importlib.util.spec_from_file_location("shadow_huddle_amp", ROOT / "scripts" / "shadow-amp.py")
amp = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(amp)

PLAN = """# Amp Huddle

## Brief

- Project: amp-huddle
- Mode: ship
- Priority: 1

## Tasks

### Execute safely
- [pending] first writer ~aa11 | proof: cmd true
- [pending] later writer ~bb22 | proof: cmd true

## Progress
"""


class HuddleAmpProjection(unittest.TestCase):
    def fixture(self) -> tuple[Path, Path, dict[str, str]]:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        home, repo = root / "home", root / "repo"
        home.mkdir()
        repo.mkdir()
        for args in (("init", "-q"), ("config", "user.email", "t@example.invalid"),
                     ("config", "user.name", "Test")):
            subprocess.run(["git", "-C", str(repo), *args], check=True)
        (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "PLAN.md"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "plan"], check=True)
        env = {**os.environ, "HOME": str(home)}
        return repo, home, env

    def claim_pair(self, repo: Path, home: Path) -> dict:
        board.ensure(home=home)
        board.reconcile([{"plan": str(repo / "PLAN.md"), "project": "amp-huddle", "priority": 1,
                          "candidates": ["~aa11", "~bb22"]}], [], home=home)
        board.claim(repo / "PLAN.md", "~aa11", "seat-a", project="amp-huddle", priority=1,
                    repo=repo, home=home)
        board.claim(repo / "PLAN.md", "~bb22", "seat-b", project="amp-huddle", priority=1,
                    repo=repo, home=home)
        return board.snapshot(home=home)

    def invoke(self, repo: Path, env: dict[str, str], *args: str) -> tuple[int, str, str]:
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(sys, "argv", [str(ROOT / "scripts" / "shadow-amp.py"), "--repo", str(repo), *args]), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            return amp.main(), out.getvalue(), err.getvalue()

    def test_later_overlap_is_held_and_first_packet_has_exact_context(self) -> None:
        repo, home, env = self.fixture()
        snapshot = self.claim_pair(repo, home)
        huddle = snapshot["huddles"][0]
        self.assertEqual(huddle["holds"], [board._claim_ref(snapshot["claims"][1])])

        code, out, err = self.invoke(repo, env, "--by", "seat-b", "--task", "~bb22")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn(f"shadow huddle show --id {huddle['id']}", err)

        code, out, err = self.invoke(repo, env, "--by", "seat-a", "--task", "~aa11")
        self.assertEqual(code, 0, err)
        first = next(claim for claim in snapshot["claims"] if claim["owner"] == "seat-a")
        expected = {key: first[key] for key in ("entity", "row", "owner", "claim_revision")}
        expected["board_revision"] = snapshot["revision"]
        self.assertIn('HOST --claim-context', out)
        self.assertIn(amp.json.dumps(expected, sort_keys=True, separators=(",", ":")), out)
        self.assertIn("unscoped requires declared preflight", out)

    def test_read_only_claim_remains_a_non_source_packet(self) -> None:
        repo, home, env = self.fixture()
        board.ensure(home=home)
        board.reconcile([{"plan": str(repo / "PLAN.md"), "project": "amp-huddle", "priority": 1,
                          "candidates": ["~aa11"]}], [], home=home)
        board.claim(repo / "PLAN.md", "~aa11", "reader", project="amp-huddle", priority=1,
                    access="read_only", home=home)
        code, out, err = self.invoke(repo, env, "--by", "reader", "--task", "~aa11")
        self.assertEqual(code, 0, err)
        self.assertIn("read_only grants no source changes", out)

    def test_second_snapshot_change_refuses_before_packet(self) -> None:
        repo, home, env = self.fixture()
        self.claim_pair(repo, home)
        actual = amp._board.snapshot
        calls = 0

        def race(*, home=None):
            nonlocal calls
            calls += 1
            value = actual(home=home)
            if calls >= 2:
                value["revision"] += 1
            return value

        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(amp._board, "snapshot", side_effect=race):
            code, out, err = self.invoke(repo, env, "--by", "seat-a", "--task", "~aa11")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("board changed while selecting", err)

    def test_terminal_replacement_of_a_held_ref_stays_held(self) -> None:
        repo, home, _env = self.fixture()
        snapshot = self.claim_pair(repo, home)
        entity = snapshot["entities"][0]
        state = board._state_for_entity(snapshot, entity)
        held = board._claim_ref(next(claim for claim in snapshot["claims"] if claim["owner"] == "seat-b"))
        successor = board._claim_ref(next(claim for claim in snapshot["claims"] if claim["owner"] == "seat-a"))
        projected = {**snapshot, "huddles": [{
            **snapshot["huddles"][0],
            "holds": [held],
            "replacements": [{"original": held, "current": successor}],
        }]}
        with mock.patch.object(amp._board, "snapshot", return_value=projected):
            with self.assertRaisesRegex(board.BoardError, "selected claim is held"):
                amp._v2_selected_claim(state, "~bb22", "seat-b")


if __name__ == "__main__":
    unittest.main()
