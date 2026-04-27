#!/usr/bin/env python3
"""vidux-linear-reconcile.py — One-shot reconcile of auto-promoted Linear tasks.

Background (2026-04-27):
    Before PR #56 shipped Task 14 (state.type filter on linear adapter
    fetch_inbox), canceled Linear cards leaked into PLAN.md as auto-promoted
    BD-* tasks. PR #56 stops new leaks but does not clean up the BD-* tasks
    already minted in PLAN.md and recorded in .external-state.json.

What this script does:
    1. Read a target vidux plan dir (default: projects/vidux-linear-primacy).
    2. Find every task line in PLAN.md with a [Source: linear:<uuid>] marker.
    3. Batch-query Linear for each issue's state.type.
    4. For tasks whose remote state.type is "canceled" (Linear models Duplicate
       as a canceled-typed workflow state, so this catches both):
         - Remove the task line from PLAN.md.
         - Remove the task_id ↔ external_id mapping from
           .external-state.json["adapters"]["linear"]["task_to_external"].
    5. Print summary; exit 0.

Tasks whose remote state is anything else (Backlog, Todo, In Progress,
In Review, Done) are KEPT — only canceled/duplicate cards get reconciled.

Usage:
    # Dry-run first — print intended diff, no writes.
    python3 scripts/vidux-linear-reconcile.py --dry-run

    # Real run — mutates PLAN.md + .external-state.json in place.
    python3 scripts/vidux-linear-reconcile.py

    # Different plan dir.
    python3 scripts/vidux-linear-reconcile.py path/to/plan-dir

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

LINEAR_TOKEN_PATH = Path(os.path.expanduser("~/.config/vidux/linear.token"))
LINEAR_ENDPOINT = "https://api.linear.app/graphql"
DEFAULT_PLAN_DIR = Path(__file__).resolve().parent.parent / "projects" / "vidux-linear-primacy"

# Linear state types that mean "this card is dead, drop the local task"
DROP_STATE_TYPES = {"canceled"}

_SOURCE_RE = re.compile(r"\[Source:\s*linear:([0-9a-f-]{36})\]")


def load_token() -> str:
    if not LINEAR_TOKEN_PATH.exists():
        sys.exit(f"linear token missing at {LINEAR_TOKEN_PATH}")
    return LINEAR_TOKEN_PATH.read_text().strip()


def query_states(token: str, issue_ids: list[str]) -> dict[str, dict]:
    """Batch-fetch state info for issue UUIDs. Returns {uuid: {name, type}}."""
    if not issue_ids:
        return {}
    aliases = " ".join(
        f'i{n}: issue(id: "{uid}") {{ id state {{ name type }} }}'
        for n, uid in enumerate(issue_ids)
    )
    query = "{ " + aliases + " }"
    req = urllib.request.Request(
        LINEAR_ENDPOINT,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": token, "Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"linear http error {e.code}: {e.read().decode()[:500]}")
    if "errors" in resp:
        sys.exit(f"linear graphql errors: {resp['errors']}")
    out: dict[str, dict] = {}
    for entry in resp["data"].values():
        if entry is None:
            continue
        out[entry["id"]] = entry["state"]
    return out


def reconcile_plan(plan_dir: Path, dry_run: bool) -> dict:
    plan_path = plan_dir / "PLAN.md"
    state_path = plan_dir / ".external-state.json"
    if not plan_path.exists():
        sys.exit(f"PLAN.md missing at {plan_path}")

    plan_text = plan_path.read_text()
    plan_lines = plan_text.splitlines(keepends=True)

    # Map task line index -> linear uuid
    line_to_uuid: dict[int, str] = {}
    for i, line in enumerate(plan_lines):
        m = _SOURCE_RE.search(line)
        if m:
            line_to_uuid[i] = m.group(1)

    if not line_to_uuid:
        return {"plan": str(plan_dir), "scanned": 0, "removed_lines": [], "dropped_uuids": []}

    token = load_token()
    states = query_states(token, list(set(line_to_uuid.values())))

    removed_indices: list[int] = []
    dropped_uuids: list[str] = []
    for i, uid in line_to_uuid.items():
        st = states.get(uid)
        if st and st["type"] in DROP_STATE_TYPES:
            removed_indices.append(i)
            dropped_uuids.append(uid)

    # Mutate plan text — drop lines from highest index down.
    new_lines = list(plan_lines)
    for i in sorted(removed_indices, reverse=True):
        del new_lines[i]
    new_text = "".join(new_lines)

    # Mutate .external-state.json to drop the linear mappings for those uuids.
    state_changes: dict[str, str] = {}
    if state_path.exists():
        state_obj = json.loads(state_path.read_text())
        linear_map = (
            state_obj.get("adapters", {}).get("linear", {}).get("task_to_external", {})
        )
        for task_id, ext_id in list(linear_map.items()):
            if ext_id in dropped_uuids:
                state_changes[task_id] = ext_id
                if not dry_run:
                    del linear_map[task_id]
        if state_changes and not dry_run:
            state_path.write_text(json.dumps(state_obj, indent=2) + "\n")

    if removed_indices and not dry_run:
        plan_path.write_text(new_text)

    return {
        "plan": str(plan_dir),
        "scanned": len(line_to_uuid),
        "removed_lines": [
            {"index": i, "uuid": line_to_uuid[i], "preview": plan_lines[i].rstrip()[:140]}
            for i in sorted(removed_indices)
        ],
        "dropped_uuids": dropped_uuids,
        "state_mapping_dropped": state_changes,
        "dry_run": dry_run,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan_dir", nargs="?", default=str(DEFAULT_PLAN_DIR))
    ap.add_argument("--dry-run", action="store_true", help="print intended changes without writing")
    ap.add_argument("--json", action="store_true", help="emit machine-readable summary")
    args = ap.parse_args()

    result = reconcile_plan(Path(args.plan_dir).resolve(), args.dry_run)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"plan: {result['plan']}")
    print(f"scanned: {result['scanned']} task lines with linear sources")
    print(f"would-remove: {len(result['removed_lines'])}" if result["dry_run"] else f"removed: {len(result['removed_lines'])}")
    for entry in result["removed_lines"]:
        print(f"  - line {entry['index']:3d} | {entry['uuid'][:8]} | {entry['preview']}")
    if result["state_mapping_dropped"]:
        print(f"state-mapping {('would-drop' if result['dry_run'] else 'dropped')}: {len(result['state_mapping_dropped'])}")
        for task_id, ext_id in sorted(result["state_mapping_dropped"].items()):
            print(f"  - {task_id} -> {ext_id[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
