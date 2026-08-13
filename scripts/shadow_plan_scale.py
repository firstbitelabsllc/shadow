"""Measure Shadow plan lookup cost without creating another authority.

The board and PLAN bytes are read-only inputs. Reports contain public entity
locators, source digests, aggregate timings, and result digests—never plan text
or private filesystem paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import statistics
import sys
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_grammar as _grammar  # noqa: E402
import shadow_root_board as _board  # noqa: E402


_AMP_SPEC = importlib.util.spec_from_file_location(
    "shadow_plan_scale_amp", ROOT / "scripts" / "shadow-amp.py"
)
assert _AMP_SPEC and _AMP_SPEC.loader
_amp = importlib.util.module_from_spec(_AMP_SPEC)
sys.modules.setdefault(_AMP_SPEC.name, _amp)
_AMP_SPEC.loader.exec_module(_amp)


SCHEMA = "shadow.plan-scale-baseline.v1"
ARCHIVE_RE = re.compile(
    r"^- Archived milestone: \[[^]]+\]\((?P<path>[^)]+)\)"
)


class PlanScaleError(ValueError):
    """The benchmark input changed, is malformed, or cannot answer its corpus."""


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _distribution(values: list[float | int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "max": 0}
    numeric = [float(value) for value in values]
    return {
        "count": len(values),
        "min": round(min(numeric), 6),
        "p50": round(_percentile(numeric, 0.50), 6),
        "p95": round(_percentile(numeric, 0.95), 6),
        "max": round(max(numeric), 6),
    }


def _timing(action: Callable[[], object], repeats: int) -> dict[str, float | int]:
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "runs": repeats,
        "p50": round(_percentile(samples, 0.50), 6),
        "p95": round(_percentile(samples, 0.95), 6),
    }


def _load_board(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        content = path.read_bytes()
        payload = json.loads(content)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanScaleError("board is unreadable or malformed") from exc
    if not isinstance(payload, dict) or payload.get("schema") != _board.SCHEMA:
        raise PlanScaleError("board schema is not supported")
    if not isinstance(payload.get("revision"), int):
        raise PlanScaleError("board revision is missing")
    if not isinstance(payload.get("entities"), list) or not isinstance(
        payload.get("claims"), list
    ):
        raise PlanScaleError("board entities or claims are malformed")
    return payload, content


def _plan_bytes(entity: dict[str, Any]) -> tuple[Path, bytes]:
    raw = entity.get("plan")
    if not isinstance(raw, str) or not raw:
        raise PlanScaleError("entity plan locator is missing")
    path = Path(raw)
    try:
        return path, _board.read_plan_bytes(path)
    except _board.BoardError as exc:
        raise PlanScaleError("entity plan is not a bounded regular PLAN.md") from exc


def _entity_ref(entity: dict[str, Any]) -> str:
    identity = entity.get("id")
    if not isinstance(identity, str) or _board.ENTITY_ID.fullmatch(identity) is None:
        raise PlanScaleError("entity id is malformed")
    return f"entity@{identity[:12]}/PLAN.md"


def _source(ref: str, content: bytes) -> dict[str, str | int]:
    return {"ref": ref, "sha256": _sha256(content), "bytes": len(content)}


def _text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeError as exc:
        raise PlanScaleError("plan is not valid UTF-8") from exc


def _row_line(text: str, row_id: str) -> str:
    matches = [
        line
        for line in text.splitlines()
        if (match := _grammar.ROW_RE.fullmatch(line)) is not None
        and match.group("id") == row_id
    ]
    if len(matches) != 1:
        raise PlanScaleError(f"resume row is absent or duplicated: {row_id}")
    return matches[0]


def _latest_line(text: str, section: str, token: str) -> str:
    matches = [
        line for line in _board.section_lines(text, section)
        if line.startswith("- ") and token in line
    ]
    return matches[-1] if matches else ""


def _first_contradiction(text: str) -> str:
    return next(
        (
            line for line in _board.section_lines(text, "Contradictions")
            if line.startswith("- ")
        ),
        "",
    )


def _archive_paths(text: str) -> list[str]:
    return [
        match.group("path")
        for line in text.splitlines()
        if (match := ARCHIVE_RE.match(line)) is not None
    ]


def _read_archive(plan: Path, relative: str) -> tuple[Path, bytes, str] | None:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise PlanScaleError("archive link escapes its plan directory")
    root = Path(os.path.realpath(plan.parent))
    candidate = root / relative_path
    try:
        candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PlanScaleError("archive link escapes its plan directory") from exc
    cursor = root
    try:
        for part in relative_path.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise PlanScaleError("archive link crosses a symlink")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(candidate, flags)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise PlanScaleError("archive link is not a regular file")
            content = stream.read(_board.MAX_PLAN_BYTES + 1)
        if len(content) > _board.MAX_PLAN_BYTES:
            raise PlanScaleError("archive exceeds the bounded size limit")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PlanScaleError("archive link is not a bounded regular file") from exc
    return candidate, content, relative


def _safe_archive(plan: Path, text: str) -> tuple[Path, bytes, str] | None:
    for relative in _archive_paths(text):
        if archive := _read_archive(plan, relative):
            return archive
    return None


def _selected_entities(
    board: dict[str, Any], projects: tuple[str, ...]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for project in projects:
        candidates: list[tuple[int, str, dict[str, Any]]] = []
        for entity in board["entities"]:
            if not isinstance(entity, dict) or entity.get("project") != project:
                continue
            _, content = _plan_bytes(entity)
            candidates.append((len(content), str(entity.get("id", "")), entity))
        if not candidates:
            raise PlanScaleError(f"board has no readable entity for project: {project}")
        candidates.sort(key=lambda item: (-item[0], item[1]))
        selected.append(candidates[0][2])
    return selected


def _profile_plan(entity: dict[str, Any], repeats: int) -> dict[str, Any]:
    path, content = _plan_bytes(entity)
    text = _text(content)
    parsed = _amp._parse(text)
    budget = _board.hot_plan_budget(content)
    archive_paths = _archive_paths(text)
    archive_present = sum(
        1 for relative in archive_paths if _read_archive(path, relative) is not None
    )
    return {
        "project": entity["project"],
        "entity": _entity_ref(entity),
        "sha256": _sha256(content),
        "bytes": len(content),
        "lines": len(text.splitlines()),
        "task_rows": budget["task_rows"],
        "milestones": budget["milestones"],
        "progress_lines": sum(
            1 for line in _board.section_lines(text, "Progress") if line.startswith("- ")
        ),
        "contradictions": len(parsed["contradictions"]),
        "archive_links": len(archive_paths),
        "missing_archive_links": len(archive_paths) - archive_present,
        "resume": entity.get("resume"),
        "parse_ms": _timing(lambda: _amp._parse(text), repeats),
        "read_parse_ms": _timing(
            lambda: _amp._parse(_text(_board.read_plan_bytes(path))), repeats
        ),
    }


def _query_report(
    case_id: str,
    kind: str,
    action: Callable[[], tuple[str, int, int, list[dict[str, str | int]]]],
    repeats: int,
) -> dict[str, Any]:
    result, source_bytes, hops, sources = action()
    timing = _timing(action, repeats)
    return {
        "case_id": case_id,
        "kind": kind,
        "found": bool(result),
        "hops": hops,
        "source_bytes": source_bytes,
        "result_bytes": len(result.encode("utf-8")),
        "result_sha256": _sha256(result.encode("utf-8")),
        "latency_ms": timing,
        "sources": sources,
    }


def _plan_action(
    entity: dict[str, Any],
    selector: Callable[[str], str],
) -> Callable[[], tuple[str, int, int, list[dict[str, str | int]]]]:
    def run() -> tuple[str, int, int, list[dict[str, str | int]]]:
        _, content = _plan_bytes(entity)
        result = selector(_text(content))
        return result, len(content), 1, [_source(_entity_ref(entity), content)]

    return run


def _owner_action(
    board_path: Path, entity: dict[str, Any]
) -> Callable[[], tuple[str, int, int, list[dict[str, str | int]]]]:
    def run() -> tuple[str, int, int, list[dict[str, str | int]]]:
        board, board_content = _load_board(board_path)
        _, plan_content = _plan_bytes(entity)
        resume = entity.get("resume")
        if not isinstance(resume, str):
            raise PlanScaleError("entity resume row is missing")
        _row_line(_text(plan_content), resume)
        owners = sorted(
            claim["owner"]
            for claim in board["claims"]
            if isinstance(claim, dict)
            and claim.get("entity") == entity["id"]
            and claim.get("row") == resume
            and isinstance(claim.get("owner"), str)
        )
        result = f"{resume}:{','.join(owners) if owners else 'unclaimed'}"
        sources = [
            _source(f"board@{board['revision']}", board_content),
            _source(_entity_ref(entity), plan_content),
        ]
        return result, len(board_content) + len(plan_content), 2, sources

    return run


def _history_action(
    entity: dict[str, Any]
) -> Callable[[], tuple[str, int, int, list[dict[str, str | int]]]]:
    def run() -> tuple[str, int, int, list[dict[str, str | int]]]:
        plan, plan_content = _plan_bytes(entity)
        archive = _safe_archive(plan, _text(plan_content))
        if archive is None:
            result = next(
                (
                    line for line in _board.section_lines(_text(plan_content), "Progress")
                    if line.startswith("- ")
                ),
                "",
            )
            return result, len(plan_content), 1, [_source(_entity_ref(entity), plan_content)]
        _, archive_content, relative = archive
        result = next(
            (line for line in _text(archive_content).splitlines() if line.strip()), ""
        )
        archive_ref = _entity_ref(entity).removesuffix("/PLAN.md") + f"/{relative}"
        sources = [
            _source(_entity_ref(entity), plan_content),
            _source(archive_ref, archive_content),
        ]
        return result, len(plan_content) + len(archive_content), 2, sources

    return run


def _cross_entity_action(
    board_path: Path, entities: list[dict[str, Any]]
) -> Callable[[], tuple[str, int, int, list[dict[str, str | int]]]]:
    def run() -> tuple[str, int, int, list[dict[str, str | int]]]:
        board, board_content = _load_board(board_path)
        results: list[str] = []
        sources = [_source(f"board@{board['revision']}", board_content)]
        source_bytes = len(board_content)
        for entity in entities:
            _, content = _plan_bytes(entity)
            resume = entity.get("resume")
            if not isinstance(resume, str):
                raise PlanScaleError("entity resume row is missing")
            line = _row_line(_text(content), resume)
            results.append(f"{entity['project']}:{resume}:{_sha256(line.encode('utf-8'))}")
            sources.append(_source(_entity_ref(entity), content))
            source_bytes += len(content)
        return "\n".join(results), source_bytes, len(entities) + 1, sources

    return run


def benchmark_board(
    board_path: Path,
    *,
    projects: tuple[str, ...],
    repeats: int = 31,
) -> dict[str, Any]:
    """Benchmark the largest registered entity for each requested project."""
    if not projects:
        raise PlanScaleError("at least one project is required")
    if repeats < 1 or repeats > 10_000:
        raise PlanScaleError("repeats must be between 1 and 10000")
    board_path = Path(board_path)
    board, board_content = _load_board(board_path)
    entities = _selected_entities(board, projects)
    profiles = [_profile_plan(entity, repeats) for entity in entities]
    layout_comparisons = []
    for entity in entities:
        _, content = _plan_bytes(entity)
        comparison = compare_layouts(content)
        comparison["project"] = entity["project"]
        comparison["entity"] = _entity_ref(entity)
        layout_comparisons.append(comparison)

    candidate_queries: list[dict[str, Any]] = []
    for entity in entities:
        resume = entity.get("resume")
        if not isinstance(resume, str):
            raise PlanScaleError("entity resume row is missing")
        prefix = f"{entity['project']}-{entity['id'][:8]}"
        candidate_queries.extend(
            (
                _query_report(
                    f"{prefix}-current", "current_work",
                    _plan_action(entity, lambda text, row=resume: _row_line(text, row)),
                    repeats,
                ),
                _query_report(
                    f"{prefix}-decision", "decision",
                    _plan_action(entity, lambda text: _latest_line(text, "Progress", " DECISION ")),
                    repeats,
                ),
                _query_report(
                    f"{prefix}-contradiction", "contradiction",
                    _plan_action(entity, _first_contradiction), repeats,
                ),
                _query_report(
                    f"{prefix}-proof", "proof",
                    _plan_action(entity, lambda text: _latest_line(text, "Progress", " PROOF ")),
                    repeats,
                ),
                _query_report(
                    f"{prefix}-history", "history", _history_action(entity), repeats,
                ),
            )
        )
    candidate_queries.append(
        _query_report("portfolio-owner", "owner", _owner_action(board_path, entities[0]), repeats)
    )
    candidate_queries.append(
        _query_report(
            "portfolio-current-work", "cross_entity",
            _cross_entity_action(board_path, entities), repeats,
        )
    )

    queries = [query for query in candidate_queries if query["found"]]
    excluded_queries = [
        {
            "case_id": query["case_id"],
            "kind": query["kind"],
            "reason": "no source-backed result in the frozen input",
        }
        for query in candidate_queries
        if not query["found"]
    ]
    return {
        "schema": SCHEMA,
        "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "board": {
            "revision": board["revision"],
            "sha256": _sha256(board_content),
            "bytes": len(board_content),
        },
        "projects": list(projects),
        "repeats": repeats,
        "plans": profiles,
        "layout_comparisons": layout_comparisons,
        "queries": queries,
        "excluded_queries": excluded_queries,
        "distributions": {
            "plan_bytes": _distribution([profile["bytes"] for profile in profiles]),
            "parse_p95_ms": _distribution(
                [profile["parse_ms"]["p95"] for profile in profiles]
            ),
            "query_source_bytes": _distribution(
                [query["source_bytes"] for query in queries]
            ),
            "query_p95_ms": _distribution(
                [query["latency_ms"]["p95"] for query in queries]
            ),
            "query_hops": _distribution([query["hops"] for query in queries]),
        },
    }


def _shard_boundaries(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return exact line boundaries for sections, milestones, and log items."""
    boundaries: list[tuple[int, str, str]] = [(0, "preamble", "")]
    section = ""
    for index, line in enumerate(lines):
        if line.startswith("## "):
            section = line[3:].strip()
            boundaries.append((index, "section", section))
            continue
        if section == "Tasks" and line.startswith("### "):
            boundaries.append((index, "milestone", section))
            continue
        if (
            section in {"Progress", "Deferred", "Contradictions"}
            and line.startswith("- ")
        ):
            boundaries.append((index, "item", section))
    by_index: dict[int, tuple[int, str, str]] = {}
    for boundary in boundaries:
        # A canonical section or milestone boundary is more useful than the
        # synthetic preamble boundary when a file starts directly on one.
        by_index[boundary[0]] = boundary
    return [by_index[index] for index in sorted(by_index)]


