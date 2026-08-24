#!/usr/bin/env python3
"""Read a few exact canonical plan-tree shards with complete provenance."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_store as store  # noqa: E402


MAX_SELECTORS: Final = 8
MAX_RESULT_BYTES: Final = 128 * 1024
SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_RE: Final = re.compile(
    r"^(?P<tag>[a-z][a-z0-9-]*):(?P<sequence>[0-9]+)$"
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("plan", type=Path, help="absolute path to one PLAN.md tree root")
    result.add_argument(
        "--row",
        action="append",
        default=[],
        metavar="~ID",
        help="exact current row selector; repeatable",
    )
    result.add_argument(
        "--receipt",
        action="append",
        default=[],
        metavar="TAG:N",
        help="exact zero-based tag receipt selector; repeatable",
    )
    result.add_argument(
        "--expect-root",
        metavar="ROOT_SHA256",
        help="refuse unless PLAN.md still has this exact root digest",
    )
    return result


def _selector_specs(
    rows: list[str], receipts: list[str]
) -> list[tuple[str, str, int | None]]:
    selectors: list[tuple[str, str, int | None]] = [
        (f"row:{row}", row, None) for row in rows
    ]
    for receipt in receipts:
        match = RECEIPT_RE.fullmatch(receipt)
        if match is None:
            raise store.PlanStoreError(
                "receipt selector must be TAG:N with a non-negative sequence"
            )
        tag = match.group("tag")
        sequence = int(match.group("sequence"))
        selectors.append((f"tag:{tag}:{sequence}", tag, sequence))
    if not selectors:
        raise store.PlanStoreError("choose at least one --row or --receipt selector")
    if len(selectors) > MAX_SELECTORS:
        raise store.PlanStoreError(
            f"choose at most {MAX_SELECTORS} exact selectors per projection"
        )
    seen: set[str] = set()
    for selector, _, _ in selectors:
        if selector in seen:
            raise store.PlanStoreError(f"duplicate selector {selector}")
        seen.add(selector)
    return selectors


def _provenance(value: store.PlanProvenance) -> dict[str, Any]:
    return {
        "selector": value.selector,
        "root_sha256": value.root_sha256,
        "index_sha256": list(value.index_sha256),
        "shard_sha256": value.shard_sha256,
        "shard_bytes": value.shard_bytes,
        "catalog_key": value.catalog_key,
        "result_start": value.result_start,
        "result_end": value.result_end,
        "result_sha256": value.result_sha256,
        "file_reads": value.file_reads,
        "source_bytes": value.source_bytes,
    }


def project(
    plan: Path,
    *,
    rows: list[str],
    receipts: list[str],
    expect_root: str | None,
) -> dict[str, Any]:
    selectors = _selector_specs(rows, receipts)
    if not plan.is_absolute():
        raise store.PlanStoreError("plan path must be absolute")
    if expect_root is not None and SHA256_RE.fullmatch(expect_root) is None:
        raise store.PlanStoreError("expected root must be one lowercase SHA-256 digest")

    snapshot = store.PlanSnapshot.open(Path(os.path.abspath(plan)))
    if not snapshot.is_tree:
        raise store.PlanStoreError(
            "bounded projection requires a shadow.plan-tree.v1 root; migrate first"
        )
    if expect_root is not None and snapshot.root_sha256 != expect_root:
        raise store.PlanStoreError("plan root changed; read the new root and retry")

    results: list[dict[str, Any]] = []
    result_bytes = 0
    for selector, value, sequence in selectors:
        selected = (
            snapshot.row(value)
            if sequence is None
            else snapshot.receipt(value, sequence)
        )
        if selected.provenance.selector != selector:
            raise store.PlanStoreError("selected result provenance does not match request")
        result_bytes += len(selected.content)
        if result_bytes > MAX_RESULT_BYTES:
            raise store.PlanStoreError(
                f"selected results exceed the {MAX_RESULT_BYTES}-byte projection limit"
            )
        try:
            content = selected.content.decode("utf-8")
        except UnicodeError as exc:
            raise store.PlanStoreError("selected plan shard is not valid UTF-8") from exc
        results.append(
            {
                "selector": selector,
                "content": content,
                "provenance": _provenance(selected.provenance),
            }
        )

    assert snapshot.root is not None
    payload: dict[str, Any] = {
        "schema": "shadow.plan-projection.v1",
        "plan": "PLAN.md",
        "root_sha256": snapshot.root_sha256,
        "logical_sha256": snapshot.root["logical_sha256"],
        "generation": snapshot.root["generation"],
        "result_count": len(results),
        "selection_budget": {
            "selector_limit": MAX_SELECTORS,
            "result_byte_limit": MAX_RESULT_BYTES,
            "result_bytes": result_bytes,
            "aggregate_file_reads": sum(
                item["provenance"]["file_reads"] for item in results
            ),
            "aggregate_source_bytes": sum(
                item["provenance"]["source_bytes"] for item in results
            ),
        },
        "results": results,
    }
    payload["projection_sha256"] = store.digest_bytes(store.canonical_json(payload))
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = project(
            args.plan,
            rows=args.row,
            receipts=args.receipt,
            expect_root=args.expect_root,
        )
    except store.PlanStoreError as exc:
        print(f"shadow read: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
