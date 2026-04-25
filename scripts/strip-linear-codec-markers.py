#!/usr/bin/env python3
"""Strip vidux HTML-comment codec markers from Linear EVE issue descriptions.

Background (2026-04-25):
    The earlier Linear adapter round-tripped vidux metadata (Evidence,
    Investigation, Source, ETA, VidxId, VidxPlan) inside the issue description
    using HTML-comment delimiters:

        <!-- vidux:Evidence -->
        path/to/file.tsx; path/to/other.tsx
        <!-- /vidux:Evidence -->

    Linear renders HTML comments as visible text in its description UI. The
    markers leaked into the rendered view, breaking human readability. We
    dropped the codec from `adapters/linear.py` and moved metadata into the
    per-plan `.external-state.json` sidecar's `task_metadata` dict (keyed by
    VidxId).

What this script does:
    1. Query every issue in the EVE Linear team (paginated `first: 250`).
    2. For each issue with `<!-- vidux:` blocks in description:
        a. Extract every (tag, body) pair into a metadata dict.
        b. Locate the per-plan sidecar at
           `~/Development/strongyes-web/vidux/<VidxPlan>/.external-state.json`
           and merge `task_metadata[VidxId] = {evidence, investigation, source,
           eta, vidx_plan}` into the `linear` adapter section.
        c. Re-render the description as clean human markdown using the same
           sectioning shape as the new `LinearAdapter._render_body()`.
        d. Push the cleaned description back via `issueUpdate`.
    3. Skip issues whose descriptions don't contain any codec markers.

Idempotent: safe to re-run.

Usage:
    # Dry-run first — print diff per issue, no writes.
    python3 scripts/strip-linear-codec-markers.py --dry-run

    # Real run — pushes updates to Linear and writes sidecars.
    python3 scripts/strip-linear-codec-markers.py

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# --- Constants ---------------------------------------------------------------

LINEAR_TOKEN_PATH = Path(os.path.expanduser("~/.config/vidux/linear.token"))
EVE_TEAM_ID = "2f745857-a4df-4f99-93a9-6ac89f9991a2"
LINEAR_ENDPOINT = "https://api.linear.app/graphql"
PAGE_SIZE = 250

# Where strongyes-web vidux sub-plans live. <slug> is VidxPlan tag value.
PLAN_ROOT = Path(os.path.expanduser("~/Development/strongyes-web/vidux"))
SIDECAR_FILENAME = ".external-state.json"

# Codec regex — matches a balanced <!-- vidux:Tag -->...<!-- /vidux:Tag --> block.
_BLOCK_RE = re.compile(
    r"<!--\s*vidux:(?P<tag>[A-Za-z_][A-Za-z0-9_]*)\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/vidux:(?P=tag)\s*-->",
    re.DOTALL,
)
# Cleanup regex — strips orphaned open/close markers if any block is unbalanced.
_ORPHAN_RE = re.compile(
    r"<!--\s*/?vidux:[A-Za-z_][A-Za-z0-9_]*\s*-->",
)
# Quick "is this issue already migrated?" detector.
_HAS_CODEC = re.compile(r"<!--\s*vidux:")


# --- Linear GraphQL helpers --------------------------------------------------


def _load_token() -> str:
    if not LINEAR_TOKEN_PATH.exists():
        raise SystemExit(f"token file not found: {LINEAR_TOKEN_PATH}")
    token = LINEAR_TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit(f"token file empty: {LINEAR_TOKEN_PATH}")
    return token


def _graphql(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    max_attempts: int = 4,
) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    last_err: str | None = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(
            LINEAR_ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": _load_token(),
                "Content-Type": "application/json",
                "User-Agent": "vidux-linear-codec-stripper/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            last_err = f"HTTP {exc.code}: {err_body[:300]}"
            if exc.code == 401:
                raise SystemExit(
                    "Linear returned 401 Unauthorized — token may have rotated. "
                    f"Check {LINEAR_TOKEN_PATH}. Aborting."
                ) from exc
            if exc.code == 429:
                raise SystemExit(f"rate limited: {last_err}") from exc
            if attempt + 1 < max_attempts and exc.code in (502, 503, 504):
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise SystemExit(last_err) from exc
        except urllib.error.URLError as exc:
            last_err = f"URLError: {exc}"
            if attempt + 1 < max_attempts:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise SystemExit(last_err) from exc
        payload = json.loads(raw)
        if payload.get("errors"):
            err_text = json.dumps(payload["errors"])
            raise SystemExit(f"graphql errors: {err_text[:500]}")
        return payload.get("data", {})
    raise SystemExit(f"exhausted retries: {last_err}")


_ISSUES_QUERY = """
query($teamId: ID!, $first: Int!, $after: String) {
  issues(
    filter: { team: { id: { eq: $teamId } } },
    first: $first,
    after: $after,
    orderBy: updatedAt
  ) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      identifier
      title
      description
    }
  }
}
"""


_ISSUE_UPDATE_MUTATION = """
mutation($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue { id identifier }
  }
}
"""


def fetch_all_issues() -> list[dict[str, Any]]:
    """Paginate through every issue on the EVE team."""
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        data = _graphql(
            _ISSUES_QUERY,
            {"teamId": EVE_TEAM_ID, "first": PAGE_SIZE, "after": cursor},
        )
        issues = data.get("issues") or {}
        items.extend(issues.get("nodes", []))
        page = issues.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return items


# --- Codec extraction --------------------------------------------------------


def extract_codec_blocks(description: str) -> tuple[dict[str, str], str]:
    """Return ({tag: body}, prose_with_blocks_stripped).

    Also strips orphaned open/close markers if any block is unbalanced.
    """
    blocks: dict[str, str] = {}
    for m in _BLOCK_RE.finditer(description):
        tag = m.group("tag")
        body = m.group("body").strip()
        if tag in blocks and blocks[tag] != body:
            # Multiple blocks for the same tag — concatenate, preserving order.
            blocks[tag] = blocks[tag] + "\n\n" + body
        else:
            blocks[tag] = body
    # Strip the matched blocks from the description, then any orphan markers.
    stripped = _BLOCK_RE.sub("", description)
    stripped = _ORPHAN_RE.sub("", stripped)
    # Collapse the runs of blank lines we just left behind.
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return blocks, stripped


# --- Sidecar I/O -------------------------------------------------------------


def sidecar_path(vidx_plan: str) -> Path:
    return PLAN_ROOT / vidx_plan / SIDECAR_FILENAME


def load_sidecar(vidx_plan: str) -> dict[str, Any]:
    p = sidecar_path(vidx_plan)
    if not p.exists():
        return {"adapters": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"adapters": {}}


def save_sidecar(vidx_plan: str, state: dict[str, Any]) -> None:
    p = sidecar_path(vidx_plan)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_metadata(
    state: dict[str, Any],
    vidx_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Merge a single VidxId metadata blob into the linear adapter sidecar."""
    adapters = state.setdefault("adapters", {})
    linear = adapters.setdefault("linear", {})
    linear.setdefault("task_to_external", {})
    metadata_dict = linear.setdefault("task_metadata", {})
    existing = metadata_dict.get(vidx_id, {})
    existing.update(metadata)
    metadata_dict[vidx_id] = existing
    return state


