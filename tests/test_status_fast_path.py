"""The human seat resume reads its owned board rows before the portfolio."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
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
        owned_id = status._board.entity_id(owned)
        unrelated_id = status._board.entity_id(unrelated)
        payload = {
            "schema": "shadow.root-board.v1",
            "revision": 42,
            "projects": [
                {"id": "owned", "priority": 1},
                {"id": "unrelated", "priority": 2},
            ],
            "entities": [
                {
                    "id": owned_id,
                    "project": "owned",
                    "plan": str(owned),
                    "resume": "~aa11",
                },
                {
                    "id": unrelated_id,
                    "project": "unrelated",
                    "plan": str(unrelated),
                    "resume": "~bb22",
                },
            ],
            "claims": [
                {
                    "entity": owned_id,
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
        with (
            mock.patch.dict(
                status.os.environ, {"SHADOW_DEV_ROOT": str(root)}, clear=False
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = status.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def batched_remote_records(
        self,
        root: Path,
        payload: dict,
        tips: dict[tuple[str, str], tuple[str, str]],
    ) -> tuple[list[dict], list[tuple[str, ...]]]:
        repo = (root / "repo").resolve()
        claim = {
            key: payload["claims"][0][key]
            for key in ("claimed_at", "return_by", "recovery")
        }
        payload["claims"] = []
        commit_id = "a" * 40
        receipts = {
            status._remote_claim.claim_ref(entity, row): {
                "row": row,
                "owner": owner,
                "claim": claim,
                "plan": {"relative": relative},
                "state": "acquired",
            }
            for (entity, row), (owner, relative) in tips.items()
        }

        def git(_repo, *args, **_kwargs):
            if args[:3] == ("ls-remote", "--refs", "origin"):
                output = "".join(
                    f"{commit_id}\t{ref}\n"
                    for ref in args[3:]
                    if ref in receipts
                )
                return subprocess.CompletedProcess(args, 0, output.encode(), b"")
            if args[0] == "fetch":
                return subprocess.CompletedProcess(args, 0, b"", b"")
            self.fail(f"unexpected git call: {args}")

        def validated(_repo, *, ref, **_kwargs):
            return receipts[ref]

        with (
            mock.patch.object(
                status._remote_claim, "managed_repo_for_plan", return_value=repo
            ),
            mock.patch.object(
                status._remote_claim, "uses_origin_upstream", return_value=True
            ),
            mock.patch.object(
                status._board,
                "frozen_plan_snapshot",
                return_value=({"repo": str(repo), "relative": "PLAN.md"}, b""),
            ),
            mock.patch.object(
                status._remote_claim, "_git", side_effect=git
            ) as remote_git,
            mock.patch.object(
                status._remote_claim,
                "_validated_tip_commit",
                side_effect=validated,
            ),
        ):
            records = status.board_records(payload)
        return records, [call.args[1:] for call in remote_git.call_args_list]

    def test_explicit_root_bypasses_the_machine_board_fast_path(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            machine_root = root / "machine"
            requested_root = root / "requested"
            machine_root.mkdir()
            requested_root.mkdir()
            machine_payload, machine_owned, _ = self.fixture(machine_root)
            requested_payload, requested_owned, _ = self.fixture(requested_root)
            machine_owned.write_text(
                plan("machine", "~aa11", "continue machine-wide work"),
                encoding="utf-8",
            )
            requested_owned.write_text(
                plan("requested", "~aa11", "continue explicit-root work"),
                encoding="utf-8",
            )
            machine_payload["entities"][0]["id"] = status._board.entity_id(
                machine_owned
            )
            machine_payload["claims"][0]["entity"] = machine_payload[
                "entities"
            ][0]["id"]
            requested_payload["entities"][0]["id"] = status._board.entity_id(
                requested_owned
            )
            requested_payload["claims"][0]["entity"] = requested_payload[
                "entities"
            ][0]["id"]

            with (
                mock.patch.object(
                    status._board, "snapshot", return_value=machine_payload
                ) as snapshot,
                mock.patch.object(
                    status._import,
                    "reconcile_portfolio",
                    return_value=requested_payload,
                ) as reconcile,
                mock.patch.object(
                    status,
                    "projected_claims",
                    side_effect=lambda entity, project, path, parsed, local: (
                        list(local),
                        None,
                    ),
                ),
                redirect_stdout(stdout := io.StringIO()),
                redirect_stderr(stderr := io.StringIO()),
            ):
                code = status.main(
                    ["--root", str(requested_root), "--by", "codex"]
                )

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertIn("continue explicit-root work", stdout.getvalue())
        self.assertNotIn("continue machine-wide work", stdout.getvalue())
        snapshot.assert_not_called()
        reconcile.assert_called_once()

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
        self.assertEqual(remotes, [payload["entities"][0]["id"]], remotes)

    def test_unowned_seat_reads_only_the_highest_priority_board_resume(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, owned, unrelated = self.fixture(root)
            payload["claims"] = []
            # Entity list order is not authority. The lower-priority entity is
            # first, while the project priorities choose `owned`.
            payload["entities"].reverse()
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
                code, stdout, stderr = self.invoke(root, "--by", "cold-seat")

        self.assertEqual(code, 0, stderr)
        self.assertIn("continue the owned row", stdout)
        self.assertIn("Owned: 0", stdout)
        self.assertNotIn("never read this portfolio row", stdout)
        reconcile.assert_not_called()
        self.assertEqual(reads, [owned], reads)
        self.assertEqual(remotes, [payload["entities"][1]["id"]], remotes)

    def test_unowned_seat_skips_a_remotely_owned_board_resume(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, owned, unrelated = self.fixture(root)
            payload["claims"] = []
            reads: list[Path] = []
            remotes: list[str] = []
            real_read = status._board.read_plan_text
            first_entity = payload["entities"][0]
            second_entity = payload["entities"][1]

            def read(path: Path) -> str:
                reads.append(Path(path))
                return real_read(path)

            def project(entity, project, plan_path, parsed, local_claims):
                remotes.append(entity["id"])
                if entity["id"] == first_entity["id"]:
                    return (
                        [
                            {
                                "entity": entity["id"],
                                "row": first_entity["resume"],
                                "owner": "other-seat",
                                "claimed_at": "2026-08-27T00:00:00Z",
                                "return_by": "2099-08-27T08:00:00Z",
                                "recovery": "probe-proof-then-adopt-park-or-close",
                                "remote": True,
                            }
                        ],
                        None,
                    )
                return list(local_claims), None

            with (
                mock.patch.object(status._board, "snapshot", return_value=payload),
                mock.patch.object(
                    status._import, "reconcile_portfolio", return_value=payload
                ) as reconcile,
                mock.patch.object(status._board, "read_plan_text", side_effect=read),
                mock.patch.object(status, "projected_claims", side_effect=project),
            ):
                code, stdout, stderr = self.invoke(root, "--by", "cold-seat")

        self.assertEqual(code, 0, stderr)
        self.assertNotIn("continue the owned row", stdout)
        self.assertIn("never read this portfolio row", stdout)
        reconcile.assert_not_called()
        self.assertEqual(reads, [owned, unrelated], reads)
        self.assertEqual(
            remotes,
            [first_entity["id"], second_entity["id"]],
            remotes,
        )

    def test_resume_selection_skips_an_entity_with_no_board_resume(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, owned, _ = self.fixture(root)
            payload["claims"] = []
            payload["projects"][0]["priority"] = 2
            payload["projects"][1]["priority"] = 1
            payload["entities"][1]["resume"] = None
            reads: list[Path] = []
            real_read = status._board.read_plan_text

            def read(path: Path) -> str:
                reads.append(Path(path))
                return real_read(path)

            with (
                mock.patch.object(status._board, "snapshot", return_value=payload),
                mock.patch.object(
                    status._import, "reconcile_portfolio", return_value=payload
                ) as reconcile,
                mock.patch.object(status._board, "read_plan_text", side_effect=read),
                mock.patch.object(
                    status,
                    "projected_claims",
                    side_effect=lambda entity, project, path, parsed, local: (
                        list(local),
                        None,
                    ),
                ),
            ):
                code, stdout, stderr = self.invoke(root, "--by", "cold-seat")

        self.assertEqual(code, 0, stderr)
        self.assertIn("continue the owned row", stdout)
        reconcile.assert_not_called()
        self.assertEqual(reads, [owned], reads)

    def test_selected_remote_failure_is_unknown_and_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, owned, _ = self.fixture(root)
            reads: list[Path] = []
            remotes: list[str] = []
            real_read = status._board.read_plan_text

            def read(path: Path) -> str:
                reads.append(Path(path))
                return real_read(path)

            def unavailable(entity, project, plan_path, parsed, local_claims):
                remotes.append(entity["id"])
                return list(local_claims), "remote claim discovery is unavailable or unauthenticated"

            with (
                mock.patch.object(status._board, "snapshot", return_value=payload),
                mock.patch.object(
                    status._import, "reconcile_portfolio", return_value=payload
                ) as reconcile,
                mock.patch.object(status._board, "read_plan_text", side_effect=read),
                mock.patch.object(status, "projected_claims", side_effect=unavailable),
            ):
                code, stdout, stderr = self.invoke(root, "--by", "codex")

        self.assertEqual(code, 1, (stdout, stderr))
        self.assertIn("UNKNOWN — remote claim discovery is unavailable", stdout)
        reconcile.assert_not_called()
        self.assertEqual(reads, [owned], reads)
        self.assertEqual(remotes, [payload["entities"][0]["id"]], remotes)

    def test_changed_selected_identity_fails_before_plan_or_remote_read(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, _, _ = self.fixture(root)
            changed_id = "c" * 64
            payload["entities"][0]["id"] = changed_id
            payload["claims"][0]["entity"] = changed_id
            with (
                mock.patch.object(status._board, "snapshot", return_value=payload),
                mock.patch.object(
                    status._import, "reconcile_portfolio", return_value=payload
                ) as reconcile,
                mock.patch.object(status._board, "read_plan_text") as read,
                mock.patch.object(
                    status,
                    "projected_claims",
                    side_effect=lambda entity, project, path, parsed, local: (
                        list(local),
                        None,
                    ),
                ) as project,
            ):
                code, stdout, stderr = self.invoke(root, "--by", "codex")

        self.assertEqual(code, 1, (stdout, stderr))
        self.assertIn("UNKNOWN", stdout)
        reconcile.assert_not_called()
        read.assert_not_called()
        project.assert_not_called()

    def test_exhaustive_batches_remote_discovery_once_per_repo(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, _, _ = self.fixture(root)
            first, second = payload["entities"]
            records, calls = self.batched_remote_records(
                root,
                payload,
                {(first["id"], first["resume"]): ("remote-owned", "PLAN.md")},
            )

        ls_remote_calls = [call for call in calls if call[0] == "ls-remote"]
        self.assertEqual(len(ls_remote_calls), 1, ls_remote_calls)
        refs = ls_remote_calls[0][3:]
        self.assertEqual(len(refs), 4)
        self.assertEqual({ref.split("/")[-2] for ref in refs}, {first["id"], second["id"]})
        self.assertEqual(
            [[claim["owner"] for claim in record["live_claims"]] for record in records],
            [["remote-owned"], []],
        )

    def test_exhaustive_isolates_invalid_remote_receipt_per_entity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            payload, _, _ = self.fixture(root)
            first, second = payload["entities"]
            records, calls = self.batched_remote_records(
                root,
                payload,
                {
                    (first["id"], first["resume"]): (
                        "invalid-owner",
                        "wrong/PLAN.md",
                    ),
                    (first["id"], "~zz99"): ("must-not-restore", "PLAN.md"),
                    (second["id"], second["resume"]): (
                        "healthy-owner",
                        "PLAN.md",
                    ),
                },
            )

        self.assertEqual(len([call for call in calls if call[0] == "ls-remote"]), 1)
        self.assertEqual(len([call for call in calls if call[0] == "fetch"]), 1)
        self.assertTrue(records[0]["broken"])
        self.assertIn(status.REMOTE_DISCOVERY_ISSUE, records[0]["resume"])
        self.assertNotIn("must-not-restore", str(records[0]))
        self.assertFalse(records[1].get("broken", False), records[1])
        self.assertEqual(records[1]["owner"], "healthy-owner")
        self.assertEqual(
            [claim["owner"] for claim in records[1]["live_claims"]],
            ["healthy-owner"],
        )

    def test_single_entity_discovery_reraises_invalid_batch_value(self) -> None:
        entity = "a" * 64
        with mock.patch.object(
            status._remote_claim,
            "discover_active_batch",
            return_value={entity: None},
        ):
            with self.assertRaises(status._remote_claim.RemoteClaimError):
                status._remote_claim.discover_active(
                    Path("."),
                    entity=entity,
                    project="owned",
                    rows=["~aa11"],
                    relative="PLAN.md",
                )

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
