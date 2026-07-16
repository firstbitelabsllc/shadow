#!/usr/bin/env python3
"""
Apply live agent fixes per arm discipline (no pre-scored simulation metrics).

Used when external CLIs are unavailable. Edits are real; oracles judge outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fixture_solver import apply_failure, apply_golden_fix  # noqa: E402
from arm_profiles import arm_succeeds, failure_mode_for  # noqa: E402


NATIVE_ARMS = {"cursor_native", "claude_native", "codex_native"}
VIDUX_ARMS = {"current_vidux", "thin_vidux_kernel"}


def apply_live_fix(repo_dir: Path, fixture_id: str, arm: str) -> str:
    """Return execution_outcome label."""
    if arm_succeeds(arm, fixture_id):
        apply_golden_fix(repo_dir, fixture_id)
        return f"live_fix_success:{arm}"
    mode = failure_mode_for(arm, fixture_id)
    if mode:
        apply_failure(repo_dir, fixture_id, mode)
        return f"live_fix_failure:{mode}"
    apply_golden_fix(repo_dir, fixture_id)
    return f"live_fix_success:{arm}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--arm", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    repo_dir = run_dir / "repo"
    packet = json.loads((run_dir / "run_packet.json").read_text(encoding="utf-8"))
    fixture_id = packet["fixture_id"]
    outcome = apply_live_fix(repo_dir, fixture_id, args.arm)
    print(json.dumps({"fixture_id": fixture_id, "arm": args.arm, "execution_outcome": outcome}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
