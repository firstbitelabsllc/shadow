#!/usr/bin/env python3
"""Inspect and migrate one authoritative Shadow plan without another queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from shadow_plan_store import PlanStoreError, dry_run_migration  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="verify a lossless plan-tree migration")
    migrate.add_argument("plan", type=Path)
    migrate.add_argument("--dry-run", action="store_true", required=True)
    migrate.add_argument("--board", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command != "migrate":
        parser().error("unsupported command")
    try:
        report = dry_run_migration(args.plan, board=args.board)
    except PlanStoreError as exc:
        print(f"shadow plan migrate: {exc}", file=sys.stderr)
        return 3 if "changed during dry run" in str(exc) else 2
    if (
        not report.exact_materialization
        or not report.routes_rebuilt
        or report.query_mismatches
    ):
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return 2
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