# --- Description renderer (mirrors LinearAdapter._render_body shape) --------


def _split_evidence(raw: str) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace("\n", ";").split(";"):
        chunk = chunk.strip().strip("`").strip()
        if chunk:
            parts.append(chunk)
    return parts


def render_clean_description(
    title: str,
    blocks: dict[str, str],
    leftover_prose: str,
) -> str:
    """Build the new clean human-readable description from extracted metadata.

    Mirrors `LinearAdapter._render_body` shape: Purpose / Evidence /
    Investigation / Source / ETA. Sections with no source data are omitted.
    Any leftover prose that wasn't inside a vidux block is appended under
    Purpose so we never silently drop human-written content.
    """
    sections: list[str] = []

    purpose_lines: list[str] = [title.strip()]
    if leftover_prose:
        purpose_lines.append(leftover_prose.strip())
    sections.append("## Purpose\n" + "\n\n".join(p for p in purpose_lines if p))

    evidence = blocks.get("Evidence")
    if evidence:
        items = _split_evidence(evidence)
        if items:
            bullets = "\n".join(f"- {it}" for it in items)
            sections.append(f"## Evidence\n{bullets}")

    investigation = blocks.get("Investigation")
    if investigation:
        sections.append(f"## Investigation\n{investigation.strip()}")

    source = blocks.get("Source")
    if source:
        sections.append(f"## Source\n{source.strip()}")

    eta = blocks.get("ETA")
    if eta:
        eta_clean = eta.strip()
        if not eta_clean.endswith("h"):
            try:
                num = float(eta_clean)
                eta_clean = f"{int(num)}h" if num.is_integer() else f"{num}h"
            except ValueError:
                pass
        sections.append(f"## ETA\n{eta_clean}")

    return "\n\n".join(sections)


# --- Push update -------------------------------------------------------------


def push_clean_description(issue_id: str, new_description: str) -> None:
    data = _graphql(
        _ISSUE_UPDATE_MUTATION,
        {"id": issue_id, "input": {"description": new_description}},
    )
    payload = data.get("issueUpdate") or {}
    if not payload.get("success"):
        raise SystemExit(f"issueUpdate failed for {issue_id}: {data}")


