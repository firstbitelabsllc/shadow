#!/usr/bin/env python3
"""Read this computer's board and project its canonical entity plans."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402
import shadow_board_import as _import  # noqa: E402
import shadow_remote_claim as _remote_claim  # noqa: E402

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


def plain_name(value: str) -> str:
    return re.sub(r"^[A-Za-z]+\d+\s*[—-]\s*", "", " ".join(value.split()))


def v4_brief(
    plan_path: Path,
    display_path: str | None = None,
    resume_id: str | None = None,
    *,
    hide_internal: bool = False,
    claimed: set[str] | None = None,
    plan_text: str | None = None,
    parsed: dict | None = None,
    claims: list[dict] | None = None,
) -> dict | None:
    """Render a v4-grammar plan into a bounded status record, or None if the
    plan does not carry a v4 Brief (legacy plans fall through to the old view).

    `display_path` is what the record shows: discovery hands us a root-relative
    path and the record must keep it, so a portfolio board never prints the
    operator's home directory (legacy records are relative for the same
    reason) and both plan versions render one path format."""
    if plan_text is None:
        if not _board.regular_plan(plan_path):
            return None
        try:
            plan_text = _board.read_plan_text(plan_path)
        except _board.BoardError:
            return None
    plan = parsed if parsed is not None else _amp._parse(plan_text)
    plan["claimed"] = claimed or {claim["row"] for claim in (claims or [])}
    brief = plan["brief"]
    if "Project" not in brief or "Mode" not in brief:
        return None
    milestones = plan["milestones"]
    selected = _amp._select(plan, resume_id)
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
    blocking = [
        f for f in _lint.lint_plan(plan_text) if f.get("severity") == "blocking"
    ]
    record: dict = {
        "schema": "shadow.status.v4-brief",
        "lint_blocking": len(blocking),
        "lint_first": (f"line {blocking[0].get('line')}: {blocking[0].get('check')} — "
                       f"{blocking[0].get('detail')}") if blocking else None,
        "path": display_path or str(plan_path),
        "project": brief["Project"],
        "entity_name": next(
            (
                plain_name(line[2:])[:120]
                for line in plan_text.splitlines()
                if line.startswith("# ") and line[2:].strip()
            ),
            brief["Project"].replace("-", " "),
        ),
        "mode": brief["Mode"],
        "priority": brief.get("Priority"),
        "contradictions_open": len(plan["contradictions"]),
    }
    if current:
        done = sum(1 for r in current["rows"] if r["state"] == "completed")
        record["milestone"] = f"{current['title']} ({done}/{len(current['rows'])} done)"
        if hide_internal:
            record["milestone_human"] = plain_name(current["title"])
    record["milestones"] = milestone_rotation(
        plan,
        resume_id,
        claims or [],
        hide_internal=hide_internal,
    )
    if selected:
        _, row = selected
        record["resume"] = f"[{row['state']}] {row['text']} {row['id']}"
        if hide_internal:
            record["resume_human"] = f"[{row['state']}] {row['text']}"
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


def milestone_rotation(
    plan: dict,
    resume_id: str | None,
    claims: list[dict],
    *,
    hide_internal: bool = False,
) -> list[dict]:
    """Every live milestone and checkpoint, derived from one parsed plan."""
    owners: dict[str, list[str]] = {}
    for claim in claims:
        owners.setdefault(claim["row"], []).append(claim["owner"])
    reachable = set(_amp._candidate_ids(plan))
    rotation = []
    for milestone in plan["milestones"]:
        checkpoints = []
        for row in milestone["rows"]:
            row_owners = sorted(set(owners.get(row["id"], [])))
            is_resume = row["id"] == resume_id
            if row["state"] == "completed" and not row_owners and not is_resume:
                continue
            availability = (
                "claimed" if row_owners else
                "blocked" if row["state"] == "blocked" else
                "reachable" if row["id"] in reachable else
                "waiting"
            )
            checkpoints.append(
                {
                    "id": row["id"],
                    "state": row["state"],
                    "text": row["text"],
                    "availability": availability,
                    "resume": is_resume,
                    "owners": row_owners,
                }
            )
        open_milestone = any(
            row["state"] != "completed" for row in milestone["rows"]
        )
        if not open_milestone and not checkpoints:
            continue
        counts = {
            state: sum(1 for row in milestone["rows"] if row["state"] == state)
            for state in ("pending", "in_progress", "blocked", "completed")
        }
        title = milestone["title"]
        rotation.append(
            {
                "title": title,
                "title_human": (
                    plain_name(title)
                    if hide_internal else title
                ),
                "counts": counts,
                "current": any(row["resume"] for row in checkpoints),
                "resume": next(
                    (row["id"] for row in checkpoints if row["resume"]), None
                ),
                "owners": sorted(
                    {owner for row in checkpoints for owner in row["owners"]}
                ),
                "checkpoints": checkpoints,
            }
        )
    return rotation


def render_v4(record: dict, seat: str | None = None) -> str:
    lines = [
        f"{record['project'].replace('-', ' ')} — {record.get('entity_name', record['project'])}",
        f"  Entity plan: {record['path']}",
        f"  Mode: {record['mode']}"
        + (f" | Priority: {record['priority']}" if record.get("priority") else ""),
    ]
    if record.get("milestone_human"):
        lines.append(f"  Current outcome: {record['milestone_human']}")
    elif record.get("milestone"):
        lines.append(f"  Milestone: {record['milestone']}")
    if record.get("milestones"):
        lines.append("  Milestone rotation:")
        for milestone in record["milestones"]:
            counts = milestone["counts"]
            total = sum(counts.values())
            marker = "current" if milestone["current"] else "open"
            owner = (
                f" | Owner: {', '.join(milestone['owners'])}"
                if milestone["owners"] else ""
            )
            lines.append(
                f"    {marker}: {milestone.get('title_human', milestone['title'])} "
                f"({counts['completed']}/{total} done){owner}"
            )
            for checkpoint in milestone["checkpoints"]:
                checkpoint_owner = (
                    f" | Owner: {', '.join(checkpoint['owners'])}"
                    if checkpoint["owners"] else ""
                )
                lines.append(
                    f"      [{checkpoint['state']}/{checkpoint['availability']}] "
                    f"{checkpoint['text']}{checkpoint_owner}"
                )
    lines.append(f"  Resume: {record.get('resume_human', record['resume'])}")
    live_claims = sorted(
        record.get("live_claims", []),
        key=lambda claim: (claim["owner"] != seat if seat else False, claim["row"]),
    )
    for claim in live_claims:
        lines.append(
            f"  In flight: [{claim['state']}] {claim['text']} "
            f"| Owner: {claim['owner']}"
        )
        if (
            record.get("entity")
            and seat is not None
            and claim["owner"] == seat
            and claim["state"] in {"pending", "in_progress"}
        ):
            lines.append(
                f"  Continue: shadow amp --entity {record['entity']} "
                f"--task {shlex.quote(claim['row'])} --by {shlex.quote(claim['owner'])}"
            )
        elif (
            record.get("entity")
            and seat is not None
            and claim["owner"] == seat
            and claim["state"] in {"blocked", "completed"}
        ):
            lines.append(
                f"  Recover: shadow return --entity {record['entity']} "
                f"--row {shlex.quote(claim['row'])} --by {shlex.quote(claim['owner'])}"
            )
    claimable = record.get("next_unclaimed")
    if not claimable and not record.get("owner"):
        claimable = record.get("board_resume")
    if record.get("entity") and claimable and not record.get("broken"):
        owner = shlex.quote(seat) if seat else "YOUR-STABLE-SEAT"
        lines.append(
            f"  Claim: shadow throw --entity {record['entity']} "
            f"--task {shlex.quote(claimable)} --by {owner}"
        )
    if record.get("proof"):
        lines.append(f"  Proof: {record['proof']}")
    if record.get("unclean"):
        lines.append(f"  Plan health: {record['unclean']}")
    if record.get("contradictions_open"):
        lines.append(f"  Contradictions open: {record['contradictions_open']}")
    return "\n".join(lines)


def root_board_view(payload: dict) -> dict:
    """A bounded, path-free rendering of the local authority for JSON output."""
    entities = {entity["id"]: entity for entity in payload["entities"]}
    return {
        "schema": payload["schema"],
        "revision": payload["revision"],
        "projects": [
            {
                "project": project["id"],
                "priority": project["priority"],
                "entities": sum(
                    1 for entity in payload["entities"]
                    if entity["project"] == project["id"]
                ),
            }
            for project in payload["projects"]
        ],
        "entities": [
            {
                "entity": entity["id"],
                "project": entity["project"],
                "plan": _board.public_plan_locator(Path(entity["plan"])),
                "resume": entity["resume"],
            }
            for entity in payload["entities"]
        ],
        "claims": [
            {
                "entity": claim["entity"],
                "project": entities[claim["entity"]]["project"],
                "row": claim["row"],
                "owner": claim["owner"],
                "claimed_at": claim["claimed_at"],
                "return_by": claim["return_by"],
                "recovery": claim["recovery"],
                "stale": _board.claim_is_stale(claim),
            }
            for claim in payload["claims"]
        ],
    }


def projected_claims(
    entity: dict,
    project: str,
    plan_path: Path,
    parsed: dict,
    local_claims: list[dict],
) -> tuple[list[dict], str | None]:
    """Join authenticated remote locks without changing the local board."""
    claims = list(local_claims)
    row_ids = {
        row["id"]
        for milestone in parsed["milestones"]
        for row in milestone["rows"]
    }
    repo = _remote_claim.managed_repo_for_plan(plan_path)
    if repo is None:
        return claims, None
    try:
        token, _ = _board.frozen_plan_snapshot(plan_path)
        if Path(token["repo"]) != repo:
            return claims, "remote claim discovery is unavailable or unauthenticated"
        observed = _remote_claim.discover_active(
            repo,
            entity=entity["id"],
            project=project,
            rows=sorted(row_ids),
            relative=token["relative"],
        )
    except _board.BoardError:
        return claims, "remote claim discovery is unavailable or unauthenticated"
    except _remote_claim.RemoteClaimError:
        return claims, "remote claim discovery is unavailable or unauthenticated"
    for journal in observed or []:
        projected = {
            "entity": entity["id"],
            "row": journal["row"],
            "owner": journal["owner"],
            "claimed_at": journal["claim"]["claimed_at"],
            "return_by": journal["claim"]["return_by"],
            "recovery": journal["claim"]["recovery"],
            "remote": True,
        }
        same_row = [claim for claim in claims if claim["row"] == projected["row"]]
        if same_row and any(
            any(
                claim.get(key) != projected[key]
                for key in ("owner", "claimed_at", "return_by", "recovery")
            )
            for claim in same_row
        ):
            return claims, "local and remote claim ownership disagree"
        if not same_row:
            claims.append(projected)
    return claims, None


def board_records(payload: dict) -> list[dict]:
    records: list[dict] = []
    priorities = {project["id"]: project["priority"] for project in payload["projects"]}
    ordered = sorted(
        payload["entities"],
        key=lambda entity: (priorities[entity["project"]], entity["project"], entity["id"]),
    )
    for entity in ordered:
        plan_path = Path(entity["plan"])
        project = entity["project"]
        locator = _board.public_plan_locator(plan_path)
        local_claims = [
            claim for claim in payload["claims"] if claim["entity"] == entity["id"]
        ]
        try:
            text = _board.read_plan_text(plan_path)
            parsed = _amp._parse(text)
            row_ids = {
                row["id"]
                for milestone in parsed["milestones"]
                for row in milestone["rows"]
            }
            claims, remote_issue = projected_claims(
                entity, project, plan_path, parsed, local_claims
            )
            entity_claims = {claim["row"] for claim in claims}
            record = v4_brief(
                plan_path,
                locator,
                entity["resume"],
                hide_internal=True,
                claimed=entity_claims,
                plan_text=text,
                parsed=parsed,
                claims=claims,
            )
        except (_board.BoardError, OSError, UnicodeError):
            record = None
        if record is None:
            records.append(
                {
                    "path": locator,
                    "project": project,
                    "entity": entity["id"],
                    "mode": "unknown",
                    "priority": str(priorities[project]),
                    "resume": "UNKNOWN — the entity plan is missing or unreadable",
                    "broken": True,
                }
            )
            continue
        record["entity"] = entity["id"]
        record["board_resume"] = entity["resume"]
        record["priority"] = str(priorities[project])
        unclean = _amp.unclean_note(parsed) if parsed is not None else None
        if unclean:
            # A quarantined unclean plan renders, but never as healthy: the
            # row is broken and the resume line carries the reason. Budget
            # breaches additionally name the remedy that actually works.
            record["broken"] = True
            budget = _board.hot_plan_budget(text.encode("utf-8"))
            remedy = (
                "; " + _board.hot_plan_budget_remedy(text.encode("utf-8"))
                if budget["exceeded"]
                else ""
            )
            record["resume"] = "UNHEALTHY — " + unclean + remedy
        candidates = _amp._candidate_ids(parsed) if parsed is not None else []
        rows = {
            row["id"]: row
            for milestone in (parsed or {"milestones": []})["milestones"]
            for row in milestone["rows"]
        }
        record["live_claims"] = [
            {
                "row": claim["row"],
                "owner": claim["owner"],
                "state": rows.get(claim["row"], {}).get("state", "unknown"),
                "text": rows.get(claim["row"], {}).get("text", "UNKNOWN — row missing"),
            }
            for claim in claims
        ]
        issue = _board.entity_integrity(
            entity,
            claims,
            row_ids,
            candidates,
        )
        record["next_unclaimed"] = next(
            (row for row in candidates if row not in entity_claims),
            None,
        )
        issue = issue or remote_issue
        if issue:
            record["resume"] = f"UNKNOWN — {issue}"
            record.pop("resume_human", None)
            record["broken"] = True
        if remote_issue:
            record["next_unclaimed"] = None
            for milestone in record.get("milestones", []):
                for checkpoint in milestone["checkpoints"]:
                    if not checkpoint["owners"]:
                        checkpoint["availability"] = "unknown"
        owner = next(
            (
                claim["owner"]
                for claim in claims
                if claim["row"] == entity["resume"]
            ),
            None,
        )
        if owner:
            record["owner"] = owner
        records.append(record)
    return records


def board_in_flight(payload: dict) -> list[dict]:
    rows: list[dict] = []
    entities = {entity["id"]: entity for entity in payload["entities"]}
    claims = list(payload["claims"])
    remote_failures: list[tuple[dict, str]] = []
    for pointer in payload["entities"]:
        plan_path = Path(pointer["plan"])
        local = [claim for claim in claims if claim["entity"] == pointer["id"]]
        try:
            parsed = _amp._parse(_board.read_plan_text(plan_path))
        except (_board.BoardError, OSError, UnicodeError):
            continue
        projected, issue = projected_claims(
            pointer, pointer["project"], plan_path, parsed, local
        )
        if issue:
            remote_failures.append((pointer, issue))
            continue
        known = {(claim["entity"], claim["row"]) for claim in claims}
        claims.extend(
            claim
            for claim in projected
            if claim.get("remote") and (claim["entity"], claim["row"]) not in known
        )
    for pointer, issue in remote_failures:
        rows.append(
            {
                "project": pointer["project"],
                "entity": pointer["id"],
                "plan": _board.public_plan_locator(Path(pointer["plan"])),
                "milestone": "remote claim discovery",
                "id": pointer["resume"] or "UNKNOWN",
                "text": f"UNKNOWN — {issue}",
                "proof": "MISSING — retry when the configured origin can be read",
                "thrown_at": None,
                "return_by": None,
                "by": None,
                "dispatched": False,
                "broken": True,
                "stale": False,
            }
        )
    for claim in claims:
        pointer = entities[claim["entity"]]
        plan_path = Path(pointer["plan"])
        project = pointer["project"]
        locator = _board.public_plan_locator(plan_path)
        try:
            plan = _amp._parse(_board.read_plan_text(plan_path))
        except (_board.BoardError, OSError, UnicodeError):
            plan = None
        located = next(
            (
                (milestone, row)
                for milestone in (plan or {"milestones": []})["milestones"]
                for row in milestone["rows"]
                if row["id"] == claim["row"]
            ),
            None,
        )
        if located is None:
            reason = (
                "the project plan is missing or unreadable"
                if plan is None
                else "the claimed row is missing from the project plan"
            )
            rows.append(
                {
                    "project": project,
                    "entity": pointer["id"],
                    "plan": locator,
                    "milestone": "entity pointer broken",
                    "id": claim["row"],
                    "text": f"UNKNOWN — {reason}",
                    "proof": f"MISSING — {reason}",
                    "thrown_at": claim["claimed_at"],
                    "return_by": claim["return_by"],
                    "by": claim["owner"],
                    "dispatched": True,
                    "broken": True,
                    "stale": _board.claim_is_stale(claim),
                }
            )
            continue
        milestone, row = located
        rows.append(
            {
                "project": project,
                "entity": pointer["id"],
                "plan": locator,
                "milestone": milestone["title"],
                "id": row["id"],
                "text": row["text"],
                "proof": row["fields"].get("proof", "MISSING"),
                "state": row["state"],
                "recovery": row["state"] in {"blocked", "completed"},
                "thrown_at": claim["claimed_at"],
                "return_by": claim["return_by"],
                "by": claim["owner"],
                "dispatched": True,
                "broken": False,
                "stale": _board.claim_is_stale(claim),
            }
        )
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
            if row.get("return_by"):
                kind += f" | return by {row['return_by']}"
            if row.get("stale"):
                kind += " | STALE — probe proof, then adopt, park, or close"
            out.append(f"  {row['text']}")
            out.append(f"       {kind} | {plain_name(row['milestone'])}")
            out.append(f"       proof: {row['proof']}")
        out.append("")
    out.append("Probe each proof before assuming a job died — it may have finished after the chat did.")
    return "\n".join(out) + "\n"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="shadow status", description=__doc__)
    default_root = os.environ.get("SHADOW_DEV_ROOT") or str(Path.cwd())
    result.add_argument("--root", type=Path, default=default_root, help="directory to scan")
    result.add_argument("--json", action="store_true", help="print bounded JSON")
    result.add_argument("--by", default=None, help="stable seat name for executable next moves")
    result.add_argument(
        "--shadowed",
        action="store_true",
        help="inspect plans withheld by canonical election or self-demotion",
    )
    result.add_argument(
        "--in-flight",
        action="store_true",
        help="local claims and authenticated remote locks — the recovery view",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.by:
        try:
            _board.validate_owner(args.by)
        except _board.BoardError as exc:
            print(f"shadow status: --by is unsafe: {exc}", file=sys.stderr)
            return 2
    explicit_root = any(a == "--root" or a.startswith("--root=") for a in (argv or sys.argv[1:]))
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print("shadow status: scan root is not a directory", file=sys.stderr)
        return 2
    root_board = None
    import_error = None
    original = root
    if args.shadowed:
        try:
            inspection_root = root if explicit_root else _import.portfolio_root(root)
            receipts = _import.suppression_receipts(inspection_root, _amp)
        except _board.BoardError as exc:
            print(f"shadow status: {exc}", file=sys.stderr)
            return 1
        if args.json:
            public_rows = [receipt.as_dict() for receipt in receipts]
            print(json.dumps({"schema": "shadow.shadowed.v1", "rows": public_rows}, indent=2))
        elif not receipts:
            print("nothing suppressed — every plan discovery enumerated was read")
        else:
            for receipt in receipts:
                print(f"{receipt.path} — {receipt.reason}")
        return 0
    try:
        if not explicit_root:
            root = _import.portfolio_root(root)
        root_board = _import.reconcile_portfolio(root, _amp)
    except _board.BoardError as exc:
        import_error = str(exc)
        try:
            root_board = _board.snapshot()
        except _board.BoardError as board_exc:
            print(
                f"shadow status: this computer's root board is unreadable: {board_exc}",
                file=sys.stderr,
            )
            return 1
        if root_board is None:
            print(
                f"shadow status: portfolio import failed before a board existed: {exc}",
                file=sys.stderr,
            )
            return 1
        print(
            "shadow status: portfolio refresh failed; showing the last-good computer "
            f"board — {exc}",
            file=sys.stderr,
        )
    if not explicit_root and root != original:
        print(
            "shadow status: showing the portfolio for this computer "
            "(set SHADOW_PORTFOLIO_ROOT to change where that is)",
            file=sys.stderr,
        )
    if args.in_flight:
        assert root_board is not None
        rows = board_in_flight(root_board)
        if args.json:
            report = {
                "schema": "shadow.in-flight.v1",
                "rows": rows,
                "root_board": root_board_view(root_board),
            }
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(render_in_flight(rows), end="")
        return 1 if import_error or any(row.get("broken") for row in rows) else 0

    assert root_board is not None
    v4_records = board_records(root_board)
    if not v4_records and import_error is None:
        try:
            receipts = _import.suppression_receipts(root, _amp)
        except _board.BoardError:
            receipts = []
        for receipt in receipts:
            if receipt.shadowed_by is None:
                print(
                    f"shadow status: {receipt.path} — {receipt.reason}",
                    file=sys.stderr,
                )
    if args.json:
        report = {
            "schema": "shadow.status.v1",
            "plans": [],
            "v4_plans": v4_records,
        }
        report["root_board"] = root_board_view(root_board)
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        blocks = [f"This computer — root board revision {root_board['revision']}"]
        blocks.extend(render_v4(record, args.by) for record in v4_records)
        if not v4_records:
            blocks.append("No registered Shadow entities on this computer.")
        print("\n\n".join(blocks) + "\n", end="")
    return 1 if import_error or any(record.get("broken") for record in v4_records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
