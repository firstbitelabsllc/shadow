#!/usr/bin/env python3
"""Print chief-of-staff briefs from repository-owned PLAN.md files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from browser.server import discover_plans  # noqa: E402


def visible(records: list[dict], include_all: bool) -> list[dict]:
    if include_all:
        return records
    return [
        record
        for record in records
        if record.get("contract_error")
        or (record.get("briefing") or {}).get("state") != "finished_with_proof"
    ]


def render(records: list[dict]) -> str:
    if not records:
        return "No active Pilot Puppy Outcome found.\n"
    blocks = []
    for record in records:
        briefing = record.get("briefing")
        if not briefing:
            blocks.append(
                "\n".join(
                    [
                        record["title"],
                        f"  State: needs a valid Operator Brief",
                        f"  Next: {record.get('contract_error') or 'Add a typed Outcome.'}",
                    ]
                )
            )
            continue
        lines = [
            record["title"],
            f"  State: {briefing['state'].replace('_', ' ')}",
            f"  Outcome: {record['outcome']['outcome']['summary']}",
            f"  Now: {record['outcome']['outcome']['current_move']}",
            f"  Recommendation: {briefing['recommendation']}",
        ]
        for index, option in enumerate(briefing.get("choices") or []):
            lines.append(f"  {chr(65 + index)}. {option['label']} — {option['consequence']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="pilot-puppy status", description=__doc__)
    result.add_argument("--root", type=Path, default=Path.cwd(), help="directory to scan")
    result.add_argument("--all", action="store_true", help="include finished Outcomes")
    result.add_argument("--json", action="store_true", help="print bounded JSON")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print("pilot-puppy status: scan root is not a directory", file=sys.stderr)
        return 2
    records = visible(discover_plans(root), args.all)
    if args.json:
        print(json.dumps({"schema": "pilot-puppy.status.v1", "plans": records}, indent=2, sort_keys=True))
    else:
        print(render(records), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