def _shard_tags(section: str, content: bytes) -> list[str]:
    text = _text(content)
    tags: set[str] = set()
    if section == "Progress":
        if " PROOF " in text:
            tags.add("proof")
        if " DECISION " in text:
            tags.add("decision")
        if " LESSON " in text:
            tags.add("lesson")
    if section == "Contradictions":
        tags.add("contradiction")
    if section == "Deferred":
        tags.add("deferred")
    if section == "Brief":
        tags.add("brief")
    if section == "Tasks" and _grammar.HASH_RE.search(text):
        tags.add("task")
    return sorted(tags)


def sharded_layout(content: bytes) -> dict[str, Any]:
    """Split exact PLAN bytes into a manifest-addressed, lossless virtual tree.

    This is a comparison model, not a migration. The manifest orders and
    digests canonical shards; tags and row IDs route reads but never copy task
    state, proof, or prose.
    """
    text = _text(content)
    lines = text.splitlines(keepends=True)
    boundaries = _shard_boundaries(lines)
    shards: list[dict[str, Any]] = []
    for position, (start, kind, section) in enumerate(boundaries):
        end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        body = "".join(lines[start:end]).encode("utf-8")
        if not body:
            continue
        digest = _sha256(body)
        row_ids = sorted(set(_grammar.HASH_RE.findall(_text(body))))
        shards.append(
            {
                "id": f"s{len(shards):04d}",
                "kind": kind,
                "section": section,
                "sha256": digest,
                "bytes": len(body),
                "row_ids": row_ids,
                "tags": _shard_tags(section, body),
                "content": body,
            }
        )
    manifest_payload = {
        "schema": "shadow.plan-shards.v1",
        "source_sha256": _sha256(content),
        "source_bytes": len(content),
        "shards": [
            {key: value for key, value in shard.items() if key != "content"}
            for shard in shards
        ],
    }
    manifest = json.dumps(
        manifest_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "source_sha256": manifest_payload["source_sha256"],
        "source_bytes": len(content),
        "manifest": manifest,
        "manifest_sha256": _sha256(manifest),
        "shards": shards,
    }


