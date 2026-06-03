#!/usr/bin/env python3
"""Emit the M24 honest-deferrals firewall for the local operator stack.

The firewall is deliberately read-only: it proves that tempting follow-on
surfaces are tracked in canonical plans with explicit re-entry conditions, then
keeps them out of the current FirstBite trust/drift slice.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SCRIPT_NAME = "vidux-local-operator-deferrals.py"


FIREWALL_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "moussey_mobile_pwa",
        "surface": "Moussey mobile PWA quick wins and installable shell",
        "gate": "owner_gated",
        "canonical_refs": [
            {
                "plan": "projects/connect-the-fleet/PLAN.md",
                "rows": ["C-7", "C-17", "C-18", "C-19", "C-20"],
            },
            {
                "plan": "projects/moussey-mobile-operator/PLAN.md",
                "rows": ["M-R66", "M-R68", "M-R74"],
            },
        ],
        "summary": "Mobile PWA code is a M1 Pro Claude lane, not this FirstBite trust slice.",
        "re_entry": [
            "M1 Pro Claude takes the code PR for C-7 or bundles C-17..C-20.",
            "Proof returns to connect-the-fleet with Nicole-visible screenshots or gate measurements.",
        ],
        "non_claim": "Does not claim mobile PWA code shipped or Nicole installed the tile.",
    },
    {
        "id": "tailscale_remote_lan",
        "surface": "Tailscale remote LAN exposure",
        "gate": "leo_keyboard_gated",
        "canonical_refs": [
            {"plan": "projects/connect-the-fleet/PLAN.md", "rows": ["C-16", "C-19", "C-24"]},
            {"plan": "projects/moussey-mobile-operator/PLAN.md", "rows": ["M-R6"]},
        ],
        "summary": "Tailnet exposure waits for Leo keyboard work and enforced chat auth.",
        "re_entry": [
            "M-R6/MOUSSEY_CHAT_AUTH is in enforce mode before any 0.0.0.0 exposure.",
            "Leo runs the NET-1..NET-4 ritual and saves MagicDNS/HTTPS/LTE proof.",
        ],
        "non_claim": "Does not claim tailnet, MagicDNS, HTTPS, or LTE tap-to-talk is live.",
    },
    {
        "id": "nicole_device_handoffs",
        "surface": "Nicole bookmark, peer-name, iPhone OS, and install handoff",
        "gate": "human_device_gated",
        "canonical_refs": [
            {
                "plan": "projects/connect-the-fleet/PLAN.md",
                "rows": ["C-3", "C-4", "C-21", "C-22", "C-24"],
            }
        ],
        "summary": "Nicole-facing handoffs require a human/device moment and are not agent-autonomous.",
        "re_entry": [
            "Leo or Nicole changes the live bookmark or peer-name on Nicole-owned hardware.",
            "Studio records the iOS version and one-page handoff evidence after the human action.",
        ],
        "non_claim": "Does not claim messages were sent, bookmarks changed, or Nicole devices touched.",
    },
    {
        "id": "fleet_state_and_secret_rotation",
        "surface": "Fleet state snapshots and unified secret-rotation runbook",
        "gate": "followup_plan_or_owner_gated",
        "canonical_refs": [
            {"plan": "projects/connect-the-fleet/PLAN.md", "rows": ["C-11", "C-14", "C-15"]},
        ],
        "summary": "Fleet-state implementation and MOU-36 runbook stay as explicit follow-ups.",
        "re_entry": [
            "Open MOU-36 in the Moussey plan before changing secret-rotation behavior.",
            "M1 Pro Claude owns fleet-state app code; per-surface owners publish seed snapshots after C-14.",
        ],
        "non_claim": "Does not claim fleet-state CLI/endpoints or secret rotation are implemented.",
    },
    {
        "id": "voice_streaming_and_router",
        "surface": "Live voice streaming, fast local brain, TTS, and router v2",
        "gate": "followup_not_current_stack_blocker",
        "canonical_refs": [
            {
                "plan": "projects/connect-the-fleet/PLAN.md",
                "rows": ["C-25", "C-30", "C-31", "C-32", "C-33", "C-34", "C-35"],
            }
        ],
        "summary": "Voice has its own evidence chain and is not required to finish FirstBite trust/drift.",
        "re_entry": [
            "Resume from the connect-the-fleet Phase 8/9 rows with real browser or live-device proof.",
            "Keep voice performance claims tied to current evidence, not old soak summaries.",
        ],
        "non_claim": "Does not claim flagship streaming, router v2, or live-device voice is complete.",
    },
    {
        "id": "worker_pool_embeddings_autodispatch",
        "surface": "Worker pool, embeddings, and autonomous dispatch promotion",
        "gate": "deferred_quarter",
        "canonical_refs": [
            {"plan": "projects/firstbite-local-ci-mega/PLAN.md", "rows": ["M22", "M23", "M24"]},
        ],
        "summary": "Autodispatch stays closed until the trust/drift layer has explicit promotion approval.",
        "re_entry": [
            "M21/M22/M23 warnings are reduced and the operator approves a separate dispatch-promotion row.",
            "A future plan names worker authority, budget, rollback, and proof requirements before code runs.",
        ],
        "non_claim": "Does not dispatch workers, write embeddings, or promote observe-only automation.",
    },
]


def _find_row(plan_text: str, row_id: str) -> dict[str, Any]:
    needle = f"{row_id}:"
    alt = f"{row_id} /"
    for index, line in enumerate(plan_text.splitlines(), start=1):
        if needle in line or alt in line:
            lowered = line.lower()
            status = "unknown"
            for candidate in ("completed", "in_progress", "pending", "blocked", "deferred-quarter"):
                if f"[{candidate}" in lowered or f"[{candidate}]" in lowered:
                    status = candidate
                    break
            return {"row": row_id, "found": True, "line": index, "status": status}
    return {"row": row_id, "found": False, "line": None, "status": "missing"}


def _resolve_refs(repo_root: Path, refs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    resolved: list[dict[str, Any]] = []
    missing: list[str] = []
    for ref in refs:
        rel_plan = str(ref["plan"])
        plan_path = repo_root / rel_plan
        plan_result: dict[str, Any] = {
            "plan": str(plan_path),
            "plan_relative": rel_plan,
            "exists": plan_path.exists(),
            "rows": [],
        }
        if not plan_path.exists():
            missing.append(f"{rel_plan}:plan")
            for row in ref["rows"]:
                plan_result["rows"].append({"row": row, "found": False, "line": None, "status": "missing"})
                missing.append(f"{rel_plan}:{row}")
            resolved.append(plan_result)
            continue
        text = plan_path.read_text(encoding="utf-8")
        for row in ref["rows"]:
            row_result = _find_row(text, str(row))
            plan_result["rows"].append(row_result)
            if not row_result["found"]:
                missing.append(f"{rel_plan}:{row}")
        resolved.append(plan_result)
    return resolved, missing


def build_payload(repo_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    all_missing: list[str] = []

    for entry in FIREWALL_ENTRIES:
        refs, missing = _resolve_refs(repo_root, entry["canonical_refs"])
        status = "blocked" if missing else "ready"
        if missing:
            all_missing.extend([f"{entry['id']}:{item}" for item in missing])
        entries.append(
            {
                "id": entry["id"],
                "surface": entry["surface"],
                "gate": entry["gate"],
                "status": status,
                "summary": entry["summary"],
                "canonical_refs": refs,
                "re_entry": entry["re_entry"],
                "non_claim": entry["non_claim"],
            }
        )
        checks.append(
            {
                "id": entry["id"],
                "status": status,
                "summary": entry["summary"] if status == "ready" else f"missing canonical refs: {', '.join(missing)}",
            }
        )

    overall_status = "blocked" if all_missing else "ready"
    ready_entry_count = sum(1 for entry in entries if entry["status"] == "ready")
    blocked_entry_count = len(entries) - ready_entry_count
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SCRIPT_NAME,
        "mode": "honest_deferrals_firewall",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "status": overall_status,
        "summary": (
            f"{overall_status}: {ready_entry_count} tracked surface group(s), "
            f"{blocked_entry_count} blocked surface group(s), {len(all_missing)} missing canonical reference(s)"
            if all_missing
            else f"{overall_status}: {len(entries)} deferred surface group(s) have canonical owners and re-entry gates"
        ),
        "checks": checks,
        "entries": entries,
        "global_non_claims": [
            "This firewall did not edit Moussey app code.",
            "This firewall did not touch Nicole-owned devices or send human messages.",
            "This firewall did not expose services over Tailscale or public networking.",
            "This firewall did not execute local-CI lanes or dispatch workers.",
            "This firewall does not mark deferred rows as product-complete.",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Local Operator Deferrals Firewall - {payload['generated_at']}",
        "",
        f"Status: `{payload['status']}`",
        "",
        payload["summary"],
        "",
        "## Deferred Surfaces",
        "",
    ]
    for entry in payload["entries"]:
        lines.extend(
            [
                f"### {entry['surface']}",
                "",
                f"- `id`: `{entry['id']}`",
                f"- `gate`: `{entry['gate']}`",
                f"- `status`: `{entry['status']}`",
                f"- `summary`: {entry['summary']}",
                f"- `non_claim`: {entry['non_claim']}",
                "- `canonical_refs`:",
            ]
        )
        for ref in entry["canonical_refs"]:
            row_bits = []
            for row in ref["rows"]:
                suffix = f":{row['line']}" if row["line"] else ""
                row_bits.append(f"{row['row']}[{row['status']}{suffix}]")
            lines.append(f"  - `{ref['plan']}` -> {', '.join(row_bits)}")
        lines.append("- `re_entry`:")
        for condition in entry["re_entry"]:
            lines.append(f"  - {condition}")
        lines.append("")

    lines.extend(["## Global Non-Claims", ""])
    for item in payload["global_non_claims"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit the read-only M24 deferrals firewall.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Vidux repo root. Defaults to the script's parent repo.",
    )
    parser.add_argument("--markdown", action="store_true", help="Emit markdown instead of JSON.")
    parser.add_argument("--write-json", type=Path, help="Write JSON payload to this path.")
    parser.add_argument("--write-markdown", type=Path, help="Write markdown payload to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args.repo_root.resolve())

    if args.write_json:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_markdown:
        args.write_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.write_markdown.write_text(_markdown(payload), encoding="utf-8")

    if args.markdown:
        print(_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
