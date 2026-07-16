#!/usr/bin/env python3
"""Mark a prepared live run complete after agent edits (no simulation)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--arm", required=True)
    parser.add_argument("--runner", default="cursor_agent_live")
    parser.add_argument("--notes", default="cursor_agent_live_complete")
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    payload = {
        "runner": args.runner,
        "arm": args.arm,
        "status": "complete",
        "execution_outcome": args.notes,
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
    }
    (run_dir / "runner_result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    awaiting = run_dir / "AWAITING_AGENT.json"
    if awaiting.exists():
        awaiting.unlink()

    if args.finalize:
        packet = json.loads((run_dir / "run_packet.json").read_text(encoding="utf-8"))
        cmd = [
            "python3",
            str(SCRIPTS / "run_arm.py"),
            "--fixture-id",
            packet["fixture_id"],
            "--arm",
            args.arm,
            "--run-id",
            run_dir.name,
            "--work-root",
            str(run_dir.parent),
            "--finalize",
        ]
        result = subprocess.run(cmd, cwd=BASE, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode
        score = subprocess.run(
            ["python3", str(SCRIPTS / "build_reviewer_packet.py"), str(run_dir)],
            cwd=BASE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if score.returncode != 0:
            print(score.stderr, file=sys.stderr)
            return score.returncode
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
        print(json.dumps({"mechanical_outcome": metrics["mechanical_outcome"], "mode": metrics["mode"]}))

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