def _validate_layout(layout: dict[str, Any]) -> dict[str, Any]:
    try:
        manifest = json.loads(layout["manifest"])
        shards = layout["shards"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PlanScaleError("shard layout is malformed") from exc
    if manifest.get("schema") != "shadow.plan-shards.v1":
        raise PlanScaleError("shard manifest schema is not supported")
    entries = manifest.get("shards")
    if not isinstance(entries, list) or not isinstance(shards, list) or len(entries) != len(shards):
        raise PlanScaleError("shard manifest and content set disagree")
    for entry, shard in zip(entries, shards, strict=True):
        if not isinstance(entry, dict) or not isinstance(shard, dict):
            raise PlanScaleError("shard entry is malformed")
        content = shard.get("content")
        if not isinstance(content, bytes) or _sha256(content) != entry.get("sha256"):
            raise PlanScaleError("shard digest mismatch")
        if any(shard.get(key) != value for key, value in entry.items()):
            raise PlanScaleError("shard metadata mismatch")
    return manifest


def reassemble_shards(layout: dict[str, Any]) -> bytes:
    manifest = _validate_layout(layout)
    content = b"".join(shard["content"] for shard in layout["shards"])
    if _sha256(content) != manifest.get("source_sha256"):
        raise PlanScaleError("reassembled source digest mismatch")
    if len(content) != manifest.get("source_bytes"):
        raise PlanScaleError("reassembled source byte count mismatch")
    return content


def route_shard(
    layout: dict[str, Any], *, row_id: str | None = None, tag: str | None = None
) -> dict[str, Any]:
    _validate_layout(layout)
    if (row_id is None) == (tag is None):
        raise PlanScaleError("route exactly one row id or tag")
    matches = [
        shard
        for shard in layout["shards"]
        if (row_id is not None and row_id in shard["row_ids"])
        or (tag is not None and tag in shard["tags"])
    ]
    if not matches:
        raise PlanScaleError("manifest has no matching shard")
    if row_id is not None:
        task_matches = [shard for shard in matches if "task" in shard["tags"]]
        if task_matches:
            return task_matches[0]
    # Progress is append-only, so the last matching receipt is the current one.
    return matches[-1]


def compare_layouts(content: bytes) -> dict[str, Any]:
    """Compare the three M26 candidates on one exact source snapshot."""
    layout = sharded_layout(content)
    reassembled = reassemble_shards(layout)
    manifest_bytes = len(layout["manifest"])
    row_ids = [
        row_id for shard in layout["shards"] for row_id in shard["row_ids"]
        if "task" in shard["tags"]
    ]
    current = route_shard(layout, row_id=row_ids[0]) if row_ids else layout["shards"][0]
    offset_index_bytes = manifest_bytes
    candidates = [
        {
            "name": "monolith-plus-index",
            "authorities": 1,
            "canonical_bytes": len(content),
            "derived_bytes": offset_index_bytes,
            "current_lookup_bytes": offset_index_bytes + current["bytes"],
            "write_amplification_bytes": len(content),
            "exact_reassembly": True,
            "failure_mode": "offset index may be stale; source plan remains readable",
        },
        {
            "name": "hot-plan-plus-archives",
            "authorities": 1,
            "canonical_bytes": len(content),
            "derived_bytes": 0,
            "current_lookup_bytes": len(content),
            "write_amplification_bytes": len(content),
            "exact_reassembly": True,
            "failure_mode": "archive tombstone may outlive its adjacent archive",
        },
        {
            "name": "manifest-plus-shards",
            "authorities": 1,
            "canonical_bytes": manifest_bytes + len(content),
            "derived_bytes": 0,
            "current_lookup_bytes": manifest_bytes + current["bytes"],
            # A completion rewrites one task shard and the manifest, then
            # appends one bounded receipt shard. Existing receipt shards are
            # immutable and therefore are not write amplification.
            "write_amplification_bytes": manifest_bytes + current["bytes"] + 512,
            "exact_reassembly": reassembled == content,
            "failure_mode": "manifest or shard digest mismatch must refuse",
        },
    ]
    return {
        "schema": "shadow.plan-layout-comparison.v1",
        "source_sha256": _sha256(content),
        "source_bytes": len(content),
        "candidates": candidates,
        "decision": "manifest-plus-shards",
    }
