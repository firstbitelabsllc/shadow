#!/usr/bin/env python3
"""End-to-end live pilot: prepare, agent fix, finalize, append (no CLI simulation metrics)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, cwd=BASE, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{result.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(BASE / "results" / "live"))
    parser.add_argument("--work-root", default=str(BASE / "runs" / "live"))
    parser.add_argument("--runner", default="cursor_agent_live")
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    work_root = Path(args.work_root).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)

    run(["python3", str(SCRIPTS / "run_live_matrix.py"), "--pilot-only", "--prepare-only", "--results-dir", str(results_dir), "--work-root", str(work_root)])

    queue = json.loads((results_dir / "awaiting_cursor.json").read_text(encoding="utf-8"))
    (results_dir / "raw-runs.jsonl").write_text("", encoding="utf-8")
    (results_dir / "reviewer-scores.jsonl").write_text("", encoding="utf-8")

    setup_note = {
        "claude_cli": "blocked_not_logged_in",
        "codex_cli": "blocked_or_hung",
        "executor": args.runner,
        "note": "Live edits + real oracles; arm discipline via live_agent_fix.py",
    }
    (results_dir / "RUNNER_SETUP.md").write_text(
        "# Live Runner Setup\n\n```json\n" + json.dumps(setup_note, indent=2) + "\n```\n",
        encoding="utf-8",
    )

    for item in queue:
        run_dir = Path(item["run_dir"])
        arm = item["arm"]
        run(["python3", str(SCRIPTS / "live_agent_fix.py"), str(run_dir), "--arm", arm])
        run(
            [
                "python3",
                str(SCRIPTS / "complete_live_run.py"),
                str(run_dir),
                "--arm",
                arm,
                "--runner",
                args.runner,
                "--notes",
                f"live_agent_fix:{arm}",
                "--finalize",
            ]
        )
        run(["python3", str(SCRIPTS / "append_live_result.py"), str(run_dir), "--results-dir", str(results_dir)])
        print(f"done {item['run_id']} {arm}", flush=True)

    run(
        [
            "python3",
            str(SCRIPTS / "aggregate_results.py"),
            "--results-dir",
            str(results_dir),
            "--label",
            "live-pilot",
            "--pilot-only",
        ]
    )
    run(["python3", str(SCRIPTS / "apply_decision_thresholds.py"), "--results-dir", str(results_dir)])
    exit_code = subprocess.run(
        ["python3", str(SCRIPTS / "check_pilot_exit.py"), "--results-dir", str(results_dir)],
        cwd=BASE,
    ).returncode
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
