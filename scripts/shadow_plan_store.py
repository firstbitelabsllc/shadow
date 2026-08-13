"""One lossless, content-addressed storage format for large Shadow plans.

The root and every object in a build are canonical bytes.  This module owns
format mechanics only; the private root board continues to own coordination.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_grammar as _grammar  # noqa: E402


ROOT_SCHEMA = "shadow.plan-tree.v1"
PAGE_SCHEMA = "shadow.plan-tree-page.v1"
ROOT_MAX_BYTES = 8 * 1024
INDEX_MAX_BYTES = 16 * 1024
DATA_MAX_BYTES = 32 * 1024
PAGE_FANOUT = 64
MAX_TREE_DEPTH = 16
ROOT_PREFIX = b"# Shadow plan tree\n\n```json\n"
ROOT_SUFFIX = b"\n```\n"
TIMESTAMP_RE = re.compile(
    r"^- (?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
)


class PlanStoreError(ValueError):
    """The candidate tree is malformed, lossy, stale, or unsafe."""


@dataclass(frozen=True)
class FormatLimits:
    root_bytes: int = ROOT_MAX_BYTES
    index_bytes: int = INDEX_MAX_BYTES
    data_bytes: int = DATA_MAX_BYTES
    page_fanout: int = PAGE_FANOUT
    max_tree_depth: int = MAX_TREE_DEPTH


DEFAULT_LIMITS = FormatLimits()


@dataclass(frozen=True)
class PlanTreeBuild:
    root_bytes: bytes
    root: dict[str, Any]
    objects: dict[str, bytes]
    row_routes: dict[str, str]
    tag_routes: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class BuildResult:
    content: bytes
    catalog_key: str
    object_sha256: str


@dataclass(frozen=True)
class RebuiltRoutes:
    row_routes: dict[str, str]
    tag_routes: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class PlanProvenance:
    selector: str
    root_sha256: str
    index_sha256: tuple[str, ...]
    shard_sha256: str
    shard_bytes: int
    catalog_key: str
    result_start: int
    result_end: int
    result_sha256: str
    file_reads: int
    source_bytes: int


@dataclass(frozen=True)
class PlanResult:
    content: bytes
    provenance: PlanProvenance


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeError as exc:
        raise PlanStoreError("plan is not valid UTF-8") from exc


def _boundaries(lines: list[str]) -> list[tuple[int, str, str]]:
    boundaries: dict[int, tuple[int, str, str]] = {0: (0, "preamble", "")}
    section = ""
    for index, line in enumerate(lines):
        if line.startswith("## "):
            section = line[3:].strip()
            boundaries[index] = (index, "section", section)
            continue
        if section == "Tasks" and line.startswith("### "):
            boundaries[index] = (index, "milestone", section)
            continue
        if section in {"Brief", "Progress", "Deferred", "Contradictions"} and line.startswith("- "):
            boundaries[index] = (index, "item", section)
    return [boundaries[index] for index in sorted(boundaries)]


def _split(content: bytes, limits: FormatLimits) -> list[dict[str, Any]]:
    text = _text(content)
    lines = text.splitlines(keepends=True)
    if not lines:
        raise PlanStoreError("plan is empty")
    boundaries = _boundaries(lines)
    shards: list[dict[str, Any]] = []
    section_occurrences: dict[str, int] = {}
    for position, (start, kind, section) in enumerate(boundaries):
        end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        body = "".join(lines[start:end]).encode("utf-8")
        if not body:
            continue
        if len(body) > limits.data_bytes:
            raise PlanStoreError(
                f"grammar item exceeds {limits.data_bytes} byte data-shard limit"
            )
        body_text = _text(body)
        task_rows: list[str] = []
        needs: list[str] = []
        for line in body_text.splitlines():
            match = _grammar.ROW_RE.fullmatch(line)
            if match is None:
                continue
            task_rows.append(match.group("id"))
            fields = {
                field.group("key"): field.group("value").strip()
                for field in _grammar.FIELD_RE.finditer(match.group("tail"))
            }
            needs.extend(_grammar.NEEDS_REF_RE.findall(fields.get("needs", "")))
        tags: list[str] = []
        if section == "Progress":
            for token, marker in (
                ("proof", " PROOF "),
                ("decision", " DECISION "),
                ("lesson", " LESSON "),
            ):
                if marker in body_text:
                    tags.append(token)
        elif section == "Contradictions":
            tags.append("contradiction")
        elif section == "Deferred":
            tags.append("deferred")
        elif section == "Brief":
            tags.append("brief")
        elif section == "Tasks":
            tags.append("task")
        occurrence = section_occurrences.get(section, 0)
        section_occurrences[section] = occurrence + 1
        body_digest = digest_bytes(body)
        if kind == "milestone" and task_rows:
            logical_id = f"milestone/{task_rows[0]}"
        elif kind == "item" and section == "Progress":
            timestamp = TIMESTAMP_RE.match(body_text)
            stamp = timestamp.group("timestamp") if timestamp else "unstamped"
            logical_id = f"progress/{stamp}/{body_digest[:16]}"
        elif kind == "preamble":
            logical_id = "preamble"
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-") or kind
            logical_id = f"section/{slug}/{occurrence:06d}"
        shards.append(
            {
                "content": body,
                "object": body_digest,
                "bytes": len(body),
                "kind": kind,
                "section": section,
                "logical_id": logical_id,
                "row_ids": task_rows,
                "needs": needs,
                "tags": sorted(tags),
            }
        )
    return shards


def _add_object(objects: dict[str, bytes], content: bytes) -> str:
    digest = digest_bytes(content)
    previous = objects.get(digest)
    if previous is not None and previous != content:
        raise PlanStoreError("SHA-256 object collision")
    objects[digest] = content
    return digest


def _page(tree: str, kind: str, entries: list[dict[str, Any]]) -> bytes:
    return canonical_json(
        {"schema": PAGE_SCHEMA, "tree": tree, "kind": kind, "entries": entries}
    )


def _pack_pages(
    tree: str,
    kind: str,
    entries: list[dict[str, Any]],
    objects: dict[str, bytes],
    limits: FormatLimits,
) -> list[dict[str, str]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for entry in entries:
        if not current:
            current = [entry]
            if len(_page(tree, kind, current)) > limits.index_bytes:
                raise PlanStoreError("one index entry exceeds the page byte limit")
            continue
        candidate = [*current, entry]
        encoded = _page(tree, kind, candidate)
        if (
            len(candidate) > limits.page_fanout or len(encoded) > limits.index_bytes
        ):
            groups.append(current)
            current = [entry]
            encoded = _page(tree, kind, current)
            if len(encoded) > limits.index_bytes:
                raise PlanStoreError("one index entry exceeds the page byte limit")
            continue
        current = candidate
    if current or not groups:
        groups.append(current)
    nodes: list[dict[str, str]] = []
    for group in groups:
        encoded = _page(tree, kind, group)
        digest = _add_object(objects, encoded)
        minimum = group[0]["key"] if group else ""
        maximum = group[-1].get("max", group[-1]["key"]) if group else ""
        nodes.append({"min": minimum, "max": maximum, "object": digest})
    return nodes


def _build_index(
    tree: str,
    pairs: Iterable[tuple[str, Any]],
    objects: dict[str, bytes],
    limits: FormatLimits,
) -> str:
    ordered = sorted(pairs, key=lambda pair: pair[0])
    keys = [key for key, _ in ordered]
    if len(keys) != len(set(keys)):
        raise PlanStoreError(f"duplicate key in {tree} index")
    leaf_entries = [{"key": key, "value": value} for key, value in ordered]
    nodes = _pack_pages(tree, "leaf", leaf_entries, objects, limits)
    depth = 1
    while len(nodes) > 1:
        if depth >= limits.max_tree_depth:
            raise PlanStoreError("index exceeds the maximum tree depth")
        branch_entries = [
            {"key": node["min"], "max": node["max"], "object": node["object"]}
            for node in nodes
        ]
        nodes = _pack_pages(tree, "branch", branch_entries, objects, limits)
        depth += 1
    return nodes[0]["object"]


def _decode_page(content: bytes, tree: str) -> dict[str, Any]:
    try:
        page = json.loads(content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PlanStoreError("index page is malformed") from exc
    if (
        not isinstance(page, dict)
        or page.get("schema") != PAGE_SCHEMA
        or page.get("tree") != tree
        or page.get("kind") not in {"leaf", "branch"}
        or not isinstance(page.get("entries"), list)
    ):
        raise PlanStoreError("index page schema is invalid")
    return page


def _verified_object(build: PlanTreeBuild, digest: str) -> bytes:
    content = build.objects.get(digest)
    if content is None:
        raise PlanStoreError("referenced object is missing")
    if digest_bytes(content) != digest:
        raise PlanStoreError("object digest mismatch")
    return content


def _iter_tree(build: PlanTreeBuild, tree: str, root: str) -> Iterator[tuple[str, Any]]:
    def visit(digest: str, ancestors: frozenset[str], depth: int) -> Iterator[tuple[str, Any]]:
        if depth > MAX_TREE_DEPTH:
            raise PlanStoreError("index exceeds the maximum tree depth")
        if digest in ancestors:
            raise PlanStoreError("index cycle detected")
        page = _decode_page(_verified_object(build, digest), tree)
        entries = page["entries"]
        if page["kind"] == "leaf":
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("key"), str) or "value" not in entry:
                    raise PlanStoreError("leaf entry is malformed")
                yield entry["key"], entry["value"]
            return
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("object"), str):
                raise PlanStoreError("branch entry is malformed")
            yield from visit(entry["object"], ancestors | {digest}, depth + 1)

    previous: str | None = None
    for key, value in visit(root, frozenset(), 1):
        if previous is not None and key <= previous:
            raise PlanStoreError("index keys are not strictly ordered")
        previous = key
        yield key, value


def _exact_lookup(build: PlanTreeBuild, tree: str, root: str, key: str) -> Any:
    for candidate, value in _iter_tree(build, tree, root):
        if candidate == key:
            return value
        if candidate > key:
            break
    raise PlanStoreError(f"{tree} index has no route for {key}")


def _root_bytes(payload: dict[str, Any], limits: FormatLimits) -> bytes:
    result = ROOT_PREFIX + canonical_json(payload) + ROOT_SUFFIX
    if len(result) > limits.root_bytes:
        raise PlanStoreError("plan-tree root exceeds the byte limit")
    return result


def build_tree(
    content: bytes, *, limits: FormatLimits = DEFAULT_LIMITS
) -> PlanTreeBuild:
    """Build one deterministic in-memory tree without touching the filesystem."""
    shards = _split(content, limits)
    objects: dict[str, bytes] = {}
    rows: dict[str, str] = {}
    tag_routes: dict[str, list[str]] = {}
    catalog_pairs: list[tuple[str, Any]] = []
    all_needs: list[str] = []
    for ordinal, shard in enumerate(shards):
        _add_object(objects, shard["content"])
        catalog_key = f"{ordinal:020d}"
        for row_id in shard["row_ids"]:
            if row_id in rows:
                raise PlanStoreError(f"duplicate row id {row_id}")
            rows[row_id] = catalog_key
        all_needs.extend(shard["needs"])
        for tag in shard["tags"]:
            tag_routes.setdefault(tag, []).append(catalog_key)
        descriptor = {
            key: value
            for key, value in shard.items()
            if key not in {"content", "needs"}
        }
        descriptor["state"] = "active"
        catalog_pairs.append((catalog_key, descriptor))
    for target in all_needs:
        if target not in rows:
            raise PlanStoreError(f"needs target {target} does not exist")
    row_pairs = [(row_id, key) for row_id, key in rows.items()]
    tag_pairs: list[tuple[str, Any]] = []
    for tag, keys in sorted(tag_routes.items()):
        tag_pairs.append((f"latest/{tag}", keys[-1]))
        for sequence, key in enumerate(keys):
            tag_pairs.append((f"receipt/{tag}/{sequence:020d}", key))
    catalog_root = _build_index("catalog", catalog_pairs, objects, limits)
    row_root = _build_index("row", row_pairs, objects, limits)
    tag_root = _build_index("tag", tag_pairs, objects, limits)
    payload: dict[str, Any] = {
        "schema": ROOT_SCHEMA,
        "generation": 0,
        "logical_sha256": digest_bytes(content),
        "logical_bytes": len(content),
        "catalog_root": catalog_root,
        "row_root": row_root,
        "tag_root": tag_root,
        "object_count": len(objects),
        "row_count": len(rows),
        "limits": {
            "root_bytes": limits.root_bytes,
            "index_bytes": limits.index_bytes,
            "data_bytes": limits.data_bytes,
            "page_fanout": limits.page_fanout,
            "max_tree_depth": limits.max_tree_depth,
        },
        "previous_root": None,
    }
    return PlanTreeBuild(
        root_bytes=_root_bytes(payload, limits),
        root=payload,
        objects=objects,
        row_routes=dict(sorted(rows.items())),
        tag_routes={tag: tuple(keys) for tag, keys in sorted(tag_routes.items())},
    )


def materialize_build(build: PlanTreeBuild) -> bytes:
    parts: list[bytes] = []
    for _, descriptor in _iter_tree(build, "catalog", build.root["catalog_root"]):
        if not isinstance(descriptor, dict):
            raise PlanStoreError("catalog descriptor is malformed")
        digest = descriptor.get("object")
        expected_bytes = descriptor.get("bytes")
        if not isinstance(digest, str) or not isinstance(expected_bytes, int):
            raise PlanStoreError("catalog descriptor is incomplete")
        content = _verified_object(build, digest)
        if len(content) != expected_bytes:
            raise PlanStoreError("catalog byte count mismatch")
        parts.append(content)
    result = b"".join(parts)
    if len(result) != build.root.get("logical_bytes"):
        raise PlanStoreError("materialized byte count mismatch")
    if digest_bytes(result) != build.root.get("logical_sha256"):
        raise PlanStoreError("materialized digest mismatch")
    return result


def catalog_entries(build: PlanTreeBuild) -> tuple[tuple[str, dict[str, Any]], ...]:
    """Return verified descriptors in exact logical-plan order."""
    result: list[tuple[str, dict[str, Any]]] = []
    for key, descriptor in _iter_tree(
        build, "catalog", build.root["catalog_root"]
    ):
        if not isinstance(descriptor, dict):
            raise PlanStoreError("catalog descriptor is malformed")
        result.append((key, descriptor))
    return tuple(result)


def _catalog_result(build: PlanTreeBuild, catalog_key: str) -> BuildResult:
    descriptor = _exact_lookup(
        build, "catalog", build.root["catalog_root"], catalog_key
    )
    if not isinstance(descriptor, dict) or not isinstance(descriptor.get("object"), str):
        raise PlanStoreError("catalog route is malformed")
    content = _verified_object(build, descriptor["object"])
    return BuildResult(content, catalog_key, descriptor["object"])


def lookup_build(
    build: PlanTreeBuild, *, row_id: str | None = None, tag: str | None = None
) -> BuildResult:
    if (row_id is None) == (tag is None):
        raise PlanStoreError("route exactly one row id or tag")
    if row_id is not None:
        catalog_key = _exact_lookup(build, "row", build.root["row_root"], row_id)
        result = _catalog_result(build, catalog_key)
        if not any(
            (match := _grammar.ROW_RE.fullmatch(line)) is not None
            and match.group("id") == row_id
            for line in _text(result.content).splitlines()
        ):
            raise PlanStoreError("row route does not match canonical shard")
        return result
    assert tag is not None
    catalog_key = _exact_lookup(
        build, "tag", build.root["tag_root"], f"latest/{tag}"
    )
    result = _catalog_result(build, catalog_key)
    descriptor = _exact_lookup(
        build, "catalog", build.root["catalog_root"], catalog_key
    )
    if tag not in descriptor.get("tags", []):
        raise PlanStoreError("tag route does not match canonical shard")
    return result


def rebuild_routes(build: PlanTreeBuild) -> RebuiltRoutes:
    """Re-derive row and tag locators only from verified canonical shards."""
    rows: dict[str, str] = {}
    tags: dict[str, list[str]] = {}
    for catalog_key, descriptor in _iter_tree(
        build, "catalog", build.root["catalog_root"]
    ):
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("object"), str):
            raise PlanStoreError("catalog descriptor is malformed")
        content = _text(_verified_object(build, descriptor["object"]))
        for line in content.splitlines():
            match = _grammar.ROW_RE.fullmatch(line)
            if match is not None:
                row_id = match.group("id")
                if row_id in rows:
                    raise PlanStoreError(f"duplicate row id {row_id}")
                rows[row_id] = catalog_key
        for tag in descriptor.get("tags", []):
            if not isinstance(tag, str):
                raise PlanStoreError("catalog tag is malformed")
            tags.setdefault(tag, []).append(catalog_key)
    return RebuiltRoutes(
        row_routes=dict(sorted(rows.items())),
        tag_routes={tag: tuple(keys) for tag, keys in sorted(tags.items())},
    )


def _safe_read(path: Path, limit: int) -> bytes:
    """Read one stable regular file without following its leaf symlink."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise PlanStoreError("plan-tree source is not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            content = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
    except PlanStoreError:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        if isinstance(exc, FileNotFoundError):
            raise PlanStoreError("referenced object is missing") from exc
        raise PlanStoreError("plan-tree source is unreadable") from exc
    before_state = (
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
        before.st_dev,
        before.st_ino,
    )
    after_state = (
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_dev,
        after.st_ino,
    )
    if before_state != after_state:
        raise PlanStoreError("plan-tree source changed while reading")
    if len(content) > limit:
        raise PlanStoreError("plan-tree source exceeds its byte limit")
    return content


