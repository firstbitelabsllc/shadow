#!/usr/bin/env python3
"""Check pilot exit criteria from PROTOCOL.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(BASE / "results" / "live"))
    args = parser.parse_args()

    results = Path(args.results_dir).resolve()
    raw_path = results / "raw-runs.jsonl"
    if not raw_path.exists():
        print(f"Missing {raw_path}")
        return 1

    runs = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pilot_runs = [r for r in runs if r["fixture_id"].startswith("pilot-")]
    arms = {r["arm"] for r in pilot_runs}

    all_live = all(r.get("mode") == "live" for r in pilot_runs)
    score_lines = sum(1 for _ in (results / "reviewer-scores.jsonl").open(encoding="utf-8")) if (results / "reviewer-scores.jsonl").exists() else 0

    checks = {
        "fixtures_reproducible": len(pilot_runs) == 40,
        "all_runs_live_mode": all_live,
        "reviewer_packets_blindable": (results / "reviewer-scores.jsonl").exists() and score_lines == len(pilot_runs) * 20,
        "token_cost_capture_all_arms": arms
        == {
            "cursor_native",
            "claude_native",
            "codex_native",
            "current_vidux",
            "thin_vidux_kernel",
        }
        and all("input_tokens" in r for r in pilot_runs),
        "hidden_tests_catch_bad_solutions": any(r["mechanical_outcome"] == "fail" for r in pilot_runs),
        "each_arm_runnable": len(arms) == 5,
    }
    proceed = all(checks.values())
    lines = ["# Pilot Exit Criteria (Live)", ""]
    for name, ok in checks.items():
        lines.append(f"- {name}: **{'PASS' if ok else 'FAIL'}**")
    lines.extend(["", f"Proceed to full bake-off: **{'YES' if proceed else 'NO'}**", ""])
    out = results / "pilot-exit-criteria.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if proceed else 1


if __name__ == "__main__":
    raise SystemExit(main())
