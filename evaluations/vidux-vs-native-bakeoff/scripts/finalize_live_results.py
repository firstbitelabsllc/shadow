#!/usr/bin/env python3
"""After live matrix completes, aggregate + decision + pilot exit check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"


def main() -> int:
    results_dir = BASE / "results" / "live"
    cmds = [
        [sys.executable, str(SCRIPTS / "aggregate_results.py"), "--results-dir", str(results_dir), "--label", "live-pilot", "--pilot-only", "--out", str(results_dir / "aggregate.md")],
        [sys.executable, str(SCRIPTS / "apply_decision_thresholds.py"), "--results-dir", str(results_dir)],
        [sys.executable, str(SCRIPTS / "check_pilot_exit.py"), "--results-dir", str(results_dir)],
    ]
    for cmd in cmds:
        print(">>", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=BASE).returncode
        if rc != 0 and "check_pilot_exit" in cmd[1]:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