def _parse_root(content: bytes) -> dict[str, Any] | None:
    if not content.startswith(ROOT_PREFIX):
        _text(content)
        return None
    if not content.endswith(ROOT_SUFFIX):
        raise PlanStoreError("plan-tree root fence is malformed")
    encoded = content[len(ROOT_PREFIX):-len(ROOT_SUFFIX)]
    try:
        payload = json.loads(encoded)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PlanStoreError("plan-tree root JSON is malformed") from exc
    if not isinstance(payload, dict) or payload.get("schema") != ROOT_SCHEMA:
        raise PlanStoreError("plan-tree root schema is not supported")
    if content != ROOT_PREFIX + canonical_json(payload) + ROOT_SUFFIX:
        raise PlanStoreError("plan-tree root is not canonical JSON")
    for key in ("catalog_root", "row_root", "tag_root", "logical_sha256"):
        value = payload.get(key)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise PlanStoreError(f"plan-tree root {key} is malformed")
    if not isinstance(payload.get("logical_bytes"), int) or payload["logical_bytes"] < 0:
        raise PlanStoreError("plan-tree logical byte count is malformed")
    return payload


class PlanSnapshot:
    """One frozen legacy plan or content-addressed plan-tree generation."""

    def __init__(
        self,
        plan: Path,
        root_bytes: bytes,
        root: dict[str, Any] | None,
    ) -> None:
        self.plan = plan
        self.root_bytes = root_bytes
        self.root = root
        self.root_sha256 = digest_bytes(root_bytes)
        self._legacy_build: PlanTreeBuild | None = None

    @classmethod
    def open(cls, plan: Path) -> "PlanSnapshot":
        candidate = Path(os.path.abspath(plan))
        if candidate.name != "PLAN.md":
            raise PlanStoreError("plan-tree root must be named PLAN.md")
        content = _safe_read(candidate, 1_000_000)
        root = _parse_root(content)
        if root is not None and len(content) > ROOT_MAX_BYTES:
            raise PlanStoreError("plan-tree root exceeds the byte limit")
        return cls(candidate, content, root)

    @property
    def is_tree(self) -> bool:
        return self.root is not None

    def object_path(self, digest: str) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise PlanStoreError("object digest is malformed")
        root = self.plan.parent / "PLAN.d" / "objects" / "sha256"
        for component in (self.plan.parent / "PLAN.d", root.parent, root, root / digest[:2]):
            try:
                if component.exists() and component.is_symlink():
                    raise PlanStoreError("plan-tree object path crosses a symlink")
            except OSError as exc:
                raise PlanStoreError("plan-tree object path is unavailable") from exc
        return root / digest[:2] / digest

    def _read_object(
        self,
        digest: str,
        limit: int,
        counters: list[int],
    ) -> bytes:
        content = _safe_read(self.object_path(digest), limit)
        counters[0] += 1
        counters[1] += len(content)
        if digest_bytes(content) != digest:
            raise PlanStoreError("object digest mismatch")
        return content

    def _page(
        self,
        tree: str,
        digest: str,
        counters: list[int],
        visited: list[str],
    ) -> dict[str, Any]:
        if digest in visited:
            raise PlanStoreError("index cycle detected")
        if len(visited) >= MAX_TREE_DEPTH:
            raise PlanStoreError("index exceeds the maximum tree depth")
        page = _decode_page(self._read_object(digest, INDEX_MAX_BYTES, counters), tree)
        visited.append(digest)
        return page

    def _tree_lookup(
        self,
        tree: str,
        root: str,
        key: str,
        counters: list[int],
        visited: list[str],
    ) -> Any:
        digest = root
        path_seen: set[str] = set()
        while True:
            if digest in path_seen:
                raise PlanStoreError("index cycle detected")
            path_seen.add(digest)
            page = self._page(tree, digest, counters, visited)
            entries = page["entries"]
            keys = [entry.get("key") for entry in entries if isinstance(entry, dict)]
            if len(keys) != len(entries) or any(not isinstance(item, str) for item in keys):
                raise PlanStoreError("index entry is malformed")
            if keys != sorted(keys) or len(keys) != len(set(keys)):
                raise PlanStoreError("index keys are not strictly ordered")
            if page["kind"] == "leaf":
                for entry in entries:
                    if entry["key"] == key and "value" in entry:
                        return entry["value"]
                raise PlanStoreError(f"{tree} index has no route for {key}")
            matches = [
                entry for entry in entries
                if isinstance(entry.get("max"), str)
                and isinstance(entry.get("object"), str)
                and entry["key"] <= key <= entry["max"]
            ]
            if len(matches) != 1:
                raise PlanStoreError(f"{tree} branch has no unique route for {key}")
            digest = matches[0]["object"]

    def _tree_entries(
        self,
        tree: str,
        digest: str,
        counters: list[int],
        visited: list[str],
        ancestors: frozenset[str] = frozenset(),
    ) -> Iterator[tuple[str, Any]]:
        if digest in ancestors:
            raise PlanStoreError("index cycle detected")
        page = self._page(tree, digest, counters, visited)
        entries = page["entries"]
        if page["kind"] == "leaf":
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("key"), str) or "value" not in entry:
                    raise PlanStoreError("leaf entry is malformed")
                yield entry["key"], entry["value"]
            return
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("object"), str):
                raise PlanStoreError("branch entry is malformed")
            yield from self._tree_entries(
                tree,
                entry["object"],
                counters,
                visited,
                ancestors | {digest},
            )

    def _legacy(self) -> PlanTreeBuild:
        if self._legacy_build is None:
            self._legacy_build = build_tree(self.root_bytes)
        return self._legacy_build

    def materialize(self) -> bytes:
        if self.root is None:
            return self.root_bytes
        counters = [1, len(self.root_bytes)]
        visited: list[str] = []
        parts: list[bytes] = []
        previous: str | None = None
        for key, descriptor in self._tree_entries(
            "catalog", self.root["catalog_root"], counters, visited
        ):
            if previous is not None and key <= previous:
                raise PlanStoreError("catalog keys are not strictly ordered")
            previous = key
            if not isinstance(descriptor, dict) or not isinstance(descriptor.get("object"), str):
                raise PlanStoreError("catalog descriptor is malformed")
            content = self._read_object(
                descriptor["object"], DATA_MAX_BYTES, counters
            )
            if len(content) != descriptor.get("bytes"):
                raise PlanStoreError("catalog byte count mismatch")
            parts.append(content)
        materialized = b"".join(parts)
        if len(materialized) != self.root["logical_bytes"]:
            raise PlanStoreError("materialized byte count mismatch")
        if digest_bytes(materialized) != self.root["logical_sha256"]:
            raise PlanStoreError("materialized digest mismatch")
        return materialized

    def row(self, row_id: str) -> PlanResult:
        if _grammar.ROW_ID_RE.fullmatch(row_id) is None:
            raise PlanStoreError("row id is malformed")
        if self.root is None:
            result = lookup_build(self._legacy(), row_id=row_id)
            return PlanResult(
                result.content,
                PlanProvenance(
                    selector=f"row:{row_id}",
                    root_sha256=self.root_sha256,
                    index_sha256=(),
                    shard_sha256=self.root_sha256,
                    shard_bytes=len(self.root_bytes),
                    catalog_key=result.catalog_key,
                    result_start=0,
                    result_end=len(result.content),
                    result_sha256=digest_bytes(result.content),
                    file_reads=1,
                    source_bytes=len(self.root_bytes),
                ),
            )
        counters = [1, len(self.root_bytes)]
        visited: list[str] = []
        catalog_key = self._tree_lookup(
            "row", self.root["row_root"], row_id, counters, visited
        )
        descriptor = self._tree_lookup(
            "catalog", self.root["catalog_root"], catalog_key, counters, visited
        )
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("object"), str):
            raise PlanStoreError("catalog route is malformed")
        content = self._read_object(descriptor["object"], DATA_MAX_BYTES, counters)
        if len(content) != descriptor.get("bytes"):
            raise PlanStoreError("catalog byte count mismatch")
        if not any(
            (match := _grammar.ROW_RE.fullmatch(line)) is not None
            and match.group("id") == row_id
            for line in _text(content).splitlines()
        ):
            raise PlanStoreError("row route does not match canonical shard")
        return PlanResult(
            content,
            PlanProvenance(
                selector=f"row:{row_id}",
                root_sha256=self.root_sha256,
                index_sha256=tuple(visited),
                shard_sha256=descriptor["object"],
                shard_bytes=len(content),
                catalog_key=catalog_key,
                result_start=0,
                result_end=len(content),
                result_sha256=digest_bytes(content),
                file_reads=counters[0],
                source_bytes=counters[1],
            ),
        )

    def latest(self, tag: str) -> PlanResult:
        if not tag or not re.fullmatch(r"[a-z][a-z0-9-]*", tag):
            raise PlanStoreError("tag is malformed")
        if self.root is None:
            result = lookup_build(self._legacy(), tag=tag)
            return PlanResult(
                result.content,
                PlanProvenance(
                    selector=f"tag:{tag}",
                    root_sha256=self.root_sha256,
                    index_sha256=(),
                    shard_sha256=self.root_sha256,
                    shard_bytes=len(self.root_bytes),
                    catalog_key=result.catalog_key,
                    result_start=0,
                    result_end=len(result.content),
                    result_sha256=digest_bytes(result.content),
                    file_reads=1,
                    source_bytes=len(self.root_bytes),
                ),
            )
        counters = [1, len(self.root_bytes)]
        visited: list[str] = []
        catalog_key = self._tree_lookup(
            "tag", self.root["tag_root"], f"latest/{tag}", counters, visited
        )
        descriptor = self._tree_lookup(
            "catalog", self.root["catalog_root"], catalog_key, counters, visited
        )
        if not isinstance(descriptor, dict) or tag not in descriptor.get("tags", []):
            raise PlanStoreError("tag route does not match canonical shard")
        content = self._read_object(descriptor["object"], DATA_MAX_BYTES, counters)
        return PlanResult(
            content,
            PlanProvenance(
                selector=f"tag:{tag}",
                root_sha256=self.root_sha256,
                index_sha256=tuple(visited),
                shard_sha256=descriptor["object"],
                shard_bytes=len(content),
                catalog_key=catalog_key,
                result_start=0,
                result_end=len(content),
                result_sha256=digest_bytes(content),
                file_reads=counters[0],
                source_bytes=counters[1],
            ),
        )
