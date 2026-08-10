#!/usr/bin/env python3
"""Set one registered project's global priority on this computer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as board  # noqa: E402

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shadow priority", description=__doc__)
    parser.add_argument("--repo", default=".", type=Path)
    parser.add_argument("--value", required=True, type=int, choices=range(1, 6))
    args = parser.parse_args(argv)
    plan = args.repo.resolve() / "PLAN.md"
    if not plan.is_file():
        print(f"shadow priority: no plan at {plan}", file=sys.stderr)
        return 2
    try:
        payload = board.set_priority(plan, args.value)
    except (OSError, UnicodeError, board.BoardError) as exc:
        print(f"shadow priority: {exc}", file=sys.stderr)
        return 1
    print(f"priority {args.value}; root board revision {payload['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
