#!/usr/bin/env python3
"""Hidden oracle checks for pilot and full bake-off fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PILOT_ORACLE = BASE / "scripts" / "pilot_oracle.py"


def template_for(fixture_id: str) -> str:
    rules = [
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
    for prefix, template in rules:
        if fixture_id == prefix or fixture_id.startswith(prefix):
            return template
    raise KeyError(fixture_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_id")
    parser.add_argument("run_cwd")
    args = parser.parse_args()
    template = template_for(args.fixture_id)
    spec = importlib.util.spec_from_file_location("pilot_oracle", PILOT_ORACLE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    root = Path(args.run_cwd).resolve()
    sys.path.insert(0, str(root))
    module.ORACLES[template](root)
    print(f"{args.fixture_id} hidden oracle PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
