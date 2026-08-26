"""The human seat resume reads its owned board rows before the portfolio."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "scripts" / "shadow-status.py"
SPEC = importlib.util.spec_from_file_location("shadow_status_fast_path", STATUS)
assert SPEC and SPEC.loader
status = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = status
SPEC.loader.exec_module(status)


def plan(project: str, row: str, text: str) -> str:
    return f"""# {project}

## Brief

- Project: {project}
- Mode: ship

## Tasks

### Current work
- [in_progress] {text} {row} | proof: cmd true
- [pending] {project} is accepted ~zz99 (DoD) | proof: cmd true | needs: {row}
"""


class StatusOwnedSeatFastPath(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[dict, Path, Path]:
        owned = root / "owned" / "PLAN.md"
        unrelated = root / "unrelated" / "PLAN.md"
        owned.parent.mkdir()
        unrelated.parent.mkdir()
        owned.write_text(plan("owned", "~aa11", "continue the owned row"), encoding="utf-8")
        unrelated.write_text(
            plan("unrelated", "~bb22", "never read this portfolio row"),
            encoding="utf-8",
        )
        payload = {
            "schema": "shadow.root-board.v1",
            "revision": 42,
            "projects": [
                {"id": "owned", "priority": 1},
                {"id": "unrelated", "priority": 2},
            ],
            "entities": [
                {
                    "id": "a" * 64,
                    "project": "owned",
                    "plan": str(owned),
                    "resume": "~aa11",
                },
                {
                    "id": "b" * 64,
                    "project": "unrelated",
                    "plan": str(unrelated),
                    "resume": "~bb22",
                },
            ],
            "claims": [
                {
                    "entity": "a" * 64,
                    "row": "~aa11",
                    "owner": "codex",
                    "claimed_at": "2026-08-26T00:00:00Z",
                    "return_by": "2099-08-26T08:00:00Z",
                    "recovery": "probe-proof-then-adopt-park-or-close",
                }
            ],
        }
        return payload, owned, unrelated

    def invoke(self, root: Path, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = status.main(["--root", str(root), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_owned_human_seat_reads_only_its_board_entity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, owned, unrelated = self.fixture(root)
            reads: list[Path] = []
            remotes: list[str] = []
            real_read = status._board.read_plan_text

            def read(path: Path) -> str:
                reads.append(Path(path))
                return real_read(path)

            def project(entity, project, plan_path, parsed, local_claims):
                remotes.append(entity["id"])
                return list(local_claims), None

            with (
                mock.patch.object(status._board, "snapshot", return_value=payload),
                mock.patch.object(
                    status._import, "reconcile_portfolio", return_value=payload
                ) as reconcile,
                mock.patch.object(status._board, "read_plan_text", side_effect=read),
                mock.patch.object(status, "projected_claims", side_effect=project),
            ):
                code, stdout, stderr = self.invoke(root, "--by", "codex")

        self.assertEqual(code, 0, stderr)
        self.assertIn("continue the owned row", stdout)
        self.assertNotIn("never read this portfolio row", stdout)
        reconcile.assert_not_called()
        self.assertEqual(reads, [owned], reads)
        self.assertNotIn(str(unrelated), [str(path) for path in reads])
        self.assertEqual(remotes, [], remotes)

    def test_exhaustive_surfaces_still_reconcile_and_fail_closed(self) -> None:
        cases = (
            (),
            ("--by", "codex", "--json"),
            ("--by", "codex", "--in-flight"),
        )
        for args in cases:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                payload, _, _ = self.fixture(root)
                with (
                    mock.patch.object(status._board, "snapshot", return_value=payload),
                    mock.patch.object(
                        status._import,
                        "reconcile_portfolio",
                        side_effect=status._board.BoardError("delayed portfolio unavailable"),
                    ) as reconcile,
                    mock.patch.object(
                        status,
                        "projected_claims",
                        side_effect=lambda entity, project, path, parsed, local: (
                            list(local),
                            None,
                        ),
                    ),
                ):
                    code, stdout, stderr = self.invoke(root, *args)

            self.assertEqual(reconcile.call_count, 1)
            self.assertEqual(code, 1, (stdout, stderr))
            self.assertIn("portfolio refresh failed", stderr)


if __name__ == "__main__":
    unittest.main()
