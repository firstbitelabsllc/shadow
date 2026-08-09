#!/usr/bin/env python3
"""Print chief-of-staff briefs from repository-owned PLAN.md files."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from browser.server import SKIP_DIRS, discover_plans  # noqa: E402

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

_lint_spec = _ilu.spec_from_file_location("shadow_lint", ROOT / "scripts" / "shadow-lint.py")
_lint = _ilu.module_from_spec(_lint_spec)
sys.modules.setdefault("shadow_lint", _lint)
_lint_spec.loader.exec_module(_lint)


def v4_brief(plan_path: Path, display_path: str | None = None) -> dict | None:
    """Render a v4-grammar plan into a bounded status record, or None if the
    plan does not carry a v4 Brief (legacy plans fall through to the old view).

    `display_path` is what the record shows: discovery hands us a root-relative
    path and the record must keep it, so a portfolio board never prints the
    operator's home directory (legacy records are relative for the same
    reason) and both plan versions render one path format."""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return None
    plan = _amp._parse(text)
    brief = plan["brief"]
    if "Project" not in brief or "Mode" not in brief:
        return None
    milestones = plan["milestones"]
    selected = _amp._select(plan, None)
    # The milestone line derives from the SELECTED row's milestone — the same
    # one amp's goal block names — never independently. (An in_progress row in
    # a later milestone outranks an earlier milestone's needs-blocked pending
    # rows; deriving "current" as first-with-open-work here while amp resumed
    # elsewhere broke the shared-parser guarantee.) Only when nothing is
    # selectable does the first milestone with open work label the plan.
    if selected:
        current = selected[0]
    else:
        current = next(
            (m for m in milestones if any(r["state"] != "completed" for r in m["rows"])),
            None,
        )
    # A v4-SHAPED plan is not a v4-VALID plan. `_parse` skips rows it cannot
    # match, so a plan with an illegal mode or a malformed open task could
    # render as "every task complete; mint the successor" — hiding real work.
    # Lint is additive here: the brief still renders (an operator needs it),
    # but a blocking finding is stated and completion is never claimed.
    blocking = [f for f in _lint.lint_plan(text) if f.get("severity") == "blocking"]
    record: dict = {
        "schema": "shadow.status.v4-brief",
        "lint_blocking": len(blocking),
        "lint_first": (f"line {blocking[0].get('line')}: {blocking[0].get('check')} — "
                       f"{blocking[0].get('detail')}") if blocking else None,
        "path": display_path or str(plan_path),
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
        # Nothing selectable has two very different meanings: the plan is
        # finished (chain to the successor) or it is stalled with open rows
        # that are person-gated, blocked, or waiting on unmet needs. amp owns
        # that distinction so status and the goal block can never disagree.
        # Never let a lint-blocking plan claim "nothing left to do": _parse
        # skips malformed rows, so the real work may simply be unreadable.
        record["resume"] = (
            "UNKNOWN — blocking lint findings mean 'complete' cannot be trusted; fix them first"
            if blocking else f"none — {_amp.stall_reason(plan)}"
        )
    # A v4 Brief is not a promise that the plan reads clean: parsing is
    # tolerant, so illegal modes and malformed rows would otherwise be
    # invisible on the board. Surface them beside the resume line.
    unclean = _amp.unclean_note(plan)
    if unclean:
        record["unclean"] = unclean
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
    if record.get("unclean"):
        lines.append(f"  Plan health: {record['unclean']}")
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


def portfolio_root() -> Path | None:
    """The durable fallback scan root — same board from ANY working directory.

    Shadow opened in a blank workspace (a fresh chat, a voice session, a
    scratch dir) must show the same durable plan list as Shadow opened inside
    a project. "This workspace has no plan — which project should I attach
    to?" is the failure mode this exists to delete: the wrapping agent had
    nothing to read, so it asked the person to do Shadow's job.

    Resolution: $SHADOW_PORTFOLIO_ROOT, else ~/Development if it exists.
    Returns None when neither resolves; callers fall back to cwd behavior.
    """
    configured = os.environ.get("SHADOW_PORTFOLIO_ROOT")
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_dir() else None
    default = Path.home() / "Development"
    return default if default.is_dir() else None


def in_flight(root: Path) -> list[dict]:
    """Every in_progress row in every plan under root — one master list with as
    many heads as there are plans. This is the recovery view a cold successor
    reads after a chat dies holding a dozen conversations: what was claimed,
    what proof would tell you it finished, and when it was thrown."""
    rows: list[dict] = []
    for record in discover_plans(root):
        path = record.get("path")
        if not path:
            continue
        plan_path = root / path
        try:
            text = plan_path.read_text(encoding="utf-8")
        except OSError:
            continue
        plan = _amp._parse(text)
        project = plan["brief"].get("Project") or plan_path.parent.name
        stamps: dict[str, str] = {}
        leads: dict[str, str] = {}
        for m in re.finditer(
            r"^- (?P<ts>\S+) THROWN (?P<id>~[0-9a-z]{4})\b(?P<tail>.*)$", text, flags=re.M
        ):
            stamps.setdefault(m.group("id"), m.group("ts"))
            named = re.search(r"\| by: ([^|]+)", m.group("tail"))
            if named:
                leads.setdefault(m.group("id"), named.group(1).strip())
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["state"] != "in_progress":
                    continue
                rows.append({
                    "project": project,
                    "plan": path,  # root-relative: never leak the home directory
                    "milestone": milestone["title"],
                    "id": row["id"],
                    "text": row["text"],
                    "proof": row["fields"].get("proof", "MISSING"),
                    "thrown_at": stamps.get(row["id"]),
                    "by": leads.get(row["id"]),
                    "dispatched": row["id"] in stamps,
                })
    return rows


def render_in_flight(rows: list[dict]) -> str:
    if not rows:
        return "Nothing in flight on this machine.\n"
    projects = sorted({r["project"] for r in rows})
    out = [f"{len(rows)} row(s) in flight across {len(projects)} project(s):", ""]
    for project in projects:
        out.append(project)
        for row in [r for r in rows if r["project"] == project]:
            kind = f"thrown {row['thrown_at']}" if row["dispatched"] else "hand-claimed (no THROWN line)"
            # Who to talk to. With several leads on one plan this is the
            # difference between "someone has this" and a name you can address.
            if row.get("by"):
                kind += f" by {row['by']}"
            out.append(f"  {row['id']} {row['text']}")
            out.append(f"       {kind} | {row['milestone']}")
            out.append(f"       proof: {row['proof']}")
        out.append("")
    out.append("Probe each proof before assuming a job died — it may have finished after the chat did.")
    return "\n".join(out) + "\n"


def _any_plan_file(root: Path) -> Path | None:
    """First PLAN.md file under root using discover_plans' own walk pruning,
    or None. Existence only — no parsing — so it distinguishes 'no plan at
    all' (safe to fall back) from 'a plan exists but failed ingestion'."""
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in SKIP_DIRS
            and not name.startswith(".")
            and not name.endswith("-worktrees")
        )
        if "PLAN.md" in files:
            return Path(current) / "PLAN.md"
    return None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="shadow status", description=__doc__)
    default_root = os.environ.get("SHADOW_DEV_ROOT") or str(Path.cwd())
    result.add_argument("--root", type=Path, default=default_root, help="directory to scan")
    result.add_argument("--all", action="store_true", help="include finished Outcomes")
    result.add_argument("--json", action="store_true", help="print bounded JSON")
    result.add_argument(
        "--in-flight",
        action="store_true",
        help="every claimed (in_progress) row across the portfolio — the recovery view",
    )
    result.add_argument(
        "--no-portfolio-fallback",
        action="store_true",
        help="report an empty scan as empty instead of falling back to the portfolio root",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    explicit_root = any(a == "--root" or a.startswith("--root=") for a in (argv or sys.argv[1:]))
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print("shadow status: scan root is not a directory", file=sys.stderr)
        return 2
    if (
        not explicit_root
        and not args.no_portfolio_fallback
        and not discover_plans(root)
    ):
        # discover_plans silently skips a PLAN.md that fails to load (OSError,
        # UnicodeError, contract crash). An empty result therefore has two
        # meanings, and only "no plan file exists at all" may fall back —
        # falling back over a BROKEN local plan would mask the breakage behind
        # a healthy-looking portfolio board.
        broken = _any_plan_file(root)
        if broken is not None:
            print(
                f"shadow status: {broken} exists but failed to load — fix it "
                "(shadow lint) or pass --root explicitly; not falling back.",
                file=sys.stderr,
            )
        else:
            fallback = portfolio_root()
            if fallback is not None and fallback.resolve() != root:
                print(
                    f"shadow status: no plan under {root} — showing the portfolio from {fallback}",
                    file=sys.stderr,
                )
                root = fallback.resolve()
    if args.in_flight:
        rows = in_flight(root)
        if args.json:
            print(json.dumps({"schema": "shadow.in-flight.v1", "rows": rows},
                             indent=2, sort_keys=True))
        else:
            print(render_in_flight(rows), end="")
        return 0

    # v4 plans first: a grammar-clean plan must never fall through to the
    # legacy validator and misreport as "needs a valid Brief".
    legacy_records: list[dict] = []
    v4_records: list[dict] = []
    for record in discover_plans(root):
        path = record.get("path")
        # discover_plans emits root-relative paths (browser/server.py keeps
        # them short for the board); resolve before reading.
        v4 = v4_brief(root / path, str(path)) if path else None
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
