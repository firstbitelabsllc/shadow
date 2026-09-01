#!/usr/bin/env python3
"""Inspect and migrate one authoritative Shadow plan without another queue."""

from __future__ import annotations

import argparse
from collections import Counter
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_store as store  # noqa: E402
import shadow_git as _shadow_git  # noqa: E402
import shadow_plan_grammar as grammar  # noqa: E402
import shadow_remote_claim as remote_claim  # noqa: E402
import shadow_root_board as board_store  # noqa: E402
from shadow_durable_lib import durable_write  # noqa: E402
from shadow_json_lib import json_text  # noqa: E402

_AMP_SPEC = importlib.util.spec_from_file_location(
    "shadow_amp",
    ROOT / "scripts" / "shadow-amp.py",
)
amp = importlib.util.module_from_spec(_AMP_SPEC)
sys.modules.setdefault("shadow_amp", amp)
_AMP_SPEC.loader.exec_module(amp)


PlanStoreError = store.PlanStoreError


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PlanStoreError(f"{label} is unreadable") from exc


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    # The migration verb's probes and mutations answer about the true
    # repository: an ambient GIT_DIR/GIT_WORK_TREE from the caller's shell
    # must not redirect either. A missing git binary is a refusal, not a
    # traceback.
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            check=False,
            env=_shadow_git.sanitized_git_env(),
        )
    except OSError as exc:
        raise PlanStoreError("git is not available") from exc


def _git_context(plan: Path) -> tuple[Path, Path] | None:
    if board_store.is_local_plan(plan):
        return None
    probe = _git(plan.parent, "rev-parse", "--show-toplevel")
    if probe.returncode:
        return None
    try:
        repo = Path(probe.stdout.decode("utf-8").strip()).resolve()
        relative = plan.resolve().relative_to(repo)
    except (UnicodeError, ValueError):
        raise PlanStoreError("plan does not resolve inside its Git repository") from None
    tracked = _git(repo, "ls-files", "--error-unmatch", "--", relative.as_posix())
    if tracked.returncode:
        raise PlanStoreError("Git-backed migration requires a tracked PLAN.md")
    tree = relative.parent / "PLAN.d"
    dirty = _git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        relative.as_posix(),
        tree.as_posix(),
    )
    if dirty.returncode or dirty.stdout.strip():
        raise PlanStoreError("plan root or object tree is not clean at Git HEAD")
    return repo, relative


def _reset_index(repo: Path, relative: Path) -> None:
    tree = relative.parent / "PLAN.d"
    _git(repo, "reset", "--quiet", "HEAD", "--", relative.as_posix(), tree.as_posix())


def _commit_tree(repo: Path, relative: Path, message: str) -> str:
    tree = relative.parent / "PLAN.d"
    added = _git(repo, "add", "--", relative.as_posix(), tree.as_posix())
    if added.returncode:
        raise PlanStoreError("partitioned plan could not be staged")
    committed = _git(
        repo,
        "-c", "core.hooksPath=/dev/null",
        "-c", "commit.gpgsign=false",
        "-c", "user.name=Shadow Plan",
        "-c", "user.email=shadow-plan@localhost",
        "commit", "--quiet", "--no-verify", "--no-gpg-sign", "--only",
        "-m", message, "--", relative.as_posix(), tree.as_posix(),
    )
    if committed.returncode:
        raise PlanStoreError("partitioned plan could not be committed")
    head = _git(repo, "rev-parse", "HEAD")
    if head.returncode:
        raise PlanStoreError("migration commit could not be read back")
    return head.stdout.decode("ascii").strip()


