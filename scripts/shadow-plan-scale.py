#!/usr/bin/env python3
"""Print a path-free baseline for large registered Shadow plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from shadow_plan_scale import PlanScaleError, benchmark_board  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="measure whole-plan lookup cost from the private root board"
    )
    result.add_argument("--board", required=True, type=Path)
    result.add_argument("--project", action="append", required=True)
    result.add_argument("--repeats", type=int, default=31)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = benchmark_board(
            args.board, projects=tuple(args.project), repeats=args.repeats
        )
    except PlanScaleError as exc:
        print(f"shadow plan-scale: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