# --- Main migration loop -----------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print before/after per issue without pushing or writing sidecars.",
    )
    args = parser.parse_args()

    issues = fetch_all_issues()
    print(
        f"[stripper] fetched {len(issues)} EVE issues; scanning for codec markers...",
        file=sys.stderr,
    )

    # Group sidecar mutations per vidx_plan so we only write each sidecar once.
    sidecar_mutations: dict[str, dict[str, Any]] = {}

    migrated = 0
    skipped_clean = 0
    skipped_no_vidxid = 0
    skipped_no_plan = 0

    for issue in issues:
        identifier = issue.get("identifier", "?")
        description = issue.get("description") or ""

        if not _HAS_CODEC.search(description):
            skipped_clean += 1
            continue

        original_len = len(description)
        blocks, leftover_prose = extract_codec_blocks(description)

        vidx_id = blocks.pop("VidxId", None)
        vidx_plan = blocks.pop("VidxPlan", None)

        if not vidx_id:
            print(
                f"[skip] {identifier} — codec present but no VidxId tag; "
                f"stripping markers but no sidecar update possible.",
                file=sys.stderr,
            )
            skipped_no_vidxid += 1
        elif not vidx_plan:
            print(
                f"[skip-sidecar] {identifier} (VidxId={vidx_id}) — no VidxPlan tag; "
                f"stripping markers but cannot route to a sidecar.",
                file=sys.stderr,
            )
            skipped_no_plan += 1
        else:
            # Build the per-VidxId metadata blob for the sidecar.
            metadata: dict[str, Any] = {"vidx_plan": vidx_plan}
            if "Evidence" in blocks:
                metadata["evidence"] = _split_evidence(blocks["Evidence"])
                metadata["evidence_raw"] = blocks["Evidence"].strip()
            if "Investigation" in blocks:
                metadata["investigation"] = blocks["Investigation"].strip()
            if "Source" in blocks:
                metadata["source"] = blocks["Source"].strip()
            if "ETA" in blocks:
                eta_raw = blocks["ETA"].strip().rstrip("h")
                try:
                    metadata["eta"] = float(eta_raw)
                except ValueError:
                    metadata["eta_raw"] = blocks["ETA"].strip()

            # Stash the mutation for this plan; we'll commit after the loop.
            state = sidecar_mutations.get(vidx_plan)
            if state is None:
                state = load_sidecar(vidx_plan)
                sidecar_mutations[vidx_plan] = state
            merge_metadata(state, vidx_id, metadata)

        # Re-render the clean description (reusing original title).
        title = issue.get("title") or identifier
        new_description = render_clean_description(title, blocks, leftover_prose)
        new_len = len(new_description)
        delta = original_len - new_len

        if args.dry_run:
            print(
                f"\n=== {identifier} (VidxId={vidx_id} / VidxPlan={vidx_plan}) ===",
                file=sys.stderr,
            )
            print(f"--- BEFORE ({original_len} chars) ---", file=sys.stderr)
            print(description[:600] + ("..." if original_len > 600 else ""), file=sys.stderr)
            print(f"--- AFTER ({new_len} chars) ---", file=sys.stderr)
            print(new_description[:600] + ("..." if new_len > 600 else ""), file=sys.stderr)
        else:
            push_clean_description(issue["id"], new_description)
            print(
                f"[migrated] {identifier} — extracted {len(blocks)} fields, "
                f"stripped {delta} chars",
                file=sys.stderr,
            )
        migrated += 1

    # Commit sidecar mutations (skip in dry-run).
    sidecars_written = 0
    if args.dry_run:
        for plan, state in sidecar_mutations.items():
            metadata = state.get("adapters", {}).get("linear", {}).get("task_metadata", {})
            print(
                f"[dry-run sidecar] {plan} — would write {len(metadata)} task_metadata entries",
                file=sys.stderr,
            )
    else:
        for plan, state in sidecar_mutations.items():
            save_sidecar(plan, state)
            sidecars_written += 1
            metadata = state.get("adapters", {}).get("linear", {}).get("task_metadata", {})
            print(
                f"[sidecar] {plan} — wrote {len(metadata)} task_metadata entries",
                file=sys.stderr,
            )

    # Final summary.
    print("", file=sys.stderr)
    print(f"=== summary ===", file=sys.stderr)
    print(f"  total queried:        {len(issues)}", file=sys.stderr)
    print(f"  migrated:             {migrated}", file=sys.stderr)
    print(f"  skipped (clean):      {skipped_clean}", file=sys.stderr)
    print(f"  skipped (no VidxId):  {skipped_no_vidxid}", file=sys.stderr)
    print(f"  skipped (no Plan):    {skipped_no_plan}", file=sys.stderr)
    print(f"  sidecars written:     {sidecars_written}", file=sys.stderr)
    print(f"  dry-run:              {args.dry_run}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
