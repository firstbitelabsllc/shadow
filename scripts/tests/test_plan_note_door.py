"""~pn02 — the progress-note door for plan-tree plans.

Proves the ~pn01 ruling: a fresh seat appends one dated Progress note to a
plan-tree plan through PlanTransaction, and every refuser holds:

1. raw fence append fails closed on parse (the 2026-09-17 outage shape),
2. begin() refuses a stale root/generation before anything is composed,
3. publish() refuses when the root changed concurrently (CAS re-check),
4. restore_exact_root() heals through the same CAS after an out-of-band
   repair, and the door keeps working — no parser relaxation anywhere.

Hermetic: every plan lives in tmp_path. The store's internal root lock is
what serializes publish; project_lock is the outer verb-layer wrapper and is
deliberately not exercised here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SHADOW_SCRIPTS = Path(__file__).resolve().parents[1]
if str(SHADOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHADOW_SCRIPTS))

from shadow_plan_store import (  # noqa: E402
    PlanStoreError,
    PlanTransaction,
    build_tree,
    digest_bytes,
    materialize_build,
    restore_exact_root,
    with_lineage,
)

SEAT = "fresh-seat"


def mint_tree_plan(tmp_path: Path) -> Path:
    """Publish a one-milestone plan-tree PLAN.md at generation 0."""
    content = (
        "# Fresh plan\n\n"
        "## Brief\n\n"
        "- Outcome: prove the note door.\n"
        "\n## Tasks\n\n"
        "### M1 - The door\n"
        "- [pending] A fresh seat appends one Progress note through the door "
        "~note (DoD) | proof: read this row's appended Progress line\n"
    ).encode()
    build = build_tree(content)
    assert materialize_build(build) == content
    plan = tmp_path / "PLAN.md"
    for digest, body in build.objects.items():
        object_dir = plan.parent / "PLAN.d" / "objects" / "sha256" / digest[:2]
        object_dir.mkdir(parents=True)
        (object_dir / digest).write_bytes(body)
    plan.write_bytes(build.root_bytes)
    return plan


def read_logical(plan: Path) -> str:
    snapshot = _snapshot(plan)
    return snapshot.materialize().decode()


def _snapshot(plan: Path):
    from shadow_plan_store import PlanSnapshot

    return PlanSnapshot.open(plan)


def append_note(plan: Path, line: str):
    """The whole door: begin CAS -> append -> publish. Nothing else."""
    tx = PlanTransaction.begin(plan)
    text = tx.original_content.decode()
    updated = text + line
    return tx.replace_content(updated.encode()).publish()


def test_fresh_seat_appends_one_progress_note(tmp_path: Path) -> None:
    plan = mint_tree_plan(tmp_path)
    before = _snapshot(plan)
    line = (
        "\n## Progress\n\n"
        "- 2026-09-19T00:00:00Z ~note PROGRESS appended by fresh-seat through "
        "PlanTransaction; root fence untouched by hand.\n"
    )
    receipt = append_note(plan, line)
    assert receipt.generation == 1
    assert receipt.previous_root_sha256 == before.root_sha256
    after = _snapshot(plan)
    assert after.root_sha256 == receipt.root_sha256
    logical = read_logical(plan)
    assert "~note PROGRESS" in logical
    assert logical.count("## Progress") == 1
    # DoD row intact and exactly one seat-visible fence.
    assert logical.count("~note (DoD)") == 1
    with pytest.raises(PlanStoreError):
        PlanTransaction.begin(plan, expected_root=before.root_sha256)


def test_raw_fence_append_fails_closed(tmp_path: Path) -> None:
    plan = mint_tree_plan(tmp_path)
    good = plan.read_bytes()
    # The 2026-09-17 outage: hand-append under the closing fence.
    plan.write_bytes(good + b"- sneaky raw line\n")
    with pytest.raises(PlanStoreError):
        _snapshot(plan).materialize()
    from shadow_plan_store import PlanSnapshot

    with pytest.raises(PlanStoreError):
        PlanSnapshot.open(plan)
    # Heal through the same CAS: the corrupt bytes are the CAS expectation,
    # the known-good root is the target — exactly how the 2026-09-17 repair ran.
    corrupt = plan.read_bytes()
    assert corrupt != good
    restore_exact_root(
        plan, expected_current_root=digest_bytes(corrupt), target_root_bytes=good
    )
    receipt = append_note(
        plan, "\n## Progress\n\n- 2026-09-19T00:00:00Z ~note healed.\n"
    )
    assert receipt.generation == 1


def test_begin_refuses_stale_root_and_generation(tmp_path: Path) -> None:
    plan = mint_tree_plan(tmp_path)
    before = _snapshot(plan)
    append_note(plan, "\n## Progress\n\n- first.\n")
    with pytest.raises(PlanStoreError):
        PlanTransaction.begin(plan, expected_root=before.root_sha256)
    with pytest.raises(PlanStoreError):
        PlanTransaction.begin(plan, expected_generation=0)
    # A seat that re-reads before composing gets through.
    tx = PlanTransaction.begin(plan, expected_generation=1)
    tx.abort()


def test_publish_refuses_concurrent_root_change(tmp_path: Path) -> None:
    plan = mint_tree_plan(tmp_path)
    # Seat A opens a transaction from generation 0.
    tx_a = PlanTransaction.begin(plan)
    # Seat B lands first.
    append_note(plan, "\n## Progress\n\n- seat B got here first.\n")
    # Seat A's publish must be refused by the CAS re-check, not merged.
    text = tx_a.original_content.decode()
    tx_a.replace_content((text + "\n## Progress\n\n- seat A late.\n").encode())
    with pytest.raises(PlanStoreError):
        tx_a.publish()
    # The refusal left seat B's note intact and seat A's absent.
    logical = read_logical(plan)
    assert "seat B got here first" in logical
    assert "seat A late" not in logical
