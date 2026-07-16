#!/usr/bin/env python3
"""Setup any bake-off fixture (pilot or full variant)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PILOT_SETUP = BASE / "scripts" / "setup_pilot_fixture.py"

RULES = [
    ("full-atomic", "pilot-atomic-route-method"),
    ("pilot-atomic-route-method", "pilot-atomic-route-method"),
    ("full-compound", "pilot-compound-reconciliation"),
    ("pilot-compound-reconciliation", "pilot-compound-reconciliation"),
    ("full-ui-runtime", "pilot-runtime-ui-proof"),
    ("pilot-runtime-ui-proof", "pilot-runtime-ui-proof"),
    ("full-cold-resume-dirty", "pilot-cold-resume-dirty-wip"),
    ("pilot-cold-resume-dirty-wip", "pilot-cold-resume-dirty-wip"),
    ("full-cold-resume-blocked", "pilot-cold-resume-blocked-gate"),
    ("pilot-cold-resume-blocked-gate", "pilot-cold-resume-blocked-gate"),
    ("full-convergence", "pilot-convergence-stranded-branches"),
    ("pilot-convergence-stranded-branches", "pilot-convergence-stranded-branches"),
    ("full-safety", "pilot-safety-proof-honesty"),
    ("pilot-safety-proof-honesty", "pilot-safety-proof-honesty"),
    ("full-plan-noise", "pilot-plan-noise-duplicate-trap"),
    ("pilot-plan-noise-duplicate-trap", "pilot-plan-noise-duplicate-trap"),
]


def template_for(fixture_id: str) -> str:
    for prefix, template in RULES:
        if fixture_id == prefix or fixture_id.startswith(prefix):
            return template
    raise KeyError(f"no template for {fixture_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_id")
    parser.add_argument("dest")
    args = parser.parse_args()
    template = template_for(args.fixture_id)
    dest = Path(args.dest).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    result = subprocess.run(
        ["python3", str(PILOT_SETUP), template, str(dest)],
        cwd=BASE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
