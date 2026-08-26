#!/usr/bin/env python3
"""Read a few exact canonical plan-tree shards with complete provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_store as store  # noqa: E402
import shadow_root_board as board  # noqa: E402
from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE  # noqa: E402


MAX_SELECTORS: Final = 8
MAX_RESULT_BYTES: Final = 128 * 1024
MAX_FIND_QUERY_BYTES: Final = 256
MAX_FIND_MATCHES: Final = 24
MAX_FIND_LINE_BYTES: Final = 4 * 1024
SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_RE: Final = re.compile(
    r"^(?P<tag>[a-z][a-z0-9-]*):(?P<sequence>[0-9]{1,20})$"
)
OBJECT_ERROR_RE: Final = re.compile(
    r"^(?P<reason>referenced object is missing|object digest mismatch): "
    r"expected digest (?P<digest>[0-9a-f]{64}) at .+$"
)
ABSOLUTE_PATH_RE: Final = re.compile(r"(?<![A-Za-z0-9])/(?!/)(?:[^\s]+)")


class ReadError(ValueError):
    """The requested projection cannot be proven without leaking its pointer."""


class SafeArgumentParser(argparse.ArgumentParser):
    """Refuse malformed argv without reflecting a private path or secret."""

    def error(self, message: str) -> None:
        del message
        self.print_usage(sys.stderr)
        self.exit(2, "shadow read: invalid arguments; run `shadow help read`\n")


def parser() -> argparse.ArgumentParser:
    result = SafeArgumentParser(description=__doc__)
    result.add_argument(
        "--entity",
        required=True,
        metavar="ENTITY_ID",
        help="full logical entity id already registered on this computer's board",
    )
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
        "--find",
        action="append",
        default=[],
        metavar="LITERAL",
        help="case-insensitive literal to find in this one complete canonical plan",
    )
    result.add_argument(
        "--expect-root",
        metavar="ROOT_SHA256",
        help="refuse unless PLAN.md still has this exact root digest",
    )
    return result


def _selector_specs(
    rows: list[str], receipts: list[str], finds: list[str]
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
    for query in finds:
        try:
            encoded = query.encode("utf-8")
        except UnicodeError as exc:
            raise store.PlanStoreError("find query must be valid UTF-8") from exc
        if (
            not encoded
            or len(encoded) > MAX_FIND_QUERY_BYTES
            or any(character in query for character in ("\x00", "\n", "\r"))
        ):
            raise store.PlanStoreError(
                f"find query must be 1-{MAX_FIND_QUERY_BYTES} UTF-8 bytes on one line"
            )
        normalized = query.casefold()
        selectors.append((f"find:{normalized}", query, -1))
    if not selectors:
        raise store.PlanStoreError(
            "choose at least one --row, --receipt, or --find selector"
        )
    if len(selectors) > MAX_SELECTORS:
        raise store.PlanStoreError(
            f"choose at most {MAX_SELECTORS} selectors per projection"
        )
    seen: set[str] = set()
    for selector, _, _ in selectors:
        if selector in seen:
            raise store.PlanStoreError(f"duplicate selector {selector}")
        seen.add(selector)
    return selectors


def _bounded_line(line: str) -> tuple[str, bool]:
    encoded = line.encode("utf-8")
    if len(encoded) <= MAX_FIND_LINE_BYTES:
        return line, False
    clipped = encoded[: MAX_FIND_LINE_BYTES - 3]
    while True:
        try:
            return clipped.decode("utf-8") + "...", True
        except UnicodeDecodeError:
            clipped = clipped[:-1]


def _find_result(
    snapshot: store.PlanSnapshot,
    *,
    entity: str,
    entity_locator: str,
    selector: str,
    query: str,
) -> dict[str, Any]:
    content, file_reads, source_bytes = snapshot.materialize_with_metrics()
    try:
        text_content = content.decode("utf-8")
    except UnicodeError as exc:
        raise store.PlanStoreError("canonical logical plan is not valid UTF-8") from exc
    needle = query.casefold()
    match_count = 0
    returned: list[str] = []
    line_was_clipped = False
    for line_number, line in enumerate(text_content.splitlines(), start=1):
        if needle not in line.casefold():
            continue
        match_count += 1
        if len(returned) >= MAX_FIND_MATCHES:
            continue
        bounded, clipped = _bounded_line(line)
        line_was_clipped = line_was_clipped or clipped
        candidate = f"{line_number}:{bounded}\n"
        current_bytes = sum(len(value.encode("utf-8")) for value in returned)
        if current_bytes + len(candidate.encode("utf-8")) > MAX_RESULT_BYTES:
            line_was_clipped = True
            continue
        returned.append(candidate)
    rendered = "".join(returned)
    assert snapshot.root is not None
    return {
        "selector": selector,
        "kind": "find",
        "query": query,
        "content": rendered,
        "match_count": match_count,
        "returned_match_count": len(returned),
        "truncated": match_count > len(returned) or line_was_clipped,
        "complete_scan": True,
        "provenance": {
            "entity_id": entity,
            "entity_locator": entity_locator,
            "selector": selector,
            "root_sha256": snapshot.root_sha256,
            "logical_sha256": snapshot.root["logical_sha256"],
            "scan_bytes": len(content),
            "file_reads": file_reads,
            "source_bytes": source_bytes,
        },
    }


def _provenance(
    value: store.PlanProvenance,
    *,
    entity_id: str,
    entity_locator: str,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_locator": entity_locator,
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


def _safe_error(exc: Exception, entity_locator: str | None = None) -> str:
    """Keep a useful reason while never exporting a machine-private pointer."""
    detail = str(exc)
    matched = OBJECT_ERROR_RE.fullmatch(detail)
    if matched is not None:
        location = entity_locator or "the requested entity"
        return (
            f"{matched.group('reason')}: expected digest "
            f"{matched.group('digest')} in {location}"
        )
    if (
        PRIVATE_PATH_RE.search(detail)
        or SECRET_SHAPE_RE.search(detail)
        or ABSOLUTE_PATH_RE.search(detail)
    ):
        return f"canonical plan read failed for {entity_locator or 'the requested entity'}"
    return detail


def _resolve_entity(entity: str) -> tuple[Path, int, str]:
    if board.ENTITY_ID.fullmatch(entity) is None:
        raise ReadError("entity id must be one full lowercase SHA-256 digest")
    locator = board.public_entity_locator(entity)
    try:
        resolved = board.resolve_entity(entity)
    except board.BoardError as exc:
        raise ReadError(_safe_error(exc, locator)) from None
    if resolved is None:
        raise ReadError("this computer has no Shadow board yet")
    if resolved["plan"] is None:
        raise ReadError(f"{locator} is not registered on this computer")
    return resolved["plan"], resolved["state"]["revision"], locator


def _select(
    snapshot: store.PlanSnapshot,
    selectors: list[tuple[str, str, int | None]],
    *,
    entity: str,
    entity_locator: str,
) -> tuple[list[dict[str, Any]], int]:
    """Read and verify one bounded selector set against one root snapshot."""
    results: list[dict[str, Any]] = []
    result_bytes = 0
    for selector, value, sequence in selectors:
        if sequence == -1:
            try:
                selected_find = _find_result(
                    snapshot,
                    entity=entity,
                    entity_locator=entity_locator,
                    selector=selector,
                    query=value,
                )
            except store.PlanStoreError as exc:
                raise ReadError(_safe_error(exc, entity_locator)) from None
            result_bytes += len(selected_find["content"].encode("utf-8"))
            if result_bytes > MAX_RESULT_BYTES:
                raise store.PlanStoreError(
                    f"selected results exceed the {MAX_RESULT_BYTES}-byte projection limit"
                )
            results.append(selected_find)
            continue
        try:
            selected = (
                snapshot.row(value)
                if sequence is None
                else snapshot.receipt(value, sequence)
            )
        except store.PlanStoreError as exc:
            raise ReadError(_safe_error(exc, entity_locator)) from None
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
                "provenance": _provenance(
                    selected.provenance,
                    entity_id=entity,
                    entity_locator=entity_locator,
                ),
            }
        )
    return results, result_bytes


def project(
    *,
    entity: str,
    rows: list[str],
    receipts: list[str],
    finds: list[str],
    expect_root: str | None,
) -> dict[str, Any]:
    selectors = _selector_specs(rows, receipts, finds)
    if expect_root is not None and SHA256_RE.fullmatch(expect_root) is None:
        raise store.PlanStoreError("expected root must be one lowercase SHA-256 digest")

    plan, board_revision, entity_locator = _resolve_entity(entity)
    try:
        snapshot = board.open_plan(plan)
    except (board.BoardError, store.PlanStoreError) as exc:
        raise ReadError(_safe_error(exc, entity_locator)) from None
    if not snapshot.is_tree:
        raise store.PlanStoreError(
            "bounded projection requires a shadow.plan-tree.v1 root; migrate first"
        )
    if expect_root is not None and snapshot.root_sha256 != expect_root:
        raise store.PlanStoreError("plan root changed; read the new root and retry")

    initial_results, result_bytes = _select(
        snapshot,
        selectors,
        entity=entity,
        entity_locator=entity_locator,
    )

    try:
        verified = board.resolve_entity(entity)
        if verified is None or verified["plan"] is None:
            raise ReadError(f"{entity_locator} is no longer registered")
        if verified["plan"] != plan:
            raise ReadError("registered entity pointer changed during projection")
        current = board.open_plan(plan)
    except ReadError:
        raise
    except (board.BoardError, store.PlanStoreError) as exc:
        raise ReadError(_safe_error(exc, entity_locator)) from None
    if current.root_bytes != snapshot.root_bytes:
        raise ReadError("plan root changed during projection; retry")

    # Content-addressed objects are immutable by contract, but a missing or
    # tampered index/shard must still fail at the final linearization point.
    # Re-run the bounded selectors against the re-opened root and return only
    # that verified pass; the comparison also refuses any nondeterministic
    # projection under identical canonical bytes.
    results, verified_result_bytes = _select(
        current,
        selectors,
        entity=entity,
        entity_locator=entity_locator,
    )
    if results != initial_results or verified_result_bytes != result_bytes:
        raise ReadError("plan objects changed during projection; retry")
    result_bytes = verified_result_bytes

    assert snapshot.root is not None
    payload: dict[str, Any] = {
        "schema": "shadow.plan-projection.v1",
        "plan": entity_locator,
        "entity_id": entity,
        "board_revision": board_revision,
        "board_revision_verified": verified["state"]["revision"],
        "root_sha256": snapshot.root_sha256,
        "logical_sha256": snapshot.root["logical_sha256"],
        "generation": snapshot.root["generation"],
        "result_count": len(results),
        "selection_budget": {
            "selector_limit": MAX_SELECTORS,
            "result_byte_limit": MAX_RESULT_BYTES,
            "result_bytes": result_bytes,
            "verification_passes": 2,
            "aggregate_file_reads": sum(
                item["provenance"]["file_reads"]
                for pass_results in (initial_results, results)
                for item in pass_results
            ),
            "aggregate_source_bytes": sum(
                item["provenance"]["source_bytes"]
                for pass_results in (initial_results, results)
                for item in pass_results
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
            entity=args.entity,
            rows=args.row,
            receipts=args.receipt,
            finds=args.find,
            expect_root=args.expect_root,
        )
    except ValueError as exc:
        print(f"shadow read: {_safe_error(exc)}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