def _git_value(repo: Path, label: str, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode:
        raise PlanStoreError(f"{label} could not be read")
    try:
        values = result.stdout.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise PlanStoreError(f"{label} could not be read") from exc
    if len(values) != 1 or not values[0].strip():
        raise PlanStoreError(f"{label} could not be read")
    return values[0].strip()


def _canonical_sha256(payload: dict[str, object], field: str) -> str:
    frozen = json.loads(json.dumps(payload))
    frozen.pop(field, None)
    return store.digest_bytes(store.canonical_json(frozen))


def _safe_receipt_path(path: Path, repo: Path) -> Path:
    if not path.is_absolute():
        raise PlanStoreError("migration receipt path must be absolute")
    canonical = Path(os.path.abspath(path))
    try:
        resolved = canonical.resolve(strict=False)
    except OSError as exc:
        raise PlanStoreError("migration receipt path is unsafe") from exc
    platform_aliases = {Path("/tmp"), Path("/var")}
    if canonical.is_symlink() or any(
        parent.is_symlink() and parent not in platform_aliases
        for parent in canonical.parents
    ):
        raise PlanStoreError("migration receipt path must not cross a symlink")
    canonical = resolved
    try:
        canonical.relative_to(repo.resolve())
    except ValueError:
        pass
    else:
        raise PlanStoreError("migration receipt must live outside the repository")
    if not canonical.parent.is_dir():
        raise PlanStoreError("migration receipt parent is unavailable")
    if canonical.exists() and (canonical.is_symlink() or not canonical.is_file()):
        raise PlanStoreError("migration receipt must be one regular file")
    return canonical


def _atomic_json(
    path: Path,
    payload: dict[str, object],
    *,
    repo: Path,
    allow_identical: bool = False,
) -> None:
    path = _safe_receipt_path(path, repo)
    if path.exists():
        if allow_identical and _read_receipt(path, repo=repo) == payload:
            return
        raise PlanStoreError("migration receipt already exists")
    payload_bytes = json_text(payload).encode("utf-8")
    try:
        durable_write(path, payload_bytes, exclusive=True, follow_symlinks=False)
    except FileExistsError as exc:
        raise PlanStoreError("migration receipt already exists") from exc


def _read_receipt(path: Path, *, repo: Path) -> dict[str, object]:
    path = _safe_receipt_path(path, repo)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PlanStoreError(
            "migration receipt must be one absolute regular file"
        ) from exc
    try:
        stat_result = os.fstat(descriptor)
        if not stat.S_ISREG(stat_result.st_mode):
            raise PlanStoreError(
                "migration receipt must be one absolute regular file"
            )
        if stat_result.st_size > 128 * 1024:
            raise PlanStoreError(
                "migration receipt exceeds the bounded size limit"
            )
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            payload = json.load(stream)
    except (OSError, UnicodeError, ValueError) as exc:
        raise PlanStoreError("migration receipt is unreadable or malformed") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(payload, dict):
        raise PlanStoreError("migration receipt is unreadable or malformed")
    return payload


def _map_repo(plan: Path) -> tuple[Path, Path]:
    plan = Path(os.path.abspath(plan))
    if board_store.is_local_plan(plan):
        raise PlanStoreError("project-map migration requires a Git-backed plan")
    probe = _git(plan.parent, "rev-parse", "--show-toplevel")
    if probe.returncode:
        raise PlanStoreError("project-map migration requires a Git repository")
    try:
        repo = Path(probe.stdout.decode("utf-8").strip()).resolve()
        relative = plan.resolve().relative_to(repo)
    except (UnicodeError, ValueError) as exc:
        raise PlanStoreError("plan does not resolve inside its Git repository") from exc
    return repo, relative


def _map_git_context(plan: Path) -> tuple[Path, Path, str, str]:
    plan = Path(os.path.abspath(plan))
    repo, relative = _map_repo(plan)
    if board_store.open_plan(plan).is_tree:
        raise PlanStoreError("project-map migration requires one plain PLAN.md root")
    dirty = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty.returncode or dirty.stdout.strip():
        raise PlanStoreError("project-map migration requires one completely clean checkout")
    branch = _git_value(repo, "current branch", "symbolic-ref", "--quiet", "HEAD")
    head = _git_value(repo, "current HEAD", "rev-parse", "HEAD")
    eligibility = remote_claim.upstream_eligibility(repo)
    if eligibility is not remote_claim.RemoteEligibility.VERIFIED_LOCAL_ONLY:
        raise PlanStoreError(
            "project-map migration requires a verified local-only branch"
        )
    return repo, relative, branch, head


def _blob_at(repo: Path, revision: str, relative: str) -> tuple[str, bytes]:
    blob = _git_value(
        repo,
        f"{relative} blob",
        "rev-parse",
        f"{revision}:{relative}",
    )
    content = _git(repo, "cat-file", "blob", blob)
    if content.returncode:
        raise PlanStoreError(f"{relative} bytes could not be read")
    return blob, content.stdout


def _plan_analysis(
    text: str,
    label: str,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    parsed = amp._parse(text)
    unclean = amp.unclean_note(parsed)
    if unclean is not None:
        raise PlanStoreError(f"project-map {label} {unclean}")
    rows: dict[str, dict[str, object]] = {}
    for milestone in parsed["milestones"]:
        for item in milestone["rows"]:
            row = item["id"]
            line = (
                f"- [{item['state']}] {item['text']} {row}"
                f"{item.get('dod') or ''}{item.get('tail') or ''}"
            )
            if row in rows:
                raise PlanStoreError(
                    f"project-map migration duplicates task row {row}"
                )
            needs = grammar.NEEDS_REF_RE.findall(
                item["fields"].get("needs", "")
            )
            rows[row] = {
                "line": line,
                "state": item["state"],
                "needs": needs,
            }
    return rows, amp._candidate_ids(parsed)


def _brief(text: str) -> tuple[str, int, list[str]]:
    active = False
    project: str | None = None
    priority: int | None = None
    plans: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            active = line[3:].strip() == "Brief"
            continue
        if not active:
            continue
        if line.startswith("- Project: "):
            project = line.removeprefix("- Project: ").strip()
        elif line.startswith("- Priority: "):
            try:
                priority = int(line.removeprefix("- Priority: ").strip())
            except ValueError as exc:
                raise PlanStoreError("project-map plan priority is invalid") from exc
        elif line.startswith("- Plans: "):
            plans.extend(
                item.strip()
                for item in line.removeprefix("- Plans: ").split(",")
                if item.strip()
            )
    if project is None or priority is None:
        raise PlanStoreError("project-map plan Brief is incomplete")
    return project, priority, plans


def _section_bullets(text: str, section: str) -> list[str]:
    active = False
    result: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            active = line[3:].strip() == section
            continue
        if active and line.startswith("- "):
            result.append(line)
    return result


def _project_map_plan_record(
    relative: str,
    identity: str,
    head: str,
    blob: str,
    content: bytes,
    rows: dict[str, dict[str, object]],
    candidates: list[str],
) -> dict[str, object]:
    return {
        "relative": relative,
        "entity_id": identity,
        "head": head,
        "blob": blob,
        "logical_sha256": hashlib.sha256(content).hexdigest(),
        "rows": list(rows),
        "candidates": candidates,
    }


def _board_journal_head(home: Path | None = None) -> str:
    root = (home or Path.home()).resolve() / ".shadow"
    return _git_value(root, "root board journal", "rev-parse", "HEAD")


_PRUNED_PLAN_DIRS = frozenset(
    {".git", ".shadow", ".venv", "venv", "node_modules", "dist", "build"}
)


def _bounded_plan_match(path: str, pattern: str) -> bool:
    path_parts = Path(path).parts
    pattern_parts = Path(pattern).parts
    return len(path_parts) == len(pattern_parts) and all(
        fnmatch.fnmatchcase(part, expected)
        for part, expected in zip(path_parts, pattern_parts)
    )


def _validate_child_declaration(
    repo: Path,
    target_head: str,
    declared: list[str],
    child_relative: str,
) -> None:
    if not declared or len(declared) > 3:
        raise PlanStoreError(
            "project-map root must declare one bounded child plan pattern"
        )
    for pattern in declared:
        parts = Path(pattern).parts
        if (
            not pattern
            or pattern.startswith(("/", ":"))
            or Path(pattern).is_absolute()
            or any(part in {"", ".", "..", "**"} for part in parts)
        ):
            raise PlanStoreError(
                "project-map root has an unsafe child plan declaration"
            )
    listed = _git(repo, "ls-tree", "-r", "--name-only", target_head)
    if listed.returncode:
        raise PlanStoreError("project-map target plans could not be enumerated")
    try:
        plan_paths = {
            path
            for path in listed.stdout.decode("utf-8").splitlines()
            if Path(path).name == "PLAN.md"
            and not any(
                segment.startswith(".") or segment in _PRUNED_PLAN_DIRS
                for segment in Path(path).parts[:-1]
            )
        }
    except UnicodeError as exc:
        raise PlanStoreError(
            "project-map target plans could not be enumerated"
        ) from exc
    matches = {
        path
        for path in plan_paths
        if any(_bounded_plan_match(path, pattern) for pattern in declared)
    }
    if matches != {child_relative}:
        raise PlanStoreError(
            "project-map root declaration must resolve to exactly the new child"
        )


def _prepare_project_map_migration(
    plan: Path,
    target_ref: str,
    child: Path,
) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    repo, relative, branch, source_head = _map_git_context(plan)
    root_relative = relative.as_posix()
    child_relative = child.as_posix()
    if (
        child.is_absolute()
        or child_relative == root_relative
        or child.name != "PLAN.md"
        or any(part in {"", ".", ".."} for part in child.parts)
        or child_relative.startswith(":")
        or any(character in child_relative for character in "*?[]\\")
        or any(
            part.startswith(".") or part in _PRUNED_PLAN_DIRS
            for part in child.parts[:-1]
        )
    ):
        raise PlanStoreError("project-map child must be one safe relative PLAN.md")
    source_token, source_content = board_store.committed_plan_snapshot(plan)
    if source_token["head"] != source_head:
        raise PlanStoreError("project-map source ref changed; retry")
    source_blob = source_token["blob"]
    source_tree = _git_value(repo, "source tree", "rev-parse", f"{source_head}^{{tree}}")
    target_head = _git_value(
        repo,
        "project-map target",
        "rev-parse",
        f"{target_ref}^{{commit}}",
    )
    parents = _git_value(
        repo,
        "project-map target ancestry",
        "rev-list",
        "--parents",
        "-n",
        "1",
        target_head,
    ).split()
    if len(parents) != 2 or parents[1] != source_head:
        raise PlanStoreError(
            "project-map target changed or is not one direct child commit of the source"
        )
    changed = _git(
        repo,
        "diff",
        "--name-only",
        "--diff-filter=ACDMRT",
        source_head,
        target_head,
    )
    if changed.returncode:
        raise PlanStoreError("project-map target diff could not be read")
    try:
        changed_paths = {
            line for line in changed.stdout.decode("utf-8").splitlines() if line
        }
    except UnicodeError as exc:
        raise PlanStoreError("project-map target diff could not be read") from exc
    if changed_paths != {root_relative, child_relative}:
        raise PlanStoreError(
            "project-map target may change only the root and declared child plans"
        )
    if not _git(repo, "cat-file", "-e", f"{source_head}:{child_relative}").returncode:
        raise PlanStoreError("project-map child must be new at the target commit")
    root_blob, root_content = _blob_at(repo, target_head, root_relative)
    child_blob, child_content = _blob_at(repo, target_head, child_relative)
    target_tree = _git_value(repo, "target tree", "rev-parse", f"{target_head}^{{tree}}")
    try:
        source_text = source_content.decode("utf-8")
        root_text = root_content.decode("utf-8")
        child_text = child_content.decode("utf-8")
    except UnicodeError as exc:
        raise PlanStoreError("project-map plans must be UTF-8") from exc
    source_rows, source_candidates = _plan_analysis(source_text, "source plan")
    root_rows, root_candidates = _plan_analysis(root_text, "root plan")
    child_rows, child_candidates = _plan_analysis(child_text, "child plan")
    if set(root_rows).intersection(child_rows) or (
        set(root_rows).union(child_rows) != set(source_rows)
    ):
        raise PlanStoreError("target plans must partition every source task row exactly once")
    destinations = {
        row: "root" if row in root_rows else "child"
        for row in source_rows
    }
    for row, record in source_rows.items():
        target_rows = root_rows if destinations[row] == "root" else child_rows
        if row not in target_rows or target_rows[row]["line"] != record["line"]:
            raise PlanStoreError(f"project-map target changed task row {row}")
    for label, rows in (("root", root_rows), ("child", child_rows)):
        for row, record in rows.items():
            missing = set(record["needs"]).difference(rows)
            if missing:
                raise PlanStoreError(
                    f"project-map {label} row {row} has a cross-entity dependency"
                )
    source_project, source_priority, _ = _brief(source_text)
    root_project, root_priority, declared = _brief(root_text)
    child_project, child_priority, _ = _brief(child_text)
    if (
        root_project != source_project
        or child_project != source_project
        or root_priority != source_priority
        or child_priority != source_priority
    ):
        raise PlanStoreError("project-map target changed project identity or priority")
    _validate_child_declaration(
        repo,
        target_head,
        declared,
        child_relative,
    )
    source_provenance = {
        section: _section_bullets(source_text, section)
        for section in ("Contradictions", "Progress")
    }
    target_provenance = {
        section: (
            _section_bullets(root_text, section),
            _section_bullets(child_text, section),
        )
        for section in ("Contradictions", "Progress")
    }
    provenance: list[dict[str, str]] = []
    for section, source_lines in source_provenance.items():
        root_lines, child_lines = target_provenance[section]
        if Counter(source_lines) != Counter(root_lines + child_lines):
            raise PlanStoreError(
                f"project-map target changed {section} provenance"
            )
        for line, count in Counter(source_lines).items():
            scoped = {
                destinations[row]
                for row in grammar.HASH_RE.findall(line)
                if row in destinations
            }
            if len(scoped) > 1:
                raise PlanStoreError(
                    f"project-map {section} line spans both entities"
                )
            destination = next(iter(scoped), "root")
            root_count = root_lines.count(line)
            child_count = child_lines.count(line)
            if (
                destination == "root"
                and (root_count != count or child_count)
            ) or (
                destination == "child"
                and (child_count != count or root_count)
            ):
                raise PlanStoreError(
                    f"project-map {section} provenance moved to the wrong entity"
                )
            provenance.extend(
                {
                    "section": section,
                    "line_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    "destination": destination,
                }
                for _ in range(count)
            )
    state = board_store.entity_state(plan)
    board_payload = board_store.snapshot()
    if (
        state is None
        or state["entity"] is None
        or board_payload is None
        or state["entity"]["plan"] != str(plan.resolve())
    ):
        raise PlanStoreError(
            "project-map source must be the exact registered board authority"
        )
    if state["project"] != {
        "id": source_project,
        "priority": source_priority,
    }:
        raise PlanStoreError("project-map board project identity does not match the plan")
    origin = board_store.origin_of(repo)
    root_identity = board_store.logical_entity_id(origin, root_relative)
    child_identity = board_store.logical_entity_id(origin, child_relative)
    if state["entity"]["id"] != root_identity:
        raise PlanStoreError("project-map source entity identity is stale")
    before = {
        "revision": board_payload["revision"],
        "raw_sha256": board_store.board_file_sha256(),
        "authority_sha256": board_store.board_authority_sha256(board_payload),
        "project": state["project"],
        "root_entity": {
            "id": state["entity"]["id"],
            "project": state["entity"]["project"],
            "resume": state["entity"]["resume"],
        },
        "claims": sorted(
            state["claims"],
            key=lambda item: (item["entity"], item["row"]),
        ),
        "journal_head": _board_journal_head(),
    }
    prepared: dict[str, object] = {
        "schema": "shadow.project-map-migration.v1",
        "phase": "prepared",
        "repo": {
            "origin_sha256": hashlib.sha256(origin.encode("utf-8")).hexdigest(),
            "branch_ref": branch,
            "source_head": source_head,
            "source_tree": source_tree,
            "target_ref": target_ref,
            "target_head": target_head,
            "target_tree": target_tree,
            "remote_eligibility": remote_claim.RemoteEligibility.VERIFIED_LOCAL_ONLY.value,
        },
        "plans": {
            "source": _project_map_plan_record(
                root_relative,
                root_identity,
                source_head,
                source_blob,
                source_content,
                source_rows,
                source_candidates,
            ),
            "root": _project_map_plan_record(
                root_relative,
                root_identity,
                target_head,
                root_blob,
                root_content,
                root_rows,
                root_candidates,
            ),
            "child": _project_map_plan_record(
                child_relative,
                child_identity,
                target_head,
                child_blob,
                child_content,
                child_rows,
                child_candidates,
            ),
        },
        "row_map": [
            {"row": row, "destination": destinations[row]}
            for row in source_rows
        ],
        "provenance": sorted(
            provenance,
            key=lambda item: (
                item["section"],
                item["line_sha256"],
                item["destination"],
            ),
        ),
        "board": {
            "before": before,
        },
        "transaction_sha256": "",
    }
    prepared["transaction_sha256"] = _canonical_sha256(
        prepared,
        "transaction_sha256",
    )
    return prepared


def _reset_exact(repo: Path, revision: str) -> None:
    reset = _git(repo, "reset", "--hard", "--quiet", revision)
    if reset.returncode:
        raise PlanStoreError("project-map Git state could not be restored")
    if (
        _git_value(repo, "project-map restored HEAD", "rev-parse", "HEAD")
        != revision
    ):
        raise PlanStoreError("project-map Git state could not be restored")
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode or status.stdout.strip():
        raise PlanStoreError("project-map Git state could not be restored")


def _validate_prepared_receipt(
    payload: dict[str, object],
    expected: str,
) -> None:
    if (
        payload.get("schema") != "shadow.project-map-migration.v1"
        or payload.get("phase") != "prepared"
        or payload.get("transaction_sha256") != expected
        or _canonical_sha256(payload, "transaction_sha256") != expected
    ):
        raise PlanStoreError("project-map migration receipt is invalid or stale")


def _validate_receipt_repository(
    prepared: dict[str, object],
    repo: Path,
    relative: Path,
    branch: str,
) -> dict[str, object]:
    repo_receipt = prepared.get("repo")
    plans = prepared.get("plans")
    if (
        not isinstance(repo_receipt, dict)
        or not isinstance(plans, dict)
        or set(plans) != {"source", "root", "child"}
        or repo_receipt.get("branch_ref") != branch
        or repo_receipt.get("origin_sha256")
        != hashlib.sha256(board_store.origin_of(repo).encode("utf-8")).hexdigest()
        or plans["source"].get("relative") != relative.as_posix()
        or plans["root"].get("relative") != relative.as_posix()
    ):
        raise PlanStoreError("project-map receipt names a different repository")
    return repo_receipt


def _applied_result(
    prepared: dict[str, object],
    board_payload: dict[str, object],
) -> dict[str, object]:
    result = json.loads(json.dumps(prepared))
    result["action"] = "applied"
    result["applied_sha256"] = prepared["transaction_sha256"]
    result["board_revision"] = board_payload["revision"]
    return result


def _apply_project_map_migration(
    plan: Path,
    target_ref: str,
    child: Path,
    expected: str,
    receipt: Path,
) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    repo, relative = _map_repo(plan)
    receipt = _safe_receipt_path(receipt, repo)
    child_relative = child.as_posix()
    child_plan = repo / child_relative
    with board_store.project_lock(plan):
        repo, relative, branch, head = _map_git_context(plan)
        if receipt.exists():
            prepared = _read_receipt(receipt, repo=repo)
            _validate_prepared_receipt(prepared, expected)
            repo_receipt = _validate_receipt_repository(
                prepared,
                repo,
                relative,
                branch,
            )
            if repo_receipt.get("target_ref") != target_ref:
                raise PlanStoreError(
                    "project-map receipt names a different target ref"
                )
            if head == repo_receipt["target_head"]:
                try:
                    applied = board_store.validate_project_map_migration_applied(
                        plan,
                        child_plan,
                        prepared,
                    )
                except board_store.BoardError:
                    applied = board_store.apply_project_map_migration(
                        plan,
                        child_plan,
                        prepared,
                    )
                return _applied_result(prepared, applied)
            if head != repo_receipt["source_head"]:
                raise PlanStoreError(
                    "project-map repository is neither the source nor target state"
                )
            current = _prepare_project_map_migration(plan, target_ref, child)
            if current != prepared:
                raise PlanStoreError(
                    "project-map migration target changed; rerun the dry run"
                )
        else:
            prepared = _prepare_project_map_migration(plan, target_ref, child)
            _validate_prepared_receipt(prepared, expected)
            _atomic_json(
                receipt,
                prepared,
                repo=repo,
                allow_identical=True,
            )
            repo_receipt = prepared["repo"]
        if prepared["transaction_sha256"] != expected:
            raise PlanStoreError(
                "project-map migration target changed; rerun the dry run"
            )
        target_head = repo_receipt["target_head"]
        merged = _git(repo, "merge", "--ff-only", target_head)
        if merged.returncode:
            raise PlanStoreError("project-map target could not fast-forward cleanly")
        if _git_value(repo, "project-map applied HEAD", "rev-parse", "HEAD") != target_head:
            raise PlanStoreError("project-map HEAD changed during fast-forward")
        try:
            applied = board_store.apply_project_map_migration(
                plan,
                child_plan,
                prepared,
            )
        except (OSError, PlanStoreError, board_store.BoardError):
            current_head = _git_value(
                repo,
                "project-map failed HEAD",
                "rev-parse",
                "HEAD",
            )
            if current_head != target_head:
                raise PlanStoreError(
                    "project-map board refused after another writer changed HEAD"
                )
            _reset_exact(repo, repo_receipt["source_head"])
            raise
        if _git_value(repo, "project-map final HEAD", "rev-parse", "HEAD") != target_head:
            raise PlanStoreError("project-map HEAD changed during board commit")
        return _applied_result(prepared, applied)


def _rollback_project_map_migration(
    plan: Path,
    receipt: Path,
    expected: str,
) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    repo, relative = _map_repo(plan)
    receipt = _safe_receipt_path(receipt, repo)
    applied = _read_receipt(receipt, repo=repo)
    _validate_prepared_receipt(applied, expected)
    rollback_path = receipt.with_name(receipt.stem + ".rollback.json")
    rollback_path = _safe_receipt_path(rollback_path, repo)
    with board_store.project_lock(plan):
        repo, relative, branch, head = _map_git_context(plan)
        repo_receipt = _validate_receipt_repository(
            applied,
            repo,
            relative,
            branch,
        )
        plans = applied["plans"]
        child_plan = repo / plans["child"]["relative"]
        rollback: dict[str, object] = {
            "schema": "shadow.project-map-rollback.v1",
            "phase": "prepared",
            "migration_sha256": expected,
            "source_head": repo_receipt["source_head"],
            "source_authority_sha256": applied["board"]["before"][
                "authority_sha256"
            ],
            "expected_board_revision": applied["board"]["before"]["revision"] + 2,
            "rollback_sha256": "",
        }
        rollback["rollback_sha256"] = _canonical_sha256(
            rollback,
            "rollback_sha256",
        )
        if head == repo_receipt["source_head"]:
            try:
                board_store.validate_project_map_migration_rolled_back(
                    plan,
                    child_plan,
                    applied,
                )
                _atomic_json(
                    rollback_path,
                    rollback,
                    repo=repo,
                    allow_identical=True,
                )
                return rollback
            except board_store.BoardError:
                pass
            _atomic_json(
                rollback_path,
                rollback,
                repo=repo,
                allow_identical=True,
            )
        elif head == repo_receipt["target_head"]:
            board_store.validate_project_map_migration_applied(
                plan,
                child_plan,
                applied,
            )
            _atomic_json(
                rollback_path,
                rollback,
                repo=repo,
                allow_identical=True,
            )
            _reset_exact(repo, repo_receipt["source_head"])
        else:
            raise PlanStoreError(
                "project-map repository is neither the source nor target state"
            )
        try:
            board_store.rollback_project_map_migration(
                plan,
                child_plan,
                applied,
            )
        except (OSError, PlanStoreError, board_store.BoardError):
            current_head = _git_value(
                repo,
                "project-map rollback HEAD",
                "rev-parse",
                "HEAD",
            )
            if current_head != repo_receipt["source_head"]:
                raise PlanStoreError(
                    "project-map rollback failed after another writer changed HEAD"
                )
            _reset_exact(repo, repo_receipt["target_head"])
            raise
        board_store.validate_project_map_migration_rolled_back(
            plan,
            child_plan,
            applied,
        )
        return rollback


def _apply(plan: Path, board: Path | None, expected: str) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    board_before = _read(board, "board") if board is not None else None
    report = store.dry_run_migration(plan, board=board)
    if report.source_sha256 != expected:
        raise PlanStoreError("migration source digest changed; rerun the dry run")
    git_context = _git_context(plan)
    snapshot = store.PlanSnapshot.open(plan)
    # Codex (PR #469, P1): the dry run's digest only names the bytes it read.
    # Machine-local plans have no cleanliness check, so recheck the exact source
    # CAS against the snapshot this transaction will actually migrate.
    if snapshot.is_tree or snapshot.root_sha256 != expected:
        raise PlanStoreError("migration source digest changed; rerun the dry run")
    transaction = store.PlanTransaction.begin(plan, expected_root=expected)
    publication = transaction.replace_content(snapshot.materialize()).publish()
    commit: str | None = None
    try:
        if board is not None and _read(board, "board") != board_before:
            raise PlanStoreError("board changed during migration")
        if git_context is not None:
            commit = _commit_tree(
                git_context[0], git_context[1], "shadow: partition authoritative plan"
            )
    except (OSError, PlanStoreError):
        store.rollback(plan, expected_root=publication.root_sha256)
        if git_context is not None:
            _reset_index(*git_context)
        store.discard_unreachable(plan, publication.new_objects)
        raise
    result = report.as_dict()
    result.update(
        {
            "action": "migrated",
            "writes": publication.object_writes + 1,
            "previous_root_sha256": publication.previous_root_sha256,
            "root_sha256": publication.root_sha256,
            "generation": publication.generation,
            "commit": commit,
            "board_preserved": board is None or _read(board, "board") == board_before,
        }
    )
    return result


def _rollback(plan: Path, board: Path | None, expected: str) -> dict[str, object]:
    plan = Path(os.path.abspath(plan))
    board_before = _read(board, "board") if board is not None else None
    git_context = _git_context(plan)
    original_root = store.PlanSnapshot.open(plan).root_bytes
    receipt = store.rollback(plan, expected_root=expected)
    commit: str | None = None
    try:
        if board is not None and _read(board, "board") != board_before:
            raise PlanStoreError("board changed during rollback")
        if git_context is not None:
            commit = _commit_tree(
                git_context[0], git_context[1], "shadow: roll back partitioned plan"
            )
    except (OSError, PlanStoreError):
        store.restore_exact_root(
            plan,
            expected_current_root=receipt.root_sha256,
            target_root_bytes=original_root,
        )
        if git_context is not None:
            _reset_index(*git_context)
        raise
    return {
        "schema": "shadow.plan-rollback.v1",
        "action": "rolled_back",
        "plan": "PLAN.md",
        "expected_root_sha256": expected,
        "root_sha256": receipt.root_sha256,
        "logical_sha256": receipt.logical_sha256,
        "generation": receipt.generation,
        "commit": commit,
        "board_preserved": board is None or _read(board, "board") == board_before,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="verify a lossless plan-tree migration")
    migrate.add_argument("plan", type=Path)
    mode = migrate.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    migrate.add_argument("--expect")
    migrate.add_argument("--board", type=Path)
    rollback = commands.add_parser("rollback", help="restore the exact previous plan root")
    rollback.add_argument("plan", type=Path)
    rollback.add_argument("--expect", required=True)
    rollback.add_argument("--board", type=Path)
    map_migrate = commands.add_parser(
        "map-migrate",
        help="atomically split one local-only monolith into a root plus one child",
    )
    map_migrate.add_argument("plan", type=Path)
    map_mode = map_migrate.add_mutually_exclusive_group(required=True)
    map_mode.add_argument("--dry-run", action="store_true")
    map_mode.add_argument("--apply", action="store_true")
    map_migrate.add_argument("--target-ref", required=True)
    map_migrate.add_argument("--child", required=True, type=Path)
    map_migrate.add_argument("--expect")
    map_migrate.add_argument("--receipt", type=Path)
    map_rollback = commands.add_parser(
        "map-rollback",
        help="restore one project-map migration from its applied receipt",
    )
    map_rollback.add_argument("plan", type=Path)
    map_rollback.add_argument("--receipt", required=True, type=Path)
    map_rollback.add_argument("--apply", action="store_true", required=True)
    map_rollback.add_argument("--expect", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "map-rollback":
            payload = _rollback_project_map_migration(
                args.plan,
                args.receipt,
                args.expect,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "map-migrate":
            if args.apply:
                if not args.expect or args.receipt is None:
                    parser().error(
                        "map-migrate --apply requires --expect TRANSACTION_SHA256 "
                        "and --receipt /ABS/receipt.json"
                    )
                payload = _apply_project_map_migration(
                    args.plan,
                    args.target_ref,
                    args.child,
                    args.expect,
                    args.receipt,
                )
            else:
                payload = _prepare_project_map_migration(
                    args.plan,
                    args.target_ref,
                    args.child,
                )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "rollback":
            payload = _rollback(args.plan, args.board, args.expect)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.apply:
            if not args.expect:
                parser().error("migrate --apply requires --expect SOURCE_SHA256")
            payload = _apply(args.plan, args.board, args.expect)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        report = store.dry_run_migration(args.plan, board=args.board)
    except (PlanStoreError, board_store.BoardError) as exc:
        print(f"shadow plan {args.command}: {exc}", file=sys.stderr)
        return 3 if "changed during dry run" in str(exc) else 2
    if (
        not report.exact_materialization
        or not report.routes_rebuilt
        or report.query_mismatches
    ):
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return 2
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
