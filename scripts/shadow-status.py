#!/usr/bin/env python3
"""Print chief-of-staff briefs from repository-owned PLAN.md files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from browser.server import discover_plans  # noqa: E402

# The v4 grammar parser lives in shadow-amp; status reuses it so the two
# projections can never disagree about what the current milestone or resume
# row is. (Before this, status validated ONLY the retired v3 outcome schema,
# so every grammar-clean v4 plan reported "needs a valid Brief / outcome must
# be a string" — 250/250 plans on the reference machine.)
import importlib.util as _ilu  # noqa: E402

_amp_spec = _ilu.spec_from_file_location("shadow_amp", ROOT / "scripts" / "shadow-amp.py")
_amp = _ilu.module_from_spec(_amp_spec)
sys.modules.setdefault("shadow_amp", _amp)
_amp_spec.loader.exec_module(_amp)


def v4_brief(plan_path: Path) -> dict | None:
    """Render a v4-grammar plan into a bounded status record, or None if the
    plan does not carry a v4 Brief (legacy plans fall through to the old view)."""
    try:
        plan = _amp._parse(plan_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    brief = plan["brief"]
    if "Project" not in brief or "Mode" not in brief:
        return None
    milestones = plan["milestones"]
    current = next(
        (m for m in milestones if any(r["state"] != "completed" for r in m["rows"])),
        None,
    )
    selected = _amp._select(plan, None)
    record: dict = {
        "schema": "shadow.status.v4-brief",
        "path": str(plan_path),
        "project": brief["Project"],
        "mode": brief["Mode"],
        "priority": brief.get("Priority"),
        "contradictions_open": len(plan["contradictions"]),
    }
    if current:
        done = sum(1 for r in current["rows"] if r["state"] == "completed")
        record["milestone"] = f"{current['title']} ({done}/{len(current['rows'])} done)"
    if selected:
        _, row = selected
        record["resume"] = f"[{row['state']}] {row['text']} {row['id']}"
        record["proof"] = row["fields"].get("proof", "MISSING")
    else:
        record["resume"] = "none — every task complete; mint the successor (goal chaining)"
    return record


def render_v4(record: dict) -> str:
    lines = [
        f"{record['project']} — {record['path']}",
        f"  Mode: {record['mode']}"
        + (f" | Priority: {record['priority']}" if record.get("priority") else ""),
    ]
    if record.get("milestone"):
        lines.append(f"  Milestone: {record['milestone']}")
    lines.append(f"  Resume: {record['resume']}")
    if record.get("proof"):
        lines.append(f"  Proof: {record['proof']}")
    if record.get("contradictions_open"):
        lines.append(f"  Contradictions open: {record['contradictions_open']}")
    return "\n".join(lines)


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
        return "No active Shadow Outcome found.\n"
    blocks = []
    for record in records:
        briefing = record.get("briefing")
        if not briefing:
            blocks.append(
                "\n".join(
                    [
                        record["title"],
                        f"  State: needs a valid Brief",
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
    result = argparse.ArgumentParser(prog="shadow status", description=__doc__)
    default_root = os.environ.get("SHADOW_DEV_ROOT") or str(Path.cwd())
    result.add_argument("--root", type=Path, default=default_root, help="directory to scan")
    result.add_argument("--all", action="store_true", help="include finished Outcomes")
    result.add_argument("--json", action="store_true", help="print bounded JSON")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print("shadow status: scan root is not a directory", file=sys.stderr)
        return 2
    # v4 plans first: a grammar-clean plan must never fall through to the
    # legacy validator and misreport as "needs a valid Brief".
    legacy_records: list[dict] = []
    v4_records: list[dict] = []
    for record in discover_plans(root):
        path = record.get("path")
        # discover_plans emits root-relative paths (browser/server.py keeps
        # them short for the board); resolve before reading.
        v4 = v4_brief(root / path) if path else None
        if v4 is not None:
            v4_records.append(v4)
        else:
            legacy_records.append(record)
    legacy_records = visible(legacy_records, args.all)
    if args.json:
        print(
            json.dumps(
                {
                    "schema": "shadow.status.v1",
                    "plans": legacy_records,
                    "v4_plans": v4_records,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        blocks = [render_v4(r) for r in v4_records]
        if legacy_records:
            blocks.append(render(legacy_records).rstrip("\n"))
        print(("\n\n".join(blocks) + "\n") if blocks else render([]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
